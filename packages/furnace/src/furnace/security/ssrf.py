"""SSRF protection for every outbound request to a user-supplied URL.

- http/https only, no credentials in the URL
- hostname resolved once; every resolved address must be public
- the connection is pinned to the validated IP (defeats DNS rebinding); TLS SNI
  and certificate verification still use the hostname
- redirects are not followed automatically; callers re-validate each hop
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

_BLOCKED_NETS = [
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",  # CGNAT
        "127.0.0.0/8",
        "169.254.0.0/16",  # link-local incl. cloud metadata 169.254.169.254
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.0.2.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "198.51.100.0/24",
        "203.0.113.0/24",
        "224.0.0.0/4",
        "240.0.0.0/4",
        "255.255.255.255/32",
        "::/128",
        "::1/128",
        "::ffff:0:0/96",  # IPv4-mapped: checked via the mapped address below
        "64:ff9b::/96",
        "100::/64",
        "fc00::/7",
        "fe80::/10",
        "ff00::/8",
    )
]


class UnsafeURL(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedURL:
    url: str
    scheme: str
    host: str
    port: int
    ip: str


def is_public_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return not any(addr in net for net in _BLOCKED_NETS if net.version == addr.version)


def validate_url(url: str, *, allow_private: bool = False) -> ValidatedURL:
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        raise UnsafeURL("only http and https URLs are allowed")
    if parts.username or parts.password:
        raise UnsafeURL("credentials in URLs are not allowed")
    host = parts.hostname
    if not host:
        raise UnsafeURL("URL has no host")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURL(f"cannot resolve {host}") from exc
    ips = sorted({str(info[4][0]) for info in infos})
    if not ips:
        raise UnsafeURL(f"cannot resolve {host}")
    if not allow_private:
        bad = [ip for ip in ips if not is_public_ip(ip)]
        if bad:
            raise UnsafeURL(f"{host} resolves to a non-public address")
    return ValidatedURL(url=url, scheme=parts.scheme, host=host, port=port, ip=ips[0])


class PinnedTransport(httpx.AsyncHTTPTransport):
    """Connects to the pre-validated IP while keeping Host header and TLS SNI."""

    def __init__(self, validated: ValidatedURL, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._v = validated

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != self._v.host:
            raise UnsafeURL("request host does not match the validated host")
        ip = self._v.ip
        ip_host = f"[{ip}]" if ":" in ip else ip
        request.extensions = {**request.extensions, "sni_hostname": self._v.host}
        request.headers["Host"] = request.url.netloc.decode()
        request.url = request.url.copy_with(host=ip_host.strip("[]"))
        return await super().handle_async_request(request)


async def safe_get(
    url: str, *, max_bytes: int = 5 * 2**20, timeout_s: float = 15.0, max_redirects: int = 3
) -> httpx.Response:
    """GET a user-supplied URL with SSRF checks on every redirect hop and a body cap."""
    current = url
    for _ in range(max_redirects + 1):
        v = validate_url(current)
        transport = PinnedTransport(v)
        async with (
            httpx.AsyncClient(transport=transport, timeout=timeout_s) as client,
            client.stream("GET", current) as resp,
        ):
            if resp.is_redirect and "location" in resp.headers:
                # Resolve against the hostname URL (resp.url carries the pinned IP).
                current = str(httpx.URL(current).join(resp.headers["location"]))
                continue
            body = bytearray()
            async for chunk in resp.aiter_bytes():
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise UnsafeURL(f"response larger than {max_bytes} bytes")
            return httpx.Response(
                resp.status_code, headers=resp.headers, content=bytes(body), request=resp.request
            )
    raise UnsafeURL("too many redirects")

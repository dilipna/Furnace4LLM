"""Bounded literal-loopback chat endpoint. Never loads model code.

User-operated servers are called without credentials. A server Furnace operates
is called with its per-launch key, which callers keep in memory only.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import socket
import threading
import time
import uuid
from typing import Any
from urllib.parse import urlsplit

from furnace.runtime.manager import RuntimeFault

MAX_RESPONSE = 262144
MAX_OUTPUT_CHARS = 16000
MAX_TIMEOUT_SECONDS = 120


def endpoint_port(base_url: str) -> int:
    try:
        url = urlsplit(base_url)
        port = url.port
        valid = (
            url.scheme == "http"
            and url.hostname == "127.0.0.1"
            and url.netloc == f"127.0.0.1:{port}"
            and port is not None
            and 1024 <= port <= 65535
            and url.path == "/v1"
            and not url.query
            and not url.fragment
            and base_url == f"http://127.0.0.1:{port}/v1"
        )
    except ValueError:
        valid, port = False, None
    if not valid or port is None:
        raise RuntimeFault("use_http_127_0_0_1_port_v1")
    return port


class LocalChatEndpoint:
    def request(
        self,
        base_url: str,
        path: str,
        timeout: float,
        data: dict | None = None,
        api_key: str | None = None,
    ) -> dict:
        port = endpoint_port(base_url)
        if path not in {"/models", "/chat/completions"}:
            raise RuntimeFault("endpoint_path_refused")
        if not 0 < timeout <= MAX_TIMEOUT_SECONDS:
            raise RuntimeFault("invalid_endpoint_timeout")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if api_key is not None:
            headers["Authorization"] = f"Bearer {api_key}"
        # Literal IP, no DNS, environment proxies, redirects or cookies.
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
        expired = threading.Event()
        active_socket: socket.socket | None = None

        def abort() -> None:
            expired.set()
            if active_socket is not None:
                with contextlib.suppress(OSError):
                    active_socket.shutdown(socket.SHUT_RDWR)
            # Leave HTTPConnection state to its owning thread. Concurrent close()
            # clears .sock while request/getresponse may still be using it.

        timer = threading.Timer(timeout, abort)
        timer.daemon = True
        timer.start()
        try:
            connection.connect()
            active_socket = connection.sock
            if expired.is_set():
                raise RuntimeFault("endpoint_timeout")
            connection.request(
                "POST" if data is not None else "GET",
                "/v1" + path,
                body=json.dumps(data).encode() if data is not None else None,
                headers=headers,
            )
            response = connection.getresponse()
            if response.status != 200:
                # Never include arbitrary upstream bodies/headers in logs or errors.
                raise RuntimeFault(f"endpoint_http_{response.status}")
            if response.getheader("Content-Type", "").split(";")[0].strip() != "application/json":
                raise RuntimeFault("endpoint_json_required")
            raw = response.read(MAX_RESPONSE + 1)
            if expired.is_set():
                raise RuntimeFault("endpoint_timeout")
            if len(raw) > MAX_RESPONSE:
                raise RuntimeFault("endpoint_response_too_large")
            result = json.loads(raw.decode("utf-8"))
            if not isinstance(result, dict):
                raise RuntimeFault("endpoint_invalid_response")
            return result
        except (OSError, http.client.HTTPException, ValueError):
            raise RuntimeFault(
                "endpoint_timeout" if expired.is_set() else "endpoint_unavailable_or_invalid"
            ) from None
        finally:
            timer.cancel()
            connection.close()

    def check(self, config: dict[str, Any], api_key: str | None = None) -> None:
        response = self.request(
            config["base_url"], "/models", config["timeout_seconds"], api_key=api_key
        )
        models = response.get("data")
        if not isinstance(models, list) or not any(
            isinstance(item, dict) and item.get("id") == config["model_id"] for item in models
        ):
            raise RuntimeFault("configured_model_not_advertised")

    def predict(
        self,
        config: dict[str, Any],
        value: str,
        timeout: float,
        api_key: str | None = None,
        *,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        began = time.monotonic()
        response = self.request(
            config["base_url"],
            "/chat/completions",
            timeout,
            {
                "model": config["model_id"],
                "messages": (
                    [{"role": "system", "content": system_prompt}] if system_prompt else []
                )
                + [{"role": "user", "content": value}],
                "stream": False,
                "temperature": 0,
                "max_tokens": config["max_tokens"],
            },
            api_key=api_key,
        )
        try:
            choices = response["choices"]
            if (
                response.get("model") != config["model_id"]
                or not isinstance(choices, list)
                or len(choices) != 1
            ):
                raise ValueError
            output = choices[0]["message"]["content"]
            finish = choices[0]["finish_reason"]
            if not isinstance(output, str) or not output.strip() or len(output) > MAX_OUTPUT_CHARS:
                raise ValueError
            # JSON escapes can decode to lone surrogates: reject before hashing,
            # persistence or HTTP serialization can leave an attempt stuck running.
            output.encode("utf-8")
            if finish not in {"stop", "length"}:
                raise ValueError
        except (KeyError, TypeError, ValueError, IndexError):
            raise RuntimeFault("endpoint_invalid_or_mismatched_completion") from None
        return {
            "output": output,
            "finish_reason": finish,
            "model_id": response["model"],
            "request_id": uuid.uuid4().hex,
            "duration_ms": round((time.monotonic() - began) * 1000),
            "usage": _numbers(response.get("usage"), ("prompt_tokens", "completion_tokens")),
            "server_timings": _numbers(
                response.get("timings"), ("prompt_ms", "predicted_ms", "predicted_per_second")
            ),
            "execution_kind": "local_endpoint_response",
            "model_identity_independently_verified": False,
        }


def _numbers(value: Any, keys: tuple[str, ...]) -> dict[str, float]:
    """Server-reported counters, kept only when they are plain finite numbers."""
    if not isinstance(value, dict):
        return {}
    return {
        key: round(float(value[key]), 3)
        for key in keys
        if isinstance(value.get(key), int | float)
        and not isinstance(value.get(key), bool)
        and abs(float(value[key])) < 1e12
    }

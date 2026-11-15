"""Bounded, unauthenticated literal-loopback chat endpoint. Never loads model code."""

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

MAX_RESPONSE = 65536


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
    def request(self, base_url: str, path: str, timeout: float, data: dict | None = None) -> dict:
        port = endpoint_port(base_url)
        if path not in {"/models", "/chat/completions"}:
            raise RuntimeFault("endpoint_path_refused")
        if not 0 < timeout <= 10:
            raise RuntimeFault("invalid_endpoint_timeout")
        # Literal IP, no DNS, environment proxies, redirects, cookies or credentials.
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
        expired = threading.Event()
        active_socket: socket.socket | None = None

        def abort() -> None:
            expired.set()
            if active_socket is not None:
                with contextlib.suppress(OSError):
                    active_socket.shutdown(socket.SHUT_RDWR)
            connection.close()

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
                headers={"Content-Type": "application/json", "Accept": "application/json"},
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

    def check(self, config: dict[str, Any]) -> None:
        response = self.request(config["base_url"], "/models", config["timeout_seconds"])
        models = response.get("data")
        if not isinstance(models, list) or not any(
            isinstance(item, dict) and item.get("id") == config["model_id"] for item in models
        ):
            raise RuntimeFault("configured_model_not_advertised")

    def predict(self, config: dict[str, Any], value: str, timeout: float) -> dict[str, Any]:
        began = time.monotonic()
        response = self.request(
            config["base_url"],
            "/chat/completions",
            timeout,
            {
                "model": config["model_id"],
                "messages": [{"role": "user", "content": value}],
                "stream": False,
                "temperature": 0,
                "max_tokens": config["max_tokens"],
            },
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
            if not isinstance(output, str) or not output.strip() or len(output) > 8000:
                raise ValueError
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
            "execution_kind": "local_endpoint_response",
            "model_identity_independently_verified": False,
        }

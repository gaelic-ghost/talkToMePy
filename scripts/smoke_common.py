from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _decode_response_body(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return raw


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, str], Any]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url=url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return resp.status, dict(resp.headers.items()), _decode_response_body(raw)
    except HTTPError as exc:
        raw = exc.read()
        return exc.code, dict(exc.headers.items()), _decode_response_body(raw)
    except URLError as exc:
        raise RuntimeError(f"Request failed for {method} {url}: {exc}") from exc


def request_binary(
    method: str,
    url: str,
    payload: dict[str, Any],
    timeout: float = 120.0,
) -> tuple[int, dict[str, str], bytes]:
    req = Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "audio/wav,application/json",
        },
        method=method,
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers.items()), resp.read()
    except HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()
    except URLError as exc:
        raise RuntimeError(f"Binary request failed for {method} {url}: {exc}") from exc


def ensure_healthy(base_url: str, timeout_seconds: int = 120) -> None:
    deadline = time.time() + timeout_seconds
    last_error: str | None = None
    while time.time() < deadline:
        try:
            status, _, payload = request_json("GET", f"{base_url}/health", timeout=5.0)
            if status == 200 and isinstance(payload, dict) and payload.get("status") == "ok":
                return
            last_error = f"unexpected /health status={status} payload={payload}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"Service did not become healthy: {last_error}")


def load_mode_and_wait(base_url: str, mode: str, timeout_seconds: int = 600) -> dict[str, Any]:
    status, _, payload = request_json(
        "POST",
        f"{base_url}/model/load",
        payload={"mode": mode, "strict_load": False},
        timeout=30.0,
    )
    if status not in (200, 202):
        raise RuntimeError(f"/model/load failed for mode={mode}: status={status} payload={payload}")

    deadline = time.time() + timeout_seconds
    last_payload: Any = None
    while time.time() < deadline:
        status, _, payload = request_json("GET", f"{base_url}/model/status", timeout=10.0)
        last_payload = payload
        if status == 200 and isinstance(payload, dict):
            if payload.get("loading") is False and payload.get("loaded") is True and payload.get("mode") == mode:
                return payload
        time.sleep(2)

    raise RuntimeError(f"Timed out waiting for mode load={mode}. Last model status: {last_payload}")


def assert_wav_response(status: int, headers: dict[str, str], body: bytes, endpoint: str) -> None:
    if status != 200:
        body_text = body.decode("utf-8", errors="replace")
        raise RuntimeError(f"{endpoint} failed status={status} body={body_text}")

    content_type = headers.get("Content-Type", headers.get("content-type", ""))
    if not content_type.startswith("audio/wav"):
        raise RuntimeError(f"{endpoint} returned unexpected content-type: {content_type}")

    if len(body) < 44:
        raise RuntimeError(f"{endpoint} returned unexpectedly short WAV payload ({len(body)} bytes)")

    if body[:4] != b"RIFF" or body[8:12] != b"WAVE":
        raise RuntimeError(f"{endpoint} response is not a valid RIFF/WAVE header")

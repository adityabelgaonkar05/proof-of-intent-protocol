"""
Thin Python wrapper over the AXL node's local HTTP API.

Each agent runs its own AXL node bound to a distinct `api_port`
(see agents/axl_configs/*.json). All peer-to-peer routing happens
inside the AXL Yggdrasil network — Python only talks to localhost.

Endpoints used:
    GET  /topology   → {"our_public_key": "...", "our_ipv6": "...", ...}
    POST /send       → header X-Destination-Peer-Id, body raw bytes
    GET  /recv       → 204 if empty, else 200 with X-From-Peer-Id header
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request


class AXLTimeout(TimeoutError):
    """Raised when listen_for_message exhausts its timeout with no message."""


def _api_base(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def get_public_key(port: int = 9002) -> str:
    """Return this node's hex-encoded ed25519 public key from /topology."""
    with urllib.request.urlopen(f"{_api_base(port)}/topology", timeout=5) as resp:
        return json.loads(resp.read())["our_public_key"]


def send_message(
    to_pubkey: str,
    message: dict,
    port: int = 9002,
    retries: int = 5,
    backoff: float = 1.0,
) -> None:
    """
    Fire-and-forget JSON message to the AXL node identified by `to_pubkey`.

    `message` is JSON-encoded into the POST body. AXL itself treats the body
    as opaque bytes; we standardize on JSON across all of our agents.

    The first send after node startup can return 502 while the Yggdrasil
    spanning tree is still propagating routes — retry on 502/503 with
    linear backoff.
    """
    body = json.dumps(message).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(
            f"{_api_base(port)}/send",
            data=body,
            method="POST",
            headers={
                "X-Destination-Peer-Id": to_pubkey,
                "Content-Type": "application/octet-stream",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return
                raise RuntimeError(f"AXL /send returned {resp.status}")
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code in (502, 503) and attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
                continue
            raise
    if last_err is not None:
        raise last_err


def listen_for_message(timeout: int, port: int = 9002, poll_interval: float = 0.2) -> dict:
    """
    Poll /recv until a message arrives or `timeout` seconds elapse.

    Returns a dict with keys:
        from:    sender's hex public key (from X-From-Peer-Id)
        message: the decoded JSON payload

    Raises AXLTimeout on timeout.
    """
    deadline = time.time() + timeout
    url = f"{_api_base(port)}/recv"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 204:
                    time.sleep(poll_interval)
                    continue
                if resp.status == 200:
                    body = resp.read()
                    sender = resp.headers.get("X-From-Peer-Id", "")
                    return {"from": sender, "message": json.loads(body)}
                raise RuntimeError(f"AXL /recv returned {resp.status}")
        except urllib.error.URLError:
            time.sleep(poll_interval)
    raise AXLTimeout(f"No AXL message received within {timeout}s on port {port}")

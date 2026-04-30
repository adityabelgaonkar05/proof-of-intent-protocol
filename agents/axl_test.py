"""
End-to-end AXL P2P test.

Boots two local AXL nodes (orchestrator on :9002 and research on :9012),
waits for the Yggdrasil mesh to converge, then has the orchestrator send
a JSON message to research's public key and confirms it arrives intact.

Usage:
    python -m agents.axl_test

Prerequisites:
    vendor/axl/node             — built binary
    agents/keys/*.key           — ed25519 identity keys
    agents/axl_configs/*.json   — node configs
"""

from __future__ import annotations

import os
import pathlib
import sys as _sys
if __package__ is None:
    _sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

from utils.axl_client import (
    AXLTimeout,
    get_public_key,
    listen_for_message,
    send_message,
)

_ROOT     = pathlib.Path(__file__).parent.parent
_NODE_BIN = _ROOT / "vendor" / "axl" / "node"
_CONFIGS  = _ROOT / "agents" / "axl_configs"


def _wait_for_api(port: int, timeout: float = 15.0) -> None:
    """Block until /topology responds 200, or raise."""
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/topology"
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            last_err = exc
        time.sleep(0.2)
    raise RuntimeError(f"Node on port {port} did not come up: {last_err}")


def _start_node(config_filename: str, log_path: pathlib.Path) -> subprocess.Popen:
    """Start an AXL node with the given config; pipe stderr/stdout to a logfile."""
    log = log_path.open("w")
    return subprocess.Popen(
        [str(_NODE_BIN), "-config", str(_CONFIGS / config_filename)],
        cwd=str(_ROOT),
        stdout=log,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,  # so we can kill the whole process group
    )


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


def main() -> int:
    if not _NODE_BIN.exists():
        print(f"AXL node binary not found at {_NODE_BIN}. Run the build first.")
        return 1

    log_dir = _ROOT / "agents" / "axl_logs"
    log_dir.mkdir(exist_ok=True)

    print("[1] Starting orchestrator node (api 9002, listen 9001)...")
    orch = _start_node("orchestrator.json", log_dir / "orchestrator.log")
    _wait_for_api(9002)
    orch_pubkey = get_public_key(9002)
    print(f"    orchestrator pubkey = {orch_pubkey}")

    research = None
    try:
        print("[2] Starting research node (api 9012, peers→9001)...")
        research = _start_node("research.json", log_dir / "research.log")
        _wait_for_api(9012)
        research_pubkey = get_public_key(9012)
        print(f"    research pubkey     = {research_pubkey}")

        # Yggdrasil takes a moment to converge after the peer link comes up
        print("[3] Waiting for mesh to converge...")
        time.sleep(3)

        message = {"test": "hello from orchestrator", "delegationId": "0xabc"}
        print(f"[4] Orchestrator → research: {message}")
        send_message(research_pubkey, message, port=9002)

        print("[5] Polling research /recv (timeout 15s)...")
        received = listen_for_message(timeout=15, port=9012)

        print(f"    received from: {received['from']}")
        print(f"    payload:       {received['message']}")

        assert received["message"] == message, (
            f"Payload mismatch: sent {message!r}, got {received['message']!r}"
        )
        # AXL's X-From-Peer-Id is the Yggdrasil prefix-masked form of the
        # sender's public key — the leading bytes match the full pubkey,
        # the trailing bytes are 0xff padding. Compare only the prefix.
        masked = received["from"].rstrip("f")
        assert orch_pubkey.startswith(masked) and len(masked) >= 24, (
            f"Sender prefix mismatch: expected pubkey {orch_pubkey} to start "
            f"with {masked!r}"
        )

        print("\nAXL end-to-end P2P communication confirmed.")
        return 0

    except AXLTimeout as exc:
        print(f"\nAXL test FAILED: {exc}")
        print("Check agents/axl_logs/*.log for node startup/peering errors.")
        return 1

    finally:
        if research is not None:
            _stop(research)
        _stop(orch)


if __name__ == "__main__":
    sys.exit(main())

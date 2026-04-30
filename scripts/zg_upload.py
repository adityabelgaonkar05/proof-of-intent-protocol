"""
Standalone 0G storage upload helper.

Reads JSON metadata from stdin, uploads to 0G Newton testnet, prints the
rootHash to stdout. Designed to be invoked as a subprocess so it runs in
an isolated Python namespace without conflicting with the project's own
`config` and `utils` packages (which share names with 0g-storage-sdk).

Usage (internal — called by utils/contract_client.py):
    python scripts/zg_upload.py <ZG_API_KEY> <ZG_RPC_URL> <ZG_INDEXER_URL>
    # JSON metadata piped via stdin
    # Outputs: rootHash on success, ERROR:<msg> on failure
"""
import sys, os

# Strip any project-root entries from sys.path so the 0g-sdk's own `utils`,
# `config`, `core`, and `contracts` packages resolve from site-packages
# rather than from our project directory.
_this_dir = os.path.dirname(os.path.abspath(__file__))
_proj_root = os.path.dirname(_this_dir)
sys.path = [
    p for p in sys.path
    if p not in ("", _proj_root, _this_dir)
    and not (os.path.isabs(p) and p == _proj_root)
]

def main():
    if len(sys.argv) != 4:
        print("ERROR:usage: zg_upload.py <key> <rpc> <indexer>", flush=True)
        sys.exit(1)

    api_key, rpc_url, indexer_url = sys.argv[1], sys.argv[2], sys.argv[3]
    payload_bytes = sys.stdin.buffer.read()

    try:
        from eth_account import Account
        from core.indexer import Indexer
        from core.file import ZgFile
    except ImportError as e:
        print(f"ERROR:{e}", flush=True)
        sys.exit(1)

    try:
        account = Account.from_key(api_key)
        file = ZgFile.from_bytes(payload_bytes)
        indexer = Indexer(indexer_url)
        upload_opts = {
            "tags": b"\x00",
            "finalityRequired": True,
            "taskSize": 10,
            "expectedReplica": 1,
            "skipTx": False,
            "fee": 0,
            "account": account,
        }
        result, err = indexer.upload(file, rpc_url, account, upload_opts)
        if err is not None:
            print(f"ERROR:{err}", flush=True)
            sys.exit(1)
        ref = result.get("rootHash") or result.get("txHash") or ""
        print(ref, flush=True)
    except Exception as exc:
        print(f"ERROR:{exc}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

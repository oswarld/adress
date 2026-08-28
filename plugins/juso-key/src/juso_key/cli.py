"""Command-line interface for direct verification outside an MCP client."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from .contract import verify_address_with_client, verify_live_address

DEFAULT_INDEX_ENV = "JUSO_BULK_INDEX"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="juso-key")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser(
        "verify", help="find and verify a Korean address, postal code, and English address"
    )
    verify.add_argument("address")
    verify.add_argument(
        "--offline",
        action="store_true",
        help="resolve against a local bulk-dataset index instead of the search API",
    )
    verify.add_argument(
        "--index",
        type=Path,
        default=None,
        help=f"path to the bulk index (default: ${DEFAULT_INDEX_ENV})",
    )

    build = subparsers.add_parser(
        "build-index", help="index the downloaded bulk address datasets into SQLite"
    )
    build.add_argument("--address-dir", type=Path, required=True)
    build.add_argument("--english-dir", type=Path, default=None)
    build.add_argument("--out", type=Path, required=True)
    return parser.parse_args(argv)


def resolve_index_path(explicit: Path | None) -> Path | None:
    if explicit:
        return explicit
    from_env = os.environ.get(DEFAULT_INDEX_ENV, "")
    return Path(from_env) if from_env else None


def run_verify(args: argparse.Namespace) -> int:
    if args.offline:
        index_path = resolve_index_path(args.index)
        if not index_path:
            print(
                f"--index or ${DEFAULT_INDEX_ENV} is required for offline verification",
                file=sys.stderr,
            )
            return 2
        if not index_path.exists():
            print(f"index not found: {index_path}", file=sys.stderr)
            return 2
        from .bulk import BulkSearchClient

        with BulkSearchClient(index_path) as client:
            result = verify_address_with_client(args.address, client)
    else:
        approval_key = os.environ.get("JUSO_API_KEY", "")
        if not approval_key:
            print("JUSO_API_KEY is required", file=sys.stderr)
            return 2
        result = verify_live_address(args.address, approval_key)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def run_build_index(args: argparse.Namespace) -> int:
    from .bulk import build_index

    report = build_index(
        address_dir=args.address_dir,
        english_dir=args.english_dir,
        db_path=args.out,
        progress=lambda message: print(message, file=sys.stderr, flush=True),
    )
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "build-index":
            return run_build_index(args)
        return run_verify(args)
    except (OSError, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

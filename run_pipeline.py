from __future__ import annotations

import argparse
from pathlib import Path

import build_indices
import cleanup_outputs
import crawl_source
import detect_relations
import discover_sources
import normalize_archive


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full archive pipeline.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--families", nargs="*", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--discover-limit", type=int, default=None)
    parser.add_argument("--download-limit", type=int, default=None)
    parser.add_argument("--clean", action="store_true", help="Remove generated outputs before running.")
    parser.add_argument("--clean-only", action="store_true", help="Remove generated outputs and exit.")
    args = parser.parse_args()

    families = set(args.families) if args.families else None

    if args.clean or args.clean_only:
        cleanup_outputs.clean_outputs(args.root, families)
        if args.clean_only:
            return 0

    discover_sources.discover_documents(args.root, families, args.dry_run, args.discover_limit)
    crawl_source.crawl_documents(args.root, families, args.dry_run, args.download_limit)
    normalize_archive.normalize(args.root, families, args.dry_run, None)
    detect_relations.detect(args.root, families)
    build_indices.build(args.root, families)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

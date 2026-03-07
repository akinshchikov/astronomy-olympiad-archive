# Publishing Notes

This repository is prepared for a public GitHub release as a reproducible pipeline plus lightweight metadata.

## Intended Public Content

- Python pipeline code
- `README.md`
- `data/manifests/source_candidates.csv`
- `data/manifests/discovered_documents.jsonl`
- `data/manifests/discovery_coverage.csv`
- `data/indices/olympiads_index.csv`
- `data/indices/files_index.csv`
- `data/indices/relation_groups.csv`
- `data/indices/coverage_report.md`

## Intentionally Excluded by `.gitignore`

- `data/raw/`
- `data/archive/`
- `data/logs/`
- local/manually derived manifests with absolute paths

## Why

- The full local archive is large.
- Public availability of a source URL is not the same thing as permission to republish mirrored binaries through GitHub.
- The public repo should stay lightweight and reproducible.

## Before Creating the GitHub Repo

1. Initialize git after the current `.gitignore` is in place.
2. Keep the `MIT` code license in [`LICENSE`](LICENSE) unless you intentionally want a different licensing model.
3. Do not add `data/raw/`, `data/archive/`, or `data/logs/`.
4. If you later want to publish binaries, review redistribution terms per source first.

## Recommended Release Model

- GitHub repository: code + manifests + indices
- Local/private storage: raw files and normalized archive
- Optional later addition: a separate downloader-friendly mirror manifest, not the binaries themselves

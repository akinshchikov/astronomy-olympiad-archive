# Publishing Notes

This repository publishes a reproducible pipeline and lightweight metadata, not a
mirror of olympiad binaries. A public source URL or a successful local download does
not itself grant permission to redistribute that file.

## Intended public content

- Python pipeline code, tests, and documentation.
- `README.md`, `README.ru.md`, and this policy.
- Source and discovery metadata: `data/manifests/source_candidates.csv`,
  `data/manifests/discovered_documents.jsonl`, and
  `data/manifests/discovery_coverage.csv`.
- Lightweight public indices: `data/indices/olympiads_index.csv`,
  `data/indices/files_index.csv`, `data/indices/relation_groups.csv`, and
  `data/indices/coverage_report.md`.
- The durable source-status record
  `data/audits/global_expansion_batch_c.csv`.
- Release notes and automatically generated GitHub source-code archives.

## Always local and ignored

- `data/raw/`, `data/archive/`, and `data/logs/`.
- `data/manual/`, including manually obtained OWAO files and its local manifest.
- `data/manifests/download_manifest.jsonl`,
  `data/manifests/download_checkpoint.jsonl`,
  `data/manifests/normalized_entries.jsonl`, and
  `data/manifests/relation_edges.jsonl`.
- Raw downloads, normalized PDFs, ZIPs, DOC/DOCX files, locally extracted ZIP
  members, object-store files, checkpoints, logs, temporary HTML, and any manifest
  containing local absolute paths.

The public GitHub release must not attach those files. GitHub's normal source-code
archives are sufficient release assets.

## Source status and roles

The Batch C audit distinguishes `INGESTED_PARTIAL`, `ACTIVE_DISCOVERY_ONLY`,
`CONDITIONAL_UNRESOLVED`, and `DEFERRED_NO_RELIABLE_ARCHIVE`. Discovery-only,
form-gated, robots-blocked, policy-blocked, unavailable, or deferred records retain
provenance; they do not represent downloaded coverage and must not be bypassed.

`official`, `mirror`, and archive roles are metadata, not interchangeable claims of
authority. In particular, Iran's Batch C source is a mirror; Israel Space Agency
provenance does not make Multi-Space authoritative; and provincial Chinese contests
are not CNAO. Preserve family boundaries such as Poland senior/junior, Sri Lanka
senior/junior, the three Slovenia lineages, BAO/BDOAA, and Macao/CNAO.

## Redistribution and access boundaries

- INAO/HBCSE papers and solutions retain
  `redistribution_status=explicit-no-redistribution` and stay local.
- Protected Czech material, interactive rounds, login gates, and form-gated files
  are not targets for authentication or access-control workarounds.
- External Drive links that crawler policy cannot fetch remain discovery-only.
- Croatia ZIP containers may be safely expanded only into the local archive after
  bounded validation; their extracted members are never release assets.
- A file being publicly reachable is not evidence of a license to republish it.

## Release checklist

1. Keep the working tree free of generated binaries, logs, checkpoints, and local
   manifests.
2. Run `python3 -m unittest discover -s tests -q` and `git diff --check`.
3. Confirm committed public counts are derived from the tracked manifests and
   indices; do not hand-edit generated coverage facts.
4. Publish only code, lightweight metadata, documentation, and release notes.
5. If a future release changes source availability, record its actual state rather
   than treating discovery as permission or completeness.

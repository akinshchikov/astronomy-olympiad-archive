# Publishing Notes

This repository publishes a reproducible pipeline and lightweight metadata by
default, not a general mirror of olympiad binaries. A public source URL or a
successful local download does not itself grant permission to redistribute that
file.

A narrow preservation exception is documented below for small, bounded historical
corpora whose original public publication has disappeared for technical reasons and
whose redistribution is explicitly permitted. Those files live only under
`data/preserved/` and are treated as source inputs, not as a precedent for mirroring
ordinary downloads.

## Intended public content

- Python pipeline code, tests, and documentation.
- `README.md`, `README.ru.md`, and this policy.
- Source and discovery metadata: `data/manifests/source_candidates.csv`,
  `data/manifests/discovered_documents.jsonl`, and
  `data/manifests/discovery_coverage.csv`.
- Lightweight public indices: `data/indices/olympiads_index.csv`,
  `data/indices/collections_index.csv`, `data/indices/files_index.csv`,
  `data/indices/relation_groups.csv`, and `data/indices/coverage_report.md`.
- The repository-wide source coverage catalog
  `data/audits/source_coverage.csv` and `data/config/family_metadata.csv`, used by
  the generated coverage report.
- Release notes and automatically generated GitHub source-code archives.
- Bounded historical source files under `data/preserved/` only when they satisfy
  the preserved-publication exception below.

## Always local and ignored

- `data/raw/`, `data/archive/`, and `data/logs/`.
- `data/manual/`, including manually obtained OWAO files and its local manifest.
- `data/manifests/download_manifest.jsonl`,
  `data/manifests/download_checkpoint.jsonl`,
  `data/manifests/normalized_entries.jsonl`, and
  `data/manifests/relation_edges.jsonl`.
- Raw downloads, normalized PDFs, ZIPs, DOC/DOCX files, locally extracted ZIP
  members, object-store files, checkpoints, logs, temporary HTML, and any manifest
  containing local absolute paths, except for explicitly approved files below
  `data/preserved/`.

The public GitHub release must not attach those files. GitHub's normal source-code
archives are sufficient release assets.

## Preserved-publication exception

A binary source file may be committed below `data/preserved/` only when all of the
following are true:

1. The material is directly within the archive's competition scope and was
   intentionally published for public access in the past.
2. The original/current public hosting has disappeared for technical or archival
   reasons, rather than because of a login gate, takedown, redistribution
   restriction, robots policy, or other access-control boundary.
3. Redistribution of the exact material is explicitly permitted by the organizer,
   author, or other relevant rights holder, or an equivalent documented
   public-redistribution grant exists.
4. Provenance is clear enough to identify the competition and publication history.
   Private correspondence may support that provenance internally, but is not
   committed merely to prove permission.
5. The preservation set is small and bounded. A tracked manifest records the
   repository path, year/context, byte size, and SHA-256 of every committed binary.

Preserved files are ingested directly from the checked-out repository and must pass
the same signature/integrity checks as downloaded inputs. They are not copied into
GitHub Release assets separately; the normal source-code archive already contains
them.

The first use of this exception is the Russian Open Correspondence School Astronomy
Olympiad corpus for 2005–2008: four Russian tasks-with-solutions PDFs that were
historically public, later disappeared from public hosting for technical reasons,
and are explicitly permitted for republication. The private correspondence used to
confirm provenance is intentionally not part of the repository.

This exception is reusable for genuinely similar lost-publication cases. It must not
be used merely because a file was once reachable on the web.

## Independent coverage dimensions

The source catalog records local content state (`indexed`, `metadata_only`,
`unresolved`, or `deferred`) independently from archive completeness, current access,
source provenance, and redistribution restrictions. These fields describe current
evidence and may be revisited; they do not rank olympiad families.

Metadata-only, form-gated, robots-blocked, policy-blocked, unavailable, or deferred
records retain provenance; they do not represent downloaded coverage and must not be
bypassed. Partial archives and sample-only coverage are not claims about the full
competition history.

`official`, `mirror`, and archive roles are metadata, not interchangeable claims of
authority. In particular, Iran's catalogued source is a mirror; Israel Space Agency
provenance does not make Multi-Space authoritative; and provincial Chinese contests
are not CNAO. Preserve family boundaries such as Poland senior/junior, Sri Lanka
senior/junior, the three Slovenia lineages, BAO/BDOAA, and Macao/CNAO.

## Public collections and training publications

Official olympiad sources may expose problem books, solved-problem collections,
training sets, observation exercises, study notes, or reference material that span
several competition years. The pipeline may catalogue and download those public
documents into the normal local archive. They use `record_kind=collection` and are
indexed separately in `data/indices/collections_index.csv`; they must not create
synthetic competition years or gaps in `olympiads_index.csv`.

A public collection link is an acquisition source, not permission to republish the
binary. Ordinary collection PDFs remain local under the same rules as competition
papers. Purchase-only listings are not crawl targets. General books or recommended
external literature are not pulled merely because an olympiad page mentions them;
the collection source must itself be a bounded public olympiad/organizer resource.

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
3. Confirm committed public counts are derived from the tracked repository-wide
   manifests and indices; do not hand-edit generated coverage facts. Focused
   `--families` runs are local validation and must not replace this public snapshot.
4. Publish only code, lightweight metadata, documentation, release notes, and
   explicitly approved `data/preserved/` files that satisfy the exception above.
5. Verify every preserved binary against its tracked byte size and SHA-256 manifest.
6. If a future release changes source availability, record its actual state rather
   than treating discovery as permission or completeness.

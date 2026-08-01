# AGENTS.md

## Purpose and public boundary

This repository builds a reproducible local archive from public astronomy-olympiad
sources. GitHub contains code and lightweight metadata only, never a mirror of
downloaded binaries. Every olympiad family is first-class. Coverage fields describe
current source evidence and acquisition state, not the value of a competition. The
repository-wide source catalog is `data/audits/source_coverage.csv`; the generated
family view is in `data/indices/coverage_report.md`.

Core stages are `discover_sources.py`, `crawl_source.py`,
`import_manual_files.py`, `normalize_archive.py`, `detect_relations.py`,
`build_indices.py`, `run_pipeline.py`, and `cleanup_outputs.py`. Shared helpers are
in `utils/`; tests are in `tests/`.

## Source boundaries

- Use public URLs, respect `robots.txt`, and never bypass login, form, paywall, or
  anti-bot controls. Record a bounded failure and continue with other sources.
- `metadata_only`, `unresolved`, and `deferred` catalog rows are durable provenance,
  not automatic runtime ingestion targets. Incompleteness and access limitations are
  revisitable source states.
- Preserve source roles (`official`, `mirror`, archive) and competition boundaries:
  Poland senior/junior; Sri Lanka senior/junior; Slovenia high-school/primary/Utrinek;
  BAO/BDOAA; Macao/CNAO; and CNAO/provincial contests are distinct. Iran's source is
  a mirror, and an Israel Space Agency page does not make Multi-Space authoritative.
- Nepal sample/practice files do not prove historic national-round coverage. INAO
  retains `redistribution_status=explicit-no-redistribution`; protected Czech
  material remains a discovery gap.
- For external hosts, a discovered extension is not proof of file type. Validate the
  HTTP response/signature before storing a PDF or archive.
- ZIP/container processing must be source-specific, bounded, validated, and local.
  Never commit raw containers or extracted members.

Every family follows the same workflow:

```text
identify family -> identify source -> preserve source role -> record access state
-> discover documents -> acquire what is safely accessible -> normalize
-> update content, completeness, access, provenance, and redistribution dimensions
```

## Committed and local data

Committed lightweight metadata is limited to the source/discovery manifests, public
indices, coverage report, and durable audits. Never commit `data/raw/`,
`data/archive/`, `data/logs/`, `data/manual/`, download manifests, download
checkpoints, normalized-entry manifests, relation-edge manifests, or any binaries.
`PUBLISHING.md` is the release policy.

Downloads use `data/manifests/download_checkpoint.jsonl` locally. A resume may reuse
only a validated local binary; metadata must be refreshed from current discovery.

## Development and validation

Target Python is `>=3.12`; runtime dependencies are standard-library only. Prefer
small, source-specific functions and deterministic output. Keep normalized filenames
in the documented year/family/stage/type/language format and preserve meaningful
stage, category, language, and source-role metadata.

Canonical quick validation:

```bash
python3 -m unittest discover -s tests -q
```

For crawler or normalization changes, add fixture-first positive and contamination
tests, then use a focused family run if needed. Also run `git diff --check` before
proposing a commit.

Do not run a full global network crawl or global clean rebuild inside short Codex
execution windows. Run it manually in a persistent local terminal (for example
`tmux`) when explicitly requested. Focused runs are preferred during development.

## Commit guidance

Use coherent commits: a source configuration/parser change with its tests and
targeted metadata refresh, or a documentation-only release preparation. Before a
commit, inspect `git status --short`, run the canonical test command, and ensure no
local binary/archive output is staged. Do not push, tag, or release unless the user
explicitly asks.

#!/usr/bin/env bash
# Manually refresh public metadata. All generation happens in staging first.
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
root=$(cd -- "$script_dir/.." && pwd)
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
log_dir=${TMPDIR:-/tmp}/astronomy-olympiad-refresh-logs
mkdir -p "$log_dir"
log_path="$log_dir/source-expansion-$timestamp.log"
stage_repo=$(mktemp -d "${TMPDIR:-/tmp}/astronomy-source-expansion.XXXXXX")
success=0
outputs=(data/manifests/discovered_documents.jsonl data/manifests/discovery_coverage.csv data/indices/olympiads_index.csv data/indices/coverage_report.md)
protected=("${outputs[@]}" data/indices/files_index.csv data/indices/relation_groups.csv)
backup_dir=$(mktemp -d "${TMPDIR:-/tmp}/astronomy-source-expansion-backups.XXXXXX")
declare -A original_hash=()
declare -a install_temps=()
error_reported=0

# Log every command after setup, not only discovery's (usually empty) stdout.
exec > >(tee -a "$log_path") 2>&1

rollback() {
    [[ -d "$backup_dir" && ${#original_hash[@]} -eq ${#protected[@]} ]] || return 0
    local changed=()
    for output in "${protected[@]}"; do
        [[ $(sha256sum "$root/$output" | awk '{print $1}') == ${original_hash[$output]} ]] || changed+=("$output")
    done
    if ((${#changed[@]})); then
        echo "INTERNAL TRANSACTION VIOLATION: ${changed[*]}" >&2
        for output in "${protected[@]}"; do cp -p "$backup_dir/$output" "$root/$output"; done
        echo "Restored all protected files from script-created backups." >&2
    else
        echo "Transaction integrity verified: protected root files unchanged." >&2
    fi
    for temporary in "${install_temps[@]}"; do
        rm -f -- "$temporary"
    done
}

on_error() {
    local line=$1 command=$2 status=$3
    (( error_reported )) && return "$status"
    error_reported=1
    echo "ERROR: status=$status line=$line command=$command" >&2
    echo "Staging repository: $stage_repo" >&2
    echo "Log: $log_path" >&2
    return "$status"
}
on_exit() {
    local status=$?
    if (( success )); then
        rm -rf -- "$stage_repo"
        rm -rf -- "$backup_dir"
    else
        rollback
        echo "Refresh failed; staging retained at: $stage_repo" >&2
        echo "Log: $log_path" >&2
    fi
    trap - EXIT
    exit "$status"
}
trap 'on_error "$LINENO" "$BASH_COMMAND" "$?"' ERR
trap on_exit EXIT

cd "$root"
for required in .git discover_sources.py build_indices.py data/manifests/discovered_documents.jsonl data/manifests/discovery_coverage.csv data/manifests/normalized_entries.jsonl data/manifests/relation_edges.jsonl; do
    [[ -e "$required" ]] || { echo "Missing required repository path: $required" >&2; exit 1; }
done
command -v rsync >/dev/null
command -v python3 >/dev/null
mkdir -p "$backup_dir"
for output in "${protected[@]}"; do
    mkdir -p "$backup_dir/$(dirname "$output")"
    cp -p "$root/$output" "$backup_dir/$output"
    original_hash[$output]=$(sha256sum "$root/$output" | awk '{print $1}')
done

echo "Staging repository: $stage_repo"
echo "Log: $log_path"
rsync -a --delete --exclude='.git/' --exclude='data/raw/' --exclude='data/archive/' --exclude='data/logs/' "$root/" "$stage_repo/"
[[ "$stage_repo" != "$root" ]]
for output in "${protected[@]}"; do
    [[ -f "$stage_repo/$output" && ! -L "$stage_repo/$output" && -f "$root/$output" && ! -L "$root/$output" ]] || { echo "Missing independent regular staging file: $output" >&2; exit 1; }
    [[ $(stat -c '%i' "$stage_repo/$output") != $(stat -c '%i' "$root/$output") ]] || { echo "Staging file shares root inode: $output" >&2; exit 1; }
done
python3 - "$stage_repo" "${outputs[@]}" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
for relative in sys.argv[2:]:
    path = (root / relative).resolve()
    if root not in path.parents:
        raise SystemExit(f"Staged output resolves outside staging repository: {relative} -> {path}")
PY

previous_rows=$(python3 - "$root/data/manifests/discovered_documents.jsonl" <<'PY'
import sys
from pathlib import Path
print(sum(1 for line in Path(sys.argv[1]).open(encoding="utf-8") if line.strip()))
PY
)

(
    cd "$stage_repo"
    python3 discover_sources.py --root "$stage_repo"
    [[ -s data/manifests/normalized_entries.jsonl ]]
    [[ -s data/manifests/relation_edges.jsonl ]]
)
if grep -Fq 'Traceback (most recent call last)' "$stage_repo/data/logs/crawl.log" "$stage_repo/data/logs/errors.log" 2>/dev/null; then
    echo "Discovery emitted a traceback" >&2; exit 1
fi

python3 - "$root" "$stage_repo" "$previous_rows" <<'PY'
import csv, json, re, sys
from collections import Counter
from pathlib import Path
root, stage, previous = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
old = [json.loads(x) for x in (root/'data/manifests/discovered_documents.jsonl').read_text(encoding='utf-8').splitlines() if x]
new = [json.loads(x) for x in (stage/'data/manifests/discovered_documents.jsonl').read_text(encoding='utf-8').splitlines() if x]
def source_map(path):
    with path.open(encoding='utf-8', newline='') as f: return {r['source_id']: r['olympiad_family'] for r in csv.DictReader(f) if r.get('source_id') and r.get('olympiad_family')}
legacy_sources = source_map(root/'data/manifests/source_candidates.csv')
def family(row): return row.get('olympiad_family') or legacy_sources.get(row.get('source_id'))
old_families, unclassified = [family(r) for r in old], []
for r, value in zip(old, old_families):
    if value is None: unclassified.append(r)
before, after = Counter(v for v in old_families if v), Counter(r.get('olympiad_family') for r in new if r.get('olympiad_family'))
problems=[]
if not new: problems.append('empty snapshot')
if len(new) < previous * .80: problems.append(f'total {len(new)} is below 80% of {previous}')
for family, count in before.items():
    if not after[family]: problems.append(f'{family} disappeared')
    elif after[family] < count * .70: problems.append(f'{family} fell from {count} to {after[family]}')
def need(label, predicate):
    if not any(predicate(r) for r in new): problems.append(label)
need('Struve 2026 final written direct', lambda r:r.get('source_id')=='struve_astroedu_archive' and r.get('year')==2026 and r.get('stage_or_round')=='final' and r.get('round_detail')=='written' and r.get('access_mode','download')=='download')
uts_years={r.get('year') for r in new if r.get('olympiad_family')=='struve' and r.get('source_domain')=='uts.astroedu.ru' and r.get('stage_or_round')=='regional' and r.get('round_detail')=='online' and r.get('access_mode')=='discovery_only'}
if not {2023,2024,2025,2026}.issubset(uts_years): problems.append(f'Struve regional-online UTS coverage missing years: {sorted({2023,2024,2025,2026}-uts_years)}')
need('MAO 2026', lambda r:r.get('source_id')=='mao_official_archive' and r.get('year')==2026)
need('Russia-team UTS series', lambda r:r.get('olympiad_family')=='russia_team_qual' and r.get('source_domain')=='uts.astroedu.ru' and r.get('access_mode')=='discovery_only' and re.search(r'Q\d{2}S\d+',str(r.get('round_detail',''))))
need('official IAO issp provenance', lambda r:r.get('olympiad_family')=='iao' and r.get('source_domain') in {'issp.ac.ru','www.issp.ac.ru'} and r.get('source_role')=='official' and 'discovered_via=' in str(r.get('notes','')))
with (stage/'data/manifests/source_candidates.csv').open(encoding='utf-8',newline='') as f: candidates={r['source_id']:r for r in csv.DictReader(f)}
for sid,role,priority in [('struve_astroedu_archive','official','1'),('struve_moscow_year_pages','mirror','2'),('mao_official_archive','official','1'),('mao_moscow_archive','archive','2')]:
    if (r:=candidates.get(sid)) is None or r['source_role']!=role or r['source_priority']!=priority: problems.append(f'bad priority {sid}: {r}')
print(f'Old total={len(old)} new total={len(new)} classified old={sum(before.values())} unclassified old={len(unclassified)}')
assert sum(before.values()) + len(unclassified) == len(old)
print('Before/after family totals:')
for f in sorted(set(before)|set(after)): print(f'{f}: {before[f]} -> {after[f]}')
if problems:
    print('Discovery validation failed:', *problems, sep='\n- ', file=sys.stderr)
    raise SystemExit(1)
PY

(
    cd "$stage_repo"
    python3 build_indices.py --root "$stage_repo"
    python3 - <<'PY'
import csv
from pathlib import Path
report=Path('data/indices/coverage_report.md').read_text(encoding='utf-8')
if 'Known not-held components: 2022 final' not in report: raise SystemExit('Struve not-held validation failed')
rows=list(csv.DictReader(Path('data/indices/olympiads_index.csv').open(encoding='utf-8')))
for family in ('mao','serbia_astronomy'):
    if not any(r['olympiad_family']==family and r['year']=='2026' and r['has_tasks']=='True' and r['has_solutions']=='True' for r in rows): raise SystemExit(f'combined-type validation failed: {family}')
for family,first in [('iao',1996),('ioaa',2007)]:
    section=report.split(f'## {family}\n',1)[1].split('\n## ',1)[0]
    if f'Gaps: {first-1}' in section: raise SystemExit(f'prehistory gap validation failed: {family}')
PY
    python3 -m unittest discover -s tests -q
)

# Ensure staged replacements are whitespace-clean before touching the worktree.
for output in "${outputs[@]}"; do
    [[ -s "$stage_repo/$output" ]] || { echo "Missing staged output: $output" >&2; exit 1; }
    check=$(git diff --no-index --check -- "$root/$output" "$stage_repo/$output" || true)
    [[ -z "$check" ]] || { echo "$check" >&2; exit 1; }
done
git diff --check
git status --short
git diff --stat

# Atomic, rollback-capable final installation. No generated file is copied early.
for output in "${outputs[@]}"; do
    temporary="$root/$output.refresh-$timestamp"
    cp "$stage_repo/$output" "$temporary"
    install_temps+=("$temporary")
done
installed=0
for output in "${outputs[@]}"; do
    mv -f "$root/$output.refresh-$timestamp" "$root/$output"
    ((++installed))
    if [[ ${REFRESH_FAIL_AFTER_INSTALL_COUNT:-0} =~ ^[1-9][0-9]*$ ]] && (( installed == REFRESH_FAIL_AFTER_INSTALL_COUNT )); then
        echo "Simulated final-install failure after $installed output(s)" >&2
        exit 1
    fi
done
for output in data/indices/files_index.csv data/indices/relation_groups.csv; do
    [[ $(sha256sum "$root/$output" | awk '{print $1}') == ${original_hash[$output]} ]] || { echo "Protected non-output changed: $output" >&2; exit 1; }
done
if git status --porcelain | awk '{print $2}' | grep -Eq '^(data/(raw|archive|logs)/|.*\.(pdf|zip|doc|docx|html?|png|jpg)$)'; then
    echo 'Refusing unexpected binary/raw/log changes' >&2; exit 1
fi
success=1
echo "Refresh completed successfully. Log retained at: $log_path"

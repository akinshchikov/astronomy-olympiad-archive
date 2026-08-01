# Архив астрономических олимпиад

[English version](README.md)

`astronomy-olympiad-archive` собирает воспроизводимый локальный архив публичных материалов прошлых лет по астрономическим олимпиадам. Для публичного GitHub-репо он подготовлен как `code + metadata`, без коммита тяжёлых бинарных зеркал.

Базовые семейства:

1. `vsosh_astronomy`
2. `struve`
3. `owao`
4. `serbia_astronomy`
5. `russia_team_qual`
6. `spbao`
7. `mao`
8. `iao`
9. `ioaa`
10. `ioaa_junior`
11. `usaaao`
12. `inao`
13. `czech_astronomy`
14. `gecaa`

Архив различает три состояния покрытия. В текущих публичных индексах есть metadata локальных файлов для 27 семейств; олимпиадный индекс представляет 32 семейства, включая discovery-only provenance. [Аудит активации Batch C](data/audits/global_expansion_batch_c.csv) — авторитетная запись об источниках, которые остаются discovery-only, неразрешёнными или отложенными. Наличие записи об источнике не означает, что его бинарные файлы скачаны или что исторический архив полон.

## Что лежит в публичной версии

- код pipeline
- конфиг источников
- discovery-manifest и coverage-manifest
- итоговые индексы покрытия и relation groups
- документация

Тяжёлые локальные бинарные данные намеренно не коммитятся:

- `data/raw/`
- `data/archive/`
- `data/logs/`

Правила публикации собраны в [PUBLISHING.md](PUBLISHING.md).

## Источники и ограничения

Основной архив Струве — `https://astroedu.ru/struve/problems`; старые страницы Москвы сохранены как mirror. Основной архив МАО — `https://mosastro.olimpiada.ru/tasks`; `mao_moscow_archive` сохранён как исторический fallback. Ссылки UTS/Edu Sirius остаются discovery-only metadata: архив не проходит авторизацию и не скачивает интерактивные туры. Исторические ссылки СПбАО 2012–2013 могут оставаться нерабочими; поддерживаемый путь восстановления — документированный ручной импорт, а не непроверенные зеркала.

## Ручное обновление source-expansion

Полное сетевое обновление metadata запускайте в persistent-сессии:

```bash
tmux new -s olympiad-refresh
./scripts/refresh_source_expansion.sh
```

Отсоединиться: `Ctrl-b d`; вернуться: `tmux attach -t olympiad-refresh`. Скрипт использует временную staging-копию, проверяет discovery snapshot до копирования и оставляет staging-копию при ошибке проверки.

## Pipeline

1. [discover_sources.py](discover_sources.py)
2. [crawl_source.py](crawl_source.py)
3. [normalize_archive.py](normalize_archive.py)
4. [detect_relations.py](detect_relations.py)
5. [build_indices.py](build_indices.py)

Оркестрация:

- [run_pipeline.py](run_pipeline.py)

Скрипты работают только с публичными URL, уважают `robots.txt`, пишут логи, проверяют фактический тип ответа перед принятием загрузки и продолжают работу при ошибках отдельных источников. Возобновляемые checkpoint используют только проверенный локальный бинарный файл, а metadata обновляют из текущего discovery.

## Структура

```text
data/
  raw/                  # локальные оригинальные загрузки, не коммитятся
  archive/              # локальный нормализованный архив, не коммитится
    objects/            # локальное объектное хранилище по sha256
  manifests/
    source_candidates.csv
    discovered_documents.jsonl
    discovery_coverage.csv
    download_manifest.jsonl        # локальный, не коммитится
    download_checkpoint.jsonl      # локальное состояние возобновляемой загрузки, не коммитится
    normalized_entries.jsonl       # локальный, не коммитится
    relation_edges.jsonl           # локальный, не коммитится
  indices/
    olympiads_index.csv
    files_index.csv
    relation_groups.csv
    coverage_report.md
  logs/                 # локальные логи, не коммитятся
  manual/owao/          # опциональные вручную загруженные OWAO-файлы, не коммитятся
```

Нормализованное имя файла:

```text
<year|unknown-year>--<olympiad-family>--<stage-or-round>--<document-type>--<lang>--<descriptor-1>[--<descriptor-2>...]--<variant-tag>.<ext>
```

Примеры:

- `2024--vsosh-astronomy--qualifying--tasks--ru--grade-10--school--mirror.pdf`
- `2024--vsosh-astronomy--final--tasks--ru--grade-10--theory--mirror.pdf`
- `2025--ioaa--observational--tasks--en--planetarium--questions--official.pdf`
- `unknown-year--iao--theoretical--tasks--en--tasks-page--archive.html`

Вместо одного длинного `detail_tag` имя теперь собирается из отдельных смысловых частей: класс, программа/подэтап, тур, тип материала. Типичные дескрипторы:

- `grade-10`, `grade-10-11`
- `theory`, `practical`, `test`, `blitz`
- `school`, `municipal`, `invitational`, `selection`
- `reference-data`, `questions`, `exam`, `problem-sheet`, `tasks-page`

Это сделано, чтобы по имени сразу было видно класс и тур, а запасной `-v2`, `-v3` использовался только там, где действительно есть несколько осмысленных вариантов одного и того же комплекта.

В каждой папке события служебные файлы лежат в `info/`:

- `event-metadata.json`
- `event-source-urls.txt`
- `event-relations.json`

`data/archive/objects/` используется как локальное объектное хранилище по `sha256`, а событийные папки содержат hardlink/copy на эти объекты.

## Запуск

Сухой прогон:

```bash
python3 run_pipeline.py --dry-run
```

Полный прогон:

```bash
python3 run_pipeline.py
```

Полная пересборка с очисткой:

```bash
python3 run_pipeline.py --clean
```

Только очистка, без запуска pipeline:

```bash
python3 cleanup_outputs.py
```

Та же очистка через оркестратор:

```bash
python3 run_pipeline.py --clean-only
```

Только выбранные семейства:

```bash
python3 run_pipeline.py --families struve owao serbia_astronomy russia_team_qual
```

Тот же фильтр `--families` теперь применяется и к `coverage_report.md`.

Очистить и локально пересобрать только одно семейство:

```bash
python3 run_pipeline.py --clean --families spbao
```

Только очистка для выбранных семейств:

```bash
python3 cleanup_outputs.py --families spbao
```

Та же семейная очистка через оркестратор:

```bash
python3 run_pipeline.py --clean-only --families spbao
```

Замечания:

- `python3 run_pipeline.py --clean` сначала удаляет все локально сгенерированные артефакты: `data/raw/`, `data/archive/`, `data/logs/`, сгенерированные manifest-файлы и итоговые индексы.
- `python3 cleanup_outputs.py --families ...` удаляет только дерево архива выбранного семейства, соответствующие папки в `data/raw/` и общие логи. Общее объектное хранилище `data/archive/objects/` оно намеренно не трогает.
- Точечная очистка также удаляет строки выбранных семейств из сгенерированных JSONL-manifest, чтобы в точечной пересборке не использовались устаревшие записи. `data/archive/objects/` при этом не удаляется.
- Checkpoint загрузки повторно использует только проверенный локальный бинарный файл; при продолжении прогона metadata всегда берётся из текущего discovery.
- Запуск с `--families ...` предназначен для локального точечного обновления. Чтобы снова получить полный глобальный набор manifest-файлов и индексов, после этого нужен прогон без `--families`.

## Источники первой очереди

- `vsosh_edsoo_official`: `https://vserosolimp.edsoo.ru/astronom`
- `owao_tasks_official`: страница `https://owao.siriusolymp.ru/2025en/tasks` и архивные страницы 2024 и 2023 годов
- `owao_astroedu_archive`: `https://astroedu.ru/hq/problems/owao` (direct-file fallback для теоретического и практического туров)
- `serbia_astronomy_official`: `https://www.das.org.rs/naoc.html`
- `russia_team_qual_archive`: `https://astroedu.ru/hq/problems/`
- `mao_official_archive`: `https://mosastro.olimpiada.ru/tasks` (official; `mao_moscow_archive` остаётся историческим fallback)
- `ioaa_problems`: `https://www.ioaastrophysics.org/resources/problems-from-past-ioaa`

Границы и политика источников:

- `ioaa_junior_official` ведёт Junior IOAA отдельно от core IOAA. В официальных PDF прошлых олимпиад один документ может объединять несколько компонентов соревнования.
- `usaaao_past_exams` сохраняет в metadata фактический контекст соревнования: practice, First Round, NAC и selection exams.
- `inao_hbcse_past_papers` и `inao_hbcse_current` дают публичные metadata, но явное требование HBCSE о запрете перераспространения сохраняется как `redistribution_status=explicit-no-redistribution`. Скачанные материалы и решения INAO остаются локальными и не коммитятся и не публикуются повторно.
- `czech_astronomy_official` — отдельное семейство Чешской астрономической олимпиады, не IAO. Защищённые или недоступные материалы — это discovery gap; pipeline не обходит login/access control и отфильтровывает не относящиеся к делу IAO, пресс- и result-материалы.
- `gecaa_ioaa_archive` даёт доступные официальные материалы GeCAA из IOAA-hosted archive. `gecaa_official_archive` остаётся внешним availability gap: текущие загрузки с `gecaa.ee`, включая известные team documents, не заявляются как локально архивированные.

Часть семейств сейчас стартует не с источника первого приоритета, а с archive/mirror-источников, прежде всего `struve`, `spbao` и `iao`.

Batch C сохраняет отдельность линий: старшая польская олимпиада (`poland_astronomy`) не является младшей; старшая и младшая олимпиады Шри-Ланки различны; а словенские high-school, primary-school и Utrinek — три отдельные семьи. Bangladesh BAO отделён от BDOAA, а местные предварительные работы Макао не являются работами CNAO. CNAO исключает провинциальные китайские отборы. Непал пока представлен только sample/practice-работами с неизвестным годом, а не подтверждёнными историческими национальными турами.

Роли источников сохраняются. Иран представлен mirror-источником, а не официальным архивом; страница события Israel Space Agency не делает Multi-Space авторитетным архивом. Для Хорватии используется ограниченное локальное извлечение проверенных публичных ZIP-контейнеров; извлечённые материалы остаются локальными. OBA сохраняет семантику уровней/категорий и исключает неподтверждённые training/selection-материалы.

Полный актуальный список seed-источников сохранён в [data/manifests/source_candidates.csv](data/manifests/source_candidates.csv).

## OWAO: прямой fallback Astroedu, official discovery и ручной импорт

Официальные архивные страницы OWAO остаются discovery-источником первого приоритета. Часть их файлов находится на robots-blocked, external-share, интерактивных или login-like сервисах, поэтому такие ссылки могут оставаться discovery-only.

Discovery-only покрытие Batch C намеренно там, где политика или доступ не позволяют безопасно ingest: официальные Drive-файлы OLAA и NZOAA заблокированы политикой crawler; файлы Таиланда требуют форму; официальные страницы Сингапура и Малайзии закрыты robots; часть официальных страниц даёт provenance, но не безопасно перечисляемый архив работ. Аудит также сохраняет неразрешённые и отложенные кандидаты вне runtime-конфигурации ingestion.

Источник второго приоритета `owao_astroedu_archive` даёт прямые публичные PDF и ZIP с данными практического тура со страницы `https://astroedu.ru/hq/problems/owao`. Для перечисленных там лет точечный запуск

```bash
python3 run_pipeline.py --clean --families owao
```

должен скачать прямые материалы теоретического и практического туров и создать `data/archive/owao/`. Онлайн-наблюдательный и блиц-туры, ведущие в UTS, остаются discovery-only; pipeline не обходит ограничения доступа.

Ручной импорт по-прежнему нужен для публичных файлов OWAO, которых нет в прямом архиве. Положите скачанный в браузере файл в `data/manual/owao/`, добавьте обязательную sidecar-строку в `data/manual/owao/manual_manifest.jsonl`, запустите `python3 import_manual_files.py`, затем normalization/indexing.

### Как проверить OWAO локально

```bash
grep '^owao' data/manifests/discovery_coverage.csv
python3 - <<'PY'
import json
from collections import Counter

rows = []
with open("data/manifests/discovered_documents.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("olympiad_family") == "owao":
            rows.append(r)

print("OWAO discovered rows:", len(rows))
for k, v in sorted(Counter((r.get("year"), r.get("stage_or_round"), r.get("document_type")) for r in rows).items()):
    print(v, k)
PY
find data/archive -maxdepth 3 -type d -name 'owao' -print
```

## Семантика metadata

- Один физический документ может логически представлять несколько типов материалов (например, задачи и решения). Он не разрезается лишь ради одного `document_type` на файл.
- `access_mode=discovery_only` сохраняет полезную публичную provenance-информацию, но не является целью скачивания.
- Конфигурация хронологии отличает реальные пробелы соревнований от сохранённых prehistory/anomalous years и известных не проведённых компонентов.

## Snapshot

Текущий публичный snapshot по коммитимым артефактам обновлён на `2026-08-01`:

- настроенные seed-источники: `53`
- обнаруженные публичные документы: `3768`
- строки в `olympiads_index.csv`: `687`
- уникальные публичные файлы в `files_index.csv`: `3538`
- relation groups: `592`

Batch C добавляет 940 индексированных файлов ещё для 13 семейств: Bangladesh BAO, Brazil OBA, Болгарии, CAAO, Хорватии, Макао, Непала, старшей польской астрономической олимпиады, трёх самостоятельных словенских линий, а также старшей и младшей олимпиад Шри-Ланки. В долговечном [аудите Batch C](data/audits/global_expansion_batch_c.csv) 32 кандидата: 13 `INGESTED_PARTIAL`, 11 `ACTIVE_DISCOVERY_ONLY`, 7 `CONDITIONAL_UNRESOLVED` и 1 `DEFERRED_NO_RELIABLE_ARCHIVE`.

Семейства с индексированными локальными файлами (27; диапазоны представленных лет для базовых семейств ниже; типы материалов, discovery-only записи, prehistory и не проведённые компоненты приведены в coverage report):

- `vsosh_astronomy`: `1994..2026`, 33 года
- `struve`: `2022..2026`, 5 лет
- `owao`: `2022..2025`, 4 года
- `serbia_astronomy`: `2012..2026`, 15 лет
- `russia_team_qual`: `2016..2026`, 11 лет
- `spbao`: `2010..2026`, 17 лет
- `mao`: `2010..2026`, 16 лет
- `iao`: `1989..2023`, 28 лет (с сохранённым prehistory 1989)
- `ioaa`: `2003..2025`, 20 лет (2003 и 2005 сохранены как prehistory)
- `ioaa_junior`: `2022..2025`, 4 года
- `usaaao`: `2014..2026`, 13 лет
- `inao`: `2008..2026`, 18 лет
- `czech_astronomy`: `2004..2025`, 22 года
- `gecaa`: `2020`, 1 год

- Batch C: `bangladesh_bao`, `brazil_oba`, `bulgaria_astronomy`, `caao`, `croatia_astronomy`, `macao_astronomy`, `nepal_astronomy`, `poland_astronomy`, `slovenia_astronomy`, `slovenia_astronomy_primary`, `slovenia_utrinek`, `sri_lanka_astronomy` и `sri_lanka_junior_astronomy`.

Ещё пять семейств в олимпиадном индексе имеют provenance-покрытие без индексированных локальных файлов: `baao`, `olaa`, `poland_astronomy_junior`, `singapore_astronomy` и `thailand_astronomy`. Остальные кандидаты аудита намеренно остаются неразрешёнными или отложенными, а не представлены как ingested-архивы.

## Итоговые индексы

- [data/indices/coverage_report.md](data/indices/coverage_report.md)
- [data/indices/olympiads_index.csv](data/indices/olympiads_index.csv)
- [data/indices/files_index.csv](data/indices/files_index.csv)
- [data/indices/relation_groups.csv](data/indices/relation_groups.csv)

## Ограничения и известные пробелы

- Для PDF пока нет полноценного OCR/извлечения текста; near-duplicate строится по метаданным, именам и размерам файлов.
- Часть старых IAO-страниц на `issp.ac.ru` нестабильна, поэтому используются и официальные индексы, и зеркала.
- `vso.edsoo.ru` блокирует часть официальных файлов через `robots.txt`, поэтому они остаются только в discovery.
- Для OWAO поддерживаются официальные архивные страницы 2022–2025, а fallback Astroedu даёт прямые PDF теоретического/практического туров и архивы данных для перечисленных там лет. Отдельной рабочей страницы `2022en/tasks` нет (HTTP 404): official metadata за 2022 год извлекается из встроенного раздела. Онлайн-туры UTS и заблокированные внешние ссылки остаются discovery-only.
- Для `russia_team_qual` сейчас покрыт только direct-PDF-поднабор с `astroedu.ru/assets/problems/hq/...pdf`; связанные quiz-страницы на `uts.astroedu.ru` намеренно оставлены вне первого патча.
- В старых архивах СПбАО и ВсОШ есть битые ссылки (`404`), особенно в исторических зеркалах.
- Материалы и решения INAO/HBCSE остаются локальными в соответствии с явным запретом на перераспространение.
- Защищённые материалы Czech AO остаются discovery gap; обход authentication/access control не предпринимается.
- IOAA-hosted archive GeCAA индексируется, но текущая ошибка загрузки с `gecaa.ee` остаётся внешним gap, включая известные team documents.
- Аудит Batch C сохраняет дополнительные gaps вместо их обхода: robots-ограничения, политика внешних хостов, формы, недоступные архивы и mirror-only provenance не разрешают альтернативный scraping или перераспространение.

## Для GitHub

Этот репозиторий подготовлен так, чтобы на GitHub выкладывать код и лёгкие метаданные, а полный бинарный архив пересобирать локально.

Важно:

- код в этом репозитории распространяется под лицензией `MIT`, см. [LICENSE](LICENSE)
- это не означает автоматического разрешения на перераспространение скачанных олимпиадных файлов; для них нужно отдельно учитывать условия исходных источников

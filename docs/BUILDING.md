# Building from source

This page is for maintainers who want to regenerate `dist/Forkfed_Chinese.apkg` from the source deck and the scripts in this repository.

For deck installation, see the [README](../README.md).

## Requirements

| Tool | Version used | Purpose |
| --- | --- | --- |
| Python | 3.14.6 | pipeline, SQLite/ZIP packaging, validation |
| pypinyin | 0.55.0 | dictionary readings and secondary candidate |
| jieba | 0.42.1 | word segmentation, i+1 diagnostics, third-tone domains |
| opencc-python-reimplemented | 0.1.7 | `s2tw` traditional conversion and round-trip checks |
| Node.js | 26.10.0 | runs the `pinyin-pro` batch helper |
| pinyin-pro | 3.29.5 | primary lexical-pinyin candidate |
| Anki Python backend | 26.9.3 | headless package import test |

Python 3.11+ and Node 18+ should work; the versions above are the tested baseline. Python dependencies are pinned in [`requirements.txt`](../requirements.txt), and the Node dependency is pinned in [`package-lock.json`](../package-lock.json).

You do **not** need Anki installed to run the pipeline, but the Anki Python package is required for the headless import test. `scripts/10_anki_import_test.py` uses it directly.

## 1. Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
npm install
```

On macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
```

## 2. Add the source deck

The pipeline reads:

```text
source/Spoonfed_Chinese_Forkfed.apkg
```

This file is not committed because it is about 121 MB, over GitHub's 100 MiB per-file limit. Download the base deck from [AnkiWeb 772959041](https://ankiweb.net/shared/info/772959041) and save the APKG under that name.

The source deck contains **7,335 notes**, **7,335 cards**, four fields (`English`, `Pinyin`, `Hanzi`, `Audio`), and **7,316 media files**. `scripts/01_extract.py` checks those assumptions and will fail early if the file is missing or does not match the expected schema.

## 3. Run the pipeline

Run the scripts from the repository root, in this order:

```powershell
python scripts/01_extract.py
python scripts/02_normalize.py
python scripts/02b_apply_feedback.py
python scripts/03_generate_pinyin.py
python scripts/04_tone_sandhi.py
python scripts/05_zhuyin_traditional.py
python scripts/06_audit.py
python scripts/08_review_decisions.py
python scripts/09_gold_accuracy.py
python scripts/07_build_apkg.py
```

| Step | Input | Output | What it does |
| --- | --- | --- | --- |
| `01_extract.py` | source APKG | `notes.json`, `cards.json`, `meta.json`, `media_map.json` | opens the real `collection.anki21`, preserves note/card metadata |
| `02_normalize.py` | extracted data | `normalized.json`, `normalization_stats.json` | repairs HTML/Unicode, aligns lines, normalizes fields |
| `02b_apply_feedback.py` | normalized data + `scripts/lib/sp_feedback.py` | `normalized.json`, feedback/duplicate/audio ledgers | applies curated community corrections, removes nine duplicates |
| `03_generate_pinyin.py` | normalized data | `pinyin.json`, `pinyin_corrections.csv` | combines `pypinyin`, `pinyin-pro`, and the curated lexicon |
| `04_tone_sandhi.py` | lexical pinyin | `sandhi.json`, `sandhi_review.csv` | applies 一/不 and conservative third-tone sandhi |
| `05_zhuyin_traditional.py` | sandhi data | `zhuyin_traditional.json` | creates zhuyin and `s2tw` traditional text |
| `06_audit.py` | all prior data | `audit.json`, `audit.csv`, review queue | builds the final note model, gold set, Sequence/SortOrder |
| `08_review_decisions.py` | audit queue + pinyin data | `review_decisions.csv` | records one decision per review finding |
| `09_gold_accuracy.py` | review queue + zhuyin data | `gold_set_accuracy.json` | measures the fixed 200-note gold sample |
| `07_build_apkg.py` | audit data + source APKG | `dist/Forkfed_Chinese.apkg` | copies media byte-for-byte, updates the note type and cards |

The feedback pass intentionally runs **before** pinyin generation so corrected Hanzi, added syllables, and changed sentence subjects regenerate consistent pinyin, sandhi, zhuyin, and traditional text. Existing Phase 2 overrides in `scripts/lib/sp_phase2.py` apply afterward.

## 4. Validate

```powershell
python scripts/validate_deck.py
python scripts/validate_pinyin.py
python scripts/validate_sandhi.py
python scripts/10_anki_import_test.py
```

`validate_deck.py` runs the full acceptance matrix and writes `data/qa.json`. It expects **0 failures**. `validate_pinyin.py` checks syllable counts, invalid syllables, apostrophes, and case. `validate_sandhi.py` checks tone-sandhi bolding and 一/不 rules. `10_anki_import_test.py` imports the package into a clean headless Anki collection and re-imports it to verify duplicate stability.

The current build passes **74/74** checks. The package hash and size are recorded in `data/qa.json`.

## Common maintenance tasks

### Template or CSS-only change

Edit `QUESTION`, `ANSWER`, or `CSS` in `scripts/07_build_apkg.py`, then rebuild and validate:

```powershell
python scripts/07_build_apkg.py
python scripts/validate_deck.py
```

No data regeneration is needed for layout changes. `scripts/validate_deck.py` checks the template tokens and CSS.

### Pinyin or translation correction

- **Curated word/line reading:** edit `scripts/lib/sp_lexicon.py` or `scripts/lib/sp_phase2.py`.
- **Community feedback:** update the ledger in `scripts/lib/sp_feedback.py`; `data/feedback_source.txt` is the source text used to verify block coverage.
- **Number reading:** edit `scripts/lib/sp_numbers.py`.

Then rerun from the relevant step:

```powershell
python scripts/03_generate_pinyin.py
python scripts/04_tone_sandhi.py
python scripts/05_zhuyin_traditional.py
python scripts/06_audit.py
python scripts/08_review_decisions.py
python scripts/09_gold_accuracy.py
python scripts/07_build_apkg.py
python scripts/validate_deck.py
```

If Hanzi or English changed, rerun `02b_apply_feedback.py` before pinyin generation.

### Regenerate everything

Start at `01_extract.py` and run the full sequence in [Run the pipeline](#3-run-the-pipeline).

## Generated data

`data/` is a build directory, not source. Every file except `data/feedback_source.txt` and `data/README.md` is generated and ignored by Git. The important artifacts are:

| File | Contents |
| --- | --- |
| `notes.json`, `cards.json`, `meta.json`, `media_map.json` | extracted source data |
| `normalized.json`, `normalization_stats.json` | cleaned lines, alignment diagnostics, feedback-applied Hanzi/English |
| `pinyin.json`, `pinyin_corrections.csv` | lexical pinyin and every correction |
| `sandhi.json`, `sandhi_review.csv` | surface pinyin and uncovered third-tone runs |
| `zhuyin_traditional.json` | zhuyin, traditional Hanzi, round-trip differences |
| `audit.json`, `audit.csv` | final notes, Sequence and SortOrder, i+1 diagnostics |
| `gold_set.csv`, `review_queue.csv` | fixed sample and Phase 2 review queue |
| `review_decisions.csv` | one decision per review-queue finding |
| `feedback_corrections.csv` | one triage row per feedback item |
| `duplicates.csv` | nine removed copies, kept note, matching fields, audio |
| `audio_issues.csv` | audio cutoffs and spoken/written mismatches |
| `gold_set_accuracy.json` | fixed-sample accuracy measurement |
| `qa.json` | latest validation matrix, package hash, and release status |

`scripts/tools/phase2_wordcheck.py` is an optional review aid that writes `data/word_reading_review.csv`.

## Publishing a release

GitHub rejects files over 100 MiB, so the built APKG is deliberately not committed. Publish it as a release asset:

1. Run the full pipeline and validations.
2. Create a tag, for example `v0.3.1`.
3. Draft a GitHub release for the tag.
4. Attach `dist/Forkfed_Chinese.apkg`.
5. Include the SHA-256 from `data/qa.json` in the release notes.
6. Confirm the README install link points at [Releases](/releases/latest).

To keep a local copy of the source deck, keep it in `source/`; it is ignored by Git.

## Troubleshooting

- **`source APKG not found`** — put the source file at `source/Spoonfed_Chinese_Forkfed.apkg`.
- **Node/pinyin-pro failure** — run `npm install` at the repository root. `scripts/lib/pinyin_pro_batch.js` is called by `03_generate_pinyin.py`.
- **Anki import test failure** — the `anki` Python package must match the pinned version, and the test needs a writable temporary directory.
- **Unicode errors on Windows** — the pipeline writes UTF-8. Run commands from PowerShell 7 or set `PYTHONIOENCODING=utf-8` if your console uses a legacy code page.
- **Changed source deck** — the scripts assert the 7,335-note source schema. If the upstream deck changes, update the extraction/normalization assumptions and the audit expectations together.

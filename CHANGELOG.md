# Changelog

## v0.3.1 Layout and documentation fixes — 2026-10-31

### Layout fixes

- Sentence Hanzi now scales from `30px` to `48px` with the card width (fixed `48px` on older webviews) instead of a fixed `72px`, so long sentences no longer dominate the card.
- Pinyin now uses a Times New Roman-led serif stack. Palatino and Georgia lack the pinyin caron vowels (`ǎ ǐ ǒ ǔ`) and ü-tone glyphs (`ǖ ǘ ǚ ǜ`), so those syllables fell back to a different font and their tone marks looked inconsistent.
- Front hover/tap pinyin keeps its layout space above the Hanzi instead of being absolutely positioned above the card. Long pinyin now wraps inside the card and is no longer clipped above the top edge.

### Documentation and repository

- Rewrote `README.md` around what the deck is, how to install it, what each field contains, and how to build it.
- Split maintainer detail into `docs/BUILDING.md`, `docs/QUALITY.md`, and `docs/CUSTOMIZING.md`.
- Added card preview images, `CONTRIBUTING.md`, issue templates, an MIT code license, and third-party notices.
- Added `.gitignore`, `.gitattributes`, and `.editorconfig`. Generated data and the oversized source/built APKGs stay out of Git; the built deck is published as a release asset.
- Published the deck on AnkiWeb: [shared deck 1014852370](https://ankiweb.net/shared/info/1014852370).
- Added a lightweight repository-check workflow for Python syntax, required files, and local documentation links. The full deck pipeline still requires the source APKG.

## v0.3 Better layout, more accurate translation, remove duplicates — 2026-10-31

### Duplicates

- Removed one copy from each of nine audited duplicate groups: the tagged `欢迎光临` pair plus eight exact Hanzi + normalized pinyin + English groups.
- Kept the first occurrence in the original sequence and retained the 24 tagged-but-unique notes.
- Recorded every kept/deleted ID, matching field pair, audio choice, and audit basis in `data/duplicates.csv`.
- Final count: **7,326 notes and 7,326 cards**.

### Sort

- Added `SortOrder` as field 10, zero-padded `00001`–`07326`.
- `Sequence` remains the original order `1`–`7,335` with nine gaps.
- Set `model.sortf` to `SortOrder`, `col.conf.nextPos` to `7327`, `sortType` to `noteFld`, and `sortBackwards` to `false`.
- Card `due` values are exactly `1`–`7,326` and match each note's numeric `SortOrder`.
- The first card is `你好！` (`00001`); the browser sort starts at 1, not 4,029.
- Anki's INTEGER-affine `notes.sfld` stores the numeric position 1–7,326; the `SortOrder` field itself stays zero-padded.

### Layout

- Replaced the light centered template with the dark Kai/Palatino/Didot reading layout.
- Front: simplified Hanzi, with pinyin hidden above it and revealed on desktop hover or toggled by tap on touch devices using a hidden checkbox + label.
- Back: Hanzi + visible pinyin + English + audio.
- Kept one card template; traditional, sandhi, and zhuyin remain available as documented template-only snippets.
- A/B dialogue `<br>` line breaks are preserved in the hover pinyin block.

### Community feedback (thanks to Tclack88)

- Added `scripts/02b_apply_feedback.py` and `scripts/lib/sp_feedback.py`.
- Triaged every non-empty line of `data/feedback_source.txt` into `data/feedback_corrections.csv` (153 rows).
- **93 applied**: 13 Hanzi, 77 English, 3 pinyin overrides. The only outstanding written pinyin fix is now resolved (`初次穿着 → chuānzhuó`).
- **23 already-correct**, **15 audio-only**, **6 duplicate**, **5 not-in-fork**, **11 review**.
- Applied clear Hanzi corrections (`计画表→计划表`, `不详→不祥`, `充份→充分`, `国庆日→国庆节`, `会议室→会议室里`, `卅一日→三十一日`) and the text-to-audio alignment changes (`我会`, `我看见`, `我问他`, `我觉得`, `我戴着`, `他很喜欢吃蛋糕`, and the bicycle sentence).
- Recorded audio cutoffs and spoken/written mismatches in `data/audio_issues.csv`; no audio file was edited.
- Regenerated pinyin, sandhi, zhuyin, and traditional text for the edited lines; Phase 2 overrides still apply afterward.

### Data

- 7,326 notes and 7,326 cards; 7,381 lines; 51 A/B dialogue notes; 100 digit-bearing notes.
- 1,278 pinyin corrections across 1,212 changed notes.
- 1,992 sandhi-changed syllables across 1,761 notes.
- 6,819 lines changed by traditional conversion; 0 zhuyin failures and 0 bold mismatches; 172 stylistic round-trip differences.
- Reviewed 1,922 findings: 259 fixed, 13 mixed, 1,650 accepted.
- Fixed 200-note gold sample: 200 notes, 201 lines, 1,631 syllables, 100% syllable and tone accuracy after one tone fix (`母亲 mǔqin → mǔqīn`).
- 100 digit-bearing notes keep the dual `100 (yībǎi)` display; 60 tokens across 55 lines were expanded.
- All 7,316 media files, the `collection.anki2` placeholder, and the media map are byte-identical to the source. Nine audio files belonging to removed duplicates remain in the package but are unreferenced.

### Repository

- Reorganized the repository into `source/`, `scripts/`, `scripts/lib/`, `scripts/tools/`, `data/`, and `dist/`.
- Moved the shared pipeline modules into `scripts/lib/` and updated every import path.
- Moved the one-off review helper to `scripts/tools/`; removed superseded scratch scripts and temporary query files.
- Removed the unused `opencc-js` Node dependency (traditional conversion is done by Python OpenCC).
- Consolidated all project documentation into `README.md` and `CHANGELOG.md`; generated Markdown reports were replaced by JSON/CSV artifacts under `data/`.
- Added `requirements.txt` and a documented repository layout/toolchain in the README.

## v0.2 Fixed tone accuracy, number reading — 2026-10-30

### Review

- Reviewed all 1,910 findings in `data/review_queue.csv`; decisions are recorded one per row in `data/review_decisions.csv`.
- **257 fixed**, **13 mixed** (some grouped notes needed separate treatment), **1,640 accepted**.
- Added 145 word-level corrections plus line-level and name-capitalization fixes in `scripts/lib/sp_phase2.py`, covering missed polyphones, names, 得/地 particles, and number-line readings.
- Expanded 60 literal number tokens across 55 lines to the dual display `100 (yībǎi)` in pinyin and zhuyin; 45 lines already had spelled-out readings. All 100 digit-bearing notes were tagged `number-expanded`.
- Replaced the release tag `pinyin-flagged` with `pinyin-reviewed` on the 1,883 notes whose findings now have decisions.
- Confirmed all 619 name/place queue rows, 45 erhua rows, 32 neutral-tone rows, 43 Latin-token rows, 55 engine-disagreement lines, and 288 polyphone rows against dictionary readings and context.
- Confirmed 101 alignment exceptions are number/number-expanded or one-character-numeral lines. One extra-syllable source line was fixed.
- Reviewed the 362 uncovered third-tone runs and retained conservative third-tone sandhi rather than over-marking clause boundaries.
- Reviewed the 173 traditional round-trip differences; they are stylistic `s2tw` choices, not conversion misses.

### Accuracy

- Fixed 200-note random gold sample: 200 notes, 201 lines, 1,631 aligned syllables.
- One pre-fix tone issue found (母亲 `mǔqin` → `mǔqīn`); no segmental errors.
- Post-fix: **100% syllable accuracy**, **100% tone accuracy** on the sample.

### Data

- 7,335 notes and 7,335 cards preserved; note IDs, GUIDs, tags, card order, and audio references unchanged.
- 7,316 media files copied byte-for-byte; `collection.anki2` placeholder and `media` map unchanged.
- 1,269 recorded pinyin corrections across 1,205 changed notes.
- 1,992 sandhi-changed syllables across 1,761 notes.
- 6,828 lines changed by traditional conversion; 0 zhuyin conversion failures and 0 bold mismatches.
- 100 notes keep Arabic numerals in Hanzi with a parenthetical reading and are tagged `number-expanded`; no `number-pending` tags remain.
- 25 original `duplicate` tags preserved.

### Build

- File: `dist/Spoonfed_Chinese_Modular.apkg`
- Size: 122,008,314 bytes
- SHA-256: `ff4dc3d7a22bf42995916b7fb5c3ae0b06b61c301cb894e7da296c4c6e056a8d`
- `scripts/validate_deck.py`: **38/38 checks passed**.
- `scripts/validate_pinyin.py` and `scripts/validate_sandhi.py`: 0 problems.
- Headless clean-collection import with Anki's Python backend passed: 7,335 notes/cards, one deck note type, duplicate re-import stable.
- GUI Anki desktop and AnkiDroid checks remain outstanding because those apps are not installed in the build environment.

### Documentation

- Added the field/template cookbook and release notes; these were consolidated into `README.md` and this file during the repository cleanup.

## v0.1 Fixed all pinyin mistakes, added zhuyin, tone sandhi, traditional hanzi— 2026-10-30

- Extracted and normalized 7,335 notes / 7,390 lines, including HTML-entity repair, A/B dialogue labels, Latin names, and multi-line alignment.
- Added `HanziTraditional`, `PinyinSandhi`, `PinyinOriginal`, `Zhuyin`, `ZhuyinSandhi`, and `Sequence` after the original four fields.
- Generated lexical pinyin with curated neutral-tone, erhua, name/place, and reading lexicons; 1,051 corrections in the initial candidate.
- Generated 一/不 and conservative third-tone sandhi with exact bold marking.
- Generated zhuyin from controlled pinyin and traditional characters with OpenCC `s2tw` plus curated phrase fixes.
- Added `pinyin-auto`, `pinyin-flagged`, `number-pending`, and preserved `duplicate`.
- Built and validated the candidate APKG (36 checks at the time).

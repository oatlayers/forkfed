# Quality and audit

The deck is generated, not hand-edited note by note. Every correction and every exception is recorded in a reproducible pipeline so the current package can be checked and rebuilt.

## Deck facts

| | |
| --- | --- |
| Notes / cards | 7,326 / 7,326 |
| Lines | 7,381 |
| A/B dialogue notes | 51 |
| Media files | 7,316 unique files: 7,307 referenced (7,306 audio + 1 image), 9 unused duplicates |
| Digit-bearing notes | 100 |
| Notes with Latin tokens | 94 |
| Pinyin corrections | 1,278 across 1,172 notes |
| Tone-sandhi changes | 1,992 syllables across 1,761 notes |
| Traditional round-trip differences | 172, evaluated as stylistic `s2tw` choices |
| Zhuyin failures / bold mismatches | 0 / 0 |
| Removed duplicates | 9 exact groups |

`Sequence` preserves the original pedagogical position (`1`–`7,335` with nine gaps). `SortOrder` is the contiguous release key (`00001`–`07326`). The single card template uses `SortOrder` as the sort field.

## How the data is produced

1. **Extract** the source APKG without modifying it. Note IDs, GUIDs, card IDs, flags, tags, and media bytes are preserved.
2. **Normalize** HTML, Unicode, line breaks, and speaker labels. A/B dialogue lines are kept as separate lines and displayed with `<br>`.
3. **Apply curated feedback** from `scripts/lib/sp_feedback.py`: Hanzi, English, and pinyin corrections plus the nine duplicate decisions. Hanzi changes run before pinyin generation so every downstream field agrees.
4. **Generate lexical pinyin** with an ensemble of `pypinyin`, `pinyin-pro`, and a curated lexicon for names, places, neutral tones, erhua, and polyphones. Every correction is recorded in `pinyin_corrections.csv`.
5. **Apply tone sandhi** with 一/不 rules and conservative third-tone sandhi. Only syllables whose surface tone changes are bolded in `PinyinSandhi`.
6. **Generate zhuyin and traditional Hanzi** from the controlled readings and OpenCC `s2tw`, with explicitly reviewed round-trip differences.
7. **Audit** the final note model: alignment, syllable counts, apostrophes, case, sandhi bolding, zhuyin, traditional characters, audio references, sequence, and sort order.
8. **Build** the APKG by copying the source media and placeholder members byte-for-byte and replacing only the collection database.

The feedback pass is based on the public [Tclack88 corrections list](https://github.com/Tclack88/misc-analysis/blob/main/mandarin_frequency_analysis/chinese_anki_backup/spoonfed_chinese_deck_corrections.txt). The triage ledger has 153 rows: 93 applied, 23 already correct, 15 audio-only, 6 duplicates, 5 not in this fork, and 11 left for review.

## Review record

The Phase 2 review queue contains 1,922 findings. Decisions are recorded one per row in `review_decisions.csv`:

| Decision | Count |
| --- | ---: |
| Fixed | 259 |
| Mixed (some grouped notes needed separate treatment) | 13 |
| Accepted (reading correct, or deferred by policy) | 1,650 |

The review covered polyphones, names and places, neutral tones, erhua, Latin tokens, engine disagreements, number lines, and alignment exceptions. Curated changes live in `scripts/lib/sp_phase2.py` and are applied after pinyin generation.

## Gold sample

A fixed random 200-note sample is used as a regression check:

| Metric | Result |
| --- | ---: |
| Notes | 200 |
| Lines | 201 |
| Aligned syllables | 1,631 |
| Syllable accuracy | **100%** |
| Tone accuracy | **100%** |

One tone issue was found before the fix (`母亲 mǔqin → mǔqīn`); no segmental errors were found. The measurement is written to `gold_set_accuracy.json` by `scripts/09_gold_accuracy.py`.

## Validation

`scripts/validate_deck.py` runs the full acceptance matrix against the built APKG and writes `data/qa.json`. The current build passes **74/74** checks, including:

- package and ZIP integrity, with all non-database members byte-identical to the source;
- note/card counts, retained IDs and GUIDs, duplicate removal, and media references;
- field values, empty tags, `SortOrder`/`sfld`/`due` agreement;
- pinyin alignment, apostrophes, Latin case, sandhi bolding, zhuyin, and traditional spot checks;
- feedback, duplicate, and audio ledgers;
- the fixed gold sample;
- package hash and size.

Independent checks:

```powershell
python scripts/validate_pinyin.py
python scripts/validate_sandhi.py
python scripts/10_anki_import_test.py
```

`10_anki_import_test.py` imports the APKG into a clean headless Anki collection, verifies 7,326 notes/cards and the first card, then re-imports it to confirm the note count stays stable.

## Known limits

- **Audio is not edited.** Cuts and spoken/written mismatches are recorded in `data/audio_issues.csv` (25 notes). The source audio files are copied unchanged.
- **One inherited note** (`这个甜点是经理推荐的。`) has a `.jpg` reference in its `Audio` field instead of an audio file. It is preserved as-is and is the one image counted in the media table.
- **100 notes keep Arabic numerals in `Hanzi`** and show the reading beside them, for example `100 (yībǎi)`. This dual display is intentional.
- **100 lines are alignment exceptions** for number/number-expanded or one-character-numeral lines. They are expected and checked by the validator.
- **361 runs of three or more third tones** cross word or clause boundaries and are intentionally left unmarked under the conservative sandhi policy. They are listed in `data/sandhi_review.csv`.
- **172 traditional round-trip differences** are stylistic `s2tw` choices such as `著` and `計畫`, not conversion misses.
- **51 A/B dialogue notes** keep the speaker label in `Hanzi` but exclude it from pronounced pinyin, by design.
- **Names and places** use a curated lexicon; they are not general-G2P guesses.
- **Nine removed duplicate copies** leave nine unused audio files in the package. All media bytes and the media map are preserved, but those files are no longer referenced.
- **The source APKG is not distributed in the Git repository.** It is required to rebuild from scratch. The packaged deck is published as a release asset.

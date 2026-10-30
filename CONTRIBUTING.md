# Contributing

Thanks for helping improve Forkfed Chinese. Corrections, build fixes, and documentation improvements are welcome.

## Reporting a deck correction

Open an issue using the **Deck correction** template and include:

- the sentence in Hanzi;
- the current pinyin, translation, or character;
- the proposed correction;
- evidence: a dictionary entry, a rule reference, context, or an audio timestamp;
- the Anki note ID or `SortOrder` if you have it (shown in the card browser).

Examples of useful reports:

- a polyphone that was read in the wrong context;
- a neutral-tone or erhua decision that should change;
- a mistranslation or missing line;
- an audio cutoff (include the timestamp and which syllable is cut).

Please do not report intentional policy decisions as errors unless you have new evidence. The known exceptions are listed in [Quality and audit](docs/QUALITY.md#known-limits).

## Code changes

1. Fork the repository and create a branch.
2. Keep changes consistent with the existing script and data conventions.
3. Add a note to `CHANGELOG.md` for user-visible changes.
4. Run the relevant pipeline steps and validations.
5. Open a pull request describing the behavior change and the checks you ran.

### Full rebuild

The source APKG is not committed because of its size. Follow [Building from source](docs/BUILDING.md) to place it in `source/`, install dependencies, and run the pipeline.

### Repository checks

CI runs these lightweight checks on every push and pull request:

```powershell
python -m compileall -q scripts
python scripts/check_repo.py
```

`check_repo.py` verifies required repository files and local documentation links. It does not need the source APKG.

### Template-only changes

```powershell
python scripts/07_build_apkg.py
python scripts/validate_deck.py
```

### Data corrections

Curated readings live in:

- `scripts/lib/sp_lexicon.py` — neutral tones, erhua, names/places, polyphones;
- `scripts/lib/sp_phase2.py` — reviewed Phase 2 word/line corrections;
- `scripts/lib/sp_numbers.py` — number readings and number expansion;
- `scripts/lib/sp_feedback.py` — community feedback triage.

After editing a data source, rerun the affected stages and the validators. The expected order is documented in [Building from source](docs/BUILDING.md).

## What not to commit

Generated data, source packages, and built packages are ignored intentionally:

- `data/` (except `data/feedback_source.txt` and `data/README.md`) is generated;
- `source/*.apkg` is the source input;
- `dist/*.apkg` is the release artifact.

Publish the built APKG as a GitHub release asset, not as a tracked file.

## Licensing

By contributing code or documentation, you agree that it may be distributed under the repository's MIT license. Deck content, translations, and audio remain subject to the original Spoonfed Chinese terms; do not add media you do not have the right to distribute.

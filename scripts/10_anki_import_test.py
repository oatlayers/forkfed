"""Headless Anki import smoke test for the release APKG.

This uses Anki's Python backend (the same importer as Anki desktop) in a clean
temporary collection.  It is not a substitute for the GUI/AnkiDroid check, but
it catches package, schema, note-type, sort-field, tag, and duplicate-import
problems.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from anki.collection import Collection
from anki.import_export_pb2 import (
    ImportAnkiPackageOptions,
    ImportAnkiPackageRequest,
    ImportAnkiPackageUpdateCondition,
)

ROOT = Path(__file__).resolve().parents[1]
APKG = ROOT / "dist" / "Forkfed_Chinese.apkg"

FIELDS = [
    "English",
    "Pinyin",
    "Hanzi",
    "Audio",
    "HanziTraditional",
    "PinyinSandhi",
    "PinyinOriginal",
    "Zhuyin",
    "ZhuyinSandhi",
    "Sequence",
    "SortOrder",
]


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="forkfed-anki-") as tmp:
        col_path = os.path.join(tmp, "collection.anki2")
        col = Collection(col_path)
        try:
            request = ImportAnkiPackageRequest(
                package_path=str(APKG),
                options=ImportAnkiPackageOptions(
                    merge_notetypes=True,
                    update_notes=ImportAnkiPackageUpdateCondition.Value(
                        "IMPORT_ANKI_PACKAGE_UPDATE_CONDITION_ALWAYS"
                    ),
                    update_notetypes=ImportAnkiPackageUpdateCondition.Value(
                        "IMPORT_ANKI_PACKAGE_UPDATE_CONDITION_ALWAYS"
                    ),
                    with_scheduling=True,
                    with_deck_configs=True,
                ),
            )
            col.import_anki_package(request)
            note_count = col.note_count()
            card_count = col.card_count()
            assert note_count == 7326, f"note count {note_count}"
            assert card_count == 7326, f"card count {card_count}"

            models = col.models.all()
            deck_models = [
                model
                for model in models
                if [field["name"] for field in model["flds"]] == FIELDS
            ]
            assert len(deck_models) == 1, f"{len(deck_models)} deck note types"
            model = deck_models[0]
            assert model["name"] == "Forkfed Chinese", model["name"]
            assert model["sortf"] == 10, f"sortf {model['sortf']}"
            assert len(model["tmpls"]) == 1, "template count changed"
            assert 'class="pinyin hover-pinyin"' in model["tmpls"][0]["qfmt"]
            assert "{{Audio}}" in model["tmpls"][0]["afmt"]

            note_ids = col.find_notes("")
            assert len(note_ids) == 7326
            first = col.get_note(note_ids[0])
            assert first["Hanzi"] == "你好！"
            assert first["Pinyin"] == "Nǐ hǎo!"
            assert first["PinyinSandhi"].startswith(
                '<b class="tone-change">Ní</b>'
            )
            assert first["Sequence"] == "1"
            assert first["SortOrder"] == "00001"
            assert first.tags == [], first.tags
            assert "[sound:" in first["Audio"]

            card = first.cards()[0]
            assert card.due == 1, card.due
            output = card.render_output()
            assert "你好" in output.question_text
            assert "hover-pinyin" in output.question_text
            assert "nǐ" in output.question_text.lower()
            assert "nǐ" in output.answer_text.lower()
            assert "Hello" in output.answer_text
            assert "ㄋㄧ" not in output.answer_text
            assert "ㄋㄧ" not in output.question_text

            dialogue = None
            for nid in note_ids:
                candidate = col.get_note(nid)
                if "<br>" in candidate["Hanzi"] and "<br>" in candidate["Pinyin"]:
                    dialogue = candidate
                    break
            assert dialogue is not None, "multi-line dialogue note missing"
            dialogue_output = dialogue.cards()[0].render_output()
            assert "<br>" in dialogue_output.question_text
            assert "<br>" in dialogue_output.answer_text
            assert "<br>" in dialogue_output.question_text.split("hover-pinyin", 1)[-1]

            number_note = None
            for nid in note_ids:
                candidate = col.get_note(nid)
                if "100万" in candidate["Hanzi"]:
                    number_note = candidate
                    break
            assert number_note is not None, "number note missing"
            assert "100 (yībǎi)" in number_note["Pinyin"]
            assert "100" in number_note["Zhuyin"]

            # Importing the same package again must update, not duplicate.
            col.import_anki_package(request)
            assert col.note_count() == 7326, "duplicate import created notes"
            assert col.card_count() == 7326, "duplicate import created cards"

            print(
                {
                    "notes": note_count,
                    "cards": card_count,
                    "models": len(models),
                    "deck_models": len(deck_models),
                    "fields": [field["name"] for field in model["flds"]],
                    "first_note": first["Hanzi"],
                    "sort_order": first["SortOrder"],
                    "due": card.due,
                    "duplicate_import_notes": col.note_count(),
                }
            )
        finally:
            col.close()


if __name__ == "__main__":
    main()

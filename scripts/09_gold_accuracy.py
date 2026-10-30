"""Measure gold-set accuracy on the fixed 200-note random sample.

The sample is the ``gold-random`` slice of ``data/review_queue.csv``.  Every
note was read in Phase 2; the one tone issue found is listed below and checked
against the corrected deck.  Segmental syllables are counted from the aligned
lexical pinyin.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import sp_common as c  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# Issues found while reading the 200-note random sample.  ``before`` is the
# reviewed error, ``after`` the corrected form that must now be present.
ISSUES = [
    {
        "note_id": 1419644213074,
        "hanzi": "我爱我的母亲。",
        "before": "mǔqin",
        "after": "mǔqīn",
        "kind": "tone",
    },
]


def main() -> None:
    queue = [
        row
        for row in csv.DictReader((DATA / "review_queue.csv").open(encoding="utf-8-sig"))
        if row["category"] == "gold-random"
    ]
    ids = {int(row["example_note_id"]) for row in queue}
    data = json.loads((DATA / "zhuyin_traditional.json").read_text(encoding="utf-8"))

    notes = 0
    lines = 0
    syllables = 0
    by_id = {}
    for note in data["notes"]:
        if note["id"] not in ids:
            continue
        notes += 1
        by_id[note["id"]] = note
        for line in note["lines"]:
            lines += 1
            items = c.parse_pinyin_line(line["pinyin"], line["hanzi"])
            items, ok = c.align_items_to_hanzi(line["hanzi"], items)
            if ok:
                syllables += sum(1 for item in items if item.kind == "syl")

    unresolved = []
    for issue in ISSUES:
        note = by_id.get(issue["note_id"])
        if note is None:
            unresolved.append(f"{issue['note_id']}: note missing from random sample")
            continue
        text = " ".join(line["pinyin"] for line in note["lines"])
        if issue["before"] in text:
            unresolved.append(
                f"{issue['note_id']}: old reading {issue['before']} still present"
            )
        if issue["after"] not in text:
            unresolved.append(
                f"{issue['note_id']}: corrected reading {issue['after']} missing"
            )

    tone_errors_before = sum(1 for issue in ISSUES if issue["kind"] == "tone")
    segmental_errors_before = sum(
        1 for issue in ISSUES if issue["kind"] == "segmental"
    )
    tone_after = tone_errors_before - len(
        [i for i in ISSUES if i["kind"] == "tone" and i not in unresolved]
    )
    tone_after = max(0, tone_after)
    syllable_after = max(0, segmental_errors_before - len(unresolved))
    tone_accuracy_before = 1 - tone_errors_before / syllables
    tone_accuracy_after = 1 - tone_after / syllables
    syllable_accuracy_before = 1 - segmental_errors_before / syllables
    syllable_accuracy_after = 1 - syllable_after / syllables

    result = {
        "notes": notes,
        "lines": lines,
        "syllables": syllables,
        "tone_before": tone_accuracy_before,
        "tone_after": tone_accuracy_after,
        "syllable_before": syllable_accuracy_before,
        "syllable_after": syllable_accuracy_after,
        "issues": ISSUES,
        "unresolved": unresolved,
    }
    (DATA / "gold_set_accuracy.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if unresolved:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

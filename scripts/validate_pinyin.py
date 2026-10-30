"""Validate the generated pinyin data before adding sandhi/zhuyin/traditional."""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import sp_common as c  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def main() -> None:
    raw = json.loads((DATA / "notes.json").read_text(encoding="utf-8"))
    data = json.loads((DATA / "pinyin.json").read_text(encoding="utf-8"))
    notes = data["notes"]
    raw_by_id = {n["id"]: n for n in raw}
    stats = Counter()
    problems = []

    with (DATA / "duplicates.csv").open(encoding="utf-8-sig", newline="") as fh:
        duplicate_rows = list(csv.DictReader(fh))
    deleted_ids = {int(row["deleted_note_id"]) for row in duplicate_rows}
    note_ids = {n["id"] for n in notes}
    if set(raw_by_id) - note_ids != deleted_ids:
        problems.append(
            ("deleted-set", sorted(set(raw_by_id) - note_ids), sorted(deleted_ids))
        )
    if note_ids & deleted_ids:
        problems.append(("deleted-present", sorted(note_ids & deleted_ids), ""))

    for note in notes:
        old = raw_by_id.get(note["id"])
        if old is None:
            problems.append(("missing-raw", note["id"], ""))
            continue
        stats["notes"] += 1
        if note["guid"] != old["guid"]:
            problems.append(("guid", note["id"], note["guid"]))
        if sorted(note["tags"]) != sorted(old["tags"]):
            problems.append(("tags", note["id"], note["tags"]))
        if note["audio_refs"] != old["audio_refs"]:
            problems.append(("audio", note["id"], note["audio_refs"]))
        if not note["pinyin_original"].strip():
            problems.append(("empty-original", note["id"], ""))
        if not note["pinyin"].strip():
            problems.append(("empty-pinyin", note["id"], ""))
        if re.search(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]+);", note["pinyin"]):
            problems.append(("entity", note["id"], note["pinyin"]))
        if any(ch in note["pinyin"] for ch in "\u200b\u200c\u200d\ufeffɡŏ"):
            problems.append(("bad-char", note["id"], note["pinyin"]))
        if re.search(r"[\u4e00-\u9fff]", note["pinyin"]):
            problems.append(("hanzi-in-pinyin", note["id"], note["pinyin"]))
        for line in note["lines"]:
            stats["lines"] += 1
            hz = line["hanzi"]
            py = line["pinyin"]
            if not py.strip():
                problems.append(("empty-line", note["id"], line["index"]))
                continue
            items = c.parse_pinyin_line(py, hz)
            items, ok = c.align_items_to_hanzi(hz, items)
            cjk = sum(1 for ch in hz if c.is_cjk(ch))
            if not ok:
                if "number" in line["flags"] or "align-fail-preserved" in line["flags"]:
                    stats["allowed-align-fail"] += 1
                else:
                    problems.append(
                        ("align", note["id"], line["index"], hz, py, cjk, len([i for i in items if i.kind == "syl"]))
                    )
            elif any(ch.isdigit() for ch in hz):
                stats["number-align-ok"] += 1
            else:
                stats["align-ok"] += 1
            # Every run must either parse or be a Latin literal.
            for it in items:
                if it.kind == "lit" and re.search(r"[A-Za-z]", it.text):
                    stats["latin-literals"] += 1
            if "  " in py:
                problems.append(("double-space", note["id"], line["index"], py))
            if py != py.strip():
                problems.append(("edge-space", note["id"], line["index"], py))
            # Pinyin should start with a capital letter at the start of a line
            # unless it begins with a quote/parenthesis/number/Latin.
            first = py.lstrip('"“\'‘（(')[:1]
            if first and first.isalpha() and not first.isupper():
                stats["lowercase-line-start"] += 1

    print("stats", dict(stats))
    print("problems", len(problems))
    for p in problems[:80]:
        print(p)

    print("\nsummary", json.dumps(data["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

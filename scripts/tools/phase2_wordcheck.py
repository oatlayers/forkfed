"""Independent word-reading check against pypinyin's phrase dictionary.

For each jieba word of two or more Hanzi whose pinyin alignment is one syllable
per character, compare the deck reading with pypinyin's phrase reading.  The
report is a Phase 2 review aid, not an automatic fixer.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

import jieba
from pypinyin import Style, pinyin

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import sp_common as c  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


def main() -> None:
    data = json.loads((DATA / "zhuyin_traditional.json").read_text(encoding="utf-8"))
    rows: list[dict] = []
    for note in data["notes"]:
        for line in note["lines"]:
            hanzi = line["hanzi"]
            items = c.parse_pinyin_line(line["pinyin"], hanzi)
            items, ok = c.align_items_to_hanzi(hanzi, items)
            if not ok:
                continue
            by_char: dict[int, c.Syllable] = {}
            for item in items:
                if item.kind == "syl" and item.span and item.syl is not None:
                    if item.span[1] - item.span[0] == 1:
                        by_char[item.span[0]] = item.syl
            pos = 0
            for word in jieba.cut(hanzi):
                start = pos
                pos += len(word)
                if len(word) < 2 or any(not c.is_cjk(ch) for ch in word):
                    continue
                syls = [by_char.get(start + i) for i in range(len(word))]
                if any(s is None for s in syls):
                    continue
                py = [
                    c.syllable_from_text(x[0])
                    for x in pinyin(word, style=Style.TONE, heteronym=False)
                ]
                if any(s is None for s in py) or len(py) != len(syls):
                    continue
                diffs = []
                for cur, ref in zip(syls, py):
                    assert cur is not None and ref is not None
                    if cur.key == ref.key:
                        continue
                    # Neutral tone is a deliberate deck prior; only report a
                    # difference when both readings carry a full tone.
                    if ref.tone == 0 or cur.tone == 0:
                        continue
                    diffs.append((cur.surface_text(), ref.surface_text()))
                if not diffs:
                    continue
                rows.append(
                    {
                        "note_id": note["id"],
                        "hanzi": hanzi,
                        "word": word,
                        "current": " ".join(s.surface_text() for s in syls if s),
                        "reference": " ".join(s.surface_text() for s in py if s),
                        "diffs": " ".join(f"{a}->{b}" for a, b in diffs),
                        "pinyin": line["pinyin"],
                    }
                )
    out = DATA / "word_reading_review.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("rows", len(rows))
    counts = Counter(row["word"] for row in rows)
    for word, count in counts.most_common(80):
        print(f"{count:4d} {word}")


if __name__ == "__main__":
    main()

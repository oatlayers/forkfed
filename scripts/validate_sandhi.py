"""Validate ``data/sandhi.json`` produced by ``04_tone_sandhi.py``.

Checks:
* every note/line is present and nonempty;
* the lexical ``Pinyin`` is unchanged from ``data/pinyin.json``;
* only ``<b class="tone-change">`` tags occur;
* every bold span wraps exactly one valid pinyin syllable;
* the bold count equals ``sandhi_changed``;
* removing tags leaves the same syllable bases and separators as the lexical
  line (only tones may differ), and every tone change is accounted for.

Exit status is nonzero when a problem is found.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import sp_common as c  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

BOLD_RE = re.compile(r'<b class="tone-change">(.*?)</b>')
TAG_RE = re.compile(r"<[^>]+>")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    source = read_json(DATA / "pinyin.json")
    data = read_json(DATA / "sandhi.json")
    src_notes = {n["id"]: n for n in source["notes"]}
    notes = data["notes"]
    problems: list[str] = []

    if len(notes) != len(src_notes):
        problems.append(f"note count {len(notes)} != {len(src_notes)}")

    for note in notes:
        src = src_notes.get(note["id"])
        if src is None:
            problems.append(f"note {note['id']}: unknown id")
            continue
        if note["pinyin"] != src["pinyin"]:
            problems.append(f"note {note['id']}: lexical Pinyin changed")
        if note["hanzi"] != src["hanzi"]:
            problems.append(f"note {note['id']}: Hanzi changed")
        src_lines = {x["index"]: x for x in src["lines"]}
        if len(note["lines"]) != len(src_lines):
            problems.append(f"note {note['id']}: line count changed")
        for line in note["lines"]:
            where = f"note {note['id']} line {line['index']}"
            sl = src_lines.get(line["index"])
            if sl is None:
                problems.append(f"{where}: unknown line")
                continue
            if line["pinyin"] != sl["pinyin"] or line["hanzi"] != sl["hanzi"]:
                problems.append(f"{where}: source fields changed")
            surface = line["pinyin_sandhi"]
            if not surface.strip():
                problems.append(f"{where}: empty PinyinSandhi")
                continue

            without_bold = BOLD_RE.sub(lambda m: m.group(1), surface)
            if TAG_RE.search(without_bold):
                problems.append(f"{where}: unexpected HTML tag")
            bolds = BOLD_RE.findall(surface)
            if len(bolds) != line["sandhi_changed"]:
                problems.append(
                    f"{where}: {len(bolds)} bold spans != sandhi_changed {line['sandhi_changed']}"
                )
            for bold in bolds:
                seg = c.segment_run(bold.lower())
                if seg is None or len(seg) != 1:
                    problems.append(f"{where}: bold span is not one syllable: {bold!r}")

            lex_items = c.parse_pinyin_line(line["pinyin"], line["hanzi"])
            lex_items, lex_ok = c.align_items_to_hanzi(line["hanzi"], lex_items)
            sur_items = c.parse_pinyin_line(without_bold, line["hanzi"])
            sur_items, sur_ok = c.align_items_to_hanzi(line["hanzi"], sur_items)
            if not lex_ok:
                # Skipped lines keep lexical text with no bold.
                if bolds:
                    problems.append(f"{where}: bold on unaligned line")
                if without_bold != c.escape_text(line["pinyin"]):
                    problems.append(f"{where}: skipped line text changed")
                continue
            if not sur_ok:
                problems.append(f"{where}: surface text no longer aligns")
                continue

            lex_syl = [it for it in lex_items if it.kind == "syl"]
            sur_syl = [it for it in sur_items if it.kind == "syl"]
            if len(lex_syl) != len(sur_syl):
                problems.append(f"{where}: syllable count changed")
                continue
            tone_diffs = 0
            for a, b in zip(lex_syl, sur_syl):
                assert a.syl is not None and b.syl is not None
                if a.syl.base != b.syl.base or a.syl.erhua != b.syl.erhua:
                    problems.append(
                        f"{where}: syllable changed {a.syl.display!r} -> {b.syl.display!r}"
                    )
                if a.syl.tone != b.syl.tone:
                    tone_diffs += 1
            if tone_diffs != len(bolds):
                problems.append(
                    f"{where}: {tone_diffs} tone diffs != {len(bolds)} bold spans"
                )
            if not bolds and line["sandhi_changed"] != 0:
                problems.append(f"{where}: changed count without bold")
            # Non-syllable text must be preserved.
            lex_sep = [it.text for it in lex_items if it.kind != "syl"]
            sur_sep = [it.text for it in sur_items if it.kind != "syl"]
            if lex_sep != sur_sep:
                problems.append(f"{where}: separators changed {lex_sep!r} -> {sur_sep!r}")

    print(f"notes: {len(notes)}")
    print(f"lines: {sum(len(n['lines']) for n in notes)}")
    print(f"problems: {len(problems)}")
    for problem in problems[:120]:
        print(" -", problem)
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

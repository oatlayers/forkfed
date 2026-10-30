"""Phase 1 / step 5: zhuyin, zhuyin sandhi and traditional characters.

* ``Zhuyin`` is generated from the corrected lexical pinyin syllables, so it
  never inherits pypinyin's phrase-level sandhi.
* ``ZhuyinSandhi`` uses the surface tones from ``PinyinSandhi`` and bolds the
  same changed syllables.
* ``HanziTraditional`` uses OpenCC ``s2tw`` (Taiwan-standard character forms,
  no vocabulary substitution).  A small explicit fix table covers variant
  words that the deck uses.

Writes ``data/zhuyin_traditional.json``.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import opencc

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import sp_common as c  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

S2TW = opencc.OpenCC("s2tw")
T2S = opencc.OpenCC("t2s")
TRAD_FIXES = {
    "重覆": "重複",
    "部份": "部分",
    # opencc-python-reimplemented chooses 覆 for 复 after 天/昨天/今天 etc.
    "覆習": "複習",
    # Phrase-boundary errors seen in this deck (the converter matches across
    # word boundaries: 音樂/傢什麼, 這/傢俱樂部, 拍手/錶示, ...).
    "音樂傢": "音樂家",
    "傢俱樂部": "家俱樂部",
    "手錶示": "手表示",
    "一箇": "一個",
    "鬍須": "鬍鬚",
    "頭髮幹": "頭髮乾",
    "相對的是幹": "相對的是乾",
    "衝洗": "沖洗",
    "遊泳": "游泳",
    "遊一百米": "游一百米",
    "遊得很快": "游得很快",
    "遊5公里": "游5公里",
    "遊過河": "游過河",
    "遊了泳": "游了泳",
    "曆史": "歷史",
    "復雜": "複雜",
    "丑聞": "醜聞",
    "喂一下": "餵一下",
    "迴歸": "回歸",
    # Contextual one-to-many misses: 里/後/佔/遊 are correct in some phrases
    # but must convert in these deck phrases.
    "記事本里": "記事本裡",
    "大海里": "大海裡",
    "海里的": "海裡的",
    "碗里": "碗裡",
    "東西后": "東西後",
    "人口占": "人口佔",
    "游蕩": "遊蕩",
    # opencc-python-reimplemented maps the rare 幺 to 么; this deck uses 小幺
    # (the youngest child), which must not become 小么.
    "小么": "小幺",
}

ZH_TEST_ROWS = [
    ("你好！", "Nǐ hǎo!", "ㄋㄧˇ ㄏㄠˇ！"),
    ("妈妈", "Māma", "ㄇㄚ ˙ㄇㄚ"),
    ("哪儿", "Nǎr", "ㄋㄚˇㄦ"),
    ("女儿", "Nǚ'ér", "ㄋㄩˇ ㄦˊ"),
    ("一个", "Yī gè", "ㄧ ㄍㄜˋ"),
    ("哎哟！", "Āiyō!", "ㄞ ㄧㄛ！"),
]

TRAD_TEST_ROWS = [
    ("你好！", "你好！"),
    ("重复", "重複"),
    ("部分", "部分"),
    ("面条", "麵條"),
    ("台湾", "臺灣"),
    ("软件", "軟件"),
    ("每天复习很重要。", "每天複習很重要。"),
    ("历史", "歷史"),
    ("复杂", "複雜"),
    ("丑闻", "醜聞"),
    ("头发干了。", "頭髮乾了。"),
    ("她在冲洗头发。", "她在沖洗頭髮。"),
    ("音乐家什么时候来？", "音樂家什麼時候來？"),
    ("这家俱乐部", "這家俱樂部"),
    ("你能游一百米吗？", "你能游一百米嗎？"),
    ("小幺", "小幺"),
    ("记事本里", "記事本裡"),
    ("大海里", "大海裡"),
    ("海里的珊瑚", "海裡的珊瑚"),
    ("碗里", "碗裡"),
    ("买完东西后", "買完東西後"),
    ("人口占总人口", "人口佔總人口"),
    ("在街上游荡", "在街上遊蕩"),
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def convert_traditional(text: str) -> str:
    out = S2TW.convert(text)
    for old, new in TRAD_FIXES.items():
        out = out.replace(old, new)
    return out


def run_self_tests() -> None:
    for hz, py, expected in ZH_TEST_ROWS:
        got = c.render_zhuyin(c.parse_pinyin_line(py, hz))
        if got != expected:
            raise SystemExit(f"zhuyin self-test failed: {hz}: {got!r} != {expected!r}")
    for simplified, expected in TRAD_TEST_ROWS:
        got = convert_traditional(simplified)
        if got != expected:
            raise SystemExit(
                f"traditional self-test failed: {simplified}: {got!r} != {expected!r}"
            )
    surface = '<b class="tone-change">Ní</b> hǎo!'
    items = c.parse_pinyin_line(c.strip_bold(surface), "你好！")
    for it in items:
        if it.kind == "syl" and it.syl is not None and it.syl.tone == 2:
            it.changed = True
    got = c.render_zhuyin(items, surface=True)
    expected = '<b class="tone-change">ㄋㄧˊ</b> ㄏㄠˇ！'
    if got != expected:
        raise SystemExit(f"zhuyin bold self-test failed: {got!r} != {expected!r}")


def zhuyin_line(line: dict) -> tuple[str, str, int, list[str]]:
    """Return (lexical zhuyin, sandhi zhuyin, changed count, flags)."""
    hz = line["hanzi"]
    lex_items = c.parse_pinyin_line(line["pinyin"], hz)
    lex_syl = [it for it in lex_items if it.kind == "syl"]

    plain = c.strip_bold(line["pinyin_sandhi"])
    sur_items = c.parse_pinyin_line(plain, hz)
    sur_syl = [it for it in sur_items if it.kind == "syl"]

    flags: list[str] = []
    changed = 0
    if len(lex_syl) == len(sur_syl):
        for a, b in zip(lex_syl, sur_syl):
            assert a.syl is not None and b.syl is not None
            if a.syl.tone != b.syl.tone:
                b.changed = True
                changed += 1
    else:
        flags.append("zhuyin-sandhi-mismatch")

    # The PinyinSandhi tag count is the authority for the deck contract.
    expected_changed = len(re.findall(r'<b class="tone-change">', line["pinyin_sandhi"]))
    if changed != expected_changed:
        flags.append("zhuyin-bold-mismatch")

    lex_zy = c.render_zhuyin(lex_items)
    sur_zy = c.render_zhuyin(sur_items, surface=True)
    return lex_zy, sur_zy, changed, flags


def main() -> None:
    run_self_tests()
    data = read_json(DATA / "sandhi.json")
    notes = data["notes"]

    out_notes = []
    stats: Counter = Counter()
    trad_roundtrip_diffs: list[dict] = []
    zh_failures: list[dict] = []
    zh_bold_mismatches: list[dict] = []

    for note in notes:
        out_lines = []
        for line in note["lines"]:
            hz = line["hanzi"]
            lex_zy, sur_zy, changed, flags = zhuyin_line(line)
            if not lex_zy.strip() or not sur_zy.strip():
                zh_failures.append(
                    {"note_id": note["id"], "line": line["index"], "hanzi": hz}
                )
                flags.append("zhuyin-empty")
            if "zhuyin-bold-mismatch" in flags:
                zh_bold_mismatches.append(
                    {
                        "note_id": note["id"],
                        "line": line["index"],
                        "hanzi": hz,
                        "pinyin_sandhi": line["pinyin_sandhi"],
                        "zhuyin_sandhi": sur_zy,
                    }
                )
            # Preserve A/B dialogue labels in the Traditional field; zhuyin is
            # rendered from the label-free G2P text above.
            hz_display = line.get("hanzi_display", hz)
            traditional = convert_traditional(hz_display)
            back = T2S.convert(traditional)
            if back != hz_display:
                trad_roundtrip_diffs.append(
                    {
                        "note_id": note["id"],
                        "line": line["index"],
                        "hanzi": hz_display,
                        "traditional": traditional,
                        "roundtrip": back,
                    }
                )
            stats["lines"] += 1
            stats["zhuyin_changed"] += changed
            if traditional != hz_display:
                stats["traditional_changed_lines"] += 1
            out_lines.append(
                {
                    **line,
                    "hanzi_traditional": traditional,
                    "zhuyin": lex_zy,
                    "zhuyin_sandhi": sur_zy,
                    "zhuyin_changed": changed,
                    "zhuyin_flags": flags,
                }
            )

        out_notes.append(
            {
                **note,
                "hanzi_traditional": "<br>".join(
                    x["hanzi_traditional"] for x in out_lines
                ),
                "zhuyin": "<br>".join(x["zhuyin"] for x in out_lines),
                "zhuyin_sandhi": "<br>".join(x["zhuyin_sandhi"] for x in out_lines),
                "lines": out_lines,
            }
        )

    summary = {
        "note_count": len(out_notes),
        "line_count": stats["lines"],
        "changed_syllables": stats["zhuyin_changed"],
        "traditional_changed_lines": stats["traditional_changed_lines"],
        "zhuyin_failures": len(zh_failures),
        "zhuyin_bold_mismatches": len(zh_bold_mismatches),
        "traditional_roundtrip_diffs": len(trad_roundtrip_diffs),
    }
    (DATA / "zhuyin_traditional.json").write_text(
        json.dumps(
            {
                "summary": summary,
                "notes": out_notes,
                "traditional_roundtrip_diffs": trad_roundtrip_diffs,
                "zhuyin_failures": zh_failures,
                "zhuyin_bold_mismatches": zh_bold_mismatches,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

"""Phase 1 / step 3: build corrected lexical pinyin.

Tiered strategy from the plan:

* keep the inherited pinyin unless there is a reason to change it;
* apply curated neutral-tone / erhua / name / reading lexicons;
* fix clear engine-consensus errors;
* protect proper nouns, polyphones and the deck's neutral-tone prior;
* flag everything ambiguous instead of silently guessing.

Writes ``data/pinyin.json`` and ``data/pinyin_corrections.csv``.
"""

from __future__ import annotations

import copy
import csv
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import jieba
from pypinyin import Style, lazy_pinyin, pinyin

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import sp_common as c  # noqa: E402
import sp_feedback as FB  # noqa: E402
import sp_lexicon as L  # noqa: E402
import sp_numbers as N  # noqa: E402
import sp_phase2 as P2  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SCRIPTS = ROOT / "scripts"

# ---------------------------------------------------------------------------
# Protected readings
# ---------------------------------------------------------------------------

# The deck's fixed polyphone appendix.  A difference is never auto-fixed
# inside these characters unless the original reading is invalid or the change
# is a straight third-tone-sandhi restoration.
TOP_POLYPHONES = set(
    "行长重还得着了地和数差发分好教觉空乐量难宁片强曲少说调为相兴应只中种转传处当倒更假间卷看累落没模那期切散色省似宿提系鲜血扎占正仔作"
)

YI_BU = {"一", "不"}

NEUTRAL_COMPOUND_BLOCKS = {
    "地方": ("政府", "政策", "官", "性", "主义", "戏", "话", "税", "债", "医院", "院校", "部队", "财政", "自治"),
    "东西": ("方", "文化", "西", "南", "北", "欧", "美"),
    "葡萄": ("牙",),
}

TITLES = sorted(L.TITLES, key=len, reverse=True)
SURNAME_RE = re.compile(
    "([" + re.escape("".join(sorted(L.COMMON_SURNAMES))) + r"][\u4e00-\u9fff]{1,2})(?:"
    + "|".join(re.escape(t) for t in TITLES)
    + ")"
)

INTERJECTIONS = set("啊呀哇哦噢哟")
LANGUAGE_WORDS = {
    "汉语", "普通话", "中文", "英文", "英语", "法语", "德语", "日语", "西班牙语",
}
NATIONALITY_WORDS = {
    "中国人", "美国人", "英国人", "德国人", "法国人", "日本人",
}

PINYIN_PUNCT = str.maketrans(
    {
        "“": '"', "”": '"', "‘": "'", "’": "'",
        "，": ",", "。": ".", "！": "!", "？": "?", "：": ":", "；": ";",
        "（": "(", "）": ")", "、": ",",
    }
)

# Merge lexicons once, in priority order.  Name/place wins over a generic
# reading, which wins over erhua, which wins over neutral-tone guidance.
LEXICON_ENTRIES: dict[str, dict] = {}
for _priority, (_lex, _reason, _proper) in enumerate(
    [
        (P2.WORD_FIXES, "phase2", False),
        (L.NAME_PLACE_LEXICON, "name-place", True),
        (L.READING_LEXICON, "reading", False),
        (L.ERHUA_LEXICON, "erhua", False),
        (L.NEUTRAL_LEXICON, "neutral", False),
    ]
):
    for _word, _reading in _lex.items():
        if not _word or not _reading:
            continue
        if _word not in LEXICON_ENTRIES:
            LEXICON_ENTRIES[_word] = {
                "reading": _reading,
                "reason": _reason,
                "proper": _proper or (_reason == "phase2" and _word in P2.PROPER_WORDS),
                "priority": _priority,
            }

LEX_BY_FIRST: dict[str, list[tuple[str, dict]]] = defaultdict(list)
for _word, _entry in LEXICON_ENTRIES.items():
    LEX_BY_FIRST[_word[0]].append((_word, _entry))
for _items in LEX_BY_FIRST.values():
    _items.sort(key=lambda item: (-len(item[0]), item[1]["priority"]))

READING_CACHE: dict[str, list[tuple[str, c.Syllable]] | None] = {}


# ---------------------------------------------------------------------------
# Reading / candidate helpers
# ---------------------------------------------------------------------------

def parse_reading(value: str) -> list[tuple[str, c.Syllable]] | None:
    """Parse ``nǚ'ér`` / ``bù kèqi`` into syllable and separator tokens."""
    if value in READING_CACHE:
        return READING_CACHE[value]
    out: list[tuple[str, c.Syllable]] = []
    for part in re.split(r"(\s+|['’])", value):
        if not part:
            continue
        if part.isspace() or part in {"'", "’"}:
            out.append(("sep", part))
            continue
        syls = c.parse_syllable_string(part)
        if syls is None:
            READING_CACHE[value] = None
            return None
        out.extend(("syl", s) for s in syls)
    READING_CACHE[value] = out
    return out


def run_pinyin_pro(lines: list[dict]) -> dict[str, list[dict]]:
    payload = {"lines": lines}
    in_path = Path(tempfile.gettempdir()) / "spoonfed_pinyinpro_in.json"
    out_path = Path(tempfile.gettempdir()) / "spoonfed_pinyinpro_out.json"
    in_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    subprocess.run(
        ["node", str(SCRIPTS / "lib" / "pinyin_pro_batch.js"), str(in_path), str(out_path)],
        cwd=ROOT,
        check=True,
    )
    data = json.loads(out_path.read_text(encoding="utf-8"))
    return {row["id"]: row.get("tokens", []) for row in data["lines"]}


def pro_map(line: str, tokens: list[dict]) -> dict[int, c.Syllable]:
    out: dict[int, c.Syllable] = {}
    pos = 0
    for tok in tokens:
        origin = tok.get("origin") or ""
        if not origin:
            continue
        start = line.find(origin, pos)
        if start < 0:
            start = pos if line.startswith(origin, pos) else -1
        if start < 0:
            continue
        if tok.get("isZh"):
            syl = c.syllable_from_text(tok.get("pinyin") or "")
            if syl is not None:
                # type: all normally emits one token per Hanzi character.
                for off, ch in enumerate(origin):
                    if c.is_cjk(ch):
                        out[start + off] = syl
        pos = start + len(origin)
    return out


def pypinyin_map(line: str) -> dict[int, c.Syllable]:
    tokens = lazy_pinyin(
        line,
        style=Style.TONE,
        tone_sandhi=False,
        neutral_tone_with_five=False,
        errors=lambda chars: list(chars),
    )
    if len(tokens) != len(line):
        tokens = [
            lazy_pinyin(ch, style=Style.TONE, tone_sandhi=False, errors=lambda x: "")[0]
            if c.is_cjk(ch)
            else ch
            for ch in line
        ]
    out: dict[int, c.Syllable] = {}
    for i, ch in enumerate(line):
        if not c.is_cjk(ch):
            continue
        token = tokens[i] if i < len(tokens) else ""
        # pypinyin still applies 一/不 sandhi even with tone_sandhi=False.
        if ch == "一":
            token = "yī"
        elif ch == "不":
            token = "bù"
        syl = c.syllable_from_text(token)
        if syl is not None:
            out[i] = syl
    return out


def consensus_map(
    pro: dict[int, c.Syllable], py: dict[int, c.Syllable]
) -> dict[int, c.Syllable]:
    return {
        i: pro[i]
        for i in pro
        if i in py and pro[i].key == py[i].key
    }


@lru_cache(maxsize=None)
def valid_readings(ch: str) -> frozenset[tuple[str, int, bool]]:
    try:
        readings = pinyin(ch, style=Style.TONE, heteronym=True, errors=lambda x: [])
    except Exception:
        return frozenset()
    out = set()
    for group in readings:
        for text in group:
            syl = c.syllable_from_text(text)
            if syl is not None:
                out.add(syl.key)
    return frozenset(out)


# ---------------------------------------------------------------------------
# Lexicon matching
# ---------------------------------------------------------------------------

def blocked_compound(word: str, hanzi: str, end: int) -> bool:
    for suffix in NEUTRAL_COMPOUND_BLOCKS.get(word, ()):
        if hanzi.startswith(suffix, end):
            return True
    return False


def find_occurrences(hanzi: str) -> list[dict]:
    candidates = []
    for start in range(len(hanzi)):
        for word, entry in LEX_BY_FIRST.get(hanzi[start], []):
            if not hanzi.startswith(word, start):
                continue
            end = start + len(word)
            if blocked_compound(word, hanzi, end):
                continue
            candidates.append(
                {
                    "start": start,
                    "end": end,
                    "word": word,
                    **entry,
                }
            )
    chosen = []
    last_end = -1
    for cand in sorted(candidates, key=lambda x: (x["start"], -len(x["word"]), x["priority"])):
        if cand["start"] < last_end:
            continue
        chosen.append(cand)
        last_end = cand["end"]
    return chosen


def occurrence_read_tokens(occ: dict) -> list[tuple[str, c.Syllable]] | None:
    return parse_reading(occ["reading"])


# ---------------------------------------------------------------------------
# Single-syllable correction
# ---------------------------------------------------------------------------

def sandhi_restore(orig: c.Syllable, cand: c.Syllable, next_syl: c.Syllable | None) -> bool:
    return (
        orig.base == cand.base
        and orig.tone == 2
        and cand.tone == 3
        and next_syl is not None
        and next_syl.tone == 3
    )


def correct_syllable(
    syl: c.Syllable,
    char_index: int,
    char: str,
    pro: dict[int, c.Syllable],
    py: dict[int, c.Syllable],
    cons: dict[int, c.Syllable],
    next_syl: c.Syllable | None,
    prev_char: str,
    proper_spans: set[int],
    line_flags: list[str],
) -> tuple[c.Syllable, dict | None]:
    """Return the syllable to emit and an optional correction record."""
    orig_key = syl.key
    cand = cons.get(char_index) or pro.get(char_index)

    if char in YI_BU:
        base, tone = ("yi", 1) if char == "一" else ("bu", 4)
        new = replace(syl, base=base, tone=tone, erhua=False)
        if new.key != orig_key:
            return new, {
                "kind": "syllable",
                "char_index": char_index,
                "char": char,
                "original": syl.surface_text(),
                "corrected": new.surface_text(),
                "reason": "lexical-yi-bu",
            }
        return syl, None

    if cand is None:
        line_flags.append("no-candidate")
        return syl, None
    if cand.key == orig_key:
        return syl, None
    if char_index in proper_spans:
        line_flags.append("proper-noun")
        return syl, None

    if char in INTERJECTIONS and cand.tone == 0 and syl.tone != 0:
        # Sentence-initial 啊/呀 is an interjection with its own tone; a
        # sentence-final particle is neutral.  Keep the former, fix the latter.
        if char_index == 0 or prev_char in "，。！？：；、,.!?;:":
            line_flags.append("interjection")
            return syl, None

    if sandhi_restore(syl, cand, next_syl):
        new = replace(syl, base=cand.base, tone=cand.tone, erhua=cand.erhua)
        return new, {
            "kind": "syllable",
            "char_index": char_index,
            "char": char,
            "original": syl.surface_text(),
            "corrected": new.surface_text(),
            "reason": "sandhi-lexicalized",
        }

    if char in TOP_POLYPHONES:
        if orig_key in valid_readings(char):
            line_flags.append("polyphone")
            return syl, None
        new = replace(syl, base=cand.base, tone=cand.tone, erhua=cand.erhua)
        return new, {
            "kind": "syllable",
            "char_index": char_index,
            "char": char,
            "original": syl.surface_text(),
            "corrected": new.surface_text(),
            "reason": "invalid-reading",
        }

    if cand.tone == 0 and syl.tone != 0:
        if char_index in cons:
            new = replace(syl, base=cand.base, tone=0, erhua=cand.erhua)
            return new, {
                "kind": "syllable",
                "char_index": char_index,
                "char": char,
                "original": syl.surface_text(),
                "corrected": new.surface_text(),
                "reason": "consensus-neutral",
            }
        line_flags.append("neutral-candidate")
        return syl, None

    if syl.tone == 0 and cand.tone != 0:
        # The inherited deck's neutral reading is a useful prior; do not let
        # two generators silently over-mark it.
        line_flags.append("original-neutral")
        return syl, None

    if char_index in cons:
        reason = "consensus-segmental" if cand.base != syl.base else "consensus-tone"
        if orig_key in valid_readings(char) and char not in TOP_POLYPHONES:
            # A valid reading that the consensus disagrees with is a real
            # ambiguity (e.g. 血 xuè/xiě); route it to review.
            line_flags.append("engine-disagree")
            return syl, None
        new = replace(syl, base=cand.base, tone=cand.tone, erhua=cand.erhua)
        return new, {
            "kind": "syllable",
            "char_index": char_index,
            "char": char,
            "original": syl.surface_text(),
            "corrected": new.surface_text(),
            "reason": reason,
        }

    line_flags.append("engine-disagree")
    return syl, None


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

CLOSE_PUNCT = "，。！？：；、）》」』】”’,.!?;:"
OPEN_PUNCT = "（《「『【“‘("
MEASURE_CHARS = set("个位名家家辆本张只条件杯瓶碗双套块元钱天年月日号分秒岁次场种遍趟")


def fallback_subtokens(tokens: list[str]) -> list[str]:
    """Split a few high-frequency prefixes that standard pinyin spaces out."""
    out: list[str] = []
    for token in tokens:
        if len(token) > 1 and token[0] == "不":
            out.extend([token[0], token[1:]])
        elif (
            len(token) > 1
            and token[0] in "一两几半"
            and token[1] in MEASURE_CHARS
        ):
            out.extend([token[0], token[1:]])
        else:
            out.append(token)
    return out


def smart_join(parts: list[str]) -> str:
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        if out and not (out[-1][-1] in OPEN_PUNCT or part[0] in CLOSE_PUNCT):
            out.append(" ")
        out.append(part)
    text = "".join(out)
    text = re.sub(r"\s+([" + re.escape(CLOSE_PUNCT) + r"])", r"\1", text)
    text = re.sub(r"([" + re.escape(OPEN_PUNCT) + r"])\s+", r"\1", text)
    return text.strip()


def render_reading_tokens(tokens: list[tuple[str, c.Syllable]], proper: bool, orig_first: c.Syllable | None):
    out: list[c.Item] = []
    first = True
    for kind, val in tokens:
        if kind == "sep":
            out.append(c.Item(kind="sep", text=val))
            continue
        syl = copy.copy(val)
        if proper and first:
            syl.cap = True
        elif first and orig_first is not None and orig_first.cap:
            syl.cap = True
        out.append(c.Item(kind="syl", syl=syl))
        first = False
    return out


def render_token(token: str, start: int, char_units: dict[int, list[c.Syllable]]) -> str:
    out: list[str] = []
    prev: c.Syllable | None = None
    for off, ch in enumerate(token):
        pos = start + off
        if not c.is_cjk(ch):
            out.append(ch.translate(PINYIN_PUNCT))
            prev = None
            continue
        for syl in char_units.get(pos, []):
            if prev is not None and c.needs_apostrophe(prev, syl):
                out.append("'")
            out.append(syl.surface_text())
            prev = syl
    return "".join(out)


LATIN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")

# Lexical words ending in neutral ``de`` that must stay written as one word.
# Everything else with a neutral 的/地/得 is treated as a particle and split
# from the preceding syllable (the plan's ``nǐde`` -> ``nǐ de`` rule).
DE_KEEP_DE = {
    "似的",
}
DE_KEEP_DE2 = {
    "觉得", "记得", "值得", "显得", "懂得", "懒得", "使得", "晓得",
    "认得", "免得", "省得", "舍得", "舍不得", "巴不得", "了不得",
    "恨不得", "怪不得", "由不得", "说不得", "要不得", "吃不得",
}


def split_particle_de(hanzi: str, pinyin_text: str) -> tuple[str, list[dict]]:
    """Split attached neutral 的/地/得 particles from the preceding syllable."""
    items = c.parse_pinyin_line(pinyin_text, hanzi)
    items, ok = c.align_items_to_hanzi(hanzi, items)
    if not ok:
        return pinyin_text, []
    out: list[c.Item] = []
    fixes: list[dict] = []
    for i, item in enumerate(items):
        split = False
        if (
            item.kind == "syl"
            and item.syl is not None
            and item.syl.base == "de"
            and item.syl.tone == 0
            and item.span is not None
        ):
            pos = item.span[0]
            char = hanzi[pos]
            prev = items[i - 1] if i > 0 else None
            attached = (
                prev is not None
                and prev.kind == "syl"
                and prev.syl is not None
                and prev.span is not None
                and prev.span[1] == pos
            )
            if attached and char in "的地得":
                prefix = hanzi[: pos + 1]
                if char == "的":
                    split = not any(prefix.endswith(word) for word in DE_KEEP_DE)
                elif char == "地":
                    split = True
                else:
                    split = not any(prefix.endswith(word) for word in DE_KEEP_DE2)
        if split:
            assert item.span is not None
            prev = items[i - 1]
            assert prev is not None and prev.syl is not None
            original = prev.syl.surface_text() + item.syl.surface_text()  # type: ignore[union-attr]
            corrected = prev.syl.surface_text() + " " + item.syl.surface_text()  # type: ignore[union-attr]
            fixes.append(
                {
                    "kind": "spacing",
                    "char_index": item.span[0],
                    "char": hanzi[item.span[0]],
                    "word": hanzi[max(0, item.span[0] - 1) : item.span[0] + 1],
                    "original": original,
                    "corrected": corrected,
                    "reason": "particle-spacing",
                }
            )
            out.append(c.Item(kind="sep", text=" "))
        out.append(item)
    if not fixes:
        return pinyin_text, []
    return c.render_units(out), fixes


def fix_latin_case(hanzi: str, pinyin_text: str) -> tuple[str, list[dict]]:
    """Match Latin tokens to the casing used in the Hanzi line.

    Names and acronyms in the source are inconsistent (``Atm``, ``jake``,
    ``ibm``).  The Hanzi field is the authority for spelling, so ``ATM`` in
    Hanzi yields ``ATM`` in pinyin.  Only whole Latin tokens surrounded by
    non-letters are touched, so pinyin syllables such as ``kàn`` are safe.
    """
    wanted = {
        m.group(0).lower(): m.group(0) for m in LATIN_TOKEN_RE.finditer(hanzi)
    }
    if not wanted:
        return pinyin_text, []
    fixes: list[dict] = []
    pattern = re.compile(
        r"(?<![^\W\d_])[A-Za-z][A-Za-z0-9]*(?![^\W\d_])"
    )

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        target = wanted.get(token.lower())
        if target is None or token == target:
            return token
        fixes.append(
            {
                "kind": "latin",
                "char_index": None,
                "char": "",
                "word": target,
                "original": token,
                "corrected": target,
                "reason": "latin-case",
            }
        )
        return target

    return pattern.sub(replace, pinyin_text), fixes


def fallback_line(
    hanzi: str,
    pro: dict[int, c.Syllable],
    py: dict[int, c.Syllable],
    cons: dict[int, c.Syllable],
    occurrences: list[dict],
) -> str:
    char_units: dict[int, list[c.Syllable]] = {}
    for i, ch in enumerate(hanzi):
        if not c.is_cjk(ch):
            continue
        cand = cons.get(i) or pro.get(i) or py.get(i)
        if ch == "一":
            cand = c.Syllable(base="yi", tone=1)
        elif ch == "不":
            cand = c.Syllable(base="bu", tone=4)
        if cand is not None:
            char_units[i] = [copy.copy(cand)]

    # Lexicon words spanning the line.  Assign readings to characters where
    # the syllable count makes that possible.
    for occ in occurrences:
        tokens = occurrence_read_tokens(occ)
        if tokens is None:
            continue
        syls = [copy.copy(v) for k, v in tokens if k == "syl"]
        chars = list(range(occ["start"], occ["end"]))
        if len(syls) == len(chars):
            for pos, syl in zip(chars, syls):
                if (occ["proper"] and occ["word"] not in LANGUAGE_WORDS) or occ[
                    "word"
                ] in NATIONALITY_WORDS:
                    syl.cap = pos == chars[0]
                char_units[pos] = [syl]
        elif len(syls) == 1 and chars:
            syl = syls[0]
            if (occ["proper"] and occ["word"] not in LANGUAGE_WORDS) or occ[
                "word"
            ] in NATIONALITY_WORDS:
                syl.cap = True
            char_units[chars[0]] = [syl]
            for pos in chars[1:]:
                char_units[pos] = []
        elif len(chars) == 1:
            char_units[chars[0]] = syls

    tokens = fallback_subtokens(list(jieba.cut(hanzi)))
    parts: list[str] = []
    pos = 0
    for token in tokens:
        if not token:
            continue
        parts.append(render_token(token, pos, char_units))
        pos += len(token)
    text = smart_join(parts)
    return c.capitalize_sentence(text)


# ---------------------------------------------------------------------------
# Main line correction
# ---------------------------------------------------------------------------

def correct_line(
    note_id: int,
    line_index: int,
    hanzi: str,
    pinyin_original: str,
    pro: dict[int, c.Syllable],
    py: dict[int, c.Syllable],
    cons: dict[int, c.Syllable],
    base_flags: list[str],
    force_regenerate: bool = False,
) -> dict:
    line_flags = list(base_flags)
    items = c.parse_pinyin_line(pinyin_original, hanzi)
    items, align_ok = c.align_items_to_hanzi(hanzi, items)
    syl_items = [it for it in items if it.kind == "syl"]
    cjk_count = sum(1 for ch in hanzi if c.is_cjk(ch))
    orig_count = len(syl_items)

    occurrences = find_occurrences(hanzi)
    proper_spans: set[int] = set()
    for occ in occurrences:
        if occ["proper"]:
            proper_spans.update(range(occ["start"], occ["end"]))
    for m in SURNAME_RE.finditer(hanzi):
        proper_spans.update(range(m.start(1), m.end(1)))
    if re.search(r"[A-Za-z]", hanzi):
        line_flags.append("latin")

    if any(ch.isdigit() for ch in hanzi):
        # v1 preserves the inherited number reading and flags it for the
        # optional number-expansion pass; do not let G2P rewrite numerals.
        line_flags.append("number")
        line_flags.append("align-fail-preserved" if not align_ok else "number-preserved")
        text = c.insert_missing_apostrophes(pinyin_original, hanzi)
        corrections = []
        if text != pinyin_original:
            corrections.append(
                {
                    "kind": "line",
                    "char_index": None,
                    "char": "",
                    "word": "",
                    "original": pinyin_original,
                    "corrected": text,
                    "reason": "orthography-apostrophe",
                }
            )
        return {
            "index": line_index,
            "hanzi": hanzi,
            "pinyin_original": pinyin_original,
            "pinyin": text,
            "align_ok": align_ok,
            "generated": False,
            "flags": sorted(set(line_flags)),
            "corrections": corrections,
            "preserved_reason": "number",
        }

    if not align_ok:
        reason = "source-extra-syllable"
        if re.search(r"[A-Za-z]", hanzi):
            reason = "latin-source"
        elif orig_count <= cjk_count:
            reason = "align-fail"
        elif "èè" in pinyin_original:
            # Typo such as 一个赌徒 -> yī gèè; regenerate rather than keep the
            # duplicated syllable.
            reason = "align-fail"
        # Extra syllables usually mean the Hanzi line is missing a word.  Keep
        # the inherited reading, flag it, and let Phase 2 resolve the source.
        # A feedback-edited Hanzi line is an exception: the inherited pinyin
        # belongs to the old sentence, so regenerate it from the new text.
        if reason in {"latin-source", "source-extra-syllable"} and not force_regenerate:
            line_flags.append("align-fail-preserved")
            text = c.insert_missing_apostrophes(pinyin_original, hanzi)
            corrections = []
            if text != pinyin_original:
                corrections.append(
                    {
                        "kind": "line",
                        "char_index": None,
                        "char": "",
                        "word": "",
                        "original": pinyin_original,
                        "corrected": text,
                        "reason": "orthography-apostrophe",
                    }
                )
            return {
                "index": line_index,
                "hanzi": hanzi,
                "pinyin_original": pinyin_original,
                "pinyin": text,
                "align_ok": False,
                "generated": False,
                "flags": sorted(set(line_flags)),
                "corrections": corrections,
                "preserved_reason": reason,
            }
        text = fallback_line(hanzi, pro, py, cons, occurrences)
        line_flags.append("generated-fallback")
        return {
            "index": line_index,
            "hanzi": hanzi,
            "pinyin_original": pinyin_original,
            "pinyin": text,
            "align_ok": False,
            "generated": True,
            "flags": sorted(set(line_flags)),
            "corrections": [
                {
                    "kind": "line",
                    "char_index": None,
                    "char": "",
                    "original": pinyin_original,
                    "corrected": text,
                    "reason": "align-fail-regenerated",
                }
            ],
            "preserved_reason": None,
        }

    span_start = {}
    span_end = {}
    split_starts: set[int] = set()
    # Repair the common ``一个儿子`` case: the source writes ``gèr zǐ`` as if
    # 儿 were erhua on 个, while it is actually the first character of 儿子.
    # Split the erhua syllable and insert a placeholder for 儿 so the lexicon
    # reading can replace it.
    extra_items: list[c.Item] = []
    for it in items:
        if (
            it.kind == "syl"
            and it.syl is not None
            and it.syl.erhua
            and it.span is not None
            and it.span[1] - it.span[0] == 2
        ):
            a, b = it.span
            if any(occ["start"] == a + 1 for occ in occurrences):
                it.syl = replace(it.syl, erhua=False)
                it.span = (a, a + 1)
                placeholder = c.Item(
                    kind="syl",
                    syl=c.Syllable(base="er", tone=2),
                    span=(a + 1, a + 2),
                )
                extra_items.append(placeholder)
                split_starts.add(a + 1)
    if extra_items:
        place_by_start = {item.span[0]: item for item in extra_items}
        rebuilt: list[c.Item] = []
        for it in items:
            rebuilt.append(it)
            if it.kind == "syl" and it.span is not None:
                key = it.span[0] + 1
                if key in place_by_start and it.span[1] == key:
                    rebuilt.append(place_by_start.pop(key))
        rebuilt.extend(place_by_start.values())
        items = rebuilt
        syl_items = [it for it in items if it.kind == "syl"]

    for si, it in enumerate(syl_items):
        a, b = it.span  # type: ignore[misc]
        span_start[a] = si
        span_end[b] = si

    occ_by_start: dict[int, dict] = {}
    for occ in occurrences:
        start_ok = occ["start"] in span_start or occ["start"] in split_starts
        end_ok = occ["end"] in span_end
        if not end_ok and occ["end"] == len(hanzi) and syl_items:
            # Erhua suffix written without an ``r`` in the inherited pinyin:
            # the last syllable still ends at len(hanzi)-1.
            end_ok = syl_items[-1].span is not None and syl_items[-1].span[1] == occ["end"] - 1
        if not start_ok or not end_ok:
            line_flags.append("lexicon-unaligned")
            continue
        occ_by_start[occ["start"]] = occ

    out_items: list[c.Item] = []
    corrections: list[dict] = []
    i = 0
    while i < len(items):
        it = items[i]
        if it.kind == "syl":
            assert it.syl is not None and it.span is not None
            a, b = it.span
            occ = occ_by_start.get(a)
            if occ is not None:
                covered = [
                    j
                    for j in range(i, len(items))
                    if items[j].kind == "syl"
                    and items[j].span is not None
                    and items[j].span[0] >= a
                    and items[j].span[1] <= occ["end"]
                ]
                if not covered:
                    out_items.append(it)
                    i += 1
                    continue
                last = max(covered)
                tokens = occurrence_read_tokens(occ)
                if tokens is None:
                    out_items.append(it)
                    i += 1
                    continue
                orig_text = c.render_units(items[i : last + 1])
                capitalize = (
                    occ["proper"] and occ["word"] not in LANGUAGE_WORDS
                ) or occ["word"] in NATIONALITY_WORDS
                emit = render_reading_tokens(tokens, capitalize, it.syl)
                if a in split_starts:
                    emit = [c.Item(kind="sep", text=" ")] + emit
                new_text = c.render_units(emit)
                if orig_text != new_text:
                    corrections.append(
                        {
                            "kind": "word",
                            "char_index": a,
                            "char": hanzi[a],
                            "word": occ["word"],
                            "original": orig_text,
                            "corrected": new_text,
                            "reason": occ["reason"],
                        }
                    )
                out_items.extend(emit)
                i = last + 1
                continue

            next_syl = None
            for later in items[i + 1 :]:
                if later.kind == "syl":
                    next_syl = later.syl
                    break
            new_syl, rec = correct_syllable(
                it.syl, a, hanzi[a], pro, py, cons, next_syl,
                hanzi[a - 1] if a > 0 else "", proper_spans, line_flags
            )
            if rec:
                corrections.append(rec)
            out_items.append(
                c.Item(kind="syl", syl=new_syl, span=it.span, proper=a in proper_spans)
            )
        else:
            out_items.append(it)
        i += 1

    text = c.capitalize_sentence(c.render_units(out_items))
    return {
        "index": line_index,
        "hanzi": hanzi,
        "pinyin_original": pinyin_original,
        "pinyin": text,
        "align_ok": True,
        "generated": False,
        "flags": sorted(set(line_flags)),
        "corrections": corrections,
        "preserved_reason": None,
    }


def main() -> None:
    notes = json.loads((DATA / "normalized.json").read_text(encoding="utf-8"))

    batch_lines = []
    for note in notes:
        for line in note["lines"]:
            if line["hanzi"].strip():
                batch_lines.append(
                    {"id": f"{note['id']}:{line['index']}", "text": line["hanzi"]}
                )
    pro_tokens = run_pinyin_pro(batch_lines)

    out_notes = []
    all_corrections = []
    flag_counts = Counter()
    reason_counts = Counter()
    preserved_counts = Counter()
    changed_notes = 0
    generated_notes = 0

    for idx, note in enumerate(notes):
        out_lines = []
        note_flags: set[str] = set()
        note_corrections = 0
        for line in note["lines"]:
            lid = f"{note['id']}:{line['index']}"
            hz = line["hanzi"]
            p_orig = line["pinyin"]
            tokens = pro_tokens.get(lid, [])
            pro = pro_map(hz, tokens)
            py = pypinyin_map(hz)
            cons = consensus_map(pro, py)
            base_flags = []
            if line["label"]:
                base_flags.append("dialogue-label")
            if any(ch.isdigit() for ch in hz):
                base_flags.append("number")
            result = correct_line(
                note["id"],
                line["index"],
                hz,
                p_orig,
                pro,
                py,
                cons,
                base_flags,
                force_regenerate=bool(line.get("feedback_hanzi_changed")),
            )
            if line.get("feedback_hanzi_changed"):
                result["flags"] = sorted(
                    set(result["flags"]) | {"feedback-hanzi"}
                )
                result["feedback_hanzi_changed"] = True
            fixed_pinyin, latin_fixes = fix_latin_case(hz, result["pinyin"])
            if latin_fixes:
                result["pinyin"] = fixed_pinyin
                result["corrections"].extend(latin_fixes)
                result["flags"] = sorted(set(result["flags"]) | {"latin-case"})
            spaced_pinyin, spacing_fixes = split_particle_de(hz, result["pinyin"])
            if spacing_fixes:
                result["pinyin"] = spaced_pinyin
                result["corrections"].extend(spacing_fixes)
                result["flags"] = sorted(set(result["flags"]) | {"particle-spacing"})
            fixed_pinyin, line_fix = P2.apply_line_fix(
                note["id"], line["index"], result["pinyin"]
            )
            if line_fix:
                result["pinyin"] = fixed_pinyin
                result["corrections"].append(line_fix)
                result["flags"] = sorted(set(result["flags"]) | {"phase2-review"})
            cap_pinyin, cap_changed = P2.capitalize_name_readings(result["pinyin"])
            if cap_changed:
                result["corrections"].append(
                    {
                        "kind": "line",
                        "char_index": None,
                        "char": "",
                        "word": "",
                        "original": result["pinyin"],
                        "corrected": cap_pinyin,
                        "reason": "name-capitalization",
                    }
                )
                result["pinyin"] = cap_pinyin
            if any(ch.isdigit() for ch in hz):
                expanded, number_fixes = N.expand_numbers(hz, result["pinyin"])
                if number_fixes:
                    result["pinyin"] = expanded
                    result["corrections"].extend(number_fixes)
                    result["flags"] = sorted(
                        set(result["flags"]) | {"number-expanded"}
                    )
            feedback_pinyin, feedback_fixes = FB.apply_pinyin_overrides(
                note["id"], line["index"], result["pinyin"]
            )
            if feedback_fixes:
                result["pinyin"] = feedback_pinyin
                result["corrections"].extend(feedback_fixes)
                result["flags"] = sorted(
                    set(result["flags"]) | {"feedback-pinyin"}
                )
            # ``hanzi`` is the G2P text with any A/B dialogue label removed;
            # keep the display form (with the label) for the output fields.
            result["hanzi_display"] = line["hanzi_display"]
            result["pinyin_display"] = line["pinyin_display"]
            result["label"] = line["label"]
            out_lines.append(result)
            note_flags.update(result["flags"])
            note_corrections += len(result["corrections"])
            for rec in result["corrections"]:
                rec = {
                    "note_id": note["id"],
                    "line": line["index"],
                    "hanzi": hz,
                    **rec,
                }
                all_corrections.append(rec)
                reason_counts[rec["reason"]] += 1
            if result["preserved_reason"]:
                preserved_counts[result["preserved_reason"]] += 1
            for flag in result["flags"]:
                flag_counts[flag] += 1

        pinyin = "<br>".join(line["pinyin"] or "" for line in out_lines)
        original = "<br>".join(line["pinyin_display"] for line in note["lines"])
        if pinyin != original:
            changed_notes += 1
        if any(line["generated"] for line in out_lines):
            note_flags.add("generated")
            generated_notes += 1
        if note_corrections:
            note_flags.add("corrected")
        out_notes.append(
            {
                "id": note["id"],
                "guid": note["guid"],
                "mid": note["mid"],
                "tags": note["tags"],
                "source_sequence": note.get("source_sequence", idx + 1),
                "hanzi": note["hanzi"],
                "english": note["english"],
                "audio": note["audio"],
                "audio_refs": note["audio_refs"],
                "multiline": note["multiline"],
                "has_digits": note["has_digits"],
                "has_latin_hanzi": note["has_latin_hanzi"],
                "variant_changes": note["variant_changes"],
                "pinyin_original": original,
                "pinyin": pinyin,
                "flags": sorted(note_flags),
                "correction_count": note_corrections,
                "lines": out_lines,
            }
        )

    summary = {
        "note_count": len(out_notes),
        "line_count": sum(len(n["lines"]) for n in out_notes),
        "changed_notes": changed_notes,
        "generated_notes": generated_notes,
        "corrections": len(all_corrections),
        "corrections_by_reason": dict(reason_counts.most_common()),
        "line_flag_counts": dict(flag_counts.most_common()),
        "preserved_counts": dict(preserved_counts.most_common()),
        "flagged_notes": sum(1 for n in out_notes if "corrected" in n["flags"] or "generated" in n["flags"]),
    }
    (DATA / "pinyin.json").write_text(
        json.dumps(
            {"summary": summary, "corrections": all_corrections, "notes": out_notes},
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )

    csv_path = DATA / "pinyin_corrections.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "note_id",
                "line",
                "kind",
                "char",
                "word",
                "original",
                "corrected",
                "reason",
                "hanzi",
            ],
        )
        writer.writeheader()
        for rec in all_corrections:
            writer.writerow(
                {
                    "note_id": rec["note_id"],
                    "line": rec["line"],
                    "kind": rec["kind"],
                    "char": rec.get("char", ""),
                    "word": rec.get("word", ""),
                    "original": rec["original"],
                    "corrected": rec["corrected"],
                    "reason": rec["reason"],
                    "hanzi": rec["hanzi"],
                }
            )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

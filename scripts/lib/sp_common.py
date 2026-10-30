"""Shared helpers for the Forkfed Chinese modular-deck pipeline.

Covers text cleaning, pinyin syllable parsing/segmentation, alignment to Hanzi,
zhuyin conversion, and small rendering helpers.  No file I/O here.
"""

from __future__ import annotations

import html
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from pypinyin.contrib.tone_convert import to_normal, to_tone, to_tone3
from pypinyin.pinyin_dict import pinyin_dict

# ---------------------------------------------------------------------------
# Unicode helpers
# ---------------------------------------------------------------------------

CJK_RANGES = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
)

ZERO_WIDTH = "\u200b\u200c\u200d\ufeff"
HTML_ENTITY_RE = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]+);")
BR_RE = re.compile(r"<br\s*/?>", re.I)
TAG_RE = re.compile(r"<[^>]+>")
MULTISPACE_RE = re.compile(r"[ \t]+")
NEWLINE_RE = re.compile(r"\n{3,}")


def is_cjk(ch: str) -> bool:
    if not ch:
        return False
    o = ord(ch)
    return any(a <= o <= b for a, b in CJK_RANGES)


def is_digit(ch: str) -> bool:
    return ch.isdigit()


def is_latin(ch: str) -> bool:
    if not ch:
        return False
    return ch.isascii() and ch.isalpha()


def clean_field(raw: str) -> str:
    """Decode entities, normalise <br> to newlines, strip other tags."""
    text = raw or ""
    # A handful of source fields were escaped twice (``&amp;quot;``); decode
    # until stable so no literal entity survives in the output.
    for _ in range(3):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    text = text.replace("\xa0", " ")
    text = BR_RE.sub("\n", text)
    text = TAG_RE.sub("", text)
    text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    text = text.replace("\ufeff", "")
    text = text.replace("ɡ", "g")          # U+0261 LATIN SMALL LETTER SCRIPT G
    text = text.replace("ŏ", "ǒ")          # breve used as a third-tone typo
    text = text.replace("«", "《").replace("»", "》")
    text = unicodedata.normalize("NFC", text)
    # Tidy trailing spaces per line, preserve intentional internal spacing.
    lines = [MULTISPACE_RE.sub(" ", ln).strip() for ln in text.split("\n")]
    text = "\n".join(lines)
    text = NEWLINE_RE.sub("\n\n", text)
    return text.strip()


def clean_hanzi(raw: str) -> str:
    return clean_field(raw)


def clean_pinyin(raw: str) -> str:
    return clean_field(raw)


def split_lines(text: str) -> list[str]:
    return [ln for ln in text.split("\n")]


def drop_placeholder_lines(lines: Iterable[str]) -> list[str]:
    return [ln for ln in lines if ln.strip() not in {"", "-", "–", "—"}]


# ---------------------------------------------------------------------------
# Variant Hanzi normalisation (applied before G2P and traditional conversion)
# ---------------------------------------------------------------------------

VARIANT_HANZI = {
    "重覆": "重复",
    "部份": "部分",
    "佔": "占",
    "祇": "只",
    "裏": "里",
    "麼": "么",
    "甚麼": "什么",
    "週": "周",
    "儘": "尽",
    "唸": "念",
    "喫": "吃",
    "幷": "并",
    "竝": "并",
    "况": "况",
    "凉": "凉",
    "减": "减",
    "凑": "凑",
    "净": "净",
    "决": "决",
    "冲": "冲",
    "别": "别",
    "刮": "刮",
    "制": "制",
    "折": "折",
    "征": "征",
    "松": "松",
    "咸": "咸",
    "系": "系",
    "范": "范",
    "舍": "舍",
    "采": "采",
    "致": "致",
    "涂": "涂",
    "淀": "淀",
    "游": "游",
    "溪": "溪",
}


def normalize_variants(text: str) -> tuple[str, list[tuple[str, str]]]:
    changes: list[tuple[str, str]] = []
    out = text
    for old, new in VARIANT_HANZI.items():
        if old != new and old in out:
            changes.append((old, new))
            out = out.replace(old, new)
    return out, changes


# ---------------------------------------------------------------------------
# Pinyin syllable inventory and parser
# ---------------------------------------------------------------------------

def _build_inventory() -> tuple[dict[str, tuple[str, int]], Counter, str]:
    bases: Counter[str] = Counter()
    for readings in pinyin_dict.values():
        for reading in readings.split(","):
            base = to_normal(reading.strip())
            if re.fullmatch(r"[a-zü]+", base):
                bases[base] += 1
    for extra in ("lv", "nv", "lve", "nve"):
        bases[extra] += 1

    forms: dict[str, tuple[str, int]] = {}
    for base in bases:
        for tone in range(5):
            form = to_tone(f"{base}{tone}")
            if form:
                forms[form.lower()] = (base, tone)

    chars = set()
    for form in forms:
        chars.update(form)
    # Uppercase variants plus chars used inside runs.
    chars.update(c.upper() for c in list(chars))
    chars.update("umvUMV")
    char_class = "".join(sorted(re.escape(c) for c in chars))
    return forms, bases, f"[{char_class}]+"


TONED_FORMS, BASE_FREQ, RUN_CHARS = _build_inventory()
MAX_SYL_LEN = max(len(k) for k in TONED_FORMS)
RUN_RE = re.compile(RUN_CHARS)
LATIN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")


# Neutral syllables that normally occur as grammatical particles or common
# word-final neutral tones.  A neutral syllable outside this set is usually a
# bad split (e.g. ``yào`` -> ``yà`` + ``o``).
COMMON_NEUTRAL = {
    "a", "ba", "de", "ge", "guo", "hou", "huan", "kan", "le",
    "liang", "ma", "me", "men", "na", "ne", "sheng", "shi", "tou",
    "ya", "yi", "you", "zi", "zhe", "fu",
}


def _vowel_initial(ch: str) -> bool:
    base = unicodedata.normalize("NFD", ch)[0].lower()
    return base in {"a", "e", "i", "o", "u", "ü"}


def _tone_cost(base: str, tone: int, erhua: bool) -> float:
    freq = BASE_FREQ.get(base, 0)
    cost = -math.log(freq + 1.0)
    if erhua:
        cost += 0.5
    if tone == 0 and base not in COMMON_NEUTRAL:
        cost += 8.0
    # Prefer fewer syllables: bad splits often create an extra neutral syllable.
    cost += 10.0
    # Rare interjection bases are easy to mistake for a syllable tail.
    if base in {"ng", "n", "m", "hm", "hng", "yo", "lo"}:
        cost += 10.0
    return cost


def segment_run(run: str) -> list[dict] | None:
    """Segment a contiguous pinyin run into syllables.

    Uses a small frequency prior so strings such as ``bàngōngshì`` are parsed
    as ``bàn gōng shì`` rather than ``bàng ō ng``.  Erhua (``nǎr``) is handled as
    a single syllable with ``erhua=True``.
    """
    s = run.lower()
    n = len(s)
    if n == 0:
        return None
    inf = float("inf")
    best = [inf] * (n + 1)
    prev: list[tuple[int, dict] | None] = [None] * (n + 1)
    best[0] = 0.0
    for i in range(n):
        if best[i] == inf:
            continue
        for ln in range(1, min(MAX_SYL_LEN, n - i) + 1):
            part = s[i : i + ln]
            info = TONED_FORMS.get(part)
            if info is not None:
                base, tone = info
                cost = best[i] + _tone_cost(base, tone, False)
                # A vowel-initial syllable in the middle of a run normally
                # needs an apostrophe (Xi'an, nu'er).  Without one, the split
                # is far more likely to be a greedy mistake (dan+ao for da+nao,
                # feng+e for fen+ge).  Penalise it so consonant onsets win.
                if i > 0 and base and _vowel_initial(base[0]):
                    cost += 3.0
                if cost < best[i + ln]:
                    best[i + ln] = cost
                    prev[i + ln] = (
                        i,
                        {
                            "base": base,
                            "tone": tone,
                            "erhua": False,
                            "start": i,
                            "end": i + ln,
                        },
                    )
            # Erhua: final r attached to a normal syllable.  An ``r`` followed
            # by a vowel is an onset (dāng-rán), not an erhua coda (nǎr).
            if ln >= 2 and part.endswith("r") and not (
                i + ln < n and _vowel_initial(s[i + ln])
            ):
                prefix = part[:-1]
                info = TONED_FORMS.get(prefix)
                if info is not None:
                    base, tone = info
                    if base != "er":
                        cost = best[i] + _tone_cost(base, tone, True)
                        if base == "e":
                            cost += 10.0
                        if cost < best[i + ln]:
                            best[i + ln] = cost
                            prev[i + ln] = (
                                i,
                                {
                                    "base": base,
                                    "tone": tone,
                                    "erhua": True,
                                    "start": i,
                                    "end": i + ln,
                                },
                            )
    if best[n] == inf:
        return None
    out: list[dict] = []
    cur = n
    while cur > 0:
        p = prev[cur]
        if p is None:
            return None
        i, info = p
        item = dict(info)
        item["display"] = run[i:cur]
        out.append(item)
        cur = i
    out.reverse()
    return out


@dataclass
class Syllable:
    base: str
    tone: int
    erhua: bool = False
    display: str = ""
    cap: bool = False
    proper: bool = False
    source: str = ""

    @property
    def key(self) -> tuple[str, int, bool]:
        return (self.base, self.tone, self.erhua)

    def surface_text(self) -> str:
        base = self.base
        if self.erhua:
            assert not base.endswith("r")
            text = to_tone(f"{base}{self.tone}") + "r"
        else:
            text = to_tone(f"{base}{self.tone}")
        if self.cap and text:
            text = text[0].upper() + text[1:]
        return text

    def to_dict(self) -> dict:
        return {
            "base": self.base,
            "tone": self.tone,
            "erhua": self.erhua,
            "display": self.surface_text(),
            "cap": self.cap,
            "proper": self.proper,
            "source": self.source,
        }


def syllable_from_text(text: str) -> Syllable | None:
    text = text.strip()
    if not text:
        return None
    info = to_tone3(text.lower())
    m = re.fullmatch(r"([a-zü]+)([0-5])?", info)
    if not m:
        return None
    base, tone_s = m.group(1), m.group(2)
    tone = int(tone_s) if tone_s else 0
    erhua = False
    if base.endswith("r") and base != "er" and to_normal(base[:-1]) in BASE_FREQ:
        # erhua in a single supplied syllable
        base = base[:-1]
        erhua = True
    if base not in BASE_FREQ:
        return None
    cap = text[:1].isupper()
    return Syllable(base=base, tone=tone, erhua=erhua, display=text, cap=cap)


def parse_syllable_string(text: str) -> list[Syllable] | None:
    """Parse a whitespace-free pinyin string (e.g. from a lexicon)."""
    text = text.strip()
    if not text:
        return []
    # Normalise apostrophes to separators; keep them out of the runs.
    parts = re.split(r"['’]", text)
    out: list[Syllable] = []
    for part in parts:
        if not part:
            continue
        seg = segment_run(part)
        if seg is None:
            return None
        for item in seg:
            syl = Syllable(
                base=item["base"],
                tone=item["tone"],
                erhua=item["erhua"],
                display=item["display"],
            )
            out.append(syl)
    return out


@dataclass
class Item:
    kind: str  # syl | sep | lit
    text: str = ""
    syl: Syllable | None = None
    span: tuple[int, int] | None = None
    skip: bool = False
    lex: bool = False
    proper: bool = False
    changed: bool = False


def _literal_tokens(hanzi: str) -> set[str]:
    return {m.group(0).lower() for m in LATIN_TOKEN_RE.finditer(hanzi)}


def parse_pinyin_line(py: str, hanzi: str = "") -> list[Item]:
    """Parse a pinyin line into syllable/separator/literal items.

    Latin tokens that also occur in the Hanzi line (names such as ``Tom``) are
    kept as literals rather than being parsed as pinyin.
    """
    py = py.replace("’", "'")
    py = re.sub(r"['’]r\b", "r", py)
    literals = _literal_tokens(hanzi)
    items: list[Item] = []
    pos = 0
    for m in RUN_RE.finditer(py):
        if m.start() > pos:
            items.append(Item(kind="sep", text=py[pos : m.start()]))
        run = m.group()
        if run.lower() in literals:
            items.append(Item(kind="lit", text=run))
        else:
            seg = segment_run(run)
            if seg is None:
                items.append(Item(kind="lit", text=run))
            else:
                for info in seg:
                    syl = Syllable(
                        base=info["base"],
                        tone=info["tone"],
                        erhua=info["erhua"],
                        display=info["display"],
                        cap=info["display"][:1].isupper(),
                    )
                    items.append(Item(kind="syl", syl=syl))
        pos = m.end()
    if pos < len(py):
        items.append(Item(kind="sep", text=py[pos:]))
    return items


def align_items_to_hanzi(hanzi: str, items: list[Item]) -> tuple[list[Item], bool]:
    """Attach a (start, end) Hanzi char span to every syllable item.

    Returns the items and whether alignment succeeded.  Erhua syllables may
    consume a following 儿 character.
    """
    syllables = [it for it in items if it.kind == "syl"]
    chars = [(i, c) for i, c in enumerate(hanzi) if is_cjk(c)]
    for it in syllables:
        it.span = None
    if not syllables:
        return items, len(chars) == 0

    si = 0
    ci = 0
    while ci < len(chars):
        if si >= len(syllables):
            return items, False
        idx, ch = chars[ci]
        syl = syllables[si].syl
        assert syl is not None
        if syl.erhua and ci + 1 < len(chars) and chars[ci + 1][1] == "儿":
            syllables[si].span = (idx, chars[ci + 1][0] + 1)
            ci += 2
        else:
            syllables[si].span = (idx, idx + 1)
            ci += 1
        si += 1
    if si != len(syllables):
        return items, False
    covered: list[int] = []
    for it in syllables:
        a, b = it.span  # type: ignore[misc]
        covered.extend(range(a, b))
    if covered != [idx for idx, _ in chars]:
        return items, False
    return items, True


# ---------------------------------------------------------------------------
# Zhuyin
# ---------------------------------------------------------------------------

INITIALS = [
    ("zh", "ㄓ"),
    ("ch", "ㄔ"),
    ("sh", "ㄕ"),
    ("b", "ㄅ"),
    ("p", "ㄆ"),
    ("m", "ㄇ"),
    ("f", "ㄈ"),
    ("d", "ㄉ"),
    ("t", "ㄊ"),
    ("n", "ㄋ"),
    ("l", "ㄌ"),
    ("g", "ㄍ"),
    ("k", "ㄎ"),
    ("h", "ㄏ"),
    ("j", "ㄐ"),
    ("q", "ㄑ"),
    ("x", "ㄒ"),
    ("r", "ㄖ"),
    ("z", "ㄗ"),
    ("c", "ㄘ"),
    ("s", "ㄙ"),
]

FINALS = {
    "a": "ㄚ",
    "o": "ㄛ",
    "e": "ㄜ",
    "ê": "ㄝ",
    "ai": "ㄞ",
    "ei": "ㄟ",
    "ao": "ㄠ",
    "ou": "ㄡ",
    "an": "ㄢ",
    "en": "ㄣ",
    "ang": "ㄤ",
    "eng": "ㄥ",
    "er": "ㄦ",
    "i": "ㄧ",
    "ia": "ㄧㄚ",
    "ie": "ㄧㄝ",
    "iao": "ㄧㄠ",
    "iu": "ㄧㄡ",
    "iou": "ㄧㄡ",
    "ian": "ㄧㄢ",
    "in": "ㄧㄣ",
    "iang": "ㄧㄤ",
    "ing": "ㄧㄥ",
    "iong": "ㄩㄥ",
    "u": "ㄨ",
    "ua": "ㄨㄚ",
    "uo": "ㄨㄛ",
    "uai": "ㄨㄞ",
    "ui": "ㄨㄟ",
    "uei": "ㄨㄟ",
    "uan": "ㄨㄢ",
    "un": "ㄨㄣ",
    "uen": "ㄨㄣ",
    "uang": "ㄨㄤ",
    "ueng": "ㄨㄥ",
    "ong": "ㄨㄥ",
    "ü": "ㄩ",
    "v": "ㄩ",
    "üe": "ㄩㄝ",
    "ve": "ㄩㄝ",
    "üan": "ㄩㄢ",
    "van": "ㄩㄢ",
    "ün": "ㄩㄣ",
    "vn": "ㄩㄣ",
}

ZERO_INITIAL = {
    "a": "ㄚ", "o": "ㄛ", "e": "ㄜ", "ê": "ㄝ", "ai": "ㄞ", "ei": "ㄟ",
    "ao": "ㄠ", "ou": "ㄡ", "an": "ㄢ", "en": "ㄣ", "ang": "ㄤ", "eng": "ㄥ",
    "er": "ㄦ", "yo": "ㄧㄛ", "n": "ㄣ", "ng": "ㄥ", "m": "ㄇ", "hm": "ㄏㄇ",
    "hng": "ㄏㄥ",
    "yi": "ㄧ", "ya": "ㄧㄚ", "ye": "ㄧㄝ", "yao": "ㄧㄠ", "you": "ㄧㄡ",
    "yan": "ㄧㄢ", "yin": "ㄧㄣ", "yang": "ㄧㄤ", "ying": "ㄧㄥ", "yong": "ㄩㄥ",
    "wu": "ㄨ", "wa": "ㄨㄚ", "wo": "ㄨㄛ", "wai": "ㄨㄞ", "wei": "ㄨㄟ",
    "wan": "ㄨㄢ", "wen": "ㄨㄣ", "wang": "ㄨㄤ", "weng": "ㄨㄥ",
    "yu": "ㄩ", "yue": "ㄩㄝ", "yuan": "ㄩㄢ", "yun": "ㄩㄣ",
}

SPECIAL_FINALS = {
    "zhi": "ㄓ", "chi": "ㄔ", "shi": "ㄕ", "ri": "ㄖ",
    "zi": "ㄗ", "ci": "ㄘ", "si": "ㄙ",
}

TONE_MARKS = {1: "", 2: "ˊ", 3: "ˇ", 4: "ˋ", 0: ""}


def pinyin_to_zhuyin(base: str, tone: int, erhua: bool = False) -> str | None:
    b = base.replace("ü", "v")
    b = b.replace("lü", "lv").replace("nü", "nv")
    if b in SPECIAL_FINALS:
        core = SPECIAL_FINALS[b]
    elif b in ZERO_INITIAL:
        core = ZERO_INITIAL[b]
    else:
        initial = ""
        final = b
        for ini, zy in INITIALS:
            if b.startswith(ini):
                initial = zy
                final = b[len(ini) :]
                break
        if initial in {"ㄐ", "ㄑ", "ㄒ"} and final.startswith("u"):
            final = "v" + final[1:]
        if final in FINALS:
            core = initial + FINALS[final]
        elif final == "i" and initial in {"ㄓ", "ㄔ", "ㄕ", "ㄖ", "ㄗ", "ㄘ", "ㄙ"}:
            core = initial
        else:
            return None
    if tone == 0:
        out = "˙" + core
    else:
        out = core + TONE_MARKS[tone]
    if erhua:
        out += "ㄦ"
    return out


def zhuyin_from_syllable(syl: Syllable) -> str | None:
    return pinyin_to_zhuyin(syl.base, syl.tone, syl.erhua)


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

PUNCT_MAP = {
    ",": "，",
    ".": "。",
    "!": "！",
    "?": "？",
    ":": "：",
    ";": "；",
    "(": "（",
    ")": "）",
}


def escape_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def needs_apostrophe(prev: Syllable | None, current: Syllable) -> bool:
    """True when two adjacent syllables need an orthographic apostrophe."""
    if prev is None:
        return False
    return current.base[:1] in {"a", "o", "e"}


def insert_missing_apostrophes(text: str, hanzi: str = "") -> str:
    """Insert required apostrophes without otherwise rewriting ``text``.

    Used for preserved lines where a full re-render would also change
    capitalisation (for example after a leading Arabic numeral).
    """
    items = parse_pinyin_line(text, hanzi)
    positions: list[tuple[int, Item]] = []
    pos = 0
    for it in items:
        if it.kind != "syl" or it.syl is None:
            continue
        display = it.syl.display or it.syl.surface_text()
        found = text.find(display, pos)
        if found < 0:
            return text
        positions.append((found, it))
        pos = found + len(display)
    if not positions:
        return text

    out: list[str] = []
    cursor = 0
    prev_syl: Syllable | None = None
    prev_end = 0
    for start, it in positions:
        out.append(text[cursor:start])
        if (
            prev_syl is not None
            and start == prev_end
            and needs_apostrophe(prev_syl, it.syl)
        ):
            out.append("'")
        out.append(text[start : start + len(it.syl.display or it.syl.surface_text())])
        prev_syl = it.syl
        prev_end = start + len(it.syl.display or it.syl.surface_text())
        cursor = prev_end
    out.append(text[cursor:])
    return "".join(out)


def render_units(items: Iterable[Item], *, surface: bool = False, bold_class: str = "tone-change") -> str:
    out: list[str] = []
    prev_syl: Syllable | None = None
    separated = True
    for it in items:
        if it.kind == "syl":
            if it.skip:
                continue
            assert it.syl is not None
            text = it.syl.surface_text()
            if not separated and needs_apostrophe(prev_syl, it.syl):
                out.append("'")
            if surface and it.changed:
                text = f'<b class="{bold_class}">{text}</b>'
            out.append(text)
            prev_syl = it.syl
            separated = False
        elif it.kind == "sep":
            out.append(escape_text(it.text))
            prev_syl = None
            separated = True
        else:
            out.append(escape_text(it.text))
            prev_syl = None
            separated = True
    return "".join(out)


def render_zhuyin(items: Iterable[Item], *, surface: bool = False, bold_class: str = "tone-change") -> str:
    pieces: list[str] = []
    for it in items:
        if it.kind == "syl":
            if it.skip:
                continue
            assert it.syl is not None
            zy = zhuyin_from_syllable(it.syl)
            if zy is None:
                zy = escape_text(it.syl.surface_text())
            if surface and getattr(it, "changed", False):
                zy = f'<b class="{bold_class}">{zy}</b>'
            if pieces and not pieces[-1].endswith((" ", "\n")):
                pieces.append(" ")
            pieces.append(zy)
        elif it.kind == "lit":
            if pieces and not pieces[-1].endswith((" ", "\n")):
                pieces.append(" ")
            pieces.append(escape_text(it.text))
        else:
            txt = it.text
            if txt.strip() == "":
                if pieces and not pieces[-1].endswith(" "):
                    pieces.append(" ")
                continue
            mapped = "".join(PUNCT_MAP.get(ch, ch) for ch in txt)
            mapped = mapped.replace("'", "").replace("’", "")
            pieces.append(mapped)
    out = "".join(pieces)
    out = re.sub(r" +", " ", out)
    out = re.sub(r" ([，。！？：；）])", r"\1", out)
    out = re.sub(r"([（]) ", r"\1", out)
    return out.strip()


def capitalize_sentence(text: str) -> str:
    """Capitalise the first letter of a line and after . ! ?

    HTML tags are copied verbatim so the ``b`` in ``<b class=...>`` is not
    mistaken for the first letter of the line.
    """
    chars = list(text)
    start = True
    in_tag = False
    for i, ch in enumerate(chars):
        if ch == "<":
            in_tag = True
            continue
        if ch == ">":
            in_tag = False
            continue
        if in_tag:
            continue
        if ch in ".!?。！？":
            start = True
            continue
        if start and ch.isalpha() and not is_cjk(ch):
            chars[i] = ch.upper()
            start = False
        elif start and ch not in " \t'\"“”‘’《》（）()":
            # A digit or Hanzi does not break sentence-start capitalisation; the
            # next pinyin letter should still be capitalised.
            if ch.isalpha() and not is_cjk(ch):
                start = False
    return "".join(chars)


def strip_bold(text: str) -> str:
    return re.sub(r"</?b[^>]*>", "", text)


def count_changes(lexical: str, surface: str) -> int:
    return len(re.findall(r'<b class="tone-change">', surface))

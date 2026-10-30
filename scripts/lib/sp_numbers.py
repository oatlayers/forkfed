"""Read numbers for the dual numeral + reading display.

The deck keeps Arabic numerals in ``Hanzi``.  For readability, a numeral that
still appears literally in ``Pinyin`` is rewritten as ``100 (yībǎi)``; the
reading is also what ``Zhuyin`` converts.  Numbers that were already spelled
out in the source pinyin are left alone.

Readings are lexical (no tone sandhi); ``PinyinSandhi`` keeps number lines
verbatim because they are alignment exceptions by policy.
"""

from __future__ import annotations

import re

DIGITS = {
    0: "líng",
    1: "yī",
    2: "èr",
    3: "sān",
    4: "sì",
    5: "wǔ",
    6: "liù",
    7: "qī",
    8: "bā",
    9: "jiǔ",
}

# Two is liǎng before a measure word, but èr in dates, ordinals, and arithmetic.
LIANG_FOLLOWERS = (
    "点", "个", "天", "年", "岁", "小时", "公里", "米", "公斤", "美元",
    "万", "名", "位", "本", "张", "杯", "份", "间", "辆", "只", "条",
)
ER_FOLLOWERS = ("月", "号", "日", "乘", "加", "减", "除", "等")

NUM_RE = re.compile(r"\d+(?:\.\d+)?%?")


def _apostrophe(text: str) -> str:
    return re.sub(r"(?<=[A-Za-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ])(?=è)", "'", text)


def int_to_pinyin(value: int) -> str:
    """Lexical reading for 0..9999 (quantities, not years)."""
    if value < 0:
        raise ValueError(value)
    if value == 0:
        return "líng"
    if value < 10:
        return DIGITS[value]
    if value < 20:
        if value == 10:
            return "shí"
        return _apostrophe("shí" + DIGITS[value % 10])
    if value < 100:
        tens, ones = divmod(value, 10)
        text = DIGITS[tens] + "shí"
        if ones:
            text += DIGITS[ones]
        return _apostrophe(text)
    if value < 1000:
        hundreds, rest = divmod(value, 100)
        text = DIGITS[hundreds] + "bǎi"
        if rest:
            if rest < 10:
                text += " líng " + DIGITS[rest]
            else:
                text += " " + int_to_pinyin(rest)
        return text
    thousands, rest = divmod(value, 1000)
    text = DIGITS[thousands] + "qiān"
    if rest:
        if rest < 100:
            text += " líng " + int_to_pinyin(rest)
        else:
            text += " " + int_to_pinyin(rest)
    return text


def digit_by_digit(token: str) -> str:
    return " ".join(DIGITS[int(ch)] for ch in token)


def number_reading(token: str, after: str) -> str:
    """Reading for one numeric token, using the following Hanzi as context."""
    if token.endswith("%"):
        return "bǎifēnzhī " + int_to_pinyin(int(token[:-1]))
    if len(token) == 4 and after.startswith("年"):
        return digit_by_digit(token)
    if token == "911" and after.startswith("事件"):
        return "jiǔ yāo yāo"
    value = int(token)
    if token == "2":
        if after.startswith(ER_FOLLOWERS):
            return "èr"
        if after.startswith(LIANG_FOLLOWERS):
            return "liǎng"
        return "èr"
    return int_to_pinyin(value)


def expand_numbers(hanzi: str, pinyin_text: str) -> tuple[str, list[dict]]:
    """Add ``numeral (reading)`` where the pinyin still contains the numeral."""
    out = pinyin_text
    cursor = 0
    corrections: list[dict] = []
    for match in NUM_RE.finditer(hanzi):
        token = match.group(0)
        pattern = re.compile(r"(?<!\d)" + re.escape(token) + r"(?!\d)")
        hit = pattern.search(out, cursor)
        if hit is None:
            continue
        after = hanzi[match.end() : match.end() + 2]
        reading = number_reading(token, after)
        replacement = f"{token} ({reading})"
        original = out[hit.start() : hit.end()]
        out = out[: hit.start()] + replacement + out[hit.end() :]
        cursor = hit.start() + len(replacement)
        corrections.append(
            {
                "kind": "number",
                "char_index": match.start(),
                "char": hanzi[match.start()],
                "word": token,
                "original": original,
                "corrected": replacement,
                "reason": "number-expanded",
            }
        )
    return out, corrections

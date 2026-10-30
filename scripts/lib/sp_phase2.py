"""Phase 2 review fixes.

Every entry here was found by reviewing the Phase 1 review queue against
dictionary readings and the Hanzi/English context.  Word fixes are merged at
the highest lexicon priority; line fixes are exact, audited replacements for
cases where a word-level rule would be unsafe.

Adding an entry is a review decision: see ``data/review_decisions.csv`` for the
queue rows these fixes close.
"""

from __future__ import annotations

import sp_lexicon as L

# Word -> controlled reading.  Keys use the exact Hanzi substring that appears
# in the deck.  Readings use the same convention as ``sp_lexicon``: syllables
# separated by spaces, ``ü`` written with an umlaut, neutral tone bare.
WORD_FIXES: dict[str, str] = {    # --- readings that the Phase 1 ensemble missed ---------------------
    "幢": "zhuàng",
    "没必要": "méi bìyào",
    "喉咙很干": "hóulóng hěn gān",
    "麻将": "májiāng",
    "在校": "zàixiào",
    "曝光": "bàoguāng",
    "克林顿": "Kèlíndùn",
    "小时候": "xiǎoshíhou",
    "露西": "Lùxī",
    "炸死": "zhàsǐ",
    "过河拆桥": "guò hé chāi qiáo",
    "弹钢琴": "tán gāngqín",
    "弹吉他": "tán jítā",
    "弹奏": "tánzòu",
    "读经济": "dú jīngjì",
    "狼吞虎咽地": "lángtūnhǔyàn de",
    "嘴裂开": "zuǐ lièkāi",
    "绰号": "chuòhào",
    "尽情": "jìnqíng",
    "遛一圈": "liù yī quān",
    "栅栏": "zhàlan",
    "木栅栏": "mù zhàlan",
    "围了起来": "wéi le qǐlái",
    "同归于尽": "tóng guī yú jìn",
    "鸟儿": "niǎor",
    "华佗": "Huà Tuó",
    "醋溜": "cùliū",
    "穷困潦倒": "qióngkùn liáodǎo",
    "吹嘘": "chuīxū",
    "健将": "jiànjiàng",
    "之谜": "zhī mí",
    "布什": "Bùshí",
    "里根": "Lǐgēn",
    "曝露": "pùlù",
    # --- high-frequency polyphones corrected after context review -------
    "尽快": "jǐnkuài",
    "宁可": "nìngkě",
    "占有": "zhànyǒu",
    "切水果": "qiē shuǐguǒ",
    "散了步": "sàn le bù",
    "着火": "zháohuǒ",
    "闭着眼": "bìzhe yǎn",
    "嗅觉": "xiùjué",
    "长得": "zhǎng de",
    "更不要说": "gèng bùyào shuō",
    "更不幸": "gèng bùxìng",
    "看不到": "kàn bù dào",
    "为表演者": "wèi biǎoyǎnzhě",
    "为她的诗人": "wèi tā de shīrén",
    "为美国承受": "wèi Měiguó chéngshòu",
    "为我腾出": "wèi wǒ téngchū",
    "为我准备": "wèi wǒ zhǔnbèi",
    "为一本书": "wèi yī běn shū",
    "为她的家人": "wèi tā de jiārén",
    "为你着想": "wèi nǐ zhuóxiǎng",
    "为风险投资": "wèi fēngxiǎntóuzī",
    "为学生提供": "wèi xuésheng tígōng",
    "为更年轻的人": "wèi gèng niánqīng de rén",
    "为的是": "wèi de shì",
    # --- second word-check pass (pypinyin phrase dictionary) -------------
    "意识": "yìshí",
    "迹象": "jìxiàng",
    "几乎": "jīhū",
    "癌症": "áizhèng",
    "时分": "shífēn",
    "最差": "zuì chà",
    "露面": "lòumiàn",
    "一应俱全": "yīyīng jùquán",
    "无济于事": "wú jì yú shì",
    "字体": "zìtǐ",
    "太薄": "tài báo",
    "空闲": "kòngxián",
    "糊掉": "húdiào",
    "一只": "yī zhī",
    "长篇大论": "chángpiāndàlùn",
    "指派": "zhǐpài",
    "模棱两可": "mó léng liǎng kě",
    "建筑师": "jiànzhùshī",
    "相互": "xiānghù",
    "经验教训": "jīngyàn jiàoxùn",
    "还清": "huánqīng",
    "互相": "hùxiāng",
    "参与": "cānyù",
    "应急": "yìngjí",
    "无论": "wúlùn",
    "教过": "jiàoguò",
    "理发店": "lǐfàdiàn",
    "颇": "pǒ",
    "母亲": "mǔqīn",
    "想要点": "xiǎng yào diǎn",
    "对外语": "duì wàiyǔ",
    "变差": "biàn chà",
    "很差": "hěn chà",
    "重得多": "zhòng de duō",
    "得过重病": "déguò zhòngbìng",
    "种瓜得瓜": "zhòng guā dé guā",
    "种豆得豆": "zhòng dòu dé dòu",
    "得了第一名": "dé le dìyī míng",
    "得了癌症": "dé le áizhèng",
    "得了肺癌": "dé le fèi'ái",
    "得了皮肤癌": "dé le pífū'ái",
    # --- structural 得 / 地 particles misread as full tones -------------
    "变得": "biàn de",
    "弄得": "nòng de",
    "做得": "zuò de",
    "说得": "shuō de",
    "笑得": "xiào de",
    "困得": "kùn de",
    "刮得": "guā de",
    "冷得": "lěng de",
    "活得": "huó de",
    "知道得": "zhīdào de",
    "惊得": "jīng de",
    "搞得": "gǎo de",
    "学习得": "xuéxí de",
    "写得": "xiě de",
    "晓得": "xiǎode",
    "毫不犹豫地": "háobù yóuyù de",
    "毫无问题地": "háowú wèntí de",
    "安全地": "ānquán de",
    "通宵达旦地": "tōngxiāo dá dàn de",
    "一点一点地": "yīdiǎn yīdiǎn de",
    "好心地": "hǎoxīn de",
    "更好地": "gèng hǎo de",
    "慢慢地": "mànmàn de",
    "迅速地": "xùnsù de",
    "安详地": "ānxiáng de",
    "耐心地": "nàixīn de",
}

# Names that must keep proper-noun capitalization.
PROPER_WORDS = {"露西", "克林顿", "华佗", "布什", "里根"}

# Name readings that should be capitalized wherever they occur.  Language
# names are excluded because the deck writes them lowercase mid-sentence.
_NAME_CAP_EXCLUDE = {
    "zhōngwén", "hànyǔ", "yīngwén", "yīngyǔ", "fǎyǔ", "déyǔ", "rìyǔ",
    "xībānyáyǔ", "pǔtōnghuà",
}
NAME_CAP_READINGS: tuple[str, ...] = tuple(
    sorted(
        {
            value
            for value in L.NAME_PLACE_LEXICON.values()
            if " " not in value and value not in _NAME_CAP_EXCLUDE
        },
        key=len,
        reverse=True,
    )
)


def capitalize_name_readings(pinyin_text: str) -> tuple[str, bool]:
    """Capitalize known name readings that survived a preserved-number line."""
    changed = False
    for reading in NAME_CAP_READINGS:
        capitalized = reading[0].upper() + reading[1:]
        if reading in pinyin_text:
            pinyin_text = pinyin_text.replace(reading, capitalized)
            changed = True
    return pinyin_text, changed


# (note_id, line_index) -> (old substring, replacement, reason).  Substring
# replacements are precise and survive earlier word-level fixes on the same
# line.  A missing ``old`` raises, so a stale fix cannot pass silently.
LINE_FIXES: dict[tuple[int, int], tuple[str, str, str]] = {
    (1419644216323, 0): (
        "Wǒmen liǎ shì",
        "Wǒmen shì",
        "source-extra-syllable",
    ),
    (1419644218375, 0): (
        "Xìshàng",
        "Jì shàng",
        "polyphone-jì",
    ),
    (1419644216657, 0): (
        "ná zháo",
        "názhe",
        "polyphone-zhe",
    ),
    (1419644214865, 0): (
        "Děi le!",
        "Dé le!",
        "polyphone-dé",
    ),
    (1419644218360, 0): (
        "Lùxīhé",
        "Lùxī hé",
        "name-spacing",
    ),
    (1419644220690, 0): (
        "Huà tuó",
        "Huà Tuó",
        "name-capitalization",
    ),
    (1419644216599, 0): (
        "xiào děi",
        "xiào de",
        "polyphone-de-number-line",
    ),
    (1419644217720, 0): (
        "zhānyǒulǜ",
        "zhànyǒulǜ",
        "polyphone-zhàn-number-line",
    ),
    (1419644217650, 0): (
        "jīn'nián",
        "jīnnián",
        "apostrophe-number-line",
    ),
    (1419644219948, 0): (
        "Tāde",
        "Tā de",
        "particle-spacing-number-line",
    ),
}


def apply_line_fix(
    note_id: int, line_index: int, pinyin_text: str
) -> tuple[str, dict | None]:
    """Apply an exact substring replacement and return an audit record."""
    entry = LINE_FIXES.get((note_id, line_index))
    if entry is None:
        return pinyin_text, None
    old, new, reason = entry
    if old not in pinyin_text:
        raise ValueError(
            f"phase2 line fix {note_id}:{line_index} missing {old!r} in "
            f"{pinyin_text!r}"
        )
    return pinyin_text.replace(old, new, 1), {
        "kind": "line",
        "char_index": None,
        "char": "",
        "word": "",
        "original": old,
        "corrected": new,
        "reason": reason,
    }

"""Curated community-feedback and duplicate policy for the 3.0 release.

Every row in ``FEEDBACK_ROWS`` is the machine-readable triage record for one
block of ``data/feedback_source.txt``.  Only rows with ``status == "applied"``
change note data.  The other statuses are deliberate decisions:

* ``already-correct`` - the current deck already has the requested form;
* ``audio-only``      - the source audio is wrong but the text is kept;
* ``duplicate``       - a reported duplicate that is not paired in this fork;
* ``not-in-fork``     - the sentence does not exist in this fork;
* ``review``          - subjective, incomplete, or contradicted by the data.

``DUPLICATE_GROUPS`` is the independent audit result: eight exact
Hanzi+pinyin+English groups plus the tagged 欢迎光临 pair.  One copy of each is
removed, keeping the first occurrence in the original sequence.  The other 24
``duplicate``-tagged notes are unique sentences and stay in the deck.
"""

from __future__ import annotations

import re
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"

STATUSES = {
    "applied",
    "already-correct",
    "audio-only",
    "duplicate",
    "not-in-fork",
    "review",
}

# ---------------------------------------------------------------------------
# Duplicate audit
# ---------------------------------------------------------------------------

DUPLICATE_GROUPS = [
    {
        "group": 1,
        "kept": 1419644217514,
        "deleted": 1419644217516,
        "hanzi": "欢迎光临",
        "basis": "tagged duplicate pair; only the final punctuation differs",
    },
    {
        "group": 2,
        "kept": 1419644212763,
        "deleted": 1419644212768,
        "hanzi": "我是老师。",
        "basis": "exact Hanzi + normalized pinyin + English",
    },
    {
        "group": 3,
        "kept": 1419644212772,
        "deleted": 1419644212774,
        "hanzi": "他是美国人。",
        "basis": "exact Hanzi + normalized pinyin + English",
    },
    {
        "group": 4,
        "kept": 1419644213300,
        "deleted": 1419644213304,
        "hanzi": "我去过北京。",
        "basis": "exact Hanzi + normalized pinyin + English",
    },
    {
        "group": 5,
        "kept": 1419644213932,
        "deleted": 1419644213933,
        "hanzi": "我很快乐。",
        "basis": "exact Hanzi + normalized pinyin + English",
    },
    {
        "group": 6,
        "kept": 1419644215606,
        "deleted": 1419644215607,
        "hanzi": "他出席了会议。",
        "basis": "exact Hanzi + normalized pinyin + English",
    },
    {
        "group": 7,
        "kept": 1419644216249,
        "deleted": 1419644216369,
        "hanzi": "我头痛。",
        "basis": "exact Hanzi + normalized pinyin + English",
    },
    {
        "group": 8,
        "kept": 1419644217116,
        "deleted": 1419644217119,
        "hanzi": "物价上涨了。",
        "basis": "exact Hanzi + normalized pinyin + English",
    },
    {
        "group": 9,
        "kept": 1419644218644,
        "deleted": 1419644218645,
        "hanzi": "截至目前为止，还没有什么消息。",
        "basis": "exact Hanzi + normalized pinyin + English",
    },
]

DELETED_NOTE_IDS = {row["deleted"] for row in DUPLICATE_GROUPS}
KEPT_NOTE_IDS = {row["kept"] for row in DUPLICATE_GROUPS}

# ---------------------------------------------------------------------------
# Audio defects.  These are recorded, never edited: the source audio is not
# part of this repository.  ``disposition`` explains what the release does.
# ---------------------------------------------------------------------------

AUDIO_ISSUES = [
    (1419644213558, "Audio", "ending cut off", "recorded; audio not edited"),
    (1419644216513, "Audio", "ending cut off", "recorded; audio not edited"),
    (1419644218575, "Audio", "beginning slightly cut off", "recorded; audio not edited"),
    (1419644216929, "Audio", "beginning and ending cut off", "recorded; audio not edited"),
    (1419644216769, "Audio", "two sentences spoken in one file", "recorded; audio not edited"),
    (1419644217768, "Audio", "spoken 打 is dá; text/pinyin use dǎ", "recorded; text kept"),
    (1419644219145, "Audio", "spoken syllable sounds like 'kan' instead of tán", "recorded; text kept"),
    (1419644219886, "Audio", "spoken word sounds like 'shuye' instead of shùlín", "recorded; text kept"),
    (1419644214132, "Audio", "spoken subject is 他/她; written subject is 你", "recorded; text kept"),
    (1419644217589, "Audio", "spoken sentence differs substantially from written text", "recorded; text kept"),
    (1419644213125, "Audio", "extra audio after the sentence", "recorded; audio not edited"),
    (1419644217655, "Audio", "spoken 妒嫉; written 嫉妒", "recorded; text kept"),
    (1419644216371, "Audio", "audio does not fully match the written sentence", "recorded; audio not edited"),
    (1419644217228, "Audio", "slight beginning cut-off", "recorded; audio not edited"),
    (1419644217703, "Audio", "spoken zhuā; written/pinyin zhuō", "recorded; text kept"),
    (1419644220731, "Audio", "spoken 三十一日; text changed to match", "text aligned to audio"),
    (1419644213399, "Audio", "spoken 会; text changed to match", "text aligned to audio"),
    (1419644214388, "Audio", "spoken 我 at the start; text changed to match", "text aligned to audio"),
    (1419644216334, "Audio", "spoken 他; text changed to match", "text aligned to audio"),
    (1419644219319, "Audio", "spoken 我; text changed to match", "text aligned to audio"),
    (1419644217590, "Audio", "spoken 我; text changed to match", "text aligned to audio"),
    (1419644212879, "Audio", "spoken 我; text changed to match", "text aligned to audio"),
    (1419644219038, "Audio", "spoken 里; text changed to match", "text aligned to audio"),
    (1419644218807, "Audio", "spoken 节; text changed to match", "text aligned to audio"),
    (1419644218635, "Audio", "spoken wording adopted in the text", "text aligned to audio"),
]

# ---------------------------------------------------------------------------
# Feedback ledger
# ---------------------------------------------------------------------------

FEEDBACK_ROWS = [
    # 1: document header
    {
        "source_line": "1",
        "note_id": None,
        "field": "meta",
        "before": "",
        "after": "",
        "status": "review",
        "reason": "Document header; no deck change.",
    },
    # 3-4
    {
        "source_line": "3-4",
        "note_id": 1419644216250,
        "field": "Hanzi",
        "before": "这张票3天内有效。",
        "after": "这张票3天内有效。",
        "status": "already-correct",
        "reason": "The fork already uses 天, not 月.",
    },
    # 6-7
    {
        "source_line": "6-7",
        "note_id": 1419644214012,
        "field": "English",
        "before": "Two times two is four.",
        "after": "Two doubled is four.",
        "status": "applied",
        "reason": "The suggested literal wording is clearer for 二的两倍.",
    },
    # 9-10
    {
        "source_line": "9-10",
        "note_id": None,
        "field": "English",
        "before": "I'm about to send e-mails to my friends.",
        "after": "",
        "status": "not-in-fork",
        "reason": "This sentence is not present in this fork.",
    },
    # 12-13
    {
        "source_line": "12-13",
        "note_id": 1419644212879,
        "field": "Hanzi",
        "before": "我们看见孩子上了车。",
        "after": "我看见孩子上了车。",
        "status": "applied",
        "reason": "The audio clearly says 我, not 我们.",
    },
    {
        "source_line": "12-13",
        "note_id": 1419644212879,
        "field": "English",
        "before": "We saw the child get on the bus.",
        "after": "I saw the child get on the bus.",
        "status": "applied",
        "reason": "Align the translation with the spoken subject.",
    },
    # 15-16
    {
        "source_line": "15-16",
        "note_id": None,
        "field": "Hanzi",
        "before": "我在公园遇到了Ken.",
        "after": "",
        "status": "not-in-fork",
        "reason": "This sentence is not present in this fork.",
    },
    # 18-19
    {
        "source_line": "18-19",
        "note_id": 1419644214805,
        "field": "English",
        "before": "Do you believe in God?",
        "after": "",
        "status": "duplicate",
        "reason": "The exact duplicate does not exist in this fork; only one card remains.",
    },
    # 21
    {
        "source_line": "21",
        "note_id": 1419644214388,
        "field": "Hanzi",
        "before": "问问他会不会说日语。",
        "after": "我问他会不会说日语。",
        "status": "applied",
        "reason": "The audio says 我 at the start.",
    },
    {
        "source_line": "21",
        "note_id": 1419644214388,
        "field": "English",
        "before": "Ask him if he can speak Japanese.",
        "after": "I asked him if he can speak Japanese.",
        "status": "applied",
        "reason": "Align the translation with the spoken subject.",
    },
    {
        "source_line": "21",
        "note_id": 1419644214388,
        "field": "Pinyin",
        "before": "tā, huìbùhuì",
        "after": "tā huìbùhuì",
        "status": "applied",
        "reason": "Remove the inherited comma; the corrected Hanzi has no comma.",
    },
    # 23
    {
        "source_line": "23",
        "note_id": 1419644213399,
        "field": "Hanzi",
        "before": "明天下午之前我将把它完成。",
        "after": "明天下午之前我会把它完成。",
        "status": "applied",
        "reason": "The audio says 会, not 将.",
    },
    {
        "source_line": "23",
        "note_id": 1419644213399,
        "field": "English",
        "before": "I will finish it by tomorrow afternoon.",
        "after": "I will finish it by tomorrow afternoon.",
        "status": "already-correct",
        "reason": "The English already matches the spoken meaning.",
    },
    # 25
    {
        "source_line": "25",
        "note_id": 1419644215642,
        "field": "English",
        "before": "That couple lives a happy/blessed life.",
        "after": "That married couple lives a happy life.",
        "status": "applied",
        "reason": "夫妻 means a married couple, not a dating couple.",
    },
    # 27
    {
        "source_line": "27",
        "note_id": 1419644214643,
        "field": "English",
        "before": "When work is letting out, there are super many people in the subway.",
        "after": "When work is letting out, there are super many people in the subway.",
        "status": "already-correct",
        "reason": "The release already uses the requested informal wording.",
    },
    # 29-30
    {
        "source_line": "29-30",
        "note_id": 1419644216090,
        "field": "English",
        "before": "He's appreciating the work.",
        "after": "He's appreciating this work of art.",
        "status": "applied",
        "reason": "Make clear that 作品 is a work of art.",
    },
    # 32-33
    {
        "source_line": "32-33",
        "note_id": None,
        "field": "English",
        "before": "起床的时间到了",
        "after": "",
        "status": "not-in-fork",
        "reason": "This sentence is not present in this fork.",
    },
    # 35-36
    {
        "source_line": "35-36",
        "note_id": 1419644215634,
        "field": "English",
        "before": "He did it at the expense of his health.",
        "after": "He completed the job at the expense of his health.",
        "status": "applied",
        "reason": "The suggested wording is more explicit and accurate.",
    },
    # 38-39
    {
        "source_line": "38-39",
        "note_id": 1419644213558,
        "field": "Audio",
        "before": "我和她外出了几个月",
        "after": "",
        "status": "audio-only",
        "reason": "Audio is cut off; text is correct and audio is not edited.",
    },
    # 41-42
    {
        "source_line": "41-42",
        "note_id": None,
        "field": "Audio",
        "before": "我今天有空",
        "after": "",
        "status": "not-in-fork",
        "reason": "This sentence is not present in this fork.",
    },
    # 44-46
    {
        "source_line": "44-46",
        "note_id": 1419644216402,
        "field": "English",
        "before": "They began a discussion to exchange each other's views.",
        "after": "",
        "status": "review",
        "reason": "The pasted pinyin belongs to a different sentence; the current translation is correct.",
    },
    # 48-49
    {
        "source_line": "48-49",
        "note_id": 1419644216334,
        "field": "Hanzi",
        "before": "我很喜欢吃蛋糕。",
        "after": "他很喜欢吃蛋糕。",
        "status": "applied",
        "reason": "The audio says 他, not 我.",
    },
    {
        "source_line": "48-49",
        "note_id": 1419644216334,
        "field": "English",
        "before": "I love cake.",
        "after": "He loves cake.",
        "status": "applied",
        "reason": "Align the translation with the spoken subject.",
    },
    # 51-52
    {
        "source_line": "51-52",
        "note_id": 1419644216371,
        "field": "Audio",
        "before": "唯一比无论什么资源都珍贵的是土地",
        "after": "",
        "status": "audio-only",
        "reason": "Audio does not fully match the text; text is correct and audio is not edited.",
    },
    # 54-55
    {
        "source_line": "54-55",
        "note_id": 1419644216513,
        "field": "Audio",
        "before": "你其实没必要带伞",
        "after": "",
        "status": "audio-only",
        "reason": "Audio is cut off; text is correct and audio is not edited.",
    },
    # 57-58
    {
        "source_line": "57-58",
        "note_id": 1419644216769,
        "field": "Audio",
        "before": "我妹妹嫁给了一个医生。",
        "after": "",
        "status": "audio-only",
        "reason": "Two sentences are spoken in one file; text is correct.",
    },
    # 60-61
    {
        "source_line": "60-61",
        "note_id": 1419644216866,
        "field": "English",
        "before": "He came over, carrying a tray of beer.",
        "after": "He came over carrying beer.",
        "status": "applied",
        "reason": "Nothing in the Chinese implies a tray.",
    },
    # 63-64
    {
        "source_line": "63-64",
        "note_id": 1419644216807,
        "field": "English",
        "before": "Dangerous driving should be punished.",
        "after": "Dangerous behavior should be punished.",
        "status": "applied",
        "reason": "行为 means behavior; driving is not mentioned.",
    },
    # 66-67
    {
        "source_line": "66-67",
        "note_id": 1419644217703,
        "field": "Pinyin",
        "before": "zhuō",
        "after": "zhuō",
        "status": "already-correct",
        "reason": "The written and pinyin forms are correct; only the audio says zhuā.",
    },
    # 69-70
    {
        "source_line": "69-70",
        "note_id": 1419644216931,
        "field": "Pinyin",
        "before": "hūlüè",
        "after": "hūlüè",
        "status": "already-correct",
        "reason": "The current release already reads hūlüè.",
    },
    # 72-73
    {
        "source_line": "72-73",
        "note_id": 1419644215247,
        "field": "English",
        "before": "Most Chinese love to eat baozi.",
        "after": "Most Chinese love to eat steamed buns.",
        "status": "applied",
        "reason": "Use the English food name instead of the transliteration.",
    },
    # 75-76
    {
        "source_line": "75-76",
        "note_id": 1419644215488,
        "field": "English",
        "before": "Don't be worried. These things take time.",
        "after": "Stay patient. These things take time.",
        "status": "applied",
        "reason": "The Chinese asks for patience, not an absence of worry.",
    },
    # 78-79
    {
        "source_line": "78-79",
        "note_id": 1419644217292,
        "field": "English",
        "before": "Be it ever so humble, there's no place like home.",
        "after": "A golden nest or a silver nest is no match for one's own dog's nest (there's no place like home).",
        "status": "applied",
        "reason": "Give the literal image before the idiomatic meaning.",
    },
    # 81-85
    {
        "source_line": "81-85",
        "note_id": 1419644215714,
        "field": "Hanzi",
        "before": "A他的发音怎么样?\nB好。他在英国学习过,所以他有英国口音。",
        "after": "",
        "status": "review",
        "reason": "Changing 好 to 很好 would contradict the audio; adding 优雅 is a curriculum suggestion.",
    },
    # 87-88
    {
        "source_line": "87-88",
        "note_id": 1419644219355,
        "field": "English",
        "before": "Sow melon and you get melon, sow beans and you get beans (idiom)\n(you reap what you sow)",
        "after": "",
        "status": "already-correct",
        "reason": "The release already gives both the literal meaning and the idiom.",
    },
    # 90-91
    {
        "source_line": "90-91",
        "note_id": 1419644218776,
        "field": "Pinyin",
        "before": "tán jítā",
        "after": "tán jítā",
        "status": "already-correct",
        "reason": "The current release already reads tán jítā.",
    },
    # 93-94
    {
        "source_line": "93-94",
        "note_id": 1419644217250,
        "field": "English",
        "before": "I didn't call on him because I had a cold.",
        "after": "I didn't visit him because I had a cold.",
        "status": "applied",
        "reason": "visit is the ordinary translation of 拜访.",
    },
    # 96-98
    {
        "source_line": "96-98",
        "note_id": 1419644217655,
        "field": "Audio",
        "before": "他们嫉妒我们的成功。",
        "after": "",
        "status": "audio-only",
        "reason": "The audio says 妒嫉; the written 嫉妒 is correct and is kept.",
    },
    # 100-101
    {
        "source_line": "100-101",
        "note_id": 1419644213125,
        "field": "Audio",
        "before": "你认识这位老师吗？",
        "after": "",
        "status": "audio-only",
        "reason": "The audio contains an extra sentence; text is correct.",
    },
    # 103-105
    {
        "source_line": "103-105",
        "note_id": 1419644215984,
        "field": "English",
        "before": "There's too much dust on the ground.",
        "after": "There's a lot of dirt on the ground.",
        "status": "applied",
        "reason": "土 is dirt/soil; 灰尘 is dust.",
    },
    # 107-108
    {
        "source_line": "107-108",
        "note_id": 1419644215986,
        "field": "English",
        "before": "According to the lowest reckoning(estimate), it will cost thirty thousand yen.",
        "after": "According to the lowest estimate, it will cost three thousand yen.",
        "status": "applied",
        "reason": "The Chinese says 3000, not 30,000.",
    },
    # 111-112
    {
        "source_line": "111-112",
        "note_id": 1419644216737,
        "field": "Hanzi",
        "before": "总统获得国会充份的支持。",
        "after": "总统获得国会充分的支持。",
        "status": "applied",
        "reason": "充分 is the standard simplified form.",
    },
    {
        "source_line": "111-112",
        "note_id": 1419644216737,
        "field": "English",
        "before": "The President received full support from Congress.",
        "after": "",
        "status": "duplicate",
        "reason": "The reported duplicate is not paired in this fork; only one copy exists.",
    },
    # 114-116
    {
        "source_line": "114-116",
        "note_id": 1419644215500,
        "field": "English",
        "before": "No wonder she didn't show up to see him off. They broke up.",
        "after": "No wonder she said she didn't want to see him again. They broke up.",
        "status": "applied",
        "reason": "表示 means she expressed something, not that she failed to appear.",
    },
    # 118-119
    {
        "source_line": "118-119",
        "note_id": 1419644217140,
        "field": "English",
        "before": "The government is carrying out the reforms step by step.",
        "after": "The government followed steps to carry out reform.",
        "status": "applied",
        "reason": "按照步骤 does not imply the idiom step by step.",
    },
    # 121-122
    {
        "source_line": "121-122",
        "note_id": 1419644218590,
        "field": "English",
        "before": "He confirmed that something was wrong with his car.",
        "after": "He firmly believes that something is wrong with his car.",
        "status": "applied",
        "reason": "坚信 means firmly believes, not confirmed.",
    },
    # 124-125
    {
        "source_line": "124-125",
        "note_id": 1419644216750,
        "field": "English",
        "before": "It is expensive running this car.",
        "after": "It is expensive to maintain this car.",
        "status": "applied",
        "reason": "保养 means maintain, not run.",
    },
    # 127-129
    {
        "source_line": "127-129",
        "note_id": 1419644215294,
        "field": "English",
        "before": "He took a vacation.",
        "after": "He asked for leave.",
        "status": "applied",
        "reason": "请假 means asked for leave.",
    },
    # 131-132
    {
        "source_line": "131-132",
        "note_id": 1419644218575,
        "field": "Audio",
        "before": "董事长召开了董事会。",
        "after": "",
        "status": "audio-only",
        "reason": "The beginning is cut off; text is correct.",
    },
    # 134-135
    {
        "source_line": "134-135",
        "note_id": 1419644218810,
        "field": "English",
        "before": "The meat has been stewed till it's very soft.",
        "after": "The meat has been stewed until it's mushy.",
        "status": "applied",
        "reason": "烂 here means overcooked/mushy, not pleasantly soft.",
    },
    # 137-138
    {
        "source_line": "137-138",
        "note_id": 1419644215801,
        "field": "English",
        "before": "He told his father of his remorse for his mistakes.",
        "after": "He reflected on his mistakes to his father.",
        "status": "applied",
        "reason": "反省 does not necessarily imply remorse.",
    },
    # 140-141
    {
        "source_line": "140-141",
        "note_id": 1419644218120,
        "field": "English",
        "before": "It gets very humid here in the summer. In the winter, on the other hand, it gets very dry.",
        "after": "It gets very hot here in the summer. In the winter, on the other hand, it gets very dry.",
        "status": "applied",
        "reason": "The Chinese says 热 (hot), not humid.",
    },
    # 143-144
    {
        "source_line": "143-144",
        "note_id": 1419644216178,
        "field": "English",
        "before": "There is no denying that she is very very efficient.",
        "after": "There is no denying that she is very capable.",
        "status": "applied",
        "reason": "有能力 means capable, not efficient.",
    },
    # 146-148
    {
        "source_line": "146-148",
        "note_id": 1419644216092,
        "field": "Hanzi",
        "before": "他更改了他的计画表。",
        "after": "他更改了他的计划表。",
        "status": "applied",
        "reason": "计划 is the standard simplified form.",
    },
    # 150-151
    {
        "source_line": "150-151",
        "note_id": 1419644218223,
        "field": "English",
        "before": "The government should deal with the problem of corruption.",
        "after": "",
        "status": "review",
        "reason": "The suggested 'improve the problem of corruption' is not idiomatic English.",
    },
    # 153-156
    {
        "source_line": "153-156",
        "note_id": 1419644215366,
        "field": "English",
        "before": "Don't expect others to think for you!",
        "after": "Don't expect others to think of you!",
        "status": "applied",
        "reason": "着想 means be considerate of, not make decisions for.",
    },
    # 158-159
    {
        "source_line": "158-159",
        "note_id": None,
        "field": "English",
        "before": "我的学生们英语发音不好。",
        "after": "",
        "status": "not-in-fork",
        "reason": "The exact sentence is not present; the equivalent 刘先生 note already says English pronunciation.",
    },
    # 161-163
    {
        "source_line": "161-163",
        "note_id": 1419644218733,
        "field": "English",
        "before": "Getting him to dance is very difficult.",
        "after": "Wouldn't it be difficult getting him to dance?",
        "status": "applied",
        "reason": "岂不是 makes the sentence rhetorical.",
    },
    # 165-167
    {
        "source_line": "165-167",
        "note_id": 1419644218635,
        "field": "Hanzi",
        "before": "自行车从右侧超过汽车是不合法的。",
        "after": "自行车在汽车的右侧行驶是不合法的。",
        "status": "applied",
        "reason": "Use the wording spoken in the audio.",
    },
    {
        "source_line": "165-167",
        "note_id": 1419644218635,
        "field": "English",
        "before": "It is illegal for bicycles to pass on the right of cars.",
        "after": "It is illegal for bicycles to drive on the right side of cars.",
        "status": "applied",
        "reason": "Align the translation with the revised Hanzi.",
    },
    # 169-170
    {
        "source_line": "169-170",
        "note_id": 1419644219056,
        "field": "Hanzi",
        "before": "在有些国家乌鸦是不详的象征。",
        "after": "在有些国家乌鸦是不祥的象征。",
        "status": "applied",
        "reason": "不祥 is the correct word for ominous.",
    },
    {
        "source_line": "169-170",
        "note_id": 1419644219056,
        "field": "English",
        "before": "Crows are an ominous symbol in some countries.",
        "after": "",
        "status": "review",
        "reason": "不祥 means ominous, not 'symbol of the unknown'; the current English is correct.",
    },
    # 172-173
    {
        "source_line": "172-173",
        "note_id": 1419644218299,
        "field": "English",
        "before": "The pears in the market are very fresh.",
        "after": "The peaches in the market are very fresh.",
        "status": "applied",
        "reason": "桃子 means peaches, not pears.",
    },
    # 175-176
    {
        "source_line": "175-176",
        "note_id": 1419644217201,
        "field": "English",
        "before": "Yesterday, the Ministry of Education announced the scope of the exam.",
        "after": "Yesterday, the Ministry of Education planned the scope of the exam.",
        "status": "applied",
        "reason": "规划 means planned, not announced.",
    },
    # 178-179
    {
        "source_line": "178-179",
        "note_id": 1419644217425,
        "field": "English",
        "before": "They looked relieved only when it was in motion.",
        "after": "When it worked, they seemed relieved.",
        "status": "applied",
        "reason": "Make explicit that 运转 refers to a machine working.",
    },
    # 181-182
    {
        "source_line": "181-182",
        "note_id": 1419644218329,
        "field": "English",
        "before": "He couldn't stand her way of doing things and he scolded her.",
        "after": "",
        "status": "already-correct",
        "reason": "The current translation already expresses the suggested meaning.",
    },
    # 184-185
    {
        "source_line": "184-185",
        "note_id": 1419644217635,
        "field": "English",
        "before": "The employees want a pay raise.",
        "after": "The employees want to fight for a pay raise.",
        "status": "applied",
        "reason": "争取 means fight/strive for, not simply want.",
    },
    # 187-188
    {
        "source_line": "187-188",
        "note_id": 1419644220030,
        "field": "English",
        "before": "Being disabled definitely doesn't have to be a tale of misfortune.",
        "after": "Being disabled doesn't have to be a misfortune.",
        "status": "applied",
        "reason": "Remove the awkward literal phrasing while keeping the meaning.",
    },
    # 190-191
    {
        "source_line": "190-191",
        "note_id": 1419644218299,
        "field": "English",
        "before": "The pears in the market are very fresh.",
        "after": "",
        "status": "duplicate",
        "reason": "Repeated feedback item; the correction is recorded at lines 172-173.",
    },
    # 193-194
    {
        "source_line": "193-194",
        "note_id": 1419644217324,
        "field": "English",
        "before": "They appointed to go climbing on Sunday.",
        "after": "They agreed to go hiking on Sunday.",
        "status": "applied",
        "reason": "登山 here means hiking, not rock climbing.",
    },
    # 196-197
    {
        "source_line": "196-197",
        "note_id": 1419644217896,
        "field": "English",
        "before": "We will never countenance terrorism.",
        "after": "We never stand for terrorism.",
        "status": "applied",
        "reason": "Use the suggested plain-English idiom.",
    },
    # 199-200
    {
        "source_line": "199-200",
        "note_id": 1419644219145,
        "field": "Audio",
        "before": "皮筋具有弹性。",
        "after": "",
        "status": "audio-only",
        "reason": "The spoken syllable does not match tán; text is correct.",
    },
    # 202-203
    {
        "source_line": "202-203",
        "note_id": 1419644217228,
        "field": "Audio",
        "before": "你觉得她最想要什么纪念品",
        "after": "",
        "status": "audio-only",
        "reason": "Slight beginning cut-off; text is correct.",
    },
    # 205-207
    {
        "source_line": "205-207",
        "note_id": 1419644216220,
        "field": "English",
        "before": "I'll give you a temporary treatment.",
        "after": "I'll help you deal with emergencies.",
        "status": "applied",
        "reason": "应急处理 means emergency handling, not a temporary treatment.",
    },
    # 209-210
    {
        "source_line": "209-210",
        "note_id": 1419644219107,
        "field": "English",
        "before": "This red hat corresponds well to her dress.",
        "after": "",
        "status": "review",
        "reason": "裙子 can be skirt or dress; the current rendering is defensible.",
    },
    # 212-213
    {
        "source_line": "212-213",
        "note_id": 1419644219260,
        "field": "English",
        "before": "I accidently injured my lower back.",
        "after": "I accidentally sprained my lower back.",
        "status": "applied",
        "reason": "闪了腰 means sprained the lower back.",
    },
    # 215-216
    {
        "source_line": "215-216",
        "note_id": 1419644216957,
        "field": "English",
        "before": "Li Ming passed his exam to become a Ph.D.",
        "after": "Li Ming passed his exam to become a medical doctor.",
        "status": "applied",
        "reason": "医学博士 is a medical doctor, not a generic Ph.D.",
    },
    # 218-219
    {
        "source_line": "218-219",
        "note_id": 1419644219514,
        "field": "English",
        "before": "The farm has a lot of cows.",
        "after": "The pasture has a lot of cows.",
        "status": "applied",
        "reason": "牧场 is a pasture or ranch.",
    },
    # 221-222
    {
        "source_line": "221-222",
        "note_id": 1419644214722,
        "field": "English",
        "before": "My father is always cool.",
        "after": "My father is always calm.",
        "status": "applied",
        "reason": "冷静 means calm, not the slang sense of cool.",
    },
    # 224-225
    {
        "source_line": "224-225",
        "note_id": 1419644219095,
        "field": "English",
        "before": "They are Protestants.",
        "after": "They are Christians.",
        "status": "applied",
        "reason": "基督教 is Christianity, not specifically Protestantism.",
    },
    # 227-228
    {
        "source_line": "227-228",
        "note_id": 1419644217502,
        "field": "English",
        "before": "My father is getting better by degrees.",
        "after": "My father is getting better gradually.",
        "status": "applied",
        "reason": "The suggested wording is clearer.",
    },
    # 230-231
    {
        "source_line": "230-231",
        "note_id": 1419644216517,
        "field": "English",
        "before": "Thousands of people are disappointed with this ad",
        "after": "",
        "status": "already-correct",
        "reason": "The release already says disappointed, not deceived.",
    },
    # 233-234
    {
        "source_line": "233-234",
        "note_id": 1419644218449,
        "field": "English",
        "before": "The police are patrolling the neighborhood.",
        "after": "The police are patrolling nearby.",
        "status": "applied",
        "reason": "附近 means nearby, not a whole neighborhood.",
    },
    # 236-237
    {
        "source_line": "236-237",
        "note_id": 1419644216133,
        "field": "English",
        "before": "The construction workers are building a road.",
        "after": "The construction workers are repairing a road.",
        "status": "applied",
        "reason": "修路 means repair/build a road; the suggested repair is accurate here.",
    },
    # 239-240
    {
        "source_line": "239-240",
        "note_id": 1419644217476,
        "field": "English",
        "before": "I should stop procrastinating.",
        "after": "I should do things decisively.",
        "status": "applied",
        "reason": "果断 means decisive, not stop procrastinating.",
    },
    # 242-244
    {
        "source_line": "242-244",
        "note_id": 1419644219766,
        "field": "Pinyin",
        "before": "chuòhào",
        "after": "chuòhào",
        "status": "already-correct",
        "reason": "The current release already reads chuòhào.",
    },
    # 246-248
    {
        "source_line": "246-248",
        "note_id": 1419644218811,
        "field": "English",
        "before": "He knocked his opponents out of the race.",
        "after": "He eliminated the other opponents.",
        "status": "applied",
        "reason": "There is no race in the Chinese; 淘汰 means eliminate.",
    },
    # 250-251
    {
        "source_line": "250-251",
        "note_id": 1419644219319,
        "field": "Hanzi",
        "before": "他觉得电视节目的内容太庸俗。",
        "after": "我觉得电视节目的内容太庸俗。",
        "status": "applied",
        "reason": "The audio says 我, not 他.",
    },
    {
        "source_line": "250-251",
        "note_id": 1419644219319,
        "field": "English",
        "before": "He thinks the TV program is too vulgar.",
        "after": "I think the TV program is too vulgar.",
        "status": "applied",
        "reason": "Align the translation with the spoken subject.",
    },
    # 253-254
    {
        "source_line": "253-254",
        "note_id": 1419644218008,
        "field": "English",
        "before": "He worked at the cost of his own time.",
        "after": "He doesn't hesitate to use his personal time to work.",
        "status": "applied",
        "reason": "The suggested wording is closer to 不惜.",
    },
    # 256-257
    {
        "source_line": "256-257",
        "note_id": 1419644219401,
        "field": "English",
        "before": "She is crouching in the grass.",
        "after": "She is lying on her stomach in the grass.",
        "status": "applied",
        "reason": "趴 means lying on one's stomach, not crouching.",
    },
    # 259-260
    {
        "source_line": "259-260",
        "note_id": 1419644219471,
        "field": "English",
        "before": "I applied on the internet for a new account.",
        "after": "",
        "status": "review",
        "reason": "The Chinese does not specify a bank account; the generic account is correct.",
    },
    # 262-263
    {
        "source_line": "262-263",
        "note_id": 1419644217293,
        "field": "English",
        "before": "For the time being, my sister is an assistant in a supermarket.",
        "after": "For the time being, my sister is a cashier in a supermarket.",
        "status": "applied",
        "reason": "收银员 is a cashier, not a general assistant.",
    },
    # 265
    {
        "source_line": "265",
        "note_id": 1419644214292,
        "field": "English",
        "before": "Behind his way of doing things, was another purpose.",
        "after": "",
        "status": "review",
        "reason": "No specific correction was supplied.",
    },
    # 267-268
    {
        "source_line": "267-268",
        "note_id": 1419644217562,
        "field": "English",
        "before": "The US President deals with national affairs in the White House.",
        "after": "The US President works in the White House.",
        "status": "applied",
        "reason": "办公 means works in an office.",
    },
    # 270-271
    {
        "source_line": "270-271",
        "note_id": 1419644217892,
        "field": "English",
        "before": "He is equal to the job.",
        "after": "He is qualified for the job.",
        "status": "applied",
        "reason": "胜任 means qualified for.",
    },
    # 273-274
    {
        "source_line": "273-274",
        "note_id": 1419644220029,
        "field": "Pinyin",
        "before": "mù zhàlan",
        "after": "mù zhàlan",
        "status": "already-correct",
        "reason": "The current release already reads mù zhàlan.",
    },
    # 276-277
    {
        "source_line": "276-277",
        "note_id": 1419644220003,
        "field": "English",
        "before": "He joined in the fundraising.",
        "after": "He is collecting donations.",
        "status": "applied",
        "reason": "募捐 means collecting donations, not fundraising as an activity.",
    },
    # 279-281
    {
        "source_line": "279-281",
        "note_id": 1419644218561,
        "field": "English",
        "before": "Danger past, God forgotten.",
        "after": "Cross the river, then tear down the bridge (forget one's benefactor once their help is no longer needed).",
        "status": "applied",
        "reason": "Give the literal image and then explain the idiom.",
    },
    {
        "source_line": "279-281",
        "note_id": 1419644218561,
        "field": "Pinyin",
        "before": "chāi qiáo",
        "after": "chāi qiáo",
        "status": "already-correct",
        "reason": "The current release already reads chāi qiáo.",
    },
    # 283-284
    {
        "source_line": "283-284",
        "note_id": 1419644218710,
        "field": "English",
        "before": "There's no water in the bottle.",
        "after": "There's no water in the kettle.",
        "status": "applied",
        "reason": "水壶 is a kettle or pitcher, not a bottle.",
    },
    # 286-287
    {
        "source_line": "286-287",
        "note_id": 1419644218679,
        "field": "English",
        "before": "She's sealing the paper box.",
        "after": "She's sealing the cardboard box.",
        "status": "applied",
        "reason": "纸箱 is a cardboard box.",
    },
    # 289-290
    {
        "source_line": "289-290",
        "note_id": 1419644219660,
        "field": "English",
        "before": "It lives in a burrow.",
        "after": "It lives in a cave.",
        "status": "applied",
        "reason": "洞穴 is a cave, not a burrow.",
    },
    # 292-294
    {
        "source_line": "292-294",
        "note_id": 1419644219654,
        "field": "English",
        "before": "The laborers are instigating a strike.",
        "after": "The laborers are planning to strike.",
        "status": "applied",
        "reason": "酝酿 means brewing/planning, not instigating.",
    },
    # 296-297
    {
        "source_line": "296-297",
        "note_id": 1419644218686,
        "field": "English",
        "before": "There's a cabinet in the living-room.",
        "after": "There's a cabinet in the bedroom.",
        "status": "applied",
        "reason": "卧室 is a bedroom, not a living room.",
    },
    # 299-300
    {
        "source_line": "299-300",
        "note_id": 1419644217768,
        "field": "Audio",
        "before": "我的爱好是打羽毛球。",
        "after": "",
        "status": "audio-only",
        "reason": "The audio says dá; the written/pinyin dǎ is correct.",
    },
    # 302-303
    {
        "source_line": "302-303",
        "note_id": 1419644216070,
        "field": "English",
        "before": "He turned to the next page.",
        "after": "",
        "status": "review",
        "reason": "The comment says only that the source is redundant; no replacement was proposed.",
    },
    # 305-306
    {
        "source_line": "305-306",
        "note_id": 1419644219598,
        "field": "Pinyin",
        "before": "tánzòu",
        "after": "tánzòu",
        "status": "already-correct",
        "reason": "The current release already reads tánzòu.",
    },
    # 308-309
    {
        "source_line": "308-309",
        "note_id": 1419644218851,
        "field": "Pinyin",
        "before": "huánqīng",
        "after": "huánqīng",
        "status": "already-correct",
        "reason": "The current release already reads huánqīng.",
    },
    # 311-312
    {
        "source_line": "311-312",
        "note_id": 1419644219886,
        "field": "Audio",
        "before": "这片树林很茂密。",
        "after": "",
        "status": "audio-only",
        "reason": "The audio says something like shuye; the written/pinyin shùlín is correct.",
    },
    # 314-315
    {
        "source_line": "314-315",
        "note_id": 1419644218851,
        "field": "Pinyin",
        "before": "huánqīng",
        "after": "",
        "status": "duplicate",
        "reason": "Repeated pinyin feedback; already recorded at lines 308-309.",
    },
    # 317-318
    {
        "source_line": "317-318",
        "note_id": 1419644218025,
        "field": "English",
        "before": "This is really a miracle.",
        "after": "This is really a spectacular sight.",
        "status": "applied",
        "reason": "奇观 is a spectacle, not a miracle.",
    },
    # 320-321
    {
        "source_line": "320-321",
        "note_id": 1419644218745,
        "field": "English",
        "before": "She'll never give up smoking.",
        "after": "She may be unable to quit smoking.",
        "status": "applied",
        "reason": "未必 means may not, not never.",
    },
    # 323-324
    {
        "source_line": "323-324",
        "note_id": 1419644219405,
        "field": "English",
        "before": "He went sketching in the suburbs.",
        "after": "",
        "status": "review",
        "reason": "写生 is sketching from life, not still life; the suggested rewrite is inaccurate.",
    },
    # 326-327
    {
        "source_line": "326-327",
        "note_id": 1419644217388,
        "field": "English",
        "before": "This store is having a sale on its clothes.",
        "after": "This shopping mall is having a sale on clothes.",
        "status": "applied",
        "reason": "商场 is a mall or shopping centre, not a small store.",
    },
    # 329-330
    {
        "source_line": "329-330",
        "note_id": 1419644219038,
        "field": "Hanzi",
        "before": "他正坐在会议室。",
        "after": "他正坐在会议室里。",
        "status": "applied",
        "reason": "The audio contains 里.",
    },
    {
        "source_line": "329-330",
        "note_id": 1419644219038,
        "field": "English",
        "before": "He's sitting in the waiting room.",
        "after": "He's sitting in the meeting room.",
        "status": "applied",
        "reason": "会议室 is a meeting room, not a waiting room.",
    },
    # 332-334
    {
        "source_line": "332-334",
        "note_id": 1419644218635,
        "field": "Pinyin",
        "before": "Zìxíngchē cóng yòu cè chāoguò qìchē shì bùhéfǎ de.",
        "after": "Zìxíngchē zài qìchē de yòu cè xíngshǐ shì bùhéfǎ de.",
        "status": "already-correct",
        "reason": "Regenerated from the corrected Hanzi recorded at lines 165-167.",
    },
    # 336-337
    {
        "source_line": "336-337",
        "note_id": 1419644217321,
        "field": "Pinyin",
        "before": "jiējiǎo",
        "after": "jiējiǎo",
        "status": "already-correct",
        "reason": "The current release already reads jiējiǎo.",
    },
    # 339-340
    {
        "source_line": "339-340",
        "note_id": 1419644217951,
        "field": "English",
        "before": "She's washing the clothes.",
        "after": "She is washing the clothes by hand.",
        "status": "applied",
        "reason": "搓洗 specifically means hand-washing/rubbing.",
    },
    # 342-343
    {
        "source_line": "342-343",
        "note_id": 1419644220234,
        "field": "English",
        "before": "Grapes can be made into wine.",
        "after": "",
        "status": "review",
        "reason": "The proposed swap with the next card is stylistic; both translations are correct.",
    },
    # 345-346
    {
        "source_line": "345-346",
        "note_id": 1419644220394,
        "field": "English",
        "before": "We could have gone on a picnic if not for the rain.",
        "after": "We could have gone on an outing if not for the rain.",
        "status": "applied",
        "reason": "郊游 is an outing/excursion, not specifically a picnic.",
    },
    # 348-349
    {
        "source_line": "348-349",
        "note_id": 1419644219111,
        "field": "English",
        "before": "The shape of this diamond is very unique.",
        "after": "The shape of this diamond ring is very unique.",
        "status": "applied",
        "reason": "钻戒 is a diamond ring.",
    },
    # 351-352
    {
        "source_line": "351-352",
        "note_id": 1419644216201,
        "field": "Pinyin",
        "before": "zhuàng",
        "after": "zhuàng",
        "status": "already-correct",
        "reason": "The current release already reads zhuàng.",
    },
    # 354-355
    {
        "source_line": "354-355",
        "note_id": 1419644218942,
        "field": "English",
        "before": "She is painting the wall.",
        "after": "She is whitewashing the wall.",
        "status": "applied",
        "reason": "粉刷 is whitewashing/plastering rather than ordinary painting.",
    },
    # 357-358
    {
        "source_line": "357-358",
        "note_id": 1419644219037,
        "field": "Pinyin",
        "before": "chuānzhe",
        "after": "chuānzhuó",
        "status": "applied",
        "reason": "穿着 meaning attire is chuānzhuó, not the progressive chuānzhe.",
    },
    # 360-361
    {
        "source_line": "360-361",
        "note_id": 1419644217590,
        "field": "Hanzi",
        "before": "她戴着耳机听音乐。",
        "after": "我戴着耳机听音乐。",
        "status": "applied",
        "reason": "The audio says 我, not 她.",
    },
    {
        "source_line": "360-361",
        "note_id": 1419644217590,
        "field": "English",
        "before": "She is listening to music through earphones.",
        "after": "I am listening to music through earphones.",
        "status": "applied",
        "reason": "Align the translation with the spoken subject.",
    },
    # 363-364
    {
        "source_line": "363-364",
        "note_id": 1419644218699,
        "field": "Pinyin",
        "before": "tán gāngqín",
        "after": "tán gāngqín",
        "status": "already-correct",
        "reason": "The current release already reads tán gāngqín.",
    },
    # 366-367
    {
        "source_line": "366-367",
        "note_id": 1419644219530,
        "field": "English",
        "before": "He sent flowers to his mother.",
        "after": "He presented a bouquet of flowers to his mother.",
        "status": "applied",
        "reason": "献花 means presenting flowers in person.",
    },
    # 369-370
    {
        "source_line": "369-370",
        "note_id": 1419644220115,
        "field": "English",
        "before": "He extended his right arm.",
        "after": "He extended his arm.",
        "status": "applied",
        "reason": "The Chinese does not specify the right arm.",
    },
    # 372-373
    {
        "source_line": "372-373",
        "note_id": 1419644215986,
        "field": "English",
        "before": "According to the lowest reckoning(estimate), it will cost thirty thousand yen.",
        "after": "",
        "status": "duplicate",
        "reason": "Repeated feedback item; the correction is recorded at lines 107-108.",
    },
    # 375-376
    {
        "source_line": "375-376",
        "note_id": 1419644220112,
        "field": "English",
        "before": "We are in the same generation of the family.",
        "after": "We are in the same generation.",
        "status": "applied",
        "reason": "同辈 does not specifically mean family.",
    },
    # 378-379
    {
        "source_line": "378-379",
        "note_id": 1419644220731,
        "field": "Hanzi",
        "before": "今天是卅一日。",
        "after": "今天是三十一日。",
        "status": "applied",
        "reason": "The audio says 三十一日; use the spoken form.",
    },
    {
        "source_line": "378-379",
        "note_id": 1419644220731,
        "field": "Audio",
        "before": "今天是卅一日。",
        "after": "",
        "status": "audio-only",
        "reason": "The audio uses 三十一日; the text now matches it.",
    },
    # 381-382
    {
        "source_line": "381-382",
        "note_id": 1419644220295,
        "field": "English",
        "before": "The bees are collecting honey from the flowers.",
        "after": "The bees are collecting nectar from the flowers.",
        "status": "applied",
        "reason": "Bees collect nectar, not honey.",
    },
    # 384-387
    {
        "source_line": "384-387",
        "note_id": 1419644214132,
        "field": "Audio",
        "before": "你向我保证说到做到。",
        "after": "",
        "status": "audio-only",
        "reason": "The spoken subject is 他/她; the written 你 is kept and the audio is not edited.",
    },
    # 389-390
    {
        "source_line": "389-390",
        "note_id": 1419644218561,
        "field": "Pinyin",
        "before": "chāi qiáo",
        "after": "",
        "status": "duplicate",
        "reason": "Repeated pinyin feedback; already recorded at lines 279-281.",
    },
    # 392-393
    {
        "source_line": "392-393",
        "note_id": 1419644217589,
        "field": "Audio",
        "before": "我们在任何公司都应该是执行者。",
        "after": "",
        "status": "audio-only",
        "reason": "The spoken sentence differs substantially; text is kept and audio is not edited.",
    },
    # 395-396
    {
        "source_line": "395-396",
        "note_id": 1419644218807,
        "field": "Hanzi",
        "before": "10月1日是中国的国庆日。",
        "after": "10月1日是中国的国庆节。",
        "status": "applied",
        "reason": "国庆节 is the standard name.",
    },
    {
        "source_line": "395-396",
        "note_id": 1419644218807,
        "field": "Pinyin",
        "before": "guóqìng rì",
        "after": "guóqìng jié",
        "status": "applied",
        "reason": "Number lines preserve their inherited reading, so the corrected 节 needs an explicit pinyin override.",
    },
    # 398-399
    {
        "source_line": "398-399",
        "note_id": 1419644216929,
        "field": "Audio",
        "before": "我收到了一张请帖。",
        "after": "",
        "status": "audio-only",
        "reason": "Beginning and ending are cut off; text is correct.",
    },
    # 401-403
    {
        "source_line": "401-403",
        "note_id": 1419644220727,
        "field": "English",
        "before": "She's putting on face powder and lipstick.",
        "after": "She's putting on blush.",
        "status": "applied",
        "reason": "胭脂 is blush; the Chinese does not mention lipstick or powder.",
    },
    # 405-406
    {
        "source_line": "405-406",
        "note_id": 1419644218939,
        "field": "English",
        "before": "It's cold, so be careful not to catch a cold.",
        "after": "It's cold, so be careful not to freeze.",
        "status": "applied",
        "reason": "冻坏 means freeze, not catch a cold.",
    },
    # 408-410
    {
        "source_line": "408-410",
        "note_id": 1419644220695,
        "field": "English",
        "before": "The rescue worker beat the area, looking for the child.",
        "after": "In order to find the child, the rescuers carefully searched the area.",
        "status": "applied",
        "reason": "Replace the unclear idiom with a direct translation.",
    },
    # 412-414
    {
        "source_line": "412-414",
        "note_id": 1419644220734,
        "field": "Pinyin",
        "before": "qióngkùn liáodǎo",
        "after": "qióngkùn liáodǎo",
        "status": "already-correct",
        "reason": "The current release already reads qióngkùn liáodǎo.",
    },
    # 416-417
    {
        "source_line": "416-417",
        "note_id": 1419644220749,
        "field": "English",
        "before": "He's chopping firewood on the tree stump.",
        "after": "He's chopping firewood on the log.",
        "status": "applied",
        "reason": "The object is a log driven into the ground, not a tree stump.",
    },
    # 419-420
    {
        "source_line": "419-420",
        "note_id": 1419644220513,
        "field": "English",
        "before": "Versailles is splendid in green and gold.",
        "after": "The palace of Versailles is splendid and dazzling.",
        "status": "applied",
        "reason": "金碧辉煌 means splendid/dazzling, not green and gold.",
    },
    # 422-424
    {
        "source_line": "422-424",
        "note_id": 1419644220766,
        "field": "Pinyin",
        "before": "chuīxū jiànjiàng",
        "after": "chuīxū jiànjiàng",
        "status": "already-correct",
        "reason": "The current release already reads chuīxū jiànjiàng.",
    },
    # 426-427
    {
        "source_line": "426-427",
        "note_id": 1419644220793,
        "field": "Pinyin",
        "before": "mí",
        "after": "mí",
        "status": "already-correct",
        "reason": "The current release already reads mí.",
    },
    # 429-430
    {
        "source_line": "429-430",
        "note_id": 1419644216200,
        "field": "Pinyin",
        "before": "zhuàng",
        "after": "zhuàng",
        "status": "already-correct",
        "reason": "The current release already reads zhuàng.",
    },
    # 432-433
    {
        "source_line": "432-433",
        "note_id": 1419644218375,
        "field": "Pinyin",
        "before": "jì shàng",
        "after": "jì shàng",
        "status": "already-correct",
        "reason": "The current release already reads jì shàng.",
    },
    # 435-437
    {
        "source_line": "435-437",
        "note_id": 1419644220594,
        "field": "English",
        "before": "The flute sounds very beautiful.",
        "after": "The flute is a very beautiful sounding instrument.",
        "status": "applied",
        "reason": "Use the suggested one-to-one translation.",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_source_line(value: str) -> tuple[int, int]:
    """Parse ``12`` or ``12-13`` into an inclusive line range."""
    match = re.fullmatch(r"(\d+)(?:-(\d+))?", value.strip())
    if not match:
        raise ValueError(f"bad source_line: {value!r}")
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if end < start:
        raise ValueError(f"bad source_line range: {value!r}")
    return start, end


def rows_for(field: str, status: str = "applied") -> list[dict]:
    return [
        row
        for row in FEEDBACK_ROWS
        if row["field"] == field and row["status"] == status
    ]


def applied_hanzi() -> dict[int, dict]:
    return {row["note_id"]: row for row in rows_for("Hanzi")}


def applied_english() -> dict[int, dict]:
    return {row["note_id"]: row for row in rows_for("English")}


def applied_pinyin() -> list[dict]:
    return rows_for("Pinyin")


def apply_pinyin_overrides(
    note_id: int, line_index: int, pinyin_text: str
) -> tuple[str, list[dict]]:
    """Apply exact pinyin-only feedback strings for one line."""
    changes: list[dict] = []
    for row in applied_pinyin():
        if row["note_id"] != note_id:
            continue
        before = row["before"]
        after = row["after"]
        if after in pinyin_text and before not in pinyin_text:
            continue
        if before not in pinyin_text:
            raise ValueError(
                f"pinyin feedback {row['source_line']} for {note_id}:{line_index} "
                f"missing {before!r} in {pinyin_text!r}"
            )
        pinyin_text = pinyin_text.replace(before, after, 1)
        changes.append(
            {
                "kind": "word",
                "char_index": None,
                "char": "",
                "word": "",
                "original": before,
                "corrected": after,
                "reason": "feedback-pinyin",
            }
        )
    return pinyin_text, changes


def feedback_blocks(path: Path | None = None) -> list[tuple[int, int]]:
    """Return the non-empty feedback blocks as inclusive line ranges."""
    path = path or (DATA / "feedback_source.txt")
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: list[tuple[int, int]] = []
    start: int | None = None
    for number, line in enumerate(lines, start=1):
        if line.strip():
            if start is None:
                start = number
        elif start is not None:
            blocks.append((start, number - 1))
            start = None
    if start is not None:
        blocks.append((start, len(lines)))
    return blocks


def uncovered_blocks(path: Path | None = None) -> list[tuple[int, int]]:
    """Feedback blocks with no ledger row covering them."""
    ranges = [parse_source_line(row["source_line"]) for row in FEEDBACK_ROWS]
    missing: list[tuple[int, int]] = []
    for start, end in feedback_blocks(path):
        if not any(a <= end and start <= b for a, b in ranges):
            missing.append((start, end))
    return missing


def validate_ledger() -> None:
    """Sanity-check the hand-written ledger before the build uses it."""
    for row in FEEDBACK_ROWS:
        if row["status"] not in STATUSES:
            raise ValueError(f"unknown status {row['status']!r} in {row['source_line']}")
        if row["status"] == "applied" and row["before"] == row["after"]:
            raise ValueError(f"no-op applied row at {row['source_line']}")
        if row["status"] == "applied" and row["field"] not in {
            "Hanzi",
            "English",
            "Pinyin",
        }:
            raise ValueError(f"applied row with unsupported field at {row['source_line']}")
    missing = uncovered_blocks()
    if missing:
        raise ValueError(f"feedback blocks without triage rows: {missing}")
    # One effective change per note/field.
    seen: dict[tuple[int, str], str] = {}
    for row in rows_for("Hanzi") + rows_for("English"):
        key = (row["note_id"], row["field"])
        if key in seen:
            raise ValueError(f"duplicate applied {key} at {row['source_line']}")
        seen[key] = row["after"]

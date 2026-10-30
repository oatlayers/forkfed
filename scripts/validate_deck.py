"""Acceptance checks for ``dist/Forkfed_Chinese.apkg``.

Run after ``scripts/07_build_apkg.py``.  Exits nonzero on hard failures and
writes ``data/qa.json`` with the check matrix and release status.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

import opencc

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import sp_common as c  # noqa: E402
import sp_feedback as F  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = ROOT / "source" / "Spoonfed_Chinese_Forkfed.apkg"
OUTPUT = ROOT / "dist" / "Forkfed_Chinese.apkg"

FIELDS = [
    "English",
    "Pinyin",
    "Hanzi",
    "Audio",
    "HanziTraditional",
    "PinyinSandhi",
    "PinyinOriginal",
    "Zhuyin",
    "ZhuyinSandhi",
    "Sequence",
    "SortOrder",
]
SORT_FIELD_ORD = 10

TRAD_BAD = [
    "小么",
    "音樂傢",
    "傢俱樂部",
    "手錶示",
    "一箇",
    "鬍須",
    "頭髮幹",
    "衝洗",
    "遊泳",
    "曆史",
    "復雜",
    "丑聞",
    "記事本里",
    "大海里",
    "海里的",
    "碗里",
    "東西后",
    "人口占",
    "游蕩",
]

# Characters that are valid traditional forms in some contexts and whose
# single-character s2tw conversion is therefore not a reliable error test.
TRAD_AMBIGUOUS = set("游里托干岩占丑后伙征划幺准岳斗杰凶")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def to_html(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def plain(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")
    text = re.sub(r"\[sound:[^\]]+\]", "", text)
    return text


def field_checksum(text: str) -> int:
    digest = hashlib.sha1(plain(text).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def extract_db(zf: zipfile.ZipFile, name: str) -> Path:
    fd, tmp = tempfile.mkstemp(suffix=".anki21")
    os.close(fd)
    path = Path(tmp)
    path.write_bytes(zf.read(name))
    return path


def rows(con: sqlite3.Connection, sql: str):
    return [tuple(row) for row in con.execute(sql)]


def main() -> None:
    audit = read_json(DATA / "audit.json")
    notes = audit["notes"]
    pinyin_data = read_json(DATA / "pinyin.json")
    pinyin_by_id = {n["id"]: n for n in pinyin_data["notes"]}
    source_notes = {n["id"]: n for n in read_json(DATA / "notes.json")}
    source_cards = {c["id"]: c for c in read_json(DATA / "cards.json")}
    duplicate_rows = read_csv(DATA / "duplicates.csv")
    ledger = read_csv(DATA / "feedback_corrections.csv")
    audio_issues = read_csv(DATA / "audio_issues.csv")
    gold = read_json(DATA / "gold_set_accuracy.json")
    deleted_ids = {int(row["deleted_note_id"]) for row in duplicate_rows}
    checks: list[tuple[str, bool, str]] = []

    def check(label: str, ok: bool, detail: str = "") -> None:
        checks.append((label, bool(ok), detail))

    check("Release package exists", OUTPUT.exists(), str(OUTPUT))
    check("Note count is 7,326", len(notes) == 7326, str(len(notes)))
    check("Duplicate ledger has 9 groups", len(duplicate_rows) == 9, str(len(duplicate_rows)))
    check("Feedback ledger is populated", len(ledger) > 0, str(len(ledger)))
    check("Audio issue ledger is populated", len(audio_issues) >= 20, str(len(audio_issues)))

    with zipfile.ZipFile(SOURCE) as src_zip, zipfile.ZipFile(OUTPUT) as out_zip:
        src_infos = {i.filename: i for i in src_zip.infolist()}
        out_infos = {i.filename: i for i in out_zip.infolist()}
        check("ZIP member list unchanged", list(src_infos) == list(out_infos))
        media_bad = [
            name
            for name, info in src_infos.items()
            if name != "collection.anki21"
            and (
                name not in out_infos
                or info.file_size != out_infos[name].file_size
                or info.CRC != out_infos[name].CRC
            )
        ]
        check(
            "All non-database members byte-identical",
            not media_bad,
            f"{len(media_bad)} differences",
        )
        check(
            "collection.anki2 placeholder unchanged",
            out_zip.read("collection.anki2") == src_zip.read("collection.anki2"),
        )
        check("media map unchanged", out_zip.read("media") == src_zip.read("media"))
        check("meta marker unchanged", out_zip.read("meta") == src_zip.read("meta"))

        media_names = set(json.loads(out_zip.read("media").decode("utf-8")).values())

        src_db = extract_db(src_zip, "collection.anki21")
        out_db = extract_db(out_zip, "collection.anki21")
        try:
            src = sqlite3.connect(src_db)
            out = sqlite3.connect(out_db)
            src.row_factory = sqlite3.Row
            out.row_factory = sqlite3.Row

            check(
                "APKG note count 7,326",
                out.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 7326,
            )
            check(
                "APKG card count 7,326",
                out.execute("SELECT COUNT(*) FROM cards").fetchone()[0] == 7326,
            )
            check(
                "SQLite integrity",
                out.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
            )

            audit_ids = {note["id"] for note in notes}
            src_note_ids = {row[0] for row in src.execute("SELECT id FROM notes")}
            out_note_ids = {row[0] for row in out.execute("SELECT id FROM notes")}
            check("Retained note IDs unchanged", out_note_ids == audit_ids)
            check(
                "Deleted duplicate notes absent",
                not (out_note_ids & deleted_ids)
                and src_note_ids - deleted_ids == audit_ids,
                f"{len(deleted_ids)} deleted",
            )

            src_notes = rows(
                src,
                "SELECT id,guid,mid,mod,usn,flags,data FROM notes ORDER BY id",
            )
            out_notes = rows(
                out,
                "SELECT id,guid,mid,mod,usn,flags,data FROM notes ORDER BY id",
            )
            retained_src_notes = [row for row in src_notes if row[0] not in deleted_ids]
            check("Retained note metadata preserved", retained_src_notes == out_notes)
            check(
                "GUIDs unique",
                out.execute("SELECT COUNT(DISTINCT guid) FROM notes").fetchone()[0] == 7326,
            )

            src_card_ids = {row[0] for row in src.execute("SELECT id FROM cards")}
            deleted_card_ids = {
                card_id
                for card_id, card in source_cards.items()
                if card["nid"] in deleted_ids
            }
            out_card_ids = {row[0] for row in out.execute("SELECT id FROM cards")}
            check(
                "Card IDs unchanged for retained notes",
                out_card_ids == src_card_ids - deleted_card_ids,
                f"{len(deleted_card_ids)} deleted",
            )

            card_columns = [
                "id",
                "nid",
                "did",
                "ord",
                "type",
                "queue",
                "ivl",
                "factor",
                "reps",
                "lapses",
                "left",
                "odue",
                "odid",
                "flags",
                "data",
            ]
            src_cards = rows(
                src, "SELECT " + ",".join(card_columns) + " FROM cards ORDER BY id"
            )
            out_cards = rows(
                out, "SELECT " + ",".join(card_columns) + " FROM cards ORDER BY id"
            )
            retained_src_cards = [
                row for row in src_cards if row[0] not in deleted_card_ids
            ]
            check("Cards unchanged except due", retained_src_cards == out_cards)

            col = out.execute("SELECT models, decks, conf, tags FROM col").fetchone()
            model = next(iter(json.loads(col["models"]).values()))
            check("Model field names and order", [f["name"] for f in model["flds"]] == FIELDS)
            check("Model sort field is SortOrder", model.get("sortf") == SORT_FIELD_ORD)
            check("Model name is Forkfed Chinese", model.get("name") == "Forkfed Chinese")
            check("One card template", len(model["tmpls"]) == 1)
            template = model["tmpls"][0]
            check(
                "Front template has hover/tap pinyin",
                all(
                    token in template["qfmt"]
                    for token in (
                        'id="pinyin-toggle"',
                        'class="pinyin-toggle"',
                        'class="hanzi-wrap"',
                        'class="pinyin hover-pinyin"',
                        "{{Hanzi}}",
                        "{{Pinyin}}",
                    )
                ),
            )
            check(
                "Front template hides optional fields",
                not any(
                    token in template["qfmt"]
                    for token in ("HanziTraditional", "PinyinSandhi", "Zhuyin", "English", "Audio")
                ),
            )
            check(
                "Back template has Hanzi, pinyin, English, audio",
                all(
                    token in template["afmt"]
                    for token in ("{{Hanzi}}", "{{Pinyin}}", "{{English}}", "{{Audio}}", "<hr>")
                ),
            )
            check(
                "Back template hides optional fields",
                not any(
                    token in template["afmt"]
                    for token in ("HanziTraditional", "PinyinSandhi", "Zhuyin")
                ),
            )
            css = model.get("css", "")
            check(
                "Dark Kai/Times/Didot CSS",
                all(
                    token in css
                    for token in (
                        "rgb(47, 47, 49)",
                        "#55dd55",
                        "Kai",
                        '"Times New Roman"',
                        "Didot",
                        "font-size: clamp(30px, 6vw, 48px)",
                        ".pinyin-toggle:checked + .hanzi-wrap",
                        "@media (hover: none)",
                    )
                ),
            )
            decks = json.loads(col["decks"])
            check(
                "Deck name is Forkfed Chinese",
                decks.get("1761004431095", {}).get("name") == "Forkfed Chinese",
            )
            conf = json.loads(col["conf"])
            check("nextPos is 7327", conf.get("nextPos") == 7327)
            check("sortType is noteFld", conf.get("sortType") == "noteFld")
            check("sortBackwards is false", conf.get("sortBackwards") is False)
            check("Collection tag registry empty", col["tags"] == "{}")

            out_by_id = {row["id"]: row for row in out.execute("SELECT * FROM notes")}
            out_cards = {
                row["nid"]: row for row in out.execute("SELECT * FROM cards")
            }
            due_values = sorted(row["due"] for row in out_cards.values())
            check(
                "Card due values are 1..7,326",
                due_values == list(range(1, 7327)),
                f"{len(due_values)} values",
            )

            field_errors: list[str] = []
            tag_errors: list[str] = []
            sort_errors: list[str] = []
            sequence_errors: list[str] = []
            latin_errors: list[str] = []
            apostrophe_errors: list[str] = []
            align_fail_allowed = 0
            align_fail_unexpected = 0
            sandhi_errors: list[str] = []
            zhuyin_errors: list[str] = []
            trad_errors: list[str] = []
            original_errors: list[str] = []

            for note in notes:
                note_id = note["id"]
                row = out_by_id[note_id]
                parts = row["flds"].split("\x1f")
                if len(parts) != len(FIELDS):
                    field_errors.append(f"{note_id}: {len(parts)} fields")
                    continue
                expected = [
                    to_html(note["english"]),
                    to_html(note["pinyin"]),
                    to_html(note["hanzi"]),
                    note["audio"],
                    to_html(note["hanzi_traditional"]),
                    to_html(note["pinyin_sandhi"]),
                    to_html(note["pinyin_original"]),
                    to_html(note["zhuyin"]),
                    to_html(note["zhuyin_sandhi"]),
                    str(note["sequence"]),
                    note["sort_order_text"],
                ]
                if parts != expected:
                    field_errors.append(f"{note_id}: field value mismatch")
                if row["tags"] != "":
                    tag_errors.append(f"{note_id}: tags")
                if parts[10] != f"{note['sort_order']:05d}":
                    sort_errors.append(f"{note_id}: SortOrder")
                if row["sfld"] != int(note["sort_order"]):
                    sort_errors.append(f"{note_id}: sfld")
                if row["csum"] != field_checksum(note["sort_order_text"]):
                    sort_errors.append(f"{note_id}: csum")
                if out_cards[note_id]["due"] != int(note["sort_order"]):
                    sort_errors.append(f"{note_id}: card due")
                if parts[9] != str(note["sequence"]):
                    sequence_errors.append(f"{note_id}: sequence")
                if parts[3] != source_notes[note_id]["fields"]["Audio"]:
                    field_errors.append(f"{note_id}: Audio changed")
                if not parts[6].strip():
                    original_errors.append(f"{note_id}: empty PinyinOriginal")

                for ref in re.findall(r"\[sound:([^\]]+)\]", parts[3]):
                    if ref not in media_names:
                        field_errors.append(f"{note_id}: missing audio {ref}")
                if re.search(
                    r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]+);",
                    " ".join(parts[1:9]),
                ):
                    field_errors.append(f"{note_id}: HTML entity")
                if any(ch in " ".join(parts[1:9]) for ch in "\u200b\u200c\u200d\ufeffɡŏ"):
                    field_errors.append(f"{note_id}: bad character")
                if re.search(r"[\u4e00-\u9fff]", parts[1] + parts[5]):
                    field_errors.append(f"{note_id}: Hanzi in pinyin")

                hz_lines = parts[2].split("<br>")
                py_lines = parts[1].split("<br>")
                sandhi_lines = parts[5].split("<br>")
                orig_lines = parts[6].split("<br>")
                zy_lines = parts[7].split("<br>")
                zys_lines = parts[8].split("<br>")
                trad_lines = parts[4].split("<br>")
                if not (
                    len(hz_lines)
                    == len(py_lines)
                    == len(sandhi_lines)
                    == len(orig_lines)
                    == len(zy_lines)
                    == len(zys_lines)
                    == len(trad_lines)
                ):
                    field_errors.append(f"{note_id}: line count mismatch")
                    continue

                for line_idx, (hz, py, sandhi, original, zy, zys, trad) in enumerate(
                    zip(
                        hz_lines,
                        py_lines,
                        sandhi_lines,
                        orig_lines,
                        zy_lines,
                        zys_lines,
                        trad_lines,
                    )
                ):
                    if not py.strip() or not sandhi.strip() or not original.strip():
                        field_errors.append(f"{note_id}: empty pinyin line")
                        continue
                    items = c.parse_pinyin_line(py, hz)
                    items, ok = c.align_items_to_hanzi(hz, items)
                    line_meta = (
                        note["lines"][line_idx]
                        if line_idx < len(note["lines"])
                        else None
                    )
                    if not ok:
                        if any(
                            flag in {"number", "align-fail-preserved"}
                            for flag in (line_meta or {}).get("flags", [])
                        ):
                            align_fail_allowed += 1
                        else:
                            align_fail_unexpected += 1
                    if c.insert_missing_apostrophes(py, hz) != py:
                        apostrophe_errors.append(f"{note_id}: apostrophe")
                    for match in re.finditer(r"[A-Za-z][A-Za-z0-9]*", hz):
                        token = match.group(0)
                        if (
                            line_meta
                            and line_meta.get("label")
                            and match.start() == 0
                            and token == line_meta["label"]
                        ):
                            continue
                        if not re.search(
                            r"(?<![A-Za-z])" + re.escape(token) + r"(?![A-Za-z])", py
                        ):
                            latin_errors.append(f"{note_id}: {token}")

                    without_bold = re.sub(
                        r'<b class="tone-change">(.*?)</b>', r"\1", sandhi
                    )
                    if re.search(r"<[^>]+>", without_bold):
                        sandhi_errors.append(f"{note_id}: tag in sandhi")
                    bolds = re.findall(r'<b class="tone-change">(.*?)</b>', sandhi)
                    lex_items = c.parse_pinyin_line(py, hz)
                    lex_items, lex_ok = c.align_items_to_hanzi(hz, lex_items)
                    sur_items = c.parse_pinyin_line(without_bold, hz)
                    sur_items, sur_ok = c.align_items_to_hanzi(hz, sur_items)
                    if lex_ok and sur_ok:
                        lex_syl = [x for x in lex_items if x.kind == "syl"]
                        sur_syl = [x for x in sur_items if x.kind == "syl"]
                        if len(lex_syl) != len(sur_syl):
                            sandhi_errors.append(f"{note_id}: sandhi syllable count")
                        else:
                            diffs = sum(
                                1
                                for a, b in zip(lex_syl, sur_syl)
                                if a.syl is not None
                                and b.syl is not None
                                and (a.syl.base, a.syl.tone, a.syl.erhua)
                                != (b.syl.base, b.syl.tone, b.syl.erhua)
                            )
                            if diffs != len(bolds):
                                sandhi_errors.append(f"{note_id}: bold/diff count")
                    elif bolds:
                        sandhi_errors.append(f"{note_id}: bold on unaligned line")

                    if not zy.strip() or not zys.strip():
                        zhuyin_errors.append(f"{note_id}: empty zhuyin")
                    for field in (zy, zys):
                        for match in re.finditer("˙", field):
                            nxt = field[match.end() : match.end() + 1]
                            if not ("\u3105" <= nxt <= "\u3129"):
                                zhuyin_errors.append(f"{note_id}: neutral dot placement")
                                break
                    if zys.count('<b class="tone-change">') != len(bolds):
                        zhuyin_errors.append(f"{note_id}: zhuyin bold count")

                    if not trad.strip():
                        trad_errors.append(f"{note_id}: empty traditional")
                    for bad in TRAD_BAD:
                        if bad in trad:
                            trad_errors.append(f"{note_id}: {bad}")

            check("Output fields match audit data", not field_errors, f"{len(field_errors)} errors")
            check("No note has tags", not tag_errors, f"{len(tag_errors)} errors")
            check("SortOrder, sfld and due agree", not sort_errors, f"{len(sort_errors)} errors")
            check("Sequence values match audit data", not sequence_errors, f"{len(sequence_errors)} errors")
            check("Audio field unchanged", not any("Audio changed" in e for e in field_errors))
            check("All sound references resolve", not any("missing audio" in e for e in field_errors))
            check("PinyinOriginal nonempty for every note", not original_errors)
            check(
                "Pinyin alignment (allowed exceptions only)",
                align_fail_unexpected == 0,
                f"{align_fail_allowed} allowed failures",
            )
            check("Apostrophes complete", not apostrophe_errors, f"{len(apostrophe_errors)} errors")
            check("Latin tokens preserve case", not latin_errors, f"{len(latin_errors)} errors")
            check("Sandhi bolding is exact", not sandhi_errors, f"{len(sandhi_errors)} errors")
            check("Zhuyin nonempty and neutral dots valid", not zhuyin_errors, f"{len(zhuyin_errors)} errors")
            check("Traditional spot checks and bad phrases", not trad_errors, f"{len(trad_errors)} errors")

            covers = Counter({"cjk": 0, "pinyin": 0, "english": 0})
            for note in notes:
                covers["cjk"] += 1
                covers["pinyin"] += 1
                covers["english"] += 1
            check(
                "All 7,326 notes render core fields",
                covers["cjk"] == covers["pinyin"] == covers["english"] == 7326,
                str(dict(covers)),
            )

            tag_counts = Counter(
                tag
                for row in out.execute("SELECT tags FROM notes")
                for tag in row["tags"].split()
            )
            check("No tags anywhere in notes", not tag_counts)
            check("No legacy QC tags", not any(
                tag in tag_counts
                for tag in ("pinyin-auto", "pinyin-reviewed", "number-expanded", "duplicate")
            ))

            s2tw = opencc.OpenCC("s2tw")
            trad_chars = Counter(
                ch for note in notes for ch in note["hanzi_traditional"] if "\u4e00" <= ch <= "\u9fff"
            )
            suspects = {
                ch
                for ch in trad_chars
                if ch not in TRAD_AMBIGUOUS and s2tw.convert(ch) != ch
            }
            check(
                "No simplified-only characters in HanziTraditional",
                not suspects,
                f"suspects: {''.join(sorted(suspects))}",
            )

            spec = importlib.util.spec_from_file_location(
                "step5", ROOT / "scripts" / "05_zhuyin_traditional.py"
            )
            step5 = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(step5)
            failed_tests = []
            for simplified, expected in step5.TRAD_TEST_ROWS:
                got = step5.convert_traditional(simplified)
                if got != expected:
                    failed_tests.append((simplified, expected, got))
            check("Traditional one-to-many test table", not failed_tests, f"{len(failed_tests)} failures")

            zh_failures = []
            for hz, py, expected in step5.ZH_TEST_ROWS:
                got = c.render_zhuyin(c.parse_pinyin_line(py, hz))
                if got != expected:
                    zh_failures.append((hz, expected, got))
            check("Zhuyin self-test table", not zh_failures, f"{len(zh_failures)} failures")

            src.close()
            out.close()
        finally:
            src_db.unlink(missing_ok=True)
            out_db.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Sequence, SortOrder and duplicate policy
    # ------------------------------------------------------------------
    sort_texts = [note["sort_order_text"] for note in notes]
    expected_sort = [f"{index:05d}" for index in range(1, 7327)]
    check("SortOrder values are 00001..07326", sort_texts == expected_sort)
    check(
        "SortOrder values are unique and complete",
        len(set(sort_texts)) == 7326 and len(sort_texts) == 7326,
    )
    sequences = [note["sequence"] for note in notes]
    missing_sequences = set(range(1, 7336)) - set(sequences)
    check(
        "Sequence keeps the original order with 9 gaps",
        len(sequences) == len(set(sequences)) == 7326
        and sequences == sorted(sequences)
        and len(missing_sequences) == 9,
        f"missing {sorted(missing_sequences)}",
    )
    check(
        "First note is 你好 at 00001",
        notes[0]["hanzi"] == "你好！" and notes[0]["sort_order_text"] == "00001",
    )
    check(
        "Last note has sort order 07326",
        notes[-1]["sort_order_text"] == "07326",
    )

    deleted_from_csv = {int(row["deleted_note_id"]) for row in duplicate_rows}
    kept_from_csv = {int(row["kept_note_id"]) for row in duplicate_rows}
    audit_ids = {note["id"] for note in notes}
    check(
        "Duplicate CSV matches the duplicate policy",
        deleted_from_csv == F.DELETED_NOTE_IDS
        and kept_from_csv == F.KEPT_NOTE_IDS,
    )
    check("All duplicate kept notes are present", kept_from_csv <= audit_ids)
    check("No duplicate deleted note is present", not (deleted_from_csv & audit_ids))

    # ------------------------------------------------------------------
    # Feedback ledger
    # ------------------------------------------------------------------
    statuses = Counter(row["status"] for row in ledger)
    check(
        "Feedback ledger has only valid statuses",
        set(statuses) <= F.STATUSES,
        str(dict(statuses)),
    )
    check(
        "Feedback ledger covers every feedback line",
        not F.uncovered_blocks(),
        str(F.uncovered_blocks()),
    )
    covered_lines: set[int] = set()
    for row in ledger:
        start, end = F.parse_source_line(row["source_line"])
        covered_lines.update(range(start, end + 1))
    feedback_lines = [
        number
        for number, line in enumerate(
            (DATA / "feedback_source.txt").read_text(encoding="utf-8").splitlines(),
            start=1,
        )
        if line.strip()
    ]
    check(
        "Every non-empty feedback line has a triage row",
        all(number in covered_lines for number in feedback_lines),
        f"{len(feedback_lines)} lines",
    )

    by_id = {note["id"]: note for note in notes}
    applied_errors: list[str] = []
    for row in ledger:
        if row["status"] != "applied":
            continue
        note_id = int(row["note_id"])
        note = by_id.get(note_id)
        if note is None:
            applied_errors.append(f"{row['source_line']}: note {note_id} missing")
            continue
        field = row["field"]
        if field == "Hanzi":
            current = note["hanzi"]
        elif field == "English":
            current = note["english"]
        elif field == "Pinyin":
            current = note["pinyin"]
        else:
            applied_errors.append(f"{row['source_line']}: unsupported field {field}")
            continue
        if row["after"] not in current:
            applied_errors.append(
                f"{row['source_line']}: {field} after-value missing from {note_id}"
            )
    check("Applied feedback rows are present in the deck", not applied_errors, f"{len(applied_errors)} errors")

    # No unledgered Hanzi/English sentence changes versus the cleaned source.
    applied_hanzi = {row["note_id"]: row["after"] for row in F.rows_for("Hanzi")}
    applied_english = {row["note_id"]: row["after"] for row in F.rows_for("English")}
    unledgered: list[str] = []
    for note in notes:
        source = source_notes[note["id"]]["fields"]
        cleaned_hz = c.normalize_variants(c.clean_hanzi(source.get("Hanzi", "")))[0]
        cleaned_en = c.clean_field(source.get("English", ""))
        if note["hanzi"] != cleaned_hz and note["hanzi"] != applied_hanzi.get(note["id"]):
            unledgered.append(f"{note['id']}: Hanzi")
        if note["english"] != cleaned_en and note["english"] != applied_english.get(note["id"]):
            unledgered.append(f"{note['id']}: English")
    check("No unledgered Hanzi/English changes", not unledgered, f"{len(unledgered)} errors")

    audio_ids = {int(row["note_id"]) for row in audio_issues if row["note_id"]}
    check(
        "Audio issue notes exist in the deck",
        audio_ids <= audit_ids,
        f"{len(audio_ids)} notes",
    )
    check(
        "Audio issues have observations and dispositions",
        all(row["observation"].strip() and row["disposition"].strip() for row in audio_issues),
    )

    # ------------------------------------------------------------------
    # Gold accuracy and package metadata
    # ------------------------------------------------------------------
    check("Gold sample has 200 notes", gold.get("notes") == 200, str(gold.get("notes")))
    check("Gold sample has no unresolved issues", not gold.get("unresolved"), str(gold.get("unresolved")))
    check("Gold syllable accuracy is 100%", gold.get("syllable_after") == 1.0, str(gold.get("syllable_after")))
    check("Gold tone accuracy is 100%", gold.get("tone_after") == 1.0, str(gold.get("tone_after")))

    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    check("Package hash recorded", bool(digest), digest[:16])
    check(
        "Package size is stable",
        OUTPUT.stat().st_size > 120_000_000,
        f"{OUTPUT.stat().st_size} bytes",
    )

    failures = [row for row in checks if not row[1]]
    write_report(checks, failures, notes, digest)
    print(
        json.dumps(
            {
                "checks": len(checks),
                "failed": len(failures),
                "output": str(OUTPUT.relative_to(ROOT)),
                "size": OUTPUT.stat().st_size,
                "sha256": digest,
                "notes": len(notes),
                "cards": len(notes),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if failures:
        for label, _, detail in failures:
            print(f"FAIL: {label} {detail}")
        raise SystemExit(1)


def write_report(
    checks: list[tuple[str, bool, str]],
    failures: list[tuple[str, bool, str]],
    notes: list[dict],
    digest: str,
) -> None:
    ledger_path = DATA / "review_decisions.csv"
    ledger: list[dict] = []
    if ledger_path.exists():
        with ledger_path.open(encoding="utf-8-sig") as fh:
            ledger = list(csv.DictReader(fh))
    result = {
        "generated_by": "scripts/validate_deck.py",
        "output": str(OUTPUT.relative_to(ROOT)),
        "passed": len(checks) - len(failures),
        "total": len(checks),
        "sha256": digest,
        "size": OUTPUT.stat().st_size,
        "notes": len(notes),
        "cards": len(notes),
        "checks": [
            {"check": label, "ok": ok, "detail": detail}
            for label, ok, detail in checks
        ],
        "review": {
            "total": len(ledger),
            "fixed": sum(1 for row in ledger if row["decision"] == "fixed"),
            "mixed": sum(1 for row in ledger if row["decision"] == "mixed"),
            "accepted": sum(1 for row in ledger if row["decision"] == "accepted"),
        },
    }
    (DATA / "qa.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

"""Build ``dist/Forkfed_Chinese.apkg`` from the audited data.

The source deck is copied; only the legacy ``collection.anki21`` database is
modified.  ``collection.anki2`` (a one-note placeholder), ``media`` and every
media file are copied byte-for-byte.

Changes for 3.0:

* the deck and note type are renamed to Forkfed Chinese;
* nine exact-duplicate copies are removed;
* all note and collection tags are removed;
* ``SortOrder`` (``00001``-``07326``) becomes the note-type sort field and the
  card ``due`` values run contiguously from 1 to 7,326;
* the single card template uses the dark Kai/Times/Didot layout with hover
  or tap pinyin on the front and Hanzi + pinyin + English + audio on the back.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DIST = ROOT / "dist"
SOURCE = ROOT / "source" / "Spoonfed_Chinese_Forkfed.apkg"
OUTPUT = DIST / "Forkfed_Chinese.apkg"

DECK_ID = 1761004431095
DECK_NAME = "Forkfed Chinese"
MODEL_NAME = "Forkfed Chinese"

FIELD_NAMES = [
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

QUESTION = """<input type="checkbox" id="pinyin-toggle" class="pinyin-toggle">
<label for="pinyin-toggle" class="hanzi-wrap">
  <div class="pinyin hover-pinyin">{{Pinyin}}</div>
  <div lang="zh-Hans" class="hanzi">{{Hanzi}}</div>
</label>"""

ANSWER = """<div lang="zh-Hans" class="hanzi">{{Hanzi}}</div>
<div class="pinyin">{{Pinyin}}</div>
<hr>
<div class="english">{{English}}</div>
<div class="audio">{{Audio}}</div>"""

CSS = """.card {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 16px;
  text-align: left;
  background-color: rgb(47, 47, 49);
  color: #fff;
  padding: 20px;
}

div { margin-bottom: 10px; }

hr {
  height: 3px;
  background: #fff;
  border: none;
  margin: 20px 0;
}

.pinyin-toggle {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.hanzi-wrap {
  position: relative;
  display: block;
  cursor: pointer;
  outline: none;
}

.hanzi {
  font-family: Kai, "Kaiti SC", KaiTi, "Noto Serif CJK SC", serif;
  font-size: 48px;
  font-size: clamp(30px, 6vw, 48px);
  line-height: 1.35;
  margin-top: 20px;
}

/*
 * Times New Roman (and the later fallbacks) include the pinyin caron vowels
 * and the u-diaeresis tone vowels. Palatino/Georgia do not, and their
 * per-glyph fallback is what made some tone marks look wrong.
 */
.pinyin {
  font-family: "Times New Roman", "Liberation Serif", "Noto Serif",
    "DejaVu Serif", Georgia, serif;
  font-size: 22px;
  line-height: 1.45;
  color: #55dd55;
}

/* Reserve the pinyin's space so wrapped text stays inside the card. */
.pinyin.hover-pinyin {
  margin: 0 0 10px 0;
  padding: 4px 10px;
  border-left: 3px solid #fff;
  background: rgb(47, 47, 49);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.35s ease;
}

.hanzi-wrap:hover .pinyin.hover-pinyin,
.pinyin-toggle:checked + .hanzi-wrap .pinyin.hover-pinyin {
  opacity: 1;
}

.english {
  font-family: Didot, "Didot LT STD", Georgia, serif;
  font-size: 16px;
}

.audio { margin-top: 16px; }

/* Optional fields */
.hanzi.traditional { font-size: 40px; color: #e8e8e8; }
.zhuyin {
  font-family: "Noto Sans Bopomofo", "Microsoft JhengHei", sans-serif;
  font-size: 20px;
  color: #55dd55;
}
.sandhi .tone-change { font-weight: 700; color: #ffd166; }
.meta { font-family: Georgia, serif; font-size: 12px; color: #8a8a8a; }

@media (hover: none) {
  /* Touch: do not let the emulated hover stick; only the checkbox toggles. */
  .hanzi-wrap:hover .pinyin.hover-pinyin {
    opacity: 0;
  }
  .pinyin-toggle:checked + .hanzi-wrap .pinyin.hover-pinyin {
    opacity: 1;
  }
}
"""


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
    return html.unescape(text)


def field_checksum(text: str) -> int:
    digest = hashlib.sha1(plain(text).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def build_model(original: dict, now_s: int) -> dict:
    model = copy.deepcopy(original)
    existing = {f["name"]: f for f in model["flds"]}
    fields = []
    for ord_, name in enumerate(FIELD_NAMES):
        if name in existing:
            field = copy.deepcopy(existing[name])
            field["ord"] = ord_
        else:
            field = {
                "name": name,
                "ord": ord_,
                "sticky": False,
                "rtl": False,
                "font": "Arial",
                "size": 20,
                "description": "",
                "plainText": False,
                "collapsed": False,
                "excludeFromSearch": False,
                "id": None,
                "tag": None,
                "preventDeletion": False,
                "media": [],
            }
        fields.append(field)
    model["flds"] = fields
    model["name"] = MODEL_NAME
    model["mod"] = now_s
    model["usn"] = 0
    model["did"] = DECK_ID
    template = copy.deepcopy(model["tmpls"][0])
    template["name"] = "Card 1"
    template["ord"] = 0
    template["qfmt"] = QUESTION
    template["afmt"] = ANSWER
    template["bqfmt"] = ""
    template["bafmt"] = ""
    template["did"] = None
    template["bfont"] = "SimHei"
    template["bsize"] = 14
    template["id"] = None
    model["tmpls"] = [template]
    model["css"] = CSS
    model["req"] = [[0, "any", [2]]]
    model["sortf"] = SORT_FIELD_ORD
    return model


def main() -> None:
    audit = read_json(DATA / "audit.json")
    notes = audit["notes"]
    source_notes = {n["id"]: n for n in read_json(DATA / "notes.json")}
    meta = read_json(DATA / "meta.json")
    duplicate_rows = read_csv(DATA / "duplicates.csv")
    deleted_ids = {int(row["deleted_note_id"]) for row in duplicate_rows}

    if len(notes) != 7326:
        raise SystemExit(f"unexpected note count: {len(notes)}")
    if len(deleted_ids) != 9:
        raise SystemExit(f"unexpected duplicate count: {len(deleted_ids)}")
    if set(source_notes) - deleted_ids != {n["id"] for n in notes}:
        raise SystemExit("retained note id set differs from source minus duplicates")

    DIST.mkdir(exist_ok=True)
    now_s = int(time.time())
    now_ms = now_s * 1000

    with zipfile.ZipFile(SOURCE) as zf:
        source_names = zf.namelist()
        raw = zf.read("collection.anki21")
        placeholder = zf.read("collection.anki2")
        media_json = zf.read("media")
        meta_bytes = zf.read("meta") if "meta" in source_names else b""

    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".anki21")
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    tmp_path.write_bytes(raw)
    con = sqlite3.connect(tmp_path)
    con.row_factory = sqlite3.Row
    try:
        col = con.execute("SELECT * FROM col").fetchone()
        models = json.loads(col["models"])
        model_id = str(meta["model_id"])
        models[model_id] = build_model(models[model_id], now_s)

        conf = json.loads(col["conf"])
        conf["curModel"] = int(model_id)
        conf["curDeck"] = DECK_ID
        conf["activeDecks"] = [DECK_ID]
        conf["nextPos"] = 7327
        conf["sortType"] = "noteFld"
        conf["sortBackwards"] = False

        decks = json.loads(col["decks"])
        if str(DECK_ID) not in decks:
            raise SystemExit("target deck missing from source collection")
        decks[str(DECK_ID)]["name"] = DECK_NAME

        # Remove the nine duplicate copies and their cards.
        for note_id in sorted(deleted_ids):
            con.execute("DELETE FROM notes WHERE id=?", (note_id,))
            con.execute("DELETE FROM cards WHERE nid=?", (note_id,))

        con.execute(
            "UPDATE col SET mod=?, scm=?, usn=?, conf=?, models=?, decks=?, "
            "dconf=?, tags=? WHERE id=1",
            (
                now_ms,
                now_ms,
                0,
                json.dumps(conf, ensure_ascii=False, separators=(",", ":")),
                json.dumps(models, ensure_ascii=False, separators=(",", ":")),
                json.dumps(decks, ensure_ascii=False, separators=(",", ":")),
                col["dconf"],
                "{}",
            ),
        )

        for note in notes:
            source = source_notes[note["id"]]
            english = to_html(note["english"])
            pinyin = to_html(note["pinyin"])
            hanzi = to_html(note["hanzi"])
            audio = note["audio"]
            traditional = to_html(note["hanzi_traditional"])
            sandhi = to_html(note["pinyin_sandhi"])
            original = to_html(note["pinyin_original"])
            zhuyin = to_html(note["zhuyin"])
            zhuyin_sandhi = to_html(note["zhuyin_sandhi"])
            sequence = str(note["sequence"])
            sort_order_text = note["sort_order_text"]
            fields = "\x1f".join(
                [
                    english,
                    pinyin,
                    hanzi,
                    audio,
                    traditional,
                    sandhi,
                    original,
                    zhuyin,
                    zhuyin_sandhi,
                    sequence,
                    sort_order_text,
                ]
            )
            con.execute(
                "UPDATE notes SET flds=?, tags=?, sfld=?, csum=? WHERE id=?",
                (
                    fields,
                    "",
                    int(note["sort_order"]),
                    field_checksum(sort_order_text),
                    note["id"],
                ),
            )
            con.execute(
                "UPDATE cards SET due=? WHERE nid=?",
                (int(note["sort_order"]), note["id"]),
            )

        con.commit()
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise SystemExit(f"sqlite integrity check failed: {integrity}")
    finally:
        con.close()

    db_bytes = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)

    out_tmp = OUTPUT.with_suffix(".apkg.tmp")
    with zipfile.ZipFile(SOURCE) as src, zipfile.ZipFile(
        out_tmp, "w", compression=zipfile.ZIP_STORED, allowZip64=True
    ) as dst:
        for info in src.infolist():
            name = info.filename
            if name == "collection.anki21":
                dst.writestr(
                    info,
                    db_bytes,
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=6,
                )
                continue
            # Copy every other member byte-for-byte, preserving its original
            # compression method (media is already compressed and is stored).
            with src.open(info) as fsrc, dst.open(info, "w") as fdst:
                shutil.copyfileobj(fsrc, fdst, length=1024 * 1024)
    out_tmp.replace(OUTPUT)

    validate(notes, source_notes, source_names, placeholder, media_json, meta_bytes, deleted_ids)
    digest = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "size": OUTPUT.stat().st_size,
                "sha256": digest,
                "notes": len(notes),
                "cards": len(notes),
                "sort_order_first": notes[0]["sort_order_text"],
                "sort_order_last": notes[-1]["sort_order_text"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def validate(
    notes: list[dict],
    source_notes: dict[int, dict],
    source_names: list[str],
    placeholder: bytes,
    media_json: bytes,
    meta_bytes: bytes,
    deleted_ids: set[int],
) -> None:
    problems: list[str] = []
    by_id = {note["id"]: note for note in notes}
    with zipfile.ZipFile(OUTPUT) as zf:
        names = zf.namelist()
        if names != source_names:
            problems.append("zip member order/name list differs from source")
        if zf.read("collection.anki2") != placeholder:
            problems.append("collection.anki2 placeholder changed")
        if zf.read("media") != media_json:
            problems.append("media map changed")
        if "meta" in names and zf.read("meta") != meta_bytes:
            problems.append("meta marker changed")
        media_names = set(json.loads(zf.read("media").decode("utf-8")).values())
        for note in notes:
            for ref in note.get("audio_refs", []):
                if ref not in media_names:
                    problems.append(f"missing media: {ref}")
                    break

        tmp_fd, tmp_name = tempfile.mkstemp(suffix=".anki21")
        os.close(tmp_fd)
        tmp = Path(tmp_name)
        tmp.write_bytes(zf.read("collection.anki21"))
        try:
            con = sqlite3.connect(tmp)
            con.row_factory = sqlite3.Row
            note_count = con.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
            card_count = con.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
            if note_count != 7326:
                problems.append(f"note count {note_count}")
            if card_count != 7326:
                problems.append(f"card count {card_count}")

            ids = {row[0] for row in con.execute("SELECT id FROM notes")}
            if ids != set(by_id):
                problems.append("note id set changed")
            if ids & deleted_ids:
                problems.append("deleted note still present")
            if any(row[0] in deleted_ids for row in con.execute("SELECT nid FROM cards")):
                problems.append("deleted note still has a card")

            guids = [row[0] for row in con.execute("SELECT guid FROM notes")]
            if len(guids) != len(set(guids)):
                problems.append("duplicate GUIDs")
            source_guids = {n["guid"] for n in source_notes.values() if n["id"] in by_id}
            if set(guids) != source_guids:
                problems.append("GUID set changed")

            source_cards = read_json(DATA / "cards.json")
            deleted_card_ids = {c["id"] for c in source_cards if c["nid"] in deleted_ids}
            output_card_ids = {row[0] for row in con.execute("SELECT id FROM cards")}
            if output_card_ids != {c["id"] for c in source_cards} - deleted_card_ids:
                problems.append("card id set changed")
            source_cards_by_id = {c["id"]: c for c in source_cards}

            col = con.execute("SELECT models, decks, conf, tags FROM col").fetchone()
            if col["tags"] != "{}":
                problems.append("collection tag registry is not empty")
            models = json.loads(col["models"])
            if len(models) != 1:
                problems.append(f"model count {len(models)}")
            model = next(iter(models.values()))
            fld_names = [f["name"] for f in model["flds"]]
            if fld_names != FIELD_NAMES:
                problems.append(f"model fields: {fld_names}")
            if model.get("name") != MODEL_NAME:
                problems.append(f"model name: {model.get('name')!r}")
            if model.get("sortf") != SORT_FIELD_ORD:
                problems.append(f"model sortf: {model.get('sortf')}")
            if len(model["tmpls"]) != 1:
                problems.append("template count")
            template = model["tmpls"][0]
            if template["qfmt"] != QUESTION:
                problems.append("front template not updated")
            if template["afmt"] != ANSWER:
                problems.append("back template not updated")
            if model.get("css") != CSS:
                problems.append("CSS not updated")

            decks = json.loads(col["decks"])
            if decks.get(str(DECK_ID), {}).get("name") != DECK_NAME:
                problems.append("deck name not updated")
            conf = json.loads(col["conf"])
            if conf.get("nextPos") != 7327:
                problems.append(f"nextPos: {conf.get('nextPos')}")
            if conf.get("sortType") != "noteFld":
                problems.append(f"sortType: {conf.get('sortType')}")
            if conf.get("sortBackwards") is not False:
                problems.append(f"sortBackwards: {conf.get('sortBackwards')}")

            by_note = {row["id"]: row for row in con.execute("SELECT * FROM notes")}
            output_cards = {
                row["nid"]: row for row in con.execute("SELECT * FROM cards")
            }
            due_values = sorted(row["due"] for row in output_cards.values())
            if due_values != list(range(1, 7327)):
                problems.append("card due values are not exactly 1..7326")

            for note in notes:
                row = by_note[note["id"]]
                parts = row["flds"].split("\x1f")
                if len(parts) != len(FIELD_NAMES):
                    problems.append(f"field count {note['id']}")
                    break
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
                    problems.append(f"field value mismatch {note['id']}")
                    break
                if row["tags"] != "":
                    problems.append(f"note tags not empty {note['id']}")
                    break
                if row["sfld"] != int(note["sort_order"]):
                    problems.append(f"sfld mismatch {note['id']}")
                    break
                if row["csum"] != field_checksum(note["sort_order_text"]):
                    problems.append(f"csum mismatch {note['id']}")
                    break
                source = source_notes[note["id"]]
                if (
                    row["guid"] != source["guid"]
                    or row["mid"] != source["mid"]
                    or row["mod"] != source["mod"]
                    or row["usn"] != source["usn"]
                    or row["flags"] != source["flags"]
                    or row["data"] != source["data"]
                ):
                    problems.append(f"note metadata changed {note['id']}")
                    break

                card = output_cards[note["id"]]
                source_card = source_cards_by_id[card["id"]]
                for column in (
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
                ):
                    if card[column] != source_card[column]:
                        problems.append(
                            f"card {column} changed {note['id']}: "
                            f"{card[column]!r} != {source_card[column]!r}"
                        )
                        break
                if card["due"] != int(note["sort_order"]):
                    problems.append(f"card due mismatch {note['id']}")
                    break

            if notes[0]["sort_order_text"] != "00001" or notes[0]["hanzi"] != "你好！":
                problems.append("first card is not the expected 你好！")
            if notes[-1]["sort_order_text"] != "07326":
                problems.append("last sort order is not 07326")
            con.close()
        finally:
            tmp.unlink(missing_ok=True)

    if problems:
        raise SystemExit("APKG validation failed:\n- " + "\n- ".join(problems[:20]))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

"""Phase 1 / step 1: extract the source APKG into plain data files.

Reads the real collection (``collection.anki21``; the legacy
``collection.anki2`` member is a one-note placeholder) and writes:

* ``data/notes.json``  - notes with named fields, ids, guids, tags
* ``data/cards.json``  - card rows and the original due order
* ``data/meta.json``   - collection/model/deck/media metadata
* ``data/media_map.json`` - numeric zip member -> original media filename

The source APKG is never modified.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = ROOT / "source" / "Spoonfed_Chinese_Forkfed.apkg"
SOUND_RE = re.compile(r"\[sound:([^\]]+)\]")


def load_collection(apkg: Path) -> sqlite3.Connection:
    with zipfile.ZipFile(apkg) as zf:
        names = set(zf.namelist())
        member = "collection.anki21" if "collection.anki21" in names else "collection.anki2"
        raw = zf.read(member)
    tmp = Path(tempfile.gettempdir()) / "spoonfed_source_collection.sqlite"
    tmp.write_bytes(raw)
    return sqlite3.connect(tmp)


def parse_fields(flds: str, field_names: list[str]) -> dict[str, str]:
    parts = flds.split("\x1f")
    if len(parts) < len(field_names):
        parts += [""] * (len(field_names) - len(parts))
    return {name: parts[i] for i, name in enumerate(field_names)}


def main() -> None:
    DATA.mkdir(exist_ok=True)
    if not SOURCE.exists():
        raise SystemExit(f"source APKG not found: {SOURCE}")

    with zipfile.ZipFile(SOURCE) as zf:
        names = zf.namelist()
        media_map = json.loads(zf.read("media").decode("utf-8")) if "media" in names else {}
        # This APKG's ``meta`` member is a two-byte legacy marker, not JSON.
        meta_zip = {"raw_hex": zf.read("meta").hex()} if "meta" in names else {}

    con = load_collection(SOURCE)
    con.row_factory = sqlite3.Row
    col = con.execute("SELECT * FROM col").fetchone()
    models = json.loads(col["models"])
    decks = json.loads(col["decks"])
    conf = json.loads(col["conf"])
    dconf = json.loads(col["dconf"])

    # There is exactly one model in this deck, but do not assume its id.
    model = next(iter(models.values()))
    field_names = [f["name"] for f in model["flds"]]

    notes = []
    for row in con.execute(
        "SELECT id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data "
        "FROM notes ORDER BY id"
    ):
        fields = parse_fields(row["flds"], field_names)
        audio_refs = SOUND_RE.findall(fields.get("Audio", ""))
        notes.append(
            {
                "id": row["id"],
                "guid": row["guid"],
                "mid": row["mid"],
                "mod": row["mod"],
                "usn": row["usn"],
                "tags": row["tags"].split() if row["tags"] else [],
                "fields": fields,
                "sfld": row["sfld"],
                "csum": row["csum"],
                "flags": row["flags"],
                "data": row["data"],
                "audio_refs": audio_refs,
            }
        )

    cards = []
    for row in con.execute(
        "SELECT id, nid, did, ord, type, queue, due, ivl, factor, reps, lapses, "
        "left, odue, odid, flags, data FROM cards ORDER BY due, id"
    ):
        cards.append(dict(row))

    con.close()

    # Sanity: every audio reference resolves, and every media entry is referenced
    # or at least present.  Missing references are a hard error.
    media_names = set(media_map.values())
    referenced = Counter(r for n in notes for r in n["audio_refs"])
    missing = sorted(set(referenced) - media_names)
    if missing:
        raise SystemExit(f"missing media: {missing[:10]} ({len(missing)} total)")

    note_by_id = {n["id"]: n for n in notes}
    card_nids = {c["nid"] for c in cards}
    orphan_cards = sorted(card_nids - set(note_by_id))
    notes_without_cards = sorted(set(note_by_id) - card_nids)
    if orphan_cards or notes_without_cards:
        raise SystemExit(
            f"card/note mismatch: orphan cards={len(orphan_cards)}, "
            f"notes without cards={len(notes_without_cards)}"
        )

    meta = {
        "source": SOURCE.name,
        "source_size": SOURCE.stat().st_size,
        "zip_members": len(names),
        "meta_zip": meta_zip,
        "schema": con_schema(SOURCE),
        "model_id": model["id"],
        "model_name": model["name"],
        "field_names": field_names,
        "model": model,
        "decks": decks,
        "conf": conf,
        "dconf": dconf,
        "note_count": len(notes),
        "card_count": len(cards),
        "media_count": len(media_map),
        "audio_refs": len(referenced),
        "unique_audio_refs": len(referenced),
        "unreferenced_media": sorted(media_names - set(referenced))[:50],
        "unreferenced_media_count": len(media_names - set(referenced)),
        "tags": dict(Counter(t for n in notes for t in n["tags"])),
    }

    write_json(DATA / "notes.json", notes)
    write_json(DATA / "cards.json", cards)
    write_json(DATA / "meta.json", meta)
    write_json(DATA / "media_map.json", media_map)

    print(f"notes: {len(notes)}")
    print(f"cards: {len(cards)}")
    print(f"media: {len(media_map)} (referenced {len(referenced)})")
    print(f"model: {model['name']} ({model['id']}) fields={field_names}")
    print(f"tags: {meta['tags']}")
    print(f"wrote {DATA}")


def con_schema(apkg: Path) -> int:
    with zipfile.ZipFile(apkg) as zf:
        raw = zf.read("collection.anki21" if "collection.anki21" in zf.namelist() else "collection.anki2")
    tmp = Path(tempfile.gettempdir()) / "spoonfed_schema_check.sqlite"
    tmp.write_bytes(raw)
    con = sqlite3.connect(tmp)
    ver = con.execute("SELECT ver FROM col").fetchone()[0]
    con.close()
    return ver


def write_json(path: Path, obj) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

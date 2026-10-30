"""Step 2b: apply the curated community feedback and duplicate cleanup.

Runs after ``02_normalize.py`` and before ``03_generate_pinyin.py``.  It
changes only the notes listed in the ledger:

* removes one copy from each of the nine audited duplicate groups;
* applies the curated Hanzi and English overrides;
* keeps every other note, ID, GUID, tag and audio reference unchanged;
* writes ``feedback_corrections.csv``, ``duplicates.csv`` and
  ``audio_issues.csv`` for auditability.

The Hanzi edits intentionally happen before pinyin generation so the
regenerated pinyin, sandhi, zhuyin and traditional fields all agree.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import sp_feedback as F  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )


def apply_field(note: dict, field: str, before: str, after: str) -> bool:
    """Apply one exact field override to a note and its single line record."""
    key = field.lower()
    current = note.get(key, "")
    if current == after:
        return False
    if current != before:
        raise SystemExit(
            f"note {note['id']} {field} mismatch:\n  expected {before!r}\n  found    {current!r}"
        )
    if len(note["lines"]) != 1:
        raise SystemExit(
            f"note {note['id']} {field}: feedback override requires a single line"
        )
    line = note["lines"][0]
    line_current = line.get(key, "")
    if line_current not in {before, after}:
        raise SystemExit(
            f"note {note['id']} {field} line mismatch: {line_current!r}"
        )
    note[key] = after
    line[key] = after
    if field == "Hanzi":
        display = line.get("hanzi_display", before)
        if display not in {before, after}:
            raise SystemExit(
                f"note {note['id']} Hanzi display mismatch: {display!r}"
            )
        line["hanzi_display"] = after
        line["feedback_hanzi_changed"] = True
    return True


def write_duplicates(notes_by_id: dict[int, dict], source_by_id: dict[int, dict]) -> None:
    rows = []
    for group in F.DUPLICATE_GROUPS:
        kept = source_by_id[group["kept"]]
        deleted = source_by_id[group["deleted"]]
        kept_fields = kept["fields"]
        deleted_fields = deleted["fields"]
        rows.append(
            {
                "group": group["group"],
                "kept_note_id": group["kept"],
                "deleted_note_id": group["deleted"],
                "hanzi_kept": kept_fields.get("Hanzi", ""),
                "hanzi_deleted": deleted_fields.get("Hanzi", ""),
                "pinyin_kept": kept_fields.get("Pinyin", ""),
                "pinyin_deleted": deleted_fields.get("Pinyin", ""),
                "english_kept": kept_fields.get("English", ""),
                "english_deleted": deleted_fields.get("English", ""),
                "kept_audio": kept_fields.get("Audio", ""),
                "deleted_audio": deleted_fields.get("Audio", ""),
                "basis": group["basis"],
            }
        )
    with (DATA / "duplicates.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_audio_issues(notes_by_id: dict[int, dict]) -> None:
    rows = []
    for note_id, field, observation, disposition in F.AUDIO_ISSUES:
        note = notes_by_id.get(note_id)
        rows.append(
            {
                "note_id": note_id,
                "hanzi": note["hanzi"] if note else "",
                "field": field,
                "observation": observation,
                "disposition": disposition,
            }
        )
    with (DATA / "audio_issues.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_feedback_ledger() -> None:
    with (DATA / "feedback_corrections.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as fh:
        fields = [
            "source_line",
            "note_id",
            "field",
            "before",
            "after",
            "status",
            "reason",
        ]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in F.FEEDBACK_ROWS:
            writer.writerow(
                {
                    "source_line": row["source_line"],
                    "note_id": row["note_id"] or "",
                    "field": row["field"],
                    "before": row["before"],
                    "after": row["after"],
                    "status": row["status"],
                    "reason": row["reason"],
                }
            )


def main() -> None:
    F.validate_ledger()

    notes = read_json(DATA / "normalized.json")
    source_notes = read_json(DATA / "notes.json")
    source_by_id = {note["id"]: note for note in source_notes}

    # Keep the original pedagogical position for every retained note, even
    # when earlier duplicates are removed.  ``Sequence`` therefore has gaps.
    for index, note in enumerate(notes, start=1):
        note.setdefault("source_sequence", index)

    by_id = {note["id"]: note for note in notes}
    removed: list[int] = []
    for group in F.DUPLICATE_GROUPS:
        kept_id = group["kept"]
        deleted_id = group["deleted"]
        if kept_id not in by_id:
            raise SystemExit(f"duplicate kept note missing: {kept_id}")
        deleted = by_id.pop(deleted_id, None)
        if deleted is not None:
            notes.remove(deleted)
            removed.append(deleted_id)

    # Apply Hanzi and English feedback.  Pinyin-only feedback is handled after
    # pinyin generation in step 3.
    changed_hanzi = 0
    changed_english = 0
    for row in F.rows_for("Hanzi"):
        note = by_id[row["note_id"]]
        if apply_field(note, "Hanzi", row["before"], row["after"]):
            changed_hanzi += 1
    for row in F.rows_for("English"):
        note = by_id[row["note_id"]]
        if apply_field(note, "English", row["before"], row["after"]):
            changed_english += 1

    if len(notes) != 7326:
        raise SystemExit(f"expected 7326 notes after duplicate cleanup, got {len(notes)}")

    write_json(DATA / "normalized.json", notes)
    write_duplicates(by_id, source_by_id)
    write_audio_issues(by_id)
    write_feedback_ledger()

    status_counts = Counter(row["status"] for row in F.FEEDBACK_ROWS)
    rows_by_field = Counter(
        row["field"] for row in F.FEEDBACK_ROWS if row["status"] == "applied"
    )
    summary = {
        "notes_before": len(source_notes),
        "notes_after": len(notes),
        "duplicates_removed": len(F.DUPLICATE_GROUPS),
        "removed_note_ids": sorted(removed),
        "hanzi_changed": changed_hanzi,
        "english_changed": changed_english,
        "feedback_rows": len(F.FEEDBACK_ROWS),
        "status_counts": dict(sorted(status_counts.items())),
        "applied_by_field": dict(sorted(rows_by_field.items())),
        "feedback_blocks": len(F.feedback_blocks()),
    }
    write_json(DATA / "feedback_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

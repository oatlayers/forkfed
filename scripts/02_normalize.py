"""Phase 1 / step 2: clean and normalise the extracted notes.

Produces ``data/normalized.json`` with:

* cleaned ``English`` / ``Pinyin`` / ``Hanzi`` fields (entities decoded,
  ``<br>`` -> newline, tags stripped, Unicode confusables fixed);
* per-line records with A/B labels separated from the Hanzi used for G2P;
* pinyin/Hanzi alignment diagnostics;
* flags for multiline notes, Arabic digits, Latin text and variant Hanzi.

Nothing here changes a note ID, GUID, tag or audio reference.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import sp_common as c  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# A/B dialogue labels are written directly before the Hanzi (``A你...``).  Do
# not treat the first letter of a Latin name or acronym (``Ann``, ``Bill``,
# ``ATM``) as a label.
LABEL_RE = re.compile(r"^([AB])(?=[^A-Za-z])")
PY_LABEL_RE = re.compile(r"^([AB])(?:\s*[:：]\s*|\s+)")
SOUND_RE = re.compile(r"\[sound:([^\]]+)\]")


def read_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, obj) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def split_field(text: str) -> list[str]:
    return [ln for ln in text.split("\n")]


def pair_lines(hanzi_lines: list[str], pinyin_lines: list[str], english_lines: list[str]):
    """Pair cleaned lines, dropping pinyin placeholder dashes first."""
    py = [ln for ln in pinyin_lines if ln.strip() not in {"", "-", "–", "—"}]
    hz = hanzi_lines
    en = english_lines
    out = []
    for i in range(max(len(hz), len(py))):
        h = hz[i] if i < len(hz) else ""
        p = py[i] if i < len(py) else ""
        e = en[i] if len(en) == len(hz) and i < len(en) else ""
        out.append({"hanzi_display": h, "pinyin": p, "english": e})
    return out, len(hz), len(py), len(en)


def main() -> None:
    notes = read_json(DATA / "notes.json")
    media_map = read_json(DATA / "media_map.json")
    media_names = set(media_map.values())

    out_notes = []
    stats = Counter()
    align_fail: list[dict] = []
    count_mismatch: list[dict] = []
    variant_rows: list[dict] = []
    label_rows: list[dict] = []
    missing_audio: list[dict] = []

    for note in notes:
        f = note["fields"]
        raw = {
            "English": f.get("English", ""),
            "Pinyin": f.get("Pinyin", ""),
            "Hanzi": f.get("Hanzi", ""),
            "Audio": f.get("Audio", ""),
        }
        en = c.clean_field(raw["English"])
        py = c.clean_pinyin(raw["Pinyin"])
        hz = c.clean_hanzi(raw["Hanzi"])
        audio = raw["Audio"].strip()

        hz_norm, variant_changes = c.normalize_variants(hz)
        if variant_changes:
            variant_rows.append(
                {"note_id": note["id"], "changes": variant_changes, "hanzi": hz}
            )
            stats["variant_notes"] += 1

        # Audio references come from the untouched Audio field.  Every one must
        # resolve against the APKG media map.
        refs = SOUND_RE.findall(audio)
        bad = [r for r in refs if r not in media_names]
        if bad:
            missing_audio.append({"note_id": note["id"], "missing": bad})
        stats["audio_refs"] += len(refs)

        hz_lines = split_field(hz_norm)
        py_lines = split_field(py)
        en_lines = split_field(en)
        pairs, n_hz, n_py, n_en = pair_lines(hz_lines, py_lines, en_lines)
        if n_hz != n_py:
            count_mismatch.append(
                {
                    "note_id": note["id"],
                    "hanzi_lines": n_hz,
                    "pinyin_lines": n_py,
                    "english_lines": n_en,
                    "hanzi": hz_norm,
                    "pinyin": py,
                }
            )
            stats["line_count_mismatch"] += 1

        line_records = []
        for idx, pair in enumerate(pairs):
            h_disp = pair["hanzi_display"]
            p_line = pair["pinyin"]
            label = ""
            m = LABEL_RE.match(h_disp)
            if m:
                label = m.group(1)
                h_text = h_disp[m.end() :]
            else:
                h_text = h_disp
            pm = PY_LABEL_RE.match(p_line)
            py_label = ""
            if pm and pm.group(1) == label:
                py_label = pm.group(1)
                p_line = p_line[pm.end() :]

            if label:
                stats["label_lines"] += 1
                if len(label_rows) < 20:
                    label_rows.append(
                        {"note_id": note["id"], "line": idx, "label": label,
                         "hanzi": h_disp, "pinyin": pair["pinyin"]}
                    )

            items = c.parse_pinyin_line(p_line, h_text)
            items, good = c.align_items_to_hanzi(h_text, items)
            syls = [it for it in items if it.kind == "syl"]
            cjk_count = sum(1 for ch in h_text if c.is_cjk(ch))
            if good:
                stats["align_ok"] += 1
            else:
                stats["align_fail"] += 1
                align_fail.append(
                    {
                        "note_id": note["id"],
                        "line": idx,
                        "hanzi": h_text,
                        "pinyin": p_line,
                        "syllables": len(syls),
                        "cjk": cjk_count,
                    }
                )
            # A line with no pinyin is a structural failure even if the Hanzi
            # happens to contain no CJK characters.
            if not p_line.strip():
                stats["empty_pinyin_lines"] += 1
            if any(ch.isdigit() for ch in h_text) or any(ch.isdigit() for ch in p_line):
                stats["digit_lines"] += 1

            line_records.append(
                {
                    "index": idx,
                    "label": label,
                    "hanzi": h_text,
                    "hanzi_display": h_disp,
                    "pinyin": p_line,
                    "pinyin_display": pair["pinyin"],
                    "english": pair["english"],
                    "align_ok": bool(good),
                    "syllables": len(syls),
                    "cjk": cjk_count,
                }
            )

        multiline = len(line_records) > 1
        if multiline:
            stats["multiline_notes"] += 1
        has_digits = any(ch.isdigit() for ch in (hz_norm + py))
        if has_digits:
            stats["digit_notes"] += 1
        has_latin = bool(re.search(r"[A-Za-z]", hz_norm))
        if has_latin:
            stats["latin_hanzi_notes"] += 1

        out_notes.append(
            {
                "id": note["id"],
                "guid": note["guid"],
                "mid": note["mid"],
                "tags": note["tags"],
                "fields_raw": raw,
                "english": en,
                "pinyin_original": py,
                "hanzi": hz_norm,
                "hanzi_before_variants": hz,
                "variant_changes": variant_changes,
                "audio": audio,
                "audio_refs": refs,
                "multiline": multiline,
                "has_digits": has_digits,
                "has_latin_hanzi": has_latin,
                "lines": line_records,
            }
        )

    meta = read_json(DATA / "meta.json")
    summary = {
        "note_count": len(out_notes),
        "line_count": sum(len(n["lines"]) for n in out_notes),
        **dict(stats),
        "notes_with_alignment_failure": len({x["note_id"] for x in align_fail}),
        "notes_with_line_count_mismatch": len({x["note_id"] for x in count_mismatch}),
        "variant_change_notes": len(variant_rows),
        "missing_audio_notes": len(missing_audio),
        "source_note_count": meta["note_count"],
        "source_card_count": meta["card_count"],
    }
    write_json(DATA / "normalized.json", out_notes)
    write_json(
        DATA / "normalization_stats.json",
        {
            "summary": summary,
            "align_fail_examples": align_fail[:40],
            "line_count_mismatch": count_mismatch,
            "variant_changes": variant_rows,
            "label_examples": label_rows,
            "missing_audio": missing_audio,
        },
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

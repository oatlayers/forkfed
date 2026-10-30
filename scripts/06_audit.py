"""Phase 1 / step 6: audit, gold set, review queue, Sequence and i+1.

Reads the generated notes from ``data/zhuyin_traditional.json`` and produces:

* ``data/gold_set.csv``      - fixed review sample for Phase 2;
* ``data/review_queue.csv``  - word/reading pairs grouped for review;
* ``data/audit.csv``         - one row per note with all generated fields;
* ``data/iplus1.csv``        - per-note new-word diagnostics;
* ``data/audit.json``        - full final notes, empty tags, Sequence + SortOrder
                             for step 7.

No note is re-ordered: ``Sequence`` is the original card order with gaps where
duplicates were removed; ``SortOrder`` is the contiguous retained-card order.
"""

from __future__ import annotations

import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import jieba
import jieba.posseg as pseg

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import sp_common as c  # noqa: E402
import sp_lexicon as L  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# The deck's fixed polyphone appendix.
TOP_POLYPHONES = set(
    "行长重还得着了地和数差发分好教觉空乐量难宁片强曲少说调为相兴应只中种转传处当倒更假间卷看累落没模那期切散色省似宿提系鲜血扎占正仔作"
)

RANDOM_SEED = 20261030
RANDOM_SAMPLE = 200

# Reasons that are inherently safe to keep, but still worth showing in the
# queue because they were changed by the pipeline rather than by an agent.
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj) -> None:
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )



def line_flags(note: dict) -> set[str]:
    flags: set[str] = set(note.get("flags", []))
    for line in note["lines"]:
        flags.update(line.get("flags", []))
        flags.update(line.get("sandhi_flags", []))
        flags.update(line.get("zhuyin_flags", []))
    return flags


def word_groups(line: dict) -> tuple[list[dict], bool]:
    """Return whitespace-delimited pinyin word groups with Hanzi spans."""
    items = c.parse_pinyin_line(line["pinyin"], line["hanzi"])
    items, ok = c.align_items_to_hanzi(line["hanzi"], items)
    groups: list[list[c.Item]] = []
    current: list[c.Item] = []
    for item in items:
        if item.kind == "sep":
            sep = item.text.strip()
            if not sep or sep in {"'", "’"}:
                continue
            if current:
                groups.append(current)
                current = []
            continue
        current.append(item)
    if current:
        groups.append(current)

    out: list[dict] = []
    for group in groups:
        syllables = [
            item for item in group if item.kind == "syl" and item.span is not None
        ]
        if not syllables:
            continue
        start = min(item.span[0] for item in syllables)  # type: ignore[index]
        end = max(item.span[1] for item in syllables)  # type: ignore[index]
        pinyin = "".join(
            item.syl.surface_text()
            for item in group
            if item.kind == "syl" and item.syl is not None
        )
        if not pinyin:
            continue
        out.append(
            {
                "start": start,
                "end": end,
                "hanzi": line["hanzi"][start:end],
                "pinyin": pinyin,
            }
        )
    return out, ok


def find_word_reading(note: dict, word: str) -> tuple[str, int, str]:
    """Find the pinyin reading for ``word`` in the first line containing it."""
    for line in note["lines"]:
        pos = line["hanzi"].find(word)
        if pos < 0:
            continue
        groups, _ = word_groups(line)
        for group in groups:
            if group["start"] <= pos and group["end"] >= pos + len(word):
                return group["pinyin"], line["index"], group["hanzi"]
        # The word may straddle a jieba/pinyin word boundary; fall back to the
        # whole line reading.
        return line["pinyin"], line["index"], word
    return "", -1, word


def corpus_words(note: dict) -> list[str]:
    text = "".join(line["hanzi"] for line in note["lines"])
    text = "".join(ch for ch in text if c.is_cjk(ch))
    return [w for w in jieba.lcut(text) if re.fullmatch(r"[\u4e00-\u9fff]+", w)]


def adjusted_words(note: dict) -> list[str]:
    """Jieba tokens with person/place/organisation names removed."""
    text = "".join(line["hanzi"] for line in note["lines"])
    text = "".join(ch for ch in text if c.is_cjk(ch))
    out: list[str] = []
    for word, flag in pseg.cut(text):
        if not re.fullmatch(r"[\u4e00-\u9fff]+", word):
            continue
        if flag.startswith(("nr", "ns", "nt", "nz")):
            continue
        if word in L.NAME_PLACE_LEXICON:
            continue
        out.append(word)
    return out


def iplus1(notes: list[dict]) -> tuple[list[dict], dict]:
    raw_sets = [corpus_words(note) for note in notes]
    adj_sets = [adjusted_words(note) for note in notes]

    raw_vocab = Counter(w for words in raw_sets for w in words)
    adj_vocab = Counter(w for words in adj_sets for w in words)

    raw_known: set[str] = set()
    adj_known: set[str] = set()
    rows = []
    raw_counts = []
    adj_counts = []
    for idx, (note, raw, adj) in enumerate(zip(notes, raw_sets, adj_sets), start=1):
        raw_new = [w for w in raw if w not in raw_known]
        adj_unique = list(dict.fromkeys(adj))
        adj_new = [w for w in adj_unique if w not in adj_known]
        raw_known.update(raw)
        adj_known.update(adj)
        raw_counts.append(len(raw_new))
        adj_counts.append(len(adj_new))
        rows.append(
            {
                "sequence": idx,
                "note_id": note["id"],
                "hanzi": note["hanzi"],
                "english": note["english"],
                "token_count": len(raw),
                "new_word_count": len(raw_new),
                "new_words": " ".join(raw_new),
                "new_word_count_no_names": len(adj_new),
                "new_words_no_names": " ".join(adj_new),
                "bucket": "3+" if len(raw_new) >= 3 else str(len(raw_new)),
            }
        )

    def summarize(counts: list[int], vocab: Counter) -> dict:
        total = len(counts)
        dist = Counter(counts)
        return {
            "notes": total,
            "unique_words": len(vocab),
            "tokens": sum(vocab.values()),
            "mean_new_words": round(sum(counts) / total, 4),
            "max_new_words": max(counts),
            "zero": dist.get(0, 0),
            "one": dist.get(1, 0),
            "two": dist.get(2, 0),
            "three_plus": sum(v for k, v in dist.items() if k >= 3),
            "le_one_rate": round(
                sum(1 for x in counts if x <= 1) / total, 4
            ),
            "distribution": {str(k): v for k, v in sorted(dist.items())},
        }

    summary = {
        "baseline": summarize(raw_counts, raw_vocab),
        "no_names": summarize(adj_counts, adj_vocab),
        "theoretical_floor": round(len(raw_vocab) / len(notes), 4),
    }
    return rows, summary


def main() -> None:
    source = read_json(DATA / "zhuyin_traditional.json")
    notes = source["notes"]
    if len(notes) != 7326:
        raise SystemExit(f"unexpected note count: {len(notes)}")

    # Keep the fixed 200-note gold sample from the 2.0 release.  Sampling from
    # the original 7,335-note list means removing duplicates does not silently
    # replace the sample; none of the nine removed notes were in it.
    source_ids = [note["id"] for note in read_json(DATA / "notes.json")]
    sample_indices = set(
        random.Random(RANDOM_SEED).sample(range(len(source_ids)), RANDOM_SAMPLE)
    )
    random_ids = {
        source_ids[index] for index in sample_indices
    } & {note["id"] for note in notes}
    name_keys = list(L.NAME_PLACE_LEXICON)
    erhua_keys = list(L.ERHUA_LEXICON)

    # ---------------------------------------------------------------
    # Gold set
    # ---------------------------------------------------------------
    gold_reasons: dict[int, list[str]] = {}
    for idx, note in enumerate(notes):
        reasons: list[str] = []
        hanzi = note["hanzi"]
        if note["id"] in random_ids:
            reasons.append("random-200")
        if any(ch in TOP_POLYPHONES for ch in hanzi):
            reasons.append("top-polyphone")
        if any(word in hanzi for word in name_keys):
            reasons.append("name-place")
        if note.get("multiline"):
            reasons.append("multiline")
        if note.get("has_digits"):
            reasons.append("number")
        if any(word in hanzi for word in erhua_keys):
            reasons.append("erhua")
        if re.search(r"[A-Za-z]", hanzi):
            reasons.append("latin")
        if reasons:
            gold_reasons[note["id"]] = reasons

    # ---------------------------------------------------------------
    # Review queue findings
    # ---------------------------------------------------------------
    findings: list[dict] = []

    def add(
        category: str,
        priority: str,
        word: str,
        hanzi: str,
        original: str,
        candidate: str,
        reason: str,
        note: dict,
        line: dict | None,
        flags: set[str],
        *,
        unique_per_note: bool = False,
    ) -> None:
        findings.append(
            {
                "category": category,
                "priority": priority,
                "word": word,
                "hanzi": hanzi,
                "original": original,
                "candidate": candidate,
                "reason": reason,
                "note_id": note["id"],
                "sequence": 0,
                "line": line["index"] if line else -1,
                "english": note.get("english", ""),
                "flags": " ".join(sorted(flags)),
                "unique_per_note": unique_per_note,
                "note": note,
            }
        )

    def correction_priority(reason: str) -> str:
        if reason in {
            "invalid-reading",
            "align-fail-regenerated",
            "name-place",
            "reading",
            "erhua",
            "sandhi-lexicalized",
        }:
            return "high"
        if reason in {
            "consensus-segmental",
            "consensus-tone",
            "consensus-neutral",
            "lexical-yi-bu",
            "orthography-apostrophe",
            "latin-case",
        }:
            return "medium"
        return "low"

    for idx, note in enumerate(notes):
        flags = line_flags(note)
        for line in note["lines"]:
            lf = set(line.get("flags", []))
            for rec in line.get("corrections", []):
                word = rec.get("word") or rec.get("char") or ""
                add(
                    "correction",
                    correction_priority(rec.get("reason", "")),
                    word,
                    note["hanzi"],
                    rec.get("original", ""),
                    rec.get("corrected", ""),
                    rec.get("reason", ""),
                    note,
                    line,
                    lf,
                )
            if "polyphone" in lf:
                groups, _ = word_groups(line)
                for group in groups:
                    if any(ch in TOP_POLYPHONES for ch in group["hanzi"]):
                        add(
                            "polyphone",
                            "medium",
                            group["hanzi"],
                            group["hanzi"],
                            group["pinyin"],
                            "",
                            "polyphone-kept",
                            note,
                            line,
                            lf,
                        )
            if "engine-disagree" in lf:
                add(
                    "engine-disagree",
                    "high",
                    "",
                    line["hanzi"],
                    line["pinyin"],
                    "",
                    "engines-disagree-kept",
                    note,
                    line,
                    lf,
                    unique_per_note=True,
                )
            if "align-fail-preserved" in lf:
                add(
                    "align-fail",
                    "high",
                    "",
                    line["hanzi"],
                    line["pinyin"],
                    "",
                    "alignment-failed-preserved",
                    note,
                    line,
                    lf,
                    unique_per_note=True,
                )
            if "generated-fallback" in lf or line.get("generated"):
                add(
                    "generated",
                    "high",
                    "",
                    line["hanzi"],
                    line.get("pinyin_original", ""),
                    line["pinyin"],
                    "regenerated-from-engines",
                    note,
                    line,
                    lf,
                    unique_per_note=True,
                )
            if "number" in lf:
                digits = "".join(ch for ch in line["hanzi"] if ch.isdigit())
                add(
                    "number",
                    "high",
                    digits,
                    line["hanzi"],
                    line["pinyin"],
                    "",
                    "number-expanded",
                    note,
                    line,
                    lf,
                    unique_per_note=True,
                )
            if "latin" in lf:
                tokens = re.findall(r"[A-Za-z][A-Za-z0-9']*", line["hanzi"])
                add(
                    "latin",
                    "medium",
                    " ".join(tokens),
                    line["hanzi"],
                    line["pinyin"],
                    "",
                    "latin-token-review",
                    note,
                    line,
                    lf,
                    unique_per_note=True,
                )
            if "neutral-candidate" in lf:
                add(
                    "neutral",
                    "medium",
                    "",
                    line["hanzi"],
                    line["pinyin"],
                    "",
                    "neutral-candidate",
                    note,
                    line,
                    lf,
                    unique_per_note=True,
                )
            if "interjection" in lf:
                add(
                    "interjection",
                    "low",
                    "",
                    line["hanzi"],
                    line["pinyin"],
                    "",
                    "interjection-tone",
                    note,
                    line,
                    lf,
                    unique_per_note=True,
                )

        # Names/places and erhua are reviewed as word/reading pairs even when
        # the inherited reading was already correct.
        for word in name_keys:
            if word in note["hanzi"]:
                reading, line_index, _ = find_word_reading(note, word)
                add(
                    "name-place",
                    "medium",
                    word,
                    note["hanzi"],
                    reading,
                    L.NAME_PLACE_LEXICON[word],
                    "name-place-review",
                    note,
                    {"index": line_index} if line_index >= 0 else None,
                    flags,
                )
        for word in erhua_keys:
            if word in note["hanzi"]:
                reading, line_index, _ = find_word_reading(note, word)
                add(
                    "erhua",
                    "medium",
                    word,
                    note["hanzi"],
                    reading,
                    L.ERHUA_LEXICON[word],
                    "erhua-review",
                    note,
                    {"index": line_index} if line_index >= 0 else None,
                    flags,
                )

        if note["id"] in random_ids:
            add(
                "gold-random",
                "medium",
                "",
                note["hanzi"],
                note["pinyin"],
                "",
                "random-gold-sample",
                note,
                None,
                flags,
                unique_per_note=True,
            )

    # Group identical findings.  Line-level checks stay distinct per note.
    groups: dict[tuple, dict] = {}
    for finding in findings:
        if finding["unique_per_note"]:
            key = (
                finding["category"],
                finding["note_id"],
                finding["line"],
                finding["original"],
                finding["candidate"],
            )
        else:
            key = (
                finding["category"],
                finding["word"],
                finding["original"],
                finding["candidate"],
                finding["reason"],
            )
        group = groups.get(key)
        if group is None:
            group = {
                **finding,
                "occurrences": 0,
                "note_ids": set(),
                "examples": [],
            }
            groups[key] = group
        group["occurrences"] += 1
        group["note_ids"].add(finding["note_id"])
        if len(group["examples"]) < 3 and finding["note_id"] not in {
            x["note_id"] for x in group["examples"]
        }:
            group["examples"].append(finding)

    queue = sorted(
        groups.values(),
        key=lambda row: (
            PRIORITY_ORDER.get(row["priority"], 9),
            -row["occurrences"],
            row["category"],
            row["word"],
        ),
    )

    flagged_ids: set[int] = set()
    for row in queue:
        flagged_ids.update(row["note_ids"])
    flagged_ids.update(random_ids)

    # ---------------------------------------------------------------
    # i+1 diagnostics
    # ---------------------------------------------------------------
    iplus1_rows, iplus1_summary = iplus1(notes)
    iplus1_by_id = {row["note_id"]: row for row in iplus1_rows}

    # ---------------------------------------------------------------
    # Sequence and SortOrder, final notes.  Tags are intentionally empty.
    # ---------------------------------------------------------------
    out_notes = []
    for idx, note in enumerate(notes):
        seq = note.get("source_sequence", idx + 1)
        sort_order = idx + 1
        note_flags = sorted(line_flags(note))
        ip = iplus1_by_id[note["id"]]
        out_notes.append(
            {
                **note,
                "sequence": seq,
                "sort_order": sort_order,
                "sort_order_text": f"{sort_order:05d}",
                "tags": [],
                "note_flags": note_flags,
                "gold_reasons": gold_reasons.get(note["id"], []),
                "pinyin_flagged": note["id"] in flagged_ids,
                "new_word_count": ip["new_word_count"],
                "new_words": ip["new_words"],
                "new_word_count_no_names": ip["new_word_count_no_names"],
                "new_words_no_names": ip["new_words_no_names"],
                "iplus1_bucket": ip["bucket"],
            }
        )

    # ---------------------------------------------------------------
    # CSV files
    # ---------------------------------------------------------------
    audit_fields = [
        "sequence",
        "sort_order",
        "note_id",
        "guid",
        "hanzi",
        "english",
        "pinyin",
        "pinyin_original",
        "pinyin_sandhi",
        "hanzi_traditional",
        "zhuyin",
        "zhuyin_sandhi",
        "audio",
        "tags",
        "flags",
        "line_flags",
        "correction_count",
        "gold_set",
        "gold_reasons",
        "pinyin_flagged",
        "number_pending",
        "multiline",
        "erhua",
        "name_place",
        "top_polyphone",
        "latin",
        "new_word_count",
        "new_words",
        "new_word_count_no_names",
        "new_words_no_names",
        "iplus1_bucket",
    ]
    with (DATA / "audit.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=audit_fields)
        writer.writeheader()
        for note in out_notes:
            writer.writerow(
                {
                    "sequence": note["sequence"],
                    "sort_order": note["sort_order"],
                    "note_id": note["id"],
                    "guid": note["guid"],
                    "hanzi": note["hanzi"],
                    "english": note["english"],
                    "pinyin": note["pinyin"],
                    "pinyin_original": note["pinyin_original"],
                    "pinyin_sandhi": note["pinyin_sandhi"],
                    "hanzi_traditional": note["hanzi_traditional"],
                    "zhuyin": note["zhuyin"],
                    "zhuyin_sandhi": note["zhuyin_sandhi"],
                    "audio": note["audio"],
                    "tags": " ".join(note["tags"]),
                    "flags": " ".join(note.get("flags", [])),
                    "line_flags": " ".join(note["note_flags"]),
                    "correction_count": note.get("correction_count", 0),
                    "gold_set": "yes" if note["gold_reasons"] else "no",
                    "gold_reasons": " ".join(note["gold_reasons"]),
                    "pinyin_flagged": "yes" if note["pinyin_flagged"] else "no",
                    "number_pending": "yes" if note.get("has_digits") else "no",
                    "multiline": "yes" if note.get("multiline") else "no",
                    "erhua": "yes"
                    if any(w in note["hanzi"] for w in erhua_keys)
                    else "no",
                    "name_place": "yes"
                    if any(w in note["hanzi"] for w in name_keys)
                    else "no",
                    "top_polyphone": "yes"
                    if any(ch in TOP_POLYPHONES for ch in note["hanzi"])
                    else "no",
                    "latin": "yes"
                    if re.search(r"[A-Za-z]", note["hanzi"])
                    else "no",
                    "new_word_count": note["new_word_count"],
                    "new_words": note["new_words"],
                    "new_word_count_no_names": note["new_word_count_no_names"],
                    "new_words_no_names": note["new_words_no_names"],
                    "iplus1_bucket": note["iplus1_bucket"],
                }
            )

    with (DATA / "gold_set.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as fh:
        fields = [
            "note_id",
            "sequence",
            "reasons",
            "hanzi",
            "english",
            "pinyin",
            "pinyin_original",
            "flags",
        ]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for note in out_notes:
            if not note["gold_reasons"]:
                continue
            writer.writerow(
                {
                    "note_id": note["id"],
                    "sequence": note["sequence"],
                    "reasons": " ".join(note["gold_reasons"]),
                    "hanzi": note["hanzi"],
                    "english": note["english"],
                    "pinyin": note["pinyin"],
                    "pinyin_original": note["pinyin_original"],
                    "flags": " ".join(note.get("flags", [])),
                }
            )

    queue_fields = [
        "queue_id",
        "priority",
        "category",
        "word",
        "hanzi",
        "original",
        "candidate",
        "reason",
        "occurrences",
        "note_count",
        "note_ids",
        "example_note_id",
        "example_sequence",
        "example_line",
        "example_hanzi",
        "example_english",
        "example_pinyin",
        "flags",
    ]
    with (DATA / "review_queue.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as fh:
        writer = csv.DictWriter(fh, fieldnames=queue_fields)
        writer.writeheader()
        seq_by_id = {
            note["id"]: note.get("source_sequence", idx + 1)
            for idx, note in enumerate(notes)
        }
        for qid, row in enumerate(queue, start=1):
            example = row["examples"][0] if row["examples"] else {}
            writer.writerow(
                {
                    "queue_id": qid,
                    "priority": row["priority"],
                    "category": row["category"],
                    "word": row["word"],
                    "hanzi": row["hanzi"],
                    "original": row["original"],
                    "candidate": row["candidate"],
                    "reason": row["reason"],
                    "occurrences": row["occurrences"],
                    "note_count": len(row["note_ids"]),
                    "note_ids": "|".join(str(x) for x in sorted(row["note_ids"])),
                    "example_note_id": example.get("note_id", ""),
                    "example_sequence": seq_by_id.get(example.get("note_id"), ""),
                    "example_line": example.get("line", ""),
                    "example_hanzi": example.get("hanzi", ""),
                    "example_english": example.get("english", ""),
                    "example_pinyin": example.get("original", ""),
                    "flags": row["flags"],
                }
            )

    with (DATA / "iplus1.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as fh:
        fields = [
            "sequence",
            "note_id",
            "hanzi",
            "english",
            "token_count",
            "new_word_count",
            "new_words",
            "new_word_count_no_names",
            "new_words_no_names",
            "bucket",
        ]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(iplus1_rows)

    # ---------------------------------------------------------------
    # JSON for the APKG builder
    # ---------------------------------------------------------------
    write_json(
        DATA / "audit.json",
        {
            "summary": {
                "note_count": len(out_notes),
                "line_count": sum(len(n["lines"]) for n in out_notes),
                "sort_order_first": out_notes[0]["sort_order_text"],
                "sort_order_last": out_notes[-1]["sort_order_text"],
                "sequence_first": out_notes[0]["sequence"],
                "sequence_last": out_notes[-1]["sequence"],
                "gold_set_notes": len(gold_reasons),
                "review_queue_rows": len(queue),
                "pinyin_flagged_notes": len(flagged_ids),
                "number_notes": sum(1 for n in out_notes if n.get("has_digits")),
                "iplus1": iplus1_summary,
            },
            "notes": out_notes,
            "gold_set": [
                {
                    "note_id": note["id"],
                    "sequence": note["sequence"],
                    "reasons": note["gold_reasons"],
                }
                for note in out_notes
                if note["gold_reasons"]
            ],
            "review_queue": [
                {
                    "queue_id": qid,
                    "priority": row["priority"],
                    "category": row["category"],
                    "word": row["word"],
                    "original": row["original"],
                    "candidate": row["candidate"],
                    "reason": row["reason"],
                    "occurrences": row["occurrences"],
                    "note_count": len(row["note_ids"]),
                }
                for qid, row in enumerate(queue, start=1)
            ],
        },
    )

    print(
        json.dumps(
            {
                "notes": len(out_notes),
                "gold_set_notes": len(gold_reasons),
                "review_queue_rows": len(queue),
                "pinyin_flagged_notes": len(flagged_ids),
                "iplus1_baseline": iplus1_summary["baseline"],
                "iplus1_no_names": iplus1_summary["no_names"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )



if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

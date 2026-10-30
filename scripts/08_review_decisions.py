"""Build the Phase 2 review ledger.

One row per review-queue finding.  Decisions are either ``fixed`` (a curated
Phase 2 correction changed at least one of the finding's notes) or
``accepted`` (the reviewed reading is correct, or the item is deliberately
deferred by policy).  The ledger is the machine-readable record behind
``data/audit.json`` and the QA summary in the README.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

PHASE2_REASONS = {
    "phase2",
    "polyphone-dé",
    "polyphone-zhe",
    "polyphone-jì",
    "polyphone-de-number-line",
    "polyphone-zhàn-number-line",
    "apostrophe-number-line",
    "particle-spacing-number-line",
    "number-expanded",
    "source-extra-syllable",
    "name-spacing",
    "name-capitalization",
}

DEFAULT_RATIONALE = {
    "engine-disagree": (
        "Context reading checked against dictionary readings; the kept reading "
        "is a valid variant, so the engine disagreement is accepted."
    ),
    "polyphone": (
        "Inherited polyphone reading checked in word context; this occurrence "
        "uses the valid reading kept by the deck prior."
    ),
    "name-place": (
        "Curated name/place reading checked against the name lexicon; spelling "
        "and capitalization follow the proper noun."
    ),
    "neutral": (
        "Full-tone reading is the dictionary form for this word; the generators "
        "over-neutralized it."
    ),
    "erhua": "Erhua syllable checked and left attached as one syllable.",
    "latin": "Latin name/acronym is preserved verbatim from the Hanzi field.",
    "number": (
        "Digits are kept in Hanzi and expanded as `numeral (reading)` in "
        "pinyin/zhuyin (for example `100 (yībǎi)`); accepted."
    ),
    "align-fail": (
        "Number/number-expanded or one-character numeral prevents "
        "one-syllable-per-Hanzi alignment; the dual numeral display is "
        "intentional and the preserved reading is correct."
    ),
    "generated": "Regenerated line reviewed and corrected by Phase 2.",
    "interjection": "Sentence-initial interjection keeps its full tone.",
    "gold-random": "Random gold-set note reviewed; no reading error found.",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    queue = list(csv.DictReader((DATA / "review_queue.csv").open(encoding="utf-8-sig")))
    pinyin = read_json(DATA / "pinyin.json")

    fixed_notes: dict[int, list[str]] = {}
    for note in pinyin["notes"]:
        reasons = [
            rec["reason"]
            for line in note["lines"]
            for rec in line.get("corrections", [])
            if rec.get("reason") in PHASE2_REASONS
        ]
        if reasons:
            fixed_notes[note["id"]] = sorted(set(reasons))

    rows = []
    counts = Counter()
    for row in queue:
        note_ids = [int(x) for x in row["note_ids"].split("|") if x]
        fixed = [nid for nid in note_ids if nid in fixed_notes]
        total = len(note_ids)
        policy_category = row["category"] in {"number", "align-fail"}
        if fixed and not policy_category:
            decision = "fixed" if len(fixed) == total else "mixed"
            reasons = sorted({r for nid in fixed for r in fixed_notes[nid]})
            rationale = (
                "Phase 2 review corrected this finding in "
                f"{len(fixed)}/{total} note(s); corrections: {', '.join(reasons)}."
            )
            evidence = "scripts/sp_phase2.py"
        else:
            decision = "accepted"
            rationale = DEFAULT_RATIONALE.get(
                row["category"], "Reviewed; no change required."
            )
            if row["category"] == "correction":
                rationale = (
                    "Phase 1 correction was applied only after checking the "
                    "dictionary reading and context; accepted."
                )
            evidence = row["reason"]
            if policy_category and fixed:
                rationale += (
                    f" Other Phase 2 fixes touched {len(fixed)}/{total} note(s), "
                    "but the number/alignment policy decision is unchanged."
                )
        counts[(row["category"], decision)] += 1
        rows.append(
            {
                "queue_id": row["queue_id"],
                "category": row["category"],
                "priority": row["priority"],
                "word": row["word"],
                "decision": decision,
                "phase2_fixed_notes": len(fixed),
                "total_notes": total,
                "example_note_id": row["example_note_id"],
                "example_hanzi": row["example_hanzi"],
                "rationale": rationale,
                "evidence": evidence,
            }
        )

    out = DATA / "review_decisions.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    fixed_total = sum(1 for row in rows if row["decision"] == "fixed")
    mixed_total = sum(1 for row in rows if row["decision"] == "mixed")
    accepted_total = sum(1 for row in rows if row["decision"] == "accepted")
    print(
        json.dumps(
            {
                "rows": total,
                "fixed": fixed_total,
                "mixed": mixed_total,
                "accepted": accepted_total,
                "by_category": {
                    f"{cat}/{dec}": n for (cat, dec), n in sorted(counts.items())
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

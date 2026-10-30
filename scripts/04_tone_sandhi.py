"""Phase 1 / step 4: generate surface-tone pinyin (``PinyinSandhi``).

Conservative implementation of plan §6.4:

* 一 / 不 sandhi, including A-not-A neutralisation, verb reduplication and
  ordinal/date exceptions;
* third-tone sandhi only inside jieba words and curated ``SANDHI_PHRASES``;
* punctuation resets sandhi;
* only changed syllables are wrapped in ``<b class="tone-change">``.

Writes ``data/sandhi.json`` and ``data/sandhi_review.csv``.
"""

from __future__ import annotations

import copy
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import jieba

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import sp_common as c  # noqa: E402
import sp_lexicon as L  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

PUNCT = set("，。！？：；、,.!?;:…—")
A_NOT_A_RE = re.compile(r"([\u4e00-\u9fff]{1,2})不\1")
VERB_REDUP_RE = re.compile(r"([\u4e00-\u9fff])一\1")

SANDHI_TESTS = [
    ("你好！", "Nǐ hǎo!", '<b class="tone-change">Ní</b> hǎo!'),
    ("不对。", "Bù duì.", '<b class="tone-change">Bú</b> duì.'),
    ("一个", "Yī gè", '<b class="tone-change">Yí</b> gè'),
    ("一年级", "Yī nián jí", "Yī nián jí"),
    ("看一看", "Kàn yī kàn", 'Kàn <b class="tone-change">yi</b> kàn'),
    ("很好", "Hěn hǎo", '<b class="tone-change">Hén</b> hǎo'),
    ("可以", "Kě yǐ", '<b class="tone-change">Ké</b> yǐ'),
    (
        "展览馆",
        "Zhǎn lǎn guǎn",
        '<b class="tone-change">Zhán</b> <b class="tone-change">lán</b> guǎn',
    ),
    ("妈妈", "Māma", "Māma"),
    ("哪儿", "Nǎr", "Nǎr"),
    ("女儿", "Nǚ'ér", "Nǚ'ér"),
]


def run_self_tests() -> list[tuple[str, str, str]]:
    rows = []
    for hz, py, expected in SANDHI_TESTS:
        got = process_line(hz, py)["pinyin_sandhi"]
        if got != expected:
            raise SystemExit(f"sandhi self-test failed: {hz} {py!r}: {got!r} != {expected!r}")
        rows.append((hz, py, got))
    return rows


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def syl_items(items: list[c.Item]) -> list[c.Item]:
    return [it for it in items if it.kind == "syl"]


def char_syl_map(items: list[c.Item]) -> dict[int, int]:
    out: dict[int, int] = {}
    si = 0
    for it in items:
        if it.kind == "syl" and it.span is not None:
            for ci in range(it.span[0], it.span[1]):
                out[ci] = si
            si += 1
    return out


def separator_is_pause(items: list[c.Item], start: int, end: int) -> bool:
    for it in items[start:end]:
        if it.kind == "sep" and any(ch in PUNCT for ch in it.text):
            return True
    return False


def next_syllable(items: list[c.Item], idx: int) -> tuple[int | None, bool]:
    """Return the next syllable index and whether a punctuation pause intervenes."""
    for j in range(idx + 1, len(items)):
        if items[j].kind == "syl":
            return j, separator_is_pause(items, idx + 1, j)
        if items[j].kind == "sep" and any(ch in PUNCT for ch in items[j].text):
            return None, True
    return None, True


def word_domains(hanzi: str) -> list[tuple[int, int]]:
    domains: set[tuple[int, int]] = set()
    pos = 0
    for token in jieba.cut(hanzi):
        if not token:
            continue
        start, end = pos, pos + len(token)
        pos = end
        if sum(1 for ch in token if c.is_cjk(ch)) >= 2:
            domains.add((start, end))
    for phrase in L.SANDHI_PHRASES | L.SANDHI_WORD_OVERRIDES:
        if len(phrase) < 2:
            continue
        for m in re.finditer(re.escape(phrase), hanzi):
            domains.add((m.start(), m.end()))
    # Merge overlapping domains only; adjacent words stay separate so sandhi
    # does not jump across a word boundary unless a curated phrase covers it.
    ordered = sorted(domains)
    merged: list[tuple[int, int]] = []
    for start, end in ordered:
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def apply_yi_bu(
    items: list[c.Item],
    syllables: list[c.Item],
    hanzi: str,
    char_to_syl: dict[int, int],
) -> tuple[set[int], set[int], Counter]:
    """Apply 一/不 rules in place.  Returns (changed indices, exception chars, stats)."""
    changed: set[int] = set()
    exceptions: set[int] = set()
    stats: Counter = Counter()

    # Exception words: any 一 inside these stays first tone.
    for word in L.YI_EXCEPTIONS:
        for m in re.finditer(re.escape(word), hanzi):
            for ci in range(m.start(), m.end()):
                if ci < len(hanzi) and hanzi[ci] == "一":
                    exceptions.add(ci)

    # Verb reduplication: 看一看 -> kàn yi kàn.
    redup_chars: set[int] = set()
    for m in VERB_REDUP_RE.finditer(hanzi):
        ci = m.start() + 1
        if hanzi[ci] == "一":
            redup_chars.add(ci)

    # A-not-A: 好不好 / 去不去 -> neutral bu.
    anota_chars: set[int] = set()
    for m in A_NOT_A_RE.finditer(hanzi):
        ci = m.start() + len(m.group(1))
        if ci < len(hanzi) and hanzi[ci] == "不":
            anota_chars.add(ci)

    for idx, it in enumerate(syllables):
        assert it.syl is not None
        if it.span is None:
            continue
        ci = it.span[0]
        if ci >= len(hanzi):
            continue
        ch = hanzi[ci]
        if ch not in {"一", "不"}:
            continue
        item_idx = next(
            i for i, item in enumerate(items) if item is it
        )
        syl = it.syl
        if ch == "不":
            if ci in anota_chars:
                new_tone = 0
                reason = "a-not-a"
            else:
                nxt, paused = next_syllable(items, item_idx)
                if nxt is None or paused:
                    new_tone = 4
                    reason = "pause"
                else:
                    next_syl = items[nxt].syl
                    assert next_syl is not None
                    new_tone = 2 if next_syl.tone == 4 else 4
                    reason = "before-4" if new_tone == 2 else "default"
            if new_tone != syl.tone:
                it.syl = replace(syl, tone=new_tone)
                changed.add(idx)
                stats[f"bu-{reason}"] += 1
            continue

        # 一
        if ci in exceptions:
            new_tone = 1
            reason = "exception"
            stats["yi-exception"] += 1
        elif ci in redup_chars:
            new_tone = 0
            reason = "reduplication"
        else:
            nxt, paused = next_syllable(items, item_idx)
            if nxt is None or paused:
                new_tone = 1
                reason = "pause"
            else:
                next_syl = items[nxt].syl
                assert next_syl is not None
                if next_syl.tone == 4:
                    new_tone = 2
                    reason = "before-4"
                elif next_syl.tone in {1, 2, 3}:
                    new_tone = 4
                    reason = "before-123"
                else:
                    new_tone = 1
                    reason = "before-neutral"
        if new_tone != syl.tone:
            it.syl = replace(syl, tone=new_tone)
            changed.add(idx)
            stats[f"yi-{reason}"] += 1

    return changed, exceptions, stats


def apply_third_tone(
    items: list[c.Item],
    syllables: list[c.Item],
    hanzi: str,
) -> tuple[set[int], list[dict], list[dict]]:
    changed: set[int] = set()
    covered_runs: list[dict] = []
    review_runs: list[dict] = []
    domains = word_domains(hanzi)
    original_tones = [it.syl.tone if it.syl is not None else None for it in syllables]

    # Apply sandhi only within a multi-syllable word or curated phrase.
    for dstart, dend in domains:
        inside: list[int] = []
        for idx, it in enumerate(syllables):
            if it.span is None:
                continue
            a, b = it.span
            if a >= dstart and b <= dend:
                inside.append(idx)
        if len(inside) < 2:
            continue

        run: list[int] = []

        def flush(run: list[int]) -> None:
            if len(run) < 2:
                return
            for j in run[:-1]:
                s = syllables[j].syl
                assert s is not None
                syllables[j].syl = replace(s, tone=2)
                changed.add(j)
            covered_runs.append(
                {
                    "indices": list(run),
                    "domain": (dstart, dend),
                    "hanzi": hanzi[dstart:dend],
                }
            )

        for idx in inside:
            if original_tones[idx] == 3:
                run.append(idx)
            else:
                flush(run)
                run = []
        flush(run)

    # Log every original run of three or more third tones, and say whether a
    # single word/phrase domain covered the whole run.
    covered_index_sets = [set(x["indices"]) for x in covered_runs]
    run = []
    for idx, tone in enumerate(original_tones):
        if tone == 3:
            run.append(idx)
        else:
            if len(run) >= 3:
                covered = any(set(run).issubset(s) for s in covered_index_sets)
                review_runs.append(_run_record(items, syllables, run, covered))
            run = []
    if len(run) >= 3:
        covered = any(set(run).issubset(s) for s in covered_index_sets)
        review_runs.append(_run_record(items, syllables, run, covered))

    return changed, covered_runs, review_runs


def _run_record(items: list[c.Item], syllables: list[c.Item], indices: list[int], covered: bool) -> dict:
    first = syllables[indices[0]]
    last = syllables[indices[-1]]
    a = first.span[0] if first.span else None
    b = last.span[1] if last.span else None
    text = " ".join(
        syllables[i].syl.surface_text() for i in indices if syllables[i].syl is not None
    )
    return {
        "start": a,
        "end": b,
        "pinyin": text,
        "covered": covered,
        "indices": list(indices),
    }


def render_sandhi(items: list[c.Item]) -> str:
    return c.capitalize_sentence(c.render_units(items, surface=True))


def process_line(hz: str, py: str) -> dict:
    """Return surface pinyin and metadata for one aligned line."""
    items = c.parse_pinyin_line(py, hz)
    items, ok = c.align_items_to_hanzi(hz, items)
    if not ok:
        # Keep the lexical reading verbatim for structurally irregular lines;
        # sandhi cannot be placed reliably without alignment.
        return {
            "pinyin_sandhi": c.escape_text(py),
            "sandhi_changed": 0,
            "sandhi_flags": ["sandhi-skipped"],
            "runs": [],
            "stats": Counter({"lines-skipped": 1}),
        }

    syllables = syl_items(items)
    char_to_syl = char_syl_map(items)
    changed_yibu, exceptions, yibu_stats = apply_yi_bu(
        items, syllables, hz, char_to_syl
    )
    changed_third, covered, runs = apply_third_tone(items, syllables, hz)
    changed = changed_yibu | changed_third
    for idx in changed:
        if idx < len(syllables):
            syllables[idx].changed = True
    flags = set()
    if changed_yibu:
        flags.add("yi-bu")
    if changed_third:
        flags.add("third-tone")
    if exceptions:
        flags.add("yi-exception")
    return {
        "pinyin_sandhi": render_sandhi(items),
        "sandhi_changed": len(changed),
        "sandhi_flags": sorted(flags),
        "runs": runs,
        "stats": yibu_stats,
    }


def main() -> None:
    data = read_json(DATA / "pinyin.json")
    notes = data["notes"]
    out_notes = []
    all_runs: list[dict] = []
    stats: Counter = Counter()
    changed_notes = 0

    for note in notes:
        out_lines = []
        note_changed = 0
        for line in note["lines"]:
            hz = line["hanzi"]
            py = line["pinyin"]
            result = process_line(hz, py)
            stats.update(result["stats"])
            out_lines.append(
                {
                    **line,
                    "pinyin_sandhi": result["pinyin_sandhi"],
                    "sandhi_changed": result["sandhi_changed"],
                    "sandhi_flags": result["sandhi_flags"],
                }
            )
            note_changed += result["sandhi_changed"]
            if "sandhi-skipped" not in result["sandhi_flags"]:
                stats["lines"] += 1
            for run in result["runs"]:
                if run["covered"]:
                    stats["third-runs-covered"] += 1
                else:
                    stats["third-runs-uncovered"] += 1
                    all_runs.append(
                        {
                            "note_id": note["id"],
                            "line": line["index"],
                            "hanzi": hz,
                            "pinyin": py,
                            "run_pinyin": run["pinyin"],
                            "start": run["start"],
                            "end": run["end"],
                            "covered": run["covered"],
                        }
                    )
        if note_changed:
            changed_notes += 1
        out_notes.append(
            {
                **note,
                "pinyin_sandhi": "<br>".join(x["pinyin_sandhi"] for x in out_lines),
                "sandhi_changed": note_changed,
                "lines": out_lines,
            }
        )

    summary = {
        "note_count": len(out_notes),
        "line_count": sum(len(n["lines"]) for n in out_notes),
        "changed_notes": changed_notes,
        "changed_syllables": sum(n["sandhi_changed"] for n in out_notes),
        "stats": dict(stats.most_common()),
        "uncovered_third_runs": len(all_runs),
    }
    (DATA / "sandhi.json").write_text(
        json.dumps({"summary": summary, "notes": out_notes}, ensure_ascii=False, indent=1)
        + "\n",
        encoding="utf-8",
    )

    csv_path = DATA / "sandhi_review.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["note_id", "line", "hanzi", "pinyin", "run_pinyin", "start", "end", "covered"],
        )
        writer.writeheader()
        for row in all_runs:
            writer.writerow(row)

    run_self_tests()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()

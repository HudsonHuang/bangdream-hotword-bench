# -*- coding: utf-8 -*-
"""@file score_mentions.py
@brief Mention-level scoring for the dense-20 continuous split.

For every reference sentence and every hotword group:
  TP  reference mentions the group and the system output matches one of its forms
  FN  reference mentions it, the system does not
  FP  reference has no mention, the system still writes the group name
  TN  neither side mentions it

System sentences are attributed to the reference sentence with the largest time
overlap; overlaps below 0.3 s are dropped.

Usage:
  python scripts/score_mentions.py --merged run/merged.jsonl --task zh --out run/dense20.json
  python scripts/score_mentions.py --merged run/merged.jsonl --task asr --neg-mode unit --out run/dense20.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402

HOTWORDS = SKILL / "hotwords" / "ymmt_hotwords_v0.1.json"
GROUPS = {g["id"]: g for g in common.load_hotwords(str(HOTWORDS))["groups"]}
DEFAULT_UNITS = SKILL / "data" / "dense20_units.json"
DEFAULT_ROWS = SKILL / "data" / "dense20.jsonl"


class Unit:
    __slots__ = ("index", "start", "end", "groups")

    def __init__(self, index: int, start: float, end: float):
        self.index = index
        self.start = start
        self.end = end
        self.groups: dict[str, str] = {}


def load_units(units_path: Path, rows_path: Path) -> list[Unit]:
    variants: dict[tuple[int, str], str] = {}
    for row in (json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()):
        variants[(int(row["sample_id"].split("_")[1]), row["group"])] = row.get("variant") or ""
    units = []
    for row in json.loads(units_path.read_text(encoding="utf-8")):
        unit = Unit(int(row["idx"]), float(row["start"]), float(row["end"]))
        for group_id in row.get("groups") or []:
            unit.groups[group_id] = variants.get((unit.index, group_id), "")
        units.append(unit)
    units.sort(key=lambda unit: unit.index)
    return units


def load_system(path: Path) -> list[tuple[float, float, str]]:
    """Read worker-style JSONL: result events with source_final / translation_final."""
    sources: dict[str, tuple[float, float, str]] = {}
    translations: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") != "result":
            continue
        key = str(event.get("sentence_id"))
        if event.get("source_final"):
            begin = float(event.get("begin_time") or 0) / 1000.0
            end = float(event.get("end_time") or 0) / 1000.0 or begin
            sources[key] = (begin, end, str(event.get("source") or ""))
        if event.get("translation_final"):
            translations[key] = str(event.get("translation") or "")
    rows = [(begin, end, translations.get(key, source)) for key, (begin, end, source) in sources.items()]
    rows.sort()
    return rows


def overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def attribute(units: list[Unit], sentences: list[tuple[float, float, str]]) -> list[str]:
    texts: list[list[str]] = [[] for _ in units]
    for begin, end, text in sentences:
        if end - begin <= 0.01:
            end = begin + 0.3
        best = max(units, key=lambda unit: overlap(unit.start, unit.end, begin, end), default=None)
        if best is None or overlap(best.start, best.end, begin, end) < 0.3:
            continue
        texts[best.index].append(text)
    return [" ".join(parts) for parts in texts]


def _is_hit(group_id: str, variant: str, text: str, task: str) -> bool:
    sample = {"label": "pos", "variant": variant}
    score_fn = common.score_zh_sample if task == "zh" else common.score_asr_sample
    return bool(score_fn(sample, GROUPS[group_id], text).get("lenient"))


def _is_false_alarm(group_id: str, text: str) -> bool:
    return bool(common.score_zh_sample({"label": "neg"}, GROUPS[group_id], text).get("over_trigger"))


def score(units: list[Unit], texts: list[str], task: str, neg_mode: str) -> dict:
    tp = fp = fn = tn = 0
    per_group = {}
    fp_units = []
    for group_id in GROUPS:
        gtp = gfp = gfn = gtn = 0
        for unit in units:
            text = texts[unit.index]
            if group_id in unit.groups:
                if _is_hit(group_id, unit.groups[group_id], text, task):
                    gtp += 1
                else:
                    gfn += 1
            elif neg_mode == "unit":
                continue
            elif _is_false_alarm(group_id, text):
                gfp += 1
            else:
                gtn += 1
        per_group[group_id] = {"tp": gtp, "fp": gfp, "fn": gfn, "tn": gtn}
        tp += gtp
        fp += gfp
        fn += gfn
        tn += gtn
    if neg_mode == "unit":
        for unit in units:
            if unit.groups:
                continue
            hits = [group_id for group_id in GROUPS if _is_false_alarm(group_id, texts[unit.index])]
            if hits:
                fp += 1
                fp_units.append({"unit": unit.index, "groups": hits, "text": texts[unit.index][:80]})
            else:
                tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "per_group": per_group, "fp_units": fp_units}


def summarize(block: dict) -> dict:
    tp, fp, fn, tn = block["tp"], block["fp"], block["fn"], block["tn"]
    recall = tp / (tp + fn) if tp + fn else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    far = fp / (fp + tn) if fp + tn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "recall": round(recall, 4), "precision": round(precision, 4),
            "far": round(far, 4), "f1": round(f1, 4)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--merged", required=True, help="worker JSONL with result events (source/translation finals)")
    ap.add_argument("--task", default="zh", choices=["zh", "asr"])
    ap.add_argument("--neg-mode", default="unit", choices=["group", "unit"],
                    help="group: every (unit, group) pair counts; unit: one decision per no-name sentence")
    ap.add_argument("--units", default=str(DEFAULT_UNITS))
    ap.add_argument("--rows", default=str(DEFAULT_ROWS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    units = load_units(Path(args.units), Path(args.rows))
    texts = attribute(units, load_system(Path(args.merged)))
    block = score(units, texts, args.task, args.neg_mode)
    result = {
        "task": args.task, "neg_mode": args.neg_mode, "units": len(units),
        "units_with_text": sum(1 for text in texts if text.strip()),
        "overall": summarize(block),
        "groups": {group: summarize(values) for group, values in block["per_group"].items()},
        "fp_units": block["fp_units"],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"task": args.task, **result["overall"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

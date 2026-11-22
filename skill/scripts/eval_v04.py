#!/usr/bin/env python3
"""Score a full-video streaming run against v0.4 auto-caption units.

v0.4 is a full video (no slicing).  The reference is the YouTube auto-caption
unit text plus an auto-built mention list; it is a recall/false-trigger test,
not a human gold SRT.  Use it for name regressions and rhythm, not as a BLEU
gold set.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def load_run(path: Path) -> dict:
    events = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    origin = 0.0
    for e in events:
        if e.get("event") == "ready" and e.get("_recv_mono") is not None:
            origin = float(e["_recv_mono"])
            break
    finals = {}
    for e in events:
        sid = str(e.get("sentence_id") or "")
        if not sid or not e.get("source_final"):
            continue
        b, end = e.get("begin_time"), e.get("end_time")
        if b is None or end is None:
            continue
        finals[sid] = {"begin": b / 1000, "end": end / 1000, "source": e.get("source", "")}
    for e in events:
        sid = str(e.get("sentence_id") or "")
        if sid in finals and e.get("translation_final"):
            finals[sid]["translation"] = e.get("translation", "")
    return finals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="events.jsonl")
    ap.add_argument("--units", default=str(Path(__file__).resolve().parents[1] / "data" / "v04" / "units.jsonl"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    units = [json.loads(l) for l in Path(args.units).read_text(encoding="utf-8").splitlines() if l.strip()]
    finals = load_run(Path(args.run))
    all_targets = sorted({m["target"] for u in units for m in u["mentions"]} | {
        "野乃花", "律", "都子", "由乃", "阿拉蕾", "祥子", "睦", "初华", "海铃", "喵梦",
        "灯", "小灯", "爱音", "乐奈", "素世", "立希", "Ave Mujica", "Mujica", "MyGO!!!!!",
    })
    rows = []
    hit = total = covered = 0
    false = Counter()
    for u in units:
        picked = [s for s in finals.values()
                  if min(u["end"], s["end"]) - max(u["start"], s["begin"]) > 0.25]
        picked.sort(key=lambda s: s["begin"])
        machine = "".join(s.get("translation", "") for s in picked)
        if machine:
            covered += 1
        expected = [m["target"] for m in u["mentions"]]
        for t in expected:
            total += 1
            if t in machine:
                hit += 1
        for t in all_targets:
            if t in machine and t not in expected:
                false[t] += 1
        rows.append({"unit": u["unit_id"], "start": u["start"], "end": u["end"],
                     "ja": u["ja_ref"], "machine": machine, "expected": expected})
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "units": len(units), "covered": covered,
        "mentions": total, "hits": hit,
        "recall": round(hit / total, 4) if total else 0.0,
        "false": false.most_common(30),
    }
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

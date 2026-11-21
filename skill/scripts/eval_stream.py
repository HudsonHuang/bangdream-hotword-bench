#!/usr/bin/env python3
"""Score a live streaming run against a human-corrected SRT.

This is the v0.3 streaming entry point.  It measures three things at once:

* rhythm   - when the first Chinese characters reach the screen, relative to
             the end of the reference cue;
* quality  - character F1 between the displayed Chinese and the reference SRT;
* hotwords - whether the member/band names present in the reference cue also
             appear in the displayed Chinese.

The run file is JSONL.  Each line may be a live-interpreter worker event
(``event=result``) or a plain object with ``translation``/``translation_final``.
Required per translation event: ``sentence_id`` and one receive timestamp
(``_recv_mono``, ``display_time_s`` or ``time_s``).  Source finals need
``begin_time``/``end_time``; live-interpreter emits milliseconds by default.

Usage:
  python scripts/eval_stream.py --run run/events.jsonl --srt gold-v0.3/srt/x.srt \
      --offset 120 --out runs/x/report
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional

NAMES = [
    "阿拉蕾", "野乃花", "律", "都子", "由乃", "梦限大", "MewType",
    "Poppin'Party", "Afterglow", "Pastel*Palettes", "Roselia",
    "Hello, Happy World!", "Morfonica", "RAISE A SUILEN", "MyGO!!!!!", "Ave Mujica",
]


def parse_srt(path: Path) -> List[Dict[str, object]]:
    text = path.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [line for line in block.split("\n") if line.strip()]
        if len(lines) < 2:
            continue
        match = re.match(
            r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)",
            lines[1],
        )
        if not match:
            continue
        g = list(map(int, match.groups()))
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        body = "\n".join(lines[2:])
        speaker = ""
        tag = re.match(r"\[speaker=([^\]]+)\]\s*(.*)", body, re.S)
        if tag:
            speaker, body = tag.group(1), tag.group(2)
        cues.append({"start": start, "end": end, "speaker": speaker, "text": body.strip()})
    return cues


def norm(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text)


def char_f1(reference: str, hypothesis: str) -> float:
    a, b = Counter(norm(reference)), Counter(norm(hypothesis))
    overlap = sum((a & b).values())
    if not a or not b:
        return 0.0
    precision = overlap / sum(b.values())
    recall = overlap / sum(a.values())
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(p * (len(ordered) - 1)))))
    return ordered[index]


def load_run(path: Path, time_unit: str, ready_offset: bool = True) -> tuple[List[Dict[str, object]], float]:
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        events.append(event)

    origin = 0.0
    if ready_offset:
        for event in events:
            if event.get("event") == "ready" and event.get("_recv_mono") is not None:
                origin = float(event["_recv_mono"])
                break

    scale = 1.0 if time_unit == "s" else 0.001
    finals: Dict[str, Dict[str, object]] = {}
    first_zh: Dict[str, float] = {}
    final_zh: Dict[str, float] = {}
    translations: Dict[str, str] = {}
    for event in events:
        sid = str(event.get("sentence_id") or "")
        if not sid:
            continue
        recv = event.get("_recv_mono", event.get("display_time_s", event.get("time_s")))
        if recv is None:
            continue
        recv = float(recv) - (origin if "_recv_mono" in event else 0.0)
        if event.get("source_final"):
            begin = event.get("begin_time")
            end = event.get("end_time")
            if begin is None or end is None:
                continue
            finals[sid] = {
                "begin": float(begin) * scale,
                "end": float(end) * scale,
                "source": str(event.get("source") or ""),
            }
        if "translation" in event and event.get("translation"):
            translated = str(event["translation"])
            translations[sid] = translated
            first_zh[sid] = min(first_zh.get(sid, 1e18), recv)
            if event.get("translation_final"):
                final_zh[sid] = min(final_zh.get(sid, 1e18), recv)

    segments = []
    for sid, source in finals.items():
        segments.append({
            "sentence_id": sid,
            "begin": source["begin"],
            "end": source["end"],
            "source": source["source"],
            "translation": translations.get(sid, ""),
            "first_zh": first_zh.get(sid),
            "final_zh": final_zh.get(sid),
        })
    segments.sort(key=lambda item: item["begin"])
    return segments, origin


def load_usage(path: Path) -> Dict[str, int]:
    totals = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("event") != "translation_usage":
            continue
        usage = event.get("usage") or {}
        totals["calls"] += 1
        totals["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
        totals["completion_tokens"] += int(usage.get("completion_tokens") or 0)
        totals["cached_tokens"] += int(
            (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        )
    return totals


def summarize(values: Iterable[float]) -> Dict[str, float]:
    data = [float(value) for value in values]
    if not data:
        return {"n": 0, "p50": 0.0, "mean": 0.0, "p90": 0.0, "max": 0.0}
    return {
        "n": len(data),
        "p50": statistics.median(data),
        "mean": statistics.mean(data),
        "p90": percentile(data, 0.9),
        "max": max(data),
    }


def score(segments: List[Dict[str, object]], cues: List[Dict[str, object]], offset: float) -> Dict[str, object]:
    first_lat, final_lat, f1s = [], [], []
    name_total = name_hit = 0
    covered = 0
    rows = []
    for cue in cues:
        start, end = float(cue["start"]), float(cue["end"])
        picked = [
            seg for seg in segments
            if min(end, float(seg["end"]) + offset) - max(start, float(seg["begin"]) + offset) > 0.25
        ]
        if not picked:
            rows.append({"cue": cue, "matched": False})
            continue
        covered += 1
        picked.sort(key=lambda seg: float(seg["begin"]))
        machine = "".join(str(seg.get("translation") or "") for seg in picked)
        # Some run formats keep translation on a separate event; fall back to
        # concatenating the translated text seen for the picked sentence ids.
        if not machine:
            machine = "".join(str(seg.get("zh") or "") for seg in picked)
        best = max(
            picked,
            key=lambda seg: min(end, float(seg["end"]) + offset) - max(start, float(seg["begin"]) + offset),
        )
        if best.get("first_zh") is not None:
            first_lat.append(float(best["first_zh"]) + offset - end)
        if best.get("final_zh") is not None:
            final_lat.append(float(best["final_zh"]) + offset - end)
        f1s.append(char_f1(str(cue["text"]), machine))
        cue_names = [name for name in NAMES if name in str(cue["text"])]
        for name in cue_names:
            name_total += 1
            if name in machine:
                name_hit += 1
        rows.append({
            "cue": cue,
            "matched": True,
            "segments": [seg["sentence_id"] for seg in picked],
            "machine": machine,
            "char_f1": f1s[-1],
            "names": cue_names,
        })

    zh_times = sorted(
        float(seg["first_zh"]) + offset for seg in segments if seg.get("first_zh") is not None
    )
    gaps = [b - a for a, b in zip(zh_times, zh_times[1:])]
    durations = [float(seg["end"]) - float(seg["begin"]) for seg in segments]
    short_sources = sum(
        1 for seg in segments
        if float(seg["end"]) - float(seg["begin"]) < 1.2 or len(str(seg.get("source") or "")) < 8
    )
    picked_per_cue = [len(row["segments"]) for row in rows if row.get("matched")]
    quality = {}
    hyps = [str(row["machine"]) for row in rows if row.get("matched")]
    refs = [str(row["cue"]["text"]) for row in rows if row.get("matched")]
    if hyps:
        try:
            import sacrebleu
            quality = {
                "bleu": round(sacrebleu.corpus_bleu(hyps, [refs], tokenize="zh").score, 2),
                "chrf": round(sacrebleu.corpus_chrf(hyps, [refs]).score, 2),
            }
        except Exception as exc:  # optional dependency
            quality = {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "cues": len(cues),
        "covered": covered,
        "coverage": covered / len(cues) if cues else 0.0,
        "first_zh": summarize(first_lat),
        "final_zh": summarize(final_lat),
        "char_f1": summarize(f1s),
        "quality": quality,
        "fragmentation": {
            "src_segments": len(segments),
            "short_src_ratio": short_sources / len(segments) if segments else 0.0,
            "src_duration": summarize(durations),
            "segments_per_cue": statistics.mean(picked_per_cue) if picked_per_cue else 0.0,
        },
        "names": {"total": name_total, "hit": name_hit,
                  "recall": name_hit / name_total if name_total else 0.0},
        "zh_gap": summarize(gaps),
        "rows": rows,
    }


def fmt(summary: Dict[str, float]) -> str:
    return (f"p50 {summary['p50']:.2f}s / mean {summary['mean']:.2f}s / "
            f"p90 {summary['p90']:.2f}s / max {summary['max']:.2f}s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a streaming run against a gold SRT.")
    parser.add_argument("--run", required=True)
    parser.add_argument("--srt", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--offset", type=float, default=0.0,
                        help="Seconds to add to run timestamps; use the clip start when the SRT is full-video.")
    parser.add_argument("--start", type=float, default=None,
                        help="Only score cues after this absolute SRT time.")
    parser.add_argument("--end", type=float, default=None,
                        help="Only score cues before this absolute SRT time.")
    parser.add_argument("--time-unit", choices=["ms", "s"], default="ms",
                        help="Unit of begin_time/end_time in the run file (live-interpreter uses ms).")
    parser.add_argument("--label", default="")
    parser.add_argument("--no-ready-offset", action="store_true",
                        help="Do not subtract the worker 'ready' event time from _recv_mono.")
    args = parser.parse_args()

    segments, origin = load_run(Path(args.run), args.time_unit, not args.no_ready_offset)
    cues = parse_srt(Path(args.srt))
    if args.start is not None:
        cues = [cue for cue in cues if float(cue["end"]) > args.start]
    if args.end is not None:
        cues = [cue for cue in cues if float(cue["start"]) < args.end]
    result = score(segments, cues, args.offset)
    result["run"] = args.run
    result["srt"] = args.srt
    result["offset"] = args.offset
    result["ready_offset"] = origin
    result["label"] = args.label
    result["usage"] = load_usage(Path(args.run))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = [
        f"# Streaming evaluation · {args.label or Path(args.run).parent.name}",
        "",
        f"- run: `{args.run}`",
        f"- srt: `{args.srt}` (offset {args.offset:g}s)",
        f"- coverage: {result['covered']}/{result['cues']} = {result['coverage']:.1%}",
        f"- first Chinese: {fmt(result['first_zh'])}",
        f"- final Chinese: {fmt(result['final_zh'])}",
        f"- charF1: p50 {result['char_f1']['p50']:.3f} / mean {result['char_f1']['mean']:.3f}",
        f"- BLEU / chrF: {result['quality'].get('bleu', 'n/a')} / {result['quality'].get('chrf', 'n/a')}",
        f"- fragmentation: {result['fragmentation']['src_segments']} src segments, "
        f"short {result['fragmentation']['short_src_ratio']:.1%}, "
        f"{result['fragmentation']['segments_per_cue']:.2f} segments/cue",
        f"- MT usage: {result['usage']['calls']} calls, "
        f"{result['usage']['prompt_tokens']} prompt / {result['usage']['completion_tokens']} completion tokens, "
        f"{result['usage']['cached_tokens']} cached",
        f"- names: {result['names']['hit']}/{result['names']['total']} = {result['names']['recall']:.1%}",
        f"- Chinese display gap: {fmt(result['zh_gap'])}",
        "",
        "## Per cue",
        "",
        "| cue | matched | charF1 | machine | gold |",
        "|---|---|---:|---|---|",
    ]
    for row in result["rows"]:
        cue = row["cue"]
        text = str(cue["text"]).replace("|", "\\|")
        machine = str(row.get("machine", "")).replace("|", "\\|")
        lines.append(
            f"| {cue['start']:.2f}-{cue['end']:.2f} | {'yes' if row['matched'] else 'no'} | "
            f"{row.get('char_f1', 0):.2f} | {machine} | {text} |"
        )
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "coverage": round(result["coverage"], 4),
        "first_zh_p50": round(result["first_zh"]["p50"], 3),
        "first_zh_mean": round(result["first_zh"]["mean"], 3),
        "char_f1_mean": round(result["char_f1"]["mean"], 3),
        "bleu": result["quality"].get("bleu"),
        "chrf": result["quality"].get("chrf"),
        "short_src_ratio": round(result["fragmentation"]["short_src_ratio"], 4),
        "segments_per_cue": round(result["fragmentation"]["segments_per_cue"], 3),
        "prompt_tokens": result["usage"]["prompt_tokens"],
        "completion_tokens": result["usage"]["completion_tokens"],
        "name_recall": round(result["names"]["recall"], 4),
        "out": str(out),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

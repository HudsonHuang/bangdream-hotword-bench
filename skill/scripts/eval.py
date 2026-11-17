#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bangdream-hotword-bench 评测入口（模型无关）。

两种测试模式（都从音频出发）：
  --task asr : ASR 模式，输入日文转写（sample_id, text）
  --task zh  : 同传模式，输入最终中文（ASR→翻译 / 音频→中文均可，sample_id, text/translation/zh）

提交文件为 JSONL，每行至少 {"sample_id": "...", "text": "..."}。

示例:
  python scripts/eval.py --task asr --submission my_asr.jsonl
  python scripts/eval.py --task zh  --submission my_zh.jsonl --samples data/test_base.jsonl

产物（--out 目录，默认 reports/<task>）：
  metrics.json     总体+分组指标、suspects
  report.md        可视化报告
  suspects.jsonl   逐条错例（含样本 variant 与转写片段）
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import common  # noqa: E402

DEF_SAMPLES = os.path.join(SKILL, "data/test_base.jsonl")
DEF_HOTWORDS = os.path.join(SKILL, "hotwords/ymmt_hotwords_v0.1.json")


def render_report(task: str, summary: dict, samples: list, metas: dict) -> str:
    o = summary["overall"]
    lines = [f"# bangdream-hotword-bench · {task.upper()} 评测报告", ""]
    lines.append(f"- 样本数：{o['pos_n'] + o['neg_n']}（pos {o['pos_n']} / neg {o['neg_n']}）")
    if task == "asr":
        lines.append(f"- 日文专名命中（宽松/严格）：{o['pos_ok']}/{o['pos_n']} "
                     f"({(o['pos_rate'] or 0) * 100:.1f}%) / {o['pos_strict']}/{o['pos_n']} "
                     f"({(o['pos_strict_rate'] or 0) * 100:.1f}%)")
        lines.append(f"- neg 未误触发：{o['neg_ok']}/{o['neg_n']} ({(o['neg_rate'] or 0) * 100:.1f}%)")
    else:
        lines.append(f"- 中文专名命中（宽松/严格）：{o['pos_ok']}/{o['pos_n']} "
                     f"({(o['pos_rate'] or 0) * 100:.1f}%) / {o['pos_strict']}/{o['pos_n']} "
                     f"({(o['pos_strict_rate'] or 0) * 100:.1f}%)")
        lines.append(f"- neg 未出现专名（中文）：{o['neg_ok']}/{o['neg_n']} ({(o['neg_rate'] or 0) * 100:.1f}%)")
    if o["empty"]:
        lines.append(f"- 空输出：{o['empty']} 条（{(o['empty_rate'] or 0) * 100:.1f}%）")
    lines += ["", "## 分组", "", "| group | pos | pos(严格) | neg |", "|---|---|---|---|"]
    for g in sorted(summary["per_group"]):
        c = summary["per_group"][g]
        lines.append(f"| `{g}` | {c['pos_ok']}/{c['pos_n']} | {c['pos_strict']}/{c['pos_n']} "
                     f"| {c['neg_ok']}/{c['neg_n']} |")
    if summary["suspects"]:
        lines += ["", "## 错例（前 60 条）", ""]
        for s in summary["suspects"][:60]:
            sid = s["sample_id"]
            meta = metas.get(sid) or {}
            kind = "pos 未命中" if s["suspect"] == "pos_missed" else "neg 出现过专名"
            lines.append(f"- `{sid}` [{kind}] group={s['group']} variant={s.get('variant')} "
                         f"ja_ref={str(meta.get('ja_ref'))[:60]}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, choices=["asr", "zh"])
    ap.add_argument("--submission", required=True, help="提交 JSONL")
    ap.add_argument("--samples", default=DEF_SAMPLES, help="测试集样本 JSONL")
    ap.add_argument("--hotwords", default=DEF_HOTWORDS, help="ymmt_hotwords_v0.1.json")
    ap.add_argument("--out", default="", help="输出目录，默认 reports/<task>")
    ap.add_argument("--allow-missing", action="store_true", help="允许提交缺少部分样本")
    args = ap.parse_args()

    out_dir = args.out or os.path.join("reports", args.task)
    os.makedirs(out_dir, exist_ok=True)

    hw = common.load_hotwords(args.hotwords)
    samples = common.load_samples(args.samples)
    submission = common.read_submission(args.submission)
    errors = common.check_submission(submission, samples, require_all=not args.allow_missing)
    if errors:
        print("提交校验失败：", file=sys.stderr)
        for e in errors[:20]:
            print(" -", e, file=sys.stderr)
        return 2

    by_sid = {}
    for r in submission:
        sid = r["sample_id"]
        v = r.get("text")
        if v is None:
            v = r.get("translation") if r.get("translation") is not None else r.get("zh")
        by_sid[sid] = str(v) if v is not None else ""
    metas = {s["sample_id"]: s for s in samples}

    results = {}
    for s in samples:
        g = hw["by_id"].get(s["group"])
        if g is None:
            raise SystemExit(f"hotwords 缺少组 {s['group']}；请先用 scripts/add_names.py 添加")
        text = by_sid.get(s["sample_id"], "")
        if args.task == "asr":
            results[s["sample_id"]] = common.score_asr_sample(s, g, text)
        else:
            results[s["sample_id"]] = common.score_zh_sample(s, g, text)

    summary = common.summarize(samples, results)
    json.dump(summary, open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(render_report(args.task, summary, samples, metas))
    with open(os.path.join(out_dir, "suspects.jsonl"), "w", encoding="utf-8") as f:
        for s in summary["suspects"]:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    o = summary["overall"]
    print(f"{args.task}: pos {o['pos_ok']}/{o['pos_n']} ({(o['pos_rate'] or 0) * 100:.1f}%) "
          f"| strict {o['pos_strict']}/{o['pos_n']} ({(o['pos_strict_rate'] or 0) * 100:.1f}%) "
          f"| neg {o['neg_ok']}/{o['neg_n']} ({(o['neg_rate'] or 0) * 100:.1f}%) "
          f"| empty {o['empty']}")
    print(f"-> {out_dir}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())

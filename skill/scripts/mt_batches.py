#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""翻译评测的准备/汇总工具（模型无关：翻译器可以是 DeepSeek subagent、任意 API 或本地模型）。

场景：先得到 ASR 转写（或直接用参考文本），分批交给翻译器，回收中文结果后用
`scripts/eval.py --task zh` 打分。

用法:
  # 1) 把 ASR 提交文件切成翻译任务（每批 N 条）
  python scripts/mt_batches.py split --asr my_asr.jsonl --out-dir mt_jobs --batch-size 50

  # 2) 翻译器逐批读 mt_jobs/jobs/batch_XX.json，写 mt_jobs/out/batch_XX.jsonl
  #    约定输入: [{"sample_id": "...", "ja": "..."}]；输出: {"sample_id","text"}

  # 3) 汇总成 eval.py 可用的中文提交
  python scripts/mt_batches.py merge --out-dir mt_jobs --out my_zh.jsonl

  # 4) 评测
  python scripts/eval.py --task zh --submission my_zh.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common  # noqa: E402


def cmd_split(args) -> int:
    rows = common.read_submission(args.asr)
    items = []
    for r in rows:
        text = r.get("text")
        if text is None:
            text = r.get("translation") if r.get("translation") is not None else r.get("zh")
        items.append({"sample_id": r["sample_id"], "ja": str(text or "")})
    os.makedirs(os.path.join(args.out_dir, "jobs"), exist_ok=True)
    os.makedirs(os.path.join(args.out_dir, "out"), exist_ok=True)
    n = max(1, args.batch_size)
    for i in range(0, len(items), n):
        chunk = items[i:i + n]
        path = os.path.join(args.out_dir, "jobs", f"batch_{i // n:02d}.json")
        json.dump(chunk, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"batch_{i // n:02d}: {len(chunk)} -> {path}")
    # 术语表提示（若 hotwords 目录存在）
    gloss = os.path.join(os.path.dirname(HERE), "hotwords/mt_glossary.txt")
    if os.path.exists(gloss):
        print(f"提示：翻译时请把 {gloss} 里的日文专名按规范译名翻译")
    return 0


def cmd_merge(args) -> int:
    out_dir = args.out_dir
    got = {}
    for fn in sorted(os.listdir(os.path.join(out_dir, "out"))):
        if not fn.endswith(".jsonl"):
            continue
        for line in open(os.path.join(out_dir, "out", fn), encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            got[d["sample_id"]] = d.get("text") or ""
    job_ids = set()
    for fn in sorted(os.listdir(os.path.join(out_dir, "jobs"))):
        for item in json.load(open(os.path.join(out_dir, "jobs", fn), encoding="utf-8")):
            job_ids.add(item["sample_id"])
    missing = sorted(job_ids - set(got))
    with open(args.out, "w", encoding="utf-8") as f:
        for sid in sorted(got):
            f.write(json.dumps({"sample_id": sid, "text": got[sid]}, ensure_ascii=False) + "\n")
    print(f"merged {len(got)}/{len(job_ids)} -> {args.out}")
    if missing:
        print(f"缺失 {len(missing)} 条，例如 {missing[:5]}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("split")
    s.add_argument("--asr", required=True)
    s.add_argument("--out-dir", required=True)
    s.add_argument("--batch-size", type=int, default=50)
    s.set_defaults(func=cmd_split)
    m = sub.add_parser("merge")
    m.add_argument("--out-dir", required=True)
    m.add_argument("--out", required=True)
    m.set_defaults(func=cmd_merge)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

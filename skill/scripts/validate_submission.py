#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评测提交文件校验（发布后向 l_a@live.cn 提交转写/翻译结果前应通过本脚本）。

校验内容：
  - JSONL 可解析、UTF-8
  - 每行有 sample_id 且属于测试集
  - sample_id 不重复、默认要求覆盖全部测试样本
  - text 为非空字符串（允许空的行会被统计，不作为硬失败）
输出：stats（行数/覆盖/空输出/分组缺失）与退出码（0 通过，2 失败）。

用法:
  python scripts/validate_submission.py --submission my_asr.jsonl
  python scripts/validate_submission.py --submission my_zh.jsonl --task zh
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
SKILL = os.path.dirname(HERE)

import common  # noqa: E402

DEF_SAMPLES = os.path.join(SKILL, "data/test_base.jsonl")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--submission", required=True)
    ap.add_argument("--samples", default=DEF_SAMPLES)
    ap.add_argument("--task", default="asr", choices=["asr", "zh"])
    ap.add_argument("--allow-missing", action="store_true")
    ap.add_argument("--out", default="", help="可选：校验统计写入 JSON")
    args = ap.parse_args()

    samples = common.load_samples(args.samples)
    submission = common.read_submission(args.submission)
    errors = common.check_submission(submission, samples, require_all=not args.allow_missing)

    ids = {s["sample_id"] for s in samples}
    seen = Counter(r.get("sample_id") for r in submission)
    empty = 0
    for r in submission:
        t = r.get("text") or r.get("translation") or r.get("zh") or ""
        if not str(t).strip():
            empty += 1
    missing = sorted(ids - set(seen))
    extra = sorted(set(seen) - ids)
    stats = {
        "task": args.task,
        "n_samples": len(samples),
        "n_submitted": len(submission),
        "n_unique_ids": len(seen),
        "missing": len(missing),
        "unknown_ids": len(extra),
        "empty_text": empty,
        "duplicates": sum(1 for v in seen.values() if v > 1),
        "ok": not errors,
        "errors": errors[:50],
    }
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    if args.out:
        json.dump(stats, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if errors:
        print(f"\n校验失败（{len(errors)} 个问题）", file=sys.stderr)
        return 2
    print("\n校验通过。转写/翻译结果可提交评测（发到 l_a@live.cn，附提交文件与模型名）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

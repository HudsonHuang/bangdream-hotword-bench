# -*- coding: utf-8 -*-
"""skill 自测：用标注合成「完美提交」，验证两种口径都能到 100%；再验证空提交会失败。

运行:
  python tests/selftest.py
  BENCH_NO_FUGASHI=1 python tests/selftest.py   # 不带 MeCab 的回退分词也要通过
"""
import json
import os
import subprocess
import sys
import tempfile

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(SKILL, "data/test_base.jsonl")
EVAL = os.path.join(SKILL, "scripts/eval.py")
PY = sys.executable


def build_perfect(task: str) -> list:
    rows = [json.loads(l) for l in open(SAMPLES, encoding="utf-8")]
    out = []
    neutral = "今日はいい天気ですね。全然関係ない話です。" if task == "zh" else "今日はいい天気ですね。"
    for r in rows:
        if r["label"] == "pos":
            if task == "zh":
                text = (r.get("allowed_zh") or ["某某"])[0]
            else:
                text = r["variant"]
        else:
            text = neutral
        out.append({"sample_id": r["sample_id"], "text": text})
    return out


def run(task: str, rows: list, *flags: str) -> dict:
    tmp = tempfile.mkdtemp()
    sub = os.path.join(tmp, "submission.jsonl")
    with open(sub, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    outdir = os.path.join(tmp, "out")
    r = subprocess.run([PY, EVAL, "--task", task, "--submission", sub,
                        "--out", outdir, *flags],
                       capture_output=True, text=True, env={**os.environ})
    if r.returncode != 0:
        raise SystemExit(f"eval failed: {r.stdout}\n{r.stderr}")
    return json.load(open(os.path.join(outdir, "metrics.json"), encoding="utf-8"))


def main() -> int:
    failures = []
    for task in ("asr", "zh"):
        m = run(task, build_perfect(task))["overall"]
        print(task, json.dumps({k: m[k] for k in ("pos_rate", "pos_strict_rate", "neg_rate", "empty")},
                                ensure_ascii=False))
        if (m["pos_rate"] or 0) < 0.99 or (m["neg_rate"] or 0) < 0.99:
            failures.append(f"{task}: 完美提交未达 100%")
        # 空提交：pos 应全 miss
        empty = run(task, [{"sample_id": r["sample_id"], "text": ""}
                           for r in [json.loads(l) for l in open(SAMPLES, encoding="utf-8")]])
        if (empty["overall"]["pos_rate"] or 0) > 0.01:
            failures.append(f"{task}: 空提交不应有 pos 命中")
    if failures:
        print("FAIL:", failures, file=sys.stderr)
        return 1
    print("selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

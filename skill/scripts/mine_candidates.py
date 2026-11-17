#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从粗 ASR 转写里挖掘新名字候选（扩展数据集第一步）。

输入转写格式（任选）：
  a) JSONL：每行 {"video_id": "...", "t_start": 123.4, "text": "..."}
  b) 目录：每个视频一个 JSON，形如 {"video_id": "...", "segments": [{"t_start":..., "text":...}]}
     （也接受直接是 segment 数组的 JSON）

用法:
  # 先按 add_names.py 把新名字写进热词，再只挖这些新组
  python scripts/mine_candidates.py --transcripts /path/to/rough_asr \
      --groups p_newmember,b_newband --out candidates_new.jsonl

输出 JSONL: {group, variant(读音), surface(命中写法), video_id, t_start, text}
后续：人工/LLM 判定 pos/neg → 按样本格式补标注 → 切片 → 加入测试集。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import common  # noqa: E402

DEF_HOTWORDS = os.path.join(SKILL, "hotwords/ymmt_hotwords_v0.1.json")


def iter_segments(path: str):
    """产出 (video_id, t_start, text)。"""
    if os.path.isdir(path):
        for fp in sorted(glob.glob(os.path.join(path, "*.json")) +
                         glob.glob(os.path.join(path, "*.jsonl"))):
            stem = os.path.splitext(os.path.basename(fp))[0]
            if fp.endswith(".jsonl"):
                for line in open(fp, encoding="utf-8"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    yield d.get("video_id") or stem, float(d.get("t_start") or d.get("start") or 0), d.get("text") or ""
                continue
            try:
                d = json.load(open(fp, encoding="utf-8"))
            except Exception:
                continue
            vid = d.get("video_id") if isinstance(d, dict) else stem
            segs = d.get("segments") if isinstance(d, dict) else d
            for s in segs or []:
                yield vid or stem, float(s.get("t_start") or s.get("start") or 0), s.get("text") or ""
        return
    if path.endswith(".jsonl"):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            yield d.get("video_id") or "", float(d.get("t_start") or d.get("start") or 0), d.get("text") or ""
        return
    d = json.load(open(path, encoding="utf-8"))
    vid = d.get("video_id") if isinstance(d, dict) else ""
    segs = d.get("segments") if isinstance(d, dict) else d
    for s in segs or []:
        yield vid, float(s.get("t_start") or s.get("start") or 0), s.get("text") or ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transcripts", required=True)
    ap.add_argument("--hotwords", default=DEF_HOTWORDS)
    ap.add_argument("--groups", default="", help="逗号分隔的 group id；默认全部")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-per-video", type=int, default=200)
    args = ap.parse_args()

    hw = common.load_hotwords(args.hotwords)
    groups = hw["groups"]
    if args.groups:
        want = {x.strip() for x in args.groups.split(",") if x.strip()}
        unknown = want - {g["id"] for g in groups}
        if unknown:
            raise SystemExit(f"热词里没有这些组: {sorted(unknown)}")
        groups = [g for g in groups if g["id"] in want]

    n = 0
    per_video = {}
    out = open(args.out, "w", encoding="utf-8")
    for vid, t, text in iter_segments(args.transcripts):
        if not text:
            continue
        tokens = common.tokenize(text)
        seen = set()
        for g in groups:
            for rd in g["readings"]:
                if len(rd) < 2:
                    continue
                if (g["id"], rd) in seen:
                    continue
                hits = common.aligned_forms(tokens, rd)
                if not hits:
                    continue
                seen.add((g["id"], rd))
                key = (vid, g["id"])
                if per_video.get(key, 0) >= args.max_per_video:
                    continue
                per_video[key] = per_video.get(key, 0) + 1
                rec = {"group": g["id"], "variant": rd, "surface": hits[0],
                       "video_id": vid, "t_start": round(t, 2), "text": text[:300]}
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
    out.close()
    print(f"candidates: {n} -> {args.out}")
    if n == 0:
        print("提示：没有命中。确认转写格式与 group 读音（kana）；新名字需要先 add_names.py 写入热词。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按样本 source 时间偏移从本地源音频切出评测片段（扩展数据集/自建音频时用）。

发布的测试集音频已切好；只有在**新增样本**且手里有源视频音频时才需要本脚本。

输入：
  --samples     样本 JSONL（每条含 source.video_id + source.offset_s + source.duration_s）
  --source-dir  源音频目录（文件名 <video_id>.m4a / .wav / .mp3 ...）
输出：
  --out         片段目录：<split>/<group>/<label>/<sample_id>.m4a
  --manifest    片段清单 JSONL（sample_id/path/duration/sha256）

用法:
  python scripts/clip_audio.py --samples data/test/samples_test.jsonl \
      --source-dir /data/source_audio --out /data/clips --manifest /data/clips_manifest.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys


def find_source(source_dir: str, vid: str) -> str | None:
    for ext in (".m4a", ".mp3", ".wav", ".aac", ".ogg", ".flac", ".opus", ".webm"):
        p = os.path.join(source_dir, vid + ext)
        if os.path.exists(p):
            return p
    return None


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--samples", required=True)
    ap.add_argument("--source-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", default="clips_manifest.jsonl")
    ap.add_argument("--ffmpeg", default=os.environ.get("FFMPEG", "ffmpeg"))
    ap.add_argument("--margin", type=float, default=0.25)
    args = ap.parse_args()

    samples = [json.loads(l) for l in open(args.samples, encoding="utf-8") if l.strip()]
    os.makedirs(args.out, exist_ok=True)
    mf = open(args.manifest, "w", encoding="utf-8")
    ok = fail = 0
    for s in samples:
        vid = s["source"]["video_id"]
        src = find_source(args.source_dir, vid)
        if not src:
            print(f"skip {s['sample_id']}: 源音频缺失 {vid}", file=sys.stderr)
            fail += 1
            continue
        start = max(0.0, float(s["source"]["offset_s"]) - args.margin)
        dur = float(s["source"]["duration_s"])
        dst_dir = os.path.join(args.out, s["split"], s["group"], s["label"])
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, s["sample_id"] + ".m4a")
        cmd = [args.ffmpeg, "-y", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
               "-i", src, "-vn", "-c:a", "aac", "-b:a", "128k", dst]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not os.path.exists(dst):
            print(f"ffmpeg fail {s['sample_id']}: {r.stderr[-200:]}", file=sys.stderr)
            fail += 1
            continue
        mf.write(json.dumps({"sample_id": s["sample_id"], "path": os.path.relpath(dst),
                             "duration_s": dur, "sha256": sha256(dst)}, ensure_ascii=False) + "\n")
        ok += 1
    mf.close()
    print(f"clips: ok={ok} fail={fail} manifest={args.manifest}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

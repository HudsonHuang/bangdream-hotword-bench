# -*- coding: utf-8 -*-
"""@file run_parallel.py
@brief Run several ASR / translation configurations in parallel and score them.

Two modes:

  clips   one invocation per sample, all samples across N workers, output text is
          collected into a submission JSONL that eval.py can read directly.
  stream  one invocation per configuration over the whole audio file; the JSONL
          event stream is kept as merged.jsonl and scored with score_mentions.py.

The command template may use {audio} and {sample_id}; the process must print
worker-style JSON lines ({"event": "result", ...}) or plain text on stdout.

Examples:
  python scripts/run_parallel.py --mode clips --workers 6 \\
      --configs "live=python live_interpreter_backend.py --paraformer-mt-worker --audio {audio}" \\
      --samples data/test_base.jsonl --audio-dir data/clips --out runs/clips

  python scripts/run_parallel.py --mode stream --workers 2 \\
      --configs "para=python live_interpreter_backend.py --paraformer-mt-worker --pcm {audio}" \\
      --audio audio/dense-20/dense20_01_of_01.m4a --out runs/dense20
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402


def parse_configs(items: list[str]) -> dict[str, str]:
    configs = {}
    for item in items:
        name, _, command = item.partition("=")
        if not name or not command:
            raise SystemExit(f"--configs expects name=command, got {item!r}")
        configs[name.strip()] = command.strip()
    return configs


def cli_args(sample: dict) -> str:
    return " ".join(f'--{key} "{value}"' for key, value in sample.items() if isinstance(value, (str, int, float)))


def run_clips(configs: dict[str, str], samples: list[dict], audio_arg: str, workers: int, timeout: int, out: Path) -> None:
    tasks = [(name, command, sample) for name, command in configs.items() for sample in samples]
    queue_lock = threading.Lock()
    results: dict[str, dict[str, str]] = {name: {} for name in configs}
    done = 0

    def work(task):
        nonlocal done
        name, command, sample = task
        audio = str(sample.get("audio") or "")
        if audio_arg and not os.path.isabs(audio):
            audio = str(Path(audio_arg) / Path(audio).name)
        command_line = (
            command.replace("{audio}", audio).replace("{sample_id}", str(sample["sample_id"]))
            + " " + cli_args({k: v for k, v in sample.items() if k in {"sample_id", "group", "variant", "label"}})
        )
        try:
            proc = subprocess.run(command_line, shell=True, capture_output=True, text=True, timeout=timeout)
            text = ""
            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    text = line
                    continue
                if event.get("event") == "result" and event.get("translation_final"):
                    text = str(event.get("translation") or "")
                elif event.get("event") == "result" and event.get("source_final") and not text:
                    text = str(event.get("source") or "")
            with queue_lock:
                results[name][sample["sample_id"]] = text
        except subprocess.TimeoutExpired:
            with queue_lock:
                results[name][sample["sample_id"]] = ""
        with queue_lock:
            done += 1
            if done % 25 == 0:
                print(f"{done}/{len(tasks)}", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(work, tasks))
    out.mkdir(parents=True, exist_ok=True)
    for name, mapping in results.items():
        path = out / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for sample in samples:
                handle.write(json.dumps({"sample_id": sample["sample_id"], "text": mapping.get(sample["sample_id"], "")},
                                        ensure_ascii=False) + "\n")
        empty = sum(1 for text in mapping.values() if not str(text).strip())
        print(f"[{name}] {len(mapping)} rows, empty {empty} -> {path}")


def run_stream(configs: dict[str, str], audio: str, workers: int, timeout: int, out: Path) -> None:
    def work(item):
        name, command = item
        directory = out / name
        directory.mkdir(parents=True, exist_ok=True)
        command_line = command.replace("{audio}", audio)
        started = time.monotonic()
        try:
            proc = subprocess.run(command_line, shell=True, capture_output=True, text=True, timeout=timeout)
            merged = directory / "merged.jsonl"
            merged.write_text(proc.stdout, encoding="utf-8")
            (directory / "stderr.log").write_text(proc.stderr, encoding="utf-8")
            events = sum(1 for line in proc.stdout.splitlines() if '"result"' in line)
            print(f"[{name}] events {events} in {time.monotonic() - started:.0f}s -> {merged}")
        except subprocess.TimeoutExpired:
            print(f"[{name}] timeout after {timeout}s")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(work, configs.items()))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", required=True, choices=["clips", "stream"])
    ap.add_argument("--configs", nargs="+", required=True, help="name=command templates")
    ap.add_argument("--samples", default="", help="samples JSONL for clips mode")
    ap.add_argument("--audio", default="", help="audio file for stream mode / audio root for clips")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    configs = parse_configs(args.configs)
    out = Path(args.out)
    if args.mode == "clips":
        if not args.samples:
            raise SystemExit("clips mode needs --samples")
        samples = common.load_samples(args.samples)
        run_clips(configs, samples, args.audio, args.workers, args.timeout, out)
    else:
        if not args.audio:
            raise SystemExit("stream mode needs --audio")
        run_stream(configs, args.audio, args.workers, args.timeout, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

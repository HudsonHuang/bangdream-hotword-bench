# 用 live-interp 跑本测试集

以 [live-interpreter](https://github.com/starry335/live-interpreter) 为例：它的 worker 从 stdin 读 16k 单声道 PCM、
把 `result` 事件按 JSONL 打到 stdout，所以可以直接接本仓库的 `run_parallel.py`。

## 1. 切片模式（v0.1 的 283 条）

每条样本一次进程（推荐 4–8 并发）：

```bash
python scripts/run_parallel.py --mode clips --workers 6 \
  --configs "icl=python live_interpreter_backend.py --paraformer-mt-worker --mt-mode icl --hotword-cards hotwords/name_cards.json --pcm {audio}" \
  --samples data/test_base.jsonl --audio-dir /path/to/clip_audio --out runs/clips_icl

python scripts/eval.py --task zh --submission runs/clips_icl/icl.jsonl \
  --samples data/test_base.jsonl --hotwords hotwords/ymmt_hotwords_v0.1.json --out runs/clips_icl/reports/zh
```

要点：

- 每个样本用独立进程，避免跨句上下文串味；worker 需支持 `--pcm <file>`（或等价参数）。
- 想只重跑翻译（不动 ASR），用 live-interp 仓库的 `tools/replay_*`：固定 ASR 文本，只发 LLM 请求。

## 2. 连续流模式（v0.2 的 dense-20）

整段 20 分钟一次喂完，保留时间戳：

```bash
python scripts/run_parallel.py --mode stream --workers 2 \
  --configs "para=python live_interpreter_backend.py --paraformer-mt-worker --mt-mode icl --pcm {audio}" \
  --audio audio/dense-20/dense20_01_of_01.m4a --out runs/dense20

python scripts/score_mentions.py --merged runs/dense20/para/merged.jsonl --task zh --neg-mode unit \
  --out runs/dense20/para/score_zh.json
```

`{audio}` 会替换成实际音频路径；命令必须输出 `{"event": "result", ...}` 行，至少包含
`sentence_id`、`source_final`、`begin_time`、`end_time`（毫秒或秒自洽即可），翻译模式再加
`translation_final` 与 `translation`。

## 3. 三套参考配置

| 名称 | ASR | 翻译 | 关键参数 |
|---|---|---|---|
| 基线 | Paraformer-Realtime-V2 + live 默认词表 | qwen3.8-max | `--mt-mode force` |
| 新 Para | Paraformer-Realtime-V2 + v0.1 词表 | qwen3.8-max | `--mt-mode icl --hotword-cards hotwords/name_cards.json --correct-names` |
| 新 3.1 | qwen-audio-3.1-asr-flash-streaming + 热词 | qwen3.8-max | `--mt-mode icl` |

统一关闭上下文（`--context-turns 0`），结果见 `results/dense20_results.md`。

## 4. 注意

- 3.1 的 `input.context`（会话级背景词表）实测会让 ASR 召回下降，不建议使用。
- 逐句翻译的延迟由「静音判句 + 一次 LLM 调用」组成；统一温度 0.2、`enable_thinking=false`。
- 词表与术语卡都要用本 skill 的 `hotwords/`，别混用厂商默认词表，否则数字不可比。

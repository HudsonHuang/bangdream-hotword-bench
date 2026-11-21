# v0.3 · 流式黄金集（gold-v0.3）

v0.1 是 283 条句级切片，v0.2 是 20 分钟连续片段；v0.3 补的是**带人工精标的完整高光片段**，
用来同时看三件事：

1. **回显节奏**：中文第一次出现离参考句结束有多远；
2. **翻译质量**：中文和人工译文的字符 F1；
3. **热词质量**：参考句里的人名/乐队名有没有出现在中文里。

数据在 Hugging Face 的 `gold-v0.3/` 下：

```
gold-v0.3/
├── audio/*.wav     # 16 kHz / 16-bit / mono，113–991 秒
├── srt/*.srt       # 人工修正后的中文 SRT，cue 正文带 [speaker=arl|myk|nnk|ritsu|yuno]
├── manifest.json   # 每条 clip 的元数据、源视频、修正统计、sha256
├── checksums.sha256
└── README.md
```

`skill/data/gold_v03.jsonl` 是同一份数据的机器可读清单，字段：

```json
{
  "clip_id": "9u5-VQG61So_hl04",
  "video_id": "9u5-VQG61So",
  "title_zh": "11天热量结算：1律≈4由乃",
  "duration_s": 991.2,
  "cues": 249,
  "speakers": ["ritsu", "yuno"],
  "audio": "gold-v0.3/audio/9u5-VQG61So_hl04_11天热量结算：1律≈4由乃.wav",
  "srt": "gold-v0.3/srt/9u5-VQG61So_hl04_11天热量结算：1律≈4由乃.srt",
  "name_mentions": {"野乃花": 4, "律": 17, "由乃": 16}
}
```

## 规模

| 项 | 值 |
|---|---:|
| 片段 | 32 条已发布高光 |
| 音频 | 92.4 分钟，16 kHz mono WAV |
| cue | 1,525 条人工修正中文 cue |
| 说话人 | arl / myk / nnk / ritsu / yuno |
| 精标统计 | 共 600+ 条 cue 被人工改过（细分/说话人/译文） |

## 口径

### 1. 回显节奏

以 SRT cue 的 `end` 为参考：

- `first_zh`：该 cue 覆盖的 ASR 句子里，**第一次出现中文**（流式首字/草稿/终译都算）的时间 − cue.end；
- `final_zh`：该句 `translation_final` 的时间 − cue.end；
- 统计 p50 / mean / p90 / max，以及 ≤2.5 秒的比例；
- `zh_gap`：相邻两次「首次中文」之间的间隔，用来看有没有长空档。

> `_recv_mono` 若从 worker 进程启动算起，会包含 1–2 秒的连接时间；`eval_stream.py` 默认找到
> `ready` 事件并减去它，把时间对齐到「开始喂音频」。如果 run 文件没有 `ready` 事件，用
> `--no-ready-offset`，并自己保证时间戳从第一帧音频开始。

### 2. 翻译质量

- 对该 cue 时间上重叠的所有句子的最终中文做拼接；
- 和人工 SRT 做字符级 F1（去掉标点/空白，保留中英数字）；
- 统计 p50 / mean。

### 3. 热词质量

- 从人工 SRT 里找出 16 个规范名（阿拉蕾、野乃花、律、都子、由乃、梦限大、MewType、10 个乐队名）；
- 对每个出现的名字，看拼接后的中文里是否也出现；
- 输出 `命中/总数` 和召回率。注意：人工译文有时用「她」省略名字，所以这是**保守下界**，不是严格 F1。

## 跑法

### 1. 下载数据

```bash
hf download zhongyihuang/bangdream-hotword-bench --repo-type dataset \
  --include "gold-v0.3/*" "data/gold_v03.jsonl" --local-dir data
```

### 2. 跑一个模型

录一段带时间戳的 JSONL。以 live-interpreter 为例，用它的
[`tools/replay_stream.py`](https://github.com/starry335/live-interpreter/blob/main/docs/BENCHMARK_V03.md)：

```bash
python tools/replay_stream.py \
  --wav data/gold-v0.3/audio/9u5-VQG61So_hl04_11天热量结算：1律≈4由乃.wav \
  --start 120 --seconds 180 --out runs/31_ref \
  -- --model qwen-audio-3.1-asr-flash-streaming --max-end-silence 200 \
     --vad-model near_meeting_16k --mt-model qwen3.8-max --mt-mode reference \
     --hotwords hotwords/yumemita_bangdream.txt
```

`events.jsonl` 每行至少要有：

```json
{"event":"result","sentence_id":"123","source_final":true,"begin_time":1230,"end_time":3450}
{"event":"result","sentence_id":"123","translation":"……","translation_final":true,"_recv_mono":3.9}
```

`begin_time/end_time` 默认按毫秒；`_recv_mono` 是从开始喂音频算起的秒数。

### 3. 打分

```bash
python skill/scripts/eval_stream.py \
  --run runs/31_ref/events.jsonl \
  --srt data/gold-v0.3/srt/9u5-VQG61So_hl04_11天热量结算：1律≈4由乃.srt \
  --offset 120 --start 120 --end 300 \
  --label "3.1 reference" --out runs/31_ref/report
```

产物：`report/metrics.json`（含每条 cue 的机器译文）和 `report/report.md`。

> `--offset` 用于「只跑了整条视频的一段」：SRT 是整条视频的绝对时间，run 的 `_recv_mono` 从 0 开始。
> 跑完整条片段时 `--offset 0`，不需要 `--start/--end`。

### 4. 参考结果（9u5… 的 120–300 秒）

| 配置 | coverage | first-zh p50 | mean | charF1 | 人名召回 | 成本 |
|---|---:|---:|---:|---:|---:|---:|
| Paraformer + qwen3.8-max | 95.7% | 1.77 s | 1.39 s | 0.430 | 76.9% | 2.71 元/h |
| 3.1 + qwen3.8-max reference | 91.5% | 1.34 s | 0.72 s | 0.445 | 92.3% | 2.74 元/h |
| 3.1 + qwen3.8-max ICL + 1 轮上下文 | 91.5% | 1.42 s | 0.76 s | 0.456 | 84.6% | 3.68 元/h |

完整结果见 `results/gold03_results.md`。

## 注意

- SRT 是**中文人工译文**，不是日文金标；所以这个集合只评「中文可懂度/热词/节奏」，不评 ASR WER。
- 32 条都是已发布高光，版权归原权利人；仅限非商业研究与评测。
- 片段的 `speaker` 标签是人工修正后的最终归属，可作为说话人相关分析的真值。

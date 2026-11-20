# dense-20 连续片段（v0.2）

v0.1 的 283 条是**句级切片**（每条一个判定）。dense-20 补的是一段**连续直播**：
同一套热词、同一位主播、20 分钟不切片，用来测「真跑起来」时的召回，以及分词/断句差异。

## 数据

| 文件 | 内容 |
|---|---|
| `audio/dense-20/dense20_01_of_01.m4a`（HF） | 20 分钟连续音频，`ew-HkuFPUcg` 第 7200–8400 秒 |
| `data/dense20.jsonl` | 85 条可评分样本（句 × 组），含 `chunk_start_s/chunk_end_s`、`ja_ref`、`allowed_zh` |
| `data/dense20_units.json` | 181 个参考句（含 124 个无专名句），带 `groups` 标注 |
| `data/dense20_transcript.jsonl` | 181 句语义校正后的日/中参考转写 |
| `data/stats_dense20.json` | 规模、分组计数、来源视频 |

- 181 句里 57 句带专名，共 **85 处提及**，覆盖 13 组（`b_morfonica`、`b_ras` 在这段没有出现）。
- 参考转写用 qwen-audio 3.1 转写打底，对照自动字幕 + Paraformer + 三套译文逐句校正；
  低置信度（简称、同音）保留 `confidence` 字段。
- 这段几乎全是真名，**没有天然虚警样本**：虚警率请用 v0.1 的 142 条 neg，或按下面的合并口径。

## 评分

两种方式：

1. **样本级**（需要系统按 `dense20.jsonl` 的 85 条逐条输出）：
   ```bash
   python scripts/eval.py --task zh --submission sub.jsonl \
     --samples data/dense20.jsonl --hotwords hotwords/ymmt_hotwords_v0.1.json --out reports/zh
   ```
   只有 pos，所以给出的是召回与精确率（无 neg 时虚警不适用）。

2. **连续流 / mention-level**（推荐的跑法）：
   ```bash
   python scripts/score_mentions.py --merged run/merged.jsonl --task zh --neg-mode unit --out run/dense20.json
   ```
   - 系统句按「时间重叠最大」归到参考句，重叠 < 0.3 s 丢弃；
   - `pos`：参考句标了该组，系统输出命中该组的任一形态 = TP，否则 FN；
   - `neg-mode unit`：无专名参考句里出现任何组名 = 1 次虚警（FP），否则 TN；
   - 输出 `overall` 与 `groups` 两级的 R/P/FAR/F1。

### 与 v0.1 合并

两部分计数直接相加再算指标：
v0.1 提供 TP/FP/FN/TN（每条一个判定），dense-20 提供 TP/FN（每处提及）+ FP/TN（每个无专名句）。
参考结果见 `results/dense20_results.md`。

## 局限

- 素材只有一段 20 分钟、13/15 组，别把它当全量分布。
- 参考句边界来自 3.1 的 VAD，已人工校正明显切断处；不同系统的断句差异靠重叠规则吸收。
- 音频来自公开 YouTube 直播，仅用于研究评测，版权归原版权方。

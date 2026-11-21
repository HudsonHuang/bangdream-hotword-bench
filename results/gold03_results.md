# v0.3 · gold 流式参考结果

口径：`skill/scripts/eval_stream.py`；温度 0.2，`enable_thinking=false`；3.1 使用 `near_meeting_16k` + 200 ms。

## 测什么

同时看三件事：

- **回显节奏**：`first_zh` = 该 cue 第一次出现中文 − cue.end；
- **翻译质量**：重叠句最终中文拼接 vs 人工 SRT 的字符 F1；
- **热词**：人工 SRT 里出现的 16 个规范名，在中文里是否出现（保守下界）。

## 2–5 分钟片段（9u5-VQG61So_hl04，120–300 秒）

| 配置 | coverage | first-zh p50 | mean | p90 | charF1 | 人名召回 | 成本 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Paraformer + qwen3.8-max（默认基线） | 95.7% | 1.77 s | 1.39 s | 4.74 s | 0.430 | 76.9% | 2.71 元/h |
| 3.1 + qwen3.8-max + reference（默认） | 91.5% | 1.34 s | 0.72 s | 2.64 s | 0.445 | 92.3% | 2.74 元/h |
| 3.1 + qwen3.8-max + ICL + 1 轮上下文（非默认） | 91.5% | 1.42 s | 0.76 s | 2.68 s | 0.456 | 84.6% | 3.68 元/h |

> `first-zh` 已按 worker 的 `ready` 事件对齐到开始喂音频的时刻。

结论：

- 3.1 reference 用与基线相同的成本，把 mean 从 2.41 s 降到 2.10 s，人名召回从 76.9% 提到 92.3%；
- ICL + 1 轮上下文节奏最好、charF1 最高，但成本高 36%，且这次的人名召回反而略低；
- 默认选 reference，是节奏 / 质量 / 热词 / 成本四项里最均衡的一档。

## 复现

见 `skill/docs/GOLD03.md` 和 live-interpreter 的 `docs/BENCHMARK_V03.md`。

原始 run 时间轴：

- `frozen_ref_180b`：3.1 reference，180 秒，120–300 秒窗口
- `icl2_ctx1`：3.1 ICL + 1 轮上下文
- `para_base`：Paraformer + qwen3.8-max

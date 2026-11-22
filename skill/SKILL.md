---
name: bangdream-hotword-bench
description: 邦多利烤肉场景（BanG Dream! / 梦限大 MewType）的人名热词库与 ASR/同传测试集：ymmt_hotwords_v0.1 最小完备读音热词、中文/英文标准热词、283 条句级音频 + 20 分钟连续片段（dense-20）+ 32 条人工精标流式黄金集（gold-v0.3，92.4 分钟）、三种测试口径（ASR / 同传 / 流式节奏+质量+热词）与并行 headless 评测脚本。支持扩展新名字。
---

# bangdream-hotword-bench

邦多利烤肉场景的人名热词库 + ASR / 同传测试集。

- **热词**：17 组（5 位成员 + 12 个乐队）的「最小完备读音」定义（读音基元 + 组合规则），
  含中文规范译名、英文名、各 ASR 后端现成导出；
- **测试集**：test-base，283 条句级音频（141 pos / 142 neg），15 组，来自 215 个公开 YouTube 直播；
- **连续片段**：dense-20（v0.2），20 分钟不切片音频，181 句 / 85 处专名提及，用于连续流召回；
- **流式黄金集**：gold-v0.3，32 条完整高光，92.4 分钟，16 kHz WAV + 人工精标中文 SRT（1,525 cue）；
- **完整长视频**：v0.4-full，40:56 不切片，471 个自动字幕 unit，测长时间人名召回/误替换；
- **三种测试口径**：ASR（音频 → 日文转写）、同传（音频 → 最终中文）、流式（节奏 + 质量 + 热词）；
- 数据（音频 / 视频 / 标注）在 Hugging Face：https://huggingface.co/datasets/zhongyihuang/bangdream-hotword-bench

## 目录

```
skill/
├── SKILL.md
├── README.md
├── DATASET_CARD.md
├── docs/
│   ├── SCORING.md        # 打分规则
│   ├── SUBMISSION.md     # 提交格式与验证流程
│   ├── MT_PIPELINE.md    # 同传/翻译评测跑法
│   ├── DENSE20.md        # v0.2 连续片段说明与打分
│   ├── GOLD03.md         # v0.3 流式黄金集：节奏 / 质量 / 热词
│   ├── LIVE_INTERP.md    # 用 live-interp 跑本测试集
│   └── EXTENDING.md      # 扩展新名字
├── hotwords/             # 热词定义 + 读音索引 + 中文/英文标准热词 + 后端导出
├── data/
│   ├── test_base.jsonl   # 283 条标注（含 utt 在视频中的起止）
│   ├── dense20.jsonl     # v0.2：85 条连续片段样本（句 × 组）
│   ├── dense20_units.json / dense20_transcript.jsonl
│   ├── gold_v03.jsonl    # v0.3：32 条高光清单
│   └── stats.json / stats_dense20.json
├── scripts/
│   ├── eval.py                 # 评测入口（--task asr | zh）
│   ├── eval_stream.py          # v0.3：节奏 / 字符 F1 / 人名召回
│   ├── validate_submission.py  # 提交文件校验
│   ├── add_names.py            # 扩展新名字（重建热词/索引/导出）
│   ├── score_mentions.py       # v0.2：连续片段 mention-level 打分
│   ├── run_parallel.py         # 并行 headless 跑法（切片/连续流）
│   ├── mt_batches.py           # 翻译批切分/汇总
│   ├── mine_candidates.py      # 从粗转写挖新名字候选
│   ├── clip_audio.py           # 新增样本切片（有源音频时）
│   └── common.py               # 打分核心
└── tests/selftest.py
```

## 快速开始

```bash
# 提交文件：JSONL，每行 {"sample_id": "...", "text": "模型输出"}
python scripts/validate_submission.py --submission my_asr.jsonl   # 先校验
python scripts/eval.py --task asr --submission my_asr.jsonl       # ASR 模式
python scripts/eval.py --task zh  --submission my_zh.jsonl        # 同传模式
```

产物：`reports/asr|zh/{metrics.json,report.md,suspects.jsonl}`。

## 两种测试模式（细节见 docs/SCORING.md）

| 模式 | 模型输入 | 模型输出 | 判分 |
|---|---|---|---|
| `asr` | 音频 | 日文转写 | pos：专名正确出现；neg：同音普通词不被当成专名 |
| `zh` | 音频 | 最终中文（ASR→翻译 或 直接同传） | pos：命中 `allowed_zh`；neg：不出现该组中文专名 |

## 热词

`hotwords/` 关键文件：

- `ymmt_hotwords_v0.1.json`：权威定义（读音基元 + 拼接/后缀规则 + 中文译名 + 英文名）；
- `hotwords_zh_en_v0.1.json/.md`：中英文标准热词；
- `zh_hotwords.json` / `mt_glossary.txt`：翻译/同传词表；
- `export/`：`volc_context.json`（火山 ASR2 corpus.context）、`qwen_vocabulary.json` / `qwen_context.txt`（qwen ASR）、`moss_hotwords.csv`（MOSS）。

## 扩展新名字

格式与流程见 `scripts/add_names.py` 文档头与 `docs/EXTENDING.md`：

```bash
python scripts/add_names.py --spec new_names.json --dry-run   # 校验 + 看派生
python scripts/add_names.py --spec new_names.json             # 写入并重建索引/导出
python scripts/mine_candidates.py --transcripts rough_asr/ --groups p_new --out candidates.jsonl
```

## v0.2 连续片段（dense-20）

```bash
python scripts/run_parallel.py --mode stream --workers 2 \
  --configs "icl=<worker 命令>" --audio audio/dense-20/dense20_01_of_01.m4a --out runs/dense20
python scripts/score_mentions.py --merged runs/dense20/icl/merged.jsonl --task zh --neg-mode unit --out runs/dense20/icl/score_zh.json
```

- 参考句 181 个（57 句含专名、124 句无专名）；虚警由无专名句判定，召回由 85 处提及判定；
- 与 v0.1 合并的参考结果：`results/dense20_results.md`；
- 详细说明：`docs/DENSE20.md`，live-interp 跑法：`docs/LIVE_INTERP.md`。

## v0.3 流式黄金集（gold-v0.3）

32 条完整高光，16 kHz WAV + 人工精标中文 SRT（1,525 cue），同时评三件事：

```bash
# 1. 跑模型，产出带 _recv_mono 的 events.jsonl（见 live-interp 的 tools/replay_stream.py）
# 2. 打分
python scripts/eval_stream.py \
  --run runs/31_ref/events.jsonl \
  --srt gold-v0.3/srt/9u5-VQG61So_hl04_11天热量结算：1律≈4由乃.srt \
  --offset 120 --start 120 --end 300 \
  --label "3.1 reference" --out runs/31_ref/report
```

产物：`metrics.json`（coverage / first-zh / charF1 / 人名召回 / 中文间隔）与 `report.md`。
数据清单：`data/gold_v03.jsonl`；口径与参考结果：`docs/GOLD03.md`、`results/gold03_results.md`。

## 提交官方验证

把通过校验的 JSONL（转写或中文结果）发到 **l_a@live.cn**，附模型名、解码参数、模式（asr/zh）、
是否使用热词；会用同一套脚本复算并返回报告。

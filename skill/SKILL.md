---
name: bangdream-hotword-bench
description: 邦多利烤肉场景（BanG Dream! / 梦限大 MewType）的人名热词库与 ASR/同传测试集：ymmt_hotwords_v0.1 最小完备读音热词、中文/英文标准热词、283 条句级音频与两种测试模式（ASR / 同传）的评测脚本。支持扩展新名字。
---

# bangdream-hotword-bench

邦多利烤肉场景的人名热词库 + ASR / 同传测试集。

- **热词**：17 组（5 位成员 + 12 个乐队）的「最小完备读音」定义（读音基元 + 组合规则），
  含中文规范译名、英文名、各 ASR 后端现成导出；
- **测试集**：单套 test-base，283 条句级音频（141 pos / 142 neg），15 组，来自 215 个公开 YouTube 直播；
- **两种测试模式**：ASR（音频 → 日文转写）与 同传（音频 → 最终中文）；
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
│   └── EXTENDING.md      # 扩展新名字
├── hotwords/             # 热词定义 + 读音索引 + 中文/英文标准热词 + 后端导出
├── data/
│   ├── test_base.jsonl   # 283 条标注（含 utt 在视频中的起止）
│   └── stats.json
├── scripts/
│   ├── eval.py                 # 评测入口（--task asr | zh）
│   ├── validate_submission.py  # 提交文件校验
│   ├── add_names.py            # 扩展新名字（重建热词/索引/导出）
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

## 提交官方验证

把通过校验的 JSONL（转写或中文结果）发到 **l_a@live.cn**，附模型名、解码参数、模式（asr/zh）、
是否使用热词；会用同一套脚本复算并返回报告。

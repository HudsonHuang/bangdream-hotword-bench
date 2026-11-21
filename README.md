[![🤗 Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20Dataset-bangdream--hotword--bench-yellow)](https://huggingface.co/datasets/zhongyihuang/bangdream-hotword-bench)
[![GitHub](https://img.shields.io/badge/GitHub-code%20%26%20skill-black?logo=github)](https://github.com/HudsonHuang/bangdream-hotword-bench)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey)](LICENSE)
[![Samples](https://img.shields.io/badge/samples-283-blue)](#数据)
[![Audio](https://img.shields.io/badge/audio-32.6min-orange)](#数据)
[![Chunked audio](https://img.shields.io/badge/chunked%20audio-37.3min-red)](#数据)
[![v0.3 clips](https://img.shields.io/badge/v0.3-32%20clips-green)](#v03--流式黄金集)
[![v0.3 cues](https://img.shields.io/badge/v0.3-1525%20cues-green)](#v03--流式黄金集)
[![v0.3 audio](https://img.shields.io/badge/v0.3-92.4min-green)](#v03--流式黄金集)

# bangdream-hotword-bench

邦多利烤肉场景专用的人名热词库，以及配套的 **ASR / 同传 / 流式** 测试集。

我们把 BanG Dream! / 梦限大 MewType 直播里常出现的 **17 组人名与乐队名**做成「最小完备读音」热词表，
并从真实直播里开源了三套测试数据：

- **v0.1 · 283 条句级切片**：每条一个自然字幕句（≤30 秒），标专名正/负样本，测「名字有没有转对/译对」；
- **v0.2 · dense-20**：20 分钟不切片的连续直播（181 句 / 85 处专名提及），测连续流召回；
- **v0.3 · gold-v0.3（手标黄金集）**：**32 条完整高光、92.4 分钟、1,525 条人工精标中文 cue**，
  其中 **600+ 条 cue 被人工逐条修正**（说话人 / 细分 / 译文），同时测**回显节奏、翻译质量、热词质量**。

### 开源数据总览

| 版本 | 数据 | 规模 | 评什么 |
|---|---|---:|---|
| v0.1 | 283 条句级切片 + 37.3 分钟拼接流 | 32.6 分钟 / 283 条 | ASR 专名、同传专名 |
| v0.2 | dense-20 连续直播 | 20 分钟 / 181 句 / 85 处提及 | 连续流召回、虚警 |
| **v0.3** | **32 条完整高光 + 人工中文 SRT** | **92.4 分钟 / 1,525 cue / 600+ 条人工修正** | **回显节奏 + charF1 + 热词** |

- 📖 **热词**：`ymmt_hotwords_v0.1`（读音基元 + 组合规则 + 中文译名 + 英文名），含中英文标准热词与各 ASR 后端导出
- 🎧 **v0.1**：单套 test-base，283 条句级音频（141 pos / 142 neg），15 组，来自 215 个公开 YouTube 直播
- 🎬 **v0.1 长音频**：283 条按句拼接（句间 1 秒静音）成 37.3 分钟分片音频 + 每条句子的时长轴
- 🧵 **v0.2**：dense-20，20 分钟不切片的直播（181 句 / 85 处专名提及）
- 🏅 **v0.3**：32 条完整高光（92.4 分钟），16 kHz WAV + 人工精标中文 SRT（1,525 cue）
- 🧪 **评测**：模型无关的评测 skill，三种口径（ASR / 同传 / 流式）
- 📊 **结果**：v0.1/v0.2 热词指标、v0.3 节奏/质量/热词指标见下文

## 数据怎么构建的

```text
YouTube 公开直播（约 1785 个视频 / 3221 小时日语语料）
        │
        │ ① 自动字幕 + 音频
        ▼
读音匹配挖候选  ──  每个名字的全部读法（むげんだい / みゅーたいぷ / ゆめみた …）
        │
        │ ② 10 分钟上下文裁决（双模型 + 复核）
        ▼
pos / neg 标注  ──  pos：音频在说这个名字；neg：同音普通词（無限大 / 夢見た / 迷子 …）
        │
        │ ③ 取命中句的自然字幕句段（≤30s），每组 10 pos + 10 neg
        ▼
283 条句级音频 + 标注
        │
        │ ④ 句间 1s 静音拼接 → 37.3 分钟长音频 / 视频 + 每句时间轴
        ▼
test-base（音频 + 视频 + 标注 + 来源信息）
```

热词表同样由「读音基元 + 组合规则」生成，例如：

```text
むげんだい + みゅーたいぷ  →  夢限大 / ミュータイプ / 夢限大みゅーたいぷ / ゆめみた
のの + ちゃん/ちん/たん    →  ののちゃん / ののちん / ののたん / のんちゃん / のーちゃん
```

## 三种测试口径

三种口径都**从音频出发**，区别在终点：

- **ASR 模式**：测量「音频 → 日文转写」——模型直接听音频输出日文，看专名有没有被正确转写、负样本有没有被误触发。
- **同传模式**：测量「音频 → 最终中文」——模型从音频得到最终中文（可以先 ASR 再翻译，也可以音频直接出中文），看专名有没有被正确译出、负样本有没有被误触发。
- **流式模式（v0.3）**：测量「音频 → 带时间轴的中文」——除了中文质量/热词，还看中文第一次出现离参考句结束多远、相邻两次上屏隔多久。

## 当前指标

| ASR 前端 | ASR 模式 pos | ASR 模式 neg 未误触发 | 同传模式 pos | 同传模式 neg 未误触发 |
|---|---|---|---|---|
| 火山 ASR2 | 85.8% | 99.3% | 89.4% | 91.5% |
| qwen-audio-3.1（+context 热词） | 88.6% | 99.3% | 94.3% | 96.5% |

- ASR 模式 pos 为宽松口径（严格档：ASR2 74.5%、qwen 81.6%）；同传模式当前做法：ASR 转写 → 翻译 prompt（DeepSeek subagent + 中文热词表）→ 中文；
- 逐组指标与错例在 [results/](results/)；打分细节在 [docs/EVALUATION.md](docs/EVALUATION.md)。

**v0.3 流式黄金集（2–5 分钟，`9u5-VQG61So_hl04` 的 120–300 秒）：**

| 配置 | coverage | first-zh p50 | mean | charF1 | 人名召回 | 成本 |
|---|---:|---:|---:|---:|---:|---:|
| Paraformer + qwen3.8-max | 95.7% | 1.77 s | 1.39 s | 0.430 | 76.9% | 2.71 元/h |
| qwen-audio-3.1 + reference | 91.5% | 1.34 s | 0.72 s | 0.445 | 92.3% | 2.74 元/h |
| qwen-audio-3.1 + ICL + 1 轮上下文 | 91.5% | 1.42 s | 0.76 s | 0.456 | 84.6% | 3.68 元/h |

完整 32 条的口径与跑法见 [skill/docs/GOLD03.md](skill/docs/GOLD03.md)。

## 数据

三套数据都在 Hugging Face；v0.1/v0.2 偏热词评测，v0.3 是手标流式黄金集。

单套 `test-base`：15 组，每组最多 10 pos + 10 neg（不足按可用量）。
视频/长音频按组排列：先 5 位成员、再乐队；组内先 pos 后 neg。

| 项 | 值 |
|---|---|
| 样本 | 283（141 pos / 142 neg） |
| 音频 | 句级片段 32.6 分钟（≤30s/条） |
| 长音频 | 37.3 分钟（句间 1s 静音） |
| 长音频分片 | 37.3 分钟，1 个 1 小时分片（`audio_1h/`） |
| 源视频 | 215 个公开 YouTube 直播 |
| **dense-20（v0.2）** | 20 分钟连续音频，181 句，85 处专名提及，13 组；见 `skill/docs/DENSE20.md` |
| **gold-v0.3** | 32 条完整高光，92.4 分钟，16 kHz WAV + 1,525 条人工精标中文 cue；见 `skill/docs/GOLD03.md` |

```json
{
  "sample_id": "p_arale_pos_--7cN8iGGB4_5552",
  "split": "test-base",
  "group": "p_arale",
  "label": "pos",
  "variant": "あられ",
  "ja_ref": "はい。あられちゃん、どうでしたか?",
  "allowed_zh": ["阿拉蕾", "阿拉蕾酱"],
  "name_forms_zh": ["阿拉蕾"],
  "youtube_id": "--7cN8iGGB4",
  "source_start_s": 5552.36,
  "source_end_s": 5555.02,
  "duration_s": 3.15,
  "audio": "audio/p_arale_pos_--7cN8iGGB4_5552.m4a",
  "chunk_audio": "audio_1h/test-base_01_of_01.m4a",
  "chunk_start_s": 12.34,
  "chunk_end_s": 15.49
}
```

- `label=pos`：音频里在说该专名；`label=neg`：同音但为普通词/其他词。
- `ja_ref` 是 YouTube 自动字幕文本，仅用于定位，不是金标转写。
- 音频切片在 `audio/`，37.3 分钟拼接分片在 `audio_1h/`；`data/stream_timeline.json` 给出整段流式时间轴。
- 本地生成的逐句标注视频（37.3 分钟）帧上显示每条句子的 `UTT ID`、`是否包含热词`、`名字组`，
  以及热词/同音词出现的起止时间（`热词出现: 00:12–00:15`，分:秒）；1 秒静音段显示 `silence: 1s`。
  视频会随版本迭代频繁变化，因此不随数据集发布；音频切片与长音频即评测所需全部音频。

## v0.2 · dense-20 连续片段

v0.1 的 283 条是句级切片，每条一个判定；v0.2 补一段 **20 分钟连续直播**（`ew-HkuFPUcg` 第 7200–8400 秒），
不切片、保留时间轴，用来测真实运行时的召回与断句差异：

| 文件 | 说明 |
|---|---|
| `audio/dense-20/dense20_01_of_01.m4a`（HF） | 20 分钟连续音频 |
| `data/dense20.jsonl` | 85 条可评分样本（句 × 组） |
| `data/dense20_units.json` | 181 个参考句（含 124 个无专名句，用于虚警判定） |
| `data/dense20_transcript.jsonl` | 语义校正后的日/中参考转写 |

评分：`skill/scripts/score_mentions.py`（mention-level，按句 × 组）；与 v0.1 合并的参考结果见
[results/dense20_results.md](results/dense20_results.md)，跑法见 [skill/docs/LIVE_INTERP.md](skill/docs/LIVE_INTERP.md)。

## v0.3 · 流式黄金集（gold-v0.3）

v0.2 还是「一段连续直播」；v0.3 换成 **32 条人工精修过的完整高光**，每条都有自己的 WAV + 中文 SRT，
用来同时看流式系统最关心的三件事：

- **回显节奏**：中文第一次出现离参考句结束多远；
- **翻译质量**：中文和人工译文的字符 F1；
- **热词质量**：参考句里的人名/乐队名有没有出现在中文里。

构建方式：从已发布的高光成品直接取音轨（不重新切片，天然对齐），再对 SRT 做人工说话人归属、
长句细分和译文修正；1,525 条 cue 中有 **600+ 条被人工逐条改过**。

| 文件 | 说明 |
|---|---|
| `gold-v0.3/audio/*.wav`（HF） | 32 条，16 kHz mono，113–991 秒，共 92.4 分钟 |
| `gold-v0.3/srt/*.srt`（HF） | 人工修正中文 SRT，cue 带 `[speaker=arl|myk|nnk|ritsu|yuno]` |
| `skill/data/gold_v03.jsonl` | 32 条机器可读清单（时长、cue 数、说话人、点名次数、文件路径） |
| `skill/scripts/eval_stream.py` | 节奏 / 字符 F1 / 人名召回三合一打分 |
| `skill/docs/GOLD03.md` | 口径、跑法、参考结果 |

2–5 分钟参考结果（`9u5-VQG61So_hl04` 的 120–300 秒）：

| 配置 | coverage | first-zh p50 | mean | charF1 | 人名召回 | 成本 |
|---|---:|---:|---:|---:|---:|---:|
| Paraformer + qwen3.8-max | 95.7% | 1.77 s | 1.39 s | 0.430 | 76.9% | 2.71 元/h |
| qwen-audio-3.1 + reference | 91.5% | 1.34 s | 0.72 s | 0.445 | 92.3% | 2.74 元/h |
| qwen-audio-3.1 + ICL + 1 轮上下文 | 91.5% | 1.42 s | 0.76 s | 0.456 | 84.6% | 3.68 元/h |

完整结果与复现命令：`results/gold03_results.md`、`skill/docs/GOLD03.md`。

## 怎么用

### 1. 加载数据

```python
from datasets import load_dataset

ds = load_dataset("zhongyihuang/bangdream-hotword-bench", "test_base")
row = ds["train"][0]
print(row["audio"], row["allowed_zh"])

gold = load_dataset("zhongyihuang/bangdream-hotword-bench", "gold_v03")
print(gold["train"][0]["clip_id"], gold["train"][0]["cues"])
```

### 2. 拿热词表

| 文件 | 用途 |
|---|---|
| `hotwords/ymmt_hotwords_v0.1.json` | 权威定义：读音基元 + 组合规则 + 中文译名 + 英文名 |
| `hotwords/hotwords_zh_en_v0.1.json` | 中英文标准热词（日文名 → 中文译名 / 英文名） |
| `hotwords/zh_hotwords.json` / `hotwords/mt_glossary.txt` | 同传/翻译词表（喂给翻译 prompt） |
| `hotwords/export/volc_context.json` | 火山 ASR2 的 `request.corpus.context` |
| `hotwords/export/qwen_vocabulary.json` / `qwen_context.txt` | qwen ASR 的 vocabulary / context |
| `hotwords/export/moss_hotwords.csv` | MOSS 的 `--hotwords-csv` |

### 3. 评测

```bash
git clone https://github.com/HudsonHuang/bangdream-hotword-bench
cd bangdream-hotword-bench/skill

python scripts/eval.py --task asr --submission my_asr.jsonl   # ASR 模式
python scripts/eval.py --task zh  --submission my_zh.jsonl    # 同传模式
```

提交格式：JSONL，每行 `{"sample_id": "...", "text": "模型输出"}`；先跑 `scripts/validate_submission.py` 校验。

### 4. 官方验证

- 测试集：Hugging Face 上的这一套数据（`data/test_base.jsonl` + `audio/` + `video/`）；
- 验证：把模型输出的 JSONL（转写或中文结果）发到 **l_a@live.cn**，附模型名、解码参数、模式（asr/zh）、
  是否使用热词；我们会用同一套脚本复算并返回报告。

## 仓库结构

```text
.
├── skill/                  # 模型无关的评测 skill（eval / 校验 / 扩名字 / 翻译批处理）
│   ├── scripts/            # eval.py · score_mentions.py · eval_stream.py · run_parallel.py · validate_submission.py …
│   ├── data/               # test_base.jsonl（283 条）+ dense20*.json（v0.2）+ gold_v03.jsonl（v0.3）
│   ├── hotwords/           # 热词与各后端导出
│   └── docs/               # 打分规则 / 提交 / 扩展新名字 / 翻译链路 / v0.3 黄金集
├── hotwords/               # 热词库（可直接下载）
├── docs/                   # 数据集说明（DATASET.md）与评测协议（EVALUATION.md）
├── results/                # 当前指标（JSON + Markdown）
└── LICENSE / LICENSE-CODE  # 标注与热词 CC BY-NC 4.0；代码 MIT
```

## 来源与许可

- 音频/视频来自公开可见的 YouTube 直播；会员限定、私享、下架视频已剔除，每条样本可追溯到 YouTube ID + 起止时间。
- 标注、元数据、热词：**CC BY-NC 4.0**（仅非商业用途）；代码：MIT。
- 音频/视频版权归原始创作者/权利人，仅限非商业研究与评测；权利人可要求下架，见数据集里的 `AUDIO_TERMS.md`。
- 反馈与验证：**l_a@live.cn**

## 引用

```bibtex
@misc{bangdream-hotword-bench,
  title  = {bangdream-hotword-bench: Proper-Noun Hotwords and ASR/Translation Benchmark for BanG Dream! Fan Translation},
  author = {Hudson Huang},
  year   = {2026},
  url    = {https://huggingface.co/datasets/zhongyihuang/bangdream-hotword-bench}
}
```

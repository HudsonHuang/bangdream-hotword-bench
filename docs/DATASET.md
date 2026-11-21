# 数据集说明

## 内容

单套测试集 `test-base`：15 组（5 位成员 + 10 个乐队），每组最多 10 pos + 10 neg，共 **283 条**句级音频。

| 项 | 值 |
|---|---|
| 样本 | 283（141 pos / 142 neg） |
| 音频 | 句级片段，32.6 分钟（每条 ≤30s） |
| 长音频 | 37.3 分钟（句间 1s 静音） |
| 视频 | 37.3 分钟，1 个分片（静态帧） |
| 源视频 | 215 个公开 YouTube 直播 |

音频与视频在 Hugging Face：https://huggingface.co/datasets/zhongyihuang/bangdream-hotword-bench

## 字段

```json
{
  "sample_id": "p_arale_pos_--7cN8iGGB4_5552",
  "split": "test-base",
  "group": "p_arale",
  "label": "pos",
  "difficulty": "pos|hard|easy",
  "variant": "あられ",
  "ja_ref": "はい。あられちゃん、どうでしたか?",
  "allowed_zh": ["阿拉蕾", "阿拉蕾酱"],
  "name_forms_zh": ["阿拉蕾"],
  "youtube_id": "--7cN8iGGB4",
  "source_start_s": 5552.36,
  "source_end_s": 5555.02,
  "duration_s": 3.15,
  "audio": "audio/<sample_id>.m4a",
  "video": "video/test-base_01_of_01.mp4",
  "video_start_s": 12.34,
  "video_end_s": 15.49,
  "source": {"video_id": "...", "youtube_url": "...", "title": "...", "channel": "...", "upload_date": "..."}
}
```

- 每条 = 一个自然字幕句段（≤30s），切片时保留 0.25s 边缘余量。
- `label=pos`：音频里在说该专名；`label=neg`：同音但为普通词/其他词。
- `video_start_s/end_s`：该句在 37.3 分钟视频（流式分片）中的起止时间。
- `ja_ref` 是 YouTube 自动字幕文本，仅用于定位，不是金标转写。

## 构建流程

1. YouTube 公开直播的日语自动字幕（约 1785 视频 / 3221 小时）做读音匹配，挖出候选命中点；
2. 10 分钟窗口上下文裁决（双模型 + 复核），保留 pos；同音普通词为 neg；
3. 每组最多 10 pos + 10 neg、同视频最多 1 条；
4. 取命中句的自然字幕句段（t_start–t_end，≤30s），从源音频切出；
5. 按稳定顺序拼接（句间 1s 静音），生成 37.3 分钟长音频与静态帧视频，并记录每句的视频内时间轴。

## 已知噪声

- pos 标签经上下文裁决 + 多模型复核，仍有个别错误；发现请反馈 l_a@live.cn。
- `ja_ref` 为粗识别文本，不是金标。
- 只覆盖 15 组可用名字（millsage / 一家Dumb Rock! 正样本不足未发布）。

## v0.3 · gold-v0.3 流式黄金集

32 条完整高光，16 kHz mono WAV + 人工修正中文 SRT（1,525 cue，带说话人标签），共 92.4 分钟。

| 项 | 值 |
|---|---|
| 片段 | 32 |
| 音频 | 92.4 分钟，16 kHz mono WAV |
| 字幕 | 1,525 条中文 cue；600+ 条被人工改过 |
| 用途 | 回显节奏 + 翻译质量 + 热词，三合一 |

文件在 HF 的 `gold-v0.3/` 下；清单 `skill/data/gold_v03.jsonl`；口径与跑法见 `skill/docs/GOLD03.md`。

## 许可

- 标注、元数据、热词：CC BY-NC 4.0（非商业）。
- 音频/视频片段：版权归原权利人，仅限非商业研究与评测；下架请联系 l_a@live.cn。

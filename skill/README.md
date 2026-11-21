# bangdream-hotword-bench · 发布包说明

邦多利烤肉场景的人名热词库 + ASR / 同传测试集。

## 内容

| 内容 | 位置 | 说明 |
|---|---|---|
| 热词 | `hotwords/` | ymmt_hotwords_v0.1（读音基元+组合规则）、中英文标准热词、翻译词表、各 ASR 后端导出 |
| 测试集标注 | `data/test_base.jsonl` | 283 条句级样本（141 pos / 142 neg），每条带 YouTube ID、源时间与视频内时间 |
| dense-20（v0.2） | `data/dense20*.json` | 20 分钟连续片段，181 句 / 85 处专名提及 |
| gold-v0.3 | `data/gold_v03.jsonl` | 32 条完整高光（92.4 分钟）清单；WAV + 人工 SRT 在 HF |
| 音频 / 视频 | Hugging Face | https://huggingface.co/datasets/zhongyihuang/bangdream-hotword-bench |
| 评测 skill | `scripts/` | `--task asr`、`--task zh`、`eval_stream.py`（v0.3 节奏/质量/热词） |

## 测试集

单套 `test-base`：15 组，每组最多 10 pos + 10 neg（不足按可用量），
每条 = 一个自然字幕句段（≤30s）。全量 283 条：

- 音频总长 32.6 分钟；源视频 215 个；
- 拼接后整段 37.3 分钟（句间 1s 静音），按 1 小时分片 = 1 个分片；
- 同时提供 37.3 分钟视频（静态帧）与每条句子的视频内起止时间。

## 样本字段（JSONL 每行一条）

```json
{
  "utt_id": "p_arale_pos_--7cN8iGGB4_5552",
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
  "audio": "audio/<utt_id>.m4a",
  "video": "video/test-base_01_of_01.mp4",
  "video_start_s": 12.34,
  "video_end_s": 15.49,
  "source": {"video_id": "...", "youtube_url": "...", "title": "...", "channel": "...", "upload_date": "..."}
}
```

- `label=pos`：音频里在说该专名；`label=neg`：同音但为普通词/其他词。
- `ja_ref` 是 YouTube 自动字幕文本，仅用于定位，不是金标转写。
- `video_start_s/end_s`：该句在 37.3 分钟视频（及流式分片）中的起止时间。

## 两种测试模式

1. **ASR 模式**（`--task asr`）：音频 → 日文转写；pos 看专名是否出现，neg 看是否被误触发。
2. **同传模式**（`--task zh`）：音频 → 最终中文（ASR→翻译 或 直接同传）；pos 看 `allowed_zh` 是否命中，neg 看是否出现中文专名。

## 提交验证

```bash
python scripts/validate_submission.py --submission my_output.jsonl
```

通过后发到 **l_a@live.cn**，附模型名、解码参数、模式、是否使用热词。

## 许可

- 标注、元数据、热词：CC BY-NC 4.0（仅非商业用途）。
- 代码：MIT。
- 音频/视频版权归原权利人，仅限非商业研究与评测；下架联系 l_a@live.cn。

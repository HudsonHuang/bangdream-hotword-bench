# 提交格式与验证流程

## 提交文件

JSONL（UTF-8），一行一条样本：

```json
{"sample_id": "p_arale_pos_--7cN8iGGB4_5552", "text": "はい、あられちゃん、どうでしたか？"}
```

- `sample_id` 必须来自 `data/test/samples_test.jsonl`；
- `text` 是模型输出（`translation` / `zh` 也可作为字段名）；
- 默认要求覆盖全部 283 条（`--allow-missing` 可放宽；官方验证要求全覆盖）。

## 两种测试模式

| 口径 | `text` 内容 | 示例 |
|---|---|---|
| `asr`（ASR 模式） | 日文转写 | `夢限大ミュータイプさんの方が規模でかいです` |
| `zh`（同传模式） | 最终中文（ASR→翻译 或 直接同传） | `梦限大MewType的规模更大一些` |

## 校验与本地评分

```bash
python scripts/validate_submission.py --submission my_asr.jsonl
python scripts/eval.py --task asr --submission my_asr.jsonl
python scripts/eval.py --task zh  --submission my_zh.jsonl
```

校验会检查：JSON 可解析、sample_id 覆盖/重复、text 类型、空输出统计。

## 提交评测

把以下内容发到 **l_a@live.cn**：

1. 通过校验的提交文件（JSONL，gzip 也可以）；
2. 模型名 + 版本；
3. 解码参数（温度、beam、是否用热词/词表、是否流式）；
4. 口径（`asr` 或 `zh`）；
5. 若使用热词：说明热词来源（例如 `ymmt_hotwords_v0.1` 全量 / 仅导出格式）。

我们会用同一套 `scripts/eval.py` 复算，并返回 `report.md` 与 `suspects.jsonl`。

## 注意事项

- 只有一套测试集；不要在测试集上拟合热词权重后宣称泛化。
- 若结果与自评不一致，优先检查：热词注入是否真的生效、文本字段名、是否覆盖全部样本。

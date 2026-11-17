# 评测协议

benchmark 只判最终文本，模型无关。两种测试模式都从音频出发，区别在终点。

## 1. ASR 模式（`--task asr`）

测量「音频 → 日文转写」的准确性。

提交：JSONL，每行 `{"sample_id": "...", "text": "日文转写"}`。

- **正样本（pos）**
  - 严格档：转写中出现该样本 `variant` 的读音（假名，长音归一）且按词边界对齐，或出现该 variant 的日文写法；
  - 宽松档：额外接受该组规范写法（如 `MyGO`、`アヴェムジカ`），以及长音/促音小差异、≥3 音的子串命中。
- **负样本（neg）**
  - 转写中出现该组无歧义专名形态 → 过触发（错）；
  - 同音普通词（無限大、夢見た、迷子、湯の、確率 等）不算专名；
  - 空转写单独统计（`empty`），不算 neg 通过。

指标：`pos_rate`（宽松）、`pos_strict_rate`、`neg_rate`（未误触发）。

## 2. 同传模式（`--task zh`）

测量「音频 → 最终中文」的准确性。

提交：JSONL，每行 `{"sample_id": "...", "text": "中文结果"}`（`translation` / `zh` 字段也可）。
来源可以是「ASR→翻译」或「音频→中文同传」，只看中文输出。

- **正样本**：输出包含该样本 `allowed_zh` 中任意一项（宽松档额外接受该组规范译名/别名）。
- **负样本**：输出不得包含该组 `name_forms_zh` / 规范中文译名；空输出单独统计。

中文热词表见 `hotwords/zh_hotwords.json` 和 `hotwords/mt_glossary.txt`；
翻译链路见 `skill/docs/MT_PIPELINE.md`。

## 3. 提交与验证

1. 本地校验：`python skill/scripts/validate_submission.py --submission my.jsonl`
2. 本地评测：`python skill/scripts/eval.py --task asr|zh --submission my.jsonl`
3. 官方验证：把通过校验的提交文件发到 **l_a@live.cn**，附模型名、解码参数、模式（asr/zh）、是否使用热词。

## 4. 说明

- 只有一套测试集，避免调参泄漏；不要在测试集上拟合热词权重后宣称泛化。
- 打分脚本对中文/日文名称做归一化（全半角、片假名→平假名、长音）；英文名忽略空格与大小写。
- 空输出、缺样本都会在报告中单列，不会静默算分。

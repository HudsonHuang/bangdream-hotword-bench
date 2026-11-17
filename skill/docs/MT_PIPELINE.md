# 翻译/同传评测的跑法（DeepSeek subagent 或任意翻译器）

中文口径 `--task zh` 不关心翻译器是谁：只要拿到「中文输出 JSONL」就能打分。
本评测集的翻译链路使用 **DeepSeek subagent**（文本输入）；
翻译评测流程：**ASR（或参考文本）→ DeepSeek subagent 翻译 → 中文输出 → eval.py --task zh**。

## 流程

```bash
# 0) 先有 ASR 提交（或任意日语文本）：my_asr.jsonl = {"sample_id","text"}
# 1) 切翻译任务（每批 50 条；jobs/batch_XX.json 输入，out/batch_XX.jsonl 输出）
python scripts/mt_batches.py split --asr my_asr.jsonl --out-dir mt_jobs --batch-size 50

# 2) 交给翻译器（DeepSeek subagent / API / 本地模型），逐批产出 out/batch_XX.jsonl
#    输入: [{"sample_id","ja"}]
#    输出: {"sample_id","text"}   （每行一条，顺序一致）
#    翻译要求（发给翻译器的 prompt 要点）：
#      - 口语化简体中文，不解释、不译注、不合并/拆分条目
#      - 专有名词严格按 hotwords/mt_glossary.txt（日文名 = 规范译名；# 后为可接受别名）
#      - 表里没有的人名/乐队名保留日文或音译，不要意译

# 3) 汇总并自检
python scripts/mt_batches.py merge --out-dir mt_jobs --out my_zh.jsonl

# 4) 中文口径评测
python scripts/eval.py --task zh --submission my_zh.jsonl
```

## 与「音频→中文同传」的关系

同传系统是「音频直接出中文」，同样只评测最终中文输出，因此**用同一个 judge**
（`--task zh`）；区别只在提交文件是怎么产生的：
- 离线 ASR+翻译：ASR 转写 → 翻译 → 中文
- 同传/端到端：模型直接吃音频 → 中文

## DeepSeek subagent 翻译的实操建议

- 每批 40–60 条（约 1.5 万字），模型一次上下文即可覆盖；批太大容易漏条目；
- 要求翻译器输出**逐行 JSONL**而不是表格/段落，便于机械校验；
- 汇总后先跑 `merge`，缺条会报错；再跑 `validate_submission.py` 确认覆盖全部测试样本；
- 若要复现「官方验证」，把 `my_zh.jsonl` 发到 l_a@live.cn，并注明 ASR 模型与翻译器版本。

## 中文热词

`hotwords/zh_hotwords.json` / `mt_glossary.txt` 是翻译侧的规范译名（日文专名 → 中文），
包含别名（如 梦限大MewType / 梦限大）。热词是「允许译名」的集合：
pos 命中别名任意一个都算对，neg 出现专名即过触发。

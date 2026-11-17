# 扩展新名字 / 新乐队

skill 支持持续扩充：新增名字只改热词与标注，不动评测代码。

## 步骤

### 1. 写 spec 并加入热词

`new_names.json`（数组，每个元素一组；字段与现有组一致）：

```json
[
  {
    "id": "b_newband",
    "kind": "band",
    "canonical_ja": "新しいバンド",
    "canonical_zh": ["新乐队"],
    "units": [
      {"reading": "あたらしい", "ja": ["新しい", "あたらしい"], "zh": ["新"]},
      {"reading": "ばんど", "ja": ["バンド", "band"], "zh": ["乐队"]}
    ],
    "compose": [
      {"parts": ["あたらしい", "ばんど"], "ja": ["新しいバンド"], "zh": ["新乐队"]}
    ],
    "asr_error_ja": [],
    "neg_check_forms": ["新しいバンド"],
    "zh": {
      "aliases": ["新乐队"],
      "name_forms_zh": ["新乐队"],
      "variant_zh": {"あたらしいばんど": ["新乐队"]}
    }
  }
]
```

```bash
python scripts/add_names.py --spec new_names.json \
    --samples data/test/samples_test.jsonl     # 有标注时顺便校验覆盖率
```

会做：
- 校验 group id 唯一、读音为纯假名、compose/suffix 引用的单元存在；
- 展开派生形态（units / compose / suffix / special），生成 `asr_words_ja`、`name_forms_ja`；
- 重建 `hotwords/reading_index.json`、`hotwords/zh_hotwords.*`、`hotwords/export/*`
  （Volc ASR2 / Qwen vocabulary+context / MOSS csv / 翻译词表）；
- 若给了 `--samples`，检查新组的 pos variant 是否都被派生形态覆盖。

> 关键约定：
> - `neg_check_forms` 必须手填「不会与普通词歧义」的形态（例如乐队全名/缩写），
>   否则 neg 会被普通词误伤；
> - `variant_zh` 决定中文口径严格档：只放**语音实际说出那部分名字**对应的译名
>   （例：语音 `むげんだい` 可接受「梦限大 / 梦限大MewType」，不接受单独「MewType」）。

### 2. 从粗 ASR 转写里挖候选

```bash
python scripts/mine_candidates.py \
    --transcripts /path/to/rough_asr/ \       # JSONL 或每视频一个 JSON（见脚本 docstring）
    --groups b_newband \
    --out candidates_newband.jsonl
```

输出每行：`{group, variant(读音), surface(命中写法), video_id, t_start, text}`。

### 3. 标注

对候选做上下文裁决：
- **pos**：音频中该词确实指这个专名（含缩写/昵称/同音近音变体）；
- **neg**：同音但为普通词/其他人名（记 `difficulty=easy` 若为子词/普通词近音）。

按 `data/test/samples_test.jsonl` 的字段补标注（至少：`utt_id, group, label, difficulty, variant, ja_ref, allowed_zh/name_forms_zh, youtube_id, source_start_s, source_end_s, duration_s, split`）。

### 4. 切片

```bash
python scripts/clip_audio.py --samples new_samples.jsonl \
    --source-dir /path/to/source_audio --out /path/to/clips \
    --manifest /path/to/clips_manifest.jsonl
```

### 5. 验证 & 评测

```bash
python scripts/validate_submission.py --submission my_submission.jsonl
python scripts/eval.py --task asr --submission my_submission.jsonl \
    --samples new_samples.jsonl
```

## 建议

- 新名字先加 3–5 个读音变体做冒烟（派生读音数、neg_check_forms），再扩量；
- 每次改热词都跑 `add_names.py --dry-run` 看派生结果；
- 名字跨语言（英文名、罗马字）时 `units.ja` 里同时放英日写法，中文口径在 `zh.aliases` 补译名。

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扩展 ymmt_hotwords：向标准热词里追加新名字/乐队（读音基元 + 组合规则）。

输入 spec JSON（数组，每个元素是一个组）:
[
  {
    "id": "p_newmember",                  # 唯一 id，建议 p_/b_ 前缀
    "kind": "person",                     # person | band
    "canonical_ja": "新メンバー",
    "canonical_zh": ["新成员"],
    "units": [                            # 最小读音基元（kana），可多个
      {"reading": "しん", "ja": ["新"], "zh": ["新"]},
      {"reading": "めんばー", "ja": ["メンバー", "メンバ"], "zh": ["成员"]}
    ],
    "compose": [                          # 可选：单元拼接（如 夢限大+みゅーたいぷ）
      {"parts": ["しん", "めんばー"], "ja": ["新メンバー"], "zh": ["新成员"]}
    ],
    "suffix": [                           # 可选：单元+后缀（如 のの+ちゃん）
      {"base": "めんばー", "suffixes": {"ちゃん": ["成员酱"]}}
    ],
    "asr_error_ja": ["新メンバ"],          # 已知 ASR 误写（可选，打分时用于识别「可恢复误写」）
    "neg_check_forms": ["新メンバー"],     # neg 过触发判定用的无歧义形态（务必手填，别放普通词）
    "zh": {"aliases": ["新成员"], "name_forms_zh": ["新成员"], "variant_zh": {"しんめんばー": ["新成员"]}}
  }
]

用法:
  python scripts/add_names.py --spec new_names.json            # 写入热词并重建索引/导出
  python scripts/add_names.py --spec new_names.json --dry-run  # 只看校验和派生结果
  python scripts/add_names.py --spec new_names.json --samples data/test/samples_test.jsonl  # 额外校验覆盖率

完成后记得把新组加入测试集标注（pos/neg 样本）与音频，再跑 eval.py 验证。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import common  # noqa: E402

SKILL = os.path.dirname(HERE)
DEF_HOTWORDS = os.path.join(SKILL, "hotwords/ymmt_hotwords_v0.1.json")
KANA_ONLY = re.compile(r"^[ぁ-んーゝゞ]+$")


def derive_group(g: dict) -> dict:
    """展开 units/compose/suffix -> derived/asr_words/name_forms/readings。"""
    units = g.get("units") or []
    if not units:
        raise ValueError(f"{g.get('id')}: units 不能为空")
    by_reading = {u["reading"]: u for u in units}

    derived = []
    for u in units:
        _assert_reading(g, u["reading"])
        derived.append({"reading": u["reading"], "ja": list(u.get("ja") or []),
                        "zh": list(u.get("zh") or []), "source": "unit"})
    for c in g.get("compose") or []:
        parts = c.get("parts") or []
        for p in parts:
            if p not in by_reading:
                raise ValueError(f"{g['id']}: compose 引用了不存在的单元 {p}")
        derived.append({"reading": "".join(parts), "ja": list(c.get("ja") or []),
                        "zh": list(c.get("zh") or []), "source": "compose"})
    for sp in g.get("suffix") or []:
        base = by_reading.get(sp["base"])
        if base is None:
            raise ValueError(f"{g['id']}: suffix 引用了不存在的单元 {sp['base']}")
        for suf, zh in (sp.get("suffixes") or {}).items():
            _assert_reading(g, sp["base"] + suf)
            derived.append({
                "reading": sp["base"] + suf,
                "ja": [s + suf for s in (base.get("ja") or [])] + [sp["base"] + suf],
                "zh": list(zh or []), "source": "suffix",
            })
    for x in g.get("special") or []:
        _assert_reading(g, x["reading"])
        derived.append({"reading": x["reading"], "ja": list(x.get("ja") or []),
                        "zh": list(x.get("zh") or []), "source": "special"})

    asr_words = []
    for d in derived:
        for w in d["ja"]:
            if w and w not in asr_words:
                asr_words.append(w)
    name_forms = list(asr_words)
    for w in g.get("asr_error_ja") or []:
        if w and w not in name_forms:
            name_forms.append(w)
    readings = list(dict.fromkeys(d["reading"] for d in derived))

    zh_in = g.get("zh") or {}
    aliases = list(dict.fromkeys((zh_in.get("aliases") or []) + [z for d in derived for z in d["zh"]]))
    out = dict(g)
    out.update({
        "derived": derived,
        "asr_words_ja": asr_words,
        "name_forms_ja": name_forms,
        "readings": readings,
        "neg_check_forms": list(g.get("neg_check_forms") or []),
        "zh": {
            "canonical_zh": list(g.get("canonical_zh") or []),
            "aliases": aliases,
            "name_forms_zh": list(zh_in.get("name_forms_zh") or []),
            "variant_zh": dict(zh_in.get("variant_zh") or {}),
        },
    })
    if not out["neg_check_forms"]:
        print(f"WARN {g['id']}: neg_check_forms 为空，neg 样本将无法判过触发；建议手填无歧义形态",
              file=sys.stderr)
    return out


def _assert_reading(g: dict, reading: str) -> None:
    if not reading or not KANA_ONLY.match(reading):
        raise ValueError(f"{g.get('id')}: 读音必须为纯假名（含长音ー），得到 {reading!r}")


def rebuild_exports(doc: dict, hot_dir: str) -> None:
    """重建 reading_index + 各 ASR/翻译后端的导出格式。"""
    groups = doc["groups"]
    os.makedirs(os.path.join(hot_dir, "export"), exist_ok=True)
    all_bias, all_names = [], []
    for g in groups:
        for w in g["asr_words_ja"]:
            if w not in all_bias:
                all_bias.append(w)
        for w in g["name_forms_ja"]:
            if w not in all_names:
                all_names.append(w)

    json.dump({"hotwords": [{"word": w} for w in all_bias]},
              open(os.path.join(hot_dir, "export/volc_context.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump({w: 5 for w in all_bias},
              open(os.path.join(hot_dir, "export/qwen_vocabulary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    ctx = "、".join(all_bias)
    while len(ctx) > 400 and "、" in ctx:
        ctx = ctx[:ctx.rfind("、")]
    open(os.path.join(hot_dir, "export/qwen_context.txt"), "w", encoding="utf-8").write(ctx)
    open(os.path.join(hot_dir, "export/moss_hotwords.csv"), "w", encoding="utf-8").write(
        ",".join(all_bias))

    zh_groups, zh_flat, mt_lines = {}, [], []
    for g in groups:
        zh = g["zh"]
        zh_groups[g["id"]] = zh
        for z in [zh["canonical_zh"][0]] + list(zh["aliases"]):
            if z and z not in zh_flat:
                zh_flat.append(z)
        mt_lines.append(f'{g["canonical_ja"]} = {zh["canonical_zh"][0]}')
        if zh["aliases"]:
            mt_lines.append(f'  # 可接受：{"、".join(zh["aliases"])}')
    json.dump({"schema": "ymmt-hotwords/zh/v0.1",
               "note": "中文侧规范译名：pos 命中 aliases 之一算对；neg 不得出现 name_forms_zh",
               "groups": zh_groups},
              open(os.path.join(hot_dir, "zh_hotwords.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    open(os.path.join(hot_dir, "zh_hotwords.txt"), "w", encoding="utf-8").write(
        "\n".join(zh_flat) + "\n")
    with open(os.path.join(hot_dir, "mt_glossary.txt"), "w", encoding="utf-8") as f:
        f.write("日文专名 → 中文规范译名（翻译/同传评测用）\n")
        f.write("\n".join(mt_lines) + "\n")

    index = {
        "schema": "ymmt-hotwords/reading-index/v0.1",
        "groups": {
            g["id"]: {
                "canonical_ja": g["canonical_ja"], "canonical_zh": g["canonical_zh"],
                "readings": g["readings"], "name_forms_ja": g["name_forms_ja"],
                "neg_check_forms": g["neg_check_forms"], "zh": g["zh"],
                "readings_by_variant": {d["reading"]: {"ja": d["ja"], "zh": d["zh"],
                                                      "source": d["source"]}
                                        for d in g["derived"]},
            } for g in groups
        },
    }
    json.dump(index, open(os.path.join(hot_dir, "reading_index.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, help="新名字 spec JSON（数组）")
    ap.add_argument("--hotwords", default=DEF_HOTWORDS)
    ap.add_argument("--samples", default="", help="可选：校验新组是否覆盖样本 variant")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    doc = common.load_json(args.hotwords)
    spec = common.load_json(args.spec)
    if isinstance(spec, dict):
        spec = spec.get("groups") or [spec]
    existing = {g["id"] for g in doc["groups"]}

    added = []
    for raw in spec:
        gid = raw.get("id")
        if not gid or not re.match(r"^[a-z0-9_]+$", gid):
            raise SystemExit(f"非法 group id: {gid!r}（只允许小写字母/数字/下划线）")
        if gid in existing:
            raise SystemExit(f"group id 已存在: {gid}")
        g = derive_group(raw)
        doc["groups"].append(g)
        existing.add(gid)
        added.append(g)
        print(f"+ {gid} {g['canonical_ja']} -> {g['canonical_zh']} "
              f"units={len(g.get('units') or [])} readings={len(g['readings'])} "
              f"bias_words={len(g['asr_words_ja'])}")

    # 覆盖率校验（可选）：新组的 pos 样本 variant 必须可由派生读音/表面解释
    if args.samples:
        samples = [s for s in common.load_samples(args.samples) if s["group"] in existing]
        by_id = {g["id"]: g for g in doc["groups"]}
        missing = []
        for s in samples:
            if s["label"] != "pos":
                continue
            g = by_id[s["group"]]
            surfaces = set(g["readings"])
            for d in g["derived"]:
                surfaces.update(d.get("ja") or [])
            surfaces.update(g.get("asr_error_ja") or [])
            if s["variant"] not in surfaces:
                missing.append((s["sample_id"], s["variant"]))
        if missing:
            print(f"WARN 覆盖率: {len(missing)} 个 pos variant 不在热词派生里，例如 {missing[:5]}",
                  file=sys.stderr)

    if args.dry_run:
        print("dry-run：不写文件")
        return 0

    doc["updated"] = "add_names.py"
    hot_dir = os.path.dirname(os.path.abspath(args.hotwords))
    json.dump(doc, open(args.hotwords, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rebuild_exports(doc, hot_dir)
    print(f"已更新 {args.hotwords}（新增 {len(added)} 组，总 {len(doc['groups'])} 组）")
    print(f"已重建 {hot_dir}/reading_index.json 与 export/ 导出")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""bangdream-hotword-bench · 打分核心（独立、无第三方依赖，可选 fugashi 提升分词质量）。

只用标准库。若环境里安装了 fugashi+unidic-lite 则用 MeCab 做词边界/读音；否则退化为
「按文字种类切块 + 假名读数」的近似分词，仍能完成对齐匹配。

对外主要接口：
  load_hotwords(path)                -> dict（含 groups / by_id / 读音索引）
  load_samples(path)                 -> list[dict]
  read_submission(path)              -> list[dict]（JSONL）
  score_asr_sample(sample, group, text)  -> dict（日文转写打分）
  score_zh_sample(sample, group_zh, text) -> dict（中文端到端打分）
  summarize(samples, results)        -> dict（总体/分组指标 + suspects）
"""
from __future__ import annotations

import json
import os
import re
import unicodedata

# ---------------------------------------------------------------------------
# 归一化
# ---------------------------------------------------------------------------
_KATA = str.maketrans(
    "ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾタダチヂッツヅテデトドナニヌネノハバパヒビピフブプヘベペホボポマミムメモャヤュユョヨラリルレロヮワヰヱヲンヴヵヶヽヾ",
    "ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞただちぢっつづてでとどなにぬねのはばぱひびぴふぶぷへべぺほぼぽまみむめもゃやゅゆょよらりるれろゎわゐゑをんゔゕゖゝゞ",
)


def kata2hira(s: str) -> str:
    return (s or "").translate(_KATA)


KANA_RE = re.compile(r"^[ぁ-んーゝゞ]+$")
KANA_ANY_RE = re.compile(r"^[ぁ-んァ-ヶーゝゞ・]+$")

_KANA_ROW = {}
for _chars, _row in [
    ("あかさたなはまやらわがざだばぱぁゃゎ", "a"),
    ("いきしちにひみりゐぎじぢびぴぃ", "i"),
    ("うくすつぬふむゆるゔぐずづぶぷぅゅ", "u"),
    ("えけせてねへめれゑげぜでべぺぇ", "e"),
    ("おこそとのほもよろをごぞどぼぽぉょ", "o"),
]:
    for _c in _chars:
        _KANA_ROW[_c] = _row


def normalize_long_vowels(s: str) -> str:
    """把「ー」按前一元音行展开，统一 アフターグロウ / アフターグロー 这类差异。"""
    out = []
    for ch in s or "":
        if ch == "ー" and out:
            row = _KANA_ROW.get(out[-1])
            out.append({"a": "あ", "i": "い", "u": "う", "e": "え", "o": "う"}.get(row, "ー"))
        else:
            out.append(ch)
    return "".join(out)


_SMALL_KANA = "っッゃャゅュょョぁァぃィぅゥぇェぉォ"


def strip_small_kana(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch not in _SMALL_KANA)


def norm_text(s: str) -> str:
    """全半角/大小写归一（用于表面匹配）。"""
    return unicodedata.normalize("NFKC", s or "").lower()


def latin_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def is_kana(ch: str) -> bool:
    return bool(ch) and ("ぁ" <= ch <= "ん" or "ァ" <= ch <= "ヶ")


# ---------------------------------------------------------------------------
# 分词（可选 MeCab；fallback 按文字种类切块）
# ---------------------------------------------------------------------------
_TAGGER = None
_USE_MECAB = None


class Token:
    __slots__ = ("surface", "reading")

    def __init__(self, surface: str, reading: str):
        self.surface = surface
        self.reading = reading


def _get_tagger():
    global _TAGGER, _USE_MECAB
    if _USE_MECAB is None:
        if os.environ.get("BENCH_NO_FUGASHI", "").strip() in {"1", "true", "yes"}:
            _USE_MECAB = False
            return None
        try:
            from fugashi import Tagger  # type: ignore
            _TAGGER = Tagger()
            _USE_MECAB = True
        except Exception:
            _TAGGER = None
            _USE_MECAB = False
    return _TAGGER


_SCRIPT_RUN = re.compile(r"[ぁ-ん]+|[ァ-ヶー]+|[一-龥々〆]+|[A-Za-z0-9]+|[^\s]")


def tokenize(text: str):
    """返回 list[Token]；reading 均为 hiragana（未知汉字读作空串）。"""
    tagger = _get_tagger()
    tokens = []
    if tagger is not None:
        for w in tagger(text or ""):
            surf = w.surface or ""
            try:
                kana = w.feature.kana
            except Exception:
                kana = None
            rd = kata2hira(kana) if kana else (
                kata2hira(surf) if KANA_ANY_RE.match(surf) else "")
            tokens.append(Token(surf, normalize_long_vowels(rd)))
        return tokens
    for m in _SCRIPT_RUN.finditer(text or ""):
        surf = m.group(0)
        rd = kata2hira(surf) if KANA_ANY_RE.match(surf) else ""
        tokens.append(Token(surf, normalize_long_vowels(rd)))
    return tokens


def build_reading(tokens):
    chars, idx = [], []
    for k, t in enumerate(tokens):
        for ch in t.reading:
            if KANA_RE.match(ch):
                chars.append(ch)
                idx.append(k)
    return "".join(chars), idx


def aligned_forms(tokens, pattern: str):
    """pattern 在 token 边界对齐命中的表面串列表。"""
    if not pattern:
        return []
    reading, idx = build_reading(tokens)
    out = []
    start = 0
    while True:
        pos = reading.find(pattern, start)
        if pos < 0:
            break
        start = pos + 1
        end = pos + len(pattern) - 1
        if end >= len(idx):
            continue
        left_ok = pos == 0 or idx[pos] != idx[pos - 1]
        right_ok = end == len(idx) - 1 or idx[end] != idx[end + 1]
        if not (left_ok and right_ok):
            continue
        a, b = idx[pos], idx[end]
        out.append("".join(t.surface for t in tokens[a:b + 1]))
    return out


def surface_at_boundary(text: str, form: str) -> bool:
    """form 出现且两侧不是假名（避免 ブレイズ 里命中 レイズ 这类词内子串）。"""
    if not form or len(form) < 2:
        return False
    t, f = norm_text(text), norm_text(form)
    start = 0
    while True:
        i = t.find(f, start)
        if i < 0:
            return False
        start = i + 1
        before = t[i - 1] if i > 0 else ""
        after = t[i + len(f)] if i + len(f) < len(t) else ""
        if not is_kana(before) and not is_kana(after):
            return True


# ---------------------------------------------------------------------------
# 资源加载
# ---------------------------------------------------------------------------
def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_hotwords(path: str) -> dict:
    doc = load_json(path)
    groups = doc.get("groups") or []
    by_id = {g["id"]: g for g in groups}
    for g in groups:
        g.setdefault("neg_check_forms", list(g.get("asr_words_ja") or []))
        g.setdefault("zh", {})
        # 变体读音 -> 可接受的日文表面形态
        d = {}
        for x in list(g.get("derived") or []) + list(g.get("error_forms") or []):
            for ja in x.get("ja") or []:
                d.setdefault(x["reading"], [])
                if ja not in d[x["reading"]]:
                    d[x["reading"]].append(ja)
        g["_variant_surfaces"] = d
    return {"doc": doc, "groups": groups, "by_id": by_id}


def load_samples(path: str) -> list:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def read_submission(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{i} 不是合法 JSON: {e}") from e
    return rows


AUDIO_EXTS = (".m4a", ".mp3", ".wav", ".aac", ".ogg", ".flac", ".opus")


def check_submission(submission: list, samples: list, *, require_all: bool = True) -> list:
    """校验提交文件，返回错误列表（空 = 通过）。"""
    errors = []
    ids = {s["sample_id"] for s in samples}
    seen = set()
    for r in submission:
        sid = r.get("sample_id")
        text = r.get("text")
        if text is None:
            text = r.get("translation") if r.get("translation") is not None else r.get("zh")
        if not sid:
            errors.append("存在缺少 sample_id 的记录")
            continue
        if sid in seen:
            errors.append(f"重复 sample_id: {sid}")
        seen.add(sid)
        if sid not in ids:
            errors.append(f"未知 sample_id（不在测试集）: {sid}")
        if not isinstance(text, str):
            errors.append(f"{sid}: text 必须是字符串")
    if require_all:
        missing = ids - seen
        if missing:
            errors.append(f"缺少 {len(missing)} 条样本，例如: {sorted(missing)[:5]}")
    return errors


def audio_path(manifest_row: dict, data_dir: str = ".") -> str:
    rel = manifest_row.get("clip") or manifest_row.get("path") or ""
    return rel if os.path.isabs(rel) else os.path.join(data_dir, rel)


# ---------------------------------------------------------------------------
# 打分
# ---------------------------------------------------------------------------
def _sample_reading(sample: dict, group: dict) -> str:
    """样本 variant -> 读音（优先用 hotwords 里的表面→读音映射）。"""
    variant = sample.get("variant") or ""
    for rd, ja_list in (group.get("_variant_surfaces") or {}).items():
        if variant == rd or variant in ja_list:
            return rd
    if KANA_ANY_RE.match(variant):
        return kata2hira(variant)
    for x in group.get("derived") or []:
        if variant in (x.get("ja") or []):
            return x["reading"]
    return ""


def _sample_allowed_ja(sample: dict, group: dict) -> list:
    """该样本 variant 可接受的日文表面形态（更严格口径用）。"""
    variant = sample.get("variant") or ""
    rd = _sample_reading(sample, group)
    forms = set()
    if variant:
        forms.add(variant)
    for rd2, ja_list in (group.get("_variant_surfaces") or {}).items():
        if rd2 == rd:
            forms.update(ja_list)
    return [f for f in forms if f]


def score_asr_sample(sample: dict, group: dict, text: str) -> dict:
    """日文 ASR 转写打分。

    pos: strict = variant 的读音/表面命中；lenient = 额外接受该组规范写法（如 MyGO/アヴェムジカ）
    neg: 出现 neg_check_forms 中任一形态 = 过触发；空转写单列 empty
    """
    text = text or ""
    tokens = tokenize(text)
    reading = build_reading(tokens)[0]
    variant = sample.get("variant") or ""
    vr = normalize_long_vowels(_sample_reading(sample, group))
    allowed_ja = _sample_allowed_ja(sample, group)

    strict_surface = any(surface_at_boundary(text, f) for f in allowed_ja)
    strict_reading = bool(vr) and bool(aligned_forms(tokens, vr))
    strict = strict_surface or strict_reading

    lenient = strict
    if not lenient and vr:
        small = strip_small_kana(vr)
        lenient = ((len(vr) >= 3 and vr in reading)
                   or (len(small) >= 3 and small in strip_small_kana(reading)))
    if not lenient:
        canonical = False
        t_lat = latin_key(text)
        if t_lat:
            for f in group.get("neg_check_forms") or []:
                lf = latin_key(f)
                if len(f) >= 3 and lf and len(lf) >= 3 and lf in t_lat:
                    canonical = True
                    break
        if not canonical:
            for f in group.get("neg_check_forms") or []:
                if surface_at_boundary(text, f):
                    canonical = True
                    break
        if not canonical:
            # 规范写法的读音对齐（处理「アベムジカカバー」这类粘连）
            reverse = {}
            for rd2, ja_list in (group.get("_variant_surfaces") or {}).items():
                for ja in ja_list:
                    reverse.setdefault(ja, rd2)
            for f in group.get("neg_check_forms") or []:
                rd2 = reverse.get(f)
                if not rd2:
                    continue
                rd2 = normalize_long_vowels(rd2)
                if len(rd2) >= 3 and aligned_forms(tokens, rd2):
                    canonical = True
                    break
        if canonical:
            strict = lenient = True

    if sample.get("label") == "pos":
        return {"ok": lenient, "strict": strict, "lenient": lenient,
                "empty": not text.strip(), "match": ("strict" if strict else ("lenient" if lenient else ""))}

    bad = [f for f in (group.get("neg_check_forms") or []) if surface_at_boundary(text, f)]
    return {"ok": (not bad) and bool(text.strip()), "strict": not bad, "lenient": not bad,
            "empty": not text.strip(), "over_trigger": bool(bad), "matched_forms": bad[:3]}


def _zh_group_forms(group: dict) -> dict:
    zh = group.get("zh") or {}
    return {
        "variant_zh": zh.get("variant_zh") or {},
        "aliases": list(zh.get("aliases") or []),
        "name_forms_zh": list(zh.get("name_forms_zh") or []),
        "canonical_zh": list(zh.get("canonical_zh") or []),
    }


def _zh_contains(text: str, form: str) -> bool:
    """中文/拉丁输出里的形态匹配：拉丁名忽略空格与大小写；中文直接子串。"""
    if not form:
        return False
    t, f = norm_text(text), norm_text(form)
    if latin_key(f) and not re.search(r"[\u3040-\u9fff]", f):
        return latin_key(f) in latin_key(t)
    return f in t


def score_zh_sample(sample: dict, group: dict, text: str) -> dict:
    """端到端中文输出打分（ASR→翻译 / 音频→中文同传共用）。

    pos: strict = 该样本 variant 的 allowed_zh 命中；lenient = 额外接受该组规范译名/别名
    neg: 输出中不得出现该组 name_forms_zh / canonical_zh
    """
    text = text or ""
    zh = _zh_group_forms(group)
    rd = _sample_reading(sample, group)
    variant_zh = list(zh["variant_zh"].get(rd) or [])
    variant_zh += [sample.get("allowed_zh")] if isinstance(sample.get("allowed_zh"), str) else list(sample.get("allowed_zh") or [])
    variant_zh = [z for z in dict.fromkeys(variant_zh) if z]
    strict = any(_zh_contains(text, z) for z in variant_zh)
    lenient = strict or any(_zh_contains(text, z) for z in (zh["aliases"] + zh["canonical_zh"]))
    empty = not text.strip()

    if sample.get("label") == "pos":
        return {"ok": lenient, "strict": strict, "lenient": lenient, "empty": empty,
                "match": ("strict" if strict else ("lenient" if lenient else ""))}

    bad = [z for z in dict.fromkeys(zh["name_forms_zh"] + zh["canonical_zh"]) if _zh_contains(text, z)]
    return {"ok": (not bad) and not empty, "strict": not bad, "lenient": not bad,
            "empty": empty, "over_trigger": bool(bad), "matched_forms": bad[:3]}


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------
def summarize(samples: list, results: dict) -> dict:
    """results: {sample_id: score_dict}。返回总体+分组指标与 suspects。"""
    from collections import Counter, defaultdict

    total = Counter()
    per_group = defaultdict(Counter)
    suspects = []
    for s in samples:
        sid = s["sample_id"]
        sc = results.get(sid) or {"ok": False, "empty": True, "error": "missing"}
        g, lab = s["group"], s["label"]
        total[f"{lab}_n"] += 1
        per_group[g][f"{lab}_n"] += 1
        if sc.get("empty"):
            total["empty"] += 1
            per_group[g]["empty"] += 1
        if sc.get("ok"):
            total[f"{lab}_ok"] += 1
            per_group[g][f"{lab}_ok"] += 1
        if lab == "pos" and sc.get("strict"):
            total["pos_strict"] += 1
            per_group[g]["pos_strict"] += 1
        if sc.get("over_trigger"):
            total["neg_over"] += 1
            per_group[g]["neg_over"] += 1
            suspects.append({"sample_id": sid, "group": g, "label": lab,
                             "variant": s.get("variant"), "suspect": "neg_has_name",
                             "score": sc})
        if lab == "pos" and not sc.get("ok"):
            suspects.append({"sample_id": sid, "group": g, "label": lab,
                             "variant": s.get("variant"), "suspect": "pos_missed",
                             "score": sc})

    def rate(a, b):
        return round(a / b, 4) if b else None

    overall = {
        "pos_n": total["pos_n"], "pos_ok": total["pos_ok"],
        "pos_rate": rate(total["pos_ok"], total["pos_n"]),
        "pos_strict": total["pos_strict"],
        "pos_strict_rate": rate(total["pos_strict"], total["pos_n"]),
        "neg_n": total["neg_n"], "neg_ok": total["neg_ok"],
        "neg_rate": rate(total["neg_ok"], total["neg_n"]),
        "neg_over": total["neg_over"],
        "empty": total["empty"],
        "empty_rate": rate(total["empty"], total["pos_n"] + total["neg_n"]),
    }
    groups_out = {}
    for g, c in per_group.items():
        groups_out[g] = {
            "pos_n": c["pos_n"], "pos_ok": c["pos_ok"], "pos_rate": rate(c["pos_ok"], c["pos_n"]),
            "pos_strict": c["pos_strict"], "neg_n": c["neg_n"], "neg_ok": c["neg_ok"],
            "neg_rate": rate(c["neg_ok"], c["neg_n"]), "neg_over": c["neg_over"],
        }
    return {"overall": overall, "per_group": groups_out, "suspects": suspects}

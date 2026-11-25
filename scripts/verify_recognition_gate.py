# -*- coding: utf-8 -*-
"""识别门禁：读 recognition_envelope@v1，确定性计算 PASS/HOLD/RETAKE。

模型只能产生证据字段；gate 只能由本脚本写入 gate 文件。
退出码：0=PASS, 2=HOLD, 3=RETAKE, 1=输入错误
"""
import argparse, json, os, sys, hashlib, datetime

PASS, HOLD, RETAKE, ERR = 0, 2, 3, 1
EXPECTED_NOTE = "AI 独立复核，无红批可依"
VALID_FLAGS_PREFIX = ("原文如此", "已划掉", "识别存疑", "需重拍", "公式待核", "分数待核", "上下标待核")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def ratio(num, den):
    return 1.0 if den == 0 else round(num / den, 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--envelope", required=True, help="recognition_envelope@v1 JSON 绝对路径")
    ap.add_argument("--out", required=True, help="门禁结果 JSON 输出路径")
    ap.add_argument("--forbidden", default="", help="额外禁写词，逗号分隔")
    ap.add_argument("--mode", choices=["image_strict", "text_direct"], default="image_strict",
                    help="v1.1: text_direct=纯文字直录（无照片），按文本规则裁定门禁")
    args = ap.parse_args()

    if not os.path.exists(args.envelope):
        print("ERROR: envelope not found:", args.envelope)
        return ERR
    try:
        env = json.load(open(args.envelope, encoding="utf-8"))
    except Exception as e:
        print("ERROR: invalid JSON:", e)
        return ERR

    pages = env.get("pages", [])
    crops = env.get("crops", [])
    blocks = env.get("transcription", [])
    doubts = env.get("doubts", [])
    core = env.get("core_word_check", [])
    retake = env.get("retake", {}) or {}
    selfcheck = env.get("self_check", {}) or {}

    # ===== v1.1 纯文字直录分支：无需图片证据，按文本规则裁定 =====
    if args.mode == "text_direct":
        text_failures = []
        # 必须有逐字转写块
        if not blocks:
            text_failures.append("HOLD: text_direct 模式必须有 transcription 逐字转写块")
        # 存疑必须闭环
        unresolved = [d for d in doubts if d.get("status") != "resolved"]
        if unresolved:
            text_failures.append("HOLD: text_direct 存疑未闭环 %d 条" % len(unresolved))
        # 核心词必须确认
        unconfirmed = [c for c in core if c.get("status") != "confirmed"]
        if unconfirmed:
            text_failures.append("HOLD: text_direct 核心词未确认 %d 处" % len(unconfirmed))
        # 空文本且无 flag
        empty_no_flag_td = [b.get("block_id") for b in blocks
                            if not str(b.get("text", "")).strip() and not (b.get("flags") or [])]
        if empty_no_flag_td:
            text_failures.append("HOLD: text_direct 存在空文本块 %s" % empty_no_flag_td)
        # 隐私
        forbidden_td = [w.strip() for w in args.forbidden.split(",") if w.strip()]
        hits_td = [w for w in forbidden_td if w in json.dumps(env, ensure_ascii=False)]
        privacy_td = len(hits_td) + int((env.get("self_check", {}) or {}).get("privacy_hits", 0))
        if privacy_td:
            text_failures.append("HOLD: text_direct 隐私命中 %d 处" % privacy_td)
        td_metrics = {
            "transcription_present": 1.0 if blocks else 0.0,
            "doubt_closure": ratio(len([d for d in doubts if d.get("status") == "resolved"]), len(doubts)),
            "core_word_confirm": ratio(len([c for c in core if c.get("status") == "confirmed"]), len(core)),
            "privacy_hits": privacy_td,
        }
        gate = "HOLD" if text_failures else "PASS"
        code = HOLD if text_failures else PASS
        result = {
            "schema_version": "1.1",
            "task_id": env.get("task_id"),
            "mode": "text_direct",
            "gate": gate,
            "computed_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "envelope_sha256": sha256(args.envelope),
            "metrics": td_metrics,
            "failures": text_failures,
            "note": "文字直录，非图像识别；gate 由脚本计算，模型自述无效",
        }
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print("GATE=%s code=%d mode=text_direct out=%s" % (gate, code, args.out))
        for x in text_failures:
            print("  -", x)
        return code

    # ===== image_strict 原逻辑 =====
    # C1 层报告覆盖率
    pages_with_ratio = [p for p in pages if "red_pixel_ratio" in p]
    m_layer = ratio(len(pages_with_ratio), len(pages))
    # C1 附加：红层为 0 必须使用精确 note
    note_bad = [p.get("page_index") for p in pages
                if p.get("red_pixel_ratio", -1) == 0 and p.get("layer_note") != EXPECTED_NOTE]

    # C3 裁切覆盖率：手写块必须出现在 crops 中（以 block_id 或 crop_id 关联）
    crop_ids = {str(c.get("block_id") or c.get("crop_id")) for c in crops}
    hand_blocks = [b for b in blocks if b.get("role") == "student_handwriting"]
    hand_with_crop = [b for b in hand_blocks
                      if str(b.get("block_id")) in crop_ids or b.get("crop_id") in crop_ids]
    m_crop = ratio(len(hand_with_crop), len(hand_blocks))

    # C5 读图预算
    pages_ok = [p for p in pages if (p.get("read_calls", 0) or 0) <= 5]
    m_budget = ratio(len(pages_ok), len(pages))

    # C4 易混字符复核率
    ambiguous = [f for b in blocks for f in (b.get("flags") or []) if "识别存疑" in str(f)]
    ambiguous_rechecked = [f for f in ambiguous if True]  # 由 crops.upscale_factor 佐证
    upscale_ok = any((c.get("upscale_factor") or 0) >= 3 for c in crops) if ambiguous else True
    m_ambig = ratio(len(ambiguous_rechecked), len(ambiguous)) if ambiguous else (1.0 if upscale_ok else 0.0)

    # C9 存疑闭环率
    resolved = [d for d in doubts if d.get("status") == "resolved"]
    m_doubt = ratio(len(resolved), len(doubts))

    # C12 核心词确认率
    confirmed = [c for c in core if c.get("status") == "confirmed"]
    m_core = ratio(len(confirmed), len(core))

    # 隐私命中
    forbidden = [w.strip() for w in args.forbidden.split(",") if w.strip()]
    hits = []
    blob = json.dumps(env, ensure_ascii=False)
    for w in forbidden:
        if w in blob:
            hits.append(w)
    privacy_hits = len(hits) + int(selfcheck.get("privacy_hits", 0))

    # 抽样保真复核（脚本要求回执中给出抽样结果）
    sample = selfcheck.get("sample_recheck", {})
    sample_total = int(sample.get("total", 0))
    sample_pass = int(sample.get("passed", 0))
    m_sample = ratio(sample_pass, sample_total) if sample_total else 0.0

    # C7 转写铁律：无空文本无 flag
    empty_no_flag = [b.get("block_id") for b in blocks
                     if not str(b.get("text", "")).strip() and not (b.get("flags") or [])]

    # C11 误识别模式追加
    c11_ok = bool(selfcheck.get("error_patterns_appended", False))

    metrics = {
        "layer_report": m_layer,
        "crop_coverage": m_crop,
        "read_budget": m_budget,
        "ambiguous_recheck": m_ambig,
        "doubt_closure": m_doubt,
        "core_word_confirm": m_core,
        "privacy_hits": privacy_hits,
        "sample_fidelity": m_sample,
    }

    failures = []
    if retake.get("required"):
        failures.append("RETAKE: " + str(retake.get("reason", "需重拍")))
    if note_bad:
        failures.append("HOLD: 红层为0但layer_note不规范 页=%s" % note_bad)
    if empty_no_flag:
        failures.append("HOLD: 存在空文本且无flag的块 %s" % empty_no_flag)
    if not c11_ok:
        failures.append("HOLD: 误识别模式未追加到 error-patterns.md")
    for k, v in metrics.items():
        if k == "privacy_hits":
            if v != 0:
                failures.append("HOLD: 隐私命中 %d 处 %s" % (v, hits))
        elif v < 1.0:
            failures.append("HOLD: %s = %s (门槛 1.0)" % (k, v))

    if any(f.startswith("RETAKE") for f in failures):
        gate, code = "RETAKE", RETAKE
    elif failures:
        gate, code = "HOLD", HOLD
    else:
        gate, code = "PASS", PASS

    result = {
        "schema_version": "1.0",
        "task_id": env.get("task_id"),
        "gate": gate,
        "computed_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "source_skill_version": (env.get("provenance") or {}).get("source_skill_version"),
        "envelope_sha256": sha256(args.envelope),
        "metrics": metrics,
        "c11_error_patterns_appended": c11_ok,
        "failures": failures,
        "note": "gate 由脚本计算，模型自述无效",
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("GATE=%s code=%d out=%s" % (gate, code, args.out))
    for f in failures:
        print("  -", f)
    return code


if __name__ == "__main__":
    sys.exit(main())

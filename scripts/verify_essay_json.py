# -*- coding: utf-8 -*-
"""作文 JSON 契约校验 v1.1：评分算术、改动量、核心词、变式、隐私、存疑闭环、
四色标注段拼接与 M 编号闭环、定稿全文、降级标注。
退出码：0=PASS, 2=FAIL, 1=输入错误
"""
import argparse, json, os, sys, datetime

OK, FAIL, ERR = 0, 2, 1
VALID_TYPES = {"删", "换", "补"}
VALID_SCORES = {15, 45, 50}
VALID_ROLES = {"keep", "delete", "change", "add"}
ROLE_TYPE = {"delete": "删", "change": "换", "add": "补"}
THINKING_KEYS = ("audit_thinking", "writing_thinking", "adapt_thinking")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="essay_input.json 绝对路径")
    ap.add_argument("--report", default="", help="校验报告输出路径（可选）")
    args = ap.parse_args()

    if not os.path.exists(args.data):
        print("ERROR: not found:", args.data)
        return ERR
    try:
        d = json.load(open(args.data, encoding="utf-8"))
    except Exception as e:
        print("ERROR: invalid JSON:", e)
        return ERR

    errors, warnings = [], []
    meta = d.get("meta", {})
    rec = d.get("recognition_ref", {})
    prompt = d.get("prompt_analysis", {})
    scoring = d.get("scoring", {})
    changes = d.get("change_list", [])
    summary = d.get("change_summary", {})
    variants = d.get("variants", [])
    notes = d.get("method_notes", {})
    doubts = d.get("doubts", [])
    trans = d.get("transcription", {})

    # 1 评分基准
    fs = meta.get("full_score")
    if fs not in VALID_SCORES:
        errors.append("meta.full_score 必须是 15/45/50 之一，当前=%s" % fs)
    if fs == 45:
        sysname = str(meta.get("score_system", "")) + str(meta.get("exam_name", ""))
        if "综能" not in sysname and "45" not in sysname:
            errors.append("满分45必须标注综能/45分制，禁止与50分制混用")

    # 2 识别门禁
    if rec.get("gate") != "PASS":
        errors.append("recognition_ref.gate 必须为 PASS，当前=%s" % rec.get("gate"))
    mode = rec.get("mode", "image_strict")
    if mode not in ("image_strict", "text_direct"):
        errors.append("recognition_ref.mode 必须为 image_strict 或 text_direct")
    if mode == "image_strict":
        gate_file = rec.get("gate_file", "")
        if gate_file and not os.path.isabs(gate_file) and not os.path.exists(gate_file):
            alt = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), gate_file)
            if os.path.exists(alt):
                gate_file = alt
        if gate_file and not os.path.exists(gate_file):
            errors.append("门禁文件不存在: %s" % gate_file)
    if prompt.get("core_word_status") != "confirmed":
        errors.append("prompt_analysis.core_word_status 必须为 confirmed")
    if not prompt.get("core_word"):
        errors.append("prompt_analysis.core_word 不能为空")

    # 3 降级标注（v1.1）
    if prompt.get("prompt_available") is False:
        if prompt.get("core_word_source") != "正文反推":
            errors.append("prompt_available=false 时 core_word_source 必须为正文反推")
        if not prompt.get("reliability_note"):
            errors.append("prompt_available=false 时 reliability_note 必填（判档可靠性下降说明）")
    else:
        if prompt.get("core_word_source", "题目材料") not in ("题目材料", "正文反推"):
            warnings.append("core_word_source 取值异常")
    if scoring.get("score_source") == "系统盲估":
        if not scoring.get("blind_note"):
            errors.append("score_source=系统盲估 时 blind_note 必填（非阅卷实分说明）")
        rng = scoring.get("estimate_range", [])
        if len(rng) != 2 or rng[0] > rng[1]:
            errors.append("盲估分支 estimate_range 必须为二元有效区间")
    elif scoring.get("score_source", "卷面实分") == "卷面实分":
        pass
    else:
        errors.append("score_source 必须为 卷面实分 或 系统盲估")

    # 4 评分算术
    base = scoring.get("base_score", 0)
    bonuses = sum(int(x.get("pts", 0)) for x in scoring.get("bonuses", []))
    deduct = sum(int(x.get("pts", 0)) for x in scoring.get("deductions", []))
    final = scoring.get("final_score", 0)
    blind = scoring.get("score_source") == "系统盲估"
    if not blind:
        expect = base + bonuses - deduct
        if final != expect:
            errors.append("评分算术不符: base %d + bonus %d - deduct %d = %d，但 final=%s" %
                          (base, bonuses, deduct, expect, final))
    else:
        if not (scoring["estimate_range"][0] <= final <= scoring["estimate_range"][1]):
            errors.append("盲估 final_score 必须落在 estimate_range 内")
    if isinstance(fs, int) and final > fs:
        errors.append("final_score 超过满分 %s" % fs)
    band_range = scoring.get("band_range") or []
    if len(band_range) == 2 and not (band_range[0] <= final <= band_range[1]):
        errors.append("分数 %s 不在档位区间 %s 内" % (final, band_range))
    if not scoring.get("rubric_fingerprint"):
        warnings.append("缺少 rubric_fingerprint 评分标准指纹")

    # 5 分诊
    triage = d.get("triage", {})
    if not triage:
        warnings.append("缺少 triage 分诊结论")

    # 6 改动量复算（核心）
    count = 0
    total_chars = 0
    over20 = 0
    change_map = {}
    for i, c in enumerate(changes):
        if c.get("type") not in VALID_TYPES:
            errors.append("改动项[%d].type 非法: %s" % (i, c.get("type")))
        if not c.get("oral_tip"):
            errors.append("改动项[%d] 缺 oral_tip（考场可复现要求）" % i)
        if not c.get("original") or not c.get("changed"):
            errors.append("改动项[%d] 缺 original 或 changed" % i)
        cid = c.get("id", "")
        if cid in change_map:
            errors.append("改动项 id 重复: %s" % cid)
        change_map[cid] = c
        chars = int(c.get("chars", len(str(c.get("changed", "")))))
        total_chars += chars
        whitelist = bool(c.get("whitelist")) or c.get("type") == "补"
        if chars > 20 and not whitelist:
            over20 += 1
        count += 1

    declared = int(summary.get("count", -1))
    if count != declared:
        errors.append("改动处数不符: 实际 %d，声明 %s" % (count, declared))
    if not (12 <= count <= 18):
        errors.append("改动处数应在 12-18 之间，当前 %d" % count)
    if over20:
        errors.append("有 %d 处超过20字且未标注白名单" % over20)
    if total_chars != int(summary.get("total_changed_chars", -1)):
        errors.append("改动总字数不符: 实际 %d，声明 %s" %
                      (total_chars, summary.get("total_changed_chars")))
    if summary.get("within_threshold") is not True:
        errors.append("change_summary.within_threshold 必须为 true（由脚本复算）")

    # 7 四色标注段：拼接一致 + 角色合法 + M 编号闭环（v1.1 核心）
    ab = trans.get("annotated_body", [])
    body = trans.get("essay_body", [])
    body_text = {b.get("para_id"): str(b.get("text", "")) for b in body}
    seen_ids = set()
    ab_ids = set()
    roles_by_id = {}  # change_id -> set(roles)，用于判定 type（换=delete+change）
    if not ab:
        errors.append("缺 transcription.annotated_body 四色标注段（v1.1 必填）")
    for para in ab:
        pid = para.get("para_id")
        segs = para.get("segments", [])
        # 原文 = keep + delete 片段拼接；change(红)/add(绿)是新增改动内容，不参与还原原文
        joined = "".join(str(s.get("text", "")) for s in segs
                         if s.get("role") in ("keep", "delete"))
        expect_text = body_text.get(pid) or next(
            (str(b.get("text", "")) for b in body if b.get("block_id") == pid), None)
        if expect_text is None:
            errors.append("annotated_body 段落 %s 在 essay_body 中不存在" % pid)
        elif joined != expect_text:
            errors.append("annotated_body 段落 %s 切片(keep+delete)拼接与原文不一致: 拼=%r 原=%r" %
                          (pid, joined[:40], expect_text[:40]))
        for s in segs:
            role = s.get("role")
            if role not in VALID_ROLES:
                errors.append("标注段 %s 角色非法: %s" % (pid, role))
            cid = s.get("change_id")
            if role in ("delete", "change", "add"):
                if not cid:
                    errors.append("标注段 %s 的 %s 片段缺 change_id" % (pid, role))
                else:
                    ab_ids.add(cid)
                    roles_by_id.setdefault(cid, set()).add(role)
                    if cid not in change_map:
                        errors.append("标注段引用的 M 编号 %s 不在改动清单" % cid)
                    if role == "delete" and not s.get("strike"):
                        errors.append("标注段删除片段 %s 缺 strike 标记（删除线）" % cid)
            elif role == "keep" and cid:
                warnings.append("keep 片段不应带 change_id: %s" % cid)
            if cid:
                seen_ids.add(cid)
    # 按 change_id 聚合角色判定 type：change→换；仅 add→补；仅 delete→删
    for cid, roles in roles_by_id.items():
        if cid not in change_map:
            continue
        actual = change_map[cid].get("type")
        if "change" in roles:
            expect = "换"
        elif "add" in roles and "delete" not in roles:
            expect = "补"
        elif "delete" in roles and "change" not in roles and "add" not in roles:
            expect = "删"
        else:
            expect = actual
        if actual != expect:
            errors.append("标注段 %s 角色组合 %s 对应 type 应为 %s，改动清单为 %s" %
                          (cid, sorted(roles), expect, actual))
    # 闭环：改动清单中的 M 必须都在标注段出现（三不改清单里的保留项除外）
    required_change_ids = {c.get("id") for c in changes if c.get("type") in VALID_TYPES}
    missing_in_body = required_change_ids - ab_ids
    if missing_in_body:
        errors.append("编号闭环失败：改动清单的 M 未在标注段出现: %s" % sorted(missing_in_body))

    # 8 定稿全文（v1.1）
    final_draft = d.get("final_draft", [])
    if not final_draft:
        errors.append("缺 final_draft 定稿全文（v1.1 必填）")
    else:
        draft_text = "\n".join(str(p.get("text", "")) for p in final_draft)
        core = str(prompt.get("core_word", ""))
        if core and draft_text.count(core) < 1:
            errors.append("定稿全文未出现核心词「%s」" % core)
        # 三处见核心词：首段/中段/尾段
        n = len(final_draft)
        if n >= 3 and core:
            zones = [str(final_draft[0].get("text", "")),
                     str(final_draft[n // 2].get("text", "")),
                     str(final_draft[-1].get("text", ""))]
            hit = sum(1 for z in zones if core in z)
            if hit < 3:
                errors.append("定稿全文未满足三处见核心词（首/中/尾命中 %d/3）" % hit)

    # 9 变式题三层四要素与三思路
    if len(variants) < 1:
        errors.append("variants 至少 1 道变式题")
    for i, v in enumerate(variants):
        apath = v.get("adapt_path", {})
        for layer in ("事件层", "品质层", "意义层"):
            node = apath.get(layer)
            if not isinstance(node, dict):
                errors.append("变式题[%d] adapt_path.%s 必须是四要素对象" % (i, layer))
                continue
            for f in ("original", "changed", "why", "how"):
                if not node.get(f):
                    errors.append("变式题[%d] adapt_path.%s 缺 %s" % (i, layer, f))
        for key in THINKING_KEYS:
            arr = v.get(key, [])
            if not isinstance(arr, list) or len(arr) < 3:
                errors.append("变式题[%d] 缺 %s（需≥3条）" % (i, key))
        if not v.get("risk"):
            errors.append("变式题[%d] 缺套作风险标注" % i)
        if not v.get("anti_collision"):
            warnings.append("变式题[%d] 缺反撞车说明" % i)

    # 10 方法与底层逻辑
    for k in ("实战步骤", "操作步骤与方法", "底层逻辑", "5分钟自检清单"):
        if not notes.get(k):
            errors.append("method_notes 缺 %s" % k)
    selfcheck = notes.get("5分钟自检清单", [])
    if isinstance(selfcheck, list) and len(selfcheck) > 5:
        warnings.append("考场自检清单超过5条，应移到考前一天看附录")

    # 11 存疑闭环与隐私
    open_doubts = [x for x in doubts if x.get("status") == "open"]
    if open_doubts:
        errors.append("存在 %d 条未解决存疑" % len(open_doubts))
    blob = json.dumps(d, ensure_ascii=False)
    for pat in ("姓名：", "班级：", "学号：", "考号：", "座位号"):
        if pat in blob:
            errors.append("疑似身份信息未被遮蔽: %s" % pat)

    status = "PASS" if not errors else "FAIL"
    report = {
        "schema_version": "1.1",
        "data": os.path.abspath(args.data),
        "checked_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "counts": {"changes": count, "variants": len(variants), "annotated_paras": len(ab),
                   "ab_ids": len(ab_ids), "doubts_open": len(open_doubts)},
        "errors": errors,
        "warnings": warnings,
    }
    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    print("ESSAY_JSON=%s errors=%d warnings=%d changes=%d variants=%d ab_ids=%d" %
          (status, len(errors), len(warnings), count, len(variants), len(ab_ids)))
    for e in errors:
        print("  ERR:", e)
    for w in warnings:
        print("  WARN:", w)
    return OK if status == "PASS" else FAIL


if __name__ == "__main__":
    sys.exit(main())

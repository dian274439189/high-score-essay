# -*- coding: utf-8 -*-
"""高分作文 v1.1：作文 JSON → 家长版四色诊断报告 + 学生版大白话一页纸操作卡。

模板与数据分离：换作文只改 JSON，不改本脚本。
v1.1 改动：
- 使用本包 scripts/docx_kit_local.py（新增绿/删除线/四色审计），无外部依赖
- 家长版删六类技术元信息；新增四色标注原文、六栏合并表、文末定稿全文
- 四色只从 annotated_body 读取；编号闭环由 verify_essay_json.py 保证
- 学生版全大白话
"""
import argparse, json, os, sys, hashlib, datetime, importlib.util

OK, FAIL, ERR = 0, 2, 1

BASE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(BASE)
KIT_PATH = os.path.join(BASE, "docx_kit_local.py")

spec = importlib.util.spec_from_file_location("docx_kit_local", KIT_PATH)
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_parent(d, out_dir, work_dir, filename):
    doc = Document()
    kit.setup(doc)
    sc = d["scoring"]

    kit.para(doc, "高分作文 · 家长版四色诊断报告",
             kit.HEAD, 18, True, WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    kit.para(doc, "本方案只优化文本，不能改变书写卷面，不能替孩子产生真实经历；预估为一类文上沿的条件性上限，非承诺。",
             kit.TEA, 10, False, WD_ALIGN_PARAGRAPH.CENTER, space_after=8)

    # 降级标注（需求 1、2）：显著写在开头
    pa = d.get("prompt_analysis", {})
    if pa.get("prompt_available") is False:
        kit.para(doc, "【说明】本次未提供作文题目，扣题与否无法核验；判档只依据文本自身的立意与完成度，一类文判定可靠性下降。",
                 kit.NOTE, 10, True, space_after=3)
    if sc.get("score_source") == "系统盲估":
        rng = sc.get("estimate_range", [])
        rng_txt = ("%s–%s 分" % (rng[0], rng[1])) if len(rng) == 2 else "条件性区间"
        kit.para(doc, "【说明】本次未提供卷面得分，档位为系统盲估（%s），非真实阅卷分，通常正负 2 至 3 分。" % rng_txt,
                 kit.NOTE, 10, True, space_after=3)
    if d.get("recognition_ref", {}).get("mode") == "text_direct":
        kit.para(doc, "【说明】本次按文字直录处理，无照片，书写卷面与字迹无法核验。",
                 kit.NOTE, 10, True, space_after=3)

    # 一、失分诊断（需求 4：不展示作文类型/满分/卷面定位/评分指纹/识别门禁/入口分诊）
    kit.h1(doc, "一、失分诊断")
    dims = sc.get("dims", {})
    kit.table(doc, ["维度", "现状与证据（原文为依据）"],
              [[k, v] for k, v in dims.items()], widths=[3.2, 12.8])
    if sc.get("band"):
        kit.kv(doc, "老师大致会把这篇放在：", str(sc.get("band")))
    if sc.get("evidence_refs"):
        kit.kv(doc, "关键证据位置：", "、".join(str(x) for x in sc["evidence_refs"]))

    # 二、题目与核心词
    kit.h1(doc, "二、题目与核心词")
    mat = d["transcription"].get("prompt_material", [])
    if mat:
        kit.para(doc, "题目材料原文（按转写忠实呈现）：", kit.INK, 10.5, True)
        for b in mat:
            kit.para(doc, str(b.get("text", "")), kit.INK, 10.5)
    else:
        kit.para(doc, "题目材料：本次未提供（见文首说明）。", kit.GREY, 10.5)
    core = d["prompt_analysis"].get("core_word", "")
    src = d["prompt_analysis"].get("core_word_source", "题目材料")
    kit.big(doc, "必须请回的核心词（%s）：" % src, core, kit.TEA)

    # 三、学生作文原文（四色标注，需求 5 核心）
    kit.h1(doc, "三、学生作文原文（四色标注）")
    kit.para(doc, "黑色＝保留不动；红色＝建议改成；绿色＝需要增加；灰色加横线＝要删掉。括号里的 M 编号对应下面第四节的同一行。",
             kit.BODY, 9.5)
    ab = {x.get("para_id"): x.get("segments", [])
          for x in d["transcription"].get("annotated_body", [])}
    body = d["transcription"].get("essay_body", [])
    if ab:
        for b in body:
            pid = b.get("para_id")
            segs = ab.get(pid)
            if not segs:
                kit.para(doc, str(b.get("text", "")), kit.INK, 10.5)
                continue
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.32
            kit.annotated_runs(p, segs, size=10.5, with_id=True)
    else:
        # 无标注段时按原文黑字兜底，不猜色（禁止字符串猜测）
        for b in body:
            kit.para(doc, str(b.get("text", "")), kit.INK, 10.5)
        kit.para(doc, "【提示】本卷未提供 annotated_body 标注段，故仅呈现原文，未做四色标注。", kit.GREY, 9.5)

    # 四、逐处改动·六栏合并表（需求 5）
    kit.h1(doc, "四、逐处改动对照（六栏）")
    kit.para(doc, "这张表把原来的逐处改动对照和改动明细与采分点合并了，M 编号与第三节原文一一对应。",
             kit.BODY, 9.5)
    rows = [[c.get("id", ""), c.get("original", ""), c.get("changed", ""),
             c.get("reason", ""), c.get("point_gain", ""), c.get("if_skipped", "")]
            for c in d.get("change_list", [])]
    t = kit.table(doc,
                  ["第几处", "我原来写的", "建议改成", "为什么改", "对应采分点", "不改的后果"],
                  rows, widths=[1.3, 3.0, 3.6, 3.2, 2.5, 2.4], body_size=8.5)
    # 给"我原来写的"着灰、"建议改成"着红，与四色观感一致
    for ci, c in enumerate(d.get("change_list", []), 1):
        cells = t.rows[ci].cells
        kit.cell_text(cells[1], str(c.get("original", "")), kit.GREY, 8.5)
        kit.cell_text(cells[2], str(c.get("changed", "")), kit.TEA, 8.5)

    # 五、改动量与三不改
    kit.h1(doc, "五、改动量与三不改")
    cs = d.get("change_summary", {})
    kit.table(doc, ["指标", "数值"], [
        ["改动处数", cs.get("count")],
        ["累计改动字数", cs.get("total_changed_chars")],
        ["未改动段落占比", cs.get("unchanged_para_ratio")],
        ["每处默认上限", "%s 字（白名单除外）" % cs.get("per_change_max_chars")],
    ], widths=[5.0, 10.0])
    keep = [c for c in d.get("change_list", []) if c.get("type") == "保留"]
    if keep:
        kit.h2(doc, "三不改清单")
        for c in keep:
            kit.para(doc, "· %s（%s）" % (c.get("original", ""), c.get("reason", "")), kit.INK, 10)

    # 六、变式题与三思路、三层四要素（需求 6）
    kit.h1(doc, "六、变式作文题与满分要点")
    for i, v in enumerate(d.get("variants", []), 1):
        kit.h2(doc, "变式题 %d｜%s（套作风险：%s）" % (i, v.get("type", ""), v.get("risk", "")))
        kit.para(doc, str(v.get("prompt", "")), kit.INK, 10.5)
        for label, key in [("审题思路：", "audit_thinking"), ("写作思路：", "writing_thinking"), ("套改思路：", "adapt_thinking")]:
            items = v.get(key, [])
            if items:
                kit.para(doc, label, kit.NOTE, 10, True, space_after=2)
                for x in items:
                    kit.para(doc, "· " + str(x), kit.BODY, 10, space_after=2)
        apath = v.get("adapt_path", {})
        arows = []
        for layer in ("事件层", "品质层", "意义层"):
            node = apath.get(layer, {})
            if isinstance(node, dict):
                arows.append([layer, node.get("original", ""), node.get("changed", ""),
                              node.get("why", ""), node.get("how", "")])
            else:
                arows.append([layer, "", str(node), "", ""])
        kit.table(doc, ["层", "原表述", "改后表述", "为什么", "怎么落地"],
                  arows, widths=[1.8, 3.0, 3.4, 3.6, 4.2], body_size=8.8)
        kit.kv(doc, "触动词：", str(v.get("trigger_word", "")))
        kit.kv(doc, "核心词：", str(v.get("core_word", "")))
        kit.kv(doc, "迁移关系：", str(v.get("reuse_material", "")))
        kit.kv(doc, "反撞车说明：", str(v.get("anti_collision", "")))
        pts = v.get("full_score_points", [])
        if pts:
            kit.kv(doc, "满分要点：", "；".join(str(x) for x in pts))

    mp = d.get("multi_path", {})
    if mp.get("routes"):
        kit.h1(doc, "多路评卷与冻结摘要")
        kit.table(doc, ["路", "结论", "调用ID"],
                  [[r.get("id", ""), str(r.get("conclusion", ""))[:80], r.get("call_id", "")[:24]]
                   for r in mp["routes"]], widths=[1.6, 10.4, 4.0])

    # 七、存疑与能力边界
    kit.h1(doc, "七、存疑清单与能力边界")
    doubts = d.get("doubts", [])
    if doubts:
        for x in doubts:
            kit.para(doc, "· [%s] %s" % (x.get("type", ""), x.get("text", "")), kit.TEA, 10)
    else:
        kit.para(doc, "本卷无未解决存疑。", kit.INK, 10)
    kit.para(doc, "能力边界：最小改动法的上限为一类文下沿到中上沿；冲一类高分需在立意或构思层再埋一处巧思，且书写卷面与真情实感非改稿可控制。",
             kit.NOTE, 10)

    # 八、文末定稿全文（需求 7）
    kit.h1(doc, "八、改后可誊写定稿全文")
    kit.para(doc, "下面是改完后的完整文章，纯文字、不带标注，可直接照着誊写。", kit.BODY, 9.5)
    final = d.get("final_draft", [])
    if final:
        for para in final:
            kit.para(doc, str(para.get("text", "")), kit.INK, 10.5, space_after=5)
    else:
        kit.para(doc, "【提示】本卷未提供 final_draft 定稿全文。", kit.GREY, 9.5)

    local, target = kit.save_pair(doc, filename, work_dir, out_dir)
    return local, target


def build_student(d, out_dir, work_dir, filename):
    """学生版 v1.1：全大白话，一页纸，不含四色标注与元信息。"""
    doc = Document()
    kit.setup(doc)
    sc = d["scoring"]
    pa = d.get("prompt_analysis", {})

    kit.para(doc, "高分作文 · 我的作文提分卡",
             kit.HEAD, 17, True, WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    kit.para(doc, "合上书你也能做出来，才算真的会。", kit.TEA, 10.5, True, WD_ALIGN_PARAGRAPH.CENTER, space_after=10)

    # 降级标注（学生大白话）
    if pa.get("prompt_available") is False:
        kit.para(doc, "这次没给题目，只能看你写得好不好，看不出你有没有写对题。", kit.NOTE, 10, True, space_after=3)
    if sc.get("score_source") == "系统盲估":
        kit.para(doc, "没看到卷子分数，下面这个档是大概估的，不一定准。", kit.NOTE, 10, True, space_after=3)
    if d.get("recognition_ref", {}).get("mode") == "text_direct":
        kit.para(doc, "你发的是文字，没有照片，字好不好看这边看不到。", kit.NOTE, 10, True, space_after=3)

    kit.h1(doc, "1. 这篇作文考什么")
    kit.para(doc, "题目里盯住这个词：「%s」。" % pa.get("core_word", ""), kit.INK, 11)
    kit.para(doc, "老师大概会把你放在：%s。" % sc.get("band", "某一档"), kit.INK, 11)

    kit.h1(doc, "2. 我原来写的 vs 改成这样")
    rows = [(c.get("id", ""), c.get("original", ""), c.get("changed", ""), True)
            for c in d.get("change_list", [])[:8]]
    kit.contrast_table(doc, rows)
    kit.para(doc, "红字那一行，就是最该改的地方。别的只做小修，不换故事、不重写。", kit.NOTE, 10)

    kit.h1(doc, "3. 记一句话")
    tips = []
    for c in d.get("change_list", []):
        t = c.get("oral_tip", "")
        if t and t not in tips:
            tips.append(t)
    for t in tips[:5]:
        kit.para(doc, "· " + t, kit.STU, 10.5, True)

    kit.h1(doc, "4. 老素材怎么套新题")
    for v in d.get("variants", []):
        apath = v.get("adapt_path", {})
        kit.h2(doc, str(v.get("type", "")))
        audit = v.get("audit_thinking", [])
        if audit:
            kit.para(doc, "先盯住：%s" % str(audit[0]), kit.NOTE, 10, True)
        actions = []
        for layer in ("事件层", "品质层", "意义层"):
            node = apath.get(layer, {})
            if isinstance(node, dict) and node.get("changed"):
                actions.append("%s：%s" % (layer[:2], node["changed"]))
            elif isinstance(node, str) and node:
                actions.append("%s：%s" % (layer[:2], node))
        kit.para(doc, "；".join(actions[:3]), kit.INK, 10.5)

    kit.h1(doc, "5. 考场自检（做完就看这几条）")
    checks = d.get("method_notes", {}).get("5分钟自检清单", [])
    for i, c in enumerate(checks[:5], 1):
        kit.para(doc, "%d. %s" % (i, c), kit.INK, 10.5)

    kit.h1(doc, "6. 变式题（做完再看答案）")
    for i, v in enumerate(d.get("variants", []), 1):
        kit.para(doc, "%d. %s" % (i, v.get("prompt", "")), kit.INK, 10.5)
    kit.para(doc, "—— 下面是对答案，做完再看 ——", kit.TEA, 10, True)
    for v in d.get("variants", []):
        pts = v.get("full_score_points", [])
        if pts:
            kit.para(doc, "· " + "；".join(str(x) for x in pts), kit.INK, 10)

    kit.para(doc, "说明：我只改了少量地方，故事还是你自己的。书写和真实感受，需要你自己带上考场。", kit.NOTE, 10)
    local, target = kit.save_pair(doc, filename, work_dir, out_dir)
    return local, target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", default="")
    ap.add_argument("--only", choices=["parent", "student", "both"], default="both")
    args = ap.parse_args()

    if not os.path.exists(args.data):
        print("ERROR: data not found:", args.data)
        return ERR
    d = json.load(open(args.data, encoding="utf-8"))
    # 门禁：识别 PASS 才可渲染（text_direct 亦须脚本裁定 PASS）
    if d.get("recognition_ref", {}).get("gate") != "PASS":
        print("ERROR: recognition gate is not PASS; refuse to render")
        return ERR

    out_dir = args.out
    work_dir = args.work or os.path.join(out_dir, "_work")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)
    base = "高分作文_%s" % d["meta"].get("exam_name", "样例")
    made = {}
    if args.only in ("parent", "both"):
        made["parent"] = build_parent(d, out_dir, work_dir, base + "_家长版四色诊断报告.docx")[1]
    if args.only in ("student", "both"):
        made["student"] = build_student(d, out_dir, work_dir, base + "_学生版大白话操作卡.docx")[1]

    checks = {}
    all_ok = True
    for key, path in made.items():
        counts, missing = kit.color_audit(path)
        hits = kit.privacy_scan(path)
        check = {"color_audit": "none missing" if not missing else str(missing),
                 "privacy_hits": len(hits)}
        if key == "parent":
            nstrike, strike_ok = kit.strike_audit(path, min_count=1)
            check["strike_count"] = nstrike
            check["strike_audit"] = "present" if strike_ok else "missing"
            if not strike_ok or missing:
                all_ok = False
        else:
            # 学生版只需红黑即可（无绿无灰删除线）
            _, missing_student = kit.color_audit(path, required=("000000", "C00000"))
            check["color_audit"] = "none missing" if not missing_student else str(missing_student)
            if missing_student:
                all_ok = False
        if hits:
            all_ok = False
        checks[key] = check

    manifest = {
        "schema_version": "1.1",
        "input_ref": os.path.abspath(args.data),
        "input_sha256": sha256(args.data),
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "files": made,
        "checks": checks,
        "final_draft_present": bool(d.get("final_draft")),
        "status": "PASS" if all_ok else "FAIL",
    }
    mpath = os.path.join(out_dir, base + "_manifest.json")
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("BUILD=%s manifest=%s files=%s" % (manifest["status"], mpath, list(made.values())))
    for k, v in checks.items():
        print("  ", k, v)
    return OK if all_ok else FAIL


if __name__ == "__main__":
    sys.exit(main())

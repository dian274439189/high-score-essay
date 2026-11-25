# -*- coding: utf-8 -*-
"""高分作文 v1.1 本地渲染工具箱。

本包自带的 Word 渲染工具包（三色 run／表格／对照表／颜色审计／隐私扫描）：
- 新增 GREEN 绿色常量（新增内容 add）
- 新增 set_strike(run)：通过 OXML w:strike 写入删除线
- 新增 annotated_runs(doc, segments)：从标注段按四色渲染，禁止字符串猜测
- 扩展 color_audit 必检色为黑/红/绿/灰四色，并增加删除线审计
其余 API（para/h1/h2/kv/table/shade/cell_text/save_pair/privacy_scan 等）与源 kit 保持一致。
"""
import os
import re
import shutil
from datetime import date, timedelta
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

INK = RGBColor(0x00, 0x00, 0x00)   # 保留 keep
STU = RGBColor(0x00, 0x33, 0x99)   # 学生原句（学生版对照表用）
TEA = RGBColor(0xC0, 0x00, 0x00)   # 建议改成 change / 走岔提示
GREEN = RGBColor(0x00, 0x80, 0x00) # v1.1 新增内容 add
GREY = RGBColor(0x59, 0x59, 0x59)  # 要删掉 delete（配删除线）
NOTE = RGBColor(0xE6, 0x7E, 0x22)
BODY = RGBColor(0x22, 0x22, 0x22)
HEAD = RGBColor(0x1F, 0x4E, 0x79)
SECTION = RGBColor(0x0F, 0x76, 0x6E)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT_CN = '微软雅黑'

TRI_COLOR = ('000000', '003399', 'C00000')
QUAD_COLOR = ('000000', 'C00000', '008000', '595959')
ROLE_COLOR = {'keep': INK, 'change': TEA, 'add': GREEN, 'delete': GREY}
PRIVACY_PATTERNS = [
    r'姓名\s*[：:]\s*\S', r'班级\s*[：:]\s*\S', r'学号\s*[：:]\s*\S',
    r'学校\s*[：:]\s*\S', r'考号\s*[：:]\s*\S', r'座位号\s*\d',
    r'\b\d{3,4}\s*班\b',
]


def set_run(run, color=BODY, size=10.5, bold=False, font=FONT_CN, italic=False):
    run.font.name = font
    run.font.size = Pt(size)
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.italic = italic
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn('w:rFonts'))
    if rfonts is None:
        rfonts = OxmlElement('w:rFonts')
        rpr.append(rfonts)
    for key in ('w:eastAsia', 'w:ascii', 'w:hAnsi'):
        rfonts.set(qn(key), font)
    return run


def set_strike(run, value=True):
    """v1.1：写入/移除删除线 w:strike，用于表示要删掉的原文。"""
    rpr = run._element.get_or_add_rPr()
    strike = rpr.find(qn('w:strike'))
    if strike is None:
        strike = OxmlElement('w:strike')
        rpr.append(strike)
    strike.set(qn('w:val'), '1' if value else '0')
    return run


def has_strike(run):
    rpr = run._element.find(qn('w:rPr'))
    if rpr is None:
        return False
    strike = rpr.find(qn('w:strike'))
    if strike is None:
        return False
    return strike.get(qn('w:val')) in ('1', 'true', 'on', None)


def annotated_runs(paragraph, segments, size=10.5, with_id=True):
    """v1.1：从 annotated_body 的 segments 按四色写入 run，禁止字符串猜测。

    segments: [{"text","role","change_id"?,"strike"?}]
    返回写入的 run 列表。role→颜色：keep黑、change红、add绿、delete灰+删除线。
    change_id 以（M3）形式附在片段后，颜色与片段一致。
    """
    made = []
    for seg in segments:
        role = seg.get('role', 'keep')
        color = ROLE_COLOR.get(role, BODY)
        text = str(seg.get('text', ''))
        strike_flag = bool(seg.get('strike')) or role == 'delete'
        run = set_run(paragraph.add_run(text), color, size, role in ('change', 'add'))
        if strike_flag:
            set_strike(run, True)
        made.append(run)
        if with_id and seg.get('change_id'):
            idrun = set_run(paragraph.add_run('（%s）' % seg['change_id']), color, max(size - 1.5, 8), True)
            if strike_flag:
                set_strike(idrun, True)
            made.append(idrun)
    return made


def para(doc, text='', color=BODY, size=10.5, bold=False, align=None,
         space_after=4, space_before=0, indent=0, line=1.28, italic=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    pf.line_spacing = line
    if indent:
        pf.left_indent = Cm(indent)
    if align is not None:
        p.alignment = align
    if text:
        set_run(p.add_run(text), color, size, bold, italic=italic)
    return p


def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hexcolor)
    tcPr.append(shd)


def cell_text(cell, text, color=BODY, size=9.5, bold=False, align=None):
    cell.text = ''
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    if align is not None:
        p.alignment = align
    set_run(p.add_run(str(text)), color, size, bold)
    return p


def cell_annotated(cell, segments, size=9, with_id=True):
    """v1.1：在表格单元格内写四色标注段。"""
    cell.text = ''
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    annotated_runs(p, segments, size=size, with_id=with_id)
    return p


def table(doc, headers, rows, widths=None, header_bg='1F4E79', body_size=9.5):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        shade(c, header_bg)
        cell_text(c, h, WHITE, body_size, True, WD_ALIGN_PARAGRAPH.CENTER)
    for r in rows:
        cells = t.add_row().cells
        for i, v in enumerate(r):
            cell_text(cells[i], v, BODY, body_size)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    para(doc, '', space_after=2)
    return t


def contrast_table(doc, rows):
    """双栏逐步骤对照：rows = (step, mine, right, wrong_flag)"""
    t = doc.add_table(rows=1, cols=3)
    t.style = 'Table Grid'
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    heads = ['第几处', '我当时写的（走岔处红字）', '改成这样']
    widths = [1.6, 6.9, 7.5]
    for i, h in enumerate(heads):
        c = t.rows[0].cells[i]
        shade(c, '1F4E79')
        cell_text(c, h, WHITE, 9.5, True, WD_ALIGN_PARAGRAPH.CENTER)
    for step, mine, right, wrong in rows:
        cells = t.add_row().cells
        cell_text(cells[0], step, BODY, 9, False, WD_ALIGN_PARAGRAPH.CENTER)
        cell_text(cells[1], ('【就改这一处】' if wrong else '') + mine,
                  TEA if wrong else STU, 9, wrong)
        cell_text(cells[2], right, BODY, 9)
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)
    para(doc, '', space_after=3)
    return t


def h1(doc, text):
    p = doc.add_heading(level=1)
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(7)
    set_run(p.add_run(text), HEAD, 15, True)


def h2(doc, text):
    p = doc.add_heading(level=2)
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(5)
    set_run(p.add_run(text), HEAD, 12.5, True)


def h3(doc, text):
    p = doc.add_heading(level=3)
    p.paragraph_format.space_before = Pt(7)
    p.paragraph_format.space_after = Pt(3)
    set_run(p.add_run(text), SECTION, 11.5, True)


def kv(doc, label, text, color=BODY):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.28
    set_run(p.add_run(label), NOTE, 10.5, True)
    set_run(p.add_run(text), color, 10.5, False)
    return p


def big(doc, label, text, color=TEA):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.3
    set_run(p.add_run(label), NOTE, 11, True)
    set_run(p.add_run(text), color, 11.5, True)
    return p


def setup(doc):
    sec = doc.sections[0]
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)
    sec.left_margin = Cm(2.5)
    sec.right_margin = Cm(2.5)
    st = doc.styles['Normal']
    st.font.name = FONT_CN
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), FONT_CN)


def all_text(path):
    d = Document(path)
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return '\n'.join(parts)


def _iter_runs(doc):
    for p in doc.paragraphs:
        for r in p.runs:
            yield r
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        yield r


def color_audit(path, required=QUAD_COLOR):
    """v1.1：默认审计黑红绿灰四色。"""
    d = Document(path)
    counts = {}
    for r in _iter_runs(d):
        c = r.font.color.rgb if r.font.color else None
        if c is not None:
            counts[str(c)] = counts.get(str(c), 0) + 1
    missing = [k for k in required if k not in counts]
    return counts, missing


def strike_audit(path, min_count=1):
    """v1.1：统计带删除线的 run 数，用于确认 delete 段真画了横杆。"""
    d = Document(path)
    n = sum(1 for r in _iter_runs(d) if has_strike(r))
    return n, (n >= min_count)


def privacy_scan(path, extra_forbidden=None):
    text = all_text(path)
    hits = []
    for pat in PRIVACY_PATTERNS:
        for m in re.finditer(pat, text):
            hits.append((pat, m.group(0)[:30]))
    for word in (extra_forbidden or []):
        if word and word in text:
            hits.append(('custom', word))
    return hits


def schedule_rows(tasks, base_date):
    base = date.fromisoformat(base_date)
    return [[(base + timedelta(days=int(d))).strftime('%Y-%m-%d'),
             'D+%d' % int(d), task] for d, task in tasks]


def save_pair(doc, filename, work_dir, out_dir):
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    local = os.path.join(work_dir, filename)
    doc.save(local)
    target = os.path.join(out_dir, filename)
    shutil.copy2(local, target)
    return local, target

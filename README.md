# 高分作文 · 最小改动提分教练（high-score-essay）

> 面向中考语文作文 / 英语书面表达的 AI 批改与提分技能包。给它一篇作文（照片、截图或纯文字），它先逐字认准原文，定位首要失分点，**只做 12–18 处最小改动**，最终交付两份可直接使用的 Word：家长版四色诊断报告 ＋ 学生版大白话一页纸，并附变式题与套改路径。
>
> **不承诺满分，不编造经历，不改变书写卷面。**

本仓库是 WorkBuddy 技能 `high-score-essay` 的完整源码与运行资源，自包含、可移植，不依赖任何仓库外的脚本或技能。

---

## 1. 它能做什么 / 不能做什么

**能：**

- 从作文照片 / 截图中逐字转写原文，三色分离（印刷题面 / 手写正文 / 红字批改），存疑处标注并要求确认。
- 按锁定的评分基准判档，给出条件性预估区间（非承诺分）。
- 只动 12–18 处关键小地方，每处默认不超过 20 字，保留孩子原有表达风格。
- 生成家长版四色标注报告、学生版大白话操作卡、可誊写的定稿全文、3 道变式题及套改思路。
- 通过脚本门禁复算改动量、校验四色与删除线、扫描隐私信息，未 PASS 不交付 Word。

**不能 / 边界：**

- 不承诺满分或具体分数变化，只给条件性预估区间与唯一评分基准。
- 不虚构原文没有的事实、细节、引语、心理活动；补写内容需学生确认是否属实。
- 只优化文本，不能改变书写卷面；若主要失分在卷面或立意根本偏移，会明确告知不适用最小改动。
- 一次只处理**一篇作文**；出诊断表后必须停下等用户确认，才会继续改稿。
- 产物不得出现姓名、班级、学号、学校、考号、座位号，统一写「该生 / 我 / 某同学」。

---

## 2. 安装与使用

### 2.1 在 WorkBuddy 中使用（推荐）

1. 打开 WorkBuddy → 左侧栏「专家 · 技能 · 连接器 → 技能」。
2. 导入本仓库（或打包为 zip 后安装），技能名为 `high-score-essay`。
3. 直接使用自然语言调用，例如：

   - 「孩子这篇作文扣了 8 分，帮我看看该改哪几句，别整篇重写。」
   - 「上传作文照片，给我一份家长能看懂的四色标注诊断报告。」
   - 「这篇素材还能套哪些题目？出 3 道变式题和学生版一页纸。」

4. 也可粘贴纯文字作文。上传照片后按提示确认转写结果，流程分阶段停顿等待确认，不会一次性输出全部改稿。

### 2.2 作为本地脚本运行

需要 Python 3.9+ 与 `python-docx`：

```bash
python -m pip install python-docx
```

仓库内黄金样例可直接回归测试（在仓库根目录执行）：

```bash
# 1) 识别门禁校验（照片输入场景）
python scripts/verify_recognition_gate.py \
  --envelope assets/样例_识别回执.json \
  --out output/gate.json

# 2) 作文 JSON 契约校验
python scripts/verify_essay_json.py \
  --data assets/样例数据_2026-11-22_九年级语文作文.json \
  --report output/verify.json

# 3) 生成双份 Word
python scripts/build_essay_books.py \
  --data assets/样例数据_2026-11-22_九年级语文作文.json \
  --out output
```

全部脚本通过即输出：`GATE=PASS`、`ESSAY_JSON=PASS errors=0`、`BUILD=PASS`，并在 `output/` 生成家长版与学生版两份 `.docx` 及 manifest。

---

## 3. 输入条件（细致）

### 3.1 用户侧输入

| 项目 | 要求 |
|---|---|
| 作文载体 | 作文照片 / 截图（推荐原图、光线均匀、文字清晰），或直接粘贴纯文字 |
| 作文题目 / 材料 | **最好提供**；未提供时先问一次，仍无则走「题目缺失」降级分支 |
| 卷面得分与满分 | **最好提供**；未提供时先问一次，仍无则走「系统盲估」降级分支 |
| 科目与默认满分 | 语文默认 50 分五档＋加减分；英语默认 15 分＝内容 6＋语言 9；综能 45 分卷需显式说明 |
| 一次处理量 | 一篇作文 |

**降级分支的固定标注：**

- 题目缺失 → `prompt_available=false`、`core_word_source=正文反推`，产物标注「未提供题目，扣题维度无法核验，一类文判定可靠性下降」。
- 分数缺失 → `score_source=系统盲估`，给出条件性区间并标注「系统盲估，非真实阅卷分，误差通常正负 2 至 3 分」。
- 降级只影响判档口径与标注，**不降低识别门禁标准**。

### 3.2 脚本输入 JSON（`essay_input.json`，schema v1.1）

顶层字段与硬性校验：

| 字段 | 说明与校验 |
|---|---|
| `schema_version` | 固定 `1.1` |
| `meta` | `essay_type`（语文作文 / 英语书面表达）、`grade`、`date`、`full_score`（仅允许 15 / 45 / 50）、`score_system`、`exam_name`、`source`、`privacy_note` |
| `recognition_ref` | `gate` 必须为 `PASS` 且由脚本写入（AI 不得自填）；`mode` 为 `image_strict` 或 `text_direct`；`envelope_path` / `gate_file` 指向门禁文件 |
| `transcription` | `prompt_material`（题面）、`essay_body`（正文）、`annotated_body`（四色标注段，切片须可拼回原文） |
| `prompt_analysis` | `core_word` 非空、`core_word_status=confirmed`；无题目时 `prompt_available=false` 且 `reliability_note` 非空 |
| `scoring` | `final_score` 在 0–满分之间且落在档位区间；`score_source` 为「卷面实分」或「系统盲估」；后者须有 `blind_note` 与 `estimate_range`；`rubric_fingerprint` 锁定唯一基准 |
| `triage` | `adaptable` 布尔值与原因，先分诊再改稿 |
| `change_list` | 每项含 `id`、`para`、`original`、`changed`、`type`（删/换/补）、`chars`、`reason`、`point_gain`、`oral_tip`、`if_skipped` |
| `change_summary` | `count` 必须为 **12–18**；`within_threshold` 由脚本复算，手写值不一致即 FAIL |
| `final_draft` | 非空数组，可誊写定稿全文；核心词须在首 / 中 / 尾三段至少出现 |
| `variants` | 变式题；每项 `adapt_path` 须有事件 / 品质 / 意义三层且每层四要素（original / changed / why / how）齐全，三思路数组各 ≥3 条 |
| `method_notes` | 实战步骤 / 操作步骤与方法 / 底层逻辑 / 5 分钟自检清单，四项均非空 |
| `multi_path` | 多路评审 `routes`、`verdict`、`frozen` |
| `doubts` | 未解决（status=open）数必须为 0 |

完整字段定义与示例见 `references/数据契约_作文.md`，黄金样例见 `assets/样例数据_2026-11-22_九年级语文作文.json`。

---

## 4. 输出条件（细致）

### 4.1 脚本输出

| 输出 | 说明 |
|---|---|
| `output/<日期>/<作文名>_家长版四色诊断报告.docx` | 家长版报告 |
| `output/<日期>/<作文名>_学生版大白话操作卡.docx` | 学生版一页纸 |
| `output/<日期>/<作文名>_manifest.json` | 机器可读校验结果（脚本生成，不手写） |

manifest 关键检查项：`color_audit=none missing`（黑红绿灰四色齐全）、`strike_audit=present`（删除线 run 级存在）、`privacy_hits=0`、`change_count_match`、`change_id_closed`（M 编号闭环）、`final_draft_present`、`variant_count_match`、`dual_consistency`、`gate=PASS`、`frozen_unmodified`，全部通过时 `status=PASS`。

### 4.2 家长版报告必含内容

失分诊断表 → 四色标注学生原文（黑＝保留 / 红＝建议改 / 绿＝新增 / 灰删除线＝删，配 M 编号）→ 六栏改动合并表（第几处｜我原来写的｜建议改成｜为什么改｜对应采分点｜不改的后果）→ 改动量统计 → 变式三思路＋三层四要素 → 存疑与能力边界 → 文末定稿全文。

**禁止**出现六类技术元信息：作文类型、满分、卷面定位轨迹、评分指纹、识别门禁、入口分诊。

### 4.3 学生版一页纸必含内容

我考什么（大白话）→ 我的原文对改后（红字标「就改这一处」）→ 记一句口诀 → 老素材怎么套新题（三层一句话）→ 考场自检 3–5 条 → 变式题（答案放文末「做完再看」）→ 降级标注（大白话）。

### 4.4 交付门禁

- 识别门禁：照片输入必须过 12 项核验，结论由脚本写入，禁止 AI 自证「完全过关」。
- 交付门禁：G1–G14 全部 PASS 才输出 Word；任一脚本自检未 PASS 禁止交付。
- 四色着色必须从 `annotated_body` 标注段读取，禁止用字符串猜测着色。

---

## 5. 工作流程（L0–L7）

| 层 | 内容 |
|---|---|
| 开局定档 | 科目、满分、评分版本、识别档、评审开关、改动额度、降级标注 |
| L0 识别 | 逐字转写、三色分离、存疑标注；STOP 1：用户确认转写 |
| L1 分诊 | 判断是否适合最小改动，立意结构根本缺陷不硬改 |
| L2 评分 | 锁定唯一基准，给条件性预估区间 |
| L3 诊断 | 定位首要失分点，输出诊断表；STOP 2：用户确认继续 |
| L4 最小改动 | 12–18 处改动，每处带 oral_tip，脚本复算改动量 |
| L5 校验 | 核心词三处见、编号闭环、四色与删除线自检 |
| L6 变式 | 三层四要素 + 三思路，出 3 道变式题 |
| L7 渲染 | 双份 Word + manifest，隐私扫描 |

完整规则与 STOP 点见 `SKILL.md`。

---

## 6. 目录结构

```
high-score-essay/
├── SKILL.md                     # 主规则（七层结构、铁律、STOP 点）
├── README.md                    # 本文件
├── LICENSE                      # MIT License
├── .gitignore
├── icon.png / icon.svg          # 技能图标
├── assets/
│   ├── paths.json               # 包内相对路径清单（无绝对路径）
│   ├── 样例_识别回执.json / 样例_识别门禁.json
│   ├── 样例数据_2026-11-22_九年级语文作文.json   # 黄金样例
│   └── 样例数据_2026-11-09_九年级数学.json
├── references/                  # 识别核心、评分口径、数据契约、改写规则等规则文档
├── engines/README.md            # 引擎路由表
└── scripts/
    ├── verify_recognition_gate.py  # 识别门禁
    ├── verify_essay_json.py        # JSON 契约与改动量校验
    ├── build_essay_books.py        # 双份 Word 渲染（作文）
    ├── build_books.py              # 双份 Word 渲染（通用范式）
    ├── freeze_routes.py            # 多路评审冻结
    ├── docx_kit.py / docx_kit_local.py  # Word 渲染工具包
```

---

## 7. 隐私与安全

- 本仓库**不含**任何姓名、学校、班级、学号、考号、座位号，样例数据统一以「该生」指代学生。
- 本仓库**不含**任何 API Key、Token、密码、密钥、本机绝对路径或外部服务凭证。
- 所有资源以仓库根目录为基准按相对路径解析；默认输出到当前工作目录的 `output/`，不写入仓库内部。
- 脚本内置隐私扫描：输入 JSON 混入身份信息、产物出现身份信息时退出码 1，拒绝交付。

---

## 8. 许可证

[MIT License](LICENSE) · Copyright (c) 2026 勇哥

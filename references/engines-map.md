# 引擎路由与复用边界

## 1. 复用 vs 新建判定

| 能力 | 决策 | 理由 |
|---|---|---|
| L1 识别规则 | 本包内嵌（`references/L1_识别核心.md`） | 唯一事实来源，避免规则漂移 |
| `scripts/docx_kit_local.py` | 本包内嵌 import | 三色 run／隐私／排期原语，随包提供保证可移植 |
| `scripts/build_books.py` | 仅作范式参照，**不直接复用渲染** | 其 schema 是试卷诊断结构，套作文会残留旧字段、破坏模板数据分离 |
| `build_essay_books.py` | 新建 | 作文特有章节：改动清单对照、变式作文题、实战步骤、方法底层逻辑 |
| `verify_recognition_gate.py` | 新建 | 识别量化门禁 |
| `verify_essay_json.py` | 新建 | 改动量硬指标与契约校验 |
| `freeze_routes.py` | 新建 | 多路哈希冻结与趋同检测 |
| `error-patterns.md` | 本包内嵌追加 | 误识别经验库随包提供，就地追加 |

## 2. 包内资产路径（集中写在 assets/paths.json）

| 资产 | 路径 |
|---|---|
| 主规则 | `SKILL.md` |
| L1 识别引擎 | `references/L1_识别核心.md` |
| 三步口径 | `references/三步口径.md` |
| 白话改写规则 | `references/白话改写规则.md` |
| 误识别模式库 | `references/error-patterns.md` |
| docx_kit.py | `本包 scripts/docx_kit.py` |
| Python 解释器 | `python3 / python` |
| 成果落盘 | `output/<YYYY-MM-DD>/` |

## 3. 引擎路由表

| 层 | 引擎 | 调用方式 |
|---|---|---|
| L0 识别 | `references/L1_识别核心.md` | 模型行为规则，开局强制 Read；脚本裁门禁 |
| L0 误识别模式 | `references/error-patterns.md` | 追加到本包文件，同类只记一条 |
| L3 评分 | 本技能 `references/作文评分口径.md` | 模型执行，锁定基准 |
| L4 最小改动 | 本技能 `references/最小改动方法.md` | 模型执行，脚本复算改动量 |
| L6 变式 | 本技能 `references/变式题目设计.md` | 模型执行 |
| L7 多路 | 本技能 `scripts/freeze_routes.py` | 脚本冻结与趋同检测 |
| L7 渲染 | `scripts/build_essay_books.py` ＋ `scripts/docx_kit_local.py` | 脚本执行 |

## 4. 最大风险与兜底

| 风险 | 兜底 |
|---|---|
| L1 规则丢失／漂移 | 开局强制 Read＋哈希版本锁；门禁只由脚本写入；抽样复读＋留痕 |
| 路径写死 | 全部相对路径集中 `assets/paths.json`，启动时逐个存在性检查，失效明确报错 |
| 扫描件识别失败 | 原生裁切→放大→重拍→用户录入兜底，标"非识别过关"，禁止硬读 |
| 作文隐私泄露 | 输入侧预遮蔽＋输出侧语义扫描；真实身份入文同时提示扣分风险 |
| 评分口径误用 | schema 强校验满分与档位一致，单次运行只用一个标准 |
| AI 重写全文 | 改动量硬指标复算，超标判失败，改动项必须带 `oral_tip` |
| 多路趋同 | 调用 ID 与哈希冻结，相似度过高判无效重跑 |
| 脚本失败 | preflight 检查输出目录可写、Python 有效、脚本存在；失败即停，禁止静默降级 |

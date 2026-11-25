# 引擎目录说明

本技能为**自包含实现**：识别规则、渲染工具与门禁脚本均已随包提供，运行时不读取本仓库以外的任何文件。

本目录仅保留路由表，实现细节见 `references/engines-map.md`。

| 层 | 引擎 | 载体 | 调用方式 |
|---|---|---|---|
| L0 识别 | `references/L1_识别核心.md` | 模型行为规则 | 开局强制 Read 本包内嵌 L1，脚本裁门禁 |
| L0 误识别模式 | `references/error-patterns.md` | 本包内嵌文件 | 追加到本包内嵌库，同类只记一条 |
| L3 评分 | `references/作文评分口径.md` | 规则文档 | 锁定唯一基准，生成评分标准指纹 |
| L4 最小改动 | `references/最小改动方法.md` | 规则文档 | 模型执行，脚本复算改动量 |
| L6 变式 | `references/变式题目设计.md` | 规则文档 | 模型执行 |
| L7 多路 | `scripts/freeze_routes.py` | 可执行脚本 | 分次独立调用后冻结与趋同检测 |
| L7 渲染 | `scripts/build_essay_books.py` ＋ `scripts/docx_kit_local.py` | 可执行脚本 | 模板与数据分离，换作文只改 JSON |

四层门禁脚本均位于 `scripts/`，路径集中在 `assets/paths.json`，禁止散落硬编码。

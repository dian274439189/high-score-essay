# 两份 Word 交付文档模板与生成规范

## 通用要求

- 保存路径：`output/<YYYY-MM-DD>/`
- 生成方式：走本包自带的 Word 渲染流程（scripts/build_essay_books.py ＋ scripts/docx_kit_local.py → python-docx 颜色自检）
- 颜色必须真实写入 docx，不得只做视觉近似

## 颜色规范（三色体系）

| 内容类型 | 标签写法 | docx 颜色 |
|----------|----------|-----------|
| 印刷原题 | 黑色 RGB (0, 0, 0) | #000000 |
| 学生手写答案 | 深蓝色 RGB (0, 51, 153) | #003399 |
| 红字批改/红字答案 | 正红色 RGB (192, 0, 0) | #C00000 |
| 【识别存疑】【已划掉】标注 | 灰色/橙色小标注 | #E67E22 或 #7F8C8D |

## 文档一：纯净版结构

```
页首：试卷标题（如有）＋ 学生化名 ＋ 提取日期
（逐题，题号顺序严格与试卷一致）

题号：一/1
【原题】（印刷体内容，黑色）
【学生作答】（手写内容，深蓝）
【红字批改】（批改内容，正红；无则写（无））
```

- 只放三类内容，不放解释、不放置信度
- 【已划掉】内容紧跟原作答后，用灰色小字标注
- 表格类题目用 Word 表格还原结构

## 文档二：详细说明版结构

在纯净版全部内容之外，依次追加：

```
一、图片归属与题号映射表
   | 图片序号 | 拍摄内容 | 覆盖题号 |
二、三色图层分离说明
   - 分离方法、黑红比例、是否有铅笔/蓝笔及处理方式
三、逐题识别置信度表
   | 题号 | 原题置信 | 手写置信 | 红字置信 | 存疑点 |
四、【识别存疑】清单
   - 每条：题号 + 存疑文字 + 存疑原因（连笔/污渍/低分辨率）
五、【已划掉】内容清单
六、图像质量问题记录
   - 倾斜、阴影、反光、模糊等及对识别的影响
七、历史误识别模式核对记录
   - 本次识别中参考 error-patterns.md 核对过哪些模式
```

## 自检命令（交付前必做）

```bash
"python3 / python" -c "
from docx import Document
d = Document(r'<docx路径>')
colors = set()
for p in d.paragraphs:
    for r in p.runs:
        if r.font.color and r.font.color.rgb: colors.add(str(r.font.color.rgb))
for t in d.tables:
    for row in t.rows:
        for c in row.cells:
            for p in c.paragraphs:
                for r in p.runs:
                    if r.font.color and r.font.color.rgb: colors.add(str(r.font.color.rgb))
print('颜色集合:', sorted(colors))
print('表格数:', len(d.tables))
"
```

预期：颜色集合包含 000000、003399、C00000（纯净版）；详细版另含标注色。

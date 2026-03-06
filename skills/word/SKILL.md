---
name: word
description: "Use this skill whenever the user wants to create, edit, or format Word (.docx) documents. This includes creating academic papers with proper formatting, inserting three-line tables (学术三线表), converting LaTeX formulas to native Word equations, generating reference lists in GB/T 7714 or APA format, setting page margins/fonts/headers/footers, and any task that produces a .docx file. Trigger especially for Chinese academic paper formatting (宋体/Times New Roman, standard margins, heading styles). Do NOT trigger when the primary deliverable is PDF, Excel, or HTML."
---

# Word Document Processing Guide

## Overview

This skill handles all Word (.docx) document operations using `python-docx`, with specialized support for Chinese academic paper formatting. Key capabilities:

- Create academic papers with standard formatting (fonts, margins, headings)
- Insert three-line tables (三线表) from data/CSV
- Convert LaTeX formulas to native Word OMML equations
- Generate GB/T 7714 or APA reference lists
- Set headers, footers, and page numbers

## Dependencies

All dependencies are pre-installed:
- `python-docx` (1.2.0+) — Core Word document manipulation
- `lxml` — XML processing for OMML formula conversion
- `latex2mathml` — LaTeX to MathML conversion

## Quick Start

### Create a basic academic paper

```python
import subprocess, sys
result = subprocess.run(
    [sys.executable, "/skills/word/scripts/create_docx.py",
     "--title", "数字经济对区域创新的影响研究",
     "--author", "张三",
     "--institution", "某某大学经济学院",
     "--output", "/workspace/paper.docx"],
    capture_output=True, text=True, timeout=60
)
print(result.stdout)
```

### Insert a three-line table

```python
import subprocess, sys
result = subprocess.run(
    [sys.executable, "/skills/word/scripts/add_table.py",
     "--docx", "/workspace/paper.docx",
     "--csv", "/workspace/regression_results.csv",
     "--title", "表1 基准回归结果",
     "--output", "/workspace/paper.docx"],
    capture_output=True, text=True, timeout=60
)
print(result.stdout)
```

### Insert a LaTeX formula

```python
import subprocess, sys
result = subprocess.run(
    [sys.executable, "/skills/word/scripts/add_formula.py",
     "--docx", "/workspace/paper.docx",
     "--latex", "Y_{it} = \\alpha + \\beta X_{it} + \\gamma Z_{it} + \\epsilon_{it}",
     "--label", "(1)",
     "--output", "/workspace/paper.docx"],
    capture_output=True, text=True, timeout=60
)
print(result.stdout)
```

### Add reference list

```python
import subprocess, sys, json

refs = [
    {"type": "journal", "authors": "张三,李四", "year": "2023", "title": "数字经济与创新驱动", "journal": "经济研究", "volume": "58", "issue": "3", "pages": "45-60"},
    {"type": "journal", "authors": "Wang, X.,Li, Y.", "year": "2022", "title": "Digital Economy and Innovation", "journal": "Journal of Economic Perspectives", "volume": "36", "issue": "2", "pages": "125-148"}
]

with open("/workspace/refs.json", "w", encoding="utf-8") as f:
    json.dump(refs, f, ensure_ascii=False)

result = subprocess.run(
    [sys.executable, "/skills/word/scripts/add_references.py",
     "--docx", "/workspace/paper.docx",
     "--refs", "/workspace/refs.json",
     "--style", "gbt7714",
     "--output", "/workspace/paper.docx"],
    capture_output=True, text=True, timeout=60
)
print(result.stdout)
```

## Programmatic Usage (import in Python)

For more control, import the modules directly:

```python
import sys
sys.path.insert(0, "/skills/word/scripts")
from create_docx import create_academic_paper
from add_table import insert_three_line_table
from add_formula import insert_formula
from add_references import add_reference_list
from format_utils import Cm, Pt, set_paragraph_format

# Create paper
doc = create_academic_paper(
    title="数字经济对区域创新的影响研究",
    author="张三",
    institution="某某大学经济学院"
)

# Add content paragraph
from format_utils import add_body_paragraph
add_body_paragraph(doc, "本文基于2010-2022年省级面板数据，实证检验了数字经济对区域创新的影响。")

# Insert table from list data
headers = ["变量", "(1) OLS", "(2) FE", "(3) RE"]
data = [
    ["digital_economy", "0.234***", "0.189***", "0.201***"],
    ["", "(0.045)", "(0.038)", "(0.041)"],
    ["controls", "Yes", "Yes", "Yes"],
    ["N", "310", "310", "310"],
    ["R²", "0.456", "0.523", "0.498"]
]
insert_three_line_table(doc, headers, data, title="表1 基准回归结果")

# Insert formula
insert_formula(doc, r"Y_{it} = \alpha + \beta X_{it} + \gamma Z_{it} + \epsilon_{it}", label="(1)")

# Save
doc.save("/workspace/paper.docx")
```

## Academic Paper Formatting Standards

### Page Setup (Chinese academic standard)
- Paper size: A4 (210mm × 297mm)
- Margins: Top 2.54cm, Bottom 2.54cm, Left 3.17cm, Right 3.17cm
- Line spacing: 1.5 lines (正文), Single (tables/footnotes)

### Font Standards
| Element | Chinese Font | English/Number Font | Size |
|---------|-------------|-------------------|------|
| Title (论文标题) | 黑体 (SimHei) | Times New Roman | 二号 (22pt) |
| Heading 1 (一级标题) | 黑体 | Times New Roman | 三号 (16pt) |
| Heading 2 (二级标题) | 黑体 | Times New Roman | 四号 (14pt) |
| Heading 3 (三级标题) | 黑体 | Times New Roman | 小四 (12pt) |
| Body (正文) | 宋体 (SimSun) | Times New Roman | 小四 (12pt) |
| Table content | 宋体 | Times New Roman | 五号 (10.5pt) |
| Footnote | 宋体 | Times New Roman | 小五 (9pt) |
| Header/Footer | 宋体 | Times New Roman | 小五 (9pt) |

### Three-Line Table Rules (三线表)
- Top border: 1.5pt solid black
- Header-body separator: 0.75pt solid black
- Bottom border: 1.5pt solid black
- No vertical borders, no other horizontal borders
- Table title above table, centered, 黑体 小四
- Table notes below table, left-aligned, 宋体 小五

### Formula Formatting
- Formulas centered, with equation number right-aligned in parentheses
- Use Word native OMML equations (not images)
- Conversion path: LaTeX → MathML → OMML

## Common Workflows

### Full Paper Generation
1. `create_docx.py` — Set up document structure with title page, abstract, headings
2. Write body content using programmatic API
3. `add_table.py` — Insert regression result tables
4. `add_formula.py` — Insert model specification equations
5. `add_references.py` — Append formatted reference list
6. Save final .docx to `/workspace/`

### Stata Results → Word Table
1. Run Stata regression, export to CSV via `esttab`
2. Use `add_table.py --csv results.csv` to convert to three-line table
3. Table auto-formatted with significance stars preserved

## New Capabilities

### Table of Contents (目录)

```python
import sys
sys.path.insert(0, "/skills/word/scripts")
from create_docx import create_academic_paper
from format_utils import setup_heading_styles, add_heading_with_style, insert_toc

doc = create_academic_paper(title="论文标题", author="张三", institution="某大学")

# IMPORTANT: setup heading styles first (required for TOC)
setup_heading_styles(doc)

# Insert TOC (user needs to right-click → Update Field in Word)
insert_toc(doc, title="目  录", max_level=3)

# Use add_heading_with_style (not add_heading_paragraph) for TOC-compatible headings
add_heading_with_style(doc, "一、引言", level=1)
add_heading_with_style(doc, "（一）研究背景", level=2)

doc.save("/workspace/paper_with_toc.docx")
```

**Note**: After opening in Word, right-click the TOC area → "Update Field" → "Update entire table" to generate page numbers.

### Figure/Image Insertion (图片+图题)

```python
from format_utils import insert_image

# Insert image with caption below (Chinese standard)
insert_image(doc, "/workspace/trend.png", width_cm=12, caption="图1 数字经济发展趋势")

# Caption above (less common)
insert_image(doc, "/workspace/map.png", width_cm=10, caption="图2 空间分布", caption_position='above')
```

### Footnotes (脚注)

```python
from format_utils import add_body_paragraph, add_footnote

p = add_body_paragraph(doc, "数字经济指数参考北京大学数字金融研究中心发布的指标体系")
add_footnote(p, "数据来源：北京大学数字金融研究中心，https://idf.pku.edu.cn")
```

### Cover Page (毕业论文封面)

```python
from format_utils import add_cover_page

doc = Document()
add_cover_page(
    doc,
    title="数字经济对区域创新能力的影响研究",
    author="张三",
    student_id="2022010001",
    major="应用经济学",
    supervisor="李四 教授",
    institution="某某大学",
    degree="硕士",
    date_str="2025年6月",
    logo_path="/workspace/university_logo.png"  # Optional
)
# Cover page auto-adds page break; continue with abstract, body, etc.
```

### Modify Existing Documents (修改已有文档格式)

```python
import subprocess, sys

# View document info
result = subprocess.run(
    [sys.executable, "/skills/word/scripts/modify_docx.py",
     "/workspace/draft.docx", "--info"],
    capture_output=True, text=True, timeout=60
)
print(result.stdout)

# One-click academic formatting (fonts + margins + spacing + indent)
result = subprocess.run(
    [sys.executable, "/skills/word/scripts/modify_docx.py",
     "/workspace/draft.docx", "--academic",
     "--output", "/workspace/formatted.docx"],
    capture_output=True, text=True, timeout=60
)
print(result.stdout)

# Selective: only fix fonts and tables
result = subprocess.run(
    [sys.executable, "/skills/word/scripts/modify_docx.py",
     "/workspace/draft.docx", "--fonts", "--tables",
     "--output", "/workspace/fixed.docx"],
    capture_output=True, text=True, timeout=60
)
print(result.stdout)
```

Programmatic usage:
```python
import sys
sys.path.insert(0, "/skills/word/scripts")
from modify_docx import load_docx, apply_academic_format, get_document_info

doc = load_docx("/workspace/draft.docx")
print(get_document_info(doc))  # Check structure first
apply_academic_format(doc, tables=True)  # Full reformat including tables
doc.save("/workspace/formatted.docx")
```

### Page Breaks and Section Breaks

```python
from format_utils import add_page_break, add_section_break

add_page_break(doc)  # Simple page break
add_section_break(doc, start_type='new_page')  # Section break (new page)
add_section_break(doc, start_type='continuous')  # Continuous section break
```

## Important Notes

- All scripts support both CLI and programmatic (import) usage
- Chinese fonts (SimSun, SimHei) must be available on the system; scripts fall back to available fonts gracefully
- LaTeX formula conversion handles most common math notation; very complex formulas may need manual adjustment
- Output files are always saved to the user-specified path (default: `/workspace/`)
- For multi-section papers, use the programmatic API for finer control over document structure
- **TOC requires built-in Heading styles**: Use `add_heading_with_style()` instead of `add_heading_paragraph()` when you need a TOC
- **TOC needs manual update**: After opening in Word, right-click TOC → Update Field to populate page numbers
- **Footnotes use oxml**: python-docx doesn't natively support footnotes; our implementation uses direct XML manipulation
- **modify_docx.py --academic**: One-click command to reformat any existing .docx to Chinese academic standard

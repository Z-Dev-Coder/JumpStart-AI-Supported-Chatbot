"""Builds the Findings, Discussion & Reflection Word report from the 3 markdown sections."""
import re
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE = r"D:\Software Engineering\HDSE\HDSE-CPL-Capstone Project - Application Development\JumpStart"
REPORTS = BASE + r"\Reports"

IMAGE_MAP = {
    "Reports/Screenshots/Admin-and-Staff-Dashboards/04_admin_ai_performance.png": REPORTS + r"\Screenshots\Admin-and-Staff-Dashboards\04_admin_ai_performance.png",
    "Reports/Screenshots/Admin-and-Staff-Dashboards/06_admin_audit_log_per_message_detail.png": REPORTS + r"\Screenshots\Admin-and-Staff-Dashboards\06_admin_audit_log_per_message_detail.png",
    "Reports/Screenshots/04_human_handover.png": REPORTS + r"\Screenshots\04_human_handover.png",
    "Reports/Screenshots/Admin-and-Staff-Dashboards/02_staff_case_with_ai_handover_package.png": REPORTS + r"\Screenshots\Admin-and-Staff-Dashboards\02_staff_case_with_ai_handover_package.png",
    "Reports/Screenshots/Usability-Task-Walkthrough/task2_clarification.png": REPORTS + r"\Screenshots\Usability-Task-Walkthrough\task2_clarification.png",
}

doc = Document()

style = doc.styles['Normal']
style.font.name = 'Calibri'
style.font.size = Pt(11)

title = doc.add_heading('JumpStart AI Support — Evaluation Findings, Discussion & Reflection', level=0)

files = [
    REPORTS + r"\Report-Section-1-Evaluation-Results.md",
    REPORTS + r"\Report-Section-2-Discussion.md",
    REPORTS + r"\Report-Section-3-Reflection.md",
]

def add_table_from_md(lines, idx):
    rows = []
    while idx < len(lines) and lines[idx].strip().startswith('|'):
        row = [c.strip() for c in lines[idx].strip().strip('|').split('|')]
        rows.append(row)
        idx += 1
    # remove separator row (---|---)
    rows = [r for r in rows if not all(re.match(r'^:?-+:?$', c) for c in r)]
    if not rows:
        return idx
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = 'Light Grid Accent 1'
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            table.cell(r, c).text = cell
            if r == 0:
                for p in table.cell(r, c).paragraphs:
                    for run in p.runs:
                        run.bold = True
    doc.add_paragraph()
    return idx

def add_inline_runs(paragraph, text):
    # handle **bold** and *italic* minimally
    parts = re.split(r'(\*\*.+?\*\*)', text)
    for part in parts:
        m = re.match(r'^\*\*(.+)\*\*$', part)
        if m:
            run = paragraph.add_run(m.group(1))
            run.bold = True
        else:
            paragraph.add_run(part)

for fpath in files:
    with open(fpath, encoding='utf-8') as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip('\n')
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith('# '):
            doc.add_heading(stripped[2:].strip(), level=1)
        elif stripped.startswith('## '):
            doc.add_heading(stripped[3:].strip(), level=2)
        elif stripped.startswith('### '):
            doc.add_heading(stripped[4:].strip(), level=3)
        elif stripped.startswith('|'):
            i = add_table_from_md(lines, i)
            continue
        elif stripped.startswith('[INSERT IMAGE:'):
            m = re.match(r'\[INSERT IMAGE:\s*(.+?)\s*—\s*(.+)\]', stripped)
            if m:
                rel_path, caption = m.group(1).strip(), m.group(2).strip()
                img_path = IMAGE_MAP.get(rel_path)
                if img_path:
                    try:
                        doc.add_picture(img_path, width=Inches(5.8))
                        cap = doc.add_paragraph(caption)
                        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        cap.runs[0].italic = True
                        cap.runs[0].font.size = Pt(9)
                    except Exception as e:
                        doc.add_paragraph(f"[Image not found: {rel_path} — {e}]")
                else:
                    doc.add_paragraph(f"[Image placeholder: {rel_path} — {caption}]")
            doc.add_paragraph()
        elif stripped.startswith('[PUT LINK:') or stripped.startswith('[UPDATE THIS LINE') or stripped.startswith('[FILL IN'):
            p = doc.add_paragraph()
            run = p.add_run(stripped)
            run.italic = True
            run.font.color.rgb = None
        elif re.match(r'^\d+\.\s', stripped):
            p = doc.add_paragraph(style='List Number')
            add_inline_runs(p, re.sub(r'^\d+\.\s', '', stripped))
        elif stripped.startswith('- '):
            p = doc.add_paragraph(style='List Bullet')
            add_inline_runs(p, stripped[2:])
        elif stripped.startswith('  - ') or stripped.startswith('    - '):
            p = doc.add_paragraph(style='List Bullet 2')
            add_inline_runs(p, stripped.lstrip().lstrip('- '))
        elif stripped == '---':
            pass
        else:
            p = doc.add_paragraph()
            add_inline_runs(p, stripped)

        i += 1

    doc.add_page_break()

out_path = REPORTS + r"\JumpStart-Evaluation-Findings-Discussion-Reflection.docx"
doc.save(out_path)
print("Saved:", out_path)

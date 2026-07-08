import os
import re
import io
from datetime import datetime, date
from fpdf import FPDF
from fpdf.fonts import FontFace
from db import get_db_connection

def sanitize_pdf_text(text):
    if not text:
        return ""
    # Map of unicode characters to Latin-1/ASCII equivalents
    replacements = {
        '\u2014': '-',  # em-dash —
        '\u2013': '-',  # en-dash –
        '\u201c': '"',  # curly double open
        '\u201d': '"',  # curly double close
        '\u2018': "'",  # curly single open
        '\u2019': "'",  # curly single close
        '\u00a0': ' ',  # non-breaking space
    }
    for uni_char, ascii_char in replacements.items():
        text = text.replace(uni_char, ascii_char)
    return text.encode('latin-1', 'replace').decode('latin-1')

def generate_timesheet_pdf_data(selected_month):
    consultant_name = sanitize_pdf_text(os.getenv("CONSULTANT_NAME", "Consultant"))
    company_name = sanitize_pdf_text(os.getenv("COMPANY_NAME", "Company"))
    
    try:
        sel_year, sel_mon = int(selected_month[:4]), int(selected_month[5:7])
    except (ValueError, IndexError):
        sel_year, sel_mon = datetime.now().year, datetime.now().month
        selected_month = f"{sel_year}-{sel_mon:02d}"
    
    month_label = date(sel_year, sel_mon, 1).strftime('%B %Y')
    
    conn = get_db_connection()
    logs = conn.execute(
        'SELECT * FROM logs WHERE date LIKE ? ORDER BY date ASC',
        (selected_month + '%',)
    ).fetchall()
    conn.close()
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, f"Timesheet - {month_label}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)
    
    # Consultant name
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Consultant: {consultant_name}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    
    # Column widths
    col_date = 25
    col_hours = 15
    col_eur = 25
    col_tasks = 125
    line_height = 6
    
    # Styles
    headings_style = FontFace(
        family="Helvetica",
        emphasis="B",
        size_pt=10,
        color=(255, 255, 255),
        fill_color=(59, 130, 246)
    )
    
    total_hours = 0.0
    total_payment = 0.0
    
    # Create the table using FPDF table API
    with pdf.table(
        col_widths=(col_date, col_hours, col_eur, col_tasks),
        headings_style=headings_style,
        line_height=line_height,
        text_align="CENTER",
        v_align="MIDDLE"
    ) as table:
        # Header Row
        row = table.row()
        row.cell("Date")
        row.cell("Hours")
        row.cell("EUR")
        row.cell("Tasks")
        
        fill = False
        pattern = re.compile(r';|\r?\n|,(?=\s*(?:Epic|Bug|Issue|Pull Request|PR|Task)\b)', re.IGNORECASE)
        
        for log in logs:
            total_hours += log['hours']
            total_payment += log['payment']
            
            # Split tasks by semicolon, newline, or comma (if followed by task prefix)
            tasks_text = log['tasks_summary'] or ''
            raw_tasks = pattern.split(tasks_text)
            tasks_lines = [t.strip() for t in raw_tasks if t.strip()]
            tasks_multiline = sanitize_pdf_text('\n'.join(tasks_lines)) if tasks_lines else ''
            
            bg_color = (240, 240, 250) if fill else (255, 255, 255)
            row_style = FontFace(family="Helvetica", size_pt=9, fill_color=bg_color)
            
            row = table.row()
            row.cell(log['date'], style=row_style, align="CENTER")
            row.cell(str(log['hours']), style=row_style, align="CENTER")
            row.cell(f"{log['payment']:.2f}", style=row_style, align="CENTER")
            row.cell(tasks_multiline, style=row_style, align="LEFT")
            
            fill = not fill
            
        # Totals Row
        total_style = FontFace(
            family="Helvetica",
            emphasis="B",
            size_pt=10,
            color=(255, 255, 255),
            fill_color=(30, 41, 59)
        )
        row = table.row()
        row.cell("TOTAL", style=total_style, align="CENTER")
        row.cell(str(total_hours), style=total_style, align="CENTER")
        row.cell(f"{total_payment:.2f}", style=total_style, align="CENTER")
        row.cell("", style=total_style)
        
    filename = f"Timesheet {company_name} {month_label}.pdf"
    return bytes(pdf.output()), filename

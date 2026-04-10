import os
import sqlite3
import io
import calendar
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, redirect, flash, make_response, send_file
from dotenv import load_dotenv
from fpdf import FPDF
from holidays_ro import get_holidays_for_month

import sys
# Add current directory to path to absolute import azure_service
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from azure_service import AzureDevOpsService
except ImportError:
    pass # Will be handled if missing in the final directory

load_dotenv()

app = Flask(__name__)
app.secret_key = 'super_secret_dev_key' # for flash messages

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'timesheet.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    # Determine which month to display
    selected_month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    try:
        sel_year, sel_mon = int(selected_month[:4]), int(selected_month[5:7])
    except (ValueError, IndexError):
        sel_year, sel_mon = datetime.now().year, datetime.now().month
        selected_month = f"{sel_year}-{sel_mon:02d}"
    
    # Previous / Next month strings for navigation
    if sel_mon == 1:
        prev_month = f"{sel_year - 1}-12"
    else:
        prev_month = f"{sel_year}-{sel_mon - 1:02d}"
    if sel_mon == 12:
        next_month = f"{sel_year + 1}-01"
    else:
        next_month = f"{sel_year}-{sel_mon + 1:02d}"
    
    conn = get_db_connection()
    # Only fetch logs for the selected month
    logs = conn.execute('SELECT * FROM logs WHERE date LIKE ? ORDER BY date DESC', (selected_month + '%',)).fetchall()
    
    month_totals = conn.execute(
        'SELECT COALESCE(SUM(hours), 0) as total_hours, COALESCE(SUM(payment), 0) as total_payment, COUNT(*) as days_logged FROM logs WHERE date LIKE ?',
        (selected_month + '%',)
    ).fetchone()
    conn.close()
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    hourly_rate = float(os.getenv("HOURLY_RATE", 35.0))
    
    # Calendar data for the selected month
    holidays = get_holidays_for_month(sel_year, sel_mon)
    logged_dates = [log['date'] for log in logs]
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(sel_year, sel_mon)
    
    # Calculate working days (weekdays minus holidays that fall on weekdays)
    import calendar as cal_mod
    num_days_in_month = cal_mod.monthrange(sel_year, sel_mon)[1]
    working_days = 0
    for d in range(1, num_days_in_month + 1):
        dt = date(sel_year, sel_mon, d)
        if dt.weekday() < 5 and dt.isoformat() not in holidays:
            working_days += 1
    
    # Human-readable month label
    month_label = date(sel_year, sel_mon, 1).strftime('%B %Y')
    
    return render_template('index.html', logs=logs, today=today_str, hourly_rate=hourly_rate,
                           total_hours=month_totals['total_hours'],
                           total_payment=month_totals['total_payment'],
                           days_logged=month_totals['days_logged'],
                           current_month=month_label,
                           selected_month=selected_month,
                           prev_month=prev_month,
                           next_month=next_month,
                           holidays=holidays,
                           logged_dates=logged_dates,
                           month_days=month_days,
                           cal_year=sel_year,
                           cal_month=sel_mon,
                           working_days=working_days)

@app.route('/api/azure-tasks')
def fetch_azure_tasks():
    try:
        organization = os.getenv("AZURE_ORGANIZATION")
        project = os.getenv("AZURE_PROJECT")
        pat_token = os.getenv("AZURE_PAT_TOKEN")
        email = os.getenv("AZURE_EMAIL")
        
        if not pat_token or pat_token == "your_pat_token_here":
            return jsonify({"error": "Azure PAT Token not configured properly."}), 400
            
        azure_service = AzureDevOpsService(organization, project, pat_token)
        items = azure_service.get_my_active_tasks(email)
        
        # Filter out blocked or waiting items based on System.BoardColumn
        filtered_items = []
        for item in items:
            fields = item.get('fields', {})
            board_column = fields.get('System.BoardColumn', '')
            
            # Only include tasks in Engineering (PR)
            if board_column.lower() not in ['engineering (pr)']:
                continue
            
            item_type = fields.get('System.WorkItemType', 'Item')
            item_id = item.get('id', '')
            title = fields.get('System.Title', '')
            
            filtered_items.append(f"{item_type} {item_id}: {title}")
            
        combined_string = ", ".join(filtered_items)
        if not combined_string:
            combined_string = "No active engineering tasks found today."
            
        return jsonify({"tasks": combined_string})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/log', methods=['POST'])
def log_day():
    date = request.form.get('date')
    hours = request.form.get('hours', 8.0)
    hourly_rate = float(os.getenv("HOURLY_RATE", 35.0))
    payment = request.form.get('payment', float(hours) * hourly_rate)
    tasks_summary = request.form.get('tasks_summary', '')
    
    if not date:
        flash("Date is required!", "error")
        return redirect('/')
        
    try:
        conn = get_db_connection()
        # Upsert: If date exists, update it. If not, insert.
        conn.execute('''
            INSERT INTO logs (date, hours, payment, tasks_summary)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                hours=excluded.hours,
                payment=excluded.payment,
                tasks_summary=excluded.tasks_summary
        ''', (date, float(hours), float(payment), tasks_summary))
        conn.commit()
        conn.close()
        flash("Successfully logged time for " + date + "!", "success")
    except Exception as e:
        flash("Error saving log: " + str(e), "error")
        
    return redirect('/')

@app.route('/export')
def export_pdf():
    consultant_name = os.getenv("CONSULTANT_NAME", "Consultant")
    company_name = os.getenv("COMPANY_NAME", "Company")
    
    # Support month selection via query param
    selected_month = request.args.get('month', datetime.now().strftime('%Y-%m'))
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
    
    # Table Header
    pdf.set_fill_color(59, 130, 246)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(col_date, 10, "Date", border=1, fill=True, align="C")
    pdf.cell(col_hours, 10, "Hours", border=1, fill=True, align="C")
    pdf.cell(col_eur, 10, "EUR", border=1, fill=True, align="C")
    pdf.cell(col_tasks, 10, "Tasks", border=1, fill=True, align="C")
    pdf.ln()
    
    # Table Rows
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 9)
    
    total_hours = 0.0
    total_payment = 0.0
    fill = False
    
    for log in logs:
        total_hours += log['hours']
        total_payment += log['payment']
        
        # Split tasks by comma, each on its own line
        tasks_text = log['tasks_summary'] or ''
        tasks_lines = [t.strip() for t in tasks_text.replace(', ', ',').split(',') if t.strip()]
        tasks_multiline = '\n'.join(tasks_lines) if tasks_lines else ''
        num_lines = max(len(tasks_lines), 1)
        row_height = num_lines * line_height
        
        if fill:
            pdf.set_fill_color(240, 240, 250)
        else:
            pdf.set_fill_color(255, 255, 255)
        
        # Remember Y position before drawing
        y_before = pdf.get_y()
        x_start = pdf.l_margin
        
        # Draw fixed cells
        pdf.cell(col_date, row_height, log['date'], border=1, fill=True, align="C")
        pdf.cell(col_hours, row_height, str(log['hours']), border=1, fill=True, align="C")
        pdf.cell(col_eur, row_height, f"{log['payment']:.2f}", border=1, fill=True, align="C")
        
        # Draw tasks multi_cell (this moves cursor to next line automatically)
        pdf.multi_cell(col_tasks, line_height, tasks_multiline, border=1, fill=True)
        
        # Ensure cursor is at the correct Y after the row
        pdf.set_y(y_before + row_height)
        
        fill = not fill
    
    # Totals Row
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(col_date, 10, "TOTAL", border=1, fill=True, align="C")
    pdf.cell(col_hours, 10, str(total_hours), border=1, fill=True, align="C")
    pdf.cell(col_eur, 10, f"{total_payment:.2f}", border=1, fill=True, align="C")
    pdf.cell(col_tasks, 10, "", border=1, fill=True)
    
    # Output PDF
    from flask import send_file
    buffer = io.BytesIO(bytes(pdf.output()))
    buffer.seek(0)
    filename = f"Timesheet {company_name} {month_label}.pdf"
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(debug=True, port=5001)

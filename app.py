import os
import sqlite3
import io
import calendar
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, redirect, flash, make_response, send_file
from dotenv import load_dotenv
from fpdf import FPDF
from fpdf.fonts import FontFace
import re
from holidays_ro import get_holidays_for_month

import sys
# Add current directory to path to absolute import azure_service
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from azure_service import AzureDevOpsService
except ImportError:
    pass # Will be handled if missing in the final directory

load_dotenv()

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

app = Flask(__name__)
app.secret_key = 'super_secret_dev_key' # for flash messages

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'timesheet.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

import subprocess

def send_via_local_outlook(recipient_emails, subject, body, file_path):
    escaped_subject = subject.replace('\\', '\\\\').replace('"', '\\"')
    escaped_body = body.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\r')
    
    emails = [e.strip() for e in recipient_emails.split(",") if e.strip()]
    recipients_applescript = ""
    for email in emails:
        recipients_applescript += f'make new recipient at newMail with properties {{email address:{{address:"{email}"}}}}\n'
        
    applescript = f'''
    tell application "Microsoft Outlook"
        set newMail to make new outgoing message with properties {{subject:"{escaped_subject}"}}
        set content of newMail to "{escaped_body}"
        {recipients_applescript}
        make new attachment at newMail with properties {{file:POSIX file "{file_path}"}}
        send newMail
    end tell
    '''
    
    process = subprocess.Popen(
        ['osascript', '-e', applescript],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()
    
    if process.returncode != 0:
        raise Exception(stderr.decode('utf-8'))



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
    
    daily_amount = float(os.getenv("DAILY_AMOUNT", hourly_rate * 8))
    estimated_payment = working_days * daily_amount
    total_payment = month_totals['total_payment']
    progress_percent = (total_payment / estimated_payment * 100) if estimated_payment > 0 else 0.0
    progress_percent_clamped = min(progress_percent, 100.0)
    
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
                           working_days=working_days,
                           estimated_payment=estimated_payment,
                           progress_percent=progress_percent,
                           progress_percent_clamped=progress_percent_clamped,
                           default_recipients=os.getenv("DEFAULT_RECIPIENT_EMAILS", ""))

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

def generate_timesheet_pdf_data(selected_month):
    consultant_name = os.getenv("CONSULTANT_NAME", "Consultant")
    company_name = os.getenv("COMPANY_NAME", "Company")
    
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
            tasks_multiline = '\n'.join(tasks_lines) if tasks_lines else ''
            
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

@app.route('/export')
def export_pdf():
    selected_month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    try:
        pdf_bytes, filename = generate_timesheet_pdf_data(selected_month)
        
        local_dir = os.getenv("LOCAL_EXPORT_DIR")
        saved_path = None
        if local_dir:
            try:
                os.makedirs(local_dir, exist_ok=True)
                local_path = os.path.join(local_dir, filename)
                with open(local_path, "wb") as f:
                    f.write(pdf_bytes)
                saved_path = local_path
            except Exception as e:
                print(f"Error saving PDF locally: {e}")
                
        response = make_response(send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=filename))
        if saved_path:
            response.headers['X-Local-Saved-Path'] = saved_path
            response.headers['Access-Control-Expose-Headers'] = 'X-Local-Saved-Path, Content-Disposition'
        return response
    except Exception as e:
        return make_response(f"Error generating PDF: {str(e)}", 500)

@app.route('/merge-pdfs', methods=['POST'])
def merge_pdfs():
    from pypdf import PdfMerger
    
    prepend_timesheet = request.form.get('prepend_timesheet') == 'true'
    selected_month = request.form.get('selected_month', datetime.now().strftime('%Y-%m'))
    
    uploaded_files = request.files.getlist('pdf_files')
    
    merger = PdfMerger()
    
    try:
        # 1. Prepend current month timesheet if requested
        if prepend_timesheet:
            pdf_bytes, filename = generate_timesheet_pdf_data(selected_month)
            merger.append(io.BytesIO(pdf_bytes))
            
        # 2. Append the rest of the uploaded files
        has_files = False
        for file in uploaded_files:
            if file and file.filename.endswith('.pdf'):
                merger.append(io.BytesIO(file.read()))
                has_files = True
                
        if not prepend_timesheet and not has_files:
            return jsonify({"error": "No PDFs uploaded or selected to merge."}), 400
            
        output = io.BytesIO()
        merger.write(output)
        merger.close()
        output.seek(0)
        
        company_name = os.getenv("COMPANY_NAME", "Company")
        download_name = f"Merged_Timesheet_{company_name}_{selected_month}.pdf" if prepend_timesheet else "Merged_Documents.pdf"
        
        pdf_bytes = output.getvalue()
        
        local_dir = os.getenv("LOCAL_EXPORT_DIR")
        saved_path = None
        if local_dir:
            try:
                os.makedirs(local_dir, exist_ok=True)
                local_path = os.path.join(local_dir, download_name)
                with open(local_path, "wb") as f:
                    f.write(pdf_bytes)
                saved_path = local_path
            except Exception as e:
                print(f"Error saving merged PDF locally: {e}")
                
        response = make_response(send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=download_name))
        if saved_path:
            response.headers['X-Local-Saved-Path'] = saved_path
            response.headers['Access-Control-Expose-Headers'] = 'X-Local-Saved-Path, Content-Disposition'
        return response
    except Exception as e:
        return jsonify({"error": f"Failed to merge PDFs: {str(e)}"}), 500


@app.route('/merge-and-email', methods=['POST'])
def merge_and_email():
    from pypdf import PdfMerger
    
    prepend_timesheet = request.form.get('prepend_timesheet') == 'true'
    selected_month = request.form.get('selected_month', datetime.now().strftime('%Y-%m'))
    recipient_emails = request.form.get('recipient_emails', '')
    
    if not recipient_emails:
        return jsonify({"error": "Adresele de email destinatare sunt obligatorii."}), 400
        
    uploaded_files = request.files.getlist('pdf_files')
    
    merger = PdfMerger()
    
    try:
        # 1. Prepend current month timesheet if requested
        if prepend_timesheet:
            pdf_bytes, filename = generate_timesheet_pdf_data(selected_month)
            merger.append(io.BytesIO(pdf_bytes))
            
        # 2. Append the rest of the uploaded files
        has_files = False
        for file in uploaded_files:
            if file and file.filename.endswith('.pdf'):
                merger.append(io.BytesIO(file.read()))
                has_files = True
                
        if not prepend_timesheet and not has_files:
            return jsonify({"error": "Nu ai încărcat sau selectat niciun PDF pentru îmbinare."}), 400
            
        output = io.BytesIO()
        merger.write(output)
        merger.close()
        output.seek(0)
        
        company_name = os.getenv("COMPANY_NAME", "Company")
        download_name = f"Merged_Timesheet_{company_name}_{selected_month}.pdf" if prepend_timesheet else "Merged_Documents.pdf"
        
        pdf_bytes = output.getvalue()
        
        # Save to local folder (required by Outlook as a physical file attachment)
        local_dir = os.getenv("LOCAL_EXPORT_DIR")
        if local_dir:
            try:
                os.makedirs(local_dir, exist_ok=True)
            except Exception as e:
                print(f"Error creating LOCAL_EXPORT_DIR: {e}")
            local_path = os.path.join(local_dir, download_name)
            saved_locally = True
        else:
            # Fallback to current project root directory
            local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), download_name)
            saved_locally = False
            
        try:
            with open(local_path, "wb") as f:
                f.write(pdf_bytes)
        except Exception as e:
            return jsonify({"error": f"Nu s-a putut salva PDF-ul local pentru a fi atașat: {str(e)}"}), 500
                
        # Convert selected_month (e.g. 2026-06) to human-readable month_label (e.g. June 2026)
        try:
            sel_year, sel_mon = int(selected_month[:4]), int(selected_month[5:7])
        except (ValueError, IndexError):
            sel_year, sel_mon = datetime.now().year, datetime.now().month
        month_label = date(sel_year, sel_mon, 1).strftime('%B %Y')

        # Send Email via Outlook AppleScript
        subject = f"Timesheet & Invoice - {company_name} - {month_label}"
        body = f"Hello,\n\nPlease find attached the timesheet and invoice for the month of {month_label}.\n\nBest regards,\n{os.getenv('CONSULTANT_NAME', 'Consultant')}"
        
        send_via_local_outlook(
            recipient_emails=recipient_emails,
            subject=subject,
            body=body,
            file_path=local_path
        )
        
        success_msg = f"Email trimis cu succes prin Outlook local către: <strong>{recipient_emails}</strong>."
        if saved_locally:
            success_msg += f"<br>O copie a fost salvată și în folderul OneDrive: <strong>{local_path}</strong>"
        else:
            success_msg += f"<br>O copie temporară a fost salvată în: <strong>{local_path}</strong>"
            
        return jsonify({"message": success_msg})
    except Exception as e:
        return jsonify({"error": f"Eroare la trimiterea email-ului prin Outlook: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)



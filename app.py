import os
import io
import calendar
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, redirect, flash, make_response, send_file
from dotenv import load_dotenv
from holidays_ro import get_holidays_for_month

import sys
# Add current directory to path to absolute import azure_service
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from azure_service import AzureDevOpsService
except ImportError:
    pass # Will be handled if missing in the final directory

load_dotenv()

# Import split service modules
from db import get_db_connection
from pdf_service import generate_timesheet_pdf_data
from outlook_service import send_via_local_outlook

app = Flask(__name__)
app.secret_key = 'super_secret_dev_key' # for flash messages



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



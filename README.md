# Timesheet App

A local web application to automate timesheet logging with **Azure DevOps** integration, **PDF export**, **OneDrive local synchronization**, **PDF merging**, and **macOS Outlook desktop email integration**.

Built with Flask + SQLite for personal use.

## Features

- **Azure DevOps Integration** — Auto-fetch your active tasks from specific Kanban columns (Engineering PR).
- **Smart Append** — Fetching tasks appends them to existing entries, avoiding duplicates.
- **Daily Logging** — Log hours, tasks, and auto-calculate payment based on a configurable hourly rate.
- **Edit Logs** — Click "Edit" on any entry to modify it.
- **PDF Export** — Generate a clean PDF timesheet for the selected month, named `Timesheet {Company} {Month Year}.pdf`.
- **Local OneDrive Sync** — Automatically saves copies of generated/merged PDFs to a configured local OneDrive path (which syncs to the cloud in the background).
- **Glue PDFs Together** — Merges multiple PDFs (such as invoices, receipts, or attachments) with or without your monthly timesheet into a single PDF.
- **macOS Outlook Email Integration** — Sends the merged/exported documents automatically via your local **Microsoft Outlook** desktop client on macOS (supports multiple recipient addresses).
- **Month Navigation** — Browse between months with ◀ / ▶ arrows.
- **Romanian Holidays** — Visual calendar with national holidays (including Orthodox Easter calculation).
- **Working Days Counter** — Automatically calculates working days excluding weekends and holidays.
- **Monthly Summary & Progress** — Dashboard banner with color-coded stats: days (blue), hours (purple), total EUR (green), and earnings progress bar.
- **Modern UI** — Glassmorphism dark theme with responsive layout and global top alerts.

## Setup

### 1. Clone & Install

```bash
git clone https://github.com/prundusdanielioan/timesheet.git
cd timesheet
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
AZURE_ORGANIZATION=YourOrg
AZURE_PROJECT=YourProject
AZURE_PAT_TOKEN=your_personal_access_token
AZURE_EMAIL=your.email@company.com
CONSULTANT_NAME=Your Name
HOURLY_RATE=35
COMPANY_NAME=Your Company SRL
LOCAL_EXPORT_DIR="/Users/yourusername"
DEFAULT_RECIPIENT_EMAILS="client1@example.com, accounting@example.com"
```

| Variable | Description |
|----------|-------------|
| `AZURE_ORGANIZATION` | Your Azure DevOps organization name |
| `AZURE_PROJECT` | The project to fetch tasks from |
| `AZURE_PAT_TOKEN` | Personal Access Token ([create one here](https://dev.azure.com/_usersSettings/tokens)) |
| `AZURE_EMAIL` | Your email in Azure DevOps |
| `CONSULTANT_NAME` | Your name (appears on PDF exports and in email bodies) |
| `HOURLY_RATE` | Rate per hour in EUR |
| `COMPANY_NAME` | Company name (used in PDF export filename and email subject) |
| `LOCAL_EXPORT_DIR` | Optional. Path to save copies of your PDFs (e.g. your local OneDrive directory) |
| `DEFAULT_RECIPIENT_EMAILS` | Optional. Comma-separated list of default emails to pre-populate in the UI |

### 3. Initialize Database

```bash
python init_db.py
```

### 4. Run

```bash
python app.py
```

Open **http://127.0.0.1:5001** in your browser.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Flask (Python) |
| Database | SQLite |
| PDF Export | fpdf2 |
| PDF Merger | pypdf |
| Frontend | HTML / CSS / JS |
| Design | Glassmorphism, Inter font |
| API | Azure DevOps REST API |
| Automation | macOS AppleScript (osascript) for local Outlook |
| Holidays | Custom Orthodox Easter calculator |

## Project Structure

```
timesheet/
├── app.py              # Flask app entry point & routes
├── db.py               # SQLite connection helper
├── pdf_service.py      # Timesheet PDF generation logic (FPDF)
├── outlook_service.py  # macOS Outlook AppleScript sender
├── azure_service.py    # Azure DevOps API integration
├── holidays_ro.py      # Romanian holidays & Easter calc
├── init_db.py          # Database initialization script
├── requirements.txt    # Python dependencies
├── .env                # Config (git-ignored)
├── timesheet.db        # SQLite database (git-ignored)
├── static/
│   └── style.css       # Glassmorphism dark theme
└── templates/
    └── index.html      # Dashboard UI
```

## Notes

- `.env` and `*.db` are excluded from git via `.gitignore`.
- Intended for **local use only** — no authentication implemented.
- Outlook integration runs via AppleScript (`osascript`). The first time you use the email option, macOS will prompt you to authorize Terminal/Python to control Microsoft Outlook.
- PDF export includes all logged days for the selected month with per-task line breaks.

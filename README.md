# Timesheet App

A local web application to automate timesheet logging with **Azure DevOps** integration, **PDF export**, and a **Romanian holidays calendar**.

Built with Flask + SQLite for personal use.

## Features

- **Azure DevOps Integration** — Auto-fetch your active tasks from specific Kanban columns (Engineering PR)
- **Smart Append** — Fetching tasks appends to existing entries, avoiding duplicates
- **Daily Logging** — Log hours, tasks, and auto-calculate payment based on configurable hourly rate
- **Edit Logs** — Click "Edit" on any entry to modify it
- **PDF Export** — Generate a clean PDF timesheet for the selected month, named `Timesheet {Company} {Month Year}.pdf`
- **Month Navigation** — Browse between months with ◀ / ▶ arrows
- **Romanian Holidays** — Visual calendar with national holidays (including Orthodox Easter calculation)
- **Working Days Counter** — Automatically calculates working days excluding weekends and holidays
- **Monthly Summary** — Dashboard banner with color-coded stats: days (blue), hours (purple), total EUR (green)
- **Modern UI** — Glassmorphism dark theme with responsive layout

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

Create a `.env` file:

```env
AZURE_ORGANIZATION=YourOrg
AZURE_PROJECT=YourProject
AZURE_PAT_TOKEN=your_personal_access_token
AZURE_EMAIL=your.email@company.com
CONSULTANT_NAME=Your Name
HOURLY_RATE=35
COMPANY_NAME=Your Company SRL
```

| Variable | Description |
|----------|-------------|
| `AZURE_ORGANIZATION` | Your Azure DevOps organization name |
| `AZURE_PROJECT` | The project to fetch tasks from |
| `AZURE_PAT_TOKEN` | Personal Access Token ([create one here](https://dev.azure.com/_usersSettings/tokens)) |
| `AZURE_EMAIL` | Your email in Azure DevOps |
| `CONSULTANT_NAME` | Your name (appears on PDF exports) |
| `HOURLY_RATE` | Rate per hour in EUR |
| `COMPANY_NAME` | Company name (used in PDF export filename) |

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
| Frontend | HTML / CSS / JS |
| Design | Glassmorphism, Inter font |
| API | Azure DevOps REST API |
| Holidays | Custom Orthodox Easter calculator |

## Project Structure

```
timesheet/
├── app.py              # Flask routes & PDF export
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

- `.env` and `*.db` are excluded from git via `.gitignore`
- Intended for **local use only** — no authentication implemented
- Romanian holidays include movable Orthodox Easter-based dates (Vinerea Mare, Pastele, Rusalii)
- PDF export includes all logged days for the selected month with per-task line breaks

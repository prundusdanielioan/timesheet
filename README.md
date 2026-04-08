# Timesheet App

A local web application to automate timesheet logging with **Azure DevOps** integration, **PDF export**, and a **Romanian holidays calendar**.

Built with Flask + SQLite for personal use.

## Features

- **Azure DevOps Integration** — Auto-fetch your active tasks from specific Kanban columns (Engineering PR)
- **Smart Append** — Fetching tasks appends to existing entries, avoiding duplicates
- **Daily Logging** — Log hours, tasks, and auto-calculate payment based on configurable hourly rate
- **Edit Logs** — Click "Edit" on any entry to modify it
- **PDF Export** — Generate a clean PDF timesheet for the selected month
- **Month Navigation** — Browse between months with ◀ / ▶ arrows
- **Romanian Holidays** — Visual calendar with national holidays (including Orthodox Easter calculation)
- **Working Days Counter** — Automatically calculates working days excluding weekends and holidays
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
```

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
| Frontend | HTML/CSS/JS |
| Design | Glassmorphism, Inter font |
| API | Azure DevOps REST API |

## Screenshots

The dashboard features:
- Left panel: Log form with auto-fetch from Azure DevOps
- Right panel: Monthly log history with edit capability
- Top banner: Monthly summary (days, hours, total EUR)
- Bottom: Calendar with holidays and working days count

## Notes

- The `.env` file and `*.db` database are excluded from git via `.gitignore`
- Intended for **local use only** — no authentication is implemented
- Romanian holidays include movable Orthodox Easter-based dates

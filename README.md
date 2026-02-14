# MindMend — AI-Enabled Health Awareness & Support Platform

A web-based mental health support platform that combines awareness, self-assessment, emotional support, and access to national helplines into a single, stigma-free digital environment.

## Features

- **AI Chatbot** — LLM-powered (Gemini/OpenAI) or rule-based; sentiment analysis, distress detection, personalized recommendations
- **Self-Assessment Modules** — PHQ-9 (depression), GAD-7 (anxiety), PSS-10 (stress)
- **Community Forum** — Moderated, anonymous peer support
- **Counsellor Booking** — Schedule professional mental health consultations
- **Mood Tracking** — Monitor emotional patterns over time
- **Helplines & Resources** — KIRAN (1800-599-0019), Tele-MANAS (14416) — 24/7
- **Analytical Dashboard** — Mood trends, assessment history, engagement metrics

## Tech Stack

- **Backend:** Django 6
- **Database:** SQLite (dev)
- **Frontend:** Bootstrap 5, vanilla JS

## Quick Start

### 1. Create virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate   

```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run migrations

```bash
python manage.py migrate
```

### 4. Create superuser (optional)

```bash
python manage.py createsuperuser
```

### 5. Seed sample counsellors

```bash
python manage.py seed_counsellors
```

### 6. Run development server

```bash
python manage.py runserver
```

Open http://127.0.0.1:8000

### 7. (Optional) Enable LLM-powered chat

For more natural, human-like responses, configure an LLM provider:

1. **Gemini (Google AI):** Get an API key from [Google AI Studio](https://aistudio.google.com/apikey).
2. **OpenAI:** Use your OpenAI API key.

Set environment variables before running the server:

**Windows (PowerShell):**
```powershell
$env:MINDMEND_LLM_PROVIDER = "gemini"
$env:MINDMEND_GEMINI_API_KEY = "your-api-key"
python manage.py runserver
```

**Linux/Mac:**
```bash
export MINDMEND_LLM_PROVIDER=gemini
export MINDMEND_GEMINI_API_KEY=your-api-key
python manage.py runserver
```

Or copy `.env.example` to `.env`, add your keys, and load with `python-dotenv` if you use it.  
If not configured, the chatbot uses rule-based responses with full feature parity.

## Project Structure

```
MindMend/
├── Mind_Mend/          # Main app
│   ├── models.py       # User, Assessment, Mood, Forum, Counsellor
│   ├── views.py        # All views
│   ├── services.py     # AI chatbot logic
│   ├── assessment_data.py  # PHQ-9, GAD-7, PSS questions
│   └── forms.py
├── MindMend/           # Project settings
├── templates/
├── static/
└── manage.py
```

## Admin

- URL: `/admin/`
- Create superuser with `python manage.py createsuperuser`
- Manage counsellors, forum posts, and view data

## Helplines (India)

- **KIRAN:** 1800-599-0019 — 24/7, 13 languages
- **Tele-MANAS:** 14416 or 1-800-891-4416 — 24/7, 20+ languages

---

*MindMend — Empowering users to understand their mental well-being and seek timely help.*

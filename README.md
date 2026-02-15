# MindMend — AI-Enabled Mental Health Support Platform

MindMend is a Django-based web platform for mental health awareness, self-assessment, peer support, counsellor booking, and guided recovery support.

## Core Features

- AI chatbot with rule-based mode and optional Gemini/OpenAI integration
- Assessments: PHQ-9, GAD-7, PSS-10
- Anonymous community forum and recovery stories
- Counsellor booking and live chat
- Doctor/counsellor dashboard with:
- appointment management (accept/reject/complete)
- live notifications for bookings and messages
- Mood tracking and user dashboard analytics
- Location analytics and mental health heatmap
- Contact Us submissions stored in database and visible in admin
- Session review/feedback flow (user -> counsellor)
- Finish Session flow for both user and counsellor

## Tech Stack

- Backend: Django 6, Django Channels (WebSocket support)
- Frontend: Django templates, Tailwind CSS (CDN), vanilla JavaScript
- Database: SQLite (development), PostgreSQL-ready for deployment
- Static serving: WhiteNoise

## Quick Start

1. Create and activate virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Apply migrations

```bash
python manage.py migrate
```

4. Create admin user

```bash
python manage.py createsuperuser
```

5. (Optional) Seed sample counsellors

```bash
python manage.py seed_counsellors
```

6. Run development server

```bash
python manage.py runserver
```

Open: `http://127.0.0.1:8000`

## Optional LLM Setup

Set environment variables to enable LLM chat:

```powershell
$env:MINDMEND_LLM_PROVIDER="gemini"
$env:MINDMEND_GEMINI_API_KEY="your-api-key"
```

Or for OpenAI:

```powershell
$env:MINDMEND_LLM_PROVIDER="openai"
$env:MINDMEND_OPENAI_API_KEY="your-api-key"
```

If no provider is configured, chatbot falls back to rule-based responses.

## Doctor Workflow

Doctors currently do not self-register through public UI.

Admin onboarding steps:

1. Create user in `/admin/auth/user/`
2. Create counsellor in `/admin/Mind_Mend/counsellor/`
3. Link `Counsellor.user` to that user account
4. Doctor logs in at `/doctor/login/`

## Admin Access

- Admin URL: `/admin/`
- Contact messages: `Mind_Mend -> Contact messages`
- Counsellor reviews: `Mind_Mend -> Counsellor reviews`

## Helplines (India)

- KIRAN: `1800-599-0019`
- Tele-MANAS: `14416` / `1-800-891-4416`

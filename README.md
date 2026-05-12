# MindMend — AI-Enabled Mental Health Support Platform

MindMend is a comprehensive, Django-based web platform designed to provide mental health awareness, self-assessment, peer support, and professional counsellor booking. It leverages modern web technologies and Artificial Intelligence to offer a secure, empathetic, and highly interactive user experience.

## ✨ Core Features

### 🧠 AI & Intelligent Support
- **AI Chatbot**: Empathetic, memory-aware chatbot with safety filters for suicide/violence risk detection.
- **Multiple LLM Fallback**: Natively supports multiple Gemini API keys (`MINDMEND_GEMINI_API_KEY="key1,key2"`) to seamlessly failover if quota exhausts. OpenAI fallback is also supported.
- **Rule-based Fallback**: If no AI keys are configured, falls back to a deterministic rule-based chatbot.

### 🛡️ Security & Privacy
- **Email OTP Registration**: Secure account creation with a 15-minute expiring Email OTP.
- **Field-level Encryption**: Real-time Chat messages and AI Chatbot history are encrypted at rest using AES-128-CBC + HMAC-SHA256 (Fernet).
- **Location Tracking (Opt-out)**: Track mental health trends via a geographic heatmap, with strict user opt-out controls.
- **Data Deletion**: Users can permanently delete their account and all associated data at any time.

### 🩺 Professional Counselling
- **Counsellor Booking System**: Browse doctors, view real-time availability, and book 30-minute appointment intervals.
- **Razorpay Integration**: End-to-end secure payment gateway with Server-to-Server Webhook verification (`order.paid`) for reliable transaction capture.
- **Doctor Dashboard**: Dedicated interface for counsellors to accept/reject/complete appointments, view patient history, manage 15-minute auto-release slot holds, and track monthly revenue.
- **Live Real-time Chat**: Secure WebSocket-based chat rooms for patients and doctors. Features include:
  - Persistent chat history across multiple appointments with the same doctor.
  - Automatic session completion (chats close 24 hours after the appointment slot).
  - Live pop-up notifications for doctors when a patient messages them.

### 📊 Assessments & Community
- **Clinical Assessments**: Self-administered PHQ-9 (Depression), GAD-7 (Anxiety), and PSS-10 (Stress) tools.
- **Community Forum**: Anonymous peer-support network where users can share struggles, discuss coping mechanisms, and post recovery stories.
- **Mood Tracking**: Daily mood and energy logging.
- **Live Survey Analytics**: Integrate Google Forms via a private Google Service Account for live, auto-refreshing pie/bar chart analytics of mental health surveys.

---

## 🛠️ Tech Stack

- **Backend**: Django 6, Django Channels (WebSockets / ASGI)
- **Frontend**: Django Templates, Tailwind CSS (CDN), Vanilla JavaScript, CSS Glassmorphism & Animations
- **Database**: SQLite (Local Development), PostgreSQL-ready for deployment
- **Static & Media**: WhiteNoise (Static), Local FileSystemStorage (Media)
- **Deployment Ready**: Fully configured for Render with `gunicorn`, `daphne`, and `render_start.sh`.

---

## 🚀 Quick Start (Local Development)

1. **Create and activate virtual environment**
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up Environment Variables (`.env`)**
Create a `.env` file in the same directory as `manage.py` and configure the following:
```env
# Essential
SECRET_KEY="your-django-secret-key"
DEBUG=True

# Email OTP Setup
MINDMEND_EMAIL_HOST_USER="your-email@gmail.com"
MINDMEND_EMAIL_HOST_PASSWORD="your-app-password"

# Gemini AI (Comma-separated for fallback pool)
MINDMEND_GEMINI_API_KEY="AIzaSy...Key1...,AIzaSy...Key2..."

# Razorpay Payment Gateway (Test Mode)
RAZORPAY_KEY_ID="rzp_test_yourkey"
RAZORPAY_KEY_SECRET="your_razorpay_secret"
RAZORPAY_WEBHOOK_SECRET="your_webhook_secret"

# Encryption (Required for Chat History)
# Generate via: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
MINDMEND_ENCRYPTION_KEY="your-fernet-key="
```

4. **Apply migrations**
```bash
python manage.py migrate
```

5. **Create an Admin user**
```bash
python manage.py createsuperuser
```

6. **(Optional) Seed sample counsellors**
```bash
python manage.py seed_counsellors
```

7. **Run the ASGI server (Required for WebSockets)**
```bash
daphne -b 127.0.0.1 -p 8000 MindMend.asgi:application
# OR use Django dev server (less stable for WebSockets):
# python manage.py runserver
```

Open your browser and navigate to: `http://127.0.0.1:8000`

---

## 👨‍⚕️ Doctor / Counsellor Workflow

Doctors do not currently self-register through the public UI.

**Admin Onboarding Steps:**
1. Go to `/admin/auth/user/` and create a User account.
2. Go to `/admin/Mind_Mend/counsellor/` and create a Counsellor profile.
3. Link the `Counsellor.user` field to the User account created in Step 1.
4. The Doctor can now log in at `/doctor/login/` or via the standard login page to access the Doctor Dashboard.

---

## 📞 Helplines (India)
MindMend enforces safety checks. If high-risk distress or violence is detected, it immediately recommends:
- **KIRAN**: `1800-599-0019`
- **Tele-MANAS**: `14416` / `1-800-891-4416`

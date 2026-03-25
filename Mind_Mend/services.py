"""
AI Chatbot service with sentiment analysis, distress detection, and optional LLM (Gemini/OpenAI).
"""
import random
import re
import uuid
from datetime import datetime, timedelta

from django.conf import settings


HIGH_RISK_DISTRESS = {
    'suicide', 'suicidal', 'kill myself', 'end my life',
    'self harm', 'self-harm', 'hurt myself',
    'better off dead', 'aatmahatya', 'khudkushi', 'mar jana'
}

INVALID_NAME_WORDS = {
    'sad', 'tired', 'fine', 'okay', 'ok', 'good', 'happy',
    'upset', 'angry', 'anxious', 'stressed', 'low', 'down'
}


def _safe_default_response(lang='en'):
    if lang == 'hi':
        return {
            'response': "मुझे खेद है, अभी मैं सही तरीके से जवाब नहीं दे पा रहा हूं। लेकिन मैं आपके साथ हूं। आप चाहें तो अपनी बात एक बार फिर लिख सकते हैं, या अभी के लिए 4 धीमी सांसें लें और किसी भरोसेमंद व्यक्ति से बात करें।",
            'sentiment': 'neutral',
            'is_distress': False,
            'recommendations': []
        }
    return {
        'response': "I'm sorry — I couldn't respond properly just now, but I'm here with you. You can send your message again, or for now take 4 slow breaths and reach out to someone you trust.",
        'sentiment': 'neutral',
        'is_distress': False,
        'recommendations': []
    }


def _clean_llm_text(text):
    text = (text or '').strip()
    if not text:
        return None
    if len(text) < 2:
        return None
    return text


def _format_context_for_prompt(context, lang):
    if not context:
        return ""
    situation = context.get('situation')
    emotion = context.get('emotion')
    context_label = context.get('context_label')
    memory = context.get('memory') or {}
    memory_topics = memory.get('topics') or []
    memory_activities = memory.get('activities') or []
    preferred_name = memory.get('preferred_name') or ''
    if not (situation or emotion or context_label or memory_topics or memory_activities or preferred_name):
        return ""
    parts = []
    if emotion:
        parts.append(f"emotion={emotion}")
    if context_label:
        parts.append(f"context={context_label}")
    if situation:
        parts.append(f"situation={situation}")
    if memory_topics:
        parts.append(f"memory_topics={','.join(memory_topics[:5])}")
    if memory_activities:
        parts.append(f"memory_helpful={','.join(memory_activities[:5])}")
    if preferred_name:
        parts.append(f"user_name={preferred_name}")
    if lang == 'hi':
        return (
            "Context (user-mentioned or inferred): "
            f"{', '.join(parts)}. "
            "Reference this only if helpful and keep it practical.\n"
        )
    return (
        "Context (user-mentioned or inferred): "
        f"{', '.join(parts)}. "
        "Reference this only if helpful and keep it practical.\n"
    )


def _call_llm(user_message, conversation_history, lang, context=None):
    """
    Call Gemini or OpenAI for human-like response. Returns response text or None on failure.
    """
    provider = (getattr(settings, 'MINDMEND_LLM_PROVIDER', '') or '').strip().lower()
    gemini_key = getattr(settings, 'MINDMEND_GEMINI_API_KEY', '') or ''
    openai_key = getattr(settings, 'MINDMEND_OPENAI_API_KEY', '') or ''

    if not provider:
        if gemini_key:
            provider = 'gemini'
        elif openai_key:
            provider = 'openai'
        else:
            return None

    is_hindi = lang == 'hi'
    lang_instruction = "Respond in Hindi (हिन्दी)." if is_hindi else "Respond in English."

    context_block = _format_context_for_prompt(context or {}, lang)
    system_prompt = f"""You are MindMend, a supportive mental wellness assistant. Respond like a real therapist: calm, empathetic, and practical.

Therapist Response Pattern (use this order):
1. Empathy
2. Validation
3. Suggestion
4. Gentle question

Example structure:
- Empathy: "That sounds really difficult."
- Validation: "It's understandable to feel that way."
- Suggestion: "You could try..."
- Follow-up: "Would you like to talk more about it?"

Guidelines:
1. Always respond with empathy and understanding.
2. Validate the user’s feelings before giving suggestions.
3. Provide simple and practical coping techniques when appropriate.
4. Ask gentle follow-up questions to understand the user's situation.
5. If the user asks for suggestions, give 3–5 helpful techniques.
6. Avoid sounding robotic or overly clinical.
7. Never diagnose medical conditions.
8. If the user shows severe distress or self-harm thoughts, encourage seeking professional help or contacting trusted people.

Tone:
Warm, supportive, calm, non-judgmental.

{context_block}
{lang_instruction}"""

    messages = [{"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]} for m in conversation_history]
    messages.append({"role": "user", "content": user_message})

    try:
        if provider == 'gemini':
            api_key = gemini_key
            if not api_key:
                return None

            import google.generativeai as genai
            from google.api_core import exceptions as google_exceptions
            import time

            genai.configure(api_key=api_key)

            model_names = [
                'gemini-flash-lite-latest',
                'gemini-2.0-flash-lite',
                'gemini-2.0-flash',
                'gemini-flash-latest',
                'gemma-3n-e2b-it'
            ]

            for model_name in model_names:
                try:
                    model = genai.GenerativeModel(model_name)
                    history_parts = []
                    for m in messages[:-1]:
                        role = "user" if m["role"] == "user" else "model"
                        history_parts.append({"role": role, "parts": [m["content"]]})

                    chat = model.start_chat(history=history_parts)
                    resp = chat.send_message(system_prompt + "\nUser message: " + user_message)
                    cleaned = _clean_llm_text(getattr(resp, "text", None))
                    if cleaned:
                        return cleaned

                except google_exceptions.NotFound:
                    continue

                except google_exceptions.ResourceExhausted as e:
                    retry_secs = 5
                    try:
                        match = re.search(r'retry in ([\d.]+)s', str(e).lower())
                        if match:
                            retry_secs = min(float(match.group(1)) + 1, 10)
                    except Exception:
                        pass

                    time.sleep(retry_secs)

                    try:
                        model = genai.GenerativeModel(model_name)
                        history_parts = []
                        for m in messages[:-1]:
                            role = "user" if m["role"] == "user" else "model"
                            history_parts.append({"role": role, "parts": [m["content"]]})

                        chat = model.start_chat(history=history_parts)
                        resp = chat.send_message(system_prompt + "\nUser message: " + user_message)
                        cleaned = _clean_llm_text(getattr(resp, "text", None))
                        if cleaned:
                            return cleaned
                    except Exception:
                        pass
                    continue

                except Exception:
                    continue

            return None

        elif provider == 'openai':
            api_key = openai_key
            if not api_key:
                return None

            from openai import OpenAI
            client = OpenAI(api_key=api_key)

            formatted = [{"role": "system", "content": system_prompt}]
            for m in messages:
                formatted.append({"role": m["role"], "content": m["content"]})

            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=formatted,
                max_tokens=300
            )

            content = resp.choices[0].message.content if resp.choices else None
            return _clean_llm_text(content)

    except Exception:
        return None

    return None


VIOLENCE_KEYWORDS = {
    'kill', 'killed', 'murder', 'stab', 'stabbing', 'shot', 'shoot', 'shooting',
    'beat', 'beating', 'hit', 'iron rod', 'weapon', 'blood', 'dead body',
    'body', 'accidentally killed', 'i killed', 'i hit him', 'hurt him badly'
}


def detect_violence_risk(text):
    """Detect statements about serious harm to others."""
    t = (text or '').lower()
    hits = [kw for kw in VIOLENCE_KEYWORDS if kw in t]
    return len(hits) > 0, hits


DISTRESS_KEYWORDS_EN = {
    'suicide', 'suicidal', 'kill myself', 'end my life', 'want to die',
    'self harm', 'self-harm', 'hurt myself', 'cutting', 'hopeless',
    'no reason to live', 'better off dead', 'give up', 'cant go on',
    'anxiety', 'panic', 'overwhelmed', 'cant cope', 'depressed',
    'lonely', 'isolated', 'abandoned', 'worthless', 'failure',
    'scared', 'afraid', 'terrified', 'crisis', 'emergency'
}

DISTRESS_KEYWORDS_HI = {
    'aatmahatya', 'khudkushi', 'mar jana', 'naasht', 'udaas',
    'nirash', 'bechain', 'ghabraya', 'chinta', 'takleef',
    'tang', 'thakaan', 'akela', 'bekar', 'asafal',
    'dar', 'darr', 'pareshan', 'dukhi', 'dil tuta'
}

POSITIVE_WORDS = {
    'happy', 'good', 'great', 'wonderful', 'amazing', 'better', 'improving',
    'hopeful', 'calm', 'peaceful', 'relieved', 'grateful', 'joy', 'love',
    'excited', 'optimistic', 'confident', 'strong', 'proud', 'content',
    'fine', 'ok', 'okay', 'alright', 'well', 'decent',
    'achha', 'accha', 'sukhi', 'khush', 'badhiya', 'theek', 'acchha'
}

NEGATIVE_WORDS = {
    'sad', 'bad', 'terrible', 'awful', 'horrible', 'worst', 'angry',
    'frustrated', 'anxious', 'nervous', 'scared', 'worried', 'stressed',
    'tired', 'exhausted', 'lonely', 'confused', 'lost', 'helpless', 'low', 'down',
    'hopeless', 'overwhelmed', 'depressed', 'miserable', 'upset',
    'udaas', 'dukhi', 'bura', 'bekar', 'gussa', 'thaka', 'pareshan'
}


def get_session_id():
    """Generate a unique session ID for anonymous chat."""
    return str(uuid.uuid4())[:12]


def analyze_sentiment(text):
    """Simple rule-based sentiment analysis. Returns: positive, negative, neutral."""
    text_lower = (text or '').lower()
    words = set(re.findall(r'\b\w+\b', text_lower))

    pos_count = len(words & POSITIVE_WORDS)
    neg_count = len(words & NEGATIVE_WORDS)

    if pos_count > neg_count:
        return 'positive'
    elif neg_count > pos_count:
        return 'negative'
    return 'neutral'


def detect_distress(text):
    """Check for distress keywords in English and Hindi. Returns (has_distress, matched_keywords)."""
    text_lower = (text or '').lower()
    matched = [kw for kw in DISTRESS_KEYWORDS_EN | DISTRESS_KEYWORDS_HI if kw in text_lower]
    return len(matched) > 0, matched


def detect_emotion(message):
    """
    Detect primary emotion. Uses Gemini when configured; falls back to heuristics.
    """
    text = (message or '').lower()
    gemini_key = getattr(settings, 'MINDMEND_GEMINI_API_KEY', '') or ''
    provider = (getattr(settings, 'MINDMEND_LLM_PROVIDER', '') or '').strip().lower()

    if provider == 'gemini' and gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            prompt = f"""
Detect the user's primary emotion.
Return ONLY one word.

Options:
happy
sad
anxious
angry
overwhelmed
neutral

Message:
{message}
"""
            model = genai.GenerativeModel("gemini-2.0-flash")
            resp = model.generate_content(prompt)
            out = (getattr(resp, 'text', '') or '').strip().lower()
            if out in {'happy', 'sad', 'anxious', 'angry', 'overwhelmed', 'neutral'}:
                return out
        except Exception:
            pass

    if any(k in text for k in ['angry', 'mad', 'furious', 'irritated', 'gussa']):
        return 'angry'
    if any(k in text for k in ['anxiety', 'panic', 'bechain', 'ghabraya', 'chinta']):
        return 'anxious'
    if any(k in text for k in ['overwhelmed', 'cant cope', 'too much', 'pressure']):
        return 'overwhelmed'

    sentiment = analyze_sentiment(text)
    if sentiment == 'positive':
        return 'happy'
    if sentiment == 'negative':
        return 'sad'
    return 'neutral'


def detect_context_label(message):
    contexts = {
        "class": ["class", "lecture", "teacher", "exam", "tuition", "coaching", "library"],
        "office": ["office", "meeting", "boss", "work", "deadline"],
        "home": ["home", "room", "house", "hostel", "dorm"],
        "public": ["bus", "train", "crowd", "metro", "park", "playground", "canteen", "gym"]
    }
    text = (message or '').lower()
    for context, words in contexts.items():
        for w in words:
            if w in text:
                return context
    return "unknown"


def extract_topics(message):
    text = (message or '').lower()
    topic_map = {
        'exams': ['exam', 'exams', 'test', 'tests', 'study', 'studying', 'tuition', 'coaching', 'class'],
        'work': ['work', 'office', 'boss', 'deadline', 'meeting', 'job'],
        'family': ['family', 'parents', 'mother', 'father', 'mom', 'dad', 'sibling'],
        'relationships': ['relationship', 'partner', 'boyfriend', 'girlfriend', 'breakup', 'love'],
        'friends': ['friend', 'friends', 'social', 'lonely', 'alone'],
        'health': ['health', 'sick', 'ill', 'pain', 'headache'],
        'money': ['money', 'finance', 'financial', 'bills', 'rent'],
        'sleep': ['sleep', 'insomnia', 'night', 'tired', 'exhausted'],
    }
    hits = []
    for topic, words in topic_map.items():
        if any(w in text for w in words):
            hits.append(topic)
    return hits


def extract_activities(message, recommendations=None):
    text = (message or '').lower()
    activities = []
    if any(w in text for w in ['music', 'song', 'songs']):
        activities.append('music')
    if any(w in text for w in ['walk', 'walking', 'stroll']):
        activities.append('walk')
    if any(w in text for w in ['breath', 'breathing']):
        activities.append('breathing')
    if any(w in text for w in ['journal', 'write down', 'writing']):
        activities.append('journaling')
    if any(w in text for w in ['meditation', 'meditate']):
        activities.append('meditation')
    if any(w in text for w in ['exercise', 'workout', 'gym']):
        activities.append('exercise')
    if any(w in text for w in ['talk', 'call', 'message', 'chat']):
        activities.append('reach out')

    if recommendations:
        rec_map = {
            'breathing': 'breathing',
            'activity': 'movement',
            'distract_music': 'music',
            'distract_walk': 'walk',
            'distract_call': 'reach out',
            'distract_watch': 'watch',
            'journal': 'journaling',
        }
        for r in recommendations:
            act = rec_map.get(r.get('type'))
            if act:
                activities.append(act)

    seen = set()
    out = []
    for a in activities:
        if a not in seen:
            out.append(a)
            seen.add(a)
    return out


def extract_name(message):
    text = (message or '').strip()
    patterns = [
        r"\bmy name is ([A-Za-z]+)\b",
        r"\bi am ([A-Za-z]+)\b",
        r"\bi'm ([A-Za-z]+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if name.lower() not in INVALID_NAME_WORDS and len(name) >= 2:
                return name
    return ""


def _infer_situation(msg):
    text = (msg or '').lower()
    if any(w in text for w in ['office', 'work', 'boss', 'deadline', 'meeting', 'shift']):
        return 'work'
    if any(w in text for w in ['school', 'college', 'class', 'exam', 'study', 'library', 'tuition', 'tution', 'coaching']):
        return 'study'
    if any(w in text for w in ['bus', 'train', 'metro', 'traffic', 'commute', 'commuting', 'ride']):
        return 'commuting'
    if any(w in text for w in ['crowd', 'crowded', 'public', 'outside', 'street', 'market', 'mall', 'gym', 'canteen', 'park', 'playground']):
        return 'public'
    if any(w in text for w in ['bed', 'sleeping', 'insomnia', 'night']):
        return 'bed'
    if any(w in text for w in ['home', 'house', 'room', 'kitchen', 'sofa', 'hostel', 'dorm']):
        return 'home'
    if any(w in text for w in ['alone', 'lonely', 'by myself']):
        return 'alone'
    if any(w in text for w in ['with family', 'parents', 'mom', 'dad', 'sibling']):
        return 'family'
    return None


def _context_tip(situation, lang, explicit_place=None):
    if lang == 'hi':
        if situation in ('commuting', 'public'):
            if explicit_place == 'bus':
                return "बस में हैं तो हल्का सा रीसेट करें: कंधे ढीले करें, जबड़ा ढीला छोड़ें, और 4 धीमी सांसें लें।"
            if explicit_place == 'library':
                return "लाइब्रेरी में हैं तो धीरे-धीरे सांस लें और ध्यान एक पेज/लाइन पर टिकाएं—छोटे हिस्से से शुरू करें।"
            if explicit_place == 'gym':
                return "जिम में हैं तो थोड़ा धीमा करें: पानी पिएं, कंधे ढीले करें, और 4 शांत सांसें लें।"
            if explicit_place == 'hostel':
                return "होस्टल में हैं तो पानी पीकर 1–2 मिनट शांत बैठें—फिर छोटा सा काम चुनें।"
            return "हल्का सा रीसेट करें: कंधे ढीले करें, 4 धीमी सांसें लें, और सामने किसी एक चीज़ पर ध्यान टिकाएं।"
        if situation == 'work':
            return "बहुत छोटे ब्रेक लें: 5 धीमी सांसें और कंधों को ढीला करना भी मदद करता है।"
        if situation == 'study':
            return "2 मिनट आंखें बंद करके सांस पर ध्यान दें—फिर छोटे टास्क से शुरू करें।"
        if situation == 'bed':
            return "धीरे-धीरे सांस लें और शरीर को ढीला छोड़ें—छोटी बॉडी-स्कैन मदद कर सकती है।"
        if situation == 'home':
            return "पानी पीकर खिड़की/बालकनी के पास 1-2 मिनट खड़े रहें।"
        return "अभी एक छोटा कदम लें—धीमी सांसें या थोड़ा स्ट्रेचिंग भी मदद कर सकती है।"

    if situation in ('commuting', 'public'):
        if explicit_place == 'bus':
            return "Keep it subtle on the bus: drop your shoulders, unclench your jaw, and take 4 slow breaths."
        if explicit_place == 'library':
            return "Since you're in the library, keep it quiet: slow breaths, and focus on one line at a time."
        if explicit_place == 'gym':
            return "At the gym, slow it down: sip water, relax your shoulders, and take 4 calm breaths."
        if explicit_place == 'hostel':
            return "In the hostel, take a 1–2 minute pause: drink water and pick one tiny next step."
        if explicit_place == 'park':
            return "In the park, slow your pace and take 4 steady breaths while you notice the air and sounds."
        if explicit_place == 'playground':
            return "At the playground, take a small pause: loosen your shoulders and take 4 calm breaths."
        return "Keep it subtle: drop your shoulders, take 4 slow breaths, and focus on one steady point."

    if situation == 'work':
        return "Keep it low-key: 5 slow breaths and a shoulder drop can help reset."
    if situation == 'study':
        if explicit_place == 'tuition' or explicit_place == 'coaching':
            return "In class, keep it quiet: slow breaths and focus on one small task or a single line."
        return "Close your eyes for 60 seconds and just breathe, then start with a tiny task."
    if situation == 'bed':
        return "Keep it gentle: slow breathing and a quick body scan can calm things down."
    if situation == 'home':
        return "A small reset helps: drink water and stand by a window for a minute."
    return "Try one small, doable step right now—slow breathing or a short stretch can help."


def _explicit_place_label(msg, lang):
    text = (msg or '').lower()
    if 'bus' in text:
        return 'bus', ('बस में' if lang == 'hi' else 'on the bus')
    if 'train' in text or 'metro' in text:
        return 'train', ('ट्रेन/मेट्रो में' if lang == 'hi' else 'on the train/metro')
    if 'library' in text:
        return 'library', ('लाइब्रेरी में' if lang == 'hi' else 'in the library')
    if 'hostel' in text or 'dorm' in text:
        return 'hostel', ('होस्टल में' if lang == 'hi' else 'in the hostel')
    if 'gym' in text:
        return 'gym', ('जिम में' if lang == 'hi' else 'at the gym')
    if 'canteen' in text:
        return 'canteen', ('कैंटीन में' if lang == 'hi' else 'in the canteen')
    if 'park' in text:
        return 'park', ('पार्क में' if lang == 'hi' else 'in the park')
    if 'playground' in text:
        return 'playground', ('प्लेग्राउंड में' if lang == 'hi' else 'at the playground')
    if 'tuition' in text or 'tution' in text:
        return 'tuition', ('ट्यूशन में' if lang == 'hi' else 'in tuition class')
    if 'coaching' in text:
        return 'coaching', ('कोचिंग में' if lang == 'hi' else 'in coaching class')
    if 'class' in text or 'lecture' in text:
        return 'class', ('क्लास में' if lang == 'hi' else 'in class')
    if 'office' in text or 'work' in text:
        return 'office', ('ऑफिस में' if lang == 'hi' else 'at work')
    if 'home' in text or 'room' in text or 'house' in text:
        return 'home', ('घर पर' if lang == 'hi' else 'at home')
    return '', ''


def _context_support_line(context, lang, explicit_place='', explicit_label=''):
    if not context:
        return ''
    situation = context.get('situation')
    parts = []
    if situation:
        if lang == 'hi':
            situation_map = {
                'work': 'काम पर',
                'study': 'पढ़ाई के दौरान',
                'commuting': 'यात्रा/आवागमन में',
                'public': 'भीड़/बाहर',
                'bed': 'बिस्तर पर',
                'home': 'घर पर',
                'alone': 'अकेले',
                'family': 'परिवार के साथ',
            }
            if explicit_label:
                parts.append(f"अगर आप {explicit_label} हैं")
            else:
                parts.append(f"अगर आप {situation_map.get(situation, situation)} हैं")
        else:
            situation_map = {
                'work': 'at work',
                'study': 'studying',
                'commuting': 'commuting',
                'public': 'somewhere public',
                'bed': 'in bed',
                'home': 'at home',
                'alone': 'alone',
                'family': 'with family',
            }
            if explicit_label:
                parts.append(f"since you're {explicit_label}")
            else:
                parts.append(f"if you're {situation_map.get(situation, situation)}")

    if not parts:
        return ''

    tip = _context_tip(situation, lang, explicit_place=explicit_place or None)
    if lang == 'hi':
        return (parts[0].strip() + ", " + tip) if tip else ""
    return (parts[0].strip().capitalize() + ", " + tip) if tip else ""


def _build_context(user_message, context, lang):
    situation = _infer_situation(user_message)
    return {
        'situation': situation,
    }


def get_recommendations(sentiment, distress_keywords, user_message, lang='en', context=None):
    """Generate personalized self-help recommendations based on analysis. lang: 'en' or 'hi'."""
    is_hi = lang == 'hi'
    recommendations = []

    if is_hi:
        crisis_title = 'तुरंत सहायता उपलब्ध'
        crisis_content = 'कृपया तुरंत मदद लें। आप महत्वपूर्ण हैं। KIRAN: 1800-599-0019 या Tele-MANAS: 14416 पर कॉल करें (24/7, निःशुल्क)। ये हेल्पलाइन कई भाषाओं में उपलब्ध हैं।'
        helpline_title = 'पेशेवर सहायता'
        helpline_content = 'मानसिक स्वास्थ्य पेशेवर से बात करें। KIRAN (1800-599-0019) और Tele-MANAS (14416) 24/7 निःशुल्क सहायता प्रदान करते हैं।'
        breath_title = 'ग्राउंडिंग व्यायाम'
        breath_content = '4-7-8 सांस लें: 4 सेकंड सांस अंदर, 7 सेकंड रोकें, 8 सेकंड बाहर छोड़ें। 3-4 बार दोहराएं।'
        activity_title = 'हल्की गतिविधि'
        activity_content = 'थोड़ी पैदल चलना या स्ट्रेचिंग आपके तंत्रिका तंत्र को संतुलित करने में मदद कर सकती है।'
        journal_title = 'जर्नलिंग'
        journal_content = 'अपने विचार लिखने से भावनाओं को संसाधित करने में मदद मिलती है। हमारे मूड ट्रैकर का उपयोग करें।'
        distract_music_title = 'संगीत सुनें'
        distract_music_content = 'अपने पसंदीदा गाने लगाएं। संगीत आपके मूड को बेहतर कर सकता है और नकारात्मक विचारों से ध्यान हटा सकता है।'
        distract_walk_title = 'पैदल चलें'
        distract_walk_content = 'बाहर थोड़ी सैर करें। ताज़ी हवा और चलना भारी विचारों से ध्यान हटाने में मदद कर सकता है।'
        distract_call_title = 'किसी से बात करें'
        distract_call_content = 'किसी दोस्त या परिवार को कॉल या मैसेज करें। विश्वसनीय व्यक्ति से बात करने से मन हल्का हो सकता है।'
        distract_watch_title = 'कुछ देखें'
        distract_watch_content = 'पसंदीदा शो, फिल्म या मज़ेदार वीडियो देखें। हल्का व्यस्त रहने से मन को आराम मिल सकता है।'
        checkin_title = 'सेल्फ-केयर चेक'
        checkin_content = 'अपने मानसिक स्वास्थ्य को समझने के लिए PHQ-9 या GAD-7 मूल्यांकन करें। मूड ट्रैकिंग भी आज़माएं।'
        maintain_title = 'अच्छा महसूस करते रहें'
        maintain_content = 'जो आपको खुश करता है वह करते रहें! अपनी सकारात्मकता साझा करें, पल का आनंद लें, या अच्छे दिनों को सेलिब्रेट करने के लिए मूड ट्रैकर आज़माएं।'
    else:
        crisis_title = 'Immediate Support Available'
        crisis_content = 'Please reach out for immediate help. You matter. Call KIRAN: 1800-599-0019 or Tele-MANAS: 14416 (24/7, toll-free). These helplines are available in multiple languages.'
        helpline_title = 'Professional Support'
        helpline_content = 'Consider speaking with a mental health professional. KIRAN (1800-599-0019) and Tele-MANAS (14416) offer free 24/7 support in multiple languages.'
        breath_title = 'Grounding Exercise'
        breath_content = 'Try the 4-7-8 breathing: Breathe in for 4 seconds, hold for 7, exhale for 8. Repeat 3-4 times.'
        activity_title = 'Gentle movement'
        activity_content = 'A short walk or light stretching can help regulate your nervous system.'
        journal_title = 'Journaling'
        journal_content = 'Writing down your thoughts can help process emotions. Try our mood tracking feature.'
        distract_music_title = 'Listen to Music'
        distract_music_content = 'Put on your favourite songs. Music can lift your mood and distract the mind from negative thoughts.'
        distract_walk_title = 'Take a Walk'
        distract_walk_content = 'Step outside for a short walk. Fresh air and movement can help shift your focus away from heavy thoughts.'
        distract_call_title = 'Reach Out'
        distract_call_content = 'Call or message a friend or family member. A chat with someone you trust can help take your mind off things.'
        distract_watch_title = 'Watch Something'
        distract_watch_content = 'Watch a favourite show, movie, or funny videos. A light distraction can give your mind a break.'
        checkin_title = 'Self-Care Check'
        checkin_content = 'Consider taking a PHQ-9 or GAD-7 assessment to understand your mental wellness. You can also try mood tracking.'
        maintain_title = 'Keep the Good Vibes'
        maintain_content = 'Keep doing what makes you happy! Share your positivity, savor the moment, or try our mood tracker to celebrate the good days.'

    if any(kw in HIGH_RISK_DISTRESS for kw in distress_keywords):
        recommendations.append({
            'type': 'crisis',
            'title': crisis_title,
            'content': crisis_content,
            'priority': 'urgent'
        })
        return recommendations

    if distress_keywords:
        recommendations.append({
            'type': 'helpline',
            'title': helpline_title,
            'content': helpline_content,
            'priority': 'high'
        })

    def needs_breathing(msg, matched_distress):
        text = (msg or '').lower()
        breathing_distress = {
            'anxiety', 'panic', 'overwhelmed', 'cant cope', 'scared', 'afraid', 'terrified'
        }
        if matched_distress and any(k in breathing_distress for k in matched_distress):
            return True
        keywords = [
            'anxiety', 'panic', 'panicking', 'overwhelmed', 'stress', 'stressed',
            'tight chest', 'heart racing', 'cant breathe', "can't breathe",
            'bechain', 'ghabraya', 'chinta', 'dar', 'gabrahat'
        ]
        return any(k in text for k in keywords)

    if sentiment == 'negative' or distress_keywords:
        if context:
            tip = _context_tip(context.get('situation'), lang)
            if tip:
                recommendations.append({
                    'type': 'context',
                    'title': 'Right-now idea' if not is_hi else 'अभी के लिए सुझाव',
                    'content': tip,
                    'priority': 'medium'
                })

        if needs_breathing(user_message, distress_keywords):
            recommendations.append({
                'type': 'breathing',
                'title': breath_title,
                'content': breath_content,
                'priority': 'medium'
            })

        recommendations.extend([
            {'type': 'activity', 'title': activity_title, 'content': activity_content, 'priority': 'medium'},
            {'type': 'distract_music', 'title': distract_music_title, 'content': distract_music_content, 'priority': 'medium'},
            {'type': 'distract_walk', 'title': distract_walk_title, 'content': distract_walk_content, 'priority': 'medium'},
            {'type': 'distract_call', 'title': distract_call_title, 'content': distract_call_content, 'priority': 'medium'},
            {'type': 'distract_watch', 'title': distract_watch_title, 'content': distract_watch_content, 'priority': 'low'},
        ])
    elif sentiment == 'neutral':
        neutral_options = [
            {'type': 'journal', 'title': journal_title, 'content': journal_content, 'priority': 'low'},
            {'type': 'breathing', 'title': breath_title, 'content': breath_content, 'priority': 'low'},
            {'type': 'checkin', 'title': checkin_title, 'content': checkin_content, 'priority': 'low'},
        ]
        recommendations.append(random.choice(neutral_options))
    else:
        recommendations.append({
            'type': 'maintain',
            'title': maintain_title,
            'content': maintain_content,
            'priority': 'low'
        })

    return recommendations


def _extract_topic(msg):
    msg_lower = (msg or '').lower()
    if any(w in msg_lower for w in ['work', 'job', 'office', 'boss', 'colleague']):
        return 'work'
    if any(w in msg_lower for w in ['family', 'parent', 'mom', 'dad', 'sibling']):
        return 'family'
    if any(w in msg_lower for w in ['friend', 'friends', 'relationship', 'partner']):
        return 'relationships'
    if any(w in msg_lower for w in ['study', 'exam', 'college', 'school']):
        return 'study'
    if any(w in msg_lower for w in ['today', 'day', 'morning', 'evening']):
        return 'day'
    return None


def _get_prior_context(history, lang):
    if not history or len(history) < 2:
        return None
    for i in range(len(history) - 1, -1, -1):
        if history[i]['role'] == 'user':
            prev = history[i]['content'].lower()
            if len(prev.split()) > 3:
                return prev[:100]
    return None


def _recently_asked_reason(history):
    if not history:
        return False
    for i in range(len(history) - 1, -1, -1):
        if history[i].get('role') == 'assistant':
            text = (history[i].get('content') or '').lower()
            if any(p in text for p in [
                'what feels hardest', 'what feels most difficult', 'what happened just before',
                'what do you need most', 'want to talk it through', 'tell me more', 'how are you feeling'
            ]):
                return True
            if '?' in text:
                return True
            return False
    return False


def _recently_asked_location(history):
    if not history:
        return False
    for i in range(len(history) - 1, -1, -1):
        if history[i].get('role') == 'assistant':
            text = (history[i].get('content') or '').lower()
            if any(p in text for p in [
                'where are you', 'where are you right now', 'which place', 'where are you at',
                'are you in class', 'are you at home', 'are you at work', 'are you in the office',
                'आप अभी कहाँ हैं', 'आप अभी कहां हैं', 'आप अभी कहां पर हैं', 'आप किस जगह हैं'
            ]):
                return True
            if '?' in text:
                return True
            return False
    return False


def _user_provided_reason(msg):
    text = (msg or '').lower()
    markers = [
        'because', 'since', 'due to', 'as ', 'my teacher', 'my boss', 'my friend', 'my parents',
        'scolded', 'scolded me', 'yelled', 'failed', 'missed', 'breakup', 'fight', 'argument',
        'exam', 'test', 'pressure', 'workload', 'deadline', 'lonely', 'alone', 'bullied',
        'relationship', 'family', 'money', 'financial', 'health', 'sick'
    ]
    if any(m in text for m in markers):
        return True
    return len(text.split()) >= 7


def _recent_user_messages(history, limit=4):
    if not history:
        return []
    user_msgs = [m for m in history if m.get('role') == 'user']
    return user_msgs[-limit:]


def _reason_in_history(history):
    for m in _recent_user_messages(history, limit=4):
        if _user_provided_reason(m.get('content') or ''):
            return True
    return False


def _place_in_history(history, lang, limit=4):
    for m in reversed(_recent_user_messages(history, limit=limit)):
        place, label = _explicit_place_label(m.get('content') or '', lang)
        if label:
            return place, label
    return '', ''


def _location_in_history(history, lang):
    place, label = _place_in_history(history, lang, limit=4)
    return bool(label)


def _extract_phrase(msg, min_len=4):
    words = (msg or '').split()
    if len(words) <= 2:
        return None
    skip = {'hi', 'hello', 'hey', 'ok', 'okay', 'yeah', 'yes', 'no', 'hmm', 'so', 'well'}
    for i, w in enumerate(words):
        if w.lower() not in skip and len(w) >= min_len:
            chunk = ' '.join(words[i:i+4])[:40]
            return chunk if len(chunk) > 5 else None
    return None


def get_chat_response(user_message, session_id=None, lang='en', conversation_history=None, context=None):
    """
    Main chatbot response logic - human-like, person-to-person style.
    Uses LLM (Gemini/OpenAI) when configured; otherwise falls back to rule-based responses.
    Returns dict with: response, sentiment, is_distress, recommendations
    """
    try:
        sentiment = analyze_sentiment(user_message)
        has_distress, distress_keywords = detect_distress(user_message)
        has_violence_risk, violence_keywords = detect_violence_risk(user_message)
        context_meta = _build_context(user_message, context, lang)
        history = conversation_history or []
        msg = (user_message or '').lower().strip()
        msg_words = len(msg.split())

        memory = (context or {}).get('memory') or {}
        preferred_name = memory.get('preferred_name') or ''

        if re.search(r"\bwhat is my name\b|\bdo you remember my name\b", msg):
            if preferred_name:
                response = f"Your name is {preferred_name}."
            else:
                response = "I don't think you've told me your name yet."
            return {
                'response': response,
                'sentiment': 'neutral',
                'is_distress': False,
                'recommendations': []
            }

        if has_violence_risk:
            if lang == 'hi':
                recommendations = [{
                    'type': 'emergency',
                    'title': 'तुरंत आपातकालीन सहायता',
                    'content': 'अगर किसी को चोट लगी है तो तुरंत आपातकालीन सेवा को कॉल करें (भारत: 112) और मेडिकल मदद लें।',
                    'priority': 'urgent'
                }]
                response = (
                    "यह बहुत गंभीर स्थिति है। अगर किसी को चोट लगी है, कृपया तुरंत आपातकालीन सहायता बुलाइए। "
                    "मैं किसी को नुकसान पहुंचाने या छिपाने में मदद नहीं कर सकता। "
                    "अभी सुरक्षित कदम लें: (1) आपातकालीन सेवा/पुलिस को कॉल करें (भारत में 112), "
                    "(2) घायल व्यक्ति के लिए मेडिकल मदद लें, (3) किसी विश्वसनीय बड़े/परिजन को तुरंत बताएं। "
                    "अगर आप घबराए हुए हैं, मैं अगले कुछ मिनट के लिए आपको शांत रहने में मदद कर सकता हूं।"
                )
            else:
                recommendations = [{
                    'type': 'emergency',
                    'title': 'Immediate Emergency Help',
                    'content': 'If someone is injured, call emergency services now (India: 112) and get medical help immediately.',
                    'priority': 'urgent'
                }]
                response = (
                    "This is a serious emergency. If someone may be hurt, call emergency services right now. "
                    "I can't help with harming someone or hiding what happened. "
                    "Take immediate safe steps: (1) call emergency/police now (India: 112), "
                    "(2) get medical help for the injured person, (3) inform a trusted adult/family member immediately. "
                    "If you're panicking, I can help you stay calm for the next few minutes while you do this."
                )

            return {
                'response': response,
                'sentiment': 'negative',
                'is_distress': True,
                'recommendations': recommendations,
            }

        explicit_place, explicit_label = _explicit_place_label(user_message, lang)
        if not explicit_label:
            explicit_place, explicit_label = _place_in_history(history, lang, limit=4)

        if not context_meta.get('situation') and explicit_place:
            if explicit_place in ('bus', 'train'):
                context_meta['situation'] = 'commuting'
            elif explicit_place == 'class':
                context_meta['situation'] = 'study'
            elif explicit_place == 'office':
                context_meta['situation'] = 'work'
            elif explicit_place == 'home':
                context_meta['situation'] = 'home'

        reason_present = _user_provided_reason(user_message) or _reason_in_history(history)
        location_present = bool(explicit_label) or bool(context_meta.get('situation'))
        asked_reason_recently = _recently_asked_reason(history)
        asked_location_recently = _recently_asked_location(history)

        suggestion_triggers = ['suggest', 'more', 'extra', 'other ideas', 'another way', 'any tips', 'any advice', 'help me']
        wants_suggestions = any(t in msg for t in suggestion_triggers)

        assessment_triggers = ['phq', 'gad', 'pss', 'assessment', 'test', 'questionnaire', 'screening', 'score']
        user_asked_assessment = any(t in msg for t in assessment_triggers)
        user_turns = len([m for m in history if m.get('role') == 'user']) + 1
        allow_assessments = user_asked_assessment or user_turns >= 3

        low_mood_markers = [
            'feeling low', 'feel low', 'feeling down', 'feel down', 'not feeling well',
            'not feeling good', 'not okay', 'not ok', 'sad', 'very sad'
        ]
        is_low_mood = any(m in msg for m in low_mood_markers)

        should_ask_reason = (sentiment == 'negative' or has_distress or is_low_mood) and not reason_present and not asked_reason_recently
        should_ask_location = (sentiment == 'negative' or has_distress) and reason_present and not location_present and not asked_location_recently

        if wants_suggestions:
            should_ask_reason = False
            should_ask_location = False

        if should_ask_reason:
            if lang == 'hi':
                response = "यह सुनकर दुख हुआ। क्या आप बता सकते हैं कि क्या वजह है?"
            else:
                response = "I'm really sorry you're feeling this way. Can you share what’s behind it?"
            return {
                'response': response,
                'sentiment': sentiment,
                'is_distress': has_distress,
                'recommendations': []
            }

        if should_ask_location and not wants_suggestions:
            if lang == 'hi':
                response = "धन्यवाद साझा करने के लिए। आप अभी कहाँ हैं—क्लास/ट्यूशन, कोचिंग, ऑफिस, बस/ट्रेन, लाइब्रेरी, पार्क/प्लेग्राउंड, या घर पर?"
            else:
                response = "Thanks for sharing that. Where are you right now—class/tuition, coaching, office, on a bus/train, library, hostel, gym, park/playground, or at home?"
            return {
                'response': response,
                'sentiment': sentiment,
                'is_distress': has_distress,
                'recommendations': []
            }

        greeting_words = {'hi', 'hello', 'hey', 'hii', 'hiii', 'namaste', 'hola'}
        is_greeting_only = msg_words <= 2 and any(w in msg for w in greeting_words)

        recommendations = [] if is_greeting_only else get_recommendations(
            sentiment, distress_keywords, user_message, lang, context=context_meta
        )

        if not allow_assessments and recommendations:
            recommendations = [r for r in recommendations if r.get('type') != 'checkin']

        emotion = detect_emotion(user_message)
        context_label = detect_context_label(user_message)
        llm_context = dict(context_meta)

        if memory:
            llm_context['memory'] = memory
        if emotion:
            llm_context['emotion'] = emotion
        if context_label and context_label != 'unknown':
            llm_context['context_label'] = context_label

        llm_response = _call_llm(user_message, history, lang, context=llm_context)
        if llm_response and llm_response.strip():
            return {
                'response': llm_response.strip(),
                'sentiment': sentiment,
                'is_distress': has_distress,
                'recommendations': recommendations,
            }

        is_hi = lang == 'hi'
        topic = _extract_topic(msg)
        prior = _get_prior_context(conversation_history or [], lang) if conversation_history else None
        phrase = _extract_phrase(user_message)
        asked_recently = _recently_asked_reason(conversation_history or []) or _recently_asked_location(conversation_history or [])

        if not is_hi:
            if has_distress and any(kw in HIGH_RISK_DISTRESS for kw in distress_keywords):
                response = "I hear you, and I want you to know that what you're feeling matters. You're not alone—there are people who genuinely want to help. "
            elif has_distress:
                response = random.choice([
                    "That sounds really heavy. I get it—some days everything feels like too much. Want to talk it through? Or we could find something small to shift the mood. ",
                    "I'm really sorry you're going through this. It's okay to not be okay. I'm here. Sometimes just venting helps, or we could think of one thing that might make the next hour a bit easier. ",
                ])
            elif sentiment == 'negative':
                responses = [
                    "Yeah, I feel you. Bad days happen. What usually helps you when you're in this headspace—music, a walk, talking to someone? ",
                    "That's tough. Your feelings make sense. Want to try shifting gears for a bit? Even 10 minutes of something different can sometimes help. ",
                    "I hear that. It's okay to feel this way. Sometimes the mind just needs a little break—what do you feel like doing? ",
                    "Ugh, that really sucks. Want to distract yourself for a bit? Music, a walk, or messaging a friend can help. ",
                    "I get it. Some days are just like that. You don't have to fix anything right now—but if you want to do something small, I've got ideas. ",
                ]
                if prior and ('stress' in prior or 'work' in prior or 'exam' in prior):
                    responses.append("Sounds like things have been building up. Let's find something to take the edge off—even a 5 min walk can reset things a bit. ")
                response = random.choice(responses)
            elif sentiment == 'positive':
                responses = [
                    "Oh that's so nice to hear! What's got you feeling good? ",
                    "Love that for you! Keep riding that wave. ",
                    "That's great! Savor it—you deserve it. ",
                    "Aw, I'm glad! Hope it lasts! ",
                    "Nice! Good vibes. What's making today better? ",
                ]
                if phrase and len(phrase.split()) <= 3:
                    responses.append(f"Good to hear about {phrase}! That's nice. ")
                if topic == 'work':
                    responses.append("That's awesome! A good day at work can really set the tone. What went well? ")
                elif topic == 'relationships':
                    responses.append("That's lovely! Being around people we care about really helps. ")
                response = random.choice(responses)
            else:
                response = ""

            if 'anxiety' in msg or 'panic' in msg:
                response = (response or "I hear you. ") + "Anxiety can be really overwhelming. Breathing helps—want to try a simple exercise together? "
            elif 'sleep' in msg or 'insomnia' in msg:
                response = (response or "Sleep struggles are the worst. ") + "You're not alone with that. Have you tried winding down with less screen time before bed? "
            elif 'lonely' in msg or 'isolated' in msg:
                response = (response or "Loneliness is hard. ") + "Our forum has people who get it—might help to connect with others who've felt the same. "
            elif not response.strip():
                if msg_words <= 3 and any(w in msg for w in ['hi', 'hello', 'hey', 'hola', 'namaste']):
                    response = random.choice([
                        "Hey! What's up? ",
                        "Hi! How's it going? ",
                        "Hey there! What's on your mind? ",
                    ])
                elif msg_words <= 2:
                    response = random.choice([
                        "What's going on? ",
                        "Tell me more? ",
                        "How are you feeling? ",
                    ])
                else:
                    if asked_recently:
                        response = random.choice([
                            "I hear you. I'm here with you. ",
                            "That makes sense. Take your time—no rush. ",
                            "I get it. We can go one small step at a time. ",
                        ])
                    else:
                        if phrase:
                            response = f'I hear you. When you say "{phrase}", what feels hardest about it right now? '
                        elif prior:
                            response = "I remember what you shared earlier. What changed most since then? "
                        else:
                            response = random.choice([
                                "I hear you. What part is feeling most difficult right now? ",
                                "Thanks for sharing that. What happened just before you started feeling this way? ",
                                "I'm with you. What do you need most right now: to vent, to calm down, or to plan next steps? ",
                            ])
        else:
            if has_distress and any(kw in HIGH_RISK_DISTRESS for kw in distress_keywords):
                response = "मैं सुन रहा हूं। जो आप महसूस कर रहे हैं वह महत्वपूर्ण है। आप अकेले नहीं हैं—लोग आपकी मदद करना चाहते हैं। "
            elif has_distress:
                response = random.choice([
                    "यह बहुत भारी लग रहा है। मैं समझता हूं—कभी-कभी सब कुछ ज्यादा लगता है। बात करें? या कोई छोटी चीज़ करके मूड बदल सकते हैं। ",
                    "मुझे खेद है कि आप ऐसा महसूस कर रहे हैं। ठीक नहीं होना ठीक है। मैं यहां हूं। कभी बस बात करने से ही हल्कापन लगता है। ",
                ])
            elif sentiment == 'negative':
                response = random.choice([
                    "हां, समझ सकता हूं। बुरे दिन आते हैं। आपको अक्सर क्या मदद करता है—संगीत, सैर, किसी से बात? ",
                    "यह कठिन है। आपकी भावनाएं सही हैं। ध्यान भटकाना चाहेंगे? 10 मिनट का बदलाव भी कभी-कभी मदद करता है। ",
                    "सुन रहा हूं। ऐसा महसूस करना ठीक है। मैं यहां हूं। मन को थोड़ा ब्रेक चाहिए होता है—आप क्या करना चाहेंगे? ",
                    "उफ़, ऐसा महसूस करने पर खेद है। क्या ध्यान भटकाना चाहेंगे—संगीत, बाहर जाना, या किसी दोस्त को मैसेज? ",
                ])
            elif sentiment == 'positive':
                response = random.choice([
                    "अच्छा! बहुत अच्छा लगा सुनकर। आज क्या अच्छा चल रहा है? ",
                    "यह तो बढ़िया! इस एनर्जी को बनाए रखें। आज खास क्या अच्छा है? ",
                    "बहुत खुशी हुई! आप अच्छा महसूस करने के हकदार हैं। ",
                    "वाह, अच्छा सुनकर मुझे भी अच्छा लगा। इस पल का आनंद लें! ",
                ])
            else:
                response = ""

            if 'anxiety' in msg or 'panic' in msg or 'bechain' in msg or 'ghabraya' in msg or 'chinta' in msg:
                response = (response or "सुन रहा हूं। ") + "चिंता बहुत भारी लग सकती है। सांस लेना मदद करता है—साथ में एक छोटा व्यायाम करें? "
            elif 'sleep' in msg or 'insomnia' in msg or 'neend' in msg or 'नींद' in user_message:
                response = (response or "नींद की समस्या कठिन होती है। ") + "सोने से पहले screen time कम करने से मदद मिल सकती है। "
            elif 'lonely' in msg or 'isolated' in msg or 'akela' in msg or 'अकेला' in user_message:
                response = (response or "अकेलापन कठिन है। ") + "हमारे forum में लोग हैं जो समझते हैं—जुड़ने में मदद मिल सकती है। "

            if not response.strip():
                if msg_words <= 3:
                    fallbacks_hi = [
                        "नमस्ते! कैसे हैं? ",
                        "हाय! क्या चल रहा है? ",
                        "बताइए, सुन रहा हूं। ",
                    ]
                else:
                    if asked_recently:
                        fallbacks_hi = [
                            "मैं समझ रहा हूं। मैं यहीं हूं। ",
                            "ठीक है, धीरे-धीरे चलेंगे। ",
                            "आप अकेले नहीं हैं। ",
                        ]
                    else:
                        if phrase:
                            response = f'मैं समझ रहा हूं। जब आप "{phrase}" कहते हैं, अभी सबसे मुश्किल हिस्सा क्या लग रहा है? '
                            fallbacks_hi = []
                        elif prior:
                            response = "मैंने आपकी पिछली बात याद रखी है। तब से सबसे ज्यादा क्या बदला है? "
                            fallbacks_hi = []
                        else:
                            fallbacks_hi = [
                                "मैं सुन रहा हूं। अभी सबसे भारी क्या लग रहा है? ",
                                "शेयर करने के लिए धन्यवाद। अभी आपको क्या चाहिए: बस vent करना, calm होना, या next step plan करना? ",
                                "मैं आपके साथ हूं। यह भावना कब से ज्यादा बढ़ी है? ",
                            ]
                if not response.strip() and fallbacks_hi:
                    response = random.choice(fallbacks_hi)

        if not has_violence_risk and (sentiment in ('negative', 'neutral') or has_distress) and msg_words > 2:
            context_line = _context_support_line(context_meta, lang, explicit_place=explicit_place, explicit_label=explicit_label)
            if context_line:
                response = (response + " " + context_line).strip()

        return {
            'response': response.strip(),
            'sentiment': sentiment,
            'is_distress': has_distress or has_violence_risk,
            'recommendations': recommendations
        }

    except Exception:
        return _safe_default_response(lang)
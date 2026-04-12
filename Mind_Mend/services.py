"""
MindMend AI Chatbot services
Modern LLM-driven conversational AI for empathetic mental health support.
Provides deep emotional nuance, situational memory, multilingual safety, and emergency handling.
"""
import random
import re
import uuid
from datetime import datetime
import json

from django.conf import settings

# -----------------------------------------------------------------------------
# HIGH-RISK / SAFETY DEFINITIONS (STRICT FALLBACK)
# -----------------------------------------------------------------------------
HIGH_RISK_DISTRESS = {
    'suicide', 'suicidal', 'kill myself', 'end my life', 'want to die',
    'self harm', 'self-harm', 'hurt myself', 'cutting',
    'no reason to live', 'better off dead', 'give up', 'cant go on',
    'aatmahatya', 'khudkushi', 'mar jana', 'naasht'
}

VIOLENCE_KEYWORDS = {
    'kill', 'murder', 'stab', 'stabbing', 'shot', 'shoot', 'shooting',
    'beat', 'beating', 'hit', 'weapon', 'blood', 'dead body',
    'accidentally killed', 'hurt him badly'
}

# -----------------------------------------------------------------------------
# IDENTIFIERS
# -----------------------------------------------------------------------------
def get_session_id():
    """Generate a unique session ID for anonymous chat."""
    return str(uuid.uuid4())[:12]

# -----------------------------------------------------------------------------
# LLM INTEGRATION LAYER
# -----------------------------------------------------------------------------
def _clean_llm_text(text):
    text = (text or '').strip()
    # Strip common markdown hallucinations for plain text wrappers, or keep it if UI handles markdown.
    # We will keep markdown as the current UI supports it, but ensure no weird JSON wrappers.
    return text if text else None

def _call_llm(messages, max_tokens=350):
    """
    Call Gemini or OpenAI. Expects messages in format [{'role': 'system'/'user'/'assistant', 'content': ...}]
    """
    provider = (getattr(settings, 'MINDMEND_LLM_PROVIDER', '') or '').strip().lower()
    gemini_key = getattr(settings, 'MINDMEND_GEMINI_API_KEY', '') or ''
    openai_key = getattr(settings, 'MINDMEND_OPENAI_API_KEY', '') or ''

    if not provider:
        provider = 'gemini' if gemini_key else 'openai'

    try:
        if (provider == 'gemini' and gemini_key) or provider == 'gemini':
            if not gemini_key:
                gemini_key = openai_key # fallback if configured weirdly
            import google.generativeai as genai
            from google.api_core import exceptions as google_exceptions
            import time
            genai.configure(api_key=gemini_key)
            
            # Extract system prompt if any
            system_instruction = ""
            
            for m in messages:
                if m['role'] == 'system':
                    system_instruction += m['content'] + "\n"
            
            # Gemini models
            model_names = [
                'gemini-flash-lite-latest',
                'gemini-2.0-flash-lite',
                'gemini-2.0-flash',
                'gemini-flash-latest'
            ]
            
            prompt = system_instruction + "\n\n"
            for m in messages:
                if m['role'] != 'system':
                    role_name = "User" if m['role'] == 'user' else "MindMend"
                    prompt += f"{role_name}: {m['content']}\n"
            if not prompt.endswith("MindMend: "):
                prompt += "MindMend: "

            for model_name in model_names:
                try:
                    model = genai.GenerativeModel(model_name)
                    resp = model.generate_content(prompt)
                    cleaned = _clean_llm_text(getattr(resp, 'text', None))
                    if cleaned:
                        return cleaned
                except google_exceptions.ResourceExhausted as e:
                    print(f"Gemini {model_name} rate limit. Waiting...")
                    time.sleep(5)
                    try:
                        resp = model.generate_content(prompt)
                        cleaned = _clean_llm_text(getattr(resp, 'text', None))
                        if cleaned:
                            return cleaned
                    except Exception as e2:
                        continue
                except Exception as e:
                    print(f"Gemini {model_name} failed: {e}")
                    continue
            
            # If all gemini models fail but openai key is available, fallback to openai
            if openai_key:
                provider = 'openai'
            else:
                return None

        if provider == 'openai' and openai_key:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            
            formatted_messages = []
            for m in messages:
                # Map assistant to assistant, user to user, system to system
                formatted_messages.append({'role': m['role'], 'content': m['content']})
                
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=formatted_messages,
                max_tokens=max_tokens,
                temperature=0.7
            )
            return _clean_llm_text(resp.choices[0].message.content if resp.choices else None)
    except Exception as e:
        print(f"LLM API Call Error: {e}")
        return None
    return None

# -----------------------------------------------------------------------------
# HEURISTICS & FEATURE EXTRACTION APIs (Imported by views)
# -----------------------------------------------------------------------------
def analyze_sentiment(text):
    """Simple rule-based baseline sentiment, purely for UI tagging."""
    text_lower = (text or '').lower()
    positive = {"happy", "good", "great", "amazing", "better", "improving", "hopeful", "calm", "sukhi", "khush"}
    negative = {"sad", "bad", "terrible", "angry", "anxious", "worried", "stressed", "lonely", "down", "udaas", "dukhi", "pareshan"}
    
    words = set(re.findall(r'\b\w+\b', text_lower))
    pos_count = len(words & positive)
    neg_count = len(words & negative)
    
    if pos_count > neg_count: return 'positive'
    if neg_count > pos_count: return 'negative'
    return 'neutral'

def detect_emotion(message):
    text = (message or '').lower()
    if any(k in text for k in ['angry', 'mad', 'furious', 'gussa']): return 'angry'
    if any(k in text for k in ['anxiety', 'panic', 'bechain', 'ghabraya', 'chinta']): return 'anxious'
    if any(k in text for k in ['overwhelmed', 'cant cope']): return 'overwhelmed'
    sentiment = analyze_sentiment(text)
    if sentiment == 'positive': return 'happy'
    if sentiment == 'negative': return 'sad'
    return 'neutral'

def detect_context_label(message):
    text = (message or '').lower()
    if any(w in text for w in ["class", "lecture", "exam", "library", "college", "school"]): return "class"
    if any(w in text for w in ["office", "meeting", "boss", "work", "deadline"]): return "office"
    if any(w in text for w in ["home", "room", "house", "hostel", "dorm"]): return "home"
    if any(w in text for w in ["bus", "train", "crowd", "metro", "park", "gym"]): return "public"
    return "unknown"

def extract_topics(message):
    text = (message or '').lower()
    topic_map = {
        'exams': ['exam', 'study', 'class'],
        'work': ['work', 'office', 'boss', 'job'],
        'family': ['family', 'parents', 'mom', 'dad'],
        'relationships': ['relationship', 'partner', 'boyfriend', 'girlfriend', 'breakup'],
        'friends': ['friend', 'friends', 'lonely'],
        'health': ['health', 'sick', 'pain'],
    }
    hits = []
    for topic, words in topic_map.items():
        if any(w in text for w in words):
            hits.append(topic)
    return hits

def extract_activities(message, recommendations=None):
    text = (message or '').lower()
    activities = []
    if any(w in text for w in ['music', 'song']): activities.append('music')
    if any(w in text for w in ['walk']): activities.append('walk')
    if any(w in text for w in ['breath', 'breathing']): activities.append('breathing')
    if any(w in text for w in ['journal', 'writing']): activities.append('journaling')
    return list(set(activities))

def extract_name(message):
    text = (message or '').strip()
    pattern = r"\b(?:my name is|i am|i'm) ([A-Za-z]+)\b"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        if len(name) >= 2 and name.lower() not in {"sad", "fine", "okay", "happy"}:
            return name
    return ""

# -----------------------------------------------------------------------------
# CORE LOGIC: SAFETY & RECOMMENDATIONS
# -----------------------------------------------------------------------------

def detect_distress(text):
    text_lower = (text or '').lower()
    matched = [kw for kw in HIGH_RISK_DISTRESS if kw in text_lower]
    return len(matched) > 0, matched

def detect_violence_risk(text):
    text_lower = (text or '').lower()
    matched = [kw for kw in VIOLENCE_KEYWORDS if kw in text_lower]
    return len(matched) > 0, matched

def _get_recommendations(sentiment, is_distress, is_high_risk, is_hi):
    recs = []
    if is_high_risk:
        recs.append({
            'type': 'crisis',
            'title': 'तुरंत सहायता उपलब्ध' if is_hi else 'Immediate Support Available',
            'content': 'KIRAN: 1800-599-0019 या Tele-MANAS: 14416 (24/7 निःशुल्क) पर कॉल करें।' if is_hi else 'Call KIRAN: 1800-599-0019 or Tele-MANAS: 14416 (24/7 toll-free).',
            'priority': 'urgent'
        })
        return recs
    
    if is_distress:
        recs.append({
            'type': 'helpline',
            'title': 'पेशेवर सहायता' if is_hi else 'Professional Support',
            'content': 'Tele-MANAS (14416) 24/7 निःशुल्क सहायता प्रदान करते हैं।' if is_hi else 'Tele-MANAS (14416) offers free 24/7 support.',
            'priority': 'high'
        })
    elif sentiment == 'negative':
        recs.append({
            'type': 'breathing',
            'title': 'ग्राउंडिंग व्यायाम' if is_hi else 'Grounding Exercise',
            'content': '4-7-8 सांस लें: 4 सेकंड सांस अंदर, 7 सेकंड रोकें, 8 सेकंड बाहर छोड़ें।' if is_hi else 'Try 4-7-8 breathing: In for 4s, hold for 7s, exhale for 8s.',
            'priority': 'medium'
        })
        recs.append({
            'type': 'distract_music',
            'title': 'संगीत सुनें' if is_hi else 'Listen to Music',
            'content': 'अपने पसंदीदा गाने लगाएं।' if is_hi else 'Put on your favourite songs to distract the mind.',
            'priority': 'medium'
        })
    return recs

# -----------------------------------------------------------------------------
# LLM SYSTEM PROMPT ENGINEERING
# -----------------------------------------------------------------------------
def _build_system_prompt(lang, context_meta, is_high_risk, is_violence_risk):
    lang_instruction = "IMPORTANT: You must reply entirely in Hindi (हिन्दी) or Hinglish depending on what the user speaks." if lang == 'hi' else "IMPORTANT: You must reply entirely in English."
    
    # Base Persona
    prompt = (
        "You are MindMend, a compassionate AI mental health support assistant. "
        "Your goal is to support users emotionally like a caring human friend while also giving helpful, practical coping strategies.\n\n"
        
        "Follow these rules strictly:\n"
        "1. Understand Emotion First\n"
        "- Detect if the user is feeling sad, anxious, stressed, depressed, lonely, or overwhelmed.\n"
        "- Acknowledge their feelings with empathy (e.g., \"I'm really sorry you're feeling this way\").\n\n"
        
        "2. Human-Like Response\n"
        "- Talk naturally, not like a robot. Write like you are texting a friend in short paragraphs.\n"
        "- Keep tone warm, supportive, and non-judgmental.\n\n"
        
        "3. Give Personalized Coping Tips\n"
        "Based on the user's situation, suggest 1-3 relevant techniques such as:\n"
        "- Deep breathing (for anxiety/panic)\n"
        "- Grounding techniques (for overthinking)\n"
        "- Small actionable steps (for procrastination)\n"
        "- Positive reframing (for negative thoughts)\n"
        "- Relaxation tips (for stress)\n\n"
        
        "4. Keep It Simple\n"
        "- Do NOT overload with too many tips.\n"
        "- Keep suggestions short and easy to follow. DO NOT use massive bulleted lists unless asked.\n\n"
        
        "5. Safety Handling (VERY IMPORTANT)\n"
        "- If user mentions self-harm or suicide:\n"
        "  - Respond calmly and supportively\n"
        "  - Encourage reaching out to trusted person or helpline\n"
        "  - Do NOT act as a doctor\n\n"
        
        "6. Ask Gentle Follow-up Questions\n"
        "- Example: \"Do you want to tell me what’s causing this feeling?\"\n\n"
        
        "7. Memory Awareness\n"
        "- Refer to previous messages to personalize responses.\n\n"
        
        "8. Language\n"
        "- Support both Hindi and English (Hinglish allowed if user uses it)\n\n"
        
        "9. Example Behavior:\n"
        "User: \"I feel very anxious about exams\"\n"
        "Response:\n"
        "- Acknowledge feeling\n"
        "- Give 1-2 tips (breathing + small study step)\n"
        "- Encourage gently\n\n"
        
        "If anxiety detected -> suggest breathing exercise\n"
        "If overthinking -> suggest grounding (5-4-3-2-1 method)\n"
        "If sadness/depression -> suggest small actions + emotional validation + listen music\n"
        "If stress -> suggest break + relaxation technique + walking outside\n"
        "If low motivation -> suggest micro-task strategy\n\n"

        "================ ADDITIONAL INSTRUCTIONS ==================\n"
        "10. MUST GIVE ACTIONABLE TIPS (VERY IMPORTANT)\n"
        "- ALWAYS give 2-4 practical coping tips when user is struggling.\n"
        "- Tips MUST match:\n"
        "   • Emotion (anxiety, sadness, stress)\n"
        "   • Situation (office, school, home, public place)\n\n"

        "11. SITUATION-BASED SMART SUGGESTIONS\n"
        "👉 If user is in OFFICE / WORK: Take a short break, Deep breathing at desk, Step outside for 5 minutes, Avoid overthinking about boss/work\n"
        "👉 If user is in SCHOOL / COLLEGE: Break study into small tasks, Take 5-min refresh break, Avoid comparing with others\n"
        "👉 If user is at HOME / ALONE: Go for a walk outside, Listen to calming music, Write thoughts in a journal, Talk to a trusted person\n"
        "👉 If user is in PUBLIC (bus/train/crowd): Focus on breathing (4-7-8 method), Grounding technique (5-4-3-2-1), Listen to music with earphones\n\n"

        "12. EMOTION-BASED SUGGESTIONS\n"
        "👉 Anxiety / Panic: Deep breathing (4-7-8), Grounding exercise\n"
        "👉 Depression / Sadness: Small actions (get up, walk, fresh air), Music or comfort activity\n"
        "👉 Overthinking: Write thoughts down, Reduce social media, Focus on present moment\n"
        "👉 Loneliness: Talk to a friend/family, Go outside or sit in open space\n\n"

        "13. ALWAYS FOLLOW RESPONSE STRUCTURE\n"
        "Always respond in this flow:\n"
        "1. Emotional validation\n"
        "2. Short supportive line\n"
        "3. 2-4 personalized tips\n"
        "4. Gentle follow-up question\n\n"

        "Example Response:\n"
        "\"I’m really sorry you're feeling this way... it sounds heavy.\n"
        "You're not alone in this.\n\n"
        "Maybe you can try:\n"
        "• Take a short walk outside\n"
        "• Try slow breathing for a few minutes\n"
        "• Put on some music you like\n\n"
        "Do you want to tell me what happened today?\"\n"
        "===========================================================\n"
    )

    # Memory & Context Integration
    memory = context_meta.get('memory', {})
    situation = context_meta.get('situation', 'unknown')
    
    context_str = "### USER CONTEXT:\n"
    has_context = False
    
    if memory.get('preferred_name'):
        context_str += f"- User's Name: {memory['preferred_name']}\n"
        has_context = True
    if situation and situation != 'unknown':
        context_str += f"- Current Location/Situation: {situation}\n"
        has_context = True
    if memory.get('last_emotion'):
        context_str += f"- Past Recent Emotion: {memory['last_emotion']}\n"
        has_context = True
    
    if has_context:
        prompt += context_str + "Use this context naturally to sound like you remember them. Don't be creepy by listing the facts.\n\n"

    # Emergency / High Risk Integration
    if is_high_risk:
        prompt += (
            "### EMERGENCY STATE TRIGGERED:\n"
            "The user has expressed thoughts of suicide or severe self-harm. \n"
            "1. Be extremely tender, protective, and non-judgmental.\n"
            "2. Tell them their pain matters and they are not alone.\n"
            "3. At the end of your short response, GENTLY mention: 'Please call the helpline at 1800-599-0019 or 14416. They really care and can support you right now.'\n\n"
        )
    if is_violence_risk:
        prompt += (
            "### VIOLENCE EMERGENCY STATE TRIGGERED:\n"
            "The user has expressed thoughts of severe violence, injury, or hurting others.\n"
            "1. Inform them you cannot assist with violence.\n"
            "2. Urge them to seek immediate emergency medical services (112 in India) and step away from the situation.\n\n"
        )

    prompt += lang_instruction
    return prompt

# -----------------------------------------------------------------------------
# MAIN CHAT FUNCTION
# -----------------------------------------------------------------------------
def get_chat_response(user_message, session_id=None, lang='en', conversation_history=None, context=None):
    """
    Main entry point for generating the chatbot response.
    Orchestrates safety checks, dynamic context building, LLM execution, and structured UI response.
    """
    history = conversation_history or []
    context_meta = context or {}
    msg_clean = (user_message or '').strip()
    
    if not msg_clean:
         return {
            'response': 'I am here with you. Can you tell me what is going on?',
            'sentiment': 'neutral',
            'is_distress': False,
            'recommendations': []
         }
         
    # 1. Deterministic Extraction
    sentiment = analyze_sentiment(msg_clean)
    is_high_risk, distress_kws = detect_distress(msg_clean)
    is_violence_risk, violence_kws = detect_violence_risk(msg_clean)
    
    is_distress = is_high_risk or is_violence_risk or any(bad in msg_clean.lower() for bad in ['depressed', 'anxiety attack', 'panic attack'])
    is_hi = (lang == 'hi')

    recs = _get_recommendations(sentiment, is_distress, is_high_risk, is_hi)
    
    # UI mapping for location extraction if passed
    if not context_meta.get('situation'):
        detected_loc = detect_context_label(msg_clean)
        if detected_loc != 'unknown':
            context_meta['situation'] = detected_loc

    # 2. Build the LLM Messages payload
    system_prompt = _build_system_prompt(lang, context_meta, is_high_risk, is_violence_risk)
    
    llm_messages = [{"role": "system", "content": system_prompt}]
    
    # Intercept simple greetings to prevent the LLM from overthinking history
    words = msg_clean.lower().split()
    is_greeting = len(words) <= 3 and any(w in {'hi', 'hello', 'hey', 'hii', 'namaste', 'hola'} for w in words)
    
    if is_greeting:
        # Avoid passing history if it's just a greeting, resetting interaction tone nicely
        llm_messages.append({"role": "user", "content": msg_clean + " \n[Internal System Note: The user said hello. Give a warm, 1-sentence friendly greeting. Ask how they are.]"})
    else:
        # Add limited history for context (last 6 messages max to preserve token budget & relevance)
        truncated_history = history[-6:] if len(history) > 6 else history
        for msg in truncated_history:
            role = 'user' if msg.get('role') == 'user' else 'assistant'
            llm_messages.append({"role": role, "content": msg.get('content', '')})
            
        llm_messages.append({"role": "user", "content": msg_clean})

    # 3. Request LLM Generation
    llm_response = _call_llm(llm_messages)
    
    # 4. Handle Response / Fallback
    if llm_response:
        final_response = llm_response
    else:
        # Graceful Failover
        if is_high_risk:
            final_response = "I hear you, and what you're feeling is so painful. Please know you're not alone. Reach out to 1800-599-0019 right now, there are people waiting to help."
            if is_hi:
                final_response = "मैं सुन रहा हूं। आपका यह दर्द बहुत गहरा है, लेकिन आप अकेले नहीं हैं। कृपया अभी 1800-599-0019 पर कॉल करें, वहां लोग आपकी मदद के लिए इंतज़ार कर रहे हैं।"
        elif is_violence_risk:
            final_response = "This sounds like an emergency. Please call local emergency services immediately (112)."
            if is_hi:
                final_response = "यह एक आपातकाल प्रतीत होता है। कृपया तुरंत 112 पर कॉल करें।"
        else:
            final_response = "I'm here with you. Can you tell me a little more about what's on your mind?"
            if is_hi:
                final_response = "मैं आपके साथ हूँ। क्या आप बता सकते हैं कि अभी आपको कैसा लग रहा है?"

    return {
        'response': final_response,
        'sentiment': sentiment,
        'is_distress': is_distress,
        'recommendations': recs
    }

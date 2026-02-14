"""
AI Chatbot service with sentiment analysis, distress detection, and optional LLM (Gemini/OpenAI).
"""
import random
import re
import uuid

from django.conf import settings


def _call_llm(user_message, conversation_history, lang):
    """
    Call Gemini or OpenAI for human-like response. Returns response text or None on failure.
    """
    provider = (getattr(settings, 'MINDMEND_LLM_PROVIDER', '') or '').strip().lower()
    gemini_key = getattr(settings, 'MINDMEND_GEMINI_API_KEY', '') or ''
    openai_key = getattr(settings, 'MINDMEND_OPENAI_API_KEY', '') or ''
    if not provider:
        # Auto-pick provider when keys are present to avoid silent fallback.
        if gemini_key:
            provider = 'gemini'
        elif openai_key:
            provider = 'openai'
        else:
            return None

    is_hindi = lang == 'hi'
    lang_instruction = "Respond in Hindi (हिन्दी)." if is_hindi else "Respond in English."

    system_prompt = f"""You are a warm, empathetic mental health support assistant. Talk like a caring friend—natural, conversational, human. Never sound robotic or like a bot.

Guidelines:
- Listen, validate feelings, and respond as a real person would
- If they're happy: celebrate with them, ask what's going well
- If they're sad/stressed: show empathy, suggest simple distractions (music, walk, calling a friend)
- For crisis (suicide, self-harm): be compassionate, emphasize they matter, share helplines: KIRAN 1800-599-0019, Tele-MANAS 14416 (24/7 India)
- Keep replies concise—1-3 short paragraphs. Match their energy
- Ask follow-up questions naturally. Reference what they said
- Never say you're an AI. You're just someone who listens

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

            # Build single prompt with conversation history
            parts = [system_prompt, "\n\n---\nConversation:\n"]
            for m in messages[:-1]:
                role = "User" if m["role"] == "user" else "Assistant"
                parts.append(f"{role}: {m['content']}\n")
            parts.append(f"User: {user_message}\nAssistant:")
            prompt = "".join(parts)

            # Try models in order (gemini-flash-lite-latest has best free-tier quota)
            model_names = ['gemini-flash-lite-latest', 'gemini-2.0-flash-lite', 'gemini-2.0-flash', 'gemini-flash-latest', 'gemma-3n-e2b-it']
            resp = None
            for model_name in model_names:
                try:
                    model = genai.GenerativeModel(model_name)
                    resp = model.generate_content(prompt)
                    if resp and resp.text:
                        return resp.text.strip()
                except google_exceptions.NotFound:
                    continue  # try next model
                except google_exceptions.ResourceExhausted as e:
                    # Quota exceeded - wait and retry once
                    retry_secs = 5
                    if 'retry' in str(e).lower() and 'retry_delay' in str(e):
                        try:
                            import re as re_mod
                            m = re_mod.search(r'retry in ([\d.]+)s', str(e).lower())
                            if m:
                                retry_secs = min(float(m.group(1)) + 1, 10)
                        except Exception:
                            pass
                    time.sleep(retry_secs)
                    try:
                        model = genai.GenerativeModel(model_name)
                        resp = model.generate_content(prompt)
                        if resp and resp.text:
                            return resp.text.strip()
                    except Exception:
                        pass
                    continue  # try next model
                except Exception:
                    continue
            return resp.text.strip() if resp and resp.text else None
        elif provider == 'openai':
            api_key = openai_key
            if not api_key:
                return None
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            formatted = [{"role": "system", "content": system_prompt}]
            for m in messages:
                formatted.append({"role": m["role"], "content": m["content"]})
            resp = client.chat.completions.create(model="gpt-4o-mini", messages=formatted, max_tokens=300)
            return resp.choices[0].message.content.strip() if resp.choices else None
    except Exception:
        return None
    return None


# Violence / serious harm keywords for emergency-safe handling.
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


# Distress keywords (English)
DISTRESS_KEYWORDS_EN = {
    'suicide', 'suicidal', 'kill myself', 'end my life', 'want to die',
    'self harm', 'self-harm', 'hurt myself', 'cutting', 'hopeless',
    'no reason to live', 'better off dead', 'give up', 'cant go on',
    'anxiety', 'panic', 'overwhelmed', 'cant cope', 'depressed',
    'lonely', 'isolated', 'abandoned', 'worthless', 'failure',
    'scared', 'afraid', 'terrified', 'crisis', 'emergency'
}

# Distress keywords (Hindi - Romanized)
DISTRESS_KEYWORDS_HI = {
    'aatmahatya', 'khudkushi', 'mar jana', 'naasht', 'udaas',
    'nirash', 'bechain', 'ghabraya', 'chinta', 'takleef',
    'tang', 'thakaan', 'akela', 'bekar', 'asafal',
    'dar', 'darr', 'pareshan', 'dukhi', 'dil tuta'
}

# Positive sentiment words (English + Hindi Romanized)
POSITIVE_WORDS = {
    'happy', 'good', 'great', 'wonderful', 'amazing', 'better', 'improving',
    'hopeful', 'calm', 'peaceful', 'relieved', 'grateful', 'joy', 'love',
    'excited', 'optimistic', 'confident', 'strong', 'proud', 'content',
    'fine', 'ok', 'okay', 'alright', 'well', 'decent',
    'achha', 'accha', 'sukhi', 'khush', 'badhiya', 'theek', 'acchha'
}

# Negative sentiment words (English + Hindi Romanized)
NEGATIVE_WORDS = {
    'sad', 'bad', 'terrible', 'awful', 'horrible', 'worst', 'angry',
    'frustrated', 'anxious', 'nervous', 'scared', 'worried', 'stressed',
    'tired', 'exhausted', 'lonely', 'confused', 'lost', 'helpless',
    'hopeless', 'overwhelmed', 'depressed', 'miserable', 'upset',
    'udaas', 'dukhi', 'bura', 'bekar', 'gussa', 'thaka', 'pareshan'
}


def get_session_id():
    """Generate a unique session ID for anonymous chat."""
    return str(uuid.uuid4())[:12]


def analyze_sentiment(text):
    """Simple rule-based sentiment analysis. Returns: positive, negative, neutral."""
    text_lower = text.lower()
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
    text_lower = text.lower()
    matched = [kw for kw in DISTRESS_KEYWORDS_EN | DISTRESS_KEYWORDS_HI if kw in text_lower]
    return len(matched) > 0, matched


def get_recommendations(sentiment, distress_keywords, user_message, lang='en'):
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

    # Crisis response for acute distress
    crisis_kw = ['suicide', 'suicidal', 'kill myself', 'end my life', 'self harm', 'hurt myself', 'better off dead',
                 'aatmahatya', 'khudkushi', 'mar jana']
    if any(kw in crisis_kw for kw in distress_keywords):
        recommendations.append({
            'type': 'crisis', 'title': crisis_title, 'content': crisis_content, 'priority': 'urgent'
        })
        return recommendations

    if distress_keywords:
        recommendations.append({
            'type': 'helpline', 'title': helpline_title, 'content': helpline_content, 'priority': 'high'
        })

    if sentiment == 'negative' or distress_keywords:
        # Mix of grounding + distraction activities to shift focus from negative thoughts
        recommendations.extend([
            {'type': 'breathing', 'title': breath_title, 'content': breath_content, 'priority': 'medium'},
            {'type': 'activity', 'title': activity_title, 'content': activity_content, 'priority': 'medium'},
            {'type': 'distract_music', 'title': distract_music_title, 'content': distract_music_content, 'priority': 'medium'},
            {'type': 'distract_walk', 'title': distract_walk_title, 'content': distract_walk_content, 'priority': 'medium'},
            {'type': 'distract_call', 'title': distract_call_title, 'content': distract_call_content, 'priority': 'medium'},
            {'type': 'distract_watch', 'title': distract_watch_title, 'content': distract_watch_content, 'priority': 'low'},
        ])
    elif sentiment == 'neutral':
        # Vary neutral recommendations - offer mood tracking, breathing, or forum, not just assessments
        neutral_options = [
            {'type': 'journal', 'title': journal_title, 'content': journal_content, 'priority': 'low'},
            {'type': 'breathing', 'title': breath_title, 'content': breath_content, 'priority': 'low'},
            {'type': 'checkin', 'title': checkin_title, 'content': checkin_content, 'priority': 'low'},
        ]
        recommendations.append(random.choice(neutral_options))
    else:
        recommendations.append({'type': 'maintain', 'title': maintain_title, 'content': maintain_content, 'priority': 'low'})

    return recommendations


def _extract_topic(msg):
    """Pick up on topics the user mentioned for more personal responses."""
    msg_lower = msg.lower()
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
    """Extract useful context from conversation history for continuity."""
    if not history or len(history) < 2:
        return None
    # Get last user message before current one
    for i in range(len(history) - 1, -1, -1):
        if history[i]['role'] == 'user':
            prev = history[i]['content'].lower()
            if len(prev.split()) > 3:  # Substantive message
                return prev[:100]  # First 100 chars
    return None


def _extract_phrase(msg, min_len=4):
    """Pick a short phrase from user message to reference naturally."""
    words = msg.split()
    if len(words) <= 2:
        return None
    # Get a meaningful chunk (skip hi, hello, etc.)
    skip = {'hi', 'hello', 'hey', 'ok', 'okay', 'yeah', 'yes', 'no', 'hmm', 'so', 'well'}
    for i, w in enumerate(words):
        if w.lower() not in skip and len(w) >= min_len:
            chunk = ' '.join(words[i:i+4])[:40]
            return chunk if len(chunk) > 5 else None
    return None


def get_chat_response(user_message, session_id=None, lang='en', conversation_history=None):
    """
    Main chatbot response logic - human-like, person-to-person style.
    Uses LLM (Gemini/OpenAI) when configured; otherwise falls back to rule-based responses.
    Returns dict with: response, sentiment, is_distress, recommendations
    """
    sentiment = analyze_sentiment(user_message)
    has_distress, distress_keywords = detect_distress(user_message)
    has_violence_risk, violence_keywords = detect_violence_risk(user_message)
    recommendations = get_recommendations(sentiment, distress_keywords, user_message, lang)
    history = conversation_history or []

    # Handle serious violence admissions before normal chat behavior.
    if has_violence_risk:
        if lang == 'hi':
            recommendations = [{
                'type': 'emergency',
                'title': 'तुरंत आपातकालीन सहायता',
                'content': 'अगर किसी को चोट लगी है तो तुरंत आपातकालीन सेवा को कॉल करें (भारत: 112) और मेडिकल मदद लें।',
                'priority': 'urgent'
            }]
        else:
            recommendations = [{
                'type': 'emergency',
                'title': 'Immediate Emergency Help',
                'content': 'If someone is injured, call emergency services now (India: 112) and get medical help immediately.',
                'priority': 'urgent'
            }]
        if lang == 'hi':
            response = (
                "यह बहुत गंभीर स्थिति है। अगर किसी को चोट लगी है, कृपया तुरंत आपातकालीन सहायता बुलाइए। "
                "मैं किसी को नुकसान पहुंचाने या छिपाने में मदद नहीं कर सकता। "
                "अभी सुरक्षित कदम लें: (1) आपातकालीन सेवा/पुलिस को कॉल करें (भारत में 112), "
                "(2) घायल व्यक्ति के लिए मेडिकल मदद लें, (3) किसी विश्वसनीय बड़े/परिजन को तुरंत बताएं। "
                "अगर आप घबराए हुए हैं, मैं अगले कुछ मिनट के लिए आपको शांत रहने में मदद कर सकता हूं।"
            )
        else:
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

    # Try LLM first when provider and API key are set
    llm_response = _call_llm(user_message, history, lang)
    if llm_response and llm_response.strip():
        return {
            'response': llm_response.strip(),
            'sentiment': sentiment,
            'is_distress': has_distress,
            'recommendations': recommendations,
        }

    msg = user_message.lower().strip()
    msg_words = len(msg.split())
    is_hi = lang == 'hi'
    topic = _extract_topic(msg)
    prior = _get_prior_context(conversation_history or [], lang) if conversation_history else None
    phrase = _extract_phrase(user_message)

    # Build conversational, human-like response (English)
    if not is_hi:
        if has_distress and any(kw in distress_keywords for kw in ['suicide', 'suicidal', 'kill', 'self harm', 'aatmahatya', 'khudkushi']):
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
            if prior and 'stress' in prior or 'work' in prior or 'exam' in prior:
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
            if phrase and len(phrase.split()) <= 3:  # Short phrases only
                responses.append(f"Good to hear about {phrase}! That's nice. ")
            if topic == 'work':
                responses.append("That's awesome! A good day at work can really set the tone. What went well? ")
            elif topic == 'relationships':
                responses.append("That's lovely! Being around people we care about really helps. ")
            response = random.choice(responses)
        else:
            response = ""
        # Add contextual touch when relevant
        if 'anxiety' in msg or 'panic' in msg:
            response = (response or "I hear you. ") + "Anxiety can be really overwhelming. Breathing helps—want to try a simple exercise together? "
        elif 'sleep' in msg or 'insomnia' in msg:
            response = (response or "Sleep struggles are the worst. ") + "You're not alone with that. Have you tried winding down with less screen time before bed? "
        elif 'lonely' in msg or 'isolated' in msg:
            response = (response or "Loneliness is hard. ") + "Our forum has people who get it—might help to connect with others who've felt the same. "
        elif not response.strip():
            # Match brevity - short reply for hi/hello, more for longer messages
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
                if phrase:
                    response = f"I hear you. When you say \"{phrase}\", what feels hardest about it right now? "
                elif prior:
                    response = "I remember what you shared earlier. What changed most since then? "
                else:
                    response = random.choice([
                        "I hear you. What part is feeling most difficult right now? ",
                        "Thanks for sharing that. What happened just before you started feeling this way? ",
                        "I'm with you. What do you need most right now: to vent, to calm down, or to plan next steps? ",
                    ])
    else:
        # Hindi responses - conversational, person-to-person
        if has_distress and any(kw in distress_keywords for kw in ['suicide', 'suicidal', 'kill', 'self harm', 'aatmahatya', 'khudkushi']):
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
                if phrase:
                    response = f"मैं समझ रहा हूं। जब आप \"{phrase}\" कहते हैं, अभी सबसे मुश्किल हिस्सा क्या लग रहा है? "
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

    return {
        'response': response.strip(),
        'sentiment': sentiment,
        'is_distress': has_distress or has_violence_risk,
        'recommendations': recommendations
    }

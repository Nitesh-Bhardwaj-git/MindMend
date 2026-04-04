import json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ..models import ContactMessage, ChatMessage, UserAccessLocation, UserMemory
from ..forms import ContactForm
from ..services import get_chat_response, get_session_id, detect_emotion, detect_context_label, extract_topics, extract_activities, extract_name
from ..location_tracker import reverse_geocode, get_client_ip
from django.utils import timezone


def home(request):
    return render(request, 'Mind_Mend/home.html')


def contact_us(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            ContactMessage.objects.create(
                name=form.cleaned_data['name'],
                email=form.cleaned_data['email'],
                subject=form.cleaned_data['subject'],
                message=form.cleaned_data['message'],
            )
            messages.success(request, 'Thank you for your message. We will get back to you soon.')
            return redirect('contact_us')
    else:
        form = ContactForm()
    return render(request, 'Mind_Mend/contact_us.html', {'form': form})


def resources(request):
    helplines = [
        {
            'name': 'KIRAN',
            'number': '1800-599-0019',
            'desc': '24/7 Mental Health Rehabilitation Helpline. Available in 13 languages.',
            'languages': 'Hindi, English, Assamese, Tamil, Marathi, Odia, Telugu, Malayalam, Gujarati, Punjabi, Kannada, Bengali, Urdu'
        },
        {
            'name': 'Tele-MANAS',
            'number': '14416 / 1-800-891-4416',
            'desc': '24/7 Tele Mental Health Assistance. Provides counseling, basic support, and video consultations.',
            'languages': 'English and 20+ regional languages'
        },
    ]
    return render(request, 'Mind_Mend/Helpline.html', {'helplines': helplines, 'features': []})


def share_location_api(request):
    """Accept browser GPS coordinates for accurate location. POST {lat, lon}.
    NOTE: Removed @csrf_exempt for security - request must now include X-CSRFToken header.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}
    lat = data.get('lat')
    lon = data.get('lon')
    if lat is None or lon is None:
        return JsonResponse({'error': 'lat and lon required'}, status=400)
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid lat/lon'}, status=400)
    if not (-90 <= lat_f <= 90) or not (-180 <= lon_f <= 180):
        return JsonResponse({'error': 'Invalid coordinates'}, status=400)

    if not request.session.session_key:
        request.session.save()
    session_id = request.session.session_key or get_session_id()
    addr = reverse_geocode(lat_f, lon_f)
    ip = get_client_ip(request)

    from datetime import timedelta
    recent_cutoff = timezone.now() - timedelta(minutes=10)
    recent_qs = UserAccessLocation.objects.filter(
        location_source='browser',
        created_at__gte=recent_cutoff,
        latitude=lat_f,
        longitude=lon_f,
    )
    if request.user.is_authenticated:
        recent_qs = recent_qs.filter(user=request.user)
    else:
        recent_qs = recent_qs.filter(user__isnull=True, session_id=session_id)

    if not recent_qs.exists():
        UserAccessLocation.objects.create(
            user=request.user if request.user.is_authenticated else None,
            session_id=session_id,
            ip_address=ip or None,
            country=addr.get('country', ''),
            state=addr.get('state', ''),
            city=addr.get('city', ''),
            latitude=lat_f,
            longitude=lon_f,
            page_path=request.META.get('HTTP_REFERER', '')[:255] or '/',
            location_source='browser',
        )
    return JsonResponse({'ok': True, 'city': addr.get('city'), 'state': addr.get('state'), 'country': addr.get('country')})


def chat(request):
    prior_messages = []
    if request.user.is_authenticated:
        prior = list(ChatMessage.objects.filter(user=request.user).order_by('created_at')[:20])
        prior_messages = [{'role': m.role, 'content': m.content} for m in prior]
    return render(request, 'Mind_Mend/chat.html', {
        'prior_messages_json': json.dumps(prior_messages) if prior_messages else '[]',
    })


def _chat_context_from_request(request, session_id, data):
    context = {
        'client_time': data.get('client_time') or request.POST.get('client_time'),
        'client_tz_offset': data.get('client_tz_offset') or request.POST.get('client_tz_offset'),
        'client_tz': data.get('client_tz') or request.POST.get('client_tz'),
    }
    location = None
    if request.user.is_authenticated:
        location = UserAccessLocation.objects.filter(user=request.user).order_by('-created_at').first()
    else:
        location = UserAccessLocation.objects.filter(user__isnull=True, session_id=session_id).order_by('-created_at').first()
    if location:
        context['location'] = {
            'city': location.city,
            'state': location.state,
            'country': location.country,
            'source': location.location_source,
        }
    memory = None
    if request.user.is_authenticated:
        memory = UserMemory.objects.filter(user=request.user).first()
    else:
        memory = UserMemory.objects.filter(user__isnull=True, session_id=session_id).first()
        
    context['memory'] = {}
    if memory:
        context['memory'].update({
            'topics': memory.stress_topics or [],
            'activities': memory.helpful_activities or [],
            'last_emotion': memory.last_emotion or '',
            'last_context': memory.last_context or '',
            'preferred_name': memory.preferred_name or '',
        })
        
    if not context['memory'].get('preferred_name') and request.user.is_authenticated:
        context['memory']['preferred_name'] = request.user.first_name or request.user.username
        
    return context


@csrf_exempt
def chat_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}

    message = data.get('message', '') or request.POST.get('message', '')
    session_id = data.get('session_id') or request.POST.get('session_id') or get_session_id()
    lang = data.get('lang', 'en') or request.POST.get('lang', 'en')

    if lang not in ('en', 'hi'):
        lang = 'en'

    if not message.strip():
        return JsonResponse({'error': 'Empty message'}, status=400)

    if request.user.is_authenticated:
        recent = list(ChatMessage.objects.filter(user=request.user).order_by('-created_at')[:20])
    else:
        recent = list(ChatMessage.objects.filter(session_id=session_id, user__isnull=True).order_by('-created_at')[:20])

    recent.reverse()
    history = [{'role': m.role, 'content': m.content} for m in recent]
    context = _chat_context_from_request(request, session_id, data)

    try:
        result = get_chat_response(
            message,
            session_id,
            lang=lang,
            conversation_history=history,
            context=context
        )
        if not isinstance(result, dict):
            raise ValueError("get_chat_response must return a dict")
        response_text = (result.get('response') or '').strip()
        if not response_text:
            response_text = "I'm here with you. Tell me a little more about what feels hardest right now." if lang == 'en' else "मैं आपके साथ हूँ। अभी आपको सबसे मुश्किल क्या लग रहा है, थोड़ा और बताइए।"
        sentiment = result.get('sentiment', 'neutral')
        is_distress = result.get('is_distress', False)
        recommendations = result.get('recommendations', [])
    except Exception as service_error:
        print("chat_api service error:", service_error)
        response_text = "I'm still here with you. I couldn't reach the main support system right now, but you can tell me what feels hardest at this moment." if lang == 'en' else "मैं अभी भी आपके साथ हूँ। अभी मुख्य सहायता प्रणाली तक पहुँचना संभव नहीं हुआ, लेकिन आप बता सकते हैं कि इस समय सबसे मुश्किल क्या लग रहा है।"
        sentiment = 'neutral'
        is_distress = False
        recommendations = []

    try:
        ChatMessage.objects.create(user=request.user if request.user.is_authenticated else None, session_id=session_id, role='user', content=message)
        ChatMessage.objects.create(user=request.user if request.user.is_authenticated else None, session_id=session_id, role='assistant', content=response_text, sentiment=sentiment)
    except Exception as db_error:
        print("chat_api message save error:", db_error)

    try:
        if request.user.is_authenticated:
            memory, _ = UserMemory.objects.get_or_create(user=request.user, defaults={'session_id': ''})
        else:
            memory, _ = UserMemory.objects.get_or_create(user=None, session_id=session_id)

        if memory:
            emotion = detect_emotion(message)
            context_label = detect_context_label(message)
            topics = extract_topics(message)
            activities = extract_activities(message, recommendations)

            if emotion: memory.last_emotion = emotion
            if context_label and context_label != 'unknown': memory.last_context = context_label
            name = extract_name(message)
            if name: memory.preferred_name = name

            if topics:
                merged = list(dict.fromkeys(topics + (memory.stress_topics or [])))
                memory.stress_topics = merged[:10]
            if activities:
                merged = list(dict.fromkeys(activities + (memory.helpful_activities or [])))
                memory.helpful_activities = merged[:10]
            memory.save()
    except Exception as memory_error:
        print("chat_api memory update error:", memory_error)

    return JsonResponse({
        'response': response_text,
        'sentiment': sentiment,
        'is_distress': is_distress,
        'recommendations': recommendations,
        'session_id': session_id
    })

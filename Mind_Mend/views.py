import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Count, Avg
from django.core.paginator import Paginator

from .models import (
    MoodEntry, ForumPost, ForumReply, Counsellor, CounsellorBooking,
    CounsellorChatMessage, CounsellorReview, SleepLog,
    AssessmentResult, ChatMessage, UserAccessLocation
)
from .forms import SignUpForm, MoodEntryForm, ForumPostForm, ForumReplyForm, CounsellorBookingForm, ContactForm, CounsellorReviewForm, SleepLogForm
from .services import get_chat_response, get_session_id
from .location_tracker import reverse_geocode
from .assessment_data import (
    PHQ9_QUESTIONS, GAD7_QUESTIONS, PSS_QUESTIONS,
    get_phq9_result, get_gad7_result, get_pss_result, PSS_REVERSE_ITEMS
)


def home(request):
    return render(request, 'Mind_Mend/home.html')


def contact_us(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            messages.success(request, 'Thank you for your message. We will get back to you soon.')
            return redirect('contact_us')
    else:
        form = ContactForm()
    return render(request, 'Mind_Mend/contact_us.html', {'form': form})


def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'Mind_Mend/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect(request.GET.get('next', 'home'))
        else:
            username = request.POST.get('username', '').strip()
            username_not_found = username and not User.objects.filter(username=username).exists()
    else:
        form = AuthenticationForm()
        username_not_found = False
    return render(request, 'Mind_Mend/login.html', {'form': form, 'username_not_found': username_not_found})


def logout_view(request):
    logout(request)
    return redirect('home')


@csrf_exempt
def share_location_api(request):
    """Accept browser GPS coordinates for accurate location. POST {lat, lon}."""
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

    addr = reverse_geocode(lat_f, lon_f)
    UserAccessLocation.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_id=getattr(request.session, 'session_key', '') or '',
        ip_address=None,
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
    # Load prior messages for logged-in users so they see their conversation
    prior_messages = []
    if request.user.is_authenticated:
        prior = list(ChatMessage.objects.filter(user=request.user).order_by('created_at')[:20])
        prior_messages = [{'role': m.role, 'content': m.content} for m in prior]
    return render(request, 'Mind_Mend/chat.html', {
        'prior_messages_json': json.dumps(prior_messages) if prior_messages else '[]',
    })


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
    # Fetch conversation history: by user for logged-in (persistent), by session_id for anonymous
    if request.user.is_authenticated:
        recent = list(ChatMessage.objects.filter(user=request.user).order_by('-created_at')[:20])
    else:
        recent = list(ChatMessage.objects.filter(session_id=session_id, user__isnull=True).order_by('-created_at')[:20])
    recent.reverse()  # chronological order
    history = [{'role': m.role, 'content': m.content} for m in recent]
    result = get_chat_response(message, session_id, lang=lang, conversation_history=history)
    # Save for all users (incl. anonymous) to enable conversation memory
    ChatMessage.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_id=session_id, role='user', content=message
    )
    ChatMessage.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_id=session_id, role='assistant', content=result['response'], sentiment=result['sentiment']
    )
    return JsonResponse({
        'response': result['response'],
        'sentiment': result['sentiment'],
        'is_distress': result['is_distress'],
        'recommendations': result['recommendations'],
        'session_id': session_id
    })


def assessments_home(request):
    return render(request, 'Mind_Mend/assessments.html')


def _process_phq9(request):
    if request.method != 'POST':
        return None
    total = 0
    answers = {}
    for i in range(len(PHQ9_QUESTIONS)):
        val = request.POST.get(f'q{i}')
        if val is not None:
            v = int(val)
            total += v
            answers[f'q{i}'] = v
    if len(answers) != len(PHQ9_QUESTIONS):
        return None
    result_level = get_phq9_result(total)
    return total, answers, result_level


def assessment_phq9(request):
    if request.method == 'POST':
        r = _process_phq9(request)
        if r:
            total, answers, result_level = r
            if request.user.is_authenticated:
                AssessmentResult.objects.create(
                    user=request.user, assessment_type='phq9',
                    total_score=total, result_level=result_level, answers=answers
                )
            return render(request, 'Mind_Mend/assessment_result.html', {
                'assessment_name': 'PHQ-9 Depression',
                'score': total,
                'max_score': 27,
                'result_level': result_level,
                'next_url': 'assessments',
            })
    return render(request, 'Mind_Mend/assessment_phq9.html', {
        'questions': PHQ9_QUESTIONS,
        'scale': list(range(4)),
        'labels': ['Not at all', 'Several days', 'More than half the days', 'Nearly every day']
    })


def _process_gad7(request):
    if request.method != 'POST':
        return None
    total = 0
    answers = {}
    for i in range(len(GAD7_QUESTIONS)):
        val = request.POST.get(f'q{i}')
        if val is not None:
            v = int(val)
            total += v
            answers[f'q{i}'] = v
    if len(answers) != len(GAD7_QUESTIONS):
        return None
    result_level = get_gad7_result(total)
    return total, answers, result_level


def assessment_gad7(request):
    if request.method == 'POST':
        r = _process_gad7(request)
        if r:
            total, answers, result_level = r
            if request.user.is_authenticated:
                AssessmentResult.objects.create(
                    user=request.user, assessment_type='gad7',
                    total_score=total, result_level=result_level, answers=answers
                )
            return render(request, 'Mind_Mend/assessment_result.html', {
                'assessment_name': 'GAD-7 Anxiety',
                'score': total,
                'max_score': 21,
                'result_level': result_level,
                'next_url': 'assessments',
            })
    return render(request, 'Mind_Mend/assessment_gad7.html', {
        'questions': GAD7_QUESTIONS,
        'scale': list(range(4)),
        'labels': ['Not at all', 'Several days', 'Over half the days', 'Nearly every day']
    })


def _process_pss(request):
    if request.method != 'POST':
        return None
    answers = []
    for i in range(len(PSS_QUESTIONS)):
        val = request.POST.get(f'q{i}')
        if val is None:
            return None
        answers.append(int(val))
    result_level = get_pss_result(answers)
    total = 0
    for i, a in enumerate(answers):
        if (i + 1) in PSS_REVERSE_ITEMS:
            total += (4 - a)
        else:
            total += a
    return total, {f'q{i}': a for i, a in enumerate(answers)}, result_level


def assessment_pss(request):
    if request.method == 'POST':
        r = _process_pss(request)
        if r:
            total, answers, result_level = r
            if request.user.is_authenticated:
                AssessmentResult.objects.create(
                    user=request.user, assessment_type='pss',
                    total_score=total, result_level=result_level, answers=answers
                )
            return render(request, 'Mind_Mend/assessment_result.html', {
                'assessment_name': 'PSS-10 Stress',
                'score': total,
                'max_score': 40,
                'result_level': result_level,
                'next_url': 'assessments',
            })
    return render(request, 'Mind_Mend/assessment_pss.html', {
        'questions': PSS_QUESTIONS,
        'scale': list(range(5)),
        'labels': ['Never', 'Almost Never', 'Sometimes', 'Fairly Often', 'Very Often']
    })


def forum_list(request):
    category = request.GET.get('category', '')
    qs = ForumPost.objects.all().annotate(reply_count=Count('forumreply')).order_by('-created_at')
    if category and category in dict(ForumPost.CATEGORY_CHOICES):
        qs = qs.filter(category=category)
    paginator = Paginator(qs, 10)
    page = request.GET.get('page', 1)
    posts = paginator.get_page(page)
    return render(request, 'Mind_Mend/forum_list.html', {'posts': posts, 'current_category': category})


def recovery_stories(request):
    """Recovery stories — forum posts with category=recovery."""
    posts = ForumPost.objects.filter(category='recovery').annotate(reply_count=Count('forumreply')).order_by('-created_at')
    paginator = Paginator(posts, 10)
    page = request.GET.get('page', 1)
    posts = paginator.get_page(page)
    return render(request, 'Mind_Mend/recovery_stories.html', {'posts': posts})


@login_required
def forum_create(request):
    if request.method == 'POST':
        form = ForumPostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            return redirect('forum_detail', pk=post.pk)
    else:
        initial = {}
        if request.GET.get('category') in dict(ForumPost.CATEGORY_CHOICES):
            initial['category'] = request.GET.get('category')
        form = ForumPostForm(initial=initial)
    return render(request, 'Mind_Mend/forum_create.html', {'form': form})


def forum_detail(request, pk):
    post = get_object_or_404(ForumPost, pk=pk)
    replies = post.forumreply_set.all().order_by('created_at')
    return render(request, 'Mind_Mend/forum_detail.html', {
        'post': post,
        'replies': replies,
        'reply_form': ForumReplyForm()
    })


@login_required
def forum_reply(request, pk):
    post = get_object_or_404(ForumPost, pk=pk)
    if request.method == 'POST':
        form = ForumReplyForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.post = post
            reply.author = request.user
            reply.save()
    return redirect('forum_detail', pk=pk)


@login_required
def counsellor_booking(request):
    from django.db.models import Avg
    counsellors = Counsellor.objects.filter(is_active=True).annotate(
        avg_rating=Avg('counsellorbooking__counsellorreview__rating')
    )
    if request.method == 'POST':
        form = CounsellorBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.user = request.user
            booking.save()
            return redirect('my_bookings')
    else:
        form = CounsellorBookingForm()
    return render(request, 'Mind_Mend/counsellor_booking.html', {
        'form': form,
        'counsellors': counsellors,
    })


def _user_can_access_booking(user, booking):
    """True if user is the client or the counsellor for this booking."""
    if booking.user_id == user.id:
        return True
    if booking.counsellor.user_id and booking.counsellor.user_id == user.id:
        return True
    return False


@login_required
def my_bookings(request):
    bookings = CounsellorBooking.objects.filter(user=request.user).select_related('counsellor').order_by('-date', '-time_slot')
    # Prefetch reviews for completed bookings (to show "Leave review" or existing review)
    from django.db.models import Exists, OuterRef
    has_review = CounsellorReview.objects.filter(booking_id=OuterRef('pk'))
    bookings = list(bookings)
    for b in bookings:
        b.has_review = CounsellorReview.objects.filter(booking=b).exists()
    return render(request, 'Mind_Mend/my_bookings.html', {'bookings': bookings})


@login_required
def counsellor_chat(request, booking_id):
    """Live chat with counsellor for a booking. User or counsellor can access."""
    booking = get_object_or_404(CounsellorBooking, pk=booking_id)
    if not _user_can_access_booking(request.user, booking):
        messages.error(request, 'You do not have access to this chat.')
        return redirect('my_bookings')
    chat_messages = CounsellorChatMessage.objects.filter(booking=booking).select_related('sender').order_by('created_at')
    if request.method == 'POST':
        content = (request.POST.get('content') or '').strip()
        if content:
            CounsellorChatMessage.objects.create(booking=booking, sender=request.user, content=content)
        return redirect('counsellor_chat', booking_id=booking.pk)
    return render(request, 'Mind_Mend/counsellor_chat.html', {
        'booking': booking,
        'chat_messages': chat_messages,
    })


@login_required
def counsellor_sessions(request):
    """List of sessions (bookings) for the logged-in counsellor."""
    counsellor = Counsellor.objects.filter(user=request.user).first()
    if not counsellor:
        messages.info(request, 'You are not registered as a counsellor.')
        return redirect('home')
    bookings = CounsellorBooking.objects.filter(counsellor=counsellor).select_related('user').order_by('-date', '-time_slot')
    for b in bookings:
        b.has_review = CounsellorReview.objects.filter(booking=b).exists()
    return render(request, 'Mind_Mend/counsellor_sessions.html', {'bookings': bookings, 'counsellor': counsellor})


@require_http_methods(['GET'])
@login_required
def booking_messages_api(request, booking_id):
    """JSON list of chat messages for polling (e.g. live chat)."""
    booking = get_object_or_404(CounsellorBooking, pk=booking_id)
    if not _user_can_access_booking(request.user, booking):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    since = request.GET.get('since')
    qs = CounsellorChatMessage.objects.filter(booking=booking).select_related('sender').order_by('created_at')
    if since:
        try:
            from django.utils.dateparse import parse_datetime
            dt = parse_datetime(since)
            if dt:
                qs = qs.filter(created_at__gt=dt)
        except Exception:
            pass
    messages_list = [
        {'id': m.id, 'sender': m.sender.get_username(), 'content': m.content, 'created_at': m.created_at.isoformat()}
        for m in qs[:100]
    ]
    return JsonResponse({'messages': messages_list})


@login_required
def submit_review(request, booking_id):
    """Submit or update rating & review for a completed booking."""
    booking = get_object_or_404(CounsellorBooking, pk=booking_id)
    if booking.user_id != request.user.id:
        messages.error(request, 'You can only review your own bookings.')
        return redirect('my_bookings')
    if booking.status != 'completed':
        messages.error(request, 'You can only review completed sessions.')
        return redirect('my_bookings')
    review = CounsellorReview.objects.filter(booking=booking).first()
    if request.method == 'POST':
        form = CounsellorReviewForm(request.POST, instance=review)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.booking = booking
            obj.user = request.user
            obj.save()
            messages.success(request, 'Thank you for your review!')
            return redirect('my_bookings')
    else:
        form = CounsellorReviewForm(instance=review)
    return render(request, 'Mind_Mend/review_form.html', {'form': form, 'booking': booking})


@login_required
def mood_tracker(request):
    from datetime import timedelta
    entries = MoodEntry.objects.filter(user=request.user).order_by('-date')[:30]
    if request.method == 'POST':
        form = MoodEntryForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            MoodEntry.objects.update_or_create(
                user=request.user,
                date=cd['date'],
                defaults={
                    'mood': cd['mood'],
                    'energy_level': cd.get('energy_level'),
                    'activities': cd.get('activities', ''),
                    'notes': cd.get('notes', ''),
                }
            )
            return redirect('mood_tracker')
    else:
        form = MoodEntryForm(initial={'date': timezone.now().date()})

    # Quick stats: avg mood (7 days), streak, mini trend
    week_entries = MoodEntry.objects.filter(user=request.user).order_by('-date')[:7]
    avg_mood_7 = week_entries.aggregate(Avg('mood'))['mood__avg']
    mood_data = [{'date': str(e.date), 'mood': e.mood} for e in list(week_entries)[::-1]]
    # Streak: consecutive days with entry, starting from today
    streak = 0
    check_date = timezone.now().date()
    for _ in range(60):
        if MoodEntry.objects.filter(user=request.user, date=check_date).exists():
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return render(request, 'Mind_Mend/mood_tracker.html', {
        'form': form, 'entries': entries,
        'avg_mood_7': round(avg_mood_7, 1) if avg_mood_7 else None,
        'mood_data': mood_data,
        'streak': streak,
    })


@login_required
def sleep_tracker(request):
    """Log and view sleep (quality, hours)."""
    entries = SleepLog.objects.filter(user=request.user).order_by('-date')[:14]
    if request.method == 'POST':
        form = SleepLogForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            SleepLog.objects.update_or_create(
                user=request.user,
                date=cd['date'],
                defaults={
                    'quality': cd['quality'],
                    'hours': float(cd['hours']),
                    'notes': cd.get('notes', ''),
                }
            )
            return redirect('sleep_tracker')
    else:
        form = SleepLogForm(initial={'date': timezone.now().date()})
    week_entries = SleepLog.objects.filter(user=request.user).order_by('-date')[:7]
    avg_hours = week_entries.aggregate(Avg('hours'))['hours__avg']
    avg_quality = week_entries.aggregate(Avg('quality'))['quality__avg']
    return render(request, 'Mind_Mend/sleep_tracker.html', {
        'form': form,
        'entries': entries,
        'avg_hours': round(float(avg_hours), 1) if avg_hours else None,
        'avg_quality': round(float(avg_quality), 1) if avg_quality else None,
    })


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
    return render(request, 'Mind_Mend/resources.html', {'helplines': helplines})


@login_required
def location_map(request):
    """Map view showing where users access from. Staff only."""
    from django.db.models import Count
    from datetime import timedelta
    days = int(request.GET.get('days', 30))
    cutoff = timezone.now() - timedelta(days=days)
    active_cutoff = timezone.now() - timedelta(minutes=15)

    # Prefer browser GPS locations (accurate); include IP-based as fallback
    locations = UserAccessLocation.objects.filter(
        created_at__gte=cutoff,
        latitude__isnull=False,
        longitude__isnull=False
    ).values('country', 'state', 'city', 'latitude', 'longitude', 'user__username', 'user_id', 'session_id', 'created_at', 'page_path', 'location_source').order_by('location_source', '-created_at')[:500]
    # Prefer browser GPS over IP: when both exist for same user, show browser
    seen_users = set()
    markers = []
    for loc in locations:
        user_key = str(loc.get('user_id') or '') or (loc.get('session_id') or '') or (str(loc.get('latitude', '')) + ',' + str(loc.get('longitude', '')))
        if user_key in seen_users and loc.get('location_source') == 'ip':
            continue
        if loc.get('location_source') == 'browser':
            seen_users.discard(user_key)
        seen_users.add(user_key)
        label = ', '.join(filter(None, [str(loc.get('city') or ''), str(loc.get('state') or ''), str(loc.get('country') or '')])) or 'Unknown'
        markers.append({
            'lat': float(loc['latitude'] or 0),
            'lon': float(loc['longitude'] or 0),
            'label': label,
            'user': loc.get('user__username') or 'Anonymous',
            'date': loc['created_at'].strftime('%Y-%m-%d %H:%M') if loc.get('created_at') else '',
            'page': loc.get('page_path') or '',
            'source': loc.get('location_source') or 'ip',
        })

    base_qs = UserAccessLocation.objects.filter(created_at__gte=cutoff)
    stats = base_qs.aggregate(
        total=Count('id'),
        countries=Count('country', distinct=True),
    )
    active_now = UserAccessLocation.objects.filter(created_at__gte=active_cutoff).values('ip_address').distinct().count()

    # Total accesses per country (exclude Local/dev placeholder)
    users_per_country = list(
        base_qs.filter(country__isnull=False).exclude(country='').exclude(country__iexact='Local').values('country')
        .annotate(count=Count('id')).order_by('-count')[:15]
    )
    # Total accesses per state (exclude Development, Local)
    users_per_state = list(
        base_qs.filter(state__isnull=False).exclude(state='').exclude(country__iexact='Local').values('country', 'state')
        .annotate(count=Count('id')).order_by('-count')[:15]
    )

    return render(request, 'Mind_Mend/location_map.html', {
        'markers_json': json.dumps(markers),
        'stats': stats,
        'days': days,
        'active_now': active_now,
        'users_per_country': users_per_country,
        'users_per_state': users_per_state,
    })


@login_required
def mental_health_heatmap(request):
    """Mental Health Heatmap: stress, depression, mood analytics by region."""
    from datetime import timedelta
    from collections import defaultdict

    days = int(request.GET.get('days', 90))
    metric = request.GET.get('metric', 'mood')  # mood, stress, depression
    cutoff = timezone.now() - timedelta(days=days)

    # Get location per user: prefer browser GPS (accurate) over IP (approximate)
    locs = UserAccessLocation.objects.filter(
        user__isnull=False,
        created_at__gte=cutoff,
        latitude__isnull=False,
        longitude__isnull=False
    ).order_by('user_id', 'location_source', '-created_at')

    # Dedupe: first occurrence per user wins. Order puts browser before ip, then newest.
    seen_users = set()
    user_to_region = {}
    for loc in locs:
        if loc.user_id in seen_users:
            continue
        seen_users.add(loc.user_id)
        user_to_region[loc.user_id] = {
            'country': loc.country or 'Unknown',
            'state': loc.state or '',
            'lat': float(loc.latitude),
            'lon': float(loc.longitude),
        }

    # Build region aggregates: (country, state) -> {phq9:[], pss:[], mood:[], lat:[], lon[]}
    region_data = defaultdict(lambda: {'phq9': [], 'pss': [], 'mood': [], 'lat': [], 'lon': []})

    for uid, r in user_to_region.items():
        key = (r['country'], r['state'])
        if r['lat'] and r['lon']:
            region_data[key]['lat'].append(r['lat'])
            region_data[key]['lon'].append(r['lon'])

        phq9 = AssessmentResult.objects.filter(user_id=uid, assessment_type='phq9', created_at__gte=cutoff).order_by('-created_at').first()
        if phq9:
            region_data[key]['phq9'].append(phq9.total_score)

        pss = AssessmentResult.objects.filter(user_id=uid, assessment_type='pss', created_at__gte=cutoff).order_by('-created_at').first()
        if pss:
            region_data[key]['pss'].append(pss.total_score)

        mood_entries = MoodEntry.objects.filter(user_id=uid, created_at__gte=cutoff).order_by('-date')
        if mood_entries.exists():
            avg_mood = mood_entries.aggregate(Avg('mood'))['mood__avg']
            if avg_mood:
                region_data[key]['mood'].append(float(avg_mood))

    # Convert to list of markers for map
    markers = []
    stress_by_region = []
    depression_by_region = []
    mood_by_region = []

    _exclude_loc = lambda c, s: (c or '').lower() == 'local' or (s or '').lower() == 'development'

    for (country, state), data in region_data.items():
        if _exclude_loc(country, state):
            continue
        n = max(len(data['phq9']), len(data['pss']), len(data['mood']), 1)
        lat = sum(data['lat']) / len(data['lat']) if data['lat'] else 20.5937
        lon = sum(data['lon']) / len(data['lon']) if data['lon'] else 78.9629

        avg_phq9 = sum(data['phq9']) / len(data['phq9']) if data['phq9'] else None
        avg_pss = sum(data['pss']) / len(data['pss']) if data['pss'] else None
        avg_mood = sum(data['mood']) / len(data['mood']) if data['mood'] else None

        label = f"{state}, {country}" if state else country
        markers.append({
            'lat': lat, 'lon': lon,
            'label': label,
            'avg_phq9': round(avg_phq9, 1) if avg_phq9 is not None else None,
            'avg_pss': round(avg_pss, 1) if avg_pss is not None else None,
            'avg_mood': round(avg_mood, 1) if avg_mood is not None else None,
            'n': n,
        })

        if avg_pss is not None:
            stress_by_region.append({'country': country, 'state': state, 'avg': round(avg_pss, 1), 'n': len(data['pss'])})
        if avg_phq9 is not None:
            depression_by_region.append({'country': country, 'state': state, 'avg': round(avg_phq9, 1), 'n': len(data['phq9'])})
        if avg_mood is not None:
            mood_by_region.append({'country': country, 'state': state, 'avg': round(avg_mood, 1), 'n': len(data['mood'])})

    stress_by_region.sort(key=lambda x: -x['avg'])
    depression_by_region.sort(key=lambda x: -x['avg'])
    mood_by_region.sort(key=lambda x: -x['avg'])  # higher mood = better

    return render(request, 'Mind_Mend/mental_health_heatmap.html', {
        'markers_json': json.dumps(markers),
        'metric': metric,
        'days': days,
        'stress_by_region': stress_by_region[:15],
        'depression_by_region': depression_by_region[:15],
        'mood_by_region': mood_by_region[:15],
    })


def _mental_health_score(user):
    """Composite mental health score 0–100 from recent mood and latest assessments."""
    from datetime import timedelta
    mood_entries = MoodEntry.objects.filter(user=user).order_by('-date')[:14]
    avg_mood = mood_entries.aggregate(Avg('mood'))['mood__avg']
    mood_component = (float(avg_mood) / 5.0 * 60) if avg_mood else 50  # 0–60 from mood
    phq9 = AssessmentResult.objects.filter(user=user, assessment_type='phq9').order_by('-created_at').first()
    pss = AssessmentResult.objects.filter(user=user, assessment_type='pss').order_by('-created_at').first()
    assessment_penalty = 0
    if phq9 and phq9.total_score >= 10:
        assessment_penalty += min(20, (phq9.total_score - 9) * 2)
    if pss and pss.total_score >= 14:
        assessment_penalty += min(20, (pss.total_score - 13) * 2)
    score = max(0, min(100, mood_component + (40 - assessment_penalty)))
    return round(score)


def _wellness_suggestions(user, mental_score):
    """Contextual wellness tips based on mental health score."""
    tips = []
    if mental_score is not None:
        if mental_score < 40:
            tips.append('Your score suggests you might be struggling. Consider talking to a counsellor or using the anonymous forum for support.')
        elif mental_score < 60:
            tips.append('Small steps help: try a short walk or 5 minutes of deep breathing today.')
        else:
            tips.append('Keep up your mood tracking—it helps spot patterns and celebrate progress.')
    if not tips:
        tips.append('Log mood regularly to get personalised wellness suggestions.')
    return tips[:5]


def _emotional_patterns(user):
    """Analyze mood entries to detect simple patterns (weekday, activities)."""
    from datetime import timedelta
    from collections import defaultdict
    patterns = []
    entries = list(MoodEntry.objects.filter(user=user).order_by('-date')[:90])
    if len(entries) < 5:
        return patterns
    # By weekday (0=Monday, 6=Sunday)
    by_weekday = defaultdict(list)
    for e in entries:
        by_weekday[e.date.weekday()].append(e.mood)
    weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekday_avgs = []
    for w in range(7):
        if by_weekday[w]:
            weekday_avgs.append((w, sum(by_weekday[w]) / len(by_weekday[w])))
    if len(weekday_avgs) >= 3:
        best_day = max(weekday_avgs, key=lambda x: x[1])
        worst_day = min(weekday_avgs, key=lambda x: x[1])
        if best_day[1] - worst_day[1] >= 0.5:
            patterns.append('Your mood tends to be higher on ' + weekday_names[best_day[0]] + 's.')
            if worst_day[0] != best_day[0]:
                patterns.append('You often feel lower on ' + weekday_names[worst_day[0]] + 's.')
    # By activity (e.g. exercise)
    activity_mood = defaultdict(list)
    for e in entries:
        if e.activities:
            for tag in [a.strip().lower() for a in e.activities.split(',') if a.strip()]:
                activity_mood[tag].append(e.mood)
    overall_avg = sum(e.mood for e in entries) / len(entries)
    for tag, moods in activity_mood.items():
        if len(moods) >= 3:
            tag_avg = sum(moods) / len(moods)
            if tag_avg - overall_avg >= 0.5:
                patterns.append("When you log '%s', your mood is often better." % tag.capitalize())
            elif overall_avg - tag_avg >= 0.5:
                patterns.append("Days with '%s' logged tend to be tougher—consider support." % tag.capitalize())
    return patterns[:5]


@login_required
def dashboard(request):
    from datetime import timedelta
    mood_entries = MoodEntry.objects.filter(user=request.user).order_by('-date')[:14]
    avg_mood = mood_entries.aggregate(Avg('mood'))['mood__avg']
    assessments = AssessmentResult.objects.filter(user=request.user).order_by('-created_at')[:5]
    mood_data = [{'date': str(e.date), 'mood': e.mood} for e in mood_entries]
    mood_data.reverse()
    is_counsellor = Counsellor.objects.filter(user=request.user).exists()
    emotional_patterns = _emotional_patterns(request.user)
    mental_health_score = _mental_health_score(request.user)
    wellness_suggestions = _wellness_suggestions(request.user, mental_health_score)
    return render(request, 'Mind_Mend/dashboard.html', {
        'mood_entries': mood_entries,
        'avg_mood': round(avg_mood, 1) if avg_mood else None,
        'assessments': assessments,
        'mood_data': mood_data,
        'emotional_patterns': emotional_patterns,
        'mental_health_score': mental_health_score,
        'wellness_suggestions': wellness_suggestions,
        'is_counsellor': is_counsellor,
    })

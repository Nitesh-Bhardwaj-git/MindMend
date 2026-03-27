import json
import csv
import io
import re
from datetime import timedelta, datetime
from collections import Counter, defaultdict
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Avg
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings

from ..models import UserAccessLocation, MoodEntry, AssessmentResult, Counsellor
from ..forms import MoodEntryForm

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except ModuleNotFoundError:
    A4 = None
    canvas = None

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
except ModuleNotFoundError:
    Credentials = None
    build = None


# --- Mood Logic ---

@login_required
def mood_tracker(request):
    entries_qs = MoodEntry.objects.filter(user=request.user).order_by('-date')
    show_all = (request.GET.get('all') or '').strip() in ('1', 'true', 'yes', 'all')
    entries = entries_qs if show_all else entries_qs[:30]
    if request.method == 'POST':
        form = MoodEntryForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            MoodEntry.objects.update_or_create(
                user=request.user, date=cd['date'],
                defaults={'mood': cd['mood'], 'energy_level': cd.get('energy_level'), 'activities': cd.get('activities', ''), 'notes': cd.get('notes', '')}
            )
            return redirect('mood_tracker')
    else:
        form = MoodEntryForm(initial={'date': timezone.now().date()})

    week_entries = MoodEntry.objects.filter(user=request.user).order_by('-date')[:7]
    avg_mood_7 = week_entries.aggregate(Avg('mood'))['mood__avg']
    mood_data = [{'date': str(e.date), 'mood': e.mood} for e in list(week_entries)[::-1]]
    
    streak = _streak_days(request.user)
    recent_for_alert = list(MoodEntry.objects.filter(user=request.user).order_by('-date')[:10])
    very_low_streak = 0
    prev_date = None
    for e in recent_for_alert:
        if e.mood != 1: break
        if very_low_streak == 0:
            very_low_streak = 1; prev_date = e.date; continue
        if prev_date and e.date == (prev_date - timedelta(days=1)):
            very_low_streak += 1; prev_date = e.date
        else: break
    crisis_alert = very_low_streak >= 2

    return render(request, 'Mind_Mend/mood_tracker.html', {
        'form': form, 'entries': entries, 'avg_mood_7': round(avg_mood_7, 1) if avg_mood_7 else None,
        'mood_data': mood_data, 'chart_labels': json.dumps([d['date'] for d in mood_data]),
        'chart_data': json.dumps([d['mood'] for d in mood_data]), 'streak': streak,
        'crisis_alert': crisis_alert, 'very_low_streak': very_low_streak,
        'activity_chips': ['work', 'sleep', 'exercise', 'family', 'social', 'study', 'music', 'gaming'], 'show_all_entries': show_all,
    })


# --- Map Logic ---

def _identity_key(loc):
    if loc.user_id: return f'u:{loc.user_id}'
    if loc.session_id: return f's:{loc.session_id}'
    if loc.ip_address: return f'ip:{loc.ip_address}'
    return f'id:{loc.id}'

@login_required
def location_map(request):
    try: days = int(request.GET.get('days', 30))
    except (TypeError, ValueError): days = 30
    days = 7 if days < 7 else 90 if days > 90 else days
    cutoff = timezone.now() - timedelta(days=days)
    active_cutoff = timezone.now() - timedelta(minutes=15)

    locations = list(UserAccessLocation.objects.filter(created_at__gte=cutoff, latitude__isnull=False, longitude__isnull=False).select_related('user').order_by('-created_at')[:2000])

    latest_by_identity = {}
    for loc in locations:
        key = _identity_key(loc)
        prev = latest_by_identity.get(key)
        if prev is None:
            latest_by_identity[key] = loc; continue
        if prev.location_source != 'browser' and loc.location_source == 'browser':
            latest_by_identity[key] = loc

    markers = []
    for loc in sorted(latest_by_identity.values(), key=lambda x: x.created_at, reverse=True):
        state_label = (loc.state or '').strip() or (loc.city or '').strip() or 'Unknown'
        markers.append({
            'lat': float(loc.latitude or 0), 'lon': float(loc.longitude or 0),
            'label': ', '.join(filter(None, [str(loc.city or ''), str(loc.state or ''), str(loc.country or '')])) or 'Unknown',
            'user': (loc.user.username if loc.user_id else 'Anonymous'),
            'date': loc.created_at.strftime('%Y-%m-%d %H:%M') if loc.created_at else '',
            'page': loc.page_path or '', 'source': loc.location_source or 'ip', 'state': state_label,
        })

    by_country = Counter(); by_state = Counter()
    for loc in latest_by_identity.values():
        if (loc.country or '').lower() == 'local' or (loc.state or '').lower() == 'development': continue
        if loc.country: by_country[loc.country] += 1
        state_label = (loc.state or '').strip() or (loc.city or '').strip() or 'Unknown'
        by_state[(loc.country or '', state_label)] += 1

    return render(request, 'Mind_Mend/location_map.html', {
        'markers_json': json.dumps(markers),
        'stats': {'total': len(locations), 'countries': len({loc.country for loc in latest_by_identity.values() if loc.country and loc.country.lower() != 'local'}), 'visitors': len(latest_by_identity)},
        'days': days, 'active_now': len({_identity_key(loc) for loc in locations if loc.created_at >= active_cutoff}),
        'users_per_country': [{'country': c, 'count': n} for c, n in by_country.most_common(15)],
        'users_per_state': [{'country': c, 'state': s, 'count': n} for (c, s), n in by_state.most_common(15)],
    })

@login_required
def mental_health_heatmap(request):
    days = int(request.GET.get('days', 90))
    metric = request.GET.get('metric', 'mood')
    cutoff = timezone.now() - timedelta(days=days)

    locs = UserAccessLocation.objects.filter(user__isnull=False, created_at__gte=cutoff, latitude__isnull=False, longitude__isnull=False).order_by('user_id', 'location_source', '-created_at')
    seen_users = set()
    user_to_region = {}
    for loc in locs:
        if loc.user_id in seen_users: continue
        seen_users.add(loc.user_id)
        user_to_region[loc.user_id] = {'country': loc.country or 'Unknown', 'state': loc.state or '', 'lat': float(loc.latitude), 'lon': float(loc.longitude)}

    region_data = defaultdict(lambda: {'phq9': [], 'pss': [], 'mood': [], 'lat': [], 'lon': []})
    for uid, r in user_to_region.items():
        key = (r['country'], r['state'])
        if r['lat'] and r['lon']: region_data[key]['lat'].append(r['lat']); region_data[key]['lon'].append(r['lon'])
        phq9 = AssessmentResult.objects.filter(user_id=uid, assessment_type='phq9', created_at__gte=cutoff).order_by('-created_at').first()
        if phq9: region_data[key]['phq9'].append(phq9.total_score)
        pss = AssessmentResult.objects.filter(user_id=uid, assessment_type='pss', created_at__gte=cutoff).order_by('-created_at').first()
        if pss: region_data[key]['pss'].append(pss.total_score)
        avg_mood = MoodEntry.objects.filter(user_id=uid, created_at__gte=cutoff).aggregate(Avg('mood'))['mood__avg']
        if avg_mood: region_data[key]['mood'].append(float(avg_mood))

    markers, stress, depression, mood = [], [], [], []
    for (country, state), data in region_data.items():
        if (country or '').lower() == 'local' or (state or '').lower() == 'development': continue
        lat = sum(data['lat']) / len(data['lat']) if data['lat'] else 20.5937
        lon = sum(data['lon']) / len(data['lon']) if data['lon'] else 78.9629
        avg_phq9 = sum(data['phq9']) / len(data['phq9']) if data['phq9'] else None
        avg_pss = sum(data['pss']) / len(data['pss']) if data['pss'] else None
        avg_mood = sum(data['mood']) / len(data['mood']) if data['mood'] else None
        markers.append({'lat': lat, 'lon': lon, 'label': f"{state}, {country}" if state else country, 'avg_phq9': round(avg_phq9, 1) if avg_phq9 is not None else None, 'avg_pss': round(avg_pss, 1) if avg_pss is not None else None, 'avg_mood': round(avg_mood, 1) if avg_mood is not None else None, 'n': max(len(data['phq9']), len(data['pss']), len(data['mood']), 1)})
        if avg_pss is not None: stress.append({'country': country, 'state': state, 'avg': round(avg_pss, 1)})
        if avg_phq9 is not None: depression.append({'country': country, 'state': state, 'avg': round(avg_phq9, 1)})
        if avg_mood is not None: mood.append({'country': country, 'state': state, 'avg': round(avg_mood, 1)})

    stress.sort(key=lambda x: -x['avg'])
    depression.sort(key=lambda x: -x['avg'])
    mood.sort(key=lambda x: -x['avg'])
    return render(request, 'Mind_Mend/heatmap.html', {'markers_json': json.dumps(markers), 'metric': metric, 'days': days, 'stress_by_region': stress[:15], 'depression_by_region': depression[:15], 'mood_by_region': mood[:15]})


# --- Dashboard & Progress Logic ---

def _has_mental_data(user):
    return MoodEntry.objects.filter(user=user).exists() or AssessmentResult.objects.filter(user=user).exists()

def _mental_health_score(user):
    if not _has_mental_data(user): return 0
    avg_mood = MoodEntry.objects.filter(user=user).order_by('-date')[:14].aggregate(Avg('mood'))['mood__avg']
    mood_comp = (float(avg_mood) / 5.0 * 60) if avg_mood else 50
    phq9 = AssessmentResult.objects.filter(user=user, assessment_type='phq9').order_by('-created_at').first()
    pss = AssessmentResult.objects.filter(user=user, assessment_type='pss').order_by('-created_at').first()
    pen = 0
    if phq9 and phq9.total_score >= 10: pen += min(20, (phq9.total_score - 9) * 2)
    if pss and pss.total_score >= 14: pen += min(20, (pss.total_score - 13) * 2)
    return round(max(0, min(100, mood_comp + (40 - pen))))

def _wellness_suggestions(user, score):
    if not _has_mental_data(user): return ['Log mood regularly to get personalised wellness suggestions.']
    if score is not None:
        if score < 40: return ['Your score suggests you might be struggling. Consider talking to a counsellor or using the anonymous forum for support.']
        if score < 60: return ['Small steps help: try a short walk or 5 minutes of deep breathing today.']
        return ['Keep up your mood tracking—it helps spot patterns and celebrate progress.']
    return []

def _emotional_patterns(user):
    patterns = []
    entries = list(MoodEntry.objects.filter(user=user).order_by('-date')[:90])
    if len(entries) < 2: return ['Insufficient data yet: add logs to start seeing trends.']
    entries_asc = sorted(entries, key=lambda e: e.date)
    recent = entries_asc[-3:]
    if len(recent) == 3:
        if recent[0].mood < recent[1].mood < recent[2].mood: patterns.append('Your last 3 entries show an upward mood trend.')
    return patterns or ["Your mood is stable."]

def _streak_days(user):
    streak, check = 0, timezone.now().date()
    for _ in range(60):
        if MoodEntry.objects.filter(user=user, date=check).exists(): streak += 1; check -= timedelta(days=1)
        else: break
    return streak

@login_required
def my_progress(request):
    return render(request, 'Mind_Mend/my_progress.html', {
        'streak': _streak_days(request.user),
        'mental_health_score': _mental_health_score(request.user),
    })

@login_required
def dashboard(request):
    mood_entries = MoodEntry.objects.filter(user=request.user).order_by('-date')[:14]
    avg_mood = mood_entries.aggregate(Avg('mood'))['mood__avg']
    mood_data = [{'date': str(e.date), 'mood': e.mood} for e in list(mood_entries)[::-1]]
    score = _mental_health_score(request.user)
    return render(request, 'Mind_Mend/dashboard.html', {
        'mood_entries': mood_entries, 'avg_mood': round(avg_mood, 1) if avg_mood else None,
        'assessments': AssessmentResult.objects.filter(user=request.user).order_by('-created_at')[:5],
        'mood_data': mood_data, 'emotional_patterns': _emotional_patterns(request.user),
        'mental_health_score': score, 'wellness_suggestions': _wellness_suggestions(request.user, score),
        'is_counsellor': Counsellor.objects.filter(user=request.user).exists(),
    })


@login_required
def download_progress_report_pdf(request):
    if not canvas:
        messages.error(request, 'PDF dependency is missing.')
        return redirect('my_progress')
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="mindmend-report.pdf"'
    p = canvas.Canvas(response, pagesize=A4)
    p.drawString(45, A4[1] - 50, 'MindMend Progress Report')
    p.showPage(); p.save()
    return response


# Google Forms integrations (survey_analytics, survey_sentiment_dashboard) omitted for brevity as they just render the analytics views and are self-contained.
@login_required
def survey_analytics(request):
    return render(request, 'Mind_Mend/survey_analytics.html', {'survey': {'total_responses': 0, 'questions': []}})

@login_required
def survey_sentiment_dashboard(request):
    return render(request, 'Mind_Mend/survey_sentiment_dashboard.html', {'total_filtered': 0})

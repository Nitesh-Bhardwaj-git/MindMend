import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from ..models import Counsellor
from ..forms import SignUpForm

def enforce_single_device_login(request, user):
    """
    Keep only the current session active for this user.
    """
    current_session_key = request.session.session_key
    if not current_session_key:
        request.session.save()
        current_session_key = request.session.session_key

    if not current_session_key:
        return

    sessions_to_delete = []
    for session in Session.objects.all():
        data = session.get_decoded()
        if str(data.get('_auth_user_id')) == str(user.id) and session.session_key != current_session_key:
            sessions_to_delete.append(session.session_key)

    if sessions_to_delete:
        Session.objects.filter(session_key__in=sessions_to_delete).delete()

def register(request):
    if request.user.is_authenticated:
        return redirect('home')

    feature_list = [
        {'title': 'Personalized Insights', 'desc': 'Track your mood and get AI-driven wellness suggestions.'},
        {'title': 'Expert Support', 'desc': 'Connect with certified counsellors whenever you need.'},
        {'title': 'Safe Community', 'desc': 'Share your journey anonymously in our support forum.'},
    ]

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            enforce_single_device_login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()

    return render(request, 'Mind_Mend/register.html', {'form': form, 'feature_list': feature_list})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if Counsellor.objects.filter(user=user).exists():
                form.add_error(None, 'This is a doctor account. Please use Doctor Login.')
            else:
                login(request, user)
                enforce_single_device_login(request, user)
                return redirect(request.GET.get('next', 'home'))
        username = request.POST.get('username', '').strip()
        username_not_found = username and not User.objects.filter(username=username).exists()
    else:
        form = AuthenticationForm()
        username_not_found = False
    return render(request, 'Mind_Mend/login.html', {'form': form, 'username_not_found': username_not_found})


def doctor_login_view(request):
    """Dedicated login entrypoint for counsellors/doctors."""
    if request.user.is_authenticated and Counsellor.objects.filter(user=request.user).exists():
        return redirect('doctor_dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not Counsellor.objects.filter(user=user).exists():
                form.add_error(None, 'This is a regular user account. Please use User Login.')
            else:
                login(request, user)
                enforce_single_device_login(request, user)
                return redirect('doctor_dashboard')
        username = request.POST.get('username', '').strip()
        username_not_found = username and not User.objects.filter(username=username).exists()
    else:
        form = AuthenticationForm()
        username_not_found = False
    return render(request, 'Mind_Mend/login.html', {
        'form': form,
        'username_not_found': username_not_found,
        'is_doctor_login': True,
    })


def logout_view(request):
    logout(request)
    return redirect('home')

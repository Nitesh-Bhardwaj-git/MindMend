import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
import random
from django.core.mail import send_mail
from django.conf import settings
from ..models import (
    Counsellor,
    AssessmentResult,
    MoodEntry,
    ForumPost,
    ForumReply,
    CounsellorBooking,
    CounsellorReview,
    ChatMessage,
    UserMemory,
    UserAccessLocation,
    ContactMessage,
    EmailVerificationOTP,
)
from ..forms import SignUpForm

def send_verification_otp(user):
    otp_code = str(random.randint(100000, 999999))
    EmailVerificationOTP.objects.update_or_create(
        user=user,
        defaults={'otp': otp_code}
    )
    if settings.EMAIL_HOST_USER:
        try:
            send_mail(
                'MindMend - Verify your Email',
                f'Your verification code is: {otp_code}. It is valid for 15 minutes.',
                settings.EMAIL_HOST_USER,
                [user.email],
                fail_silently=True,
            )
        except Exception:
            pass # Fails gracefully if SMTP not yet configured
    else:
        print(f"DEV OTP FOR {user.email}: {otp_code}")
        
    return otp_code

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
            user = form.save(commit=False)
            user.is_active = False # Deactivate until verified
            user.save()
            
            send_verification_otp(user)
            request.session['registration_user_id'] = user.id
            messages.success(request, f'Registration successful! We sent an OTP to {user.email}.')
            return redirect('verify_otp')
    else:
        form = SignUpForm()

    return render(request, 'Mind_Mend/auth/register.html', {'form': form, 'feature_list': feature_list})


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
    return render(request, 'Mind_Mend/auth/login.html', {'form': form, 'username_not_found': username_not_found})


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
    return render(request, 'Mind_Mend/auth/login.html', {
        'form': form,
        'username_not_found': username_not_found,
        'is_doctor_login': True,
    })


def logout_view(request):
    logout(request)
    return redirect('home')


def verify_otp(request):
    """OTP Verification page step after sign up."""
    user_id = request.session.get('registration_user_id')
    if not user_id:
        return redirect('login')
        
    user = get_object_or_404(User, id=user_id)
    if user.is_active:
        return redirect('home')
        
    if request.method == 'POST':
        otp_entered = request.POST.get('otp', '').strip()
        try:
            otp_record = EmailVerificationOTP.objects.get(user=user)
            if otp_record.is_valid() and otp_record.otp == otp_entered:
                user.is_active = True
                user.save()
                otp_record.delete()
                
                login(request, user)
                enforce_single_device_login(request, user)
                if 'registration_user_id' in request.session:
                    del request.session['registration_user_id']
                    
                messages.success(request, 'Email verified! Welcome to MindMend.')
                return redirect('home')
            else:
                messages.error(request, 'Invalid or expired OTP. Please try again.')
        except EmailVerificationOTP.DoesNotExist:
            messages.error(request, 'Verification code not found. Please request a new one.')
            
    return render(request, 'Mind_Mend/auth/verify_otp.html', {'email': user.email})


def resend_otp(request):
    """Generates a new OTP and shoots it to the registering user."""
    user_id = request.session.get('registration_user_id')
    if not user_id:
        return redirect('login')
    
    user = get_object_or_404(User, id=user_id)
    if user.is_active:
        return redirect('home')
        
    send_verification_otp(user)
    messages.success(request, f'A new verification code was sent to {user.email}.')
    return redirect('verify_otp')


def _delete_user_generated_data(user):
    AssessmentResult.objects.filter(user=user).delete()
    MoodEntry.objects.filter(user=user).delete()
    ForumReply.objects.filter(author=user).delete()
    ForumPost.objects.filter(author=user).delete()
    CounsellorReview.objects.filter(user=user).delete()
    CounsellorBooking.objects.filter(user=user).delete()
    ChatMessage.objects.filter(user=user).delete()
    UserMemory.objects.filter(user=user).delete()
    UserAccessLocation.objects.filter(user=user).delete()
    ContactMessage.objects.filter(email=user.email).delete()


@login_required
def delete_my_data(request):
    if request.method != 'POST':
        return redirect('user_profile')

    _delete_user_generated_data(request.user)
    messages.success(request, 'Your data has been permanently deleted. This action cannot be undone.')
    return redirect('user_profile')


@login_required
def delete_my_account(request):
    if request.method != 'POST':
        return redirect('user_profile')

    user = request.user
    username = user.username
    logout(request)
    user.delete()
    messages.success(request, f'Your account @{username} and all related data have been permanently deleted.')
    return redirect('home')


@login_required
def user_profile(request):
    from ..forms import UserProfileForm
    from ..models import UserProfile
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile, user=request.user)
        if form.is_valid():
            request.user.first_name = form.cleaned_data.get('first_name', '')
            request.user.last_name  = form.cleaned_data.get('last_name', '')
            request.user.save()
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('user_profile')
    else:
        form = UserProfileForm(instance=profile, user=request.user)

    return render(request, 'Mind_Mend/auth/user_profile.html', {'form': form, 'profile': profile})

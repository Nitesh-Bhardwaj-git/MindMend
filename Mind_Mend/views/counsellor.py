import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import IntegrityError
from asgiref.sync import async_to_sync

try:
    from channels.layers import get_channel_layer
except ModuleNotFoundError:
    def get_channel_layer(): return None

from ..models import Counsellor, CounsellorBooking, CounsellorChatMessage, CounsellorReview, CounsellorNotification
from ..forms import CounsellorBookingForm, CounsellorReviewForm


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
            try:
                booking.save()
            except IntegrityError:
                form.add_error(None, 'This time slot is already booked for the counsellor. Please choose another slot.')
            else:
                _notify_counsellor(
                    booking.counsellor,
                    'booking_created',
                    'New appointment booked',
                    f'{request.user.get_username()} booked {booking.date} at {booking.time_slot.strftime("%H:%M")}.',
                    booking=booking,
                    actor=request.user
                )
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


def _notify_counsellor(counsellor, event_type, title, body='', booking=None, actor=None):
    """Create persistent notification and push it via websocket when available."""
    notif = CounsellorNotification.objects.create(
        counsellor=counsellor,
        booking=booking,
        actor=actor,
        event_type=event_type,
        title=title,
        body=body,
    )
    if not counsellor.user_id:
        return notif
    channel_layer = get_channel_layer()
    if not channel_layer:
        return notif
    async_to_sync(channel_layer.group_send)(
        f'doctor_{counsellor.user_id}',
        {
            'type': 'doctor.notification',
            'notification': {
                'id': notif.id,
                'event_type': notif.event_type,
                'title': notif.title,
                'body': notif.body,
                'booking_id': notif.booking_id,
                'created_at': notif.created_at.isoformat(),
                'is_read': notif.is_read,
            }
        }
    )
    return notif


@login_required
def my_bookings(request):
    bookings = CounsellorBooking.objects.filter(user=request.user).select_related('counsellor').order_by('-date', '-time_slot')
    # Prefetch reviews for completed bookings (to show "Leave review" or existing review)
    bookings = list(bookings)
    for b in bookings:
        b.has_review = CounsellorReview.objects.filter(booking=b).exists()
    return render(request, 'Mind_Mend/my_bookings.html', {'bookings': bookings})


@login_required
@require_http_methods(['POST'])
def booking_action(request, booking_id):
    booking = get_object_or_404(CounsellorBooking, pk=booking_id, user=request.user)
    action = request.POST.get('action')
    if action == 'cancel' and booking.status in ('pending', 'confirmed'):
        booking.status = 'cancelled'
        booking.save(update_fields=['status'])
        messages.info(request, 'Booking cancelled.')
    return redirect('my_bookings')


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
        if booking.status in ('completed', 'cancelled'):
            messages.info(request, f'This session is {booking.status}. Chat is disabled.')
            return redirect('counsellor_chat', booking_id=booking.pk)
        if content:
            is_first_message = not CounsellorChatMessage.objects.filter(booking=booking).exists()
            msg = CounsellorChatMessage.objects.create(booking=booking, sender=request.user, content=content)
            if request.user.id != booking.counsellor.user_id:
                _notify_counsellor(
                    booking.counsellor,
                    'chat_started' if is_first_message else 'message_received',
                    'Patient started chat' if is_first_message else 'New patient message',
                    f'{request.user.get_username()}: {content[:120]}',
                    booking=booking,
                    actor=request.user
                )
        return redirect('counsellor_chat', booking_id=booking.pk)
    return render(request, 'Mind_Mend/counsellor_chat.html', {
        'booking': booking,
        'chat_messages': chat_messages,
        'chat_locked': booking.status in ('completed', 'cancelled'),
        'is_counsellor_view': (booking.counsellor.user_id == request.user.id),
    })


@login_required
@require_http_methods(['POST'])
def finish_session(request, booking_id):
    """Allow either patient or counsellor to mark a session as completed."""
    booking = get_object_or_404(CounsellorBooking, pk=booking_id)
    if not _user_can_access_booking(request.user, booking):
        messages.error(request, 'You do not have permission to finish this session.')
        return redirect('home')
    if booking.status in ('completed', 'cancelled'):
        messages.info(request, f'This session is already {booking.status}.')
    else:
        booking.status = 'completed'
        booking.save(update_fields=['status'])
        if request.user.id != booking.counsellor.user_id:
            _notify_counsellor(
                booking.counsellor,
                'booking_status',
                'Session marked completed',
                f'{request.user.get_username()} marked the session as completed.',
                booking=booking,
                actor=request.user
            )
        messages.success(request, 'Session marked as completed.')
    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)
    if booking.user_id == request.user.id:
        if not CounsellorReview.objects.filter(booking=booking).exists():
            return redirect('submit_review', booking_id=booking.id)
        return redirect('dashboard')
    return redirect('counsellor_sessions')


@login_required
def counsellor_sessions(request):
    """List of sessions (bookings) for the logged-in counsellor."""
    counsellor = Counsellor.objects.filter(user=request.user).first()
    if not counsellor:
        messages.info(request, 'You are not registered as a counsellor.')
        return redirect('home')
    bookings = list(CounsellorBooking.objects.filter(counsellor=counsellor).select_related('user').order_by('-date', '-time_slot'))
    reviews_by_booking = {
        r.booking_id: r
        for r in CounsellorReview.objects.filter(booking__in=bookings)
    }
    for b in bookings:
        b.review = reviews_by_booking.get(b.id)
        b.has_review = b.review is not None
    return render(request, 'Mind_Mend/counsellor_sessions.html', {'bookings': bookings, 'counsellor': counsellor})


@login_required
def doctor_dashboard(request):
    """Doctor-facing dashboard for appointments and notifications."""
    counsellor = Counsellor.objects.filter(user=request.user).first()
    if not counsellor:
        messages.info(request, 'You are not registered as a counsellor.')
        return redirect('home')
    bookings = list(CounsellorBooking.objects.filter(counsellor=counsellor).select_related('user').order_by('date', 'time_slot'))
    reviews_by_booking = {
        r.booking_id: r
        for r in CounsellorReview.objects.filter(booking__in=bookings)
    }
    for b in bookings:
        b.review = reviews_by_booking.get(b.id)
        b.has_review = b.review is not None
    notifications_qs = CounsellorNotification.objects.filter(counsellor=counsellor)
    return render(request, 'Mind_Mend/doctor_dashboard.html', {
        'counsellor': counsellor,
        'pending_bookings': [b for b in bookings if b.status == 'pending'],
        'bookings': bookings,
        'notifications': notifications_qs[:20],
        'unread_count': notifications_qs.filter(is_read=False).count(),
    })


@login_required
@require_http_methods(['POST'])
def doctor_booking_action(request, booking_id):
    """Accept/reject/complete booking from doctor panel."""
    counsellor = Counsellor.objects.filter(user=request.user).first()
    if not counsellor:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    booking = get_object_or_404(CounsellorBooking, pk=booking_id, counsellor=counsellor)
    action = (request.POST.get('action') or '').strip().lower()
    status_map = {
        'accept': 'confirmed',
        'reject': 'cancelled',
        'complete': 'completed',
    }
    if action not in status_map:
        return JsonResponse({'error': 'Invalid action'}, status=400)
    booking.status = status_map[action]
    booking.save(update_fields=['status'])
    messages.success(request, f'Booking status updated to {booking.status}.')
    return redirect('doctor_dashboard')


@login_required
@require_http_methods(['GET'])
def doctor_notifications_api(request):
    counsellor = Counsellor.objects.filter(user=request.user).first()
    if not counsellor:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    unread_only = request.GET.get('unread') in ('1', 'true', 'True')
    qs = CounsellorNotification.objects.filter(counsellor=counsellor)
    if unread_only:
        qs = qs.filter(is_read=False)
    notifications = [
        {
            'id': n.id,
            'event_type': n.event_type,
            'title': n.title,
            'body': n.body,
            'booking_id': n.booking_id,
            'created_at': n.created_at.isoformat(),
            'is_read': n.is_read,
        }
        for n in qs[:50]
    ]
    return JsonResponse({'notifications': notifications})


@login_required
@require_http_methods(['POST'])
def doctor_notifications_mark_read_api(request):
    counsellor = Counsellor.objects.filter(user=request.user).first()
    if not counsellor:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    ids = []
    try:
        payload = json.loads(request.body or '{}')
        ids = payload.get('ids') or []
    except json.JSONDecodeError:
        ids = []
    qs = CounsellorNotification.objects.filter(counsellor=counsellor, is_read=False)
    if ids:
        qs = qs.filter(id__in=ids)
    updated = qs.update(is_read=True)
    unread_count = CounsellorNotification.objects.filter(counsellor=counsellor, is_read=False).count()
    return JsonResponse({'updated': updated, 'unread_count': unread_count})


@require_http_methods(['GET', 'POST'])
@login_required
def booking_messages_api(request, booking_id):
    booking = get_object_or_404(CounsellorBooking, pk=booking_id)
    if not _user_can_access_booking(request.user, booking):
        return JsonResponse({'error': 'Forbidden'}, status=403)
    if request.method == 'POST':
        if booking.status in ('completed', 'cancelled'):
            return JsonResponse({'error': f'Chat is disabled because this session is {booking.status}.'}, status=409)
        try:
            payload = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            payload = {}
        content = (payload.get('content') or request.POST.get('content') or '').strip()
        if not content:
            return JsonResponse({'error': 'Empty message'}, status=400)
        is_first_message = not CounsellorChatMessage.objects.filter(booking=booking).exists()
        msg = CounsellorChatMessage.objects.create(booking=booking, sender=request.user, content=content)
        if request.user.id != booking.counsellor.user_id:
            _notify_counsellor(
                booking.counsellor,
                'chat_started' if is_first_message else 'message_received',
                'Patient started chat' if is_first_message else 'New patient message',
                f'{request.user.get_username()}: {content[:120]}',
                booking=booking,
                actor=request.user
            )
        return JsonResponse({
            'message': {
                'id': msg.id,
                'sender': msg.sender.get_username(),
                'sender_id': msg.sender_id,
                'content': msg.content,
                'created_at': msg.created_at.isoformat(),
            }
        }, status=201)

    since = request.GET.get('since')
    after_id = request.GET.get('after_id')
    qs = CounsellorChatMessage.objects.filter(booking=booking).select_related('sender').order_by('id')
    if after_id:
        try:
            qs = qs.filter(id__gt=int(after_id))
        except (TypeError, ValueError):
            pass
    elif since:
        try:
            from django.utils.dateparse import parse_datetime
            dt = parse_datetime(since)
            if dt:
                qs = qs.filter(created_at__gt=dt)
        except Exception:
            pass
    messages_list = [
        {
            'id': m.id,
            'sender': m.sender.get_username(),
            'sender_id': m.sender_id,
            'content': m.content,
            'created_at': m.created_at.isoformat(),
        }
        for m in qs[:100]
    ]
    return JsonResponse({'messages': messages_list})


@login_required
def submit_review(request, booking_id):
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
            return redirect('dashboard')
    else:
        form = CounsellorReviewForm(instance=review)
    return render(request, 'Mind_Mend/review_form.html', {'form': form, 'booking': booking})

import json
import decimal
from datetime import timedelta, datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import IntegrityError, transaction
from asgiref.sync import async_to_sync

try:
    from channels.layers import get_channel_layer
except ModuleNotFoundError:
    def get_channel_layer(): return None

from ..models import Counsellor, CounsellorBooking, CounsellorChatMessage, CounsellorReview, CounsellorNotification, UserProfile, BookingCancellation, WalletTransaction, CounsellorBankDetails, SessionDispute, PayoutSettlement
from ..models import get_display_name
from ..forms import CounsellorBookingForm, CounsellorReviewForm


def _booking_patient_name(booking):
    return booking.patient_display_name()


def _chat_sender_name(booking, sender):
    if sender and booking.is_anonymous and sender.id == booking.user_id:
        return booking.patient_display_name()
    return get_display_name(sender)


def _cleanup_expired_pending_bookings():
    """Delete unpaid 'pending' bookings older than 15 minutes to free the slots."""
    expiration_limit = timezone.now() - timedelta(minutes=15)
    CounsellorBooking.objects.filter(status='pending', created_at__lt=expiration_limit).delete()


def _autocomplete_past_bookings():
    """Automatically mark 'confirmed' bookings as 'completed' 24 hours after their scheduled time."""
    current_time = timezone.now()
    # Find bookings that could be 24h old (date is yesterday or older)
    # Using date__lte allows us to avoid checking future bookings unnecessarily.
    candidate_bookings = CounsellorBooking.objects.filter(
        status='confirmed',
        date__lte=current_time.date()
    )
    for booking in candidate_bookings:
        naive_dt = datetime.combine(booking.date, booking.time_slot)
        if timezone.is_naive(naive_dt):
            aware_dt = timezone.make_aware(naive_dt)
        else:
            aware_dt = naive_dt
            
        if current_time >= aware_dt + timedelta(hours=24):
            booking.status = 'completed'
            booking.completed_at = current_time
            booking.counsellor_earnings = round((booking.total_fee - booking.platform_fee) * decimal.Decimal('0.90'), 2)
            booking.save(update_fields=['status', 'counsellor_earnings', 'completed_at'])


SESSION_DURATION_MINUTES = 30


def _get_session_window(booking):
    """Return (session_start, session_end) as timezone-aware datetimes for a booking."""
    naive_start = datetime.combine(booking.date, booking.time_slot)
    session_start = timezone.make_aware(naive_start) if timezone.is_naive(naive_start) else naive_start
    session_end = session_start + timedelta(minutes=SESSION_DURATION_MINUTES)
    return session_start, session_end


def _is_session_active(booking):
    """Return 'early', 'active', or 'expired' based on current time vs booked slot window.
    'expired' is also returned when booking is completed/cancelled.
    """
    if booking.status in ('completed', 'cancelled'):
        return 'expired'
    now = timezone.now()
    session_start, session_end = _get_session_window(booking)
    if now < session_start:
        return 'early'
    if now >= session_end:
        return 'expired'
    return 'active'



def sync_bonus_balance(user):
    from django.db import transaction
    from django.utils import timezone
    from Mind_Mend.models import BonusCredit, WalletTransaction, UserProfile
    
    now = timezone.now()
    
    with transaction.atomic():
        expired_credits = BonusCredit.objects.filter(user=user, remaining_amount__gt=0, expires_at__lte=now)
        for credit in expired_credits:
            expired_amt = credit.remaining_amount
            credit.remaining_amount = 0
            credit.save(update_fields=['remaining_amount'])
            
            WalletTransaction.objects.create(
                user=user,
                amount=expired_amt,
                transaction_type='expired',
                description='Bonus credits expired after 90 days'
            )
            
        profile, _ = UserProfile.objects.get_or_create(user=user)
        active_credits = BonusCredit.objects.filter(user=user, remaining_amount__gt=0, expires_at__gt=now)
        total_bonus = sum(c.remaining_amount for c in active_credits)
        profile.bonus_balance = total_bonus
        profile.save(update_fields=['bonus_balance'])

def deduct_bonus(user, amount_to_deduct):
    from django.utils import timezone
    from Mind_Mend.models import BonusCredit
    if amount_to_deduct <= 0: return
    now = timezone.now()
    active_credits = BonusCredit.objects.filter(user=user, remaining_amount__gt=0, expires_at__gt=now).order_by('expires_at')
    
    remaining = amount_to_deduct
    for credit in active_credits:
        if remaining <= 0: break
        if credit.remaining_amount <= remaining:
            remaining -= credit.remaining_amount
            credit.remaining_amount = 0
            credit.save(update_fields=['remaining_amount'])
        else:
            credit.remaining_amount -= remaining
            credit.save(update_fields=['remaining_amount'])
            remaining = 0

def add_bonus_credit(user, amount):
    from django.utils import timezone
    from datetime import timedelta
    from Mind_Mend.models import BonusCredit
    if amount <= 0: return
    now = timezone.now()
    BonusCredit.objects.create(
        user=user,
        initial_amount=amount,
        remaining_amount=amount,
        expires_at=now + timedelta(days=90)
    )

def get_counsellor_for_user(request):
    """Returns the counsellor for the logged-in user. If superuser, can mock as first counsellor or by ID."""
    from Mind_Mend.models import Counsellor
    from django.shortcuts import get_object_or_404
    counsellor = Counsellor.objects.filter(user=request.user).first()
    if not counsellor and request.user.is_superuser:
        cid = request.GET.get('counsellor_id')
        if cid:
            return get_object_or_404(Counsellor, id=cid)
        return Counsellor.objects.first()
    return counsellor

@login_required
def counsellor_booking(request):
    sync_bonus_balance(request.user)
    _cleanup_expired_pending_bookings()

    import json as _json
    from django.db.models import Avg
    counsellors = list(
        Counsellor.objects.filter(is_active=True).annotate(
            avg_rating=Avg('counsellorbooking__counsellorreview__rating')
        )
    )
    if request.method == 'POST':
        form = CounsellorBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.user = request.user

            # Calculate fees before saving (₹2 platform convenience fee for normal bookings)
            c = booking.counsellor
            chat_fee = c.session_fee if booking.include_chat else 0
            video_fee = c.video_session_fee if booking.include_video else 0
            pfee = decimal.Decimal('2.00')
            booking.chat_fee = chat_fee
            booking.video_fee = video_fee
            booking.platform_fee = pfee
            booking.total_fee = chat_fee + video_fee + pfee
            booking.save()

            if booking.total_fee > 0:
                return redirect('checkout_payment', booking_id=booking.id)
            else:
                booking.is_paid = True
                booking.status = 'confirmed'
                booking.save(update_fields=['is_paid', 'status'])
                _notify_counsellor(
                    booking.counsellor,
                    'booking_created',
                    'New appointment booked',
                    f'{_booking_patient_name(booking)} booked {booking.date} at {booking.time_slot.strftime("%H:%M")}.',
                    booking=booking,
                    actor=request.user
                )
                return redirect('my_bookings')
    else:
        initial_data = {'date': timezone.localdate()}
        c_id = request.GET.get('counsellor')
        if c_id:
            try:
                initial_data['counsellor'] = int(c_id)
            except ValueError:
                pass
        form = CounsellorBookingForm(initial=initial_data)

    # Build counsellor availability data for the JS slot picker
    counsellors_json = _json.dumps([
        {
            'id': c.id,
            'start': c.available_time_start.strftime('%H:%M'),
            'end': c.available_time_end.strftime('%H:%M'),
            'days': [
                t.strip().lower()[:3]
                for t in (c.available_days or '').replace('/', ',').replace(' ', ',').split(',')
                if t.strip()
            ],
            'session_fee': float(c.session_fee),
            'video_session_fee': float(c.video_session_fee),
        }
        for c in counsellors
    ])

    return render(request, 'Mind_Mend/counsellor/counsellor_booking.html', {
        'form': form,
        'counsellors': counsellors,
        'counsellors_json': counsellors_json,
    })


@login_required
def instant_booking(request):
    _cleanup_expired_pending_bookings()

    import json as _json
    from django.db.models import Avg
    counsellors = list(
        Counsellor.objects.filter(is_active=True, is_instant_enabled=True).annotate(
            avg_rating=Avg('counsellorbooking__counsellorreview__rating')
        )
    )
    if request.method == 'POST':
        post_data = request.POST.copy()
        post_data['date'] = timezone.localdate().strftime('%Y-%m-%d')
        post_data['time_slot'] = timezone.localtime().strftime('%H:%M')
        form = CounsellorBookingForm(post_data, is_instant=True)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.user = request.user
            booking.is_instant = True

            # Calculate fees before saving (₹3 platform convenience fee for instant bookings)
            c = booking.counsellor
            chat_fee = c.instant_session_fee if booking.include_chat else 0
            video_fee = c.instant_video_session_fee if booking.include_video else 0
            pfee = decimal.Decimal('3.00')
            booking.chat_fee = chat_fee
            booking.video_fee = video_fee
            booking.platform_fee = pfee
            booking.total_fee = chat_fee + video_fee + pfee
            booking.save()

            if booking.total_fee > 0:
                return redirect('checkout_payment', booking_id=booking.id)
            else:
                booking.is_paid = True
                booking.status = 'confirmed'
                booking.save(update_fields=['is_paid', 'status'])
                _notify_counsellor(
                    booking.counsellor,
                    'booking_created',
                    'New instant appointment booked ⚡',
                    f'{_booking_patient_name(booking)} booked instant session on {booking.date} at {booking.time_slot.strftime("%H:%M")}.',
                    booking=booking,
                    actor=request.user
                )
                return redirect('instant_connect', booking_id=booking.id)
    else:
        initial_data = {'date': timezone.localdate()}
        c_id = request.GET.get('counsellor')
        if c_id:
            try:
                initial_data['counsellor'] = int(c_id)
            except ValueError:
                pass
        form = CounsellorBookingForm(initial=initial_data, is_instant=True)

    # Build counsellor availability data for the JS slot picker
    counsellors_json = _json.dumps([
        {
            'id': c.id,
            'start': c.available_time_start.strftime('%H:%M'),
            'end': c.available_time_end.strftime('%H:%M'),
            'days': [
                t.strip().lower()[:3]
                for t in (c.available_days or '').replace('/', ',').replace(' ', ',').split(',')
                if t.strip()
            ],
            'instant_session_fee': float(c.instant_session_fee),
            'instant_video_session_fee': float(c.instant_video_session_fee),
        }
        for c in counsellors
    ])

    return render(request, 'Mind_Mend/counsellor/instant_booking.html', {
        'form': form,
        'counsellors': counsellors,
        'counsellors_json': counsellors_json,
    })


@login_required
def instant_connect(request, booking_id):
    booking = get_object_or_404(CounsellorBooking, pk=booking_id, user=request.user)
    if not booking.is_instant:
        return redirect('my_bookings')
    return render(request, 'Mind_Mend/counsellor/instant_connect.html', {
        'booking': booking,
    })


def _user_can_access_booking(user, booking, require_dispute_for_admin=False):
    """True if user is the client or the counsellor for this booking."""
    if booking.user_id == user.id:
        return True
    if booking.counsellor.user_id and booking.counsellor.user_id == user.id:
        return True
    if user.is_superuser:
        if require_dispute_for_admin:
            return getattr(booking, 'is_disputed', False)
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
    sync_bonus_balance(request.user)
    _autocomplete_past_bookings()
    bookings = CounsellorBooking.objects.filter(user=request.user).select_related('counsellor').order_by('-date', '-time_slot')
    # Prefetch reviews for completed bookings (to show "Leave review" or existing review)
    bookings = list(bookings)
    for b in bookings:
        b.has_review = CounsellorReview.objects.filter(booking=b).exists()
    return render(request, 'Mind_Mend/counsellor/my_bookings.html', {'bookings': bookings})


@login_required
@require_http_methods(['POST'])
def booking_action(request, booking_id):
    booking = get_object_or_404(CounsellorBooking, pk=booking_id, user=request.user)
    action = request.POST.get('action')
    if action == 'cancel' and booking.status in ('pending', 'confirmed') and not booking.is_paid:
        booking.status = 'cancelled'
        booking.save(update_fields=['status'])
        messages.info(request, 'Booking cancelled.')
    return redirect('my_bookings')


@login_required
@require_http_methods(['POST'])
def delete_booking(request, booking_id):
    """Hard-delete a completed or cancelled booking. Only the patient can delete."""
    booking = get_object_or_404(CounsellorBooking, pk=booking_id, user=request.user)
    if booking.status not in ('completed', 'cancelled'):
        messages.error(request, 'Only completed or cancelled sessions can be deleted.')
        return redirect('my_bookings')
    booking.delete()
    messages.success(request, 'Session record deleted successfully.')
    return redirect('my_bookings')


@login_required
def counsellor_chat(request, booking_id):
    """Live chat with counsellor for a booking. User or counsellor can access.
    Chat is only enabled during the booked 30-minute time slot.
    All previous sessions between the same user+counsellor pair are shown as history.
    """
    _autocomplete_past_bookings()
    booking = get_object_or_404(CounsellorBooking, pk=booking_id)
    if not _user_can_access_booking(request.user, booking, require_dispute_for_admin=True):
        messages.error(request, 'Privacy Lock: Admins can only view chat transcripts for disputed sessions.')
        return redirect('my_bookings')

    session_state = _is_session_active(booking)
    session_start, session_end = _get_session_window(booking)
    now = timezone.now()
    seconds_until_start = max(0, int((session_start - now).total_seconds())) if session_state == 'early' else 0

    # Fetch ALL messages between this user+counsellor pair (across all sessions).
    # Messages are annotated so the template can render session-boundary dividers.
    raw_messages = list(CounsellorChatMessage.objects.filter(
        booking__user=booking.user,
        booking__counsellor=booking.counsellor
    ).select_related('sender', 'booking').order_by('created_at', 'id'))

    # Collect all past bookings for this pair (ordered chronologically) to build session labels.
    from ..models import CounsellorBooking as _CB
    past_bookings_qs = _CB.objects.filter(
        user=booking.user,
        counsellor=booking.counsellor
    ).order_by('date', 'time_slot')
    booking_session_num = {b.id: idx + 1 for idx, b in enumerate(past_bookings_qs)}
    total_sessions = len(booking_session_num)

    chat_messages = []
    prev_booking_id = None
    for msg in raw_messages:
        msg.sender_label = _chat_sender_name(booking, msg.sender)
        msg.is_current_session = (msg.booking_id == booking.id)
        # Mark the first message of each new session so the template can draw a divider.
        msg.is_new_session = (msg.booking_id != prev_booking_id)
        msg.session_number = booking_session_num.get(msg.booking_id, 1)
        msg.session_date = msg.booking.date
        msg.session_time = msg.booking.time_slot
        prev_booking_id = msg.booking_id
        chat_messages.append(msg)

    if request.method == 'POST':
        content = (request.POST.get('content') or '').strip()
        if session_state != 'active':
            err = 'Session has not started yet.' if session_state == 'early' else f'This session is {booking.status if booking.status in ("completed", "cancelled") else "over"}. Chat is disabled.'
            messages.info(request, err)
            return redirect('counsellor_chat', booking_id=booking.pk)
        if content:
            is_first_message = not CounsellorChatMessage.objects.filter(booking=booking).exists()
            
            update_fields = []
            if request.user.id == booking.counsellor.user_id:
                if not booking.counsellor_joined_at:
                    booking.counsellor_joined_at = timezone.now()
                    update_fields.append('counsellor_joined_at')
            else:
                if not booking.patient_joined_at:
                    booking.patient_joined_at = timezone.now()
                    update_fields.append('patient_joined_at')
            if update_fields:
                booking.save(update_fields=update_fields)

            msg = CounsellorChatMessage.objects.create(booking=booking, sender=request.user, content=content)
            if request.user.id != booking.counsellor.user_id:
                _notify_counsellor(
                    booking.counsellor,
                    'chat_started' if is_first_message else 'message_received',
                    'Patient started chat' if is_first_message else 'New patient message',
                    f'{_booking_patient_name(booking)}: {content[:120]}',
                    booking=booking,
                    actor=request.user
                )
        return redirect('counsellor_chat', booking_id=booking.pk)

    minutes_since_start = 0
    if session_state in ('active', 'expired'):
        minutes_since_start = max(0, (now - session_start).total_seconds() / 60)

    return render(request, 'Mind_Mend/counsellor/counsellor_chat.html', {
        'booking': booking,
        'chat_messages': chat_messages,
        'chat_locked': booking.status in ('completed', 'cancelled'),
        'session_state': session_state,
        'session_start': session_start,
        'session_end': session_end,
        'seconds_until_start': seconds_until_start,
        'minutes_since_start': minutes_since_start,
        'is_counsellor_view': (booking.counsellor.user_id == request.user.id),
        'total_sessions': total_sessions,
    })



@login_required
@require_http_methods(['POST'])
def request_early_finish(request, booking_id):
    """Patient or counsellor requests to end the session early.
    Both must agree before the session is actually completed."""
    booking = get_object_or_404(CounsellorBooking, pk=booking_id)
    if not _user_can_access_booking(request.user, booking):
        messages.error(request, 'You do not have permission.')
        return redirect('home')
    if booking.status != 'confirmed':
        messages.info(request, 'This session cannot be ended early.')
        next_url = request.POST.get('next', 'home')
        return redirect(next_url)

    is_counsellor = (request.user.id == booking.counsellor.user_id)
    is_patient = (request.user.id == booking.user_id)

    if is_counsellor:
        booking.counsellor_requested_finish = True
        booking.save(update_fields=['counsellor_requested_finish'])
        # Notify patient
        from Mind_Mend.models import Notification
        Notification.objects.create(
            user=booking.user,
            title='Counsellor wants to end the session early',
            body=f'{booking.counsellor.name} has requested to finish the session early. Please confirm if you agree.',
        )
        messages.info(request, 'Your request has been sent to the patient. The session will complete once they confirm.')
    elif is_patient:
        booking.patient_requested_finish = True
        booking.save(update_fields=['patient_requested_finish'])
        # Notify counsellor
        _notify_counsellor(
            booking.counsellor,
            'booking_status',
            'Patient wants to end the session early',
            f'{_booking_patient_name(booking)} has requested to finish the session early. Confirm from your session screen.',
            booking=booking,
            actor=request.user
        )
        messages.info(request, 'Your request has been sent to the counsellor. The session will complete once they confirm.')

    # If both have now agreed → auto-complete
    if booking.patient_requested_finish and booking.counsellor_requested_finish:
        _do_complete_session(booking)
        messages.success(request, 'Both parties agreed. Session has been marked as completed!')
        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        if is_patient:
            if not CounsellorReview.objects.filter(booking=booking).exists():
                return redirect('submit_review', booking_id=booking.id)
            return redirect('counsellor_booking')
        return redirect('counsellor_sessions')

    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)
    if is_patient:
        return redirect('counsellor_chat', booking_id=booking.id)
    return redirect('counsellor_chat', booking_id=booking.id)


def _do_complete_session(booking):
    """Internal helper: mark a booking as completed, calculate earnings and duration."""
    booking.status = 'completed'
    booking.completed_at = timezone.now()
    booking.session_ended_at = timezone.now()

    first_join = None
    if booking.counsellor_joined_at and booking.patient_joined_at:
        first_join = min(booking.counsellor_joined_at, booking.patient_joined_at)
    elif booking.counsellor_joined_at:
        first_join = booking.counsellor_joined_at
    elif booking.patient_joined_at:
        first_join = booking.patient_joined_at

    if first_join:
        duration_delta = booking.session_ended_at - first_join
        booking.actual_duration_minutes = max(0, int(duration_delta.total_seconds() / 60))

    booking.counsellor_earnings = round((booking.total_fee - booking.platform_fee) * decimal.Decimal('0.90'), 2)
    booking.save(update_fields=[
        'status', 'counsellor_earnings', 'completed_at',
        'session_ended_at', 'actual_duration_minutes'
    ])


@login_required
@require_http_methods(['POST'])
def finish_session(request, booking_id):
    """Allow either patient or counsellor to mark a session as completed (direct finish for auto-complete / admin)."""
    booking = get_object_or_404(CounsellorBooking, pk=booking_id)
    if not _user_can_access_booking(request.user, booking):
        messages.error(request, 'You do not have permission to finish this session.')
        return redirect('home')
    if booking.status in ('completed', 'cancelled'):
        messages.info(request, f'This session is already {booking.status}.')
    else:
        _do_complete_session(booking)
        if request.user.id != booking.counsellor.user_id:
            _notify_counsellor(
                booking.counsellor,
                'booking_status',
                'Session marked completed',
                f'{_booking_patient_name(booking)} marked the session as completed.',
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
        return redirect('counsellor_booking')
    return redirect('counsellor_sessions')



@login_required
def counsellor_video_call(request, booking_id):
    """Virtual video call room with counsellor for a booking. User or counsellor can access.
    Video call is only enabled during the booked 30-minute time slot.
    """
    _autocomplete_past_bookings()
    booking = get_object_or_404(CounsellorBooking, pk=booking_id)
    if not _user_can_access_booking(request.user, booking, require_dispute_for_admin=True):
        messages.error(request, 'Privacy Lock: Admins can only view video rooms for disputed sessions.')
        return redirect('my_bookings')
    if not booking.include_video:
        messages.error(request, 'This booking does not include a video calling session.')
        return redirect('my_bookings')
    if not booking.is_paid and booking.total_fee > 0:
        messages.error(request, 'Please complete payment before joining the session.')
        return redirect('checkout_payment', booking_id=booking.id)

    session_state = _is_session_active(booking)
    session_start, session_end = _get_session_window(booking)
    now = timezone.now()
    seconds_until_start = max(0, int((session_start - now).total_seconds())) if session_state == 'early' else 0
    
    if session_state == 'active':
        update_fields = []
        if request.user.id == booking.counsellor.user_id:
            if not booking.counsellor_joined_at:
                booking.counsellor_joined_at = now
                update_fields.append('counsellor_joined_at')
        else:
            if not booking.patient_joined_at:
                booking.patient_joined_at = now
                update_fields.append('patient_joined_at')
        if update_fields:
            booking.save(update_fields=update_fields)

    chat_messages = list(CounsellorChatMessage.objects.filter(
        booking__user=booking.user,
        booking__counsellor=booking.counsellor
    ).select_related('sender').order_by('created_at'))
    for msg in chat_messages:
        msg.sender_label = _chat_sender_name(booking, msg.sender)

    return render(request, 'Mind_Mend/counsellor/video_call.html', {
        'booking': booking,
        'chat_messages': chat_messages,
        'chat_locked': booking.status in ('completed', 'cancelled'),
        'session_state': session_state,
        'session_start': session_start,
        'session_end': session_end,
        'seconds_until_start': seconds_until_start,
        'is_counsellor_view': (booking.counsellor.user_id == request.user.id),
    })


@login_required
def counsellor_sessions(request):
    """List of sessions (bookings) for the logged-in counsellor."""
    _autocomplete_past_bookings()
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
    return render(request, 'Mind_Mend/counsellor/counsellor_sessions.html', {'bookings': bookings, 'counsellor': counsellor})


@login_required
def admin_counsellors_dashboard(request):
    """Admin directory of all counsellors with aggregated stats."""
    if not request.user.is_staff:
        return redirect('home')
    
    counsellors = Counsellor.objects.all().prefetch_related('counsellorbooking_set', 'counsellorbooking_set__counsellorreview')
    counsellor_data = []
    
    for c in counsellors:
        bookings = c.counsellorbooking_set.all()
        completed = [b for b in bookings if b.status == 'completed']
        total_sessions = len(completed)
        total_bookings = len(bookings)
        completion_rate = (total_sessions / total_bookings * 100) if total_bookings > 0 else 0
        
        # Segmented Sessions
        normal_chat_count = sum(1 for b in completed if not b.is_instant and not b.include_video)
        normal_video_count = sum(1 for b in completed if not b.is_instant and b.include_video)
        instant_chat_count = sum(1 for b in completed if b.is_instant and not b.include_video)
        instant_video_count = sum(1 for b in completed if b.is_instant and b.include_video)
        
        import decimal
        def get_earnings(b):
            if b.counsellor_earnings and b.counsellor_earnings > 0:
                return b.counsellor_earnings
            # Fallback for old mock bookings
            fee = b.total_fee if getattr(b, 'total_fee', None) else (b.counsellor.instant_session_fee if b.is_instant else b.counsellor.session_fee)
            return round((fee or 0) * decimal.Decimal('0.90'), 2)

        # Earnings
        earnings = sum(get_earnings(b) for b in completed)
        normal_earnings = sum(get_earnings(b) for b in completed if not b.is_instant)
        instant_earnings = sum(get_earnings(b) for b in completed if b.is_instant)
        
        pending_payout = sum(get_earnings(b) for b in completed if not b.is_settled and not getattr(b, 'is_disputed', False))
        
        # Ratings
        reviews = [b.counsellorreview.rating for b in completed if hasattr(b, 'counsellorreview')]
        rating = sum(reviews) / len(reviews) if reviews else 0
        
        normal_reviews = [b.counsellorreview.rating for b in completed if hasattr(b, 'counsellorreview') and not b.is_instant]
        normal_rating = sum(normal_reviews) / len(normal_reviews) if normal_reviews else 0
        
        instant_reviews = [b.counsellorreview.rating for b in completed if hasattr(b, 'counsellorreview') and b.is_instant]
        instant_rating = sum(instant_reviews) / len(instant_reviews) if instant_reviews else 0
        
        counsellor_data.append({
            'obj': c,
            'total_sessions': total_sessions,
            'earnings': earnings,
            'pending_payout': pending_payout,
            'completion_rate': completion_rate,
            'rating': rating,
            'normal_chat_count': normal_chat_count,
            'normal_video_count': normal_video_count,
            'instant_chat_count': instant_chat_count,
            'instant_video_count': instant_video_count,
            'normal_earnings': normal_earnings,
            'instant_earnings': instant_earnings,
            'normal_rating': normal_rating,
        'instant_rating': instant_rating,
        })
        
    return render(request, 'Mind_Mend/admin/counsellors.html', {
        'counsellors_data': counsellor_data,
        'total_counsellors': len(counsellors)
    })


@login_required
def admin_counsellor_analytics(request, counsellor_id):
    """Dedicated advanced analytics page for a specific counsellor."""
    if not request.user.is_staff:
        return redirect('home')
        
    counsellor = get_object_or_404(Counsellor, id=counsellor_id)
    bookings = counsellor.counsellorbooking_set.all()
    completed = [b for b in bookings if b.status == 'completed']
    total_sessions = len(completed)
    total_bookings = len(bookings)
    completion_rate = (total_sessions / total_bookings * 100) if total_bookings > 0 else 0
    
    # Segmented Sessions
    normal_chat_count = sum(1 for b in completed if not b.is_instant and not b.include_video)
    normal_video_count = sum(1 for b in completed if not b.is_instant and b.include_video)
    instant_chat_count = sum(1 for b in completed if b.is_instant and not b.include_video)
    instant_video_count = sum(1 for b in completed if b.is_instant and b.include_video)
    
    import decimal
    def get_earnings(b):
        if b.counsellor_earnings and b.counsellor_earnings > 0:
            return b.counsellor_earnings
        fee = getattr(b, 'total_fee', None) or (b.counsellor.instant_session_fee if b.is_instant else b.counsellor.session_fee)
        return round((fee or 0) * decimal.Decimal('0.90'), 2)

    # Earnings
    total_earnings = sum(get_earnings(b) for b in completed)
    normal_chat_earnings = sum(get_earnings(b) for b in completed if not b.is_instant and not b.include_video)
    normal_video_earnings = sum(get_earnings(b) for b in completed if not b.is_instant and b.include_video)
    instant_chat_earnings = sum(get_earnings(b) for b in completed if b.is_instant and not b.include_video)
    instant_video_earnings = sum(get_earnings(b) for b in completed if b.is_instant and b.include_video)
    
    # Ratings
    reviews = [b.counsellorreview.rating for b in completed if hasattr(b, 'counsellorreview')]
    rating = sum(reviews) / len(reviews) if reviews else 0
    
    normal_reviews = [b.counsellorreview.rating for b in completed if hasattr(b, 'counsellorreview') and not b.is_instant]
    normal_rating = sum(normal_reviews) / len(normal_reviews) if normal_reviews else 0
    
    instant_reviews = [b.counsellorreview.rating for b in completed if hasattr(b, 'counsellorreview') and b.is_instant]
    instant_rating = sum(instant_reviews) / len(instant_reviews) if instant_reviews else 0
    
    # Quality Badge
    badge = None
    if total_sessions >= 5:
        if rating >= 4.8 and completion_rate >= 95:
            badge = "Premium Quality"
        elif rating < 3.5:
            badge = "Quality Review"

    context = {
        'c': counsellor,
        'badge': badge,
        'total_earnings': total_earnings,
        'rating': rating,
        'normal_chat_count': normal_chat_count,
        'normal_video_count': normal_video_count,
        'instant_chat_count': instant_chat_count,
        'instant_video_count': instant_video_count,
        'normal_chat_earnings': normal_chat_earnings,
        'normal_video_earnings': normal_video_earnings,
        'instant_chat_earnings': instant_chat_earnings,
        'instant_video_earnings': instant_video_earnings,
        'normal_rating': normal_rating,
        'instant_rating': instant_rating,
    }
    return render(request, 'Mind_Mend/admin/admin_counsellor_analytics.html', context)


@login_required
def doctor_dashboard(request):
    """Doctor-facing dashboard for appointments and notifications."""
    _autocomplete_past_bookings()
    counsellor = get_counsellor_for_user(request)
    if not counsellor:
        messages.info(request, 'You are not registered as a counsellor.')
        return redirect('home')
        
    is_masquerading = request.user.is_superuser and counsellor.user != request.user
    bookings = list(CounsellorBooking.objects.filter(counsellor=counsellor).select_related('user').order_by('date', 'time_slot'))
    reviews_by_booking = {
        r.booking_id: r
        for r in CounsellorReview.objects.filter(booking__in=bookings)
    }
    for b in bookings:
        b.review = reviews_by_booking.get(b.id)
        b.has_review = b.review is not None

    # Only show booking-level notifications (not chat message events) in the dashboard panel.
    BOOKING_EVENT_TYPES = ('booking_created', 'booking_status')
    notifications_qs = CounsellorNotification.objects.filter(
        counsellor=counsellor,
        event_type__in=BOOKING_EVENT_TYPES
    )
    unread_count = notifications_qs.filter(is_read=False).count()

    # Compute unread message count per booking (messages from patient only, during the session window).
    booking_ids = [b.id for b in bookings]
    all_messages = CounsellorChatMessage.objects.filter(
        booking_id__in=booking_ids
    ).exclude(sender=counsellor.user).values('booking_id', 'created_at')

    # Group message counts per booking, restricted to the session's 30-min window.
    from collections import defaultdict
    msg_counts = defaultdict(int)
    booking_map = {b.id: b for b in bookings}
    for msg in all_messages:
        bk = booking_map.get(msg['booking_id'])
        if bk is None:
            continue
        session_start, session_end = _get_session_window(bk)
        msg_ts = msg['created_at']
        # Make message timestamp offset-aware for comparison
        if timezone.is_naive(msg_ts):
            msg_ts = timezone.make_aware(msg_ts)
        if session_start <= msg_ts <= session_end:
            msg_counts[msg['booking_id']] += 1

    for b in bookings:
        b.session_message_count = msg_counts.get(b.id, 0)

    today_date = timezone.localdate()
    today_bookings = [b for b in bookings if b.date == today_date and b.status not in ('cancelled',)]
    upcoming_bookings = [b for b in bookings if b.date > today_date and b.status not in ('completed', 'cancelled')]
    today_bookings_count = len(today_bookings)
    upcoming_bookings_count = len(upcoming_bookings)
    pending_count = len([b for b in bookings if b.status == 'pending'])
    completed_bookings = [b for b in bookings if b.status == 'completed']
    total_completed_sessions = len(completed_bookings)
    monthly_revenue = sum(
        (b.counsellor.instant_session_fee if b.is_instant else b.counsellor.session_fee)
        for b in completed_bookings
        if b.is_paid and b.date.month == today_date.month and b.date.year == today_date.year
    )

    return render(request, 'Mind_Mend/counsellor/doctor_dashboard.html', {
        'counsellor': counsellor,
        'pending_bookings': [b for b in bookings if b.status == 'pending'],
        'bookings': bookings,
        'completed_bookings': completed_bookings[::-1],
        'today_bookings': today_bookings,
        'upcoming_bookings': upcoming_bookings,
        'notifications': notifications_qs[:20],
        'unread_count': unread_count,
        'today_bookings_count': today_bookings_count,
        'upcoming_bookings_count': upcoming_bookings_count,
        'pending_count': pending_count,
        'total_completed_sessions': total_completed_sessions,
        'monthly_revenue': monthly_revenue,
        'today_date': today_date,
        'is_masquerading': is_masquerading,
    })


@login_required
@require_http_methods(['POST'])
def doctor_booking_action(request, booking_id):
    """Accept/reject/complete booking from doctor panel."""
    counsellor = get_counsellor_for_user(request)
    if not counsellor:
        return JsonResponse({'error': 'Forbidden'}, status=403)
        
    if request.user.is_superuser and counsellor.user != request.user:
        return JsonResponse({'error': 'Read-only mode. Masquerading admins cannot modify bookings.'}, status=403)
        
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
def emergency_cancel_booking(request, booking_id):
    """Counsellor cancels a booking due to emergency. Calculates compensation and warns/suspends."""
    booking = get_object_or_404(CounsellorBooking, id=booking_id)
    
    # Verify the user is the assigned counsellor
    if not hasattr(request.user, 'counsellor') or request.user.counsellor != booking.counsellor:
        messages.error(request, 'Unauthorized action.')
        return redirect('doctor_dashboard')
        
    if booking.status != 'confirmed':
        messages.error(request, 'Only confirmed bookings can be emergency cancelled.')
        return redirect('doctor_dashboard')

    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        message_to_patient = request.POST.get('message_to_patient', '').strip()
        
        if not reason or not message_to_patient:
            messages.error(request, 'Please provide both an internal reason and a message to the patient.')
            return redirect('emergency_cancel_booking', booking_id=booking.id)
            
        with transaction.atomic():
            # 1. Update Booking
            booking.status = 'cancelled'
            booking.save()
            
            # 2. Calculate Compensation (10% normal, 20% instant)
            penalty_percent = 0.20 if booking.is_instant else 0.10
            compensation = round(booking.total_fee * decimal.Decimal(penalty_percent), 2)
            
            # 3. Process Refunds (Razorpay and Wallet)
            wallet_tx = WalletTransaction.objects.filter(
                user=booking.user,
                transaction_type='session_booking',
                reference_id=str(booking.id)
            ).first()
            wallet_used = wallet_tx.amount if wallet_tx else decimal.Decimal('0.00')
            razorpay_amount = booking.total_fee - wallet_used

            # Counsellor cancelled: patient gets FULL 100% refund — no platform fee deducted
            if razorpay_amount > 0 and booking.razorpay_payment_id:
                if razorpay_amount > 0:
                    try:
                        import razorpay
                        from django.conf import settings
                        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                        client.refund.create({'payment_id': booking.razorpay_payment_id, 'amount': int(razorpay_amount * 100)})
                    except Exception as e:
                        print(f"Razorpay Refund Error: {e}")

            patient_profile, _ = UserProfile.objects.get_or_create(user=booking.user)
            
            if wallet_used > 0:
                patient_profile.wallet_balance += wallet_used
                WalletTransaction.objects.create(
                    user=booking.user,
                    amount=wallet_used,
                    transaction_type='refund',
                    description=f"Refund for cancelled session with {booking.counsellor.name}",
                    reference_id=str(booking.id)
                )

            # Credit compensation as Bonus Credit Points (non-withdrawable, expires in 90 days)
            add_bonus_credit(booking.user, compensation)
            patient_profile.bonus_balance += compensation
            patient_profile.save()
            
            WalletTransaction.objects.create(
                user=booking.user,
                amount=compensation,
                transaction_type='compensation',
                description=f"Compensation Credit Points for cancelled session with {booking.counsellor.name} (expires in 90 days)",
                reference_id=str(booking.id)
            )
            
            # 4. Create Cancellation Record
            BookingCancellation.objects.create(
                booking=booking,
                counsellor=booking.counsellor,
                reason=reason,
                message_to_patient=message_to_patient,
                compensation_credited=compensation,
                counsellor_penalty=compensation,
                refund_status='Initiated'
            )
            
            # 5. Notify Patient
            notification_body = f"Your counsellor cancelled the session due to an emergency.\n\n"
            if razorpay_amount > 0:
                notification_body += f"Bank Refund: ₹{razorpay_amount} (full 100% refund)\n"
            if wallet_used > 0:
                notification_body += f"Wallet Refund: ₹{wallet_used}\n"
            notification_body += f"Compensation Credit Points: ₹{compensation} (valid for 90 days)\n\n"
            notification_body += f"As an apology, MindMend has credited ₹{compensation} as Credit Points to your account (non-withdrawable, usable on your next booking). No platform fee has been charged for this cancellation."
            
            CounsellorNotification.objects.create(
                counsellor=booking.counsellor,
                booking=booking,
                actor=request.user,
                event_type='booking_status',
                title='Session Cancelled by Counsellor',
                body=notification_body
            )
            
            # 6. Fairness Protection (Auto-Suspend if >= 3 in 30 days)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_cancellations = BookingCancellation.objects.filter(
                counsellor=booking.counsellor,
                created_at__gte=thirty_days_ago
            ).count()
            
            if recent_cancellations >= 3:
                counsellor = booking.counsellor
                counsellor.is_active = False
                counsellor.save()
                messages.error(request, 'Your account has been automatically suspended due to excessive emergency cancellations (3 or more in 30 days). Please contact support.')
            else:
                messages.success(request, f'Session cancelled. You have {3 - recent_cancellations} cancellations remaining before suspension.')
                
            return redirect('doctor_dashboard')

    return render(request, 'Mind_Mend/counsellor/emergency_cancel.html', {
        'booking': booking
    })


@login_required
@require_http_methods(['GET'])
def doctor_notifications_api(request):
    counsellor = Counsellor.objects.filter(user=request.user).first()
    if not counsellor:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    BOOKING_EVENT_TYPES = ('booking_created', 'booking_status')
    unread_only = request.GET.get('unread') in ('1', 'true', 'True')
    qs = CounsellorNotification.objects.filter(
        counsellor=counsellor,
        event_type__in=BOOKING_EVENT_TYPES
    )
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
    BOOKING_EVENT_TYPES = ('booking_created', 'booking_status')
    qs = CounsellorNotification.objects.filter(counsellor=counsellor, is_read=False)
    if ids:
        qs = qs.filter(id__in=ids)
    updated = qs.update(is_read=True)
    # Return unread count for booking-level events only
    unread_count = CounsellorNotification.objects.filter(
        counsellor=counsellor,
        event_type__in=BOOKING_EVENT_TYPES,
        is_read=False
    ).count()
    return JsonResponse({'updated': updated, 'unread_count': unread_count})


@login_required
@require_http_methods(['GET', 'POST'])
def booking_messages_api(request, booking_id):
    booking = get_object_or_404(CounsellorBooking, pk=booking_id)
    if not _user_can_access_booking(request.user, booking, require_dispute_for_admin=True):
        return JsonResponse({'error': 'Forbidden - Privacy Lock'}, status=403)
    if request.method == 'POST':
        # Time-window enforcement
        api_session_state = _is_session_active(booking)
        if api_session_state == 'early':
            session_start, _ = _get_session_window(booking)
            return JsonResponse({
                'error': 'Session has not started yet.',
                'session_state': 'early',
                'session_start': session_start.isoformat(),
            }, status=425)
        if api_session_state == 'expired':
            return JsonResponse({
                'error': f'Chat is disabled. Session is {booking.status if booking.status in ("completed", "cancelled") else "over"}.',
                'session_state': 'expired',
            }, status=423)
        try:
            payload = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            payload = {}
        content = (payload.get('content') or request.POST.get('content') or '').strip()
        if not content:
            return JsonResponse({'error': 'Empty message'}, status=400)
        is_first_message = not CounsellorChatMessage.objects.filter(booking=booking).exists()
        
        update_fields = []
        if request.user.id == booking.counsellor.user_id:
            if not booking.counsellor_joined_at:
                booking.counsellor_joined_at = timezone.now()
                update_fields.append('counsellor_joined_at')
        else:
            if not booking.patient_joined_at:
                booking.patient_joined_at = timezone.now()
                update_fields.append('patient_joined_at')
        if update_fields:
            booking.save(update_fields=update_fields)
            
        msg = CounsellorChatMessage.objects.create(booking=booking, sender=request.user, content=content)
        if request.user.id != booking.counsellor.user_id:
            _notify_counsellor(
                booking.counsellor,
                'chat_started' if is_first_message else 'message_received',
                'Patient started chat' if is_first_message else 'New patient message',
                f'{_booking_patient_name(booking)}: {content[:120]}',
                booking=booking,
                actor=request.user
            )
        return JsonResponse({
            'message': {
                'id': msg.id,
                'sender': _chat_sender_name(booking, msg.sender),
                'sender_id': msg.sender_id,
                'content': msg.content,
                'created_at': msg.created_at.isoformat(),
            }
        }, status=201)

    since = request.GET.get('since')
    after_id = request.GET.get('after_id')
    qs = CounsellorChatMessage.objects.filter(
        booking__user=booking.user,
        booking__counsellor=booking.counsellor
    ).select_related('sender').order_by('id')
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
            'sender': _chat_sender_name(booking, m.sender),
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
            return redirect('counsellor_booking')
    else:
        form = CounsellorReviewForm(instance=review)
    return render(request, 'Mind_Mend/counsellor/review_form.html', {'form': form, 'booking': booking})


@login_required
@require_http_methods(['GET', 'POST'])
def checkout_payment(request, booking_id):
    """
    GET  → create a Razorpay order and render the payment page.
    POST → (safety fallback) redirect back to GET.
    """
    sync_bonus_balance(request.user)
    _cleanup_expired_pending_bookings()

    import razorpay
    from django.conf import settings

    booking = get_object_or_404(CounsellorBooking, pk=booking_id, user=request.user)

    if booking.is_paid or booking.status != 'pending':
        messages.info(request, "This booking has already been processed.")
        return redirect('my_bookings')

    apply_wallet = request.GET.get('apply_wallet', '1') == '1'
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    cash_balance = profile.wallet_balance
    bonus_balance = profile.bonus_balance
    total_balance = cash_balance + bonus_balance
    original_fee = booking.total_fee

    if request.method == 'POST':
        apply_wallet_post = request.POST.get('apply_wallet', '1') == '1'
        if apply_wallet_post and total_balance >= original_fee:
            with transaction.atomic():
                bonus_to_use = min(bonus_balance, original_fee)
                cash_to_use = original_fee - bonus_to_use
                
                deduct_bonus(request.user, bonus_to_use)
                profile.wallet_balance -= cash_to_use
                profile.bonus_balance -= bonus_to_use
                profile.save()
                
                if cash_to_use > 0:
                    WalletTransaction.objects.create(
                        user=request.user,
                        amount=cash_to_use,
                        transaction_type='session_booking',
                        description=f"Paid for session with {booking.counsellor.name}",
                        reference_id=str(booking.id)
                    )
                if bonus_to_use > 0:
                    WalletTransaction.objects.create(
                        user=request.user,
                        amount=bonus_to_use,
                        transaction_type='session_booking',
                        description=f"Bonus used for session with {booking.counsellor.name}",
                        reference_id=str(booking.id)
                    )

                booking.is_paid = True
                booking.status = 'confirmed'
                booking.wallet_used = cash_to_use
                booking.bonus_used = bonus_to_use
                booking.save(update_fields=['is_paid', 'status', 'wallet_used', 'bonus_used'])
                
                _notify_counsellor(
                    booking.counsellor,
                    'booking_created',
                    'New appointment booked (Paid via Wallet)',
                    f'{_booking_patient_name(booking)} booked {booking.date} at {booking.time_slot.strftime("%H:%M")}.',
                    booking=booking,
                    actor=request.user
                )
                
                messages.success(request, f"Payment successful! You used ₹{original_fee} from your balances.")
                if booking.is_instant:
                    return redirect('instant_connect', booking_id=booking.id)
                return redirect('my_bookings')
        return redirect('checkout_payment', booking_id=booking_id)
    
    amount_to_pay = original_fee
    wallet_used = decimal.Decimal('0.00')
    bonus_used = decimal.Decimal('0.00')
    
    if apply_wallet and total_balance > 0:
        if total_balance >= original_fee:
            bonus_used = min(bonus_balance, original_fee)
            wallet_used = original_fee - bonus_used
            amount_to_pay = decimal.Decimal('0.00')
        else:
            bonus_used = bonus_balance
            wallet_used = cash_balance
            amount_to_pay = original_fee - total_balance

    amount_paise = int(amount_to_pay * 100)
    
    razorpay_order_id = ""
    if amount_paise > 0:
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
        razorpay_order = client.order.create({
            'amount': amount_paise,
            'currency': 'INR',
            'payment_capture': 1,
            'receipt': f"booking_{booking.id}",
            'notes': {
                'booking_id': booking.id,
                'user_id': request.user.id,
                'apply_wallet': '1' if apply_wallet else '0',
            },
        })
        razorpay_order_id = razorpay_order['id']

    return render(request, 'Mind_Mend/counsellor/payment.html', {
        'booking': booking,
        'original_fee': original_fee,
        'wallet_used': wallet_used,
        'bonus_used': bonus_used,
        'amount_to_pay': amount_to_pay,
        'wallet_balance': cash_balance,
        'bonus_balance': bonus_balance,
        'total_balance': total_balance,
        'apply_wallet': apply_wallet,
        'razorpay_order_id': razorpay_order_id,
        'razorpay_key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
        'amount_paise': amount_paise,
        'user_name': request.user.get_full_name() or request.user.username,
        'user_email': request.user.email,
        'booking_timestamp': booking.created_at.timestamp(),
    })


@login_required
@require_http_methods(['POST'])
def razorpay_payment_verify(request, booking_id):
    """
    Called by our JS after Razorpay handler fires.
    Verifies the payment signature and confirms the booking.
    """
    import hmac
    import hashlib
    from django.conf import settings

    booking = get_object_or_404(CounsellorBooking, pk=booking_id, user=request.user)

    if booking.is_paid:
        messages.info(request, "Payment already recorded.")
        return redirect('my_bookings')

    razorpay_order_id   = request.POST.get('razorpay_order_id', '')
    razorpay_payment_id = request.POST.get('razorpay_payment_id', '')
    razorpay_signature  = request.POST.get('razorpay_signature', '')

    # HMAC-SHA256 signature verification
    message = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
    generated_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        message,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(generated_signature, razorpay_signature):
        messages.error(request, "Payment verification failed. Please contact support.")
        return redirect('checkout_payment', booking_id=booking_id)

    # Signature valid — confirm booking
    apply_wallet = request.POST.get('apply_wallet', '0') == '1'
    
    with transaction.atomic():
        if apply_wallet:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            bonus_balance = profile.bonus_balance
            cash_balance = profile.wallet_balance
            total_balance = bonus_balance + cash_balance
            
            if total_balance > 0:
                amount_to_cover = min(total_balance, booking.total_fee)
                bonus_to_use = min(bonus_balance, amount_to_cover)
                cash_to_use = amount_to_cover - bonus_to_use
                
                deduct_bonus(request.user, bonus_to_use)
                profile.bonus_balance -= bonus_to_use
                profile.wallet_balance -= cash_to_use
                profile.save()
                
                if cash_to_use > 0:
                    WalletTransaction.objects.create(
                        user=request.user,
                        amount=cash_to_use,
                        transaction_type='session_booking',
                        description=f"Partial payment for session with {booking.counsellor.name}",
                        reference_id=str(booking.id)
                    )
                if bonus_to_use > 0:
                    WalletTransaction.objects.create(
                        user=request.user,
                        amount=bonus_to_use,
                        transaction_type='session_booking',
                        description=f"Bonus used for partial payment for session with {booking.counsellor.name}",
                        reference_id=str(booking.id)
                    )
                    
                booking.wallet_used = cash_to_use
                booking.bonus_used = bonus_to_use

        booking.is_paid = True
        booking.status  = 'confirmed'
        booking.razorpay_payment_id = razorpay_payment_id
        booking.save(update_fields=['is_paid', 'status', 'razorpay_payment_id'])

    _notify_counsellor(
        booking.counsellor,
        'booking_created',
        'New appointment booked',
        f'{_booking_patient_name(booking)} booked {booking.date} at {booking.time_slot.strftime("%H:%M")}.',
        booking=booking,
        actor=request.user
    )

    messages.success(request, "Payment successful! Your appointment is confirmed.")
    if booking.is_instant:
        return redirect('instant_connect', booking_id=booking.id)
    return redirect('my_bookings')


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    """
    Server-to-server callback from Razorpay.
    Acts as a reliability fallback if the user closes the browser before redirection.
    """
    import hmac
    import hashlib
    from django.conf import settings

    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not webhook_secret:
        return HttpResponse("Webhook secret not configured", status=400)

    payload = request.body
    signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')

    # Verify Webhook Signature
    expected_signature = hmac.new(
        webhook_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        return HttpResponse("Invalid signature", status=403)

    # Process Event
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON", status=400)

    event = data.get('event')
    # Use order.paid (preferred for reliability) or payment.captured
    if event == 'order.paid':
        order_entity = data.get('payload', {}).get('order', {}).get('entity', {})
        receipt = order_entity.get('receipt', '')
        
        if receipt and receipt.startswith('booking_'):
            try:
                booking_id = int(receipt.split('_')[1])
                with transaction.atomic():
                    booking = CounsellorBooking.objects.select_for_update().get(pk=booking_id)
                    if not booking.is_paid:
                        booking.is_paid = True
                        booking.status = 'confirmed'
                        booking.save(update_fields=['is_paid', 'status'])
                        
                        # Send notification if it wasn't already sent by browser view
                        _notify_counsellor(
                            booking.counsellor,
                            'booking_created',
                            'Appointment Confirmed (via Webhook)',
                            f'Payment for booking on {booking.date} was confirmed via server notification.',
                            booking=booking
                        )
            except (ValueError, IndexError, CounsellorBooking.DoesNotExist):
                pass

    return HttpResponse("Handled", status=200)


@login_required
@require_http_methods(['GET'])
def get_booked_slots(request, counsellor_id):
    """
    Returns the list of 30-minute blocked windows for a counsellor on a date.
    Query param: ?date=YYYY-MM-DD
    Response: {"booked_slots": [{"start": "12:00", "end": "12:30"}, ...]}
    """
    from django.utils.dateparse import parse_date
    from datetime import time

    _cleanup_expired_pending_bookings()

    counsellor = get_object_or_404(Counsellor, pk=counsellor_id, is_active=True)
    date_str = request.GET.get('date', '')
    booking_date = parse_date(date_str)
    if not booking_date:
        return JsonResponse({'error': 'Invalid or missing date parameter.'}, status=400)

    SESSION_MINUTES = 30
    session_delta = timedelta(minutes=SESSION_MINUTES)

    active_bookings = CounsellorBooking.objects.filter(
        counsellor=counsellor,
        date=booking_date,
    ).exclude(status='cancelled').values_list('time_slot', flat=True)

    booked_slots = []
    for ts in active_bookings:
        start_dt = datetime.combine(booking_date, ts)
        end_dt = start_dt + session_delta
        booked_slots.append({
            'start': start_dt.strftime('%H:%M'),
            'end': end_dt.strftime('%H:%M'),
        })

    # If the date is today, block past slots from being selected
    now = timezone.localtime()
    if booking_date == now.date():
        current_time = now.time()
        c_start_mins = counsellor.available_time_start.hour * 60 + counsellor.available_time_start.minute
        c_end_mins = counsellor.available_time_end.hour * 60 + counsellor.available_time_end.minute
        current_mins = current_time.hour * 60 + current_time.minute
        
        cur = c_start_mins
        while cur + SESSION_MINUTES <= c_end_mins:
            if cur < current_mins:
                hr = cur // 60
                mn = cur % 60
                slot_time = time(hr, mn)
                slot_start_str = slot_time.strftime('%H:%M')
                if not any(s['start'] == slot_start_str for s in booked_slots):
                    slot_end_time = (datetime.combine(booking_date, slot_time) + session_delta).time()
                    booked_slots.append({
                        'start': slot_start_str,
                        'end': slot_end_time.strftime('%H:%M'),
                    })
            cur += SESSION_MINUTES

    booked_slots.sort(key=lambda s: s['start'])
    return JsonResponse({'booked_slots': booked_slots})


def how_to_book(request):
    """Static guide page explaining how to book a session."""
    return render(request, 'Mind_Mend/counsellor/how_to_book.html')


@login_required
def counsellor_detail(request, counsellor_id):
    """View to show details of a specific counsellor."""
    from django.db.models import Avg
    counsellor = get_object_or_404(
        Counsellor.objects.annotate(
            avg_rating=Avg('counsellorbooking__counsellorreview__rating')
        ),
        pk=counsellor_id,
        is_active=True
    )
    reviews = CounsellorReview.objects.filter(booking__counsellor=counsellor).select_related('user').order_by('-created_at')
    return render(request, 'Mind_Mend/counsellor/counsellor_detail.html', {
        'counsellor': counsellor,
        'reviews': reviews,
    })

@login_required
def wallet_dashboard(request):
    sync_bonus_balance(request.user)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    transactions = WalletTransaction.objects.filter(user=request.user).order_by('-created_at')
    from Mind_Mend.models import BonusCredit
    from django.utils import timezone
    active_bonus_credits = BonusCredit.objects.filter(
        user=request.user, remaining_amount__gt=0, expires_at__gt=timezone.now()
    ).order_by('expires_at')
    
    return render(request, 'Mind_Mend/core/wallet.html', {
        'wallet_balance': profile.wallet_balance,
        'bonus_balance': profile.bonus_balance,
        'transactions': transactions,
        'active_bonus_credits': active_bonus_credits
    })

@login_required
@require_http_methods(['POST'])
def add_money_checkout(request):
    """Creates a Razorpay order to add money to the wallet."""
    import razorpay
    from django.conf import settings
    amount_str = request.POST.get('amount')
    try:
        amount = decimal.Decimal(amount_str)
        if amount <= 0: raise ValueError
    except (TypeError, ValueError, decimal.InvalidOperation):
        messages.error(request, "Invalid amount.")
        return redirect('wallet_dashboard')

    amount_paise = int(amount * 100)
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    
    razorpay_order = client.order.create({
        'amount': amount_paise,
        'currency': 'INR',
        'payment_capture': 1,
        'receipt': f"wallet_{request.user.id}_{int(timezone.now().timestamp())}",
        'notes': {'user_id': request.user.id, 'purpose': 'add_money'}
    })
    
    # Store order info in session to verify later
    request.session['wallet_add_order_id'] = razorpay_order['id']
    request.session['wallet_add_amount'] = str(amount)
    
    return render(request, 'Mind_Mend/core/add_money_payment.html', {
        'amount': amount,
        'amount_paise': amount_paise,
        'razorpay_order_id': razorpay_order['id'],
        'razorpay_key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
        'user_name': request.user.get_full_name() or request.user.username,
        'user_email': request.user.email,
    })

@login_required
@require_http_methods(['POST'])
def add_money_verify(request):
    """Verifies the Razorpay payment and credits the wallet."""
    import hmac
    import hashlib
    from django.conf import settings
    
    razorpay_order_id = request.POST.get('razorpay_order_id', '')
    razorpay_payment_id = request.POST.get('razorpay_payment_id', '')
    razorpay_signature = request.POST.get('razorpay_signature', '')
    
    expected_order_id = request.session.get('wallet_add_order_id')
    amount_str = request.session.get('wallet_add_amount')
    
    if not expected_order_id or expected_order_id != razorpay_order_id:
        messages.error(request, "Invalid payment session.")
        return redirect('wallet_dashboard')

    message = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
    generated_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        message,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(generated_signature, razorpay_signature):
        messages.error(request, "Payment verification failed.")
        return redirect('wallet_dashboard')

    amount = decimal.Decimal(amount_str)
    
    with transaction.atomic():
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.wallet_balance += amount
        profile.save()
        
        WalletTransaction.objects.create(
            user=request.user,
            amount=amount,
            transaction_type='add_money',
            description="Added money via Razorpay",
            reference_id=razorpay_payment_id
        )
        
    # Clear session
    request.session.pop('wallet_add_order_id', None)
    request.session.pop('wallet_add_amount', None)
    
    messages.success(request, f"Successfully added ₹{amount} to your MindMend Wallet!")
    return redirect('wallet_dashboard')

# --- Payouts & Earnings ---

@login_required
@require_http_methods(['GET', 'POST'])
def counsellor_earnings_dashboard(request):
    """Dashboard for counsellors to view their earnings, payouts, and performance."""
    counsellor = get_counsellor_for_user(request)
    if not counsellor:
        return redirect('home')
        
    is_masquerading = request.user.is_superuser and counsellor.user != request.user
    
    if request.method == 'POST':
        if is_masquerading:
            messages.error(request, 'Read-only mode. Masquerading admins cannot modify bank details.')
            return redirect('counsellor_earnings_dashboard')
            
        bank_details, _ = CounsellorBankDetails.objects.get_or_create(counsellor=counsellor)
        bank_details.account_holder_name = request.POST.get('account_holder_name', '')
        bank_details.bank_name = request.POST.get('bank_name', '')
        bank_details.account_number = request.POST.get('account_number', '')
        bank_details.ifsc_code = request.POST.get('ifsc_code', '')
        bank_details.upi_id = request.POST.get('upi_id', '')
        bank_details.save()
        messages.success(request, 'Bank details updated successfully.')
        return redirect('counsellor_earnings_dashboard')

    completed_bookings = CounsellorBooking.objects.filter(
        counsellor=counsellor, 
        status='completed'
    ).order_by('-created_at')
    
    # 1. Financials — with fallback for old sessions where counsellor_earnings was never set
    import datetime
    def get_earnings(b):
        if b.counsellor_earnings and b.counsellor_earnings > 0:
            return b.counsellor_earnings
        fee = getattr(b, 'total_fee', None) or (
            b.counsellor.instant_session_fee if b.is_instant else b.counsellor.session_fee
        )
        return round((fee or 0) * decimal.Decimal('0.90'), 2)

    # Backfill earnings on the fly and build template-safe dicts (no underscores)
    now = timezone.now()
    enriched_bookings = []
    for b in completed_bookings:
        earned = get_earnings(b)
        # Save backfilled value to DB so future loads are correct
        if (not b.counsellor_earnings or b.counsellor_earnings == 0) and earned > 0:
            b.counsellor_earnings = earned
            b.save(update_fields=['counsellor_earnings'])
        # Determine payout hold status
        completed_ts = b.completed_at or b.created_at
        hours_since = (now - completed_ts).total_seconds() / 3600 if completed_ts else 999
        on_hold = (not b.is_settled) and hours_since < 24
        enriched_bookings.append({
            'booking': b,
            'earned': earned,
            'on_hold': on_hold,
            'is_settled': b.is_settled,
            'is_anonymous': getattr(b, 'is_anonymous', False),
            'completed_at': b.completed_at,
            'created_at': b.created_at,
            'user': b.user,
            'is_disputed': b.is_disputed,
        })

    total_lifetime_earnings = sum(row['earned'] for row in enriched_bookings)
    # Sessions still within the 24h dispute window
    on_hold_amount = sum(row['earned'] for row in enriched_bookings if row['on_hold'])
    # Sessions past 24h window, not yet settled by admin
    ready_for_payout = sum(row['earned'] for row in enriched_bookings if not row['is_settled'] and not row['on_hold'])
    pending_payout = on_hold_amount + ready_for_payout  # total unsettled

    unsettled_cancellations = BookingCancellation.objects.filter(counsellor=counsellor).exclude(refund_status='Settled')
    total_unpaid_penalties = sum(c.counsellor_penalty for c in unsettled_cancellations)
    total_deductions = total_unpaid_penalties + counsellor.outstanding_debt
    net_pending_payout = max(decimal.Decimal('0.00'), pending_payout - total_deductions)
    settled_payout = total_lifetime_earnings - pending_payout

    # 2. Performance Metrics
    total_sessions = CounsellorBooking.objects.filter(counsellor=counsellor).exclude(status='pending').count()
    completed_count = len(enriched_bookings)
    completion_rate = (completed_count / total_sessions * 100) if total_sessions > 0 else 0

    from django.db.models import Avg
    reviews = CounsellorReview.objects.filter(booking__counsellor=counsellor)
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0

    # Badge Logic
    badge = None
    if completed_count >= 5:
        if avg_rating >= 4.8 and completion_rate >= 95:
            badge = "Premium Quality"
        elif avg_rating < 3.5:
            badge = "Quality Review"

    bank_details = getattr(counsellor, 'bank_details', None)

    all_cancellations = BookingCancellation.objects.filter(
        counsellor=counsellor, counsellor_penalty__gt=0
    ).select_related('booking', 'booking__user').order_by('-created_at')

    return render(request, 'Mind_Mend/counsellor/earnings.html', {
        'counsellor': counsellor,
        'completed_bookings': enriched_bookings,
        'all_cancellations': all_cancellations,
        'total_lifetime_earnings': total_lifetime_earnings,
        'on_hold_amount': on_hold_amount,
        'ready_for_payout': ready_for_payout,
        'pending_payout': pending_payout,
        'net_pending_payout': net_pending_payout,
        'total_unpaid_penalties': total_unpaid_penalties,
        'settled_payout': settled_payout,
        'completion_rate': completion_rate,
        'avg_rating': avg_rating,
        'completed_count': completed_count,
        'badge': badge,
        'bank_details': bank_details,
        'is_masquerading': is_masquerading,
    })


@login_required
def counsellor_penalties(request):
    """Standalone page to view the penalties ledger."""
    counsellor = get_counsellor_for_user(request)
    if not counsellor:
        return redirect('home')
        
    all_cancellations = BookingCancellation.objects.filter(
        counsellor=counsellor, counsellor_penalty__gt=0
    ).select_related('booking', 'booking__user').order_by('-created_at')
    
    unsettled_cancellations = all_cancellations.exclude(refund_status='Settled')
    total_unpaid_penalties = sum(c.counsellor_penalty for c in unsettled_cancellations)
    
    return render(request, 'Mind_Mend/counsellor/penalties_ledger.html', {
        'counsellor': counsellor,
        'all_cancellations': all_cancellations,
        'total_unpaid_penalties': total_unpaid_penalties,
    })

@login_required
def counsellor_payout_history(request):
    """View showing all historical payouts settled by admin."""
    counsellor = get_counsellor_for_user(request)
    if not counsellor:
        return redirect('home')
        
    settlements = PayoutSettlement.objects.filter(counsellor=counsellor).prefetch_related(
        'settled_bookings', 'settled_bookings__user', 'settled_cancellations'
    )
    
    return render(request, 'Mind_Mend/counsellor/settlement_history.html', {
        'counsellor': counsellor,
        'settlements': settlements,
    })

from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
@require_http_methods(['GET'])
def admin_revenue_dashboard(request):
    """Dashboard for platform owner to view and settle counsellor earnings."""
    counsellors = Counsellor.objects.filter(is_active=True)
    counsellor_data = []
    
    current_time = timezone.now()
    
    for c in counsellors:
        completed_bookings = CounsellorBooking.objects.filter(counsellor=c, status='completed')
        
        # 24 hour logic
        cleared_for_payout = []
        pending_verification = []
        
        for b in completed_bookings.filter(is_settled=False):
            if b.is_disputed:
                pending_verification.append(b)
            else:
                completion_time = b.completed_at or b.created_at
                if completion_time and current_time >= completion_time + timedelta(hours=24):
                    cleared_for_payout.append(b)
                else:
                    pending_verification.append(b)
                
        gross_payout = sum(b.counsellor_earnings for b in cleared_for_payout)
        
        unsettled_cancellations = BookingCancellation.objects.filter(counsellor=c).exclude(refund_status='Settled')
        total_penalties = sum(canc.counsellor_penalty for canc in unsettled_cancellations)
        total_deductions = total_penalties + c.outstanding_debt
        
        net_payout = max(decimal.Decimal('0.00'), gross_payout - total_deductions)
        total_earnings = sum(b.counsellor_earnings for b in completed_bookings)
        
        counsellor_data.append({
            'counsellor': c,
            'cleared_payout': gross_payout,
            'penalties': total_penalties,
            'outstanding_debt': c.outstanding_debt,
            'net_payout': net_payout,
            'pending_verification_amount': sum(b.counsellor_earnings for b in pending_verification),
            'total_earnings': total_earnings,
            'cleared_count': len(cleared_for_payout),
            'pending_count': len(pending_verification),
            'bank_details': getattr(c, 'bank_details', None)
        })
        
    counsellor_data.sort(key=lambda x: x['net_payout'], reverse=True)
    
    # Analytics
    today = current_time.date()
    today_revenue = sum((b.total_fee - b.counsellor_earnings) for b in CounsellorBooking.objects.filter(status='completed', completed_at__date=today))
    month_revenue = sum((b.total_fee - b.counsellor_earnings) for b in CounsellorBooking.objects.filter(status='completed', completed_at__year=today.year, completed_at__month=today.month))
    total_platform_revenue = sum((b.total_fee - b.counsellor_earnings) for b in CounsellorBooking.objects.filter(status='completed'))
    
    total_sessions = CounsellorBooking.objects.count()
    total_cancellations = BookingCancellation.objects.count()
    cancellation_rate = (total_cancellations / total_sessions * 100) if total_sessions > 0 else 0
    
    wallet_credits_issued = sum(tx.amount for tx in WalletTransaction.objects.filter(transaction_type__in=['compensation', 'refund']))
        
    return render(request, 'Mind_Mend/admin/revenue_dashboard.html', {
        'counsellor_data': counsellor_data,
        'today_revenue': today_revenue,
        'month_revenue': month_revenue,
        'total_platform_revenue': total_platform_revenue,
        'total_sessions': total_sessions,
        'cancellation_rate': cancellation_rate,
        'wallet_credits_issued': wallet_credits_issued,
    })

@staff_member_required
@require_http_methods(['GET'])
def admin_payout_history(request):
    """View showing all payouts ever made across the platform."""
    settlements = PayoutSettlement.objects.all().select_related('counsellor', 'settled_by').prefetch_related(
        'counsellor__bank_details'
    )
    
    return render(request, 'Mind_Mend/admin/settlement_history.html', {
        'settlements': settlements,
    })

@staff_member_required
@require_http_methods(['POST'])
def admin_update_settlement_reference(request, settlement_id):
    """Allows admin to attach a bank reference ID (NEFT/UPI) to a past payout."""
    settlement = get_object_or_404(PayoutSettlement, id=settlement_id)
    reference_id = request.POST.get('bank_reference_id', '').strip()
    
    if reference_id:
        settlement.bank_reference_id = reference_id
        settlement.save(update_fields=['bank_reference_id'])
        messages.success(request, f"Reference ID updated for settlement #{settlement.id}.")
    else:
        messages.error(request, "Reference ID cannot be empty.")
        
    return redirect('admin_payout_history')

@staff_member_required
@require_http_methods(['GET'])
def admin_disputes(request):
    disputes = SessionDispute.objects.filter(outcome='pending').select_related('booking', 'booking__counsellor', 'booking__user')
    return render(request, 'Mind_Mend/admin/disputes.html', {'disputes': disputes})

@staff_member_required
@require_http_methods(['POST'])
def admin_resolve_dispute(request, dispute_id):
    dispute = get_object_or_404(SessionDispute, id=dispute_id, outcome='pending')
    action = request.POST.get('action')
    admin_notes = request.POST.get('admin_notes', '').strip()
    
    with transaction.atomic():
        dispute.admin_notes = admin_notes
        dispute.resolved_at = timezone.now()
        
        booking = dispute.booking
        
        if action == 'patient_won':
            dispute.outcome = 'patient_won'
            booking.counsellor.trust_score -= 25 if booking.is_instant else 20
            booking.counsellor.save()
            
            wallet_used = booking.wallet_used
            bonus_used = booking.bonus_used
            razorpay_amount = booking.total_fee - (wallet_used + bonus_used)
            
            if razorpay_amount > 0 and booking.razorpay_payment_id:
                try:
                    import razorpay
                    from django.conf import settings
                    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                    client.refund.create({'payment_id': booking.razorpay_payment_id, 'amount': int(razorpay_amount * 100)})
                except Exception as e:
                    print(f"Razorpay Refund Error: {e}")
                    
            patient_profile, _ = UserProfile.objects.get_or_create(user=booking.user)
            if bonus_used > 0:
                add_bonus_credit(booking.user, bonus_used)
            patient_profile.wallet_balance += wallet_used
            patient_profile.bonus_balance += bonus_used
            patient_profile.save()
            
            if wallet_used > 0:
                WalletTransaction.objects.create(user=booking.user, amount=wallet_used, transaction_type='refund', description=f"Refund (Cash) for Dispute", reference_id=str(booking.id))
            if bonus_used > 0:
                WalletTransaction.objects.create(user=booking.user, amount=bonus_used, transaction_type='refund', description=f"Refund (Bonus) for Dispute", reference_id=str(booking.id))
                
            booking.status = 'cancelled'
            booking.cancelled_by = 'system'
            booking.cancellation_reason = 'Dispute resolved in favor of patient'
            booking.is_settled = True
            booking.is_disputed = False
            booking.save()
            messages.success(request, f"Dispute #{dispute.id} resolved in favor of Patient. Refund issued and Trust Score penalized.")
            
        elif action == 'counsellor_won':
            dispute.outcome = 'counsellor_won'
            booking.is_disputed = False
            booking.save(update_fields=['is_disputed'])
            messages.success(request, f"Dispute #{dispute.id} dismissed. Funds released for normal payout.")
            
        dispute.save()
        
    return redirect('admin_disputes')

@staff_member_required
@require_http_methods(['POST'])
def admin_mark_settled(request, counsellor_id):
    """Mark all pending bookings for a counsellor as settled, and deduct penalties."""
    counsellor = get_object_or_404(Counsellor, id=counsellor_id)
    current_time = timezone.now()
    
    with transaction.atomic():
        pending_bookings = CounsellorBooking.objects.filter(
            counsellor=counsellor, 
            status='completed', 
            is_settled=False
        )
        
        # Identify bookings to settle
        settle_bookings = []
        for b in pending_bookings:
            completion_time = b.completed_at or b.created_at
            if not b.is_disputed and completion_time and current_time >= completion_time + timedelta(hours=24):
                settle_bookings.append(b)
                
        total_settled = sum(b.counsellor_earnings for b in settle_bookings)
        count = len(settle_bookings)
                
        # Identify penalties to settle
        unsettled_cancellations = BookingCancellation.objects.filter(counsellor=counsellor).exclude(refund_status='Settled')
        total_penalties = sum(c.counsellor_penalty for c in unsettled_cancellations)
        
        gross_earnings = total_settled
        total_deductions = total_penalties + counsellor.outstanding_debt
        
        if gross_earnings >= total_deductions:
            net_settled = gross_earnings - total_deductions
            new_outstanding_debt = decimal.Decimal('0.00')
        else:
            net_settled = decimal.Decimal('0.00')
            new_outstanding_debt = total_deductions - gross_earnings
            
        # Only create settlement if there's actually something being settled (earnings or penalties)
        if count > 0 or total_penalties > 0:
            settlement = PayoutSettlement.objects.create(
                counsellor=counsellor,
                settled_by=request.user,
                gross_amount=gross_earnings,
                total_deductions=total_deductions,
                net_amount_paid=net_settled
            )
            
            # Link bookings
            for b in settle_bookings:
                b.is_settled = True
                b.payout_settlement = settlement
                b.save(update_fields=['is_settled', 'payout_settlement'])
                
            # Link cancellations
            unsettled_cancellations.update(refund_status='Settled', payout_settlement=settlement)
            
            counsellor.outstanding_debt = new_outstanding_debt
            counsellor.save(update_fields=['outstanding_debt'])
        
    messages.success(request, f"Successfully settled ₹{net_settled} ({count} sessions, {total_penalties} penalties) for {counsellor.name}. Outstanding debt: ₹{counsellor.outstanding_debt}.")
    return redirect('admin_revenue_dashboard')

@login_required
def patient_cancel_booking(request, booking_id):
    booking = get_object_or_404(CounsellorBooking, id=booking_id, user=request.user)
    
    if booking.status != 'confirmed':
        messages.error(request, 'Only confirmed bookings can be cancelled.')
        return redirect('my_bookings')
        
    if booking.is_instant:
        messages.error(request, 'Instant bookings cannot be cancelled.')
        return redirect('my_bookings')
        
    naive_dt = datetime.combine(booking.date, booking.time_slot)
    session_start = timezone.make_aware(naive_dt) if timezone.is_naive(naive_dt) else naive_dt
    current_time = timezone.now()
    
    hours_until_session = (session_start - current_time).total_seconds() / 3600
    
    if hours_until_session <= 0:
        messages.error(request, 'Cannot cancel a session that has already started.')
        return redirect('my_bookings')

    # Calculate exact refund
    refund_percentage = 0.0
    if hours_until_session > 24:
        refund_percentage = 1.0
    elif 12 < hours_until_session <= 24:
        refund_percentage = 0.80 if booking.include_video else 0.90
    elif 6 < hours_until_session <= 12:
        refund_percentage = 0.60
    else:
        refund_percentage = 0.40
        
    total_refund_amount = round(booking.total_fee * decimal.Decimal(refund_percentage), 2)
    counsellor_compensation = booking.total_fee - total_refund_amount

    if request.method == 'POST':
        reason = request.POST.get('reason', 'Cancelled by patient').strip()
        
        with transaction.atomic():
            booking.status = 'cancelled'
            booking.cancelled_by = 'patient'
            booking.cancellation_reason = reason
            
            if counsellor_compensation > 0:
                booking.counsellor_earnings = round(counsellor_compensation * decimal.Decimal('0.90'), 2)
                
            booking.save()
            
            # Process refunds
            wallet_used = booking.wallet_used
            bonus_used = booking.bonus_used
            
            bonus_refund = min(bonus_used, total_refund_amount)
            remaining_refund = total_refund_amount - bonus_refund
            
            wallet_refund = min(wallet_used, remaining_refund)
            razorpay_refund_pool = remaining_refund - wallet_refund
            
            if razorpay_refund_pool > 0 and booking.razorpay_payment_id:
                platform_fee = round(razorpay_refund_pool * decimal.Decimal('0.05'), 2)
                actual_razorpay_refund = razorpay_refund_pool - platform_fee
                if actual_razorpay_refund > 0:
                    try:
                        import razorpay
                        from django.conf import settings
                        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                        client.refund.create({'payment_id': booking.razorpay_payment_id, 'amount': int(actual_razorpay_refund * 100)})
                    except Exception as e:
                        print(f"Razorpay Refund Error: {e}")
                        
            if wallet_refund > 0 or bonus_refund > 0:
                patient_profile, _ = UserProfile.objects.get_or_create(user=booking.user)
                if wallet_refund > 0:
                    patient_profile.wallet_balance += wallet_refund
                    WalletTransaction.objects.create(
                        user=booking.user,
                        amount=wallet_refund,
                        transaction_type='refund',
                        description=f"Refund (Cash) for cancelled session with {booking.counsellor.name}",
                        reference_id=str(booking.id)
                    )
                if bonus_refund > 0:
                    add_bonus_credit(booking.user, bonus_refund)
                    patient_profile.bonus_balance += bonus_refund
                    WalletTransaction.objects.create(
                        user=booking.user,
                        amount=bonus_refund,
                        transaction_type='refund',
                        description=f"Refund (Bonus) for cancelled session with {booking.counsellor.name}",
                        reference_id=str(booking.id)
                    )
                patient_profile.save()
                
            BookingCancellation.objects.create(
                booking=booking,
                counsellor=booking.counsellor,
                reason=reason,
                message_to_patient="You cancelled this session.",
                compensation_credited=decimal.Decimal('0.00'),
                counsellor_penalty=decimal.Decimal('0.00'),
                refund_status='Initiated'
            )
            
            CounsellorNotification.objects.create(
                counsellor=booking.counsellor,
                booking=booking,
                actor=request.user,
                event_type='booking_status',
                title='Session Cancelled by Patient',
                body=f"Patient cancelled the session {round(hours_until_session, 1)} hours before start. You retained ₹{booking.counsellor_earnings} of the fee."
            )
            
            messages.success(request, f"Session cancelled successfully. ₹{total_refund_amount} has been processed for refund.")
            return redirect('my_bookings')
            
    return render(request, 'Mind_Mend/counsellor/patient_cancel_confirm.html', {
        'booking': booking,
        'hours': hours_until_session,
        'refund_amount': total_refund_amount,
        'refund_percentage': refund_percentage * 100
    })

@login_required
@require_http_methods(['POST'])
def report_counsellor_no_show(request, booking_id):
    booking = get_object_or_404(CounsellorBooking, id=booking_id, user=request.user)
    
    if booking.status != 'confirmed':
        messages.error(request, 'Only confirmed bookings can be marked as No-Show.')
        return redirect('my_bookings')
        
    naive_dt = datetime.combine(booking.date, booking.time_slot)
    session_start = timezone.make_aware(naive_dt) if timezone.is_naive(naive_dt) else naive_dt
    current_time = timezone.now()
    
    if current_time < session_start + timedelta(minutes=15):
        messages.error(request, 'You must wait 15 minutes after the scheduled start time.')
        return redirect('counsellor_chat', booking_id=booking.id)
        
    with transaction.atomic():
        booking.status = 'cancelled'
        booking.cancelled_by = 'system'
        booking.cancellation_reason = 'Counsellor No-Show reported by patient.'
        booking.is_no_show = True
        booking.save()
        
        # Deduct Trust Score
        booking.counsellor.trust_score -= 25 if booking.is_instant else 20
        booking.counsellor.save()
        
        # Penalty calculation
        penalty_percent = 0.30 if booking.is_instant else 0.25
        compensation = round(booking.total_fee * decimal.Decimal(penalty_percent), 2)
        
        wallet_used = booking.wallet_used
        bonus_used = booking.bonus_used
        razorpay_amount = booking.total_fee - (wallet_used + bonus_used)
        
        if razorpay_amount > 0 and booking.razorpay_payment_id:
            try:
                import razorpay
                from django.conf import settings
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                client.refund.create({'payment_id': booking.razorpay_payment_id, 'amount': int(razorpay_amount * 100)})
            except Exception as e:
                print(f"Razorpay Refund Error: {e}")
                
        patient_profile, _ = UserProfile.objects.get_or_create(user=booking.user)
        if (bonus_used + compensation) > 0:
            add_bonus_credit(booking.user, bonus_used + compensation)
        patient_profile.wallet_balance += wallet_used
        patient_profile.bonus_balance += (bonus_used + compensation)
        patient_profile.save()
        
        if wallet_used > 0:
            WalletTransaction.objects.create(user=booking.user, amount=wallet_used, transaction_type='refund', description=f"Refund (Cash) for No-Show", reference_id=str(booking.id))
        if bonus_used > 0:
            WalletTransaction.objects.create(user=booking.user, amount=bonus_used, transaction_type='refund', description=f"Refund (Bonus) for No-Show", reference_id=str(booking.id))
            
        WalletTransaction.objects.create(user=booking.user, amount=compensation, transaction_type='compensation', description=f"Compensation for Counsellor No-Show", reference_id=str(booking.id))
        
        BookingCancellation.objects.create(
            booking=booking, counsellor=booking.counsellor, reason='Counsellor No-Show',
            message_to_patient="We apologize for the counsellor's absence. A full refund + compensation has been processed.",
            compensation_credited=compensation, counsellor_penalty=compensation, refund_status='Initiated'
        )
        
    messages.success(request, f"Counsellor No-Show recorded. You have received a full refund + ₹{compensation} compensation.")
    return redirect('my_bookings')

@login_required
@require_http_methods(['POST'])
def raise_dispute(request, booking_id):
    booking = get_object_or_404(CounsellorBooking, id=booking_id, user=request.user)
    
    if booking.status != 'completed':
        messages.error(request, "You can only dispute completed sessions.")
        return redirect('my_bookings')
        
    if booking.is_settled:
        messages.error(request, "This session has already been fully settled and can no longer be disputed.")
        return redirect('my_bookings')
        
    if not booking.is_dispute_window_open:
        messages.error(request, "The 24-hour dispute window has closed for this session.")
        return redirect('my_bookings')
        
    if booking.is_disputed:
        messages.info(request, "This session is already under dispute.")
        return redirect('my_bookings')
        
    reason = request.POST.get('reason', '').strip()
    if not reason:
        messages.error(request, "You must provide a reason for the dispute.")
        return redirect('my_bookings')
        
    with transaction.atomic():
        booking.is_disputed = True
        booking.save(update_fields=['is_disputed'])
        
        SessionDispute.objects.create(
            booking=booking,
            patient_reason=reason
        )
        
    messages.success(request, "Your dispute has been raised. Payouts have been frozen while our admin team reviews your case.")
    return redirect('my_bookings')

@login_required
@require_http_methods(['POST'])
def mark_patient_no_show(request, booking_id):
    booking = get_object_or_404(CounsellorBooking, id=booking_id)
    if not hasattr(request.user, 'counsellor') or request.user.counsellor != booking.counsellor:
        return redirect('doctor_dashboard')
        
    if booking.status != 'confirmed':
        messages.error(request, 'Only confirmed bookings can be marked as No-Show.')
        return redirect('doctor_dashboard')
        
    naive_dt = datetime.combine(booking.date, booking.time_slot)
    session_start = timezone.make_aware(naive_dt) if timezone.is_naive(naive_dt) else naive_dt
    current_time = timezone.now()
    
    if current_time < session_start + timedelta(minutes=20):
        messages.error(request, 'You must wait 20 minutes after the scheduled start time.')
        return redirect('counsellor_chat', booking_id=booking.id)
        
    with transaction.atomic():
        booking.status = 'completed'
        booking.completed_at = current_time
        booking.is_no_show = True
        booking.counsellor_earnings = round((booking.total_fee - booking.platform_fee) * decimal.Decimal('0.90'), 2)
        booking.save()
        
    messages.success(request, "Patient marked as No-Show. Your earnings have been processed.")
    return redirect('doctor_dashboard')

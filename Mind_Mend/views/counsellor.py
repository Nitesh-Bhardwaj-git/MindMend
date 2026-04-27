import json
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

from ..models import Counsellor, CounsellorBooking, CounsellorChatMessage, CounsellorReview, CounsellorNotification
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



@login_required
def counsellor_booking(request):
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
            booking.save()

            if booking.counsellor.session_fee > 0:
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
        form = CounsellorBookingForm(initial={'date': timezone.localdate()})

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
        }
        for c in counsellors
    ])

    return render(request, 'Mind_Mend/counsellor/counsellor_booking.html', {
        'form': form,
        'counsellors': counsellors,
        'counsellors_json': counsellors_json,
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
    """Live chat with counsellor for a booking. User or counsellor can access."""
    booking = get_object_or_404(CounsellorBooking, pk=booking_id)
    if not _user_can_access_booking(request.user, booking):
        messages.error(request, 'You do not have access to this chat.')
        return redirect('my_bookings')
    chat_messages = list(CounsellorChatMessage.objects.filter(booking=booking).select_related('sender').order_by('created_at'))
    for msg in chat_messages:
        msg.sender_label = _chat_sender_name(booking, msg.sender)
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
                    f'{_booking_patient_name(booking)}: {content[:120]}',
                    booking=booking,
                    actor=request.user
                )
        return redirect('counsellor_chat', booking_id=booking.pk)
    return render(request, 'Mind_Mend/counsellor/counsellor_chat.html', {
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
    return render(request, 'Mind_Mend/counsellor/counsellor_sessions.html', {'bookings': bookings, 'counsellor': counsellor})


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
    
    today_date = timezone.localdate()
    today_bookings_count = len([b for b in bookings if b.date == today_date])
    pending_count = len([b for b in bookings if b.status == 'pending'])
    completed_bookings = [b for b in bookings if b.status == 'completed']
    total_completed_sessions = len(completed_bookings)
    monthly_revenue = sum(
        b.counsellor.session_fee for b in completed_bookings 
        if b.is_paid and b.date.month == today_date.month and b.date.year == today_date.year
    )

    return render(request, 'Mind_Mend/counsellor/doctor_dashboard.html', {
        'counsellor': counsellor,
        'pending_bookings': [b for b in bookings if b.status == 'pending'],
        'bookings': bookings,
        'notifications': notifications_qs[:20],
        'unread_count': notifications_qs.filter(is_read=False).count(),
        'today_bookings_count': today_bookings_count,
        'pending_count': pending_count,
        'total_completed_sessions': total_completed_sessions,
        'monthly_revenue': monthly_revenue,
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
    _cleanup_expired_pending_bookings()

    import razorpay
    from django.conf import settings

    booking = get_object_or_404(CounsellorBooking, pk=booking_id, user=request.user)

    if booking.is_paid or booking.status != 'pending':
        messages.info(request, "This booking has already been processed.")
        return redirect('my_bookings')

    if request.method == 'POST':
        return redirect('checkout_payment', booking_id=booking_id)

    # Amount in paise (Razorpay requires smallest currency unit)
    amount_paise = int(booking.counsellor.session_fee * 100)

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )
    razorpay_order = client.order.create({
        'amount': amount_paise,
        'currency': 'INR',
        'payment_capture': 1,
        'receipt': f"booking_{booking.id}",  # Traceable ID for Dashboard
        'notes': {
            'booking_id': booking.id,
            'user_id': request.user.id,
        },
    })

    return render(request, 'Mind_Mend/counsellor/payment.html', {
        'booking': booking,
        'razorpay_order_id': razorpay_order['id'],
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
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
    booking.is_paid = True
    booking.status  = 'confirmed'
    booking.save(update_fields=['is_paid', 'status'])

    _notify_counsellor(
        booking.counsellor,
        'booking_created',
        'New appointment booked',
        f'{_booking_patient_name(booking)} booked {booking.date} at {booking.time_slot.strftime("%H:%M")}.',
        booking=booking,
        actor=request.user
    )

    messages.success(request, "Payment successful! Your appointment is confirmed.")
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

    booked_slots.sort(key=lambda s: s['start'])
    return JsonResponse({'booked_slots': booked_slots})


def how_to_book(request):
    """Static guide page explaining how to book a session."""
    return render(request, 'Mind_Mend/counsellor/how_to_book.html')

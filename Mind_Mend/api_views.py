"""REST API views for the MindMend Android app."""
import json
from django.contrib.auth import authenticate
from django.db.models import Avg, Count
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from .models import (
    Counsellor, CounsellorBooking, CounsellorChatMessage,
    CounsellorReview, MoodEntry, ForumPost, ForumReply,
    AssessmentResult, ContactMessage, ChatMessage, UserMemory,
)
from .serializers import (
    RegisterSerializer, UserSerializer,
    CounsellorSerializer, BookingSerializer, BookingCreateSerializer,
    ChatMessageSerializer, ReviewSerializer,
    MoodEntrySerializer,
    ForumPostSerializer, ForumPostCreateSerializer, ForumReplySerializer,
    AssessmentResultSerializer, AssessmentSubmitSerializer,
    ContactMessageSerializer,
)
from .assessment_data import (
    PHQ9_QUESTIONS, GAD7_QUESTIONS, PSS_QUESTIONS,
    get_phq9_result, get_gad7_result, get_pss_result, PSS_REVERSE_ITEMS,
)
from .services import get_chat_response, get_session_id


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([AllowAny])
def api_register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user': UserSerializer(user).data,
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def api_login(request):
    username = request.data.get('username', '')
    password = request.data.get('password', '')
    user = authenticate(username=username, password=password)
    if not user:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({
        'token': token.key,
        'user': UserSerializer(user).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_me(request):
    return Response(UserSerializer(request.user).data)


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_dashboard(request):
    user = request.user

    # Mood data (last 7)
    moods = MoodEntry.objects.filter(user=user).order_by('-date')[:7]
    mood_data = [{'date': str(m.date), 'mood': m.mood} for m in reversed(moods)]

    # Latest assessment scores
    assessments = AssessmentResult.objects.filter(user=user).order_by('-created_at')[:5]

    # Upcoming appointment
    from django.utils import timezone
    upcoming = CounsellorBooking.objects.filter(
        user=user, status__in=['pending', 'confirmed'],
        date__gte=timezone.now().date()
    ).select_related('counsellor').order_by('date', 'time_slot').first()

    upcoming_data = None
    if upcoming:
        upcoming_data = {
            'id': upcoming.id,
            'counsellor_name': upcoming.counsellor.name,
            'date': str(upcoming.date),
            'time_slot': upcoming.time_slot.strftime('%H:%M'),
            'status': upcoming.status,
        }

    # Mental health score (simple formula)
    avg_mood = MoodEntry.objects.filter(user=user).order_by('-date')[:30].aggregate(Avg('mood'))['mood__avg']
    score = int((avg_mood or 0) * 20)

    return Response({
        'mental_health_score': score,
        'mood_data': mood_data,
        'assessments': AssessmentResultSerializer(assessments, many=True).data,
        'upcoming_appointment': upcoming_data,
    })


# ══════════════════════════════════════════════════════════════════════════════
#  COUNSELLORS & BOOKINGS
# ══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([AllowAny])
def api_counsellors(request):
    qs = Counsellor.objects.filter(is_active=True).annotate(
        avg_rating=Avg('counsellorbooking__counsellorreview__rating')
    )
    return Response(CounsellorSerializer(qs, many=True).data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_bookings(request):
    if request.method == 'GET':
        qs = CounsellorBooking.objects.filter(user=request.user).select_related('counsellor').order_by('-date')
        return Response(BookingSerializer(qs, many=True).data)

    serializer = BookingCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    booking = serializer.save(user=request.user)
    return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_booking_action(request, booking_id):
    booking = CounsellorBooking.objects.filter(pk=booking_id).first()
    if not booking:
        return Response({'error': 'Not found'}, status=404)
    action = request.data.get('action')
    if action == 'confirm':
        booking.status = 'confirmed'
    elif action == 'cancel':
        booking.status = 'cancelled'
    elif action == 'complete':
        booking.status = 'completed'
    else:
        return Response({'error': 'Invalid action'}, status=400)
    booking.save(update_fields=['status'])
    return Response(BookingSerializer(booking).data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_booking_messages(request, booking_id):
    booking = CounsellorBooking.objects.filter(pk=booking_id).first()
    if not booking:
        return Response({'error': 'Not found'}, status=404)
    if request.method == 'GET':
        msgs = CounsellorChatMessage.objects.filter(booking=booking).select_related('sender').order_by('created_at')
        return Response(ChatMessageSerializer(msgs, many=True).data)
    content = request.data.get('content', '').strip()
    if not content:
        return Response({'error': 'Empty message'}, status=400)
    msg = CounsellorChatMessage.objects.create(booking=booking, sender=request.user, content=content)
    return Response(ChatMessageSerializer(msg).data, status=201)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_submit_review(request, booking_id):
    booking = CounsellorBooking.objects.filter(pk=booking_id, user=request.user).first()
    if not booking:
        return Response({'error': 'Not found'}, status=404)
    if CounsellorReview.objects.filter(booking=booking).exists():
        return Response({'error': 'Review already exists'}, status=400)
    serializer = ReviewSerializer(data={**request.data, 'booking': booking.id})
    serializer.is_valid(raise_exception=True)
    serializer.save(user=request.user)
    return Response(serializer.data, status=201)


# ══════════════════════════════════════════════════════════════════════════════
#  MOOD
# ══════════════════════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def api_moods(request):
    if request.method == 'GET':
        qs = MoodEntry.objects.filter(user=request.user).order_by('-date')[:30]
        return Response(MoodEntrySerializer(qs, many=True).data)
    serializer = MoodEntrySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(user=request.user)
    return Response(serializer.data, status=201)


# ══════════════════════════════════════════════════════════════════════════════
#  FORUM
# ══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([AllowAny])
def api_forum_posts(request):
    category = request.query_params.get('category', '')
    qs = ForumPost.objects.all().annotate(reply_count=Count('forumreply')).order_by('-created_at')
    if category:
        qs = qs.filter(category=category)
    return Response(ForumPostSerializer(qs[:50], many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_forum_create(request):
    serializer = ForumPostCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(author=request.user)
    return Response(serializer.data, status=201)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_forum_detail(request, pk):
    post = ForumPost.objects.filter(pk=pk).annotate(reply_count=Count('forumreply')).first()
    if not post:
        return Response({'error': 'Not found'}, status=404)
    replies = ForumReply.objects.filter(post=post).order_by('created_at')
    return Response({
        'post': ForumPostSerializer(post).data,
        'replies': ForumReplySerializer(replies, many=True).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_forum_reply(request, pk):
    post = ForumPost.objects.filter(pk=pk).first()
    if not post:
        return Response({'error': 'Not found'}, status=404)
    serializer = ForumReplySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(post=post, author=request.user)
    return Response(serializer.data, status=201)


# ══════════════════════════════════════════════════════════════════════════════
#  ASSESSMENTS
# ══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_assessments(request):
    qs = AssessmentResult.objects.filter(user=request.user).order_by('-created_at')[:20]
    return Response(AssessmentResultSerializer(qs, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_assessment_submit(request):
    serializer = AssessmentSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    atype = serializer.validated_data['assessment_type']
    answers = serializer.validated_data['answers']

    if atype == 'phq9':
        total = sum(answers.get(f'q{i}', 0) for i in range(len(PHQ9_QUESTIONS)))
        result_level = get_phq9_result(total)
        max_score = 27
    elif atype == 'gad7':
        total = sum(answers.get(f'q{i}', 0) for i in range(len(GAD7_QUESTIONS)))
        result_level = get_gad7_result(total)
        max_score = 21
    else:  # pss
        raw = [answers.get(f'q{i}', 0) for i in range(len(PSS_QUESTIONS))]
        result_level = get_pss_result(raw)
        total = sum((4 - a) if (i + 1) in PSS_REVERSE_ITEMS else a for i, a in enumerate(raw))
        max_score = 40

    result = AssessmentResult.objects.create(
        user=request.user,
        assessment_type=atype,
        total_score=total,
        result_level=result_level,
        answers=answers,
    )
    return Response({
        'id': result.id,
        'assessment_type': atype,
        'total_score': total,
        'max_score': max_score,
        'result_level': result_level,
    }, status=201)


# ══════════════════════════════════════════════════════════════════════════════
#  AI CHAT
# ══════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([AllowAny])
def api_chat(request):
    message = request.data.get('message', '').strip()
    session_id = request.data.get('session_id') or get_session_id()
    lang = request.data.get('lang', 'en')

    if not message:
        return Response({'error': 'Empty message'}, status=400)

    user = request.user if request.user.is_authenticated else None

    if user:
        recent = list(ChatMessage.objects.filter(user=user).order_by('-created_at')[:20])
    else:
        recent = list(ChatMessage.objects.filter(session_id=session_id, user__isnull=True).order_by('-created_at')[:20])
    recent.reverse()
    history = [{'role': m.role, 'content': m.content} for m in recent]

    try:
        result = get_chat_response(message, session_id, lang=lang, conversation_history=history, context={})
        response_text = (result.get('response') or '').strip() or 'I am here for you.'
        sentiment = result.get('sentiment', 'neutral')
        is_distress = result.get('is_distress', False)
        recommendations = result.get('recommendations', [])
    except Exception:
        response_text = 'I am here with you. Tell me more about what feels hardest right now.'
        sentiment = 'neutral'
        is_distress = False
        recommendations = []

    ChatMessage.objects.create(user=user, session_id=session_id, role='user', content=message)
    ChatMessage.objects.create(user=user, session_id=session_id, role='assistant', content=response_text, sentiment=sentiment)

    return Response({
        'response': response_text,
        'sentiment': sentiment,
        'is_distress': is_distress,
        'recommendations': recommendations,
        'session_id': session_id,
    })


# ══════════════════════════════════════════════════════════════════════════════
#  CONTACT
# ══════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([AllowAny])
def api_contact(request):
    serializer = ContactMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response({'ok': True}, status=201)

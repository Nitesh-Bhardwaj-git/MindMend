"""DRF serializers for the MindMend mobile API."""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Counsellor, CounsellorBooking, CounsellorChatMessage,
    CounsellorReview, MoodEntry, ForumPost, ForumReply,
    AssessmentResult, ChatMessage, ContactMessage,
)


# ─── Auth ────────────────────────────────────────────────────────────────────

class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('Username already exists.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Email already registered.')
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
        )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


# ─── Counsellor ──────────────────────────────────────────────────────────────

class CounsellorSerializer(serializers.ModelSerializer):
    avg_rating = serializers.FloatField(read_only=True, required=False)

    class Meta:
        model = Counsellor
        fields = [
            'id', 'name', 'specialization', 'bio',
            'available_days', 'available_time_start', 'available_time_end',
            'is_active', 'avg_rating',
        ]


class BookingSerializer(serializers.ModelSerializer):
    counsellor_name = serializers.CharField(source='counsellor.name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = CounsellorBooking
        fields = [
            'id', 'counsellor', 'counsellor_name', 'username',
            'date', 'time_slot', 'notes', 'status', 'created_at',
        ]
        read_only_fields = ['status', 'created_at']


class BookingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CounsellorBooking
        fields = ['counsellor', 'date', 'time_slot', 'notes']


class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.username', read_only=True)

    class Meta:
        model = CounsellorChatMessage
        fields = ['id', 'sender', 'sender_name', 'content', 'created_at']
        read_only_fields = ['sender', 'created_at']


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = CounsellorReview
        fields = ['id', 'booking', 'rating', 'review_text', 'created_at']
        read_only_fields = ['created_at']


# ─── Mood ────────────────────────────────────────────────────────────────────

class MoodEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = MoodEntry
        fields = ['id', 'mood', 'energy_level', 'activities', 'notes', 'date', 'created_at']
        read_only_fields = ['created_at']


# ─── Forum ───────────────────────────────────────────────────────────────────

class ForumReplySerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = ForumReply
        fields = ['id', 'content', 'is_anonymous', 'author_name', 'created_at']
        read_only_fields = ['created_at']

    def get_author_name(self, obj):
        if obj.is_anonymous or not obj.author:
            return 'Anonymous'
        return obj.author.username


class ForumPostSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    reply_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = ForumPost
        fields = [
            'id', 'category', 'title', 'content', 'is_anonymous',
            'author_name', 'reply_count', 'created_at',
        ]
        read_only_fields = ['created_at']

    def get_author_name(self, obj):
        if obj.is_anonymous or not obj.author:
            return 'Anonymous'
        return obj.author.username


class ForumPostCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ForumPost
        fields = ['category', 'title', 'content', 'is_anonymous']


# ─── Assessments ─────────────────────────────────────────────────────────────

class AssessmentResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentResult
        fields = ['id', 'assessment_type', 'total_score', 'result_level', 'answers', 'created_at']
        read_only_fields = ['created_at']


class AssessmentSubmitSerializer(serializers.Serializer):
    assessment_type = serializers.ChoiceField(choices=['phq9', 'gad7', 'pss'])
    answers = serializers.DictField(child=serializers.IntegerField())


# ─── Contact ─────────────────────────────────────────────────────────────────

class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']

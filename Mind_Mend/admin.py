from django.contrib import admin
from .models import (
    Counsellor, CounsellorBooking, CounsellorChatMessage, CounsellorReview,
    MoodEntry, SleepLog, ForumPost, ForumReply, AssessmentResult, ChatMessage, UserAccessLocation
)


@admin.register(Counsellor)
class CounsellorAdmin(admin.ModelAdmin):
    list_display = ['name', 'specialization', 'is_active', 'available_days']


@admin.register(CounsellorBooking)
class CounsellorBookingAdmin(admin.ModelAdmin):
    list_display = ['user', 'counsellor', 'date', 'time_slot', 'status']


@admin.register(CounsellorChatMessage)
class CounsellorChatMessageAdmin(admin.ModelAdmin):
    list_display = ['booking', 'sender', 'created_at']


@admin.register(CounsellorReview)
class CounsellorReviewAdmin(admin.ModelAdmin):
    list_display = ['booking', 'user', 'rating', 'created_at']


@admin.register(MoodEntry)
class MoodEntryAdmin(admin.ModelAdmin):
    list_display = ['user', 'mood', 'energy_level', 'activities', 'date', 'created_at']


@admin.register(SleepLog)
class SleepLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'quality', 'hours', 'created_at']


@admin.register(ForumPost)
class ForumPostAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'is_anonymous', 'is_approved', 'created_at']


@admin.register(ForumReply)
class ForumReplyAdmin(admin.ModelAdmin):
    list_display = ['post', 'author', 'is_anonymous', 'created_at']


@admin.register(AssessmentResult)
class AssessmentResultAdmin(admin.ModelAdmin):
    list_display = ['user', 'assessment_type', 'total_score', 'result_level', 'created_at']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['user', 'session_id', 'role', 'created_at']


@admin.register(UserAccessLocation)
class UserAccessLocationAdmin(admin.ModelAdmin):
    list_display = ['user', 'country', 'state', 'city', 'ip_address', 'page_path', 'created_at']
    list_filter = ['country', 'created_at']

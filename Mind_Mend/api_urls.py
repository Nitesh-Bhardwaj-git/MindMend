"""API URL routes for the MindMend mobile app."""
from django.urls import path
from . import api_views

urlpatterns = [
    # Auth
    path('auth/register/', api_views.api_register, name='api_register'),
    path('auth/login/', api_views.api_login, name='api_login'),
    path('auth/me/', api_views.api_me, name='api_me'),

    # Dashboard
    path('dashboard/', api_views.api_dashboard, name='api_dashboard'),

    # Counsellors & Bookings
    path('counsellors/', api_views.api_counsellors, name='api_counsellors'),
    path('bookings/', api_views.api_bookings, name='api_bookings'),
    path('bookings/<int:booking_id>/action/', api_views.api_booking_action, name='api_booking_action'),
    path('bookings/<int:booking_id>/messages/', api_views.api_booking_messages, name='api_booking_messages'),
    path('bookings/<int:booking_id>/review/', api_views.api_submit_review, name='api_submit_review'),

    # Mood
    path('moods/', api_views.api_moods, name='api_moods'),

    # Forum
    path('forum/', api_views.api_forum_posts, name='api_forum_posts'),
    path('forum/create/', api_views.api_forum_create, name='api_forum_create'),
    path('forum/<int:pk>/', api_views.api_forum_detail, name='api_forum_detail'),
    path('forum/<int:pk>/reply/', api_views.api_forum_reply, name='api_forum_reply'),

    # Assessments
    path('assessments/', api_views.api_assessments, name='api_assessments'),
    path('assessments/submit/', api_views.api_assessment_submit, name='api_assessment_submit'),

    # AI Chat
    path('chat/', api_views.api_chat, name='api_chat_endpoint'),

    # Contact
    path('contact/', api_views.api_contact, name='api_contact'),
]

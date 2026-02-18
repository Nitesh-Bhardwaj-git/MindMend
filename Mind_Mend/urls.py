from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('doctor/login/', views.doctor_login_view, name='doctor_login'),
    path('logout/', views.logout_view, name='logout'),

    # AI Chatbot
    path('chat/', views.chat, name='chat'),
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/share-location/', views.share_location_api, name='share_location_api'),

    # Assessments
    path('assessments/', views.assessments_home, name='assessments'),
    path('assessments/phq9/', views.assessment_phq9, name='assessment_phq9'),
    path('assessments/gad7/', views.assessment_gad7, name='assessment_gad7'),
    path('assessments/pss/', views.assessment_pss, name='assessment_pss'),

    # Forum & Community (anonymous support, peer-to-peer, recovery stories)
    path('forum/', views.forum_list, name='forum_list'),
    path('forum/recovery/', views.recovery_stories, name='recovery_stories'),
    path('forum/new/', views.forum_create, name='forum_create'),
    path('forum/<int:pk>/', views.forum_detail, name='forum_detail'),
    path('forum/<int:pk>/reply/', views.forum_reply, name='forum_reply'),

    # Counsellor Booking
    path('book/', views.counsellor_booking, name='counsellor_booking'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('counsellor/sessions/', views.counsellor_sessions, name='counsellor_sessions'),
    path('doctor/dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/booking/<int:booking_id>/action/', views.doctor_booking_action, name='doctor_booking_action'),
    path('booking/<int:booking_id>/chat/', views.counsellor_chat, name='counsellor_chat'),
    path('booking/<int:booking_id>/finish/', views.finish_session, name='finish_session'),
    path('api/booking/<int:booking_id>/messages/', views.booking_messages_api, name='booking_messages_api'),
    path('api/doctor/notifications/', views.doctor_notifications_api, name='doctor_notifications_api'),
    path('api/doctor/notifications/mark-read/', views.doctor_notifications_mark_read_api, name='doctor_notifications_mark_read_api'),
    path('booking/<int:booking_id>/review/', views.submit_review, name='submit_review'),

    # Mood
    path('mood/', views.mood_tracker, name='mood_tracker'),

    # Forum & Community
    path('forum/recovery/', views.recovery_stories, name='recovery_stories'),

    # Resources & Helplines
    path('resources/', views.resources, name='resources'),

    # Contact
    path('contact/', views.contact_us, name='contact_us'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    path('my-progress/', views.my_progress, name='my_progress'),
    path('survey-analytics/', views.survey_analytics, name='survey_analytics'),
    path('survey-sentiment/', views.survey_sentiment_dashboard, name='survey_sentiment_dashboard'),
    path('my-progress/report.pdf', views.download_progress_report_pdf, name='download_progress_report_pdf'),

    # Location Map (staff only)
    path('location-map/', views.location_map, name='location_map'),

    # Mental Health Heatmap (staff only)
    path('mental-health-heatmap/', views.mental_health_heatmap, name='mental_health_heatmap'),
]

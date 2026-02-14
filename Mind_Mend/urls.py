from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
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

    # Forum
    path('forum/', views.forum_list, name='forum_list'),
    path('forum/new/', views.forum_create, name='forum_create'),
    path('forum/<int:pk>/', views.forum_detail, name='forum_detail'),
    path('forum/<int:pk>/reply/', views.forum_reply, name='forum_reply'),

    # Counsellor Booking
    path('book/', views.counsellor_booking, name='counsellor_booking'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),

    # Mood Tracking
    path('mood/', views.mood_tracker, name='mood_tracker'),

    # Resources & Helplines
    path('resources/', views.resources, name='resources'),

    # Contact
    path('contact/', views.contact_us, name='contact_us'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Location Map (staff only)
    path('location-map/', views.location_map, name='location_map'),

    # Mental Health Heatmap (staff only)
    path('mental-health-heatmap/', views.mental_health_heatmap, name='mental_health_heatmap'),
]

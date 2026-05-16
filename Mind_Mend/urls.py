from django.urls import path
from .views import auth, core, assessments, forum, counsellor, analytics

urlpatterns = [
    path('', core.home, name='home'),
    path('privacy/', core.privacy_policy, name='privacy_policy'),
    path('register/', auth.register, name='register'),
    path('verify-email/', auth.verify_otp, name='verify_otp'),
    path('resend-otp/', auth.resend_otp, name='resend_otp'),
    path('login/', auth.login_view, name='login'),
    
    # Password Reset
    path('forgot-password/', auth.forgot_password, name='forgot_password'),
    path('forgot-password/verify/', auth.verify_reset_otp, name='verify_reset_otp'),
    path('forgot-password/reset/', auth.set_new_password, name='set_new_password'),
    
    path('doctor/login/', auth.doctor_login_view, name='doctor_login'),
    path('logout/', auth.logout_view, name='logout'),
    path('profile/', auth.user_profile, name='user_profile'),
    path('profile/delete-data/', auth.delete_my_data, name='delete_my_data'),
    path('profile/delete-account/', auth.delete_my_account, name='delete_my_account'),

    # AI Chatbot
    path('chat/', core.chat, name='chat'),
    path('api/chat/', core.chat_api, name='chat_api'),
    path('api/chat/transliterate/', core.transliterate_api, name='transliterate_api'),
    path('api/share-location/', core.share_location_api, name='share_location_api'),

    # Assessments
    path('assessments/', assessments.assessments_home, name='assessments'),
    path('assessments/phq9/', assessments.assessment_phq9, name='assessment_phq9'),
    path('assessments/gad7/', assessments.assessment_gad7, name='assessment_gad7'),
    path('assessments/pss/', assessments.assessment_pss, name='assessment_pss'),
    path('assessments/result/<int:result_id>/', assessments.assessment_result, name='assessment_result'),

    # Forum & Community (anonymous support, peer-to-peer, recovery stories)
    path('forum/', forum.forum_list, name='forum_list'),
    path('forum/recovery/', forum.recovery_stories, name='recovery_stories'),
    path('forum/new/', forum.forum_create, name='forum_create'),
    path('forum/<int:pk>/', forum.forum_detail, name='forum_detail'),
    path('forum/<int:pk>/reply/', forum.forum_reply, name='forum_reply'),

    # Counsellor Booking
    path('book/', counsellor.counsellor_booking, name='counsellor_booking'),
    path('book/how-to/', counsellor.how_to_book, name='how_to_book'),
    path('my-bookings/', counsellor.my_bookings, name='my_bookings'),
    path('counsellor/sessions/', counsellor.counsellor_sessions, name='counsellor_sessions'),
    path('doctor/dashboard/', counsellor.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/booking/<int:booking_id>/action/', counsellor.doctor_booking_action, name='doctor_booking_action'),
    path('booking/<int:booking_id>/chat/', counsellor.counsellor_chat, name='counsellor_chat'),
    path('booking/<int:booking_id>/finish/', counsellor.finish_session, name='finish_session'),
    path('booking/<int:booking_id>/cancel/', counsellor.booking_action, name='booking_action'),
    path('booking/<int:booking_id>/delete/', counsellor.delete_booking, name='delete_booking'),
    path('api/booking/<int:booking_id>/messages/', counsellor.booking_messages_api, name='booking_messages_api'),
    path('api/doctor/notifications/', counsellor.doctor_notifications_api, name='doctor_notifications_api'),
    path('api/doctor/notifications/mark-read/', counsellor.doctor_notifications_mark_read_api, name='doctor_notifications_mark_read_api'),
    path('booking/<int:booking_id>/review/', counsellor.submit_review, name='submit_review'),
    path('payment/<int:booking_id>/', counsellor.checkout_payment, name='checkout_payment'),
    path('payment/<int:booking_id>/verify/', counsellor.razorpay_payment_verify, name='razorpay_payment_verify'),
    path('payment/webhook/', counsellor.razorpay_webhook, name='razorpay_webhook'),
    path('api/counsellor/<int:counsellor_id>/booked-slots/', counsellor.get_booked_slots, name='get_booked_slots'),
    # Mood
    path('mood/', analytics.mood_tracker, name='mood_tracker'),

    # Resources & Helplines
    path('resources/', core.resources, name='resources'),

    # Contact
    path('contact/', core.contact_us, name='contact_us'),

    # Dashboard
    path('dashboard/', analytics.dashboard, name='dashboard'),

    path('survey-analytics/', analytics.survey_analytics, name='survey_analytics'),
    path('survey-sentiment/', analytics.survey_sentiment_dashboard, name='survey_sentiment_dashboard'),
    path('my-progress/report.pdf', analytics.download_progress_report_pdf, name='download_progress_report_pdf'),

    # Location Map (staff only)
    path('location-map/', analytics.location_map, name='location_map'),

    # Mental Health Heatmap (staff only)
    path('mental-health-heatmap/', analytics.mental_health_heatmap, name='mental_health_heatmap'),
]

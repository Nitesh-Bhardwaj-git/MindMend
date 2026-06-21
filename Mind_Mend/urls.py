from django.urls import path
from .views import auth, core, assessments, forum, counsellor, analytics

urlpatterns = [
    # ── Keep-alive endpoint for Render free-tier ──────────────────────────
    # Ping https://mindmend-1.onrender.com/cron-ping/ every 14 min via
    # cron-job.org (or any cron service) to prevent the dyno from sleeping.
    path('cron-ping/', core.cron_ping, name='cron_ping'),

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
    path('profile/setup/', auth.profile_setup, name='profile_setup'),
    path('profile/toggle-identity/', auth.toggle_identity, name='toggle_identity'),
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
    path('book/instant/', counsellor.instant_booking, name='instant_booking'),
    path('book/instant-connect/<int:booking_id>/', counsellor.instant_connect, name='instant_connect'),
    path('book/counsellor/<int:counsellor_id>/details/', counsellor.counsellor_detail, name='counsellor_detail'),
    
    path('wallet/', counsellor.wallet_dashboard, name='wallet_dashboard'),
    path('wallet/add/', counsellor.add_money_checkout, name='add_money_checkout'),
    path('wallet/verify/', counsellor.add_money_verify, name='add_money_verify'),
    
    # --- Earnings & Payouts ---
    path('admin/counsellors/', counsellor.admin_counsellors_dashboard, name='admin_counsellors_dashboard'),
    path('admin/counsellors/<int:counsellor_id>/analytics/', counsellor.admin_counsellor_analytics, name='admin_counsellor_analytics'),
    path('earnings/', counsellor.counsellor_earnings_dashboard, name='counsellor_earnings_dashboard'),
    path('penalties/', counsellor.counsellor_penalties, name='counsellor_penalties'),
    path('payout-history/', counsellor.counsellor_payout_history, name='counsellor_payout_history'),
    path('admin/revenue/', counsellor.admin_revenue_dashboard, name='admin_revenue_dashboard'),
    path('admin/revenue/history/', counsellor.admin_payout_history, name='admin_payout_history'),
    path('admin/revenue/history/<int:settlement_id>/reference/', counsellor.admin_update_settlement_reference, name='admin_update_settlement_reference'),
    path('admin/disputes/', counsellor.admin_disputes, name='admin_disputes'),
    path('admin/dispute/<int:dispute_id>/resolve/', counsellor.admin_resolve_dispute, name='admin_resolve_dispute'),
    path('admin/revenue/settle/<int:counsellor_id>/', counsellor.admin_mark_settled, name='admin_mark_settled'),
    path('wallet/add/checkout/', counsellor.add_money_checkout, name='add_money_checkout'),
    path('wallet/add/verify/', counsellor.add_money_verify, name='add_money_verify'),
    path('book/how-to/', counsellor.how_to_book, name='how_to_book'),
    path('my-bookings/', counsellor.my_bookings, name='my_bookings'),
    path('counsellor/sessions/', counsellor.counsellor_sessions, name='counsellor_sessions'),
    path('doctor/dashboard/', counsellor.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/booking/<int:booking_id>/action/', counsellor.doctor_booking_action, name='doctor_booking_action'),
    path('booking/<int:booking_id>/chat/', counsellor.counsellor_chat, name='counsellor_chat'),
    path('booking/<int:booking_id>/video/', counsellor.counsellor_video_call, name='counsellor_video_call'),
    path('booking/<int:booking_id>/emergency_cancel/', counsellor.emergency_cancel_booking, name='emergency_cancel_booking'),
    path('booking/<int:booking_id>/patient_cancel/', counsellor.patient_cancel_booking, name='patient_cancel_booking'),
    path('booking/<int:booking_id>/report_counsellor_no_show/', counsellor.report_counsellor_no_show, name='report_counsellor_no_show'),
    path('booking/<int:booking_id>/mark_patient_no_show/', counsellor.mark_patient_no_show, name='mark_patient_no_show'),
    path('booking/<int:booking_id>/raise_dispute/', counsellor.raise_dispute, name='raise_dispute'),
    path('booking/<int:booking_id>/finish/', counsellor.finish_session, name='finish_session'),
    path('booking/<int:booking_id>/request-early-finish/', counsellor.request_early_finish, name='request_early_finish'),
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
    path('mood/entries/', analytics.mood_entries_all, name='mood_entries_all'),

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

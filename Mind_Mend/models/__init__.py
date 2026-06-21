from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from ..encryption import EncryptedTextField


class UserProfile(models.Model):
    """Extended profile for a registered user."""
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not', 'Prefer not to say'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    dob = models.DateField(null=True, blank=True, verbose_name='Date of Birth')
    occupation = models.CharField(max_length=150, blank=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    show_real_name = models.BooleanField(
        default=False,
        help_text='If checked, your real name is visible to others. Otherwise your username is used.'
    )
    show_username = models.BooleanField(
        default=True,
        help_text='If True, your @username is shown to counsellors and in the community forum. If False, you appear as Anonymous everywhere.'
    )
    location_opt_out = models.BooleanField(
        default=False,
        help_text='If checked, location tracking is disabled for this user.'
    )
    profile_complete = models.BooleanField(
        default=False,
        help_text='Set to True after the user completes the mandatory profile setup after registration.'
    )
    wallet_balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text='Real cash deposited by the user.'
    )
    bonus_balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text='Promotional or compensation credits awarded to the user.'
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile({self.user.username})"

    def display_name(self):
        """Returns display identity: real name (if show_real_name), username (if show_username), else Anonymous."""
        if not self.show_username:
            return 'Anonymous'
        if self.show_real_name and self.user.get_full_name():
            return self.user.get_full_name()
        return self.user.username


def get_display_name(user):
    """Standalone helper for views/consumers: respects the user's privacy settings.
    - show_username=False → 'Anonymous'
    - show_username=True + show_real_name=True → Full name (or username fallback)
    - show_username=True + show_real_name=False → @username
    """
    if not user:
        return 'Anonymous'
    try:
        profile = user.profile
        if not profile.show_username:
            return 'Anonymous'
        if profile.show_real_name:
            full = user.get_full_name().strip()
            return full if full else user.username
        return user.username
    except Exception:
        return user.username


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()



class Counsellor(models.Model):
    """Counsellors available for booking."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200)
    specialization = models.CharField(max_length=200)
    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='counsellors/', null=True, blank=True)
    session_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Fee per 30-minute session")
    is_active = models.BooleanField(default=True, help_text="Can receive new bookings")
    is_approved = models.BooleanField(default=False, help_text="Approved by admin to practice")
    trust_score = models.IntegerField(default=100, help_text="Decreases on no-shows or bad behavior")
    outstanding_debt = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Unpaid penalties carried forward")
    
    is_instant_enabled = models.BooleanField(default=False, help_text="Available for instant counselling")
    instant_session_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Instant session fee")
    
    # Optional fields for detailed profile
    video_session_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Video session fee")
    instant_video_session_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Instant video session fee")
    available_days = models.CharField(max_length=100, help_text="e.g., Mon,Wed,Fri")
    available_time_start = models.TimeField()
    available_time_end = models.TimeField()
    
    # New detailed fields
    verified_qualification = models.TextField(blank=True, default="", help_text="Verified degrees and licenses")
    medical_registration = models.CharField(max_length=200, blank=True, default="", help_text="Medical registration number")
    relevant_experience = models.TextField(blank=True, default="", help_text="Brief description of relevant experience")
    review_quality = models.TextField(blank=True, default="", help_text="Summary of rating/review quality")
    years_of_experience = models.PositiveIntegerField(default=0, help_text="Years of professional experience")
    consultation_fees_policy = models.TextField(blank=True, default="", help_text="Fees and follow-up policies")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class CounsellorBooking(models.Model):
    """Counsellor appointment bookings."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    counsellor = models.ForeignKey(Counsellor, on_delete=models.CASCADE)
    date = models.DateField()
    time_slot = models.TimeField()
    notes = models.TextField(blank=True)
    is_anonymous = models.BooleanField(
        default=False,
        help_text='If checked, the counsellor sees this booking as Anonymous Patient.'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Payment'),
            ('confirmed', 'Confirmed'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending'
    )
    is_instant = models.BooleanField(default=False)
    
    # Financial fields
    wallet_used = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Cash balance used")
    bonus_used = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Bonus credits used")
    
    # Cancellation & No-Show tracking
    CANCELLED_BY_CHOICES = [
        ('counsellor', 'Counsellor'),
        ('patient', 'Patient'),
        ('system', 'System')
    ]
    cancelled_by = models.CharField(max_length=20, choices=CANCELLED_BY_CHOICES, null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)
    is_no_show = models.BooleanField(default=False, help_text="True if either party was marked as no-show")

    is_paid = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    is_disputed = models.BooleanField(default=False, help_text="True if patient raised a dispute")
    include_chat = models.BooleanField(default=True, help_text="Include Chat Session")
    include_video = models.BooleanField(default=False, help_text="Include Video Calling Session")
    chat_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    video_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Flat convenience fee charged to the patient (₹2 normal, ₹3 instant)")
    total_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Counsellor Payouts
    is_settled = models.BooleanField(default=False, help_text="Has MindMend paid the counsellor for this session?")
    counsellor_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Total fee minus platform commission")
    completed_at = models.DateTimeField(null=True, blank=True, help_text="When the session was marked as completed")
    completion_reminder_sent = models.BooleanField(default=False)
    payout_settlement = models.ForeignKey('PayoutSettlement', on_delete=models.SET_NULL, null=True, blank=True, related_name='settled_bookings')
    
    # Attendance tracking
    counsellor_joined_at = models.DateTimeField(null=True, blank=True)
    patient_joined_at = models.DateTimeField(null=True, blank=True)
    session_ended_at = models.DateTimeField(null=True, blank=True)
    actual_duration_minutes = models.IntegerField(null=True, blank=True)
    
    # Early finish mutual consent
    patient_requested_finish = models.BooleanField(default=False, help_text="Patient wants to end session early")
    counsellor_requested_finish = models.BooleanField(default=False, help_text="Counsellor wants to end session early")
    
    @property
    def is_dispute_window_open(self):
        from django.utils import timezone
        import datetime
        if self.status != 'completed' or not self.completed_at:
            return False
        return timezone.now() <= self.completed_at + datetime.timedelta(hours=24)
    
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def patient_display_name(self):
        """Returns the patient's name shown to counsellors.
        Respects both the booking-level anonymous flag and the user's global show_username toggle."""
        if self.is_anonymous:
            return 'Anonymous Patient'
        try:
            if not self.user.profile.show_username:
                return 'Anonymous Patient'
        except Exception:
            pass
        return get_display_name(self.user)

    class Meta:
        unique_together = ['counsellor', 'date', 'time_slot']
        ordering = ['date', 'time_slot']

class SessionDispute(models.Model):
    """Tracks disputes raised by patients against completed sessions."""
    OUTCOME_CHOICES = [
        ('pending', 'Pending Admin Review'),
        ('patient_won', 'Resolved in favor of Patient'),
        ('counsellor_won', 'Resolved in favor of Counsellor'),
    ]
    booking = models.OneToOneField(CounsellorBooking, on_delete=models.CASCADE, related_name='dispute')
    patient_reason = models.TextField()
    admin_notes = models.TextField(blank=True, help_text="Notes from admin resolution")
    outcome = models.CharField(max_length=30, choices=OUTCOME_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Dispute for Booking #{self.booking.id}"

class WalletTransaction(models.Model):
    """Tracks history of wallet credits and debits."""
    TRANSACTION_TYPES = [
        ('add_money', 'Added Money'),
        ('session_booking', 'Session Booking'),
        ('compensation', 'Compensation Credit'),
        ('refund', 'Refund Credit'),
        ('expired', 'Expired Bonus'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallet_transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=50, choices=TRANSACTION_TYPES)
    description = models.CharField(max_length=255)
    reference_id = models.CharField(max_length=100, blank=True, help_text="e.g., Razorpay payment ID or booking ID")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} - ₹{self.amount}"

class BonusCredit(models.Model):
    """Tracks individual bonus credit grants and their expiry dates."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bonus_credits')
    initial_amount = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        ordering = ['expires_at']
        
    def __str__(self):
        return f"Bonus: ₹{self.remaining_amount} remaining (Expires: {self.expires_at})"

class CounsellorBankDetails(models.Model):
    counsellor = models.OneToOneField(Counsellor, on_delete=models.CASCADE, related_name='bank_details')
    account_holder_name = models.CharField(max_length=100)
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=20)
    upi_id = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Bank Details for {self.counsellor.name}"

class PayoutSettlement(models.Model):
    """Tracks historical payouts settled to counsellors."""
    counsellor = models.ForeignKey(Counsellor, on_delete=models.CASCADE, related_name='settlements')
    settled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_settlements')
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)
    total_deductions = models.DecimalField(max_digits=10, decimal_places=2)
    net_amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    bank_reference_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Settlement {self.id} - {self.counsellor.name} - ₹{self.net_amount_paid}"

class BookingCancellation(models.Model):
    """Tracks emergency cancellations initiated by a counsellor."""
    booking = models.OneToOneField(CounsellorBooking, on_delete=models.CASCADE, related_name='cancellation')
    counsellor = models.ForeignKey(Counsellor, on_delete=models.CASCADE)
    reason = models.TextField()
    message_to_patient = models.TextField()
    compensation_credited = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    counsellor_penalty = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Fine deducted from counsellor's payout")
    refund_status = models.CharField(max_length=20, default='Pending')
    payout_settlement = models.ForeignKey(PayoutSettlement, on_delete=models.SET_NULL, null=True, blank=True, related_name='settled_cancellations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def patient_display_name(self):
        """Returns name shown to counsellors. Respects both the booking-level anonymous flag
        AND the user's global show_username profile toggle."""
        if self.is_anonymous:
            return 'Anonymous Patient'
        try:
            if not self.user.profile.show_username:
                return 'Anonymous Patient'
        except Exception:
            pass
        return get_display_name(self.user)

    def save(self, *args, **kwargs):
        if self.counsellor:
            if self.include_chat:
                self.chat_fee = self.counsellor.instant_session_fee if self.is_instant else self.counsellor.session_fee
            else:
                self.chat_fee = Decimal('0.00')
            
            if self.include_video:
                self.video_fee = self.counsellor.instant_video_session_fee if self.is_instant else self.counsellor.video_session_fee
            else:
                self.video_fee = Decimal('0.00')
            
            self.total_fee = self.chat_fee + self.video_fee
        super().save(*args, **kwargs)


class CounsellorChatMessage(models.Model):
    """Live chat messages between user and counsellor for a booking."""
    booking = models.ForeignKey(CounsellorBooking, on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = EncryptedTextField()  # Encrypted at rest with Fernet (AES-128/HMAC-SHA256)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class CounsellorNotification(models.Model):
    """Notifications for counsellors about bookings and chat activity."""
    EVENT_CHOICES = [
        ('booking_created', 'New booking'),
        ('chat_started', 'Chat started'),
        ('message_received', 'New message'),
        ('booking_status', 'Booking status changed'),
    ]
    counsellor = models.ForeignKey(Counsellor, on_delete=models.CASCADE)
    booking = models.ForeignKey(CounsellorBooking, on_delete=models.CASCADE, null=True, blank=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=30, choices=EVENT_CHOICES)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class CounsellorReview(models.Model):
    """Rating and review for a completed counsellor session."""
    booking = models.OneToOneField(CounsellorBooking, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
        help_text='1-5 stars'
    )
    review_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ContactMessage(models.Model):
    """Messages submitted from the Contact Us form."""
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class MoodEntry(models.Model):
    """Daily mood tracking."""
    MOOD_CHOICES = [
        (1, 'Very Low'),
        (2, 'Low'),
        (3, 'Neutral'),
        (4, 'Good'),
        (5, 'Very Good'),
    ]
    ENERGY_CHOICES = [
        (1, 'Very Low'),
        (2, 'Low'),
        (3, 'Medium'),
        (4, 'Good'),
        (5, 'High'),
    ]
    ACTIVITY_TAGS = [
        'sleep', 'work', 'exercise', 'social', 'family', 'weather',
        'health', 'stress', 'hobby', 'rest', 'outdoors', 'food', 'other'
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    mood = models.IntegerField(choices=MOOD_CHOICES)
    energy_level = models.IntegerField(choices=ENERGY_CHOICES, null=True, blank=True)
    activities = models.CharField(max_length=200, blank=True, help_text='Comma-separated: e.g. work,sleep,exercise')
    notes = models.TextField(blank=True)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']


class ForumPost(models.Model):
    """Anonymous community forum posts — support, discussion, recovery stories."""
    CATEGORY_CHOICES = [
        ('support', 'Support'),
        ('discussion', 'Discussion'),
        ('recovery', 'Recovery Story'),
    ]
    author = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='support')
    title = models.CharField(max_length=200)
    content = models.TextField()
    is_anonymous = models.BooleanField(default=True)
    is_moderated = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class ForumReply(models.Model):
    """Replies to forum posts."""
    post = models.ForeignKey(ForumPost, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    content = models.TextField()
    is_anonymous = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class AssessmentResult(models.Model):
    """Store results from PHQ-9, GAD-7, PSS assessments."""
    ASSESSMENT_TYPES = [
        ('phq9', 'PHQ-9 Depression'),
        ('gad7', 'GAD-7 Anxiety'),
        ('pss', 'PSS Stress'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    assessment_type = models.CharField(max_length=10, choices=ASSESSMENT_TYPES)
    total_score = models.IntegerField()
    result_level = models.CharField(max_length=50)
    answers = models.JSONField(default=dict)  # Store individual answers
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ChatMessage(models.Model):
    """Store chat history for the AI chatbot."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100)
    role = models.CharField(max_length=10, choices=[('user', 'User'), ('assistant', 'Assistant')])
    content = EncryptedTextField()  # Encrypted at rest with Fernet (AES-128/HMAC-SHA256)
    sentiment = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class UserMemory(models.Model):
    """Lightweight long-term memory for chat personalization."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    stress_topics = models.JSONField(default=list, blank=True)
    helpful_activities = models.JSONField(default=list, blank=True)
    last_emotion = models.CharField(max_length=50, blank=True)
    last_context = models.CharField(max_length=50, blank=True)
    preferred_name = models.CharField(max_length=100, blank=True)
    last_prompted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']


class UserAccessLocation(models.Model):
    """Track where users access the platform from (country, state, city)."""
    LOCATION_SOURCE = [('ip', 'IP geolocation'), ('browser', 'Browser GPS')]
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location_source = models.CharField(max_length=10, choices=LOCATION_SOURCE, default='ip')
    country = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=150, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    page_path = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        loc = ', '.join(filter(None, [self.city, self.state, self.country]))
        return loc or self.ip_address or 'Unknown'


class EmailVerificationOTP(models.Model):
    """OTP validation codes for new account email verification."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_otp')
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        """Valid for 15 minutes."""
        expiration_time = self.created_at + timezone.timedelta(minutes=15)
        return timezone.now() <= expiration_time

    def __str__(self):
        return f"OTP({self.user.username})"

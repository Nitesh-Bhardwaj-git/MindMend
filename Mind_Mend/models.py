from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver


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
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile({self.user.username})"

    def display_name(self):
        if self.show_real_name and self.user.get_full_name():
            return self.user.get_full_name()
        return self.user.username


def get_display_name(user):
    """Standalone helper for views/consumers: respects the user's privacy setting."""
    if not user:
        return "Anonymous"
    try:
        profile = user.profile
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
    session_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Session fee")
    available_days = models.CharField(max_length=100, help_text="e.g., Mon,Wed,Fri")
    available_time_start = models.TimeField()
    available_time_end = models.TimeField()
    is_active = models.BooleanField(default=True)
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
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('confirmed', 'Confirmed'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending'
    )
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['counsellor', 'date', 'time_slot']
        ordering = ['date', 'time_slot']


class CounsellorChatMessage(models.Model):
    """Live chat messages between user and counsellor for a booking."""
    booking = models.ForeignKey(CounsellorBooking, on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
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
    content = models.TextField()
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


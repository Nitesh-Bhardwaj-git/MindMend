from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import MoodEntry, ForumPost, ForumReply, CounsellorBooking, Counsellor
from .assessment_data import PHQ9_QUESTIONS, GAD7_QUESTIONS, PSS_QUESTIONS


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username already exists. Please choose a different one or login.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already registered. Please login or use a different email.')
        return email


class MoodEntryForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['energy_level'].required = False

    class Meta:
        model = MoodEntry
        fields = ['mood', 'energy_level', 'activities', 'notes', 'date']
        widgets = {
            'mood': forms.RadioSelect(),
            'energy_level': forms.RadioSelect(),
            'activities': forms.TextInput(attrs={'placeholder': 'e.g. work, sleep, exercise (optional)'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What\'s on your mind? (optional)'}),
            'date': forms.DateInput(attrs={'type': 'date'}),
        }


class ForumPostForm(forms.ModelForm):
    class Meta:
        model = ForumPost
        fields = ['title', 'content', 'is_anonymous']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Post title'}),
            'content': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Share your thoughts...'}),
        }


class ForumReplyForm(forms.ModelForm):
    class Meta:
        model = ForumReply
        fields = ['content', 'is_anonymous']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Write a reply...'}),
        }


class CounsellorBookingForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['counsellor'].queryset = Counsellor.objects.filter(is_active=True)

    class Meta:
        model = CounsellorBooking
        fields = ['counsellor', 'date', 'time_slot', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'time_slot': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Any specific concerns?'}),
        }


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'placeholder': 'Your name'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'placeholder': 'your@email.com'}))
    subject = forms.CharField(max_length=200, required=True, widget=forms.TextInput(attrs={'placeholder': 'Subject'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'Your message...'}), required=True)


def make_assessment_form(questions, scale_max=3, scale_labels=None):
    """Create a dynamic form for an assessment (PHQ9, GAD7 use 0-3; PSS uses 0-4)."""
    if scale_labels is None:
        scale_labels = ['Not at all', 'Several days', 'More than half', 'Nearly every day']
    choices = [(i, f"{i} - {scale_labels[i] if i < len(scale_labels) else ''}") for i in range(scale_max + 1)]

    fields = {}
    for i, q in enumerate(questions):
        fields[f'q{i}'] = forms.IntegerField(
            label=q,
            min_value=0,
            max_value=scale_max,
            widget=forms.RadioSelect(choices=choices)
        )
    return type('AssessmentForm', (forms.Form,), fields)

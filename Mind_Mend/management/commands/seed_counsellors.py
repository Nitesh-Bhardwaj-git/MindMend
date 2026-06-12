from datetime import time

from django.core.management.base import BaseCommand

from Mind_Mend.models import Counsellor


COUNSELLOR_SEED_DATA = [
    {
        'name': 'Dr Aman Raj',
        'specialization': 'General Counselling',
        'bio': 'Compassionate counsellor focused on stress, life transitions, and everyday emotional wellbeing.',
        'available_days': 'Mon,Tue,Wed,Thu,Fri',
        'available_time_start': time(10, 0),
        'available_time_end': time(18, 0),
        'session_fee': 1,
        'is_instant_enabled': True,
        'instant_session_fee': 2.00,
        'video_session_fee': 5.00,
        'instant_video_session_fee': 7.00,
        'is_active': True,
        'verified_qualification': 'M.Sc. in Clinical Psychology, PG Diploma in Guidance and Counselling',
        'medical_registration': 'Reg No: A-1245-RCI (Rehabilitation Council of India)',
        'relevant_experience': 'Specializes in stress management, cognitive behavioral therapy, and family counseling. Successfully helped over 500+ clients deal with everyday emotional challenges and life transitions.',
        'review_quality': 'Highly appreciated for empathetic active listening, actionable coping strategies, and friendly demeanor. Clients frequently note feeling immediately comfortable and heard.',
        'years_of_experience': 8,
        'consultation_fees_policy': '₹1/session. Standard 24-hour cancellation window for full refund. Includes 1 free messaging query follow-up within 3 days after the session.',
    },
    {
        'name': 'Dr Kirti',
        'specialization': 'Depression & Anxiety',
        'bio': 'Mental health specialist focused on treating depression, anxiety, and burnout with supportive therapy.',
        'available_days': 'Mon,Wed,Fri,Sat',
        'available_time_start': time(11, 0),
        'available_time_end': time(18, 0),
        'session_fee': 1,
        'is_instant_enabled': True,
        'instant_session_fee': 2.00,
        'video_session_fee': 5.00,
        'instant_video_session_fee': 8.00,
        'is_active': True,
        'verified_qualification': 'M.D. in Psychiatry, MBBS, Certified CBT Practitioner',
        'medical_registration': 'Reg No: K-9876-MCI (Medical Council of India)',
        'relevant_experience': 'Extensive experience in treating clinical depression, generalized anxiety disorder (GAD), OCD, and panic disorders. Focuses on a holistic approach combining mindfulness and talk therapy.',
        'review_quality': 'Praised for deep clinical expertise, structuring therapy sessions productively, and a calming presence. Clients report long-term progress in anxiety control.',
        'years_of_experience': 12,
        'consultation_fees_policy': '₹1/session. Refund is available if cancelled at least 12 hours before slot. One follow-up text consultation is provided for medication adjustments within 7 days.',
    },
    {
        'name': 'Dr Akash Raj',
        'specialization': 'Student Wellness',
        'bio': 'Supports students and young adults dealing with academic pressure, focus issues, and emotional stress.',
        'available_days': 'Mon,Wed,Fri',
        'available_time_start': time(9, 0),
        'available_time_end': time(17, 0),
        'session_fee': 1,
        'is_instant_enabled': False,
        'instant_session_fee': 0.00,
        'video_session_fee': 5.00,
        'instant_video_session_fee': 0.00,
        'is_active': True,
        'verified_qualification': 'M.A. in Counseling Psychology, Certified Student Wellness Coach',
        'medical_registration': 'Reg No: AR-5432-CO (Counseling Association registration)',
        'relevant_experience': 'Specialist in student counseling, career transition stress, exam anxiety, and self-esteem building. Worked with various universities and young adult programs.',
        'review_quality': 'Described by young adults as highly relatable, encouraging, and easy to talk to. Commended for modern, non-judgmental guidance and stress-relief exercises.',
        'years_of_experience': 6,
        'consultation_fees_policy': '₹1/session. Flexible cancellation policy: reschedule anytime or cancel up to 6 hours prior for a full refund. 1 follow-up advice response included.',
    },
]


class Command(BaseCommand):
    help = 'Seed sample counsellors for development or a fresh deployed database.'

    def handle(self, *args, **options):
        created = 0
        updated = 0

        for item in COUNSELLOR_SEED_DATA:
            counsellor, was_created = Counsellor.objects.update_or_create(
                name=item['name'],
                defaults=item,
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'Created counsellor: {counsellor.name}'))
            else:
                updated += 1
                self.stdout.write(self.style.WARNING(f'Updated counsellor: {counsellor.name}'))

        self.stdout.write(
            self.style.SUCCESS(
                f'Seed complete. Created: {created}, Updated: {updated}, Total now: {Counsellor.objects.count()}'
            )
        )

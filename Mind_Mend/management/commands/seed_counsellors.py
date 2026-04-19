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
        'session_fee': 10,
        'is_active': True,
    },
    {
        'name': 'Dr Kirti',
        'specialization': 'Depression & Anxiety',
        'bio': 'Mental health specialist focused on treating depression, anxiety, and burnout with supportive therapy.',
        'available_days': 'Mon,Wed,Fri,Sat',
        'available_time_start': time(11, 0),
        'available_time_end': time(18, 0),
        'session_fee': 11,
        'is_active': True,
    },
    {
        'name': 'Dr Akash Raj',
        'specialization': 'Student Wellness',
        'bio': 'Supports students and young adults dealing with academic pressure, focus issues, and emotional stress.',
        'available_days': 'Mon,Wed,Fri',
        'available_time_start': time(9, 0),
        'available_time_end': time(17, 0),
        'session_fee': 9,
        'is_active': True,
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

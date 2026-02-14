from django.core.management.base import BaseCommand
from Mind_Mend.models import Counsellor
from datetime import time


class Command(BaseCommand):
    help = 'Seed sample counsellors'

    def handle(self, *args, **options):
        if Counsellor.objects.exists():
            self.stdout.write('Counsellors already exist, skipping.')
            return
        counsellors = [
            {'name': 'Dr. Priya Sharma', 'specialization': 'Depression & Anxiety', 'bio': '10+ years experience.', 'available_days': 'Mon,Wed,Fri', 'available_time_start': time(9, 0), 'available_time_end': time(17, 0)},
            {'name': 'Dr. Rajesh Kumar', 'specialization': 'Stress & Trauma', 'bio': 'Clinical psychologist.', 'available_days': 'Tue,Thu', 'available_time_start': time(10, 0), 'available_time_end': time(18, 0)},
            {'name': 'Ms. Ananya Singh', 'specialization': 'General Counselling', 'bio': 'Supportive counselling.', 'available_days': 'Mon,Tue,Wed,Thu,Fri', 'available_time_start': time(11, 0), 'available_time_end': time(15, 0)},
        ]
        for c in counsellors:
            Counsellor.objects.create(**c)
        self.stdout.write(self.style.SUCCESS(f'Created {len(counsellors)} counsellors'))

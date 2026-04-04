import os
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MindMend.settings')
django.setup()

from Mind_Mend.services import get_chat_response

# Test with "hii"
response = get_chat_response("hii", lang="en", conversation_history=[])
print("Response:", response['response'])
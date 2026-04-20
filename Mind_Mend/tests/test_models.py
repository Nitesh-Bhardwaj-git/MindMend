from django.test import TestCase
from django.contrib.auth.models import User
from Mind_Mend.models import UserProfile

class UserProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpassword')

    def test_profile_creation(self):
        # A profile should automatically be created via the post_save signal
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertEqual(self.user.profile.user, self.user)

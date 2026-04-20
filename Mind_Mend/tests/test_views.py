from django.test import TestCase, Client
from django.urls import reverse

class CoreViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_home_page_status_code(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_contact_us_page_status_code(self):
        response = self.client.get(reverse('contact_us'))
        self.assertEqual(response.status_code, 200)

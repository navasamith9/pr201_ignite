from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import BusSchedule


class AddBusViewTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username='transport-admin',
            password='test-password',
            role='admin',
        )
        self.student = get_user_model().objects.create_user(
            username='student',
            password='test-password',
            role='student',
        )

    def test_dashboard_shows_add_bus_only_to_administrator(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('bus:dashboard'))
        self.assertContains(response, reverse('bus:add_bus'))

        self.client.force_login(self.student)
        response = self.client.get(reverse('bus:dashboard'))
        self.assertNotContains(response, reverse('bus:add_bus'))

    def test_administrator_can_add_a_bus_schedule(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('bus:add_bus'), {
            'name': 'Campus Express',
            'route': BusSchedule.ROUTE_COLLEGE_CITY,
            'day': 'mon',
            'departure_time': '09:30',
            'price': 75,
            'max_capacity': 40,
            'active': 'on',
        })

        self.assertRedirects(response, reverse('bus:dashboard'))
        self.assertTrue(BusSchedule.objects.filter(name='Campus Express').exists())

    def test_student_cannot_open_add_bus_page(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse('bus:add_bus'))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(BusSchedule.objects.exists())

    def test_bus_only_administrator_can_manage_bus_without_global_admin_access(self):
        self.student.is_bus_admin = True
        self.student.save(update_fields=['is_bus_admin'])
        self.client.force_login(self.student)

        response = self.client.get(reverse('bus:add_bus'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.student.role, self.student.Role.STUDENT)
        self.assertFalse(self.student.is_staff)

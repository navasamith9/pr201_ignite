from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class PHCAdministratorRoleTests(TestCase):
    def test_phc_only_administrator_can_open_the_phc_admin_dashboard(self):
        user = get_user_model().objects.create_user(
            username='phc-admin',
            password='test-password',
            role='student',
            is_phc_admin=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('phc:admin_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(user.role, user.Role.STUDENT)
        self.assertFalse(user.is_staff)

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AdministratorAccessTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="existing-admin",
            email="admin@example.com",
            password="test-password-123",
            role="admin",
        )
        self.student = get_user_model().objects.create_user(
            username="student-account",
            email="student@example.com",
            password="test-password-123",
            role="student",
        )

    def test_administrator_can_grant_full_app_admin_access_by_email(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("home"), {"admin_email": self.student.email})

        self.assertRedirects(response, reverse("home"))
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, self.student.Role.ADMIN)
        self.assertTrue(self.student.is_staff)

    def test_non_admin_cannot_grant_administrator_access(self):
        self.client.force_login(self.student)

        response = self.client.post(reverse("home"), {"admin_email": self.admin.email})

        self.assertEqual(response.status_code, 403)

    def test_global_admin_can_grant_lhtc_only_access_without_changing_account_role(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("home"),
            {
                "access_scope": "service",
                "service_admin_role": "lhtc",
                "admin_email": self.student.email,
            },
        )

        self.assertRedirects(response, reverse("home"))
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_lhtc_admin)
        self.assertEqual(self.student.role, self.student.Role.STUDENT)
        self.assertFalse(self.student.is_staff)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("scheduler-add-room")).status_code, 200)

    def test_administrator_can_revoke_service_only_access(self):
        self.student.is_bus_admin = True
        self.student.save(update_fields=["is_bus_admin"])
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("home"),
            {
                "access_scope": "revoke",
                "service_admin_role": "bus",
                "access_target_id": self.student.id,
            },
        )

        self.assertRedirects(response, reverse("home"))
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_bus_admin)

    def test_administrator_can_revoke_global_access_and_restore_normal_role(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("home"), {"admin_email": self.student.email})
        self.student.refresh_from_db()

        response = self.client.post(
            reverse("home"),
            {
                "access_scope": "revoke",
                "service_admin_role": "global",
                "access_target_id": self.student.id,
            },
        )

        self.assertRedirects(response, reverse("home"))
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, self.student.Role.STUDENT)
        self.assertFalse(self.student.is_staff)

    def test_admin_access_form_is_not_shown_to_non_admins(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("home"))

        self.assertNotContains(response, "Grant administrator access")

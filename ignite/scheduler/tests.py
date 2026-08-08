from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import BookingHistory, Event, Room, RoomBookingPermission, TimetableEntry
from .services import get_suitable_rooms


class SchedulerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="scheduler-tester",
            password="test-password-123",
            role="faculty",
        )
        self.student = get_user_model().objects.create_user(
            username="student-tester",
            email="student@example.com",
            password="test-password-123",
            role="student",
            branch="CSE",
            academic_year=2,
        )
        self.small_room = Room.objects.create(
            name="Test A101", capacity=40, has_projector=True, has_wifi=True
        )
        self.large_room = Room.objects.create(
            name="Test A201", capacity=90, has_projector=True, has_wifi=True
        )

    def create_event(self, **overrides):
        values = {
            "title": "Test workshop",
            "event_type": "WORKSHOP",
            "purpose": "Scheduler test",
            "expected_strength": 35,
            "branches": [],
            "years": [],
            "event_date": date(2030, 8, 5),  # Monday
            "start_time": time(10, 30),
            "end_time": time(11, 30),
            "registration_deadline": timezone.now() + timedelta(days=1),
            "created_by": self.user,
        }
        values.update(overrides)
        event = Event.objects.create(**values)
        event.coordinators.add(self.user)
        return event

    def test_timetable_conflict_excludes_room(self):
        TimetableEntry.objects.create(
            room=self.small_room,
            day_of_week=0,
            start_time=time(10),
            end_time=time(12),
            branch="CSE",
            year=2,
            subject="Data Structures",
        )

        rooms = get_suitable_rooms(self.create_event())

        self.assertEqual([item["room"] for item in rooms], [self.large_room])

    def test_booking_selected_suitable_room_creates_history(self):
        event = self.create_event(start_time=time(12), end_time=time(13))
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("confirm-booking", args=[event.pk]),
            data={"room_id": self.large_room.pk},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.booked_room, self.large_room)
        self.assertEqual(event.status, "BOOKED")
        self.assertTrue(
            BookingHistory.objects.filter(
                event=event, action="CREATED", new_room=self.large_room
            ).exists()
        )

    def test_booking_rejects_unsuitable_selected_room(self):
        event = self.create_event(expected_strength=50)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("confirm-booking", args=[event.pk]),
            data={"room_id": self.small_room.pk},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        event.refresh_from_db()
        self.assertEqual(event.status, "DRAFT")

    def test_availability_search_does_not_create_an_event(self):
        self.client.force_login(self.user)
        before = Event.objects.count()

        response = self.client.post(
            reverse("availability"),
            data={
                "title": "Availability only",
                "event_type": "WORKSHOP",
                "purpose": "Search without booking",
                "expected_strength": 35,
                "branches": ["CSE"],
                "years": [2],
                "event_date": "2030-08-05",
                "start_time": "12:00",
                "end_time": "13:00",
                "registration_deadline": (timezone.now() + timedelta(days=1)).isoformat(),
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.json()["recommended_rooms"]), 0)
        self.assertEqual(Event.objects.count(), before)

    def test_student_cannot_search_or_book_rooms_without_grant(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("availability"),
            data={},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_booked_event_is_visible_and_registerable_for_its_student_audience(self):
        event = self.create_event(
            status="BOOKED",
            booked_room=self.large_room,
            branches=["CSE"],
            years=[2],
        )
        self.client.force_login(self.student)

        campus_response = self.client.get(reverse("campus-events"))

        self.assertEqual(campus_response.status_code, 200)
        self.assertEqual([item["id"] for item in campus_response.json()], [event.id])
        self.assertTrue(campus_response.json()[0]["registration_open"])

        registration_response = self.client.post(
            reverse("register-event", args=[event.id]),
            data={},
            content_type="application/json",
        )

        self.assertEqual(registration_response.status_code, 201)
        registered_response = self.client.get(f"{reverse('list-events')}?view=student")
        self.assertEqual([item["id"] for item in registered_response.json()], [event.id])

    def test_student_with_incomplete_profile_can_see_and_register_for_booked_event(self):
        """Unprofiled accounts must not be hidden from all targeted events."""
        event = self.create_event(
            status="BOOKED",
            booked_room=self.large_room,
            branches=["cse"],
            years=[3],
        )
        self.student.branch = ""
        self.student.academic_year = None
        self.student.save(update_fields=["branch", "academic_year"])
        self.client.force_login(self.student)

        campus_response = self.client.get(f"{reverse('campus-events')}?view=student")

        self.assertEqual(campus_response.status_code, 200)
        self.assertEqual([item["id"] for item in campus_response.json()], [event.id])
        self.assertTrue(campus_response.json()[0]["registration_open"])
        self.assertEqual(
            self.client.post(
                reverse("register-event", args=[event.id]),
                data={},
                content_type="application/json",
            ).status_code,
            201,
        )

    def test_admin_can_grant_and_revoke_student_coordinator_access(self):
        admin = get_user_model().objects.create_user(
            username="scheduler-admin",
            email="admin@example.com",
            password="test-password-123",
            role="admin",
        )
        self.client.force_login(admin)

        grant_response = self.client.post(
            reverse("coordinator-permissions"),
            data={"email": self.student.email},
            content_type="application/json",
        )

        self.assertEqual(grant_response.status_code, 201)
        permission = RoomBookingPermission.objects.get(user=self.student)
        self.assertTrue(permission.is_active)
        self.assertEqual(permission.granted_by, admin)

        self.client.force_login(self.student)
        self.assertEqual(
            self.client.get(reverse("scheduler-access")).json()["role"], "coordinator"
        )
        self.assertEqual(
            self.client.post(
                reverse("availability"),
                data={
                    "title": "Coordinator search",
                    "event_type": "WORKSHOP",
                    "purpose": "Permission test",
                    "expected_strength": 20,
                    "event_date": "2030-08-05",
                    "start_time": "12:00",
                    "end_time": "13:00",
                    "registration_deadline": (timezone.now() + timedelta(days=1)).isoformat(),
                },
                content_type="application/json",
            ).status_code,
            200,
        )

        self.client.force_login(admin)
        revoke_response = self.client.delete(
            reverse("coordinator-permission-detail", args=[permission.pk])
        )
        self.assertEqual(revoke_response.status_code, 200)
        permission.refresh_from_db()
        self.assertFalse(permission.is_active)

        self.client.force_login(self.student)
        self.assertEqual(
            self.client.get(reverse("scheduler-access")).json()["role"], "student"
        )
        self.assertEqual(
            self.client.post(
                reverse("availability"), data={}, content_type="application/json"
            ).status_code,
            403,
        )

    def test_student_cannot_manage_coordinator_permissions(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("coordinator-permissions"))

        self.assertEqual(response.status_code, 403)


class SchedulerFrontendTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="scheduler-page-admin",
            email="page-admin@example.com",
            password="test-password-123",
            role="admin",
        )
        self.student = get_user_model().objects.create_user(
            username="scheduler-page-student",
            password="test-password-123",
            role="student",
        )

    def test_administrator_sees_management_cards_and_pages(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("scheduler"))
        self.assertContains(response, 'data-scheduler-calendar')
        self.assertContains(response, 'data-calendar-scope="campus"')
        self.assertContains(response, 'id="scheduler-dashboard-notifications"')
        for url_name in (
            "scheduler-add-room",
            "scheduler-timetable-entries",
            "scheduler-grant-access",
        ):
            self.assertContains(response, reverse(url_name))
            self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)

    def test_student_cannot_open_scheduler_management_pages(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("scheduler"))
        self.assertContains(response, 'data-scheduler-calendar')
        self.assertContains(response, 'data-calendar-scope="campus"')
        self.assertContains(response, 'data-student-account="true"')
        self.assertNotContains(response, reverse("scheduler-add-room"))
        for url_name in (
            "scheduler-add-room",
            "scheduler-timetable-entries",
            "scheduler-grant-access",
        ):
            self.assertEqual(self.client.get(reverse(url_name)).status_code, 403)

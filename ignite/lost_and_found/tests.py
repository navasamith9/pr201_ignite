import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import FoundClaim, FoundItem, LostAndFoundNotification, LostItem


class LostAndFoundWorkflowTests(TestCase):
    """Covers the core report → visual match → account notification path."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_directory = tempfile.mkdtemp()
        cls.media_settings = override_settings(MEDIA_ROOT=cls.media_directory)
        cls.media_settings.enable()

    @classmethod
    def tearDownClass(cls):
        cls.media_settings.disable()
        shutil.rmtree(cls.media_directory, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="finder",
            email="finder@example.com",
            password="test-password",
        )
        self.client.force_login(self.user)

    @staticmethod
    def image_upload(name="item.png", colour="#3366cc"):
        image_bytes = BytesIO()
        Image.new("RGB", (80, 80), colour).save(image_bytes, format="PNG")
        return SimpleUploadedFile(name, image_bytes.getvalue(), content_type="image/png")

    def create_lost_item(self):
        return LostItem.objects.create(
            owner=self.user,
            reporter_name="Lost Reporter",
            roll_number="23CS001",
            item_name="Blue water bottle",
            photo=self.image_upload(),
            contact_details="lost@example.com",
            lost_place="Central library",
        )

    def test_lost_report_is_created_and_searchable(self):
        response = self.client.post(
            reverse("lost_and_found:lost"),
            {
                "reporter_name": "Lost Reporter",
                "roll_number": "23CS001",
                "item_name": "Blue water bottle",
                "photo": self.image_upload(),
                "contact_details": "lost@example.com",
                "lost_place": "Central library",
            },
        )
        self.assertRedirects(response, reverse("lost_and_found:lost"))
        self.assertEqual(LostItem.objects.count(), 1)

        response = self.client.get(reverse("lost_and_found:lost"), {"q": "bottle"})
        self.assertContains(response, "Blue water bottle")

    def test_found_photo_match_can_notify_lost_report_owner(self):
        lost_item = self.create_lost_item()

        response = self.client.post(
            reverse("lost_and_found:found"),
            {
                "reporter_name": "Helpful Finder",
                "roll_number": "23CS002",
                "contact_details": "finder@example.com",
                "photo": self.image_upload("matching-item.png"),
            },
        )
        found_item = FoundItem.objects.get()
        self.assertRedirects(response, reverse("lost_and_found:found_matches", args=[found_item.id]))

        response = self.client.get(reverse("lost_and_found:found_matches", args=[found_item.id]))
        self.assertContains(response, "100% visual match")

        response = self.client.post(
            reverse("lost_and_found:claim_matched_lost", args=[lost_item.id, found_item.id]),
            {"finder_name": "Helpful Finder", "finder_contact": "9876543210"},
        )
        self.assertRedirects(response, reverse("lost_and_found:lost"))
        self.assertEqual(FoundClaim.objects.count(), 1)
        self.assertEqual(LostAndFoundNotification.objects.count(), 1)
        lost_item.refresh_from_db()
        self.assertEqual(lost_item.status, LostItem.Status.CONTACT_PENDING)

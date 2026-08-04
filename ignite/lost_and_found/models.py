from django.conf import settings
from django.db import models


class LostItem(models.Model):
    """A campus item reported as lost."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CONTACT_PENDING = "contact_pending", "Finder details received"
        CLOSED = "closed", "Closed"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lost_item_reports",
    )
    reporter_name = models.CharField(max_length=120)
    roll_number = models.CharField(max_length=40)
    item_name = models.CharField(max_length=160)
    photo = models.ImageField(upload_to="lost_and_found/lost/%Y/%m/")
    contact_details = models.CharField(max_length=160)
    lost_place = models.CharField(max_length=180)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.item_name} (lost by {self.reporter_name})"


class FoundItem(models.Model):
    """A photo and contact record submitted by someone who found an item."""

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="found_item_reports",
    )
    reporter_name = models.CharField(max_length=120)
    roll_number = models.CharField(max_length=40)
    contact_details = models.CharField(max_length=160)
    photo = models.ImageField(upload_to="lost_and_found/found/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Found item reported by {self.reporter_name}"


class FoundClaim(models.Model):
    """Finder details shared for a likely lost-item match."""

    lost_item = models.ForeignKey(LostItem, on_delete=models.CASCADE, related_name="claims")
    found_item = models.ForeignKey(
        FoundItem,
        on_delete=models.CASCADE,
        related_name="claims",
        null=True,
        blank=True,
    )
    finder_name = models.CharField(max_length=120)
    finder_contact = models.CharField(max_length=160)
    similarity_score = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=("lost_item", "found_item"), name="unique_lost_found_claim"),
        ]

    def __str__(self):
        return f"{self.lost_item.item_name} — {self.finder_name}"


class LostAndFoundNotification(models.Model):
    """In-app notification for the account that created a lost report."""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lost_and_found_notifications",
    )
    lost_item = models.ForeignKey(LostItem, on_delete=models.CASCADE, related_name="notifications")
    claim = models.OneToOneField(FoundClaim, on_delete=models.CASCADE, related_name="notification")
    title = models.CharField(max_length=160)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.title

# Generated manually for the new lost-and-found feature.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="FoundItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reporter_name", models.CharField(max_length=120)),
                ("roll_number", models.CharField(max_length=40)),
                ("contact_details", models.CharField(max_length=160)),
                ("photo", models.ImageField(upload_to="lost_and_found/found/%Y/%m/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reporter", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="found_item_reports", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="LostItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reporter_name", models.CharField(max_length=120)),
                ("roll_number", models.CharField(max_length=40)),
                ("item_name", models.CharField(max_length=160)),
                ("photo", models.ImageField(upload_to="lost_and_found/lost/%Y/%m/")),
                ("contact_details", models.CharField(max_length=160)),
                ("lost_place", models.CharField(max_length=180)),
                ("status", models.CharField(choices=[("open", "Open"), ("contact_pending", "Finder details received"), ("closed", "Closed")], default="open", max_length=24)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lost_item_reports", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="FoundClaim",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("finder_name", models.CharField(max_length=120)),
                ("finder_contact", models.CharField(max_length=160)),
                ("similarity_score", models.PositiveSmallIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("found_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="claims", to="lost_and_found.founditem")),
                ("lost_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="claims", to="lost_and_found.lostitem")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="LostAndFoundNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=160)),
                ("message", models.TextField()),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("claim", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="notification", to="lost_and_found.foundclaim")),
                ("lost_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="lost_and_found.lostitem")),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lost_and_found_notifications", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(
            model_name="foundclaim",
            constraint=models.UniqueConstraint(fields=("lost_item", "found_item"), name="unique_lost_found_claim"),
        ),
    ]

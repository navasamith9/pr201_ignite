from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_profile_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="is_lhtc_admin",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="customuser",
            name="is_phc_admin",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="customuser",
            name="is_bus_admin",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="customuser",
            name="is_canteen_admin",
            field=models.BooleanField(default=False),
        ),
    ]

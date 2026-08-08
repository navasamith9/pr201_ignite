from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_service_admin_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="global_admin_previous_role",
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name="customuser",
            name="global_admin_previous_staff",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="customuser",
            name="is_global_admin_grant",
            field=models.BooleanField(default=False),
        ),
    ]

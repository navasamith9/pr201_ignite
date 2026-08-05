from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('phc', '0001_initial')]

    operations = [
        migrations.AddField(
            model_name='doctorprofile',
            name='name',
            field=models.CharField(default='', max_length=120),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='doctorprofile',
            name='user',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='doctor_profile',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterModelOptions(
            name='doctorprofile',
            options={'ordering': ['name']},
        ),
    ]

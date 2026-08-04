# Generated manually because this workspace has no active Django environment.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveBigIntegerField()),
                ('amount_paise', models.PositiveIntegerField()),
                ('currency', models.CharField(default='INR', max_length=3)),
                ('provider', models.CharField(choices=[('razorpay', 'Razorpay')], default='razorpay', max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('failed', 'Failed')], default='pending', max_length=12)),
                ('provider_order_id', models.CharField(blank=True, max_length=128, null=True, unique=True)),
                ('provider_payment_id', models.CharField(blank=True, max_length=128)),
                ('provider_signature', models.CharField(blank=True, max_length=256)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='contenttypes.contenttype')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payments', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['content_type', 'object_id'], name='payments_pa_content_26eb0a_idx'),
        ),
    ]

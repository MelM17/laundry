# Generated by Django 4.2.7 on 2025-03-27 23:17

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('launderer', '0006_alter_laundererorderstatus_options_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='laundererorderstatus',
            options={},
        ),
        migrations.AlterField(
            model_name='laundererorderstatus',
            name='updated_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='status_updates', to=settings.AUTH_USER_MODEL),
        ),
    ]

# -*- coding: utf-8 -*-
# Generated by Django 1.11.17 on 2023-02-18 12:43
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('market', '0010_subscription_notification_sent'),
    ]

    operations = [
        migrations.RenameField(
            model_name='subscription',
            old_name='notification_sent',
            new_name='reminder_sent',
        ),
    ]

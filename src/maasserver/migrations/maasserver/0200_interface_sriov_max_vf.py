# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2019-10-07 14:39
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("maasserver", "0199_bootresource_tbz_txz")]

    operations = [
        migrations.AddField(
            model_name="interface",
            name="sriov_max_vf",
            field=models.PositiveIntegerField(default=0),
        )
    ]

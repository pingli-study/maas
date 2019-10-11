# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2019-08-07 02:55
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("metadataserver", "0021_scriptresult_applying_netconf")]

    operations = [
        # Users can change the tags for all Scripts to allow them to choose
        # which scripts run with commissioning and network-validation. Because
        # of this new tags normally aren't added to existing Scripts as MAAS
        # doesn't know if it was removed before. network-validation is a new
        # category so we want the network-validation tag added to the existing
        # internet-connectivity script on upgrade only.
        migrations.RunSQL(
            "UPDATE metadataserver_script SET "
            "tags = tags || '{network-validation}' "
            "WHERE name = 'internet-connectivity';"
        )
    ]

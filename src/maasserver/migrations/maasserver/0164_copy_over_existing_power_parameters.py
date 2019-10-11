# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-06-02 03:21
from __future__ import unicode_literals

from django.db import migrations


def copy_existing_power_parameters(apps, schema_editor):
    Node = apps.get_model("maasserver", "Node")
    BMC = apps.get_model("maasserver", "BMC")
    for bmc in BMC.objects.all():
        bmc.new_power_parameters = bmc.power_parameters
        bmc.save()
    for node in Node.objects.all():
        node.new_instance_power_parameters = node.instance_power_parameters
        node.save()


class Migration(migrations.Migration):

    dependencies = [
        ("maasserver", "0163_create_new_power_parameters_with_jsonfield")
    ]

    operations = [migrations.RunPython(copy_existing_power_parameters)]

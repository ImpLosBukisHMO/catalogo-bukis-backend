"""
Migration 0032: Add worker_role + 6 capability flag columns to UsuariosModel.
Includes a data back-fill: existing is_staff=True users get worker_role='total'.
Reverse resets all rows to worker_role='none' (columns dropped by RemoveField
if a full rollback follows).
"""

from django.db import migrations, models


def forward(apps, schema_editor):
    """Back-fill: every is_staff=True user → worker_role='total' (Spec R6)."""
    User = apps.get_model("api", "UsuariosModel")
    User.objects.filter(is_staff=True).update(worker_role="total")


def reverse(apps, schema_editor):
    """Reverse: reset every row to worker_role='none' (Spec R7 invariant)."""
    User = apps.get_model("api", "UsuariosModel")
    User.objects.all().update(worker_role="none")


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0031_pedidosmodel_comprobante_pago"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuariosmodel",
            name="worker_role",
            field=models.CharField(
                max_length=10,
                choices=[("none", "None"), ("total", "Total"), ("parcial", "Parcial")],
                default="none",
            ),
        ),
        migrations.AddField(
            model_name="usuariosmodel",
            name="can_add_products",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="usuariosmodel",
            name="can_edit_products",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="usuariosmodel",
            name="can_edit_prices",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="usuariosmodel",
            name="can_manage_discount_codes",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="usuariosmodel",
            name="can_apply_discounts",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="usuariosmodel",
            name="can_manage_offers",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(forward, reverse),
    ]

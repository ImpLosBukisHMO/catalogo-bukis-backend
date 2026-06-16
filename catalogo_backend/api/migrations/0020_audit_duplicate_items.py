"""
Audit migration: raise loudly if duplicate (producto_id, item) pairs exist
where item <> ''. No schema change. Reverse is a no-op.

This migration intentionally fails if duplicates are present — it is a
safety gate before the UniqueConstraint in 0021 is applied.
"""
from django.db import migrations


def audit_duplicate_items(apps, schema_editor):
    """
    Query the product_colores table (ProductoVariantesModel) for any
    duplicate (producto_id, item) pairs where item is not empty.
    Raise Exception with a printable list if any duplicates are found.
    """
    db_alias = schema_editor.connection.alias

    ProductoVariantesModel = apps.get_model("api", "ProductoVariantesModel")

    # Build duplicate groups in Python to stay ORM-compatible across
    # SQLite and Postgres without raw SQL.
    from collections import Counter

    pairs = ProductoVariantesModel.objects.using(db_alias).exclude(item="").values_list(
        "producto_id", "item"
    )
    counts = Counter(pairs)
    duplicates = {pair: count for pair, count in counts.items() if count > 1}

    if duplicates:
        lines = [
            f"  producto_id={producto_id}, item={item!r}, count={count}"
            for (producto_id, item), count in sorted(duplicates.items())
        ]
        raise Exception(
            "Audit failed: duplicate (producto_id, item) pairs found where item <> ''.\n"
            "Resolve duplicates before applying migration 0021_unique_item_per_producto.\n"
            "Duplicates:\n" + "\n".join(lines)
        )


def noop_reverse(apps, schema_editor):
    """Reverse is a no-op: no schema was changed."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0019_alter_variante_add_precio"),
    ]

    operations = [
        migrations.RunPython(audit_duplicate_items, reverse_code=noop_reverse),
    ]

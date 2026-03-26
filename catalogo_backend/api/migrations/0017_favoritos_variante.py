from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0016_move_item_to_variant"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="productosfavoritosmodel",
            name="producto",
        ),
        migrations.AddField(
            model_name="productosfavoritosmodel",
            name="variante",
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.CASCADE,
                to="api.productovariantesmodel",
            ),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name="productosfavoritosmodel",
            unique_together={("usuario", "variante")},
        ),
    ]

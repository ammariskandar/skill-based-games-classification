# Generated manually for SBGC-63 (non-null submitted_by after backfill).

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("classifications", "0003_backfill_submissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="editorialclassification",
            name="submitted_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="submitted_editorial_classifications",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]

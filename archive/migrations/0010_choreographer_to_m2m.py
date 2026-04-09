from django.db import migrations, models


def copy_choreographer_fk_to_m2m(apps, schema_editor):
    """Copy existing choreographer FK values into the new M2M relationship."""
    Piece = apps.get_model('archive', 'Piece')
    for piece in Piece.objects.filter(choreographer__isnull=False):
        piece.choreographers.add(piece.choreographer)


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0009_alter_customfield_choices_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='piece',
            options={'ordering': ['title'], 'verbose_name': 'Dance Work', 'verbose_name_plural': 'Dance Works'},
        ),
        # Step 1: Add M2M field (keep old FK for now)
        migrations.AddField(
            model_name='piece',
            name='choreographers',
            field=models.ManyToManyField(blank=True, related_name='choreographed_pieces', to='archive.person'),
        ),
        # Step 2: Copy existing FK data to M2M
        migrations.RunPython(copy_choreographer_fk_to_m2m, migrations.RunPython.noop),
        # Step 3: Remove old FK
        migrations.RemoveField(
            model_name='piece',
            name='choreographer',
        ),
    ]

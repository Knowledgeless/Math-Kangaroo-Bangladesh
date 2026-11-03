from django.db import migrations


LEVELS = (
    ("Pre-Ecolier", "pre-ecolier", 1, 2, 1, "A first adventure in mathematical thinking."),
    ("Ecolier", "ecolier", 3, 4, 2, "Patterns, puzzles and playful reasoning."),
    ("Benjamin", "benjamin", 5, 6, 3, "Fresh challenges for growing problem-solvers."),
    ("Cadet", "cadet", 7, 8, 4, "Build connections and explore new strategies."),
    ("Junior", "junior", 9, 10, 5, "Stretch your ideas and think beyond the obvious."),
    ("Student", "student", 11, 12, 6, "Big questions for confident, curious minds."),
)


def create_levels(apps, schema_editor):
    CompetitionLevel = apps.get_model("competitions", "CompetitionLevel")
    for name, code, min_grade, max_grade, order, description in LEVELS:
        CompetitionLevel.objects.using(schema_editor.connection.alias).get_or_create(
            code=code,
            defaults={
                "name": name,
                "min_grade": min_grade,
                "max_grade": max_grade,
                "display_order": order,
                "description": description,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("competitions", "0001_initial")]
    operations = [migrations.RunPython(create_levels, migrations.RunPython.noop)]

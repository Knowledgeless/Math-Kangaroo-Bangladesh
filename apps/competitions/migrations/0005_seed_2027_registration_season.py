from django.db import migrations


def seed_current_season(apps, schema_editor):
    database = schema_editor.connection.alias
    Season = apps.get_model("competitions", "CompetitionSeason")
    Level = apps.get_model("competitions", "CompetitionLevel")
    Division = apps.get_model("competitions", "CompetitionDivision")
    Sequence = apps.get_model("competitions", "RegistrationSequence")

    season, _ = Season.objects.using(database).get_or_create(
        slug="2027",
        defaults={
            "name": "Math Kangaroo Bangladesh 2027",
            "year": 2027,
            "status": "registration_open",
            "is_current": True,
        },
    )
    if not season.is_current:
        season.is_current = True
        season.save(using=database, update_fields=["is_current"])
    Sequence.objects.using(database).get_or_create(season=season, defaults={"next_number": 1})

    levels = Level.objects.using(database).all()
    for grade in range(1, 13):
        level = levels.filter(min_grade__lte=grade, max_grade__gte=grade).first()
        if level is None:
            continue
        Division.objects.using(database).get_or_create(
            season=season,
            grade=grade,
            defaults={"level": level, "ranking_group": f"Grade {grade}"},
        )


class Migration(migrations.Migration):
    dependencies = [("competitions", "0004_competitionseason_profile_edit_close_at_and_more")]
    operations = [migrations.RunPython(seed_current_season, migrations.RunPython.noop)]

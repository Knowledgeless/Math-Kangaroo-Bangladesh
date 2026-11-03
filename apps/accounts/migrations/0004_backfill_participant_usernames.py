from django.db import migrations, models


def assign_participant_ids(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    StudentProfile = apps.get_model("accounts", "StudentProfile")
    database = schema_editor.connection.alias
    counters = {}

    users = User.objects.using(database).order_by("date_joined", "pk")
    for user in users.iterator():
        year_prefix = user.date_joined.year % 100
        counters[year_prefix] = counters.get(year_prefix, 0) + 1
        if counters[year_prefix] > 99999:
            raise RuntimeError(f"Cannot assign a participant username for year {year_prefix:02d}.")
        user.username = f"{year_prefix:02d}{counters[year_prefix]:05d}"
        if not user.is_staff and user.role == "guardian":
            user.role = "student"
            StudentProfile.objects.using(database).get_or_create(user_id=user.pk)
        user.save(using=database, update_fields=["username", "role"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_studentprofile_date_of_birth_studentprofile_district_and_more")]

    operations = [
        migrations.RunPython(assign_participant_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(max_length=150, unique=True),
        ),
    ]

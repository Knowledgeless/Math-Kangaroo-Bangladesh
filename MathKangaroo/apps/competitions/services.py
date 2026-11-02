from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.audit.models import record_event
from apps.accounts.models import StudentProfile
from apps.competitions.models import (
    CompetitionDivision,
    CompetitionLevel,
    CompetitionRegistration,
    CompetitionSeason,
    RegistrationSequence,
)


@transaction.atomic
def register_student(*, student, season_id, school_name, grade, request=None):
    season = CompetitionSeason.objects.select_for_update().get(pk=season_id)
    if not season.is_registration_open():
        raise ValidationError("Registration for this competition year is not open.")
    if student.pk is not None and CompetitionRegistration.objects.filter(
        student=student, season=season
    ).exists():
        raise ValidationError("You are already registered for this competition year.")
    if not 1 <= grade <= 12:
        raise ValidationError({"grade": "Choose a grade from 1 to 12."})
    school_name = school_name.strip()
    if not school_name:
        raise ValidationError({"school_name": "Enter the student's school."})

    level = CompetitionLevel.objects.filter(
        min_grade__lte=grade,
        max_grade__gte=grade,
    ).first()
    if level is None:
        raise ValidationError({"grade": "There is no competition level configured for this grade."})

    division = CompetitionDivision.objects.filter(season=season, grade=grade).first()
    if division is None:
        division = CompetitionDivision.objects.create(
            season=season,
            level=level,
            grade=grade,
            ranking_group=f"Grade {grade}",
        )
    elif division.level_id != level.pk:
        raise ValidationError({"grade": "This grade is not configured for registration in the selected season."})

    sequence, _ = RegistrationSequence.objects.get_or_create(season=season)
    sequence = RegistrationSequence.objects.select_for_update().get(pk=sequence.pk)
    if sequence.next_number > 99999:
        raise ValidationError("Registration for this competition year has reached capacity.")
    registration_number = f"{season.year % 100:02d}{sequence.next_number:05d}"
    sequence.next_number += 1
    sequence.save(update_fields=["next_number"])

    if student.pk is None:
        if student.username:
            raise ValidationError("A new student account cannot choose its participant username.")
        student.username = registration_number
        student.role = student.Role.STUDENT
        student.save()
    elif not student.username:
        student.username = registration_number
        student.save(update_fields=["username"])

    try:
        with transaction.atomic():
            registration = CompetitionRegistration.objects.create(
                registration_number=registration_number,
                student=student,
                season=season,
                division=division,
                school_name=school_name,
                grade=grade,
            )
    except IntegrityError as error:
        raise ValidationError("This student is already registered for this competition year.") from error

    profile, _ = StudentProfile.objects.get_or_create(user=student)
    profile.grade = grade
    profile.save(update_fields=["grade"])
    if request is not None:
        record_event(request, action="registration.created", instance=registration)
    return registration

from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import CompetitionDivision, CompetitionLevel, CompetitionSeason


class CompetitionStructureTests(TestCase):
    def test_six_initial_levels_cover_grades_one_through_twelve(self):
        levels = list(CompetitionLevel.objects.order_by("display_order"))
        self.assertEqual(len(levels), 6)
        self.assertEqual([(level.min_grade, level.max_grade) for level in levels], [
            (1, 2),
            (3, 4),
            (5, 6),
            (7, 8),
            (9, 10),
            (11, 12),
        ])

    def test_division_grade_must_belong_to_selected_level(self):
        level = CompetitionLevel.objects.get(code="pre-ecolier")
        season = CompetitionSeason.objects.create(name="Test season", year=2027, slug="test-season")
        division = CompetitionDivision(season=season, level=level, grade=3)

        with self.assertRaises(ValidationError):
            division.full_clean()

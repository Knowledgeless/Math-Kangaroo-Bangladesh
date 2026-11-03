from django.db import migrations


FAQ_CATEGORIES = (
    ("Registration", "registration"),
    ("Competition", "competition"),
    ("Students", "students"),
    ("Parents", "parents"),
    ("Schools", "schools"),
    ("Centers", "centers"),
    ("Results", "results"),
    ("Certificates", "certificates"),
    ("Payment", "payment"),
)


def seed_public_site(apps, schema_editor):
    database = schema_editor.connection.alias
    FAQCategory = apps.get_model("cms", "FAQCategory")
    for order, (name, slug) in enumerate(FAQ_CATEGORIES, start=1):
        FAQCategory.objects.using(database).get_or_create(
            slug=slug,
            defaults={"name": name, "display_order": order},
        )

    SiteSettings = apps.get_model("cms", "SiteSettings")
    SiteSettings.objects.using(database).get_or_create(
        pk=1,
        defaults={
            "site_name": "Math Kangaroo Bangladesh",
            "tagline": "Think big. Wonder more.",
            "contact_email": "",
        },
    )

    HeroSlide = apps.get_model("cms", "HeroSlide")
    HeroSlide.objects.using(database).get_or_create(
        title="Think big. Wonder more.",
        defaults={
            "subtitle": (
                "A joyful mathematics challenge for curious students across Bangladesh. "
                "No memorising — just clever ideas, fresh perspectives and the fun of figuring it out."
            ),
            "button_1_label": "Find your level",
            "button_1_url": "#levels",
            "button_2_label": "Try a practice question",
            "button_2_url": "/questions/",
            "status": "published",
            "display_order": 1,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("cms", "0002_alter_heroslide_button_1_url_and_more"),
        ("competitions", "0002_seed_competition_levels"),
    ]
    operations = [migrations.RunPython(seed_public_site, migrations.RunPython.noop)]

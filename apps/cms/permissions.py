from django.contrib.auth.models import Group, Permission


STAFF_GROUP_PERMISSIONS = {
    "Account Manager": {
        "accounts": ("view_user", "change_user", "delete_user"),
        "competitions": ("view_competitionregistration", "view_competitionseason"),
    },
    "Content Editor": {
        "cms": (
            "view_announcement", "add_announcement", "change_announcement",
            "view_faq", "add_faq", "change_faq",
            "view_faqcategory", "view_heroslide", "add_heroslide", "change_heroslide",
            "publish_heroslide",
            "view_sitesettings", "change_sitesettings",
            "view_publicresource", "add_publicresource", "change_publicresource",
            "view_aboutpage", "manage_aboutpage",
            "view_questionpaper", "add_questionpaper", "change_questionpaper",
        ),
        "competitions": (
            "view_syllabus", "add_syllabus", "change_syllabus",
            "view_syllabustopic", "add_syllabustopic", "change_syllabustopic",
        ),
    },
    "Content Publisher": {
        "cms": (
            "view_announcement", "publish_announcement",
            "view_faq", "publish_faq",
            "view_heroslide", "publish_heroslide",
            "view_publicresource", "publish_publicresource",
            "view_questionpaper", "publish_questionpaper",
        ),
        "competitions": ("view_syllabus", "publish_syllabus"),
    },
    "Competition Manager": {
        "competitions": (
            "view_competitionseason", "add_competitionseason", "change_competitionseason",
            "view_competitionlevel", "add_competitionlevel", "change_competitionlevel",
            "view_competitiondivision", "add_competitiondivision", "change_competitiondivision",
            "view_competitionregistration", "change_competitionregistration",
            "view_syllabus", "add_syllabus", "change_syllabus",
            "view_syllabustopic", "add_syllabustopic", "change_syllabustopic",
            "publish_syllabus",
        ),
    },
    "Auditor": {
        "audit": ("view_auditlog",),
    },
}


def sync_staff_groups(sender, **_kwargs):
    if sender.label != "cms":
        return
    for group_name, app_permissions in STAFF_GROUP_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        permissions = Permission.objects.none()
        for app_label, codenames in app_permissions.items():
            permissions |= Permission.objects.filter(
                content_type__app_label=app_label,
                codename__in=codenames,
            )
        group.permissions.set(permissions)

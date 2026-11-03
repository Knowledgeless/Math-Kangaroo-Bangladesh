from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("announcements/", views.announcement_list, name="announcement-list"),
    path("announcements/<slug:slug>/", views.announcement_detail, name="announcement-detail"),
    path("faq/", views.faq_page, name="faq"),
    path("syllabus/", views.syllabus_page, name="syllabus"),
    path("questions/", views.questions_page, name="questions"),
    path("dashboard/content/", views.content_dashboard, name="cms-dashboard"),
    path("dashboard/audit/", views.audit_dashboard, name="audit-dashboard"),
    path("dashboard/content/settings/", views.site_settings_edit, name="cms-site-settings"),
    path("dashboard/content/announcements/new/", views.announcement_create, name="cms-announcement-create"),
    path("dashboard/content/announcements/<int:pk>/edit/", views.announcement_update, name="cms-announcement-edit"),
    path("dashboard/content/announcements/<int:pk>/archive/", views.announcement_archive, name="cms-announcement-archive"),
    path("dashboard/content/faqs/new/", views.faq_create, name="cms-faq-create"),
    path("dashboard/content/faqs/<int:pk>/edit/", views.faq_update, name="cms-faq-edit"),
    path("dashboard/homepage/slides/add/", views.hero_slide_create, name="hero-slide-create"),
    path("dashboard/homepage/slides/<int:pk>/order/", views.hero_slide_order, name="hero-slide-order"),
    path("dashboard/homepage/slides/<int:pk>/remove/", views.hero_slide_archive, name="hero-slide-remove"),
]

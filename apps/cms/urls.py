from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("announcements/", views.announcement_list, name="announcement-list"),
    path("announcements/<slug:slug>/", views.announcement_detail, name="announcement-detail"),
    path("about/", views.about_page, name="about"),
    path("faq/", views.faq_page, name="faq"),
    path("syllabus/", views.syllabus_page, name="syllabus"),
    path("questions/", views.questions_page, name="questions"),
    path("questions/papers/<int:pk>/download/", views.question_paper_download, name="question-paper-download"),
    path("dashboard/content/", views.content_dashboard, name="cms-dashboard"),
    path("dashboard/audit/", views.audit_dashboard, name="audit-dashboard"),
    path("dashboard/content/settings/", views.site_settings_edit, name="cms-site-settings"),
    path("dashboard/content/about/", views.about_page_edit, name="cms-about-edit"),
    path("dashboard/content/announcements/new/", views.announcement_create, name="cms-announcement-create"),
    path("dashboard/content/announcements/<int:pk>/edit/", views.announcement_update, name="cms-announcement-edit"),
    path("dashboard/content/announcements/<int:pk>/archive/", views.announcement_archive, name="cms-announcement-archive"),
    path("dashboard/content/faqs/new/", views.faq_create, name="cms-faq-create"),
    path("dashboard/content/faqs/<int:pk>/edit/", views.faq_update, name="cms-faq-edit"),
    path("dashboard/content/syllabuses/new/", views.syllabus_create, name="cms-syllabus-create"),
    path("dashboard/content/syllabuses/<int:pk>/edit/", views.syllabus_update, name="cms-syllabus-edit"),
    path("dashboard/content/question-papers/new/", views.question_paper_create, name="cms-question-paper-create"),
    path("dashboard/content/question-papers/<int:pk>/edit/", views.question_paper_update, name="cms-question-paper-edit"),
    path("dashboard/content/question-papers/<int:pk>/archive/", views.question_paper_archive, name="cms-question-paper-archive"),
    path("dashboard/homepage/slides/add/", views.hero_slide_create, name="hero-slide-create"),
    path("dashboard/homepage/slides/<int:pk>/order/", views.hero_slide_order, name="hero-slide-order"),
    path("dashboard/homepage/slides/<int:pk>/remove/", views.hero_slide_archive, name="hero-slide-remove"),
]

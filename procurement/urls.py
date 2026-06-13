from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("notifications/", views.notifications, name="notifications"),
    path("suppliers/", views.supplier_registry, name="supplier_registry"),
    path("tenders/", views.tender_list, name="tender_list"),
    path("tenders/new/", views.tender_create, name="tender_create"),
    path("tenders/<int:pk>/", views.tender_detail, name="tender_detail"),
    path("tenders/<int:pk>/bid/", views.bid_submit, name="bid_submit"),
    path("tenders/<int:pk>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("tenders/<int:pk>/question/", views.ask_question, name="ask_question"),
    path("tenders/<int:pk>/lot/", views.add_lot, name="add_lot"),
    path("tenders/<int:pk>/document/", views.add_document, name="add_document"),
    path("questions/<int:question_pk>/answer/", views.answer_question, name="answer_question"),
    path("suppliers/<int:application_pk>/<str:decision>/", views.review_supplier, name="review_supplier"),
    path("tenders/<int:tender_pk>/winner/<int:bid_pk>/", views.select_winner, name="select_winner"),
]

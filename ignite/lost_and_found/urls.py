from django.urls import path

from . import views

app_name = "lost_and_found"

urlpatterns = [
    path("", views.lost_page, name="lost"),
    path("found/", views.found_page, name="found"),
    path("found/<int:found_item_id>/matches/", views.found_matches, name="found_matches"),
    path("lost/<int:lost_item_id>/found/", views.claim_lost_item, name="claim_lost"),
    path(
        "lost/<int:lost_item_id>/found/<int:found_item_id>/",
        views.claim_lost_item,
        name="claim_matched_lost",
    ),
]

"""URL routes for the admin security perimeter — SBGC-106."""

from django.urls import path

from security import views

app_name = "security"

urlpatterns = [
    path("waiting-room/", views.waiting_room, name="waiting_room"),
    path("challenge-status/", views.challenge_status, name="challenge_status"),
    path("review-login/", views.review_login, name="review_login"),
]

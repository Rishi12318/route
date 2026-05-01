from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("plan-route/", views.plan_route, name="plan-route"),
]

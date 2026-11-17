from django.urls import path

from . import views

app_name = "ponto"

urlpatterns = [
    path("", views.meu_ponto, name="meu_ponto"),
    path("log/", views.log, name="log"),
]

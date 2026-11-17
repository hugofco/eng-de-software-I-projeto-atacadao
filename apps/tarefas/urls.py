from django.urls import path

from . import views

app_name = "tarefas"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("nova/", views.nova, name="nova"),
    path("painel/", views.painel, name="painel"),
    path("minhas/", views.minhas, name="minhas"),
    path("<int:pk>/status/", views.alterar_status, name="status"),
]

"""Autenticação por CPF OU matrícula (seção 2.4 do documento)."""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .validators import somente_digitos


class MatriculaOuCpfBackend(ModelBackend):
    """Aceita no campo 'usuário' a matrícula ou o CPF (com ou sem pontuação).

    Herda de ModelBackend para manter: bloqueio de usuários inativos (RS03) tanto
    no login quanto em sessões já abertas (get_user) e as permissões do /admin/.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        Modelo = get_user_model()
        if username is None:
            username = kwargs.get(Modelo.USERNAME_FIELD)
        if not username or password is None:
            return None

        identificador = username.strip()
        digitos = somente_digitos(identificador)
        criterio = Q(matricula__iexact=identificador)
        if len(digitos) == 11:
            criterio |= Q(cpf=digitos)

        usuario = Modelo.objects.filter(criterio).first()
        if usuario is None:
            # Gasta o mesmo tempo de um hash real para não revelar se o usuário existe.
            Modelo().set_password(password)
            return None
        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None

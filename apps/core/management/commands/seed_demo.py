"""
Popula o banco com uma loja de demonstração para testar o protótipo à mão.

    python manage.py seed_demo

É idempotente: se a demonstração já existe, não faz nada. Para recomeçar,
apague o banco (SQLite: remova db.sqlite3 e rode `make setup` de novo).
Senha de todos os usuários demo: demo1234
"""
from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Funcionario
from apps.accounts.validators import digitos_verificadores
from apps.comunicacao.models import Comunicado, DestinoComunicado, Mensagem
from apps.core.models import Cargo, Filial, Setor, Terminal
from apps.core.perfis import Perfil
from apps.core.turnos import Turno
from apps.escalas.models import Escala, Ocorrencia, TipoOcorrencia
from apps.ponto.models import RegistroPonto, TipoRegistro
from apps.tarefas.models import StatusTarefa, Tarefa

SENHA = "demo1234"

SETORES = [
    ("Bebidas", "Bebidas, Cervejas, Refrigerantes, Águas", "201"),
    ("Mercearia", "Arroz, Feijão, Óleo, Enlatados, Massas", "202"),
    ("Limpeza", "Produtos de limpeza e higiene", "203"),
    ("Açougue", "Carnes, Aves, Frios", "204"),
    ("Hortifruti", "Frutas, Verduras, Legumes", "205"),
]
CARGOS = ["Gerente de Loja", "Repositor", "Auxiliar de Limpeza", "Açougueiro", "Fiscal de Loja",
          "Comprador"]

# (matrícula, nome, perfil, setor, cargo, turno, carga semanal, padrão de dias)
PESSOAS = [
    ("G001", "Marta Oliveira", Perfil.GERENTE, "Mercearia", "Gerente de Loja", Turno.MANHA, 44, None),
    ("F001", "Carlos Souza", Perfil.FUNCIONARIO, "Bebidas", "Repositor", Turno.MANHA, 36, "seg-sab"),
    ("F002", "Ana Lima", Perfil.FUNCIONARIO, "Bebidas", "Repositor", Turno.TARDE, 36, "ter-dom"),
    ("F003", "João Pereira", Perfil.FUNCIONARIO, "Limpeza", "Auxiliar de Limpeza", Turno.MANHA, 36, "seg-sab"),
    ("F004", "Beatriz Alves", Perfil.FUNCIONARIO, "Açougue", "Açougueiro", Turno.TARDE, 36, "ter-dom"),
    ("F005", "Rafael Costa", Perfil.FUNCIONARIO, "Hortifruti", "Repositor", Turno.NOITE, 36, "seg-sab"),
    ("F006", "Luiza Fernandes", Perfil.FUNCIONARIO, "Mercearia", "Repositor", Turno.TARDE, 24, "meio"),
    ("C001", "Pedro Compras", Perfil.COMPRADOR, "Mercearia", "Comprador", Turno.MANHA, 36, None),
]

PADROES = {  # dias da semana (0 = segunda)
    "seg-sab": [0, 1, 2, 3, 4, 5],
    "ter-dom": [1, 2, 3, 4, 5, 6],
    "meio": [0, 2, 4, 5],  # 4 dias x 6 h = 24 h
}


def _cpf(n: int) -> str:
    """CPF válido e determinístico para dados de demonstração (não pertencem a ninguém)."""
    base = f"{100000000 + n * 7919:09d}"[:9]
    return base + digitos_verificadores(base)


class Command(BaseCommand):
    help = "Cria dados de demonstração (loja, setores, usuários, escalas, tarefas, ponto...)."

    @transaction.atomic
    def handle(self, *args, **opcoes):
        if Funcionario.objects.filter(matricula="G001").exists():
            self.stdout.write("Dados de demonstração já existem; nada a fazer.")
            return

        agora = timezone.now()
        hoje_local = timezone.localdate()

        filial = Filial.objects.create(nome="Atacadão Demonstração")
        setores = {n: Setor.objects.create(filial=filial, nome=n, areas=a, ramal=r)
                   for n, a, r in SETORES}
        cargos = {n: Cargo.objects.create(nome=n) for n in CARGOS}
        Terminal.objects.create(filial=filial, nome="Terminal Demo (localhost)", ip_address="127.0.0.1")

        pessoas = {}
        for i, (mat, nome, perfil, setor, cargo, turno, carga, padrao) in enumerate(PESSOAS, start=1):
            pessoas[mat] = Funcionario.objects.create_user(
                matricula=mat, password=SENHA, nome=nome, cpf=_cpf(i),
                data_nascimento=date(1985 + i, 3, 10), perfil=perfil, filial=filial,
                setor=setores[setor], cargo=cargos[cargo], turno=turno, carga_horaria_semanal=carga)
            for dia in PADROES.get(padrao, []):
                Escala.objects.create(funcionario=pessoas[mat], dia_semana=dia, turno=turno,
                                      atualizada_por=pessoas["G001"])

        gerente = pessoas["G001"]

        # Tarefas em estados variados. O prazo é um horário FIXO do dia local (e não
        # "agora + N horas"), para que apareçam no painel do dia em qualquer hora de
        # execução do seed. A última é de ontem: aparece como "atrasada" no painel.
        # (título, setor, status, responsáveis, deslocamento em dias, hora do prazo)
        exemplos = [
            ("Repor cervejas na gôndola 3", "Bebidas", StatusTarefa.PENDENTE, ["F001", "F002"], 0, 15),
            ("Organizar estoque de refrigerantes", "Bebidas", StatusTarefa.EM_ANDAMENTO, ["F002"], 0, 17),
            ("Limpeza do corredor central", "Limpeza", StatusTarefa.PENDENTE, ["F003"], 0, 14),
            ("Higienizar balcão de carnes", "Açougue", StatusTarefa.CONCLUIDA, ["F004"], 0, 12),
            ("Montar bancada de frutas", "Hortifruti", StatusTarefa.EM_ANDAMENTO, ["F005"], 0, 18),
            ("Conferir validade de enlatados", "Mercearia", StatusTarefa.PENDENTE, ["F006"], -1, 17),
        ]
        for titulo, setor, status, responsaveis, desloc, hora in exemplos:
            prazo = timezone.make_aware(
                datetime.combine(hoje_local + timedelta(days=desloc), time(hora, 0)))
            tarefa = Tarefa.objects.create(
                titulo=titulo, descricao="Tarefa de demonstração.", setor=setores[setor],
                prazo=prazo, status=status, criada_por=gerente,
                concluida_em=agora if status == StatusTarefa.CONCLUIDA else None)
            tarefa.responsaveis.set([pessoas[m] for m in responsaveis])

        # Ponto dos últimos 3 dias (registrado_em explícito: é só seed, o app nunca faz isso).
        for mat in ("F001", "F003"):
            for dias_atras in (3, 2, 1):
                dia = hoje_local - timedelta(days=dias_atras)
                inicio = timezone.make_aware(datetime.combine(dia, time(6, 0)))
                RegistroPonto.objects.create(funcionario=pessoas[mat], tipo=TipoRegistro.ENTRADA,
                                             registrado_em=inicio, ip_origem="127.0.0.1")
                RegistroPonto.objects.create(funcionario=pessoas[mat], tipo=TipoRegistro.SAIDA,
                                             registrado_em=inicio + timedelta(hours=6, minutes=5),
                                             ip_origem="127.0.0.1")

        Ocorrencia.objects.create(funcionario=pessoas["F002"], tipo=TipoOcorrencia.ATRASO,
                                  data=hoje_local - timedelta(days=1), observacao="Chegou 15 min atrasada.",
                                  registrada_por=gerente)
        Comunicado.objects.create(filial=filial, autor=gerente, destino_tipo=DestinoComunicado.TODOS,
                                  texto="Bem-vindos! Reunião rápida de equipe amanhã às 7h50.")
        Comunicado.objects.create(filial=filial, autor=gerente, destino_tipo=DestinoComunicado.SETOR,
                                  setor=setores["Bebidas"],
                                  texto="Bebidas: chegou carga nova, priorizar a reposição das cervejas.")
        Mensagem.objects.create(remetente=pessoas["F001"],
                                texto="Posso trocar o turno de sábado com o João?")

        self.stdout.write(self.style.SUCCESS(
            "Dados de demonstração criados.\n"
            f"  Gerente:     G001 / {SENHA}\n"
            f"  Funcionário: F001 / {SENHA}   (também F002..F006)\n"
            f"  Comprador:   C001 / {SENHA}"))

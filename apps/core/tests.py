"""Testes do núcleo: turnos, controle de acesso por perfil, diretório (RS18) e seed."""
from datetime import time
from io import StringIO

from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from apps.accounts.models import Funcionario
from apps.escalas import services as escalas_services
from apps.escalas.models import Escala

from .testing import SENHA, criar_cenario
from .turnos import descanso_entre, horas_do_turno, turno_em


class TurnosTests(SimpleTestCase):
    def test_horas_por_turno(self):
        for turno in ("manha", "tarde", "noite"):
            self.assertEqual(horas_do_turno(turno), 6)

    def test_turno_em_cada_hora(self):
        casos = {5: None, 6: "manha", 11: "manha", 12: "tarde", 17: "tarde", 18: "noite", 23: "noite", 0: None}
        for hora, esperado in casos.items():
            with self.subTest(hora=hora):
                self.assertEqual(turno_em(time(hora, 30)), esperado)

    def test_descanso_entre_turnos(self):
        self.assertEqual(descanso_entre("noite", "manha"), 6)    # curto demais (< 11 h)
        self.assertEqual(descanso_entre("tarde", "manha"), 12)
        self.assertEqual(descanso_entre("manha", "manha"), 18)


class AcessoPorPerfilTests(TestCase):
    """Seção 3: o acesso é estritamente ajustado à hierarquia."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def test_paginas_protegidas_redirecionam_anonimo(self):
        for nome in ("core:home", "core:diretorio", "tarefas:lista", "escalas:minha",
                     "ponto:meu_ponto", "ponto:log", "comunicacao:meus"):
            with self.subTest(rota=nome):
                resposta = self.client.get(reverse(nome))
                self.assertEqual(resposta.status_code, 302)
                self.assertIn(reverse("accounts:login"), resposta["Location"])

    def test_comprador_so_acessa_o_diretorio(self):
        self.client.login(username="C1", password=SENHA)
        proibidas = ("accounts:lista", "tarefas:lista", "tarefas:painel", "tarefas:minhas",
                     "escalas:visao_geral", "escalas:minha", "escalas:ocorrencias", "escalas:remanejar",
                     "ponto:meu_ponto", "ponto:log", "comunicacao:enviar", "comunicacao:meus",
                     "comunicacao:caixa", "comunicacao:nova_mensagem")
        for nome in proibidas:
            with self.subTest(rota=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 403)
        self.assertEqual(self.client.get(reverse("core:diretorio")).status_code, 200)

    def test_funcionario_nao_acessa_rotas_do_gerente(self):
        self.client.login(username="F1", password=SENHA)
        for nome in ("accounts:lista", "tarefas:lista", "tarefas:painel", "tarefas:nova",
                     "escalas:visao_geral", "escalas:ocorrencias", "escalas:remanejar", "ponto:log",
                     "comunicacao:enviar", "comunicacao:caixa"):
            with self.subTest(rota=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 403)

    def test_gerente_nao_usa_rotas_exclusivas_do_funcionario(self):
        self.client.login(username="G1", password=SENHA)
        for nome in ("tarefas:minhas", "escalas:minha", "ponto:meu_ponto", "comunicacao:meus",
                     "comunicacao:nova_mensagem"):
            with self.subTest(rota=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 403)

    def test_pagina_403_usa_o_template_do_projeto(self):
        self.client.login(username="F1", password=SENHA)
        resposta = self.client.get(reverse("accounts:lista"))
        self.assertTemplateUsed(resposta, "403.html")

    def test_home_por_perfil(self):
        self.client.login(username="C1", password=SENHA)
        self.assertRedirects(self.client.get(reverse("core:home")), reverse("core:diretorio"))
        self.client.login(username="G1", password=SENHA)
        resposta = self.client.get(reverse("core:home"))
        self.assertContains(resposta, reverse("accounts:lista"))      # menu do gerente
        self.client.login(username="F1", password=SENHA)
        resposta = self.client.get(reverse("core:home"))
        self.assertNotContains(resposta, reverse("accounts:lista"))   # funcionário não vê o menu de gestão
        self.assertContains(resposta, reverse("ponto:meu_ponto"))

    def test_logout_exige_post(self):
        self.client.login(username="F1", password=SENHA)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.client.post(reverse("accounts:logout"))
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 302)


class DiretorioTests(TestCase):
    """RS18 — comprador consulta setor e responsável, vendo apenas nome e setor."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def setUp(self):
        self.client.login(username="C1", password=SENHA)
        self.url = reverse("core:diretorio")

    def test_busca_por_area_do_setor(self):
        resposta = self.client.get(self.url, {"q": "cerveja"})
        linhas = resposta.context["linhas"]
        self.assertEqual([l["setor"].pk for l in linhas], [self.c.setor_a.pk])
        self.assertEqual(linhas[0]["funcionarios"], [self.c.func1.nome])

    def test_nao_expoe_dados_de_gestao(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, self.c.func1.nome)
        self.assertContains(resposta, self.c.setor_a.nome)
        for proibido in (self.c.func1.cpf, self.c.func1.cpf_formatado, self.c.cargo.nome,
                         "Carga horária"):
            with self.subTest(dado=proibido):
                self.assertNotContains(resposta, proibido)

    def test_nao_mostra_funcionarios_inativos_nem_outras_filiais(self):
        self.c.func2.is_active = False
        self.c.func2.save()
        resposta = self.client.get(self.url)
        nomes = [n for l in resposta.context["linhas"] for n in l["funcionarios"]]
        self.assertNotIn(self.c.func2.nome, nomes)
        self.assertNotIn(self.c.func_outra.nome, nomes)

    def test_busca_sem_resultado(self):
        resposta = self.client.get(self.url, {"q": "inexistente-xyz"})
        self.assertEqual(resposta.context["linhas"], [])


class SeedTests(TestCase):
    """O comando seed_demo deve rodar, ser idempotente e gerar dados que obedecem às regras."""

    def rodar(self):
        call_command("seed_demo", stdout=StringIO())

    def test_seed_cria_usuarios_que_conseguem_entrar(self):
        self.rodar()
        for matricula in ("G001", "F001", "C001"):
            with self.subTest(matricula=matricula):
                self.assertTrue(Client().login(username=matricula, password="demo1234"))

    def test_seed_e_idempotente(self):
        self.rodar()
        total = Funcionario.objects.count()
        self.rodar()
        self.assertEqual(Funcionario.objects.count(), total)

    def test_escalas_do_seed_respeitam_as_regras(self):
        self.rodar()
        for f in Funcionario.objects.filter(escalas__isnull=False).distinct():
            turnos = {e.dia_semana: e.turno for e in Escala.objects.filter(funcionario=f)}
            with self.subTest(funcionario=f.matricula):
                self.assertEqual(escalas_services.validar_escala(f, turnos), [])

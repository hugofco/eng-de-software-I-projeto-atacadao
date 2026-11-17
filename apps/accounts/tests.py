"""Testes de RS01 (cadastro), RS02 (edição), RS03 (desativação) e do login por CPF/matrícula."""
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.testing import SENHA, criar_cenario, gerar_cpf
from apps.ponto.models import RegistroPonto, TipoRegistro

from .models import AlteracaoFuncionario, Funcionario
from .validators import cpf_valido, validate_nascimento, validate_nome


class ValidadoresTests(SimpleTestCase):
    def test_cpf_valido_com_e_sem_pontuacao(self):
        self.assertTrue(cpf_valido("529.982.247-25"))
        self.assertTrue(cpf_valido("52998224725"))

    def test_cpf_invalido(self):
        for ruim in ("529.982.247-26", "111.111.111-11", "123", "", None, "abcdefghijk"):
            with self.subTest(cpf=ruim):
                self.assertFalse(cpf_valido(ruim))

    def test_nome_deve_comecar_com_letra(self):
        validate_nome("Maria")
        validate_nome("Álvaro Neto")
        for ruim in ("1Maria", "@Maria", "-João", "  9abc"):
            with self.subTest(nome=ruim), self.assertRaises(ValidationError):
                validate_nome(ruim)

    def test_nascimento_futuro_ou_menor_de_16_anos(self):
        hoje = timezone.localdate()
        with self.assertRaises(ValidationError):
            validate_nascimento(hoje + timedelta(days=1))
        with self.assertRaises(ValidationError):
            validate_nascimento(hoje)
        with self.assertRaises(ValidationError):
            validate_nascimento(date(hoje.year - 15, hoje.month, 1))
        validate_nascimento(date(hoje.year - 30, 1, 1))  # não levanta


class CadastroTests(TestCase):
    """RS01 — cadastro de funcionário."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def setUp(self):
        self.client.login(username="G1", password=SENHA)
        self.url = reverse("accounts:novo")

    def dados(self, **sobrescrever):
        base = {
            "nome": "Novo Funcionário", "cpf": gerar_cpf(50), "data_nascimento": "1995-05-20",
            "perfil": "funcionario", "cargo": self.c.cargo.pk, "setor": self.c.setor_a.pk,
            "turno": "manha", "carga_horaria_semanal": 36, "senha_inicial": "",
        }
        base.update(sobrescrever)
        return base

    def test_cadastro_valido(self):
        resposta = self.client.post(self.url, self.dados())
        self.assertRedirects(resposta, reverse("accounts:lista"))
        novo = Funcionario.objects.get(cpf=gerar_cpf(50))
        self.assertEqual(novo.filial, self.c.filial)           # herda a filial do gerente
        self.assertEqual(novo.matricula, f"{novo.pk:05d}")      # matrícula sequencial
        self.assertTrue(novo.is_active)
        self.assertTrue(novo.has_usable_password())

    def test_cpf_formatado_e_gravado_so_com_digitos(self):
        self.client.post(self.url, self.dados(cpf="529.982.247-25"))
        self.assertTrue(Funcionario.objects.filter(cpf="52998224725").exists())

    def test_senha_inicial_informada_permite_login(self):
        self.client.post(self.url, self.dados(senha_inicial="outra-senha-123"))
        novo = Funcionario.objects.get(cpf=gerar_cpf(50))
        self.assertTrue(Client().login(username=novo.matricula, password="outra-senha-123"))

    def test_senha_temporaria_exibida_quando_nao_informada(self):
        resposta = self.client.post(self.url, self.dados(), follow=True)
        textos = [m.message for m in resposta.context["messages"]]
        self.assertTrue(any("Senha temporária" in t for t in textos))

    def rejeita(self, campo, **sobrescrever):
        antes = Funcionario.objects.count()
        resposta = self.client.post(self.url, self.dados(**sobrescrever))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn(campo, resposta.context["form"].errors)
        self.assertEqual(Funcionario.objects.count(), antes)

    def test_rejeita_cpf_invalido(self):
        self.rejeita("cpf", cpf="123.456.789-00")

    def test_rejeita_cpf_duplicado(self):
        self.rejeita("cpf", cpf=self.c.func1.cpf)

    def test_rejeita_cpf_duplicado_mesmo_formatado(self):
        c = self.c.func1.cpf
        self.rejeita("cpf", cpf=f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}")

    def test_rejeita_nome_iniciando_com_numero_ou_especial(self):
        self.rejeita("nome", nome="9 Fulano")
        self.rejeita("nome", nome="#Fulano")

    def test_rejeita_menor_de_16_anos(self):
        hoje = timezone.localdate()
        self.rejeita("data_nascimento", data_nascimento=date(hoje.year - 10, 1, 1).isoformat())

    def test_rejeita_nascimento_futuro(self):
        self.rejeita("data_nascimento", data_nascimento=(timezone.localdate() + timedelta(days=5)).isoformat())

    def test_rejeita_turno_fora_da_lista(self):
        self.rejeita("turno", turno="madrugada")

    def test_rejeita_setor_de_outra_filial(self):
        self.rejeita("setor", setor=self.c.setor_outra.pk)

    def test_rejeita_cargo_ou_setor_ausente(self):
        self.rejeita("cargo", cargo="")
        self.rejeita("setor", setor="")


class EdicaoTests(TestCase):
    """RS02 — edição com registro da última alteração."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def setUp(self):
        self.client.login(username="G1", password=SENHA)
        self.url = reverse("accounts:editar", args=[self.c.func1.pk])

    def dados(self, **sobrescrever):
        f = self.c.func1
        base = {"nome": f.nome, "cpf": f.cpf, "data_nascimento": f.data_nascimento.isoformat(),
                "perfil": f.perfil, "cargo": f.cargo_id, "setor": f.setor_id, "turno": f.turno,
                "carga_horaria_semanal": f.carga_horaria_semanal}
        base.update(sobrescrever)
        return base

    def test_edicao_registra_data_usuario_e_trilha(self):
        self.assertIsNone(self.c.func1.atualizado_em)
        resposta = self.client.post(self.url, self.dados(turno="tarde", setor=self.c.setor_b.pk))
        self.assertRedirects(resposta, reverse("accounts:lista"))

        f = Funcionario.objects.get(pk=self.c.func1.pk)
        self.assertEqual((f.turno, f.setor), ("tarde", self.c.setor_b))
        self.assertEqual(f.atualizado_por, self.c.gerente)
        self.assertIsNotNone(f.atualizado_em)

        campos = {a.campo: (a.valor_anterior, a.valor_novo) for a in f.alteracoes.all()}
        self.assertEqual(campos["turno"], ("manha", "tarde"))
        self.assertEqual(campos["setor"], ("Bebidas", "Limpeza"))
        self.assertNotIn("nome", campos)

    def test_sem_mudancas_nao_registra_nada(self):
        self.client.post(self.url, self.dados())
        f = Funcionario.objects.get(pk=self.c.func1.pk)
        self.assertIsNone(f.atualizado_em)
        self.assertFalse(AlteracaoFuncionario.objects.exists())

    def test_nao_permite_cpf_de_outro_funcionario(self):
        resposta = self.client.post(self.url, self.dados(cpf=self.c.func2.cpf))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("cpf", resposta.context["form"].errors)

    def test_editar_funcionario_de_outra_filial_da_404(self):
        resposta = self.client.get(reverse("accounts:editar", args=[self.c.func_outra.pk]))
        self.assertEqual(resposta.status_code, 404)

    def test_gerente_nao_altera_o_proprio_perfil(self):
        g = self.c.gerente
        dados = self.dados(nome=g.nome, cpf=g.cpf, data_nascimento=g.data_nascimento.isoformat(),
                           cargo=g.cargo_id, setor=g.setor_id, turno=g.turno,
                           carga_horaria_semanal=g.carga_horaria_semanal, perfil="funcionario")
        self.client.post(reverse("accounts:editar", args=[g.pk]), dados)
        g.refresh_from_db()
        self.assertEqual(g.perfil, "gerente")


class DesativacaoTests(TestCase):
    """RS03 — desativar remove o acesso sem apagar histórico."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def setUp(self):
        self.client.login(username="G1", password=SENHA)

    def desativar(self, funcionario):
        return self.client.post(reverse("accounts:status", args=[funcionario.pk]))

    def test_desativado_nao_consegue_entrar_e_historico_permanece(self):
        RegistroPonto.objects.create(funcionario=self.c.func1, tipo=TipoRegistro.ENTRADA)
        self.desativar(self.c.func1)
        self.c.func1.refresh_from_db()
        self.assertFalse(self.c.func1.is_active)
        self.assertFalse(Client().login(username="F1", password=SENHA))
        self.assertEqual(RegistroPonto.objects.filter(funcionario=self.c.func1).count(), 1)
        self.assertTrue(AlteracaoFuncionario.objects.filter(campo="status", valor_novo="inativo").exists())

    def test_sessao_ja_aberta_perde_o_acesso(self):
        outro = Client()
        self.assertTrue(outro.login(username="F1", password=SENHA))
        self.assertEqual(outro.get(reverse("core:home")).status_code, 200)
        self.desativar(self.c.func1)
        resposta = outro.get(reverse("core:home"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("accounts:login"), resposta["Location"])

    def test_reativar(self):
        self.desativar(self.c.func1)
        self.desativar(self.c.func1)
        self.c.func1.refresh_from_db()
        self.assertTrue(self.c.func1.is_active)

    def test_gerente_nao_desativa_a_si_mesmo(self):
        self.desativar(self.c.gerente)
        self.c.gerente.refresh_from_db()
        self.assertTrue(self.c.gerente.is_active)

    def test_nao_e_possivel_excluir_funcionario_com_ponto(self):
        RegistroPonto.objects.create(funcionario=self.c.func1, tipo=TipoRegistro.ENTRADA)
        with self.assertRaises(ProtectedError):
            self.c.func1.delete()

    def test_status_exige_post(self):
        resposta = self.client.get(reverse("accounts:status", args=[self.c.func1.pk]))
        self.assertEqual(resposta.status_code, 405)


class LoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def test_login_por_matricula_e_por_cpf(self):
        self.assertTrue(Client().login(username="F1", password=SENHA))
        self.assertTrue(Client().login(username=self.c.func1.cpf, password=SENHA))
        self.assertTrue(Client().login(username=self.c.func1.cpf_formatado, password=SENHA))

    def test_senha_errada_ou_usuario_inexistente(self):
        self.assertFalse(Client().login(username="F1", password="errada"))
        self.assertFalse(Client().login(username="NAO-EXISTE", password=SENHA))

    def test_login_pela_tela_redireciona_para_o_inicio(self):
        resposta = self.client.post(reverse("accounts:login"),
                                    {"username": self.c.func1.cpf_formatado, "password": SENHA})
        self.assertRedirects(resposta, reverse("core:home"))

    def test_login_pela_tela_com_senha_errada_mostra_erro(self):
        resposta = self.client.post(reverse("accounts:login"), {"username": "F1", "password": "x"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "incorretos")


class PermissoesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def test_anonimo_vai_para_o_login(self):
        resposta = self.client.get(reverse("accounts:lista"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("accounts:login"), resposta["Location"])

    def test_funcionario_e_comprador_nao_acessam_gestao_de_funcionarios(self):
        for matricula in ("F1", "C1"):
            self.client.login(username=matricula, password=SENHA)
            for nome in ("accounts:lista", "accounts:novo"):
                with self.subTest(usuario=matricula, rota=nome):
                    self.assertEqual(self.client.get(reverse(nome)).status_code, 403)
            self.client.logout()

    def test_listagem_do_gerente_so_mostra_a_propria_filial(self):
        self.client.login(username="G1", password=SENHA)
        resposta = self.client.get(reverse("accounts:lista"))
        matriculas = {f.matricula for f in resposta.context["pagina"]}
        self.assertIn("F1", matriculas)
        self.assertNotIn("X1", matriculas)

    def test_filtros_da_listagem(self):
        self.client.login(username="G1", password=SENHA)
        url = reverse("accounts:lista")
        por_nome = self.client.get(url, {"q": "Pessoa F2"}).context["pagina"]
        self.assertEqual([f.matricula for f in por_nome], ["F2"])
        por_setor = self.client.get(url, {"setor": self.c.setor_b.pk}).context["pagina"]
        self.assertEqual([f.matricula for f in por_setor], ["F2"])
        por_cpf = self.client.get(url, {"q": self.c.func1.cpf}).context["pagina"]
        self.assertEqual([f.matricula for f in por_cpf], ["F1"])

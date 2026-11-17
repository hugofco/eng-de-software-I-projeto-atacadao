"""Testes de RS04 (criação), RS05 (consulta), RS10 (painel) e RS13 (status pelo funcionário)."""
from datetime import datetime, time, timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Setor
from apps.core.testing import SENHA, criar_cenario

from . import services
from .models import StatusTarefa as S
from .models import Tarefa


def nova_tarefa(c, titulo="Tarefa", setor=None, status=S.PENDENTE, responsaveis=(), prazo=None):
    tarefa = Tarefa.objects.create(
        titulo=titulo, setor=setor or c.setor_a, status=status, criada_por=c.gerente,
        prazo=prazo or timezone.now() + timedelta(hours=3))
    tarefa.responsaveis.set(responsaveis)
    return tarefa


class CriacaoTests(TestCase):
    """RS04."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def setUp(self):
        self.client.login(username="G1", password=SENHA)
        self.url = reverse("tarefas:nova")

    def dados(self, **sobrescrever):
        prazo = timezone.localtime(timezone.now() + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M")
        base = {"titulo": "Repor cervejas", "descricao": "Gôndola 3", "setor": self.c.setor_a.pk,
                "prazo": prazo, "responsaveis": [self.c.func1.pk]}
        base.update(sobrescrever)
        return base

    def test_cria_e_fica_visivel_para_o_responsavel(self):
        resposta = self.client.post(self.url, self.dados())
        self.assertRedirects(resposta, reverse("tarefas:lista"))
        tarefa = Tarefa.objects.get(titulo="Repor cervejas")
        self.assertEqual(tarefa.status, S.PENDENTE)
        self.assertEqual(tarefa.criada_por, self.c.gerente)
        self.assertEqual(list(tarefa.responsaveis.all()), [self.c.func1])

        self.client.login(username="F1", password=SENHA)
        minhas = self.client.get(reverse("tarefas:minhas"))
        self.assertContains(minhas, "Repor cervejas")

    def test_sem_responsavel_atribui_a_equipe_ativa_do_setor(self):
        extra = self.c.func1.__class__.objects.create_user(
            matricula="F9", password=SENHA, nome="Outro", cpf="52998224725",
            data_nascimento=self.c.func1.data_nascimento, filial=self.c.filial,
            setor=self.c.setor_a, cargo=self.c.cargo)
        self.client.post(self.url, self.dados(responsaveis=[]))
        tarefa = Tarefa.objects.get(titulo="Repor cervejas")
        self.assertEqual({f.pk for f in tarefa.responsaveis.all()}, {self.c.func1.pk, extra.pk})

    def test_setor_sem_equipe_exige_responsavel(self):
        vazio = Setor.objects.create(filial=self.c.filial, nome="Padaria")
        resposta = self.client.post(self.url, self.dados(setor=vazio.pk, responsaveis=[]))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("responsaveis", resposta.context["form"].errors)
        self.assertFalse(Tarefa.objects.exists())

    def test_rejeita_prazo_no_passado(self):
        passado = timezone.localtime(timezone.now() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
        resposta = self.client.post(self.url, self.dados(prazo=passado))
        self.assertIn("prazo", resposta.context["form"].errors)
        self.assertFalse(Tarefa.objects.exists())

    def test_rejeita_titulo_vazio_e_setor_de_outra_filial(self):
        self.assertIn("titulo", self.client.post(self.url, self.dados(titulo="")).context["form"].errors)
        resposta = self.client.post(self.url, self.dados(setor=self.c.setor_outra.pk))
        self.assertIn("setor", resposta.context["form"].errors)

    def test_funcionario_nao_cria_tarefa(self):
        self.client.login(username="F1", password=SENHA)
        self.assertEqual(self.client.post(self.url, self.dados()).status_code, 403)
        self.assertFalse(Tarefa.objects.exists())


class ConsultaTests(TestCase):
    """RS05 — filtros por setor, funcionário e status."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()
        cls.t1 = nova_tarefa(cls.c, "T1", cls.c.setor_a, S.PENDENTE, [cls.c.func1])
        cls.t2 = nova_tarefa(cls.c, "T2", cls.c.setor_b, S.EM_ANDAMENTO, [cls.c.func2])
        cls.t3 = nova_tarefa(cls.c, "T3", cls.c.setor_a, S.CONCLUIDA, [cls.c.func1, cls.c.func2])

    def setUp(self):
        self.client.login(username="G1", password=SENHA)

    def pks(self, **filtros):
        resposta = self.client.get(reverse("tarefas:lista"), filtros)
        self.assertEqual(resposta.status_code, 200)
        return {t.pk for t in resposta.context["pagina"]}

    def test_sem_filtro_lista_todas(self):
        self.assertEqual(self.pks(), {self.t1.pk, self.t2.pk, self.t3.pk})

    def test_filtra_por_setor(self):
        self.assertEqual(self.pks(setor=self.c.setor_a.pk), {self.t1.pk, self.t3.pk})

    def test_filtra_por_funcionario(self):
        self.assertEqual(self.pks(funcionario=self.c.func2.pk), {self.t2.pk, self.t3.pk})

    def test_filtra_por_status(self):
        self.assertEqual(self.pks(status="em_andamento"), {self.t2.pk})

    def test_combina_filtros(self):
        self.assertEqual(self.pks(setor=self.c.setor_a.pk, funcionario=self.c.func2.pk, status="concluida"),
                         {self.t3.pk})

    def test_nao_lista_tarefas_de_outra_filial(self):
        alheia = nova_tarefa(self.c, "Alheia", self.c.setor_outra, S.PENDENTE, [self.c.func_outra])
        self.assertNotIn(alheia.pk, self.pks())


class AtualizacaoPeloFuncionarioTests(TestCase):
    """RS13."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def setUp(self):
        self.client.login(username="F1", password=SENHA)
        self.minha = nova_tarefa(self.c, "Minha", responsaveis=[self.c.func1])
        self.alheia = nova_tarefa(self.c, "Alheia", responsaveis=[self.c.func2])

    def mudar(self, tarefa, novo):
        return self.client.post(reverse("tarefas:status", args=[tarefa.pk]), {"novo": novo})

    def status(self, tarefa):
        tarefa.refresh_from_db()
        return tarefa.status

    def test_iniciar_e_concluir_preenche_data_de_conclusao(self):
        self.assertIsNone(self.minha.concluida_em)
        antes = timezone.now()
        self.mudar(self.minha, "em_andamento")
        self.assertEqual(self.status(self.minha), S.EM_ANDAMENTO)
        self.assertIsNone(self.minha.concluida_em)
        self.mudar(self.minha, "concluida")
        self.assertEqual(self.status(self.minha), S.CONCLUIDA)
        self.assertGreaterEqual(self.minha.concluida_em, antes)
        self.assertLessEqual(self.minha.concluida_em, timezone.now())

    def test_pausar_volta_para_pendente(self):
        self.mudar(self.minha, "em_andamento")
        self.mudar(self.minha, "pendente")
        self.assertEqual(self.status(self.minha), S.PENDENTE)

    def test_nao_altera_tarefa_atribuida_a_outro(self):
        resposta = self.mudar(self.alheia, "em_andamento")
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(self.status(self.alheia), S.PENDENTE)

    def test_transicao_invalida_e_recusada_com_mensagem(self):
        resposta = self.mudar(self.minha, "concluida")  # pendente -> concluída não existe no diagrama 7.2
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(self.status(self.minha), S.PENDENTE)
        seguinte = self.client.get(reverse("tarefas:minhas"))
        self.assertContains(seguinte, "Não é possível passar")

    def test_tarefa_concluida_e_terminal(self):
        self.mudar(self.minha, "em_andamento")
        self.mudar(self.minha, "concluida")
        self.mudar(self.minha, "pendente")
        self.assertEqual(self.status(self.minha), S.CONCLUIDA)

    def test_funcionario_nao_cancela(self):
        self.assertEqual(self.mudar(self.minha, "cancelada").status_code, 403)
        self.assertEqual(self.status(self.minha), S.PENDENTE)

    def test_status_desconhecido_e_ignorado(self):
        self.mudar(self.minha, "inventado")
        self.assertEqual(self.status(self.minha), S.PENDENTE)

    def test_exige_post(self):
        self.assertEqual(self.client.get(reverse("tarefas:status", args=[self.minha.pk])).status_code, 405)

    def test_minhas_so_lista_as_proprias_tarefas(self):
        resposta = self.client.get(reverse("tarefas:minhas"))
        self.assertContains(resposta, "Minha")
        self.assertNotContains(resposta, "Alheia")


class CancelamentoPeloGerenteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def setUp(self):
        self.client.login(username="G1", password=SENHA)
        self.tarefa = nova_tarefa(self.c, responsaveis=[self.c.func1])

    def test_gerente_cancela(self):
        self.client.post(reverse("tarefas:status", args=[self.tarefa.pk]), {"novo": "cancelada"})
        self.tarefa.refresh_from_db()
        self.assertEqual(self.tarefa.status, S.CANCELADA)

    def test_gerente_nao_conclui_pelo_funcionario(self):
        resposta = self.client.post(reverse("tarefas:status", args=[self.tarefa.pk]), {"novo": "concluida"})
        self.assertEqual(resposta.status_code, 403)

    def test_nao_cancela_tarefa_de_outra_filial(self):
        alheia = nova_tarefa(self.c, setor=self.c.setor_outra, responsaveis=[self.c.func_outra])
        resposta = self.client.post(reverse("tarefas:status", args=[alheia.pk]), {"novo": "cancelada"})
        self.assertEqual(resposta.status_code, 404)

    def test_cancelada_nao_volta(self):
        url = reverse("tarefas:status", args=[self.tarefa.pk])
        self.client.post(url, {"novo": "cancelada"})
        self.client.post(url, {"novo": "cancelada"})
        self.tarefa.refresh_from_db()
        self.assertEqual(self.tarefa.status, S.CANCELADA)


class PainelTests(TestCase):
    """RS10 — contagem por setor das tarefas do dia."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def test_contagens_por_setor_com_relogio_fixo(self):
        c = self.c
        hoje = timezone.localdate()

        def em(dia, hora):
            return timezone.make_aware(datetime.combine(dia, time(hora, 0)))

        agora = em(hoje, 12)  # relógio fixo para não depender da hora real do teste
        nova_tarefa(c, "p-atrasada", c.setor_a, S.PENDENTE, prazo=em(hoje, 10))
        nova_tarefa(c, "p-futura", c.setor_a, S.PENDENTE, prazo=em(hoje, 15))
        nova_tarefa(c, "andamento", c.setor_a, S.EM_ANDAMENTO, prazo=em(hoje, 13))
        nova_tarefa(c, "concluida", c.setor_a, S.CONCLUIDA, prazo=em(hoje, 11))
        nova_tarefa(c, "cancelada", c.setor_a, S.CANCELADA, prazo=em(hoje, 14))   # não conta
        nova_tarefa(c, "ontem", c.setor_a, S.PENDENTE, prazo=em(hoje - timedelta(days=1), 17))
        nova_tarefa(c, "amanha", c.setor_a, S.PENDENTE, prazo=em(hoje + timedelta(days=1), 9))
        nova_tarefa(c, "outra-filial", c.setor_outra, S.PENDENTE, prazo=em(hoje, 15))

        painel = services.painel_por_setor(c.filial, agora=agora)
        linhas = {l["setor"].nome: l for l in painel["linhas"]}
        a = linhas["Bebidas"]
        self.assertEqual((a["pendente"], a["em_andamento"], a["concluida"]), (2, 1, 1))
        self.assertEqual(a["atrasadas"], 2)   # a das 10h de hoje + a de ontem
        b = linhas["Limpeza"]
        self.assertEqual((b["pendente"], b["em_andamento"], b["concluida"], b["atrasadas"]), (0, 0, 0, 0))
        self.assertEqual(painel["totais"]["pendente"], 2)
        self.assertEqual(len(painel["linhas"]), 2)   # só setores da filial do gerente

    def test_view_do_painel(self):
        self.client.login(username="G1", password=SENHA)
        resposta = self.client.get(reverse("tarefas:painel"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Bebidas")

    def test_funcionario_nao_ve_o_painel(self):
        self.client.login(username="F1", password=SENHA)
        self.assertEqual(self.client.get(reverse("tarefas:painel")).status_code, 403)

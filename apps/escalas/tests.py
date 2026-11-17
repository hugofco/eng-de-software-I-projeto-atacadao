"""Testes de RS06/RS07 (escala), RS11 (ocorrências), RS12 (escala do funcionário) e RS17 (remanejamento)."""
from datetime import date, datetime
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Funcionario
from apps.comunicacao.models import Comunicado
from apps.core.testing import SENHA, criar_cenario

from . import services
from .models import Escala, Ocorrencia, Remanejamento, TipoOcorrencia


class ValidarEscalaTests(SimpleTestCase):
    """Regras puras (sem banco) de services.validar_escala."""

    def setUp(self):
        self.func = Funcionario(nome="Teste", carga_horaria_semanal=36)

    def test_seis_dias_de_um_turno_cabem_em_36h(self):
        turnos = {d: "manha" for d in range(6)}
        self.assertEqual(services.validar_escala(self.func, turnos), [])

    def test_ultrapassar_o_limite_contratual(self):
        turnos = {d: "manha" for d in range(7)}   # 42 h > 36 h
        erros = services.validar_escala(self.func, turnos)
        self.assertEqual(len(erros), 1)
        self.assertIn("excede o limite contratual de 36 h", erros[0])

    def test_limite_exato_e_aceito(self):
        self.func.carga_horaria_semanal = 24
        self.assertEqual(services.validar_escala(self.func, {0: "tarde", 1: "tarde", 2: "tarde", 3: "tarde"}), [])

    def test_noite_seguida_de_manha_viola_descanso_minimo(self):
        erros = services.validar_escala(self.func, {0: "noite", 1: "manha"})
        self.assertEqual(len(erros), 1)
        self.assertIn("descanso", erros[0])

    def test_virada_de_domingo_para_segunda(self):
        erros = services.validar_escala(self.func, {6: "noite", 0: "manha"})
        self.assertEqual(len(erros), 1)

    def test_tarde_seguida_de_manha_e_aceita(self):
        self.assertEqual(services.validar_escala(self.func, {0: "tarde", 1: "manha"}), [])

    def test_dias_de_folga_nao_contam(self):
        self.assertEqual(services.validar_escala(self.func, {0: "noite", 1: "", 2: "manha"}), [])


class EdicaoDeEscalaTests(TestCase):
    """RS06/RS07 pela interface."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def setUp(self):
        self.client.login(username="G1", password=SENHA)
        self.url = reverse("escalas:editar", args=[self.c.func1.pk])

    def dados(self, turnos):
        return {f"dia_{d}": turnos.get(d, "") for d in range(7)}

    def test_define_a_escala(self):
        resposta = self.client.post(self.url, self.dados({d: "manha" for d in range(6)}))
        self.assertRedirects(resposta, reverse("escalas:visao_geral"))
        escalas = Escala.objects.filter(funcionario=self.c.func1)
        self.assertEqual(escalas.count(), 6)
        self.assertTrue(all(e.atualizada_por == self.c.gerente and e.atualizada_em for e in escalas))

    def test_recusa_escala_acima_da_carga_contratual(self):
        resposta = self.client.post(self.url, self.dados({d: "manha" for d in range(7)}))
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context["form"].non_field_errors())
        self.assertFalse(Escala.objects.exists())

    def test_recusa_noite_seguida_de_manha(self):
        resposta = self.client.post(self.url, self.dados({0: "noite", 1: "manha"}))
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Escala.objects.exists())

    def test_edicao_altera_remove_e_registra_data_so_do_que_mudou(self):
        Escala.objects.create(funcionario=self.c.func1, dia_semana=0, turno="manha")
        Escala.objects.create(funcionario=self.c.func1, dia_semana=1, turno="manha")
        antes = Escala.objects.get(funcionario=self.c.func1, dia_semana=0).atualizada_em

        # dia 0 igual, dia 1 removido (folga), dia 2 novo (tarde)
        self.client.post(self.url, self.dados({0: "manha", 2: "tarde"}))

        self.assertEqual({e.dia_semana: e.turno for e in Escala.objects.filter(funcionario=self.c.func1)},
                         {0: "manha", 2: "tarde"})
        self.assertEqual(Escala.objects.get(funcionario=self.c.func1, dia_semana=0).atualizada_em, antes)

    def test_turno_invalido_e_recusado(self):
        resposta = self.client.post(self.url, self.dados({0: "madrugada"}))
        self.assertIn("dia_0", resposta.context["form"].errors)

    def test_funcionario_de_outra_filial_da_404(self):
        resposta = self.client.get(reverse("escalas:editar", args=[self.c.func_outra.pk]))
        self.assertEqual(resposta.status_code, 404)

    def test_visao_geral_mostra_horas(self):
        Escala.objects.create(funcionario=self.c.func1, dia_semana=0, turno="manha")
        resposta = self.client.get(reverse("escalas:visao_geral"))
        linhas = {l["funcionario"].matricula: l for l in resposta.context["linhas"]}
        self.assertEqual(linhas["F1"]["horas"], 6)
        self.assertEqual(linhas["F1"]["dias"][0], "Manhã")
        self.assertEqual(linhas["F1"]["dias"][1], "—")
        self.assertNotIn("X1", linhas)   # outra filial


class MinhaEscalaTests(TestCase):
    """RS12 — o funcionário vê somente a própria escala."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()
        Escala.objects.create(funcionario=cls.c.func1, dia_semana=0, turno="manha")
        Escala.objects.create(funcionario=cls.c.func2, dia_semana=1, turno="noite")

    def test_mostra_apenas_a_propria_escala(self):
        self.client.login(username="F1", password=SENHA)
        resposta = self.client.get(reverse("escalas:minha"))
        dias = resposta.context["dias"]
        self.assertEqual(dias[0]["turno"], "Manhã")
        self.assertEqual(dias[1]["turno"], "—")     # o turno da noite é do F2
        self.assertEqual(resposta.context["horas"], 6)

    def test_nao_ha_como_pedir_a_escala_de_outro(self):
        self.client.login(username="F1", password=SENHA)
        resposta = self.client.get(reverse("escalas:minha"), {"id": self.c.func2.pk, "funcionario": self.c.func2.pk})
        self.assertEqual(resposta.context["dias"][1]["turno"], "—")

    def test_gerente_nao_usa_a_tela_do_funcionario(self):
        self.client.login(username="G1", password=SENHA)
        self.assertEqual(self.client.get(reverse("escalas:minha")).status_code, 403)


class OcorrenciaTests(TestCase):
    """RS11."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def setUp(self):
        self.client.login(username="G1", password=SENHA)
        self.url = reverse("escalas:ocorrencias")

    def test_registra_ocorrencia(self):
        resposta = self.client.post(self.url, {
            "funcionario": self.c.func1.pk, "tipo": "atraso", "data": "2026-11-10",
            "observacao": "Chegou 15 min depois"})
        self.assertRedirects(resposta, self.url)
        o = Ocorrencia.objects.get()
        self.assertEqual((o.funcionario, o.tipo, o.data), (self.c.func1, "atraso", date(2026, 11, 10)))
        self.assertEqual(o.registrada_por, self.c.gerente)

    def test_exige_observacao_e_tipo_valido(self):
        base = {"funcionario": self.c.func1.pk, "tipo": "atraso", "data": "2026-11-10", "observacao": "x"}
        self.assertIn("observacao", self.client.post(self.url, {**base, "observacao": ""}).context["form"].errors)
        self.assertIn("tipo", self.client.post(self.url, {**base, "tipo": "falta-grave"}).context["form"].errors)
        self.assertFalse(Ocorrencia.objects.exists())

    def test_funcionario_de_outra_filial_e_recusado(self):
        resposta = self.client.post(self.url, {
            "funcionario": self.c.func_outra.pk, "tipo": "ausencia", "data": "2026-11-10", "observacao": "x"})
        self.assertIn("funcionario", resposta.context["form"].errors)

    def test_funcionario_nao_registra(self):
        self.client.login(username="F1", password=SENHA)
        self.assertEqual(self.client.post(self.url, {}).status_code, 403)


class RemanejamentoTests(TestCase):
    """RS17 — só funcionários ativos e disponíveis no turno; notificação automática."""

    # Segunda-feira, 10:00 locais → turno da manhã, dia_semana = 0.
    AGORA = timezone.make_aware(datetime(2026, 11, 9, 10, 0))

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()
        Escala.objects.create(funcionario=cls.c.func1, dia_semana=0, turno="manha")
        Escala.objects.create(funcionario=cls.c.func2, dia_semana=0, turno="tarde")

    def disponiveis(self, agora=None):
        return list(services.funcionarios_disponiveis(self.c.filial, agora or self.AGORA))

    def test_disponivel_e_quem_esta_escalado_no_turno_atual(self):
        self.assertEqual(self.disponiveis(), [self.c.func1])

    def test_ausente_hoje_nao_esta_disponivel(self):
        Ocorrencia.objects.create(funcionario=self.c.func1, tipo=TipoOcorrencia.AUSENCIA,
                                  data=date(2026, 11, 9), observacao="atestado")
        self.assertEqual(self.disponiveis(), [])

    def test_atraso_nao_impede(self):
        Ocorrencia.objects.create(funcionario=self.c.func1, tipo=TipoOcorrencia.ATRASO,
                                  data=date(2026, 11, 9), observacao="trânsito")
        self.assertEqual(self.disponiveis(), [self.c.func1])

    def test_inativo_nao_esta_disponivel(self):
        self.c.func1.is_active = False
        self.c.func1.save()
        self.assertEqual(self.disponiveis(), [])

    def test_folga_no_dia_e_fora_de_turno(self):
        terca = timezone.make_aware(datetime(2026, 11, 10, 10, 0))
        self.assertEqual(self.disponiveis(terca), [])
        madrugada = timezone.make_aware(datetime(2026, 11, 9, 3, 0))
        self.assertEqual(self.disponiveis(madrugada), [])

    def test_turno_da_tarde_lista_o_funcionario_da_tarde(self):
        self.assertEqual(self.disponiveis(timezone.make_aware(datetime(2026, 11, 9, 14, 0))), [self.c.func2])

    def test_remanejar_cria_registro_e_notifica_com_o_horario_atual(self):
        self.client.login(username="G1", password=SENHA)
        with patch("apps.escalas.services.agora_local", return_value=self.AGORA):
            antes = timezone.now()
            resposta = self.client.post(reverse("escalas:remanejar"), {
                "funcionario": self.c.func1.pk, "setor_destino": self.c.setor_b.pk, "funcao": "Caixa"})
        self.assertRedirects(resposta, reverse("escalas:remanejar"), fetch_redirect_response=False)

        r = Remanejamento.objects.get()
        self.assertEqual((r.funcionario, r.setor_origem, r.setor_destino, r.funcao),
                         (self.c.func1, self.c.setor_a, self.c.setor_b, "Caixa"))
        self.assertGreaterEqual(r.iniciado_em, antes)     # horário = relógio do servidor
        self.assertEqual(r.criado_por, self.c.gerente)

        aviso = Comunicado.objects.para(self.c.func1).get(automatico=True)
        self.assertIn("Caixa", aviso.texto)
        self.assertIn("Limpeza", aviso.texto)
        self.assertIn("início às", aviso.texto)
        self.assertEqual(Comunicado.objects.para(self.c.func2).filter(automatico=True).count(), 0)

    def test_recusa_funcionario_indisponivel(self):
        self.client.login(username="G1", password=SENHA)
        with patch("apps.escalas.services.agora_local", return_value=self.AGORA):
            resposta = self.client.post(reverse("escalas:remanejar"), {
                "funcionario": self.c.func2.pk, "setor_destino": self.c.setor_b.pk, "funcao": "Caixa"})
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("funcionario", resposta.context["form"].errors)
        self.assertFalse(Remanejamento.objects.exists())
        self.assertFalse(Comunicado.objects.exists())

    def test_nao_altera_o_setor_de_cadastro(self):
        self.client.login(username="G1", password=SENHA)
        with patch("apps.escalas.services.agora_local", return_value=self.AGORA):
            self.client.post(reverse("escalas:remanejar"), {
                "funcionario": self.c.func1.pk, "setor_destino": self.c.setor_b.pk, "funcao": "Caixa"})
        self.c.func1.refresh_from_db()
        self.assertEqual(self.c.func1.setor, self.c.setor_a)

    def test_funcionario_nao_remaneja(self):
        self.client.login(username="F1", password=SENHA)
        self.assertEqual(self.client.get(reverse("escalas:remanejar")).status_code, 403)

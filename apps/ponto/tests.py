"""Testes de RS14 (registro de ponto) e RS09 (consulta do log pelo gerente)."""
from datetime import datetime, timedelta
from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Terminal
from apps.core.testing import SENHA, criar_cenario
from apps.core.utils import ip_do_cliente

from . import services
from .models import RegistroImutavel, RegistroPonto, TipoRegistro


def aware(ano, mes, dia, hora, minuto=0):
    return timezone.make_aware(datetime(ano, mes, dia, hora, minuto))


class RegistroTests(TestCase):
    """RS14 — o horário é sempre o do servidor."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def setUp(self):
        self.client.login(username="F1", password=SENHA)
        self.url = reverse("ponto:meu_ponto")

    def registrar(self, tipo, **extra):
        return self.client.post(self.url, {"tipo": tipo}, **extra)

    def total(self):
        return RegistroPonto.objects.filter(funcionario=self.c.func1).count()

    def test_registra_entrada_com_horario_do_servidor(self):
        antes = timezone.now()
        resposta = self.registrar("entrada")
        self.assertRedirects(resposta, self.url)
        registro = RegistroPonto.objects.get()
        self.assertEqual((registro.funcionario, registro.tipo), (self.c.func1, TipoRegistro.ENTRADA))
        self.assertGreaterEqual(registro.registrado_em, antes)
        self.assertLessEqual(registro.registrado_em, timezone.now())

    def test_horario_enviado_pelo_cliente_e_ignorado(self):
        antes = timezone.now()
        self.client.post(self.url, {"tipo": "entrada", "registrado_em": "2000-01-01T00:00",
                                    "data_hora": "2000-01-01 00:00:00"})
        self.assertGreaterEqual(RegistroPonto.objects.get().registrado_em, antes)

    def test_entrada_e_saida_se_alternam(self):
        self.registrar("entrada")
        self.registrar("entrada")          # repetida: recusada
        self.assertEqual(self.total(), 1)
        self.registrar("saida")
        self.assertEqual(self.total(), 2)
        self.registrar("saida")            # repetida: recusada
        self.assertEqual(self.total(), 2)
        self.registrar("entrada")
        self.assertEqual(self.total(), 3)

    def test_primeiro_registro_nao_pode_ser_saida(self):
        self.registrar("saida")
        self.assertEqual(self.total(), 0)

    def test_tipo_invalido(self):
        self.registrar("almoco")
        self.assertEqual(self.total(), 0)

    def test_mensagem_de_recusa_indica_o_tipo_esperado(self):
        self.registrar("entrada")
        resposta = self.client.post(self.url, {"tipo": "entrada"}, follow=True)
        textos = " ".join(m.message for m in resposta.context["messages"])
        self.assertIn("SAÍDA", textos)

    def test_tela_mostra_o_proximo_tipo_esperado(self):
        self.assertEqual(self.client.get(self.url).context["proximo"], TipoRegistro.ENTRADA)
        self.registrar("entrada")
        self.assertEqual(self.client.get(self.url).context["proximo"], TipoRegistro.SAIDA)

    def test_registros_de_cada_funcionario_sao_independentes(self):
        self.registrar("entrada")
        self.client.login(username="F2", password=SENHA)
        self.client.post(self.url, {"tipo": "entrada"})
        self.assertEqual(RegistroPonto.objects.count(), 2)

    def test_gerente_e_comprador_nao_registram_ponto(self):
        for matricula in ("G1", "C1"):
            self.client.login(username=matricula, password=SENHA)
            self.assertEqual(self.client.post(self.url, {"tipo": "entrada"}).status_code, 403)
        self.assertFalse(RegistroPonto.objects.exists())

    def test_guarda_o_ip_de_origem(self):
        self.registrar("entrada", REMOTE_ADDR="10.1.2.3")
        self.assertEqual(RegistroPonto.objects.get().ip_origem, "10.1.2.3")


class TerminalTests(TestCase):
    """Seção 1.3: Terminal = computador da loja com IP fixo."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()
        cls.terminal = Terminal.objects.create(filial=cls.c.filial, nome="Caixa 1", ip_address="10.0.0.5")

    def setUp(self):
        self.client.login(username="F1", password=SENHA)
        self.url = reverse("ponto:meu_ponto")

    @override_settings(WFM_ENFORCE_TERMINAL_IP=True)
    def test_exigindo_terminal_recusa_ip_desconhecido(self):
        self.client.post(self.url, {"tipo": "entrada"}, REMOTE_ADDR="192.168.9.9")
        self.assertFalse(RegistroPonto.objects.exists())

    @override_settings(WFM_ENFORCE_TERMINAL_IP=True)
    def test_exigindo_terminal_aceita_ip_cadastrado(self):
        self.client.post(self.url, {"tipo": "entrada"}, REMOTE_ADDR="10.0.0.5")
        registro = RegistroPonto.objects.get()
        self.assertEqual(registro.terminal, self.terminal)

    @override_settings(WFM_ENFORCE_TERMINAL_IP=True)
    def test_terminal_inativo_ou_de_outra_filial_nao_vale(self):
        self.terminal.ativo = False
        self.terminal.save()
        Terminal.objects.create(filial=self.c.outra_filial, nome="Outra loja", ip_address="10.0.0.6")
        self.client.post(self.url, {"tipo": "entrada"}, REMOTE_ADDR="10.0.0.5")
        self.client.post(self.url, {"tipo": "entrada"}, REMOTE_ADDR="10.0.0.6")
        self.assertFalse(RegistroPonto.objects.exists())

    def test_sem_exigencia_o_terminal_apenas_e_associado_quando_conhecido(self):
        self.client.post(self.url, {"tipo": "entrada"}, REMOTE_ADDR="10.0.0.5")
        self.client.post(self.url, {"tipo": "saida"}, REMOTE_ADDR="172.16.0.1")
        entrada, saida = RegistroPonto.objects.order_by("registrado_em", "pk")
        self.assertEqual(entrada.terminal, self.terminal)
        self.assertIsNone(saida.terminal)


class IpDoClienteTests(SimpleTestCase):
    def requisicao(self, **meta):
        return RequestFactory().get("/", **meta)

    def test_usa_remote_addr_por_padrao_e_ignora_x_forwarded_for(self):
        req = self.requisicao(REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.1.1.1")
        self.assertEqual(ip_do_cliente(req), "10.0.0.1")

    @override_settings(WFM_TRUST_X_FORWARDED_FOR=True)
    def test_com_proxy_confiavel_usa_o_ultimo_item(self):
        req = self.requisicao(REMOTE_ADDR="127.0.0.1", HTTP_X_FORWARDED_FOR="6.6.6.6, 10.0.0.9")
        self.assertEqual(ip_do_cliente(req), "10.0.0.9")   # o primeiro pode ter sido forjado

    def test_ip_invalido_vira_none(self):
        self.assertIsNone(ip_do_cliente(self.requisicao(REMOTE_ADDR="nao-e-ip")))
        self.assertIsNone(ip_do_cliente(self.requisicao(REMOTE_ADDR="")))


class ImutabilidadeTests(TestCase):
    """Seção 1.3: o log de ponto é imutável."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()
        cls.registro = RegistroPonto.objects.create(funcionario=cls.c.func1, tipo=TipoRegistro.ENTRADA)

    def test_nao_permite_alterar_instancia(self):
        r = RegistroPonto.objects.get(pk=self.registro.pk)
        r.tipo = TipoRegistro.SAIDA
        with self.assertRaises(RegistroImutavel):
            r.save()
        self.assertEqual(RegistroPonto.objects.get(pk=r.pk).tipo, TipoRegistro.ENTRADA)

    def test_nao_permite_apagar_instancia(self):
        with self.assertRaises(RegistroImutavel):
            RegistroPonto.objects.get(pk=self.registro.pk).delete()
        self.assertEqual(RegistroPonto.objects.count(), 1)

    def test_nao_permite_update_nem_delete_em_massa(self):
        with self.assertRaises(RegistroImutavel):
            RegistroPonto.objects.all().update(tipo=TipoRegistro.SAIDA)
        with self.assertRaises(RegistroImutavel):
            RegistroPonto.objects.all().delete()
        with self.assertRaises(RegistroImutavel):
            RegistroPonto.objects.bulk_update([self.registro], ["tipo"])
        self.assertEqual(RegistroPonto.objects.get().tipo, TipoRegistro.ENTRADA)

    def test_admin_e_somente_leitura(self):
        from django.contrib import admin
        modelo_admin = admin.site._registry[RegistroPonto]
        pedido = RequestFactory().get("/")
        self.assertFalse(modelo_admin.has_add_permission(pedido))
        self.assertFalse(modelo_admin.has_change_permission(pedido, self.registro))
        self.assertFalse(modelo_admin.has_delete_permission(pedido, self.registro))


class ResumoFrequenciaTests(SimpleTestCase):
    """Cálculo puro de frequência (sem banco)."""

    def registro(self, funcionario, tipo, quando):
        return SimpleNamespace(funcionario=funcionario, funcionario_id=funcionario.pk,
                               tipo=tipo, registrado_em=quando)

    def test_pareia_entrada_e_saida_e_soma_horas(self):
        ana = SimpleNamespace(pk=1, nome="Ana")
        registros = [
            self.registro(ana, "entrada", aware(2026, 11, 2, 8)),
            self.registro(ana, "saida", aware(2026, 11, 2, 14, 30)),
            self.registro(ana, "entrada", aware(2026, 11, 3, 8)),
            self.registro(ana, "saida", aware(2026, 11, 3, 12)),
        ]
        [linha] = services.resumo_frequencia(registros)
        self.assertEqual(linha["horas"], "10h30min")
        self.assertEqual(linha["dias_trabalhados"], 2)
        self.assertFalse(linha["em_aberto"])

    def test_entrada_sem_saida_fica_em_aberto_e_nao_soma(self):
        bia = SimpleNamespace(pk=2, nome="Bia")
        [linha] = services.resumo_frequencia([self.registro(bia, "entrada", aware(2026, 11, 2, 8))])
        self.assertTrue(linha["em_aberto"])
        self.assertEqual(linha["horas"], "0h00min")

    def test_saida_sem_entrada_no_periodo_e_ignorada(self):
        bia = SimpleNamespace(pk=2, nome="Bia")
        [linha] = services.resumo_frequencia([self.registro(bia, "saida", aware(2026, 11, 2, 8))])
        self.assertEqual((linha["horas"], linha["dias_trabalhados"]), ("0h00min", 0))

    def test_turno_que_atravessa_a_meia_noite(self):
        caio = SimpleNamespace(pk=3, nome="Caio")
        registros = [self.registro(caio, "entrada", aware(2026, 11, 2, 18)),
                     self.registro(caio, "saida", aware(2026, 11, 3, 0, 5))]
        [linha] = services.resumo_frequencia(registros)
        self.assertEqual(linha["horas"], "6h05min")

    def test_ordena_por_nome(self):
        z, a = SimpleNamespace(pk=1, nome="Zé"), SimpleNamespace(pk=2, nome="Ana")
        linhas = services.resumo_frequencia([self.registro(z, "entrada", aware(2026, 11, 2, 8)),
                                             self.registro(a, "entrada", aware(2026, 11, 2, 9))])
        self.assertEqual([l["funcionario"].nome for l in linhas], ["Ana", "Zé"])


class ConsultaLogTests(TestCase):
    """RS09 — só o gerente consulta; período válido."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()
        mk = RegistroPonto.objects.create
        mk(funcionario=cls.c.func1, tipo="entrada", registrado_em=aware(2026, 11, 2, 8))
        mk(funcionario=cls.c.func1, tipo="saida", registrado_em=aware(2026, 11, 2, 14))
        mk(funcionario=cls.c.func2, tipo="entrada", registrado_em=aware(2026, 11, 3, 8))
        mk(funcionario=cls.c.func_outra, tipo="entrada", registrado_em=aware(2026, 11, 2, 8))

    def consultar(self, **params):
        return self.client.get(reverse("ponto:log"), params)

    def test_somente_gerente_consulta(self):
        for matricula in ("F1", "C1"):
            self.client.login(username=matricula, password=SENHA)
            with self.subTest(usuario=matricula):
                self.assertEqual(self.consultar().status_code, 403)
        self.client.logout()
        self.assertEqual(self.consultar().status_code, 302)   # anônimo → login

    def test_gerente_ve_registros_e_frequencia_do_periodo(self):
        self.client.login(username="G1", password=SENHA)
        resposta = self.consultar(data_inicial="2026-11-01", data_final="2026-11-05")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.context["pagina"].object_list), 3)    # exclui a outra filial
        freq = {l["funcionario"].matricula: l for l in resposta.context["frequencia"]}
        self.assertEqual(freq["F1"]["horas"], "6h00min")
        self.assertEqual(freq["F1"]["dias_trabalhados"], 1)
        self.assertTrue(freq["F2"]["em_aberto"])
        self.assertNotIn("X1", freq)

    def test_periodo_sem_registros(self):
        self.client.login(username="G1", password=SENHA)
        resposta = self.consultar(data_inicial="2026-11-04", data_final="2026-11-05")
        self.assertEqual(resposta.context["frequencia"], [])
        self.assertContains(resposta, "Nenhum registro no período")

    def test_data_final_inclui_o_dia_inteiro(self):
        self.client.login(username="G1", password=SENHA)
        resposta = self.consultar(data_inicial="2026-11-03", data_final="2026-11-03")
        self.assertEqual(len(resposta.context["pagina"].object_list), 1)

    def test_filtra_por_funcionario(self):
        self.client.login(username="G1", password=SENHA)
        resposta = self.consultar(data_inicial="2026-11-01", data_final="2026-11-05",
                                  funcionario=self.c.func2.pk)
        self.assertEqual([r.funcionario for r in resposta.context["pagina"]], [self.c.func2])

    def test_data_inicial_posterior_a_final_e_recusada(self):
        self.client.login(username="G1", password=SENHA)
        resposta = self.consultar(data_inicial="2026-11-10", data_final="2026-11-01")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("posterior", " ".join(resposta.context["form"].non_field_errors()))
        self.assertNotIn("frequencia", resposta.context)

    def test_sem_parametros_usa_os_ultimos_sete_dias(self):
        self.client.login(username="G1", password=SENHA)
        resposta = self.consultar()
        self.assertEqual(resposta.status_code, 200)
        hoje = timezone.localdate()
        self.assertEqual(resposta.context["form"].cleaned_data["data_final"], hoje)
        self.assertEqual(resposta.context["form"].cleaned_data["data_inicial"], hoje - timedelta(days=7))

    def test_apenas_pagina_na_url_mantem_o_periodo_padrao(self):
        self.client.login(username="G1", password=SENHA)
        self.assertEqual(self.consultar(page=1).status_code, 200)

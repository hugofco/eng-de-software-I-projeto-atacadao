"""Testes de RS08 (comunicados), RS15 (leitura pelo funcionário) e RS16 (mensagem ao gerente)."""
from django.test import TestCase
from django.urls import reverse

from apps.core.testing import SENHA, criar_cenario

from .models import Comunicado, DestinoComunicado, LeituraComunicado, Mensagem


class EnvioDeComunicadoTests(TestCase):
    """RS08."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def setUp(self):
        self.client.login(username="G1", password=SENHA)
        self.url = reverse("comunicacao:enviar")

    def test_envia_para_todos(self):
        resposta = self.client.post(self.url, {"destino": "todos", "texto": "Reunião às 8h"})
        self.assertRedirects(resposta, self.url)
        c = Comunicado.objects.get()
        self.assertEqual((c.destino_tipo, c.filial, c.autor, c.setor, c.destinatario),
                         ("todos", self.c.filial, self.c.gerente, None, None))

    def test_envia_para_um_setor(self):
        self.client.post(self.url, {"destino": "setor", "setor": self.c.setor_b.pk, "texto": "Limpeza: novo produto"})
        c = Comunicado.objects.get()
        self.assertEqual((c.destino_tipo, c.setor), ("setor", self.c.setor_b))

    def test_envia_para_um_funcionario(self):
        self.client.post(self.url, {"destino": "funcionario", "funcionario": self.c.func1.pk, "texto": "Venha ao escritório"})
        c = Comunicado.objects.get()
        self.assertEqual((c.destino_tipo, c.destinatario), ("funcionario", self.c.func1))

    def test_ignora_destinos_que_nao_correspondem_ao_tipo(self):
        # Tipo "todos" não deve guardar setor/funcionário enviados por engano.
        self.client.post(self.url, {"destino": "todos", "setor": self.c.setor_a.pk,
                                    "funcionario": self.c.func1.pk, "texto": "Aviso geral"})
        c = Comunicado.objects.get()
        self.assertIsNone(c.setor)
        self.assertIsNone(c.destinatario)

    def test_setor_ou_funcionario_obrigatorios_conforme_o_destino(self):
        r1 = self.client.post(self.url, {"destino": "setor", "texto": "x"})
        self.assertIn("setor", r1.context["form"].errors)
        r2 = self.client.post(self.url, {"destino": "funcionario", "texto": "x"})
        self.assertIn("funcionario", r2.context["form"].errors)
        self.assertFalse(Comunicado.objects.exists())

    def test_limite_de_500_caracteres(self):
        ok = self.client.post(self.url, {"destino": "todos", "texto": "a" * 500})
        self.assertEqual(ok.status_code, 302)
        longo = self.client.post(self.url, {"destino": "todos", "texto": "a" * 501})
        self.assertIn("texto", longo.context["form"].errors)
        self.assertEqual(Comunicado.objects.count(), 1)

    def test_texto_vazio_e_recusado(self):
        resposta = self.client.post(self.url, {"destino": "todos", "texto": "   "})
        self.assertIn("texto", resposta.context["form"].errors)

    def test_nao_envia_para_setor_ou_funcionario_de_outra_filial(self):
        r1 = self.client.post(self.url, {"destino": "setor", "setor": self.c.setor_outra.pk, "texto": "x"})
        self.assertIn("setor", r1.context["form"].errors)
        r2 = self.client.post(self.url, {"destino": "funcionario", "funcionario": self.c.func_outra.pk, "texto": "x"})
        self.assertIn("funcionario", r2.context["form"].errors)

    def test_funcionario_nao_envia(self):
        self.client.login(username="F1", password=SENHA)
        self.assertEqual(self.client.post(self.url, {"destino": "todos", "texto": "x"}).status_code, 403)


class LeituraDeComunicadosTests(TestCase):
    """RS15 — o funcionário vê o que é para ele, para o seu setor ou para todos."""

    @classmethod
    def setUpTestData(cls):
        c = cls.c = criar_cenario()
        mk = Comunicado.objects.create
        cls.todos = mk(filial=c.filial, autor=c.gerente, destino_tipo=DestinoComunicado.TODOS, texto="TODOS")
        cls.setor_a = mk(filial=c.filial, autor=c.gerente, destino_tipo=DestinoComunicado.SETOR,
                         setor=c.setor_a, texto="SETOR-A")
        cls.setor_b = mk(filial=c.filial, autor=c.gerente, destino_tipo=DestinoComunicado.SETOR,
                         setor=c.setor_b, texto="SETOR-B")
        cls.so_f1 = mk(filial=c.filial, autor=c.gerente, destino_tipo=DestinoComunicado.FUNCIONARIO,
                       destinatario=c.func1, texto="SO-F1")
        cls.so_f2 = mk(filial=c.filial, autor=c.gerente, destino_tipo=DestinoComunicado.FUNCIONARIO,
                       destinatario=c.func2, texto="SO-F2")
        cls.outra_loja = mk(filial=c.outra_filial, destino_tipo=DestinoComunicado.TODOS, texto="OUTRA-LOJA")

    def textos_de(self, funcionario):
        return {c.texto for c in Comunicado.objects.para(funcionario)}

    def test_visibilidade_por_destino(self):
        self.assertEqual(self.textos_de(self.c.func1), {"TODOS", "SETOR-A", "SO-F1"})
        self.assertEqual(self.textos_de(self.c.func2), {"TODOS", "SETOR-B", "SO-F2"})
        self.assertEqual(self.textos_de(self.c.func_outra), {"OUTRA-LOJA"})

    def test_tela_lista_apenas_os_proprios(self):
        self.client.login(username="F1", password=SENHA)
        resposta = self.client.get(reverse("comunicacao:meus"))
        self.assertContains(resposta, "SETOR-A")
        self.assertContains(resposta, "SO-F1")
        self.assertNotContains(resposta, "SETOR-B")
        self.assertNotContains(resposta, "SO-F2")
        self.assertNotContains(resposta, "OUTRA-LOJA")

    def test_novos_viram_lidos_ao_abrir_a_lista(self):
        self.client.login(username="F1", password=SENHA)
        self.assertEqual(self.client.get(reverse("core:home")).context["badge_nao_lidos"], 3)

        primeira = self.client.get(reverse("comunicacao:meus"))
        self.assertTrue(all(c.novo for c in primeira.context["comunicados"]))
        self.assertEqual(LeituraComunicado.objects.filter(funcionario=self.c.func1).count(), 3)

        segunda = self.client.get(reverse("comunicacao:meus"))
        self.assertFalse(any(c.novo for c in segunda.context["comunicados"]))
        self.assertEqual(self.client.get(reverse("core:home")).context["badge_nao_lidos"], 0)

    def test_leitura_de_um_funcionario_nao_afeta_o_outro(self):
        self.client.login(username="F1", password=SENHA)
        self.client.get(reverse("comunicacao:meus"))
        self.client.login(username="F2", password=SENHA)
        self.assertEqual(self.client.get(reverse("core:home")).context["badge_nao_lidos"], 3)

    def test_reabrir_a_lista_nao_duplica_leituras(self):
        self.client.login(username="F1", password=SENHA)
        for _ in range(3):
            self.client.get(reverse("comunicacao:meus"))
        self.assertEqual(LeituraComunicado.objects.count(), 3)


class MensagemAoGerenteTests(TestCase):
    """RS16."""

    @classmethod
    def setUpTestData(cls):
        cls.c = criar_cenario()

    def test_funcionario_envia_e_gerente_recebe(self):
        self.client.login(username="F1", password=SENHA)
        resposta = self.client.post(reverse("comunicacao:nova_mensagem"),
                                    {"tipo": "troca_turno", "texto": "Posso trocar o sábado?"})
        self.assertRedirects(resposta, reverse("comunicacao:nova_mensagem"))
        m = Mensagem.objects.get()
        self.assertEqual((m.remetente, m.tipo, m.lida), (self.c.func1, "troca_turno", False))

        self.client.login(username="G1", password=SENHA)
        self.assertEqual(self.client.get(reverse("core:home")).context["badge_nao_lidos"], 1)
        caixa = self.client.get(reverse("comunicacao:caixa"))
        self.assertContains(caixa, "Posso trocar o sábado?")
        self.assertContains(caixa, reverse("escalas:ocorrencias"))   # atalho para registrar a troca (RU07)

        self.client.post(reverse("comunicacao:lida", args=[m.pk]))
        m.refresh_from_db()
        self.assertTrue(m.lida)
        self.assertEqual(self.client.get(reverse("core:home")).context["badge_nao_lidos"], 0)

    def test_limite_de_500_caracteres_e_vazio(self):
        self.client.login(username="F1", password=SENHA)
        url = reverse("comunicacao:nova_mensagem")
        self.assertIn("texto", self.client.post(url, {"tipo": "duvida", "texto": "a" * 501}).context["form"].errors)
        self.assertIn("texto", self.client.post(url, {"tipo": "duvida", "texto": ""}).context["form"].errors)
        self.assertFalse(Mensagem.objects.exists())

    def test_assunto_invalido(self):
        self.client.login(username="F1", password=SENHA)
        resposta = self.client.post(reverse("comunicacao:nova_mensagem"), {"tipo": "spam", "texto": "oi"})
        self.assertIn("tipo", resposta.context["form"].errors)

    def test_gerente_nao_le_mensagens_de_outra_filial(self):
        Mensagem.objects.create(remetente=self.c.func_outra, texto="MENSAGEM-ALHEIA")
        self.client.login(username="G1", password=SENHA)
        self.assertNotContains(self.client.get(reverse("comunicacao:caixa")), "MENSAGEM-ALHEIA")

    def test_gerente_nao_marca_lida_mensagem_de_outra_filial(self):
        alheia = Mensagem.objects.create(remetente=self.c.func_outra, texto="x")
        self.client.login(username="G1", password=SENHA)
        self.assertEqual(self.client.post(reverse("comunicacao:lida", args=[alheia.pk])).status_code, 404)

    def test_permissoes(self):
        self.client.login(username="F1", password=SENHA)
        self.assertEqual(self.client.get(reverse("comunicacao:caixa")).status_code, 403)
        self.client.login(username="G1", password=SENHA)
        self.assertEqual(self.client.get(reverse("comunicacao:nova_mensagem")).status_code, 403)
        self.client.login(username="C1", password=SENHA)
        self.assertEqual(self.client.get(reverse("comunicacao:nova_mensagem")).status_code, 403)

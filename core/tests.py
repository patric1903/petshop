from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Agendamento, Cliente, Funcionario as F, Pet, Receita, Servico, Vacina


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adm = F.objects.create_user("adm@t.com", "senha12345", nome="Adm", perfil=F.ADMINISTRADOR)
        cls.atd = F.objects.create_user("atd@t.com", "senha12345", nome="Atd", perfil=F.ATENDENTE)
        cls.p1 = F.objects.create_user("p1@t.com", "senha12345", nome="Prof 1", perfil=F.PROFISSIONAL)
        cls.p2 = F.objects.create_user("p2@t.com", "senha12345", nome="Prof 2", perfil=F.PROFISSIONAL)
        cls.cli = Cliente.objects.create(nome="Maria", telefone="1")
        cls.pet = Pet.objects.create(cliente=cls.cli, nome="Rex")
        cls.banho = Servico.objects.create(nome="Banho", tipo="BANHO", duracao_minutos=60, preco="50.00")
        cls.base = (timezone.now() + timedelta(days=2)).replace(minute=0, second=0, microsecond=0)

    def ag(self, prof=None, inicio=None, servico=None, **kw):
        a = Agendamento(pet=self.pet, servico=servico or self.banho, profissional=prof or self.p1,
                        inicio=inicio or self.base, **kw)
        a.full_clean()
        a.save()
        return a


class ConflitoHorario(Base):
    def test_calcula_hora_fim_pela_duracao(self):
        self.assertEqual(self.ag().hora_fim, self.base + timedelta(minutes=60))

    def test_sobreposicao_mesmo_profissional_e_bloqueada(self):
        self.ag()
        with self.assertRaises(ValidationError):
            self.ag(inicio=self.base + timedelta(minutes=30))

    def test_horario_colado_e_permitido(self):
        self.ag()
        self.ag(inicio=self.base + timedelta(minutes=60))

    def test_outro_profissional_no_mesmo_horario_e_permitido(self):
        self.ag()
        self.ag(prof=self.p2)

    def test_cancelado_libera_horario(self):
        a = self.ag()
        a.status = Agendamento.CANCELADO
        a.save()
        self.ag()

    def test_reagendar_nao_conflita_consigo_mesmo(self):
        a = self.ag()
        a.inicio += timedelta(minutes=15)
        a.full_clean()

    def test_atendente_nao_pode_ser_profissional_do_agendamento(self):
        with self.assertRaises(ValidationError):
            self.ag(prof=self.atd)


class ValorCongelado(Base):
    def test_reajuste_do_servico_nao_altera_agendamento_antigo(self):
        a = self.ag()
        self.banho.preco = Decimal("80.00")
        self.banho.save()
        a.refresh_from_db()
        self.assertEqual(a.valor_cobrado, Decimal("50.00"))
        self.assertEqual(self.ag(inicio=self.base + timedelta(hours=3)).valor_cobrado, Decimal("80.00"))


class Vacinas(Base):
    def vac(self, dias):
        hoje = timezone.localdate()
        return Vacina(pet=self.pet, nome="V10", data_aplicacao=hoje - timedelta(days=400),
                      data_proxima_dose=hoje + timedelta(days=dias), aplicada_por=self.p1)

    def test_situacoes(self):
        self.assertEqual(self.vac(-1).situacao, "vencida")
        self.assertEqual(self.vac(10).situacao, "a_vencer")
        self.assertEqual(self.vac(90).situacao, "em_dia")

    def test_proxima_dose_deve_ser_posterior(self):
        v = self.vac(0)
        v.data_proxima_dose = v.data_aplicacao
        with self.assertRaises(ValidationError):
            v.full_clean()


class Receitas(Base):
    def test_so_atendimento_concluido_gera_receita(self):
        a = self.ag()
        with self.assertRaises(ValidationError):
            Receita(agendamento=a, valor="50", forma_pagamento="PIX").full_clean()
        a.status = Agendamento.CONCLUIDO
        a.save()
        Receita(agendamento=a, valor="50", forma_pagamento="PIX").full_clean()


class Permissoes(Base):
    def login(self, u):
        self.client.force_login(u)

    def test_exige_login(self):
        self.assertEqual(self.client.get(reverse("clientes")).status_code, 302)

    def test_profissional_nao_acessa_clientes_nem_agendar(self):
        self.login(self.p1)
        for nome in ("clientes", "pets", "agendar", "financeiro", "funcionarios"):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 302, nome)

    def test_atendente_nao_acessa_financeiro_nem_funcionarios(self):
        self.login(self.atd)
        for nome in ("financeiro", "funcionarios", "servicos"):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 302, nome)
        self.assertEqual(self.client.get(reverse("clientes")).status_code, 200)

    def test_profissional_ve_so_a_propria_agenda(self):
        self.ag(prof=self.p1)
        self.ag(prof=self.p2)
        self.login(self.p1)
        dia = timezone.localtime(self.base).date().isoformat()
        r = self.client.get(reverse("agenda"), {"data": dia, "profissional": self.p2.pk})
        self.assertEqual([a.profissional for a in r.context["ags"]], [self.p1])

    def test_atendente_ve_agenda_completa(self):
        self.ag(prof=self.p1)
        self.ag(prof=self.p2)
        self.login(self.atd)
        dia = timezone.localtime(self.base).date().isoformat()
        r = self.client.get(reverse("agenda"), {"data": dia})
        self.assertEqual(len(r.context["ags"]), 2)

    def test_atendente_nao_conclui_atendimento(self):
        a = self.ag(inicio=timezone.now() - timedelta(hours=2))
        self.login(self.atd)
        self.client.post(reverse("concluir", args=[a.pk]))
        a.refresh_from_db()
        self.assertEqual(a.status, Agendamento.AGENDADO)

    def test_profissional_conclui_apenas_o_proprio(self):
        a = self.ag(prof=self.p1, inicio=timezone.now() - timedelta(hours=2))
        self.login(self.p2)
        self.client.post(reverse("concluir", args=[a.pk]))
        a.refresh_from_db()
        self.assertEqual(a.status, Agendamento.AGENDADO)
        self.login(self.p1)
        self.client.post(reverse("concluir", args=[a.pk]))
        a.refresh_from_db()
        self.assertEqual(a.status, Agendamento.CONCLUIDO)

    def test_conclui_atendimento_do_dia_mesmo_que_mais_tarde(self):
        agora = timezone.localtime()
        inicio = agora.replace(hour=23, minute=0, second=0, microsecond=0)
        if inicio.date() != timezone.localdate() or inicio < agora - timedelta(hours=1):
            inicio = agora
        a = self.ag(inicio=inicio)
        self.client.force_login(self.p1)
        self.client.post(reverse("concluir", args=[a.pk]))
        a.refresh_from_db()
        self.assertEqual(a.status, Agendamento.CONCLUIDO)

    def test_nao_conclui_atendimento_futuro(self):
        a = self.ag()
        self.login(self.p1)
        self.client.post(reverse("concluir", args=[a.pk]))
        a.refresh_from_db()
        self.assertEqual(a.status, Agendamento.AGENDADO)


class CancelamentoEExclusao(Base):
    def test_cancela_antes_do_inicio(self):
        a = self.ag()
        self.client.force_login(self.atd)
        self.client.post(reverse("cancelar", args=[a.pk]))
        a.refresh_from_db()
        self.assertEqual(a.status, Agendamento.CANCELADO)

    def test_nao_cancela_atendimento_ja_iniciado(self):
        a = self.ag(inicio=timezone.now() - timedelta(minutes=10))
        self.client.force_login(self.atd)
        self.client.post(reverse("cancelar", args=[a.pk]))
        a.refresh_from_db()
        self.assertEqual(a.status, Agendamento.AGENDADO)

    def test_cliente_com_pet_nao_e_excluido(self):
        self.client.force_login(self.atd)
        self.client.post(reverse("cliente_excluir", args=[self.cli.pk]))
        self.assertTrue(Cliente.objects.filter(pk=self.cli.pk).exists())

    def test_agendar_pela_tela_bloqueia_conflito(self):
        self.ag()
        self.client.force_login(self.atd)
        r = self.client.post(reverse("agendar"), {
            "pet": self.pet.pk, "servico": self.banho.pk, "profissional": self.p1.pk,
            "inicio": timezone.localtime(self.base + timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M")})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Conflito de horário")
        self.assertEqual(Agendamento.objects.count(), 1)


class Login(Base):
    def test_login_por_email(self):
        self.assertTrue(self.client.login(username="atd@t.com", password="senha12345"))

    def test_funcionario_desativado_nao_entra(self):
        self.atd.is_active = False
        self.atd.save()
        self.assertFalse(self.client.login(username="atd@t.com", password="senha12345"))

    def test_senha_e_armazenada_como_hash(self):
        self.assertTrue(self.atd.password.startswith("pbkdf2_sha256$"))

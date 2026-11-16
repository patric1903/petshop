from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Agendamento, Cliente, Funcionario, Pet, Receita, Servico, Vacina


class Command(BaseCommand):
    help = "Cria dados iniciais de demonstração (3 perfis, serviços, exemplos)."

    def handle(self, *args, **opts):
        F = Funcionario
        def user(email, nome, perfil, senha, esp=""):
            u, novo = F.objects.get_or_create(email=email, defaults=dict(
                nome=nome, perfil=perfil, especialidade=esp))
            if novo:
                u.set_password(senha); u.save()
            return u
        user("admin@petcare.com", "Ana Administradora", F.ADMINISTRADOR, "Admin@12345")
        user("atendente@petcare.com", "Carla Atendente", F.ATENDENTE, "Atend@12345")
        bia = user("bia@petcare.com", "Bia Banhista", F.PROFISSIONAL, "Prof@12345", "banhista e tosadora")
        user("vet@petcare.com", "Dr. Caio Veterinário", F.PROFISSIONAL, "Prof@12345", "veterinário")

        servicos = {}
        for nome, tipo, dur, preco in [
            ("Banho simples", "BANHO", 45, "50.00"), ("Banho e tosa", "TOSA", 90, "90.00"),
            ("Consulta veterinária", "CONSULTA", 30, "120.00")]:
            servicos[nome], _ = Servico.objects.get_or_create(
                nome=nome, defaults=dict(tipo=tipo, duracao_minutos=dur, preco=preco))

        if Cliente.objects.exists():
            self.stdout.write("Dados de exemplo já existem."); return
        c1 = Cliente.objects.create(nome="Maria Souza", telefone="(51) 99999-1111",
                                    email="maria@email.com", endereco="Rua das Flores, 100")
        c2 = Cliente.objects.create(nome="João Pereira", telefone="(51) 98888-2222")
        rex = Pet.objects.create(cliente=c1, nome="Rex", especie="CAO", raca="Labrador")
        mel = Pet.objects.create(cliente=c2, nome="Mel", especie="GATO", raca="Siamês")
        hoje = timezone.localdate()
        Vacina.objects.create(pet=rex, nome="V10", data_aplicacao=hoje - timedelta(days=380),
                              data_proxima_dose=hoje - timedelta(days=15), aplicada_por=bia)
        Vacina.objects.create(pet=mel, nome="Antirrábica", data_aplicacao=hoje - timedelta(days=340),
                              data_proxima_dose=hoje + timedelta(days=20), aplicada_por=bia)
        amanha = timezone.make_aware(timezone.datetime.combine(hoje + timedelta(days=1),
                                     timezone.datetime.min.time())).replace(hour=9)
        ag = Agendamento(pet=rex, servico=servicos["Banho simples"], profissional=bia, inicio=amanha)
        ag.full_clean(); ag.save()
        # atendimento já concluído (histórico + financeiro)
        passado = amanha - timedelta(days=3)
        old = Agendamento(pet=mel, servico=servicos["Banho e tosa"], profissional=bia,
                          inicio=passado, status=Agendamento.CONCLUIDO)
        old.save()
        Receita.objects.create(agendamento=old, valor=old.valor_cobrado, forma_pagamento="PIX",
                               data_pagamento=passado.date())
        self.stdout.write(self.style.SUCCESS("Dados iniciais criados."))

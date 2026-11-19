from datetime import timedelta

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# ---------------------------------------------------------------- Funcionário
class FuncionarioManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("E-mail obrigatório")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)  # grava apenas o hash
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("perfil", Funcionario.ADMINISTRADOR)
        return self.create_user(email, password, **extra)


class Funcionario(AbstractBaseUser, PermissionsMixin):
    ATENDENTE, PROFISSIONAL, ADMINISTRADOR = "ATENDENTE", "PROFISSIONAL", "ADMINISTRADOR"
    PERFIS = [(ATENDENTE, "Atendente"), (PROFISSIONAL, "Profissional"),
              (ADMINISTRADOR, "Administrador")]

    nome = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    perfil = models.CharField(max_length=15, choices=PERFIS, default=ATENDENTE)
    especialidade = models.CharField("especialidade", max_length=80, blank=True,
                                     help_text="Ex.: banhista, tosador, veterinário")
    # "ativo" do modelo ER: Django usa is_active para bloquear o login
    is_active = models.BooleanField("ativo", default=True)

    objects = FuncionarioManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome"]

    class Meta:
        ordering = ["nome"]

    @property
    def is_staff(self):
        return self.perfil == self.ADMINISTRADOR

    @property
    def is_admin(self):
        return self.perfil == self.ADMINISTRADOR

    def __str__(self):
        return self.nome


# ---------------------------------------------------------------- Cliente / Pet
class Cliente(models.Model):
    nome = models.CharField(max_length=120)
    telefone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    endereco = models.CharField("endereço", max_length=200, blank=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Pet(models.Model):
    ESPECIES = [("CAO", "Cão"), ("GATO", "Gato"), ("OUTRO", "Outro")]
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="pets")
    nome = models.CharField(max_length=80)
    especie = models.CharField("espécie", max_length=5, choices=ESPECIES, default="CAO")
    raca = models.CharField("raça", max_length=80, blank=True)
    data_nascimento = models.DateField("data de nascimento", null=True, blank=True)

    class Meta:
        ordering = ["nome"]

    def clean(self):
        if self.data_nascimento and self.data_nascimento > timezone.localdate():
            raise ValidationError({"data_nascimento": "A data não pode estar no futuro."})

    def __str__(self):
        return f"{self.nome} ({self.cliente.nome})"


# ---------------------------------------------------------------- Serviço
class Servico(models.Model):
    TIPOS = [("BANHO", "Banho"), ("TOSA", "Tosa"), ("CONSULTA", "Consulta")]
    nome = models.CharField(max_length=80)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    duracao_minutos = models.PositiveIntegerField("duração (min)")
    preco = models.DecimalField("preço", max_digits=8, decimal_places=2)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]

    def clean(self):
        if self.duracao_minutos is not None and self.duracao_minutos < 5:
            raise ValidationError({"duracao_minutos": "Duração mínima de 5 minutos."})

    def __str__(self):
        return self.nome


# ---------------------------------------------------------------- Agendamento
class Agendamento(models.Model):
    AGENDADO, CONCLUIDO, CANCELADO = "AGENDADO", "CONCLUIDO", "CANCELADO"
    STATUS = [(AGENDADO, "Agendado"), (CONCLUIDO, "Concluído"), (CANCELADO, "Cancelado")]

    pet = models.ForeignKey(Pet, on_delete=models.PROTECT, related_name="agendamentos")
    servico = models.ForeignKey(Servico, on_delete=models.PROTECT, verbose_name="serviço")
    profissional = models.ForeignKey(Funcionario, on_delete=models.PROTECT,
                                     related_name="agendamentos")
    inicio = models.DateTimeField("início")
    hora_fim = models.DateTimeField("fim", editable=False)  # inicio + duração do serviço
    # preço congelado no momento da reserva (não muda se o serviço for reajustado)
    valor_cobrado = models.DecimalField("valor cobrado", max_digits=8, decimal_places=2,
                                        editable=False)
    status = models.CharField(max_length=10, choices=STATUS, default=AGENDADO)
    observacoes = models.CharField("observações", max_length=200, blank=True)

    class Meta:
        ordering = ["inicio"]

    def calcular_fim(self):
        return self.inicio + timedelta(minutes=self.servico.duracao_minutos)

    def conflitos(self):
        """UC10: agendamentos ativos do mesmo profissional que se sobrepõem."""
        return (Agendamento.objects
                .filter(profissional=self.profissional)
                .exclude(status=self.CANCELADO)
                .exclude(pk=self.pk)
                .filter(inicio__lt=self.calcular_fim(), hora_fim__gt=self.inicio))

    def clean(self):
        if not (self.servico_id and self.profissional_id and self.inicio):
            return
        if self.profissional.perfil != Funcionario.PROFISSIONAL or not self.profissional.is_active:
            raise ValidationError({"profissional": "Selecione um profissional ativo."})
        if self.status == self.AGENDADO and self.conflitos().exists():
            outro = self.conflitos().first()
            raise ValidationError(
                f"Conflito de horário: {self.profissional} já tem atendimento "
                f"de {timezone.localtime(outro.inicio):%H:%M} às "
                f"{timezone.localtime(outro.hora_fim):%H:%M} nesse dia.")

    def save(self, *args, **kwargs):
        if self.servico_id and self.inicio:
            self.hora_fim = self.calcular_fim()
        if self.valor_cobrado is None and self.servico_id:
            self.valor_cobrado = self.servico.preco
        super().save(*args, **kwargs)

    # regras de ciclo de vida
    @property
    def ja_iniciou(self):
        return self.inicio <= timezone.now()

    @property
    def pode_alterar(self):
        """Cancelar/reagendar: só agendado e que ainda não começou."""
        return self.status == self.AGENDADO and not self.ja_iniciou

    @property
    def pode_concluir(self):
        """Concluir: atendimento agendado do dia atual (ou de dias anteriores)."""
        return (self.status == self.AGENDADO
                and timezone.localtime(self.inicio).date() <= timezone.localdate())

    def __str__(self):
        return f"{self.pet.nome} - {self.servico} - {timezone.localtime(self.inicio):%d/%m %H:%M}"


# ---------------------------------------------------------------- Vacina
class Vacina(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name="vacinas")
    nome = models.CharField(max_length=80)
    data_aplicacao = models.DateField("data de aplicação")
    data_proxima_dose = models.DateField("próxima dose", null=True, blank=True)
    lote = models.CharField(max_length=40, blank=True)
    aplicada_por = models.ForeignKey(Funcionario, on_delete=models.PROTECT,
                                     verbose_name="aplicada por", related_name="vacinas")

    class Meta:
        ordering = ["-data_aplicacao"]

    def clean(self):
        if self.data_aplicacao and self.data_proxima_dose and \
                self.data_proxima_dose <= self.data_aplicacao:
            raise ValidationError({"data_proxima_dose":
                                   "A próxima dose deve ser posterior à aplicação."})

    @property
    def situacao(self):
        """UC11: vencida, a vencer (30 dias) ou em dia."""
        if not self.data_proxima_dose:
            return "sem_reforco"
        hoje = timezone.localdate()
        if self.data_proxima_dose < hoje:
            return "vencida"
        if self.data_proxima_dose <= hoje + timedelta(days=30):
            return "a_vencer"
        return "em_dia"

    def __str__(self):
        return f"{self.nome} - {self.pet.nome}"


# ---------------------------------------------------------------- Receita
class Receita(models.Model):
    FORMAS = [("DINHEIRO", "Dinheiro"), ("PIX", "Pix"), ("CARTAO", "Cartão")]
    # pagamento integral: um atendimento concluído gera uma única receita
    agendamento = models.OneToOneField(Agendamento, on_delete=models.PROTECT,
                                       related_name="receita")
    valor = models.DecimalField(max_digits=8, decimal_places=2)
    forma_pagamento = models.CharField("forma de pagamento", max_length=10, choices=FORMAS)
    data_pagamento = models.DateField("data do pagamento", default=timezone.localdate)

    class Meta:
        ordering = ["-data_pagamento"]

    def clean(self):
        if self.agendamento_id and self.agendamento.status != Agendamento.CONCLUIDO:
            raise ValidationError("Só é possível registrar receita de atendimento concluído.")
        if self.valor is not None and self.valor <= 0:
            raise ValidationError({"valor": "O valor deve ser maior que zero."})

    def __str__(self):
        return f"R$ {self.valor} - {self.agendamento}"

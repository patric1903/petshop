from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from .models import (Agendamento, Cliente, Funcionario, Pet, Receita, Servico, Vacina)

DT = "%Y-%m-%dT%H:%M"


class BootstrapMixin:
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for f in self.fields.values():
            w = f.widget
            w.attrs["class"] = "form-check-input" if isinstance(w, forms.CheckboxInput) \
                else "form-select" if isinstance(w, forms.Select) else "form-control"


class ClienteForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ["nome", "telefone", "email", "endereco"]


class PetForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Pet
        fields = ["cliente", "nome", "especie", "raca", "data_nascimento"]
        widgets = {"data_nascimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class ServicoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Servico
        fields = ["nome", "tipo", "duracao_minutos", "preco", "ativo"]


def profissionais_ativos():
    return Funcionario.objects.filter(perfil=Funcionario.PROFISSIONAL, is_active=True)


class AgendamentoForm(BootstrapMixin, forms.ModelForm):
    inicio = forms.DateTimeField(
        label="Início", input_formats=[DT],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DT))

    class Meta:
        model = Agendamento
        fields = ["pet", "servico", "profissional", "inicio", "observacoes"]

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["servico"].queryset = Servico.objects.filter(ativo=True)
        self.fields["profissional"].queryset = profissionais_ativos()
        if self.instance.pk:  # reagendamento: só data/horário/profissional
            self.fields["pet"].disabled = True
            self.fields["servico"].disabled = True

    def clean_inicio(self):
        inicio = self.cleaned_data["inicio"]
        if not self.instance.pk and inicio < timezone.now():
            raise forms.ValidationError("Não é possível agendar no passado.")
        return inicio


class VacinaForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Vacina
        fields = ["nome", "data_aplicacao", "data_proxima_dose", "lote", "aplicada_por"]
        widgets = {
            "data_aplicacao": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_proxima_dose": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["aplicada_por"].queryset = profissionais_ativos()
        self.fields["aplicada_por"].label = "Aplicada por (profissional)"


class ReceitaForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Receita
        fields = ["valor", "forma_pagamento", "data_pagamento"]
        widgets = {"data_pagamento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class FuncionarioForm(BootstrapMixin, forms.ModelForm):
    senha = forms.CharField(label="Senha", widget=forms.PasswordInput, required=False,
                            help_text="Obrigatória no cadastro; em branco mantém a atual.")

    class Meta:
        model = Funcionario
        fields = ["nome", "email", "perfil", "especialidade", "is_active"]

    def clean_senha(self):
        s = self.cleaned_data.get("senha")
        if not self.instance.pk and not s:
            raise forms.ValidationError("Informe a senha.")
        if s:
            validate_password(s)
        return s

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("senha"):
            user.set_password(self.cleaned_data["senha"])
        if commit:
            user.save()
        return user


class PeriodoForm(BootstrapMixin, forms.Form):
    inicio = forms.DateField(label="De", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    fim = forms.DateField(label="Até", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))

    def clean(self):
        d = super().clean()
        if d.get("inicio") and d.get("fim") and d["fim"] < d["inicio"]:
            raise forms.ValidationError("A data final deve ser igual ou posterior à inicial.")
        return d

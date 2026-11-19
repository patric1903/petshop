from datetime import date, timedelta

from django.contrib import messages
from django.db.models import Q, Sum
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (AgendamentoForm, ClienteForm, FuncionarioForm, PeriodoForm, PetForm,
                    ReceitaForm, ServicoForm, VacinaForm)
from .models import Agendamento, Cliente, Funcionario, Pet, Receita, Servico, Vacina
from .permissions import perfil_required

A, P = Funcionario.ATENDENTE, Funcionario.PROFISSIONAL
ADM = Funcionario.ADMINISTRADOR


def _salvar(request, form_class, instance, titulo, voltar, msg, extra=None, before_save=None):
    """Fluxo padrão de formulário de criar/editar."""
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if before_save:
            before_save(obj)
        obj.save()
        messages.success(request, msg)
        return redirect(voltar)
    ctx = {"form": form, "titulo": titulo, "voltar": voltar}
    ctx.update(extra or {})
    return render(request, "core/form.html", ctx)


def _excluir(request, obj, voltar, nome):
    if request.method == "POST":
        try:
            obj.delete()
            messages.success(request, f"{nome} excluído.")
        except ProtectedError:
            messages.error(request, f"Não é possível excluir: há registros vinculados "
                                    f"(agendamentos ou pets). Remova-os antes.")
        return redirect(voltar)
    return render(request, "core/confirmar_exclusao.html",
                  {"obj": obj, "nome": nome, "voltar": voltar})


# ------------------------------------------------------------------ Painel
@perfil_required(A, P)
def painel(request):
    hoje = timezone.localdate()
    ags = Agendamento.objects.filter(inicio__date=hoje).exclude(status=Agendamento.CANCELADO)
    ctx = {}
    if request.user.perfil == P:
        ags = ags.filter(profissional=request.user)
    else:
        ctx["vacinas_alerta"] = (Vacina.objects
                                 .filter(data_proxima_dose__lte=hoje + timedelta(days=30))
                                 .select_related("pet", "pet__cliente")
                                 .order_by("data_proxima_dose")[:15])
    ctx["hoje"] = ags.select_related("pet", "servico", "profissional")
    ctx["data_hoje"] = hoje
    return render(request, "core/painel.html", ctx)


# ------------------------------------------------------------------ UC02 Clientes
@perfil_required(A)
def clientes(request):
    q = request.GET.get("q", "").strip()
    qs = Cliente.objects.all()
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(telefone__icontains=q))
    return render(request, "core/clientes.html", {"clientes": qs, "q": q})


@perfil_required(A)
def cliente_form(request, pk=None):
    obj = get_object_or_404(Cliente, pk=pk) if pk else None
    return _salvar(request, ClienteForm, obj, "Cliente", "clientes", "Cliente salvo.")


@perfil_required(A)
def cliente_excluir(request, pk):
    return _excluir(request, get_object_or_404(Cliente, pk=pk), "clientes", "Cliente")


# ------------------------------------------------------------------ UC03 Pets
@perfil_required(A)
def pets(request):
    q = request.GET.get("q", "").strip()
    qs = Pet.objects.select_related("cliente")
    if q:
        qs = qs.filter(Q(nome__icontains=q) | Q(cliente__nome__icontains=q))
    return render(request, "core/pets.html", {"pets": qs, "q": q})


@perfil_required(A)
def pet_form(request, pk=None):
    obj = get_object_or_404(Pet, pk=pk) if pk else None
    return _salvar(request, PetForm, obj, "Pet", "pets", "Pet salvo.")


@perfil_required(A)
def pet_excluir(request, pk):
    return _excluir(request, get_object_or_404(Pet, pk=pk), "pets", "Pet")


# ------------------------------------------------------------------ UC09 Histórico
@perfil_required(A, P)
def pet_historico(request, pk):
    pet = get_object_or_404(Pet.objects.select_related("cliente"), pk=pk)
    atendimentos = pet.agendamentos.filter(status=Agendamento.CONCLUIDO) \
        .select_related("servico", "profissional").order_by("-inicio")
    return render(request, "core/pet_historico.html", {
        "pet": pet, "atendimentos": atendimentos,
        "vacinas": pet.vacinas.select_related("aplicada_por"),
        "proximos": pet.agendamentos.filter(status=Agendamento.AGENDADO)
                       .select_related("servico", "profissional"),
    })


# ------------------------------------------------------------------ UC08 / UC11 Vacina
@perfil_required(A, P)
def vacina_nova(request, pk):
    pet = get_object_or_404(Pet, pk=pk)
    form = VacinaForm(request.POST or None,
                      initial={"aplicada_por": request.user.pk
                               if request.user.perfil == P else None,
                               "data_aplicacao": timezone.localdate()})
    form.instance.pet = pet
    if request.method == "POST" and form.is_valid():
        v = form.save()
        msg = "Vacina registrada."
        if v.situacao == "vencida":
            msg += " Atenção: a próxima dose informada já está vencida."
        messages.success(request, msg)
        return redirect("pet_historico", pk=pet.pk)
    return render(request, "core/form.html",
                  {"form": form, "titulo": f"Registrar vacina - {pet.nome}",
                   "voltar": "pet_historico", "voltar_pk": pet.pk})


# ------------------------------------------------------------------ UC05 Agenda
@perfil_required(A, P)
def agenda(request):
    try:
        dia = date.fromisoformat(request.GET.get("data", ""))
    except ValueError:
        dia = timezone.localdate()
    qs = (Agendamento.objects.filter(inicio__date=dia)
          .select_related("pet", "pet__cliente", "servico", "profissional"))
    prof_id = request.GET.get("profissional", "")
    if request.user.perfil == P:          # Profissional vê só a própria agenda
        qs = qs.filter(profissional=request.user)
    elif prof_id.isdigit():
        qs = qs.filter(profissional_id=int(prof_id))
    return render(request, "core/agenda.html", {
        "ags": qs, "dia": dia, "anterior": dia - timedelta(days=1),
        "proximo": dia + timedelta(days=1), "prof_id": prof_id,
        "profissionais": Funcionario.objects.filter(perfil=P, is_active=True),
    })


# ------------------------------------------------------------------ UC04 / UC06 / UC10
@perfil_required(A)
def agendar(request):
    form = AgendamentoForm(request.POST or None, initial={"pet": request.GET.get("pet")})
    if request.method == "POST" and form.is_valid():
        ag = form.save()
        messages.success(request, f"Agendado: {ag}.")
        return redirect("agenda")
    return render(request, "core/form.html",
                  {"form": form, "titulo": "Agendar serviço", "voltar": "agenda"})


@perfil_required(A)
def reagendar(request, pk):
    ag = get_object_or_404(Agendamento, pk=pk)
    if not ag.pode_alterar:
        messages.error(request, "Só é possível reagendar atendimentos agendados que ainda "
                                "não começaram.")
        return redirect("agenda")
    form = AgendamentoForm(request.POST or None, instance=ag)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Atendimento reagendado.")
        return redirect("agenda")
    return render(request, "core/form.html",
                  {"form": form, "titulo": f"Reagendar - {ag.pet.nome}", "voltar": "agenda"})


@perfil_required(A)
@require_POST
def cancelar(request, pk):
    ag = get_object_or_404(Agendamento, pk=pk)
    if ag.pode_alterar:
        ag.status = Agendamento.CANCELADO
        ag.save()
        messages.success(request, "Agendamento cancelado.")
    else:
        messages.error(request, "Atendimento já iniciado ou finalizado não pode ser cancelado; "
                                "o profissional deve registrá-lo como concluído.")
    return redirect("agenda")


# ------------------------------------------------------------------ UC07 Atendimento
@perfil_required(P)
@require_POST
def concluir(request, pk):
    ag = get_object_or_404(Agendamento, pk=pk)
    if request.user.perfil == P and ag.profissional_id != request.user.pk:
        messages.error(request, "Você só pode concluir os seus próprios atendimentos.")
    elif not ag.pode_concluir:
        messages.error(request, "Só é possível concluir atendimentos agendados do dia atual "
                                "ou de dias anteriores.")
    else:
        ag.status = Agendamento.CONCLUIDO
        ag.save()
        messages.success(request, "Atendimento concluído e incluído no histórico do pet.")
    return redirect("agenda")


# ------------------------------------------------------------------ UC12 / UC13 Financeiro
@perfil_required()
def financeiro(request):
    hoje = timezone.localdate()
    form = PeriodoForm(request.GET or None,
                       initial={"inicio": hoje.replace(day=1), "fim": hoje})
    ini, fim = hoje.replace(day=1), hoje
    if request.GET and form.is_valid():
        ini, fim = form.cleaned_data["inicio"], form.cleaned_data["fim"]
    receitas = Receita.objects.filter(data_pagamento__range=(ini, fim)) \
        .select_related("agendamento__pet", "agendamento__servico")
    total = receitas.aggregate(t=Sum("valor"))["t"] or 0
    por_forma = receitas.values("forma_pagamento").annotate(t=Sum("valor")).order_by("-t")
    pendentes = Agendamento.objects.filter(status=Agendamento.CONCLUIDO, receita__isnull=True) \
        .select_related("pet", "servico")
    return render(request, "core/financeiro.html", {
        "form": form, "receitas": receitas, "total": total, "ini": ini, "fim": fim,
        "por_forma": por_forma, "pendentes": pendentes})


@perfil_required()
def receita_nova(request, pk):
    ag = get_object_or_404(Agendamento, pk=pk, status=Agendamento.CONCLUIDO)
    if hasattr(ag, "receita"):
        messages.error(request, "Esse atendimento já possui receita registrada.")
        return redirect("financeiro")
    form = ReceitaForm(request.POST or None, initial={"valor": ag.valor_cobrado,
                                                     "data_pagamento": timezone.localdate()})
    form.instance.agendamento = ag
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Receita registrada.")
        return redirect("financeiro")
    return render(request, "core/form.html",
                  {"form": form, "titulo": f"Receita - {ag}", "voltar": "financeiro"})


# ------------------------------------------------------------------ UC14 Funcionários
@perfil_required()
def funcionarios(request):
    return render(request, "core/funcionarios.html", {"funcionarios": Funcionario.objects.all()})


@perfil_required()
def funcionario_form(request, pk=None):
    obj = get_object_or_404(Funcionario, pk=pk) if pk else None
    form = FuncionarioForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        if obj and obj.pk == request.user.pk and not form.cleaned_data["is_active"]:
            messages.error(request, "Você não pode desativar a própria conta.")
        else:
            form.save()
            messages.success(request, "Funcionário salvo.")
            return redirect("funcionarios")
    return render(request, "core/form.html",
                  {"form": form, "titulo": "Funcionário", "voltar": "funcionarios"})


# ------------------------------------------------------------------ Serviços
@perfil_required()
def servicos(request):
    return render(request, "core/servicos.html", {"servicos": Servico.objects.all()})


@perfil_required()
def servico_form(request, pk=None):
    obj = get_object_or_404(Servico, pk=pk) if pk else None
    return _salvar(request, ServicoForm, obj, "Serviço", "servicos", "Serviço salvo.")

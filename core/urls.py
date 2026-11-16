from django.contrib.auth import views as auth
from django.urls import path

from . import views as v

urlpatterns = [
    path("login/", auth.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("sair/", auth.LogoutView.as_view(), name="logout"),
    path("", v.painel, name="painel"),

    path("clientes/", v.clientes, name="clientes"),
    path("clientes/novo/", v.cliente_form, name="cliente_novo"),
    path("clientes/<int:pk>/editar/", v.cliente_form, name="cliente_editar"),
    path("clientes/<int:pk>/excluir/", v.cliente_excluir, name="cliente_excluir"),

    path("pets/", v.pets, name="pets"),
    path("pets/novo/", v.pet_form, name="pet_novo"),
    path("pets/<int:pk>/", v.pet_historico, name="pet_historico"),
    path("pets/<int:pk>/editar/", v.pet_form, name="pet_editar"),
    path("pets/<int:pk>/excluir/", v.pet_excluir, name="pet_excluir"),
    path("pets/<int:pk>/vacina/", v.vacina_nova, name="vacina_nova"),

    path("agenda/", v.agenda, name="agenda"),
    path("agenda/novo/", v.agendar, name="agendar"),
    path("agenda/<int:pk>/reagendar/", v.reagendar, name="reagendar"),
    path("agenda/<int:pk>/cancelar/", v.cancelar, name="cancelar"),
    path("agenda/<int:pk>/concluir/", v.concluir, name="concluir"),

    path("financeiro/", v.financeiro, name="financeiro"),
    path("financeiro/receita/<int:pk>/", v.receita_nova, name="receita_nova"),

    path("funcionarios/", v.funcionarios, name="funcionarios"),
    path("funcionarios/novo/", v.funcionario_form, name="funcionario_novo"),
    path("funcionarios/<int:pk>/editar/", v.funcionario_form, name="funcionario_editar"),

    path("servicos/", v.servicos, name="servicos"),
    path("servicos/novo/", v.servico_form, name="servico_novo"),
    path("servicos/<int:pk>/editar/", v.servico_form, name="servico_editar"),
]

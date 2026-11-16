from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Agendamento, Cliente, Funcionario, Pet, Receita, Servico, Vacina

admin.site.register([Cliente, Pet, Servico, Agendamento, Vacina, Receita])


@admin.register(Funcionario)
class FuncionarioAdmin(UserAdmin):
    ordering = ["nome"]
    list_display = ["nome", "email", "perfil", "is_active"]
    fieldsets = ((None, {"fields": ("email", "password")}),
                 ("Dados", {"fields": ("nome", "perfil", "especialidade", "is_active")}))
    add_fieldsets = ((None, {"classes": ("wide",), "fields": (
        "email", "nome", "perfil", "password1", "password2")}),)
    search_fields = ["nome", "email"]
    list_filter = ["perfil", "is_active"]
    filter_horizontal = []

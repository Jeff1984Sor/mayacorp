from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser,Produto

# Para gerenciar os produtos
@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'slug']
    prepopulated_fields = {'slug': ('nome',)} # Preenche o slug automaticamente ao digitar o nome

# Para o Usuário
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'telefone', 'is_assinante']
    
    # Adicionamos o campo 'produtos' na tela de edição
    fieldsets = UserAdmin.fieldsets + (
        ('Assinatura e Produtos', {'fields': ('is_assinante', 'produtos', 'telefone', 'cpf', 'nome_empresa')}),
    )
    # Permite selecionar produtos com filtro horizontal (visual melhor)
    filter_horizontal = ('produtos',)

admin.site.register(CustomUser, CustomUserAdmin)
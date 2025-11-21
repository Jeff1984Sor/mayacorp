from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import CustomUserCreationForm
from .models import BannerHome
from django.contrib.auth.decorators import login_required
from .decorators import possui_produto
from .models import CustomUser
from .forms import UsuarioSistemaForm
from django.contrib import messages

# Essa função agora manda o HTML completo (com menu)
def home(request):
    return render(request, 'home.html')

def cadastro(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'registration/cadastro.html', {'form': form})

def home(request):
    banners = BannerHome.objects.filter(ativo=True)
    return render(request, 'home.html', {'banners': banners})


@login_required
@possui_produto('gestao-pilates')
def lista_usuarios(request):
    # Só mostra usuários da MESMA organização
    usuarios = CustomUser.objects.filter(organizacao=request.user.organizacao)
    return render(request, 'core/lista_usuarios.html', {'usuarios': usuarios})

@login_required
@possui_produto('gestao-pilates')
def novo_usuario_sistema(request):
    if request.method == 'POST':
        form = UsuarioSistemaForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            # Vincula o novo usuário à organização do chefe
            user.organizacao = request.user.organizacao
            user.save()
            messages.success(request, "Usuário criado com sucesso!")
            return redirect('lista_usuarios')
    else:
        form = UsuarioSistemaForm()
    
    return render(request, 'core/form_usuario.html', {'form': form})
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from core.decorators import possui_produto
from .models import Aluno
from .forms import AlunoForm

@login_required
@possui_produto('gestao-pilates')
def lista_alunos(request):
    if request.user.organizacao:
        alunos = Aluno.objects.filter(organizacao=request.user.organizacao)
    else:
        alunos = Aluno.objects.none()
    return render(request, 'cadastros_fit/lista_alunos.html', {'alunos': alunos})

@login_required
@possui_produto('gestao-pilates')
def novo_aluno(request):
    if request.method == 'POST':
        form = AlunoForm(request.POST, request.FILES)
        if form.is_valid():
            aluno = form.save(commit=False)
            aluno.organizacao = request.user.organizacao
            aluno.save()
            messages.success(request, "Aluno cadastrado com sucesso!")
            return redirect('lista_alunos')
    else:
        form = AlunoForm()
    return render(request, 'cadastros_fit/form_aluno.html', {'form': form, 'titulo': 'Novo Aluno'})

@login_required
@possui_produto('gestao-pilates')
def editar_aluno(request, id):
    aluno = get_object_or_404(Aluno, id=id, organizacao=request.user.organizacao)
    if request.method == 'POST':
        form = AlunoForm(request.POST, request.FILES, instance=aluno)
        if form.is_valid():
            form.save()
            messages.success(request, "Dados atualizados!")
            return redirect('lista_alunos')
    else:
        form = AlunoForm(instance=aluno)
    return render(request, 'cadastros_fit/form_aluno.html', {'form': form, 'titulo': 'Editar Aluno'})
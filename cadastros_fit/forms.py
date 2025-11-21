from django import forms
from .models import Aluno

class AlunoForm(forms.ModelForm):
    class Meta:
        model = Aluno
        fields = ['nome', 'cpf', 'data_nascimento', 'telefone', 'email', 'endereco', 'foto_rosto']
        widgets = {
            'data_nascimento': forms.DateInput(attrs={'type': 'date'}),
        }
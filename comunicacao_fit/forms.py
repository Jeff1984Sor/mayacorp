from django import forms
from .models import TemplateMensagem, ConexaoWhatsapp

class ConexaoWhatsappForm(forms.ModelForm):
    class Meta:
        model = ConexaoWhatsapp
        fields = ['instancia', 'apikey', 'url_base', 'ativo']
        widgets = {
            'instancia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da instância'}),
            'apikey': forms.PasswordInput(render_value=True, attrs={'class': 'form-control', 'placeholder': 'Sua ApiKey'}),
            'url_base': forms.URLInput(attrs={'class': 'form-control'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class TemplateMensagemForm(forms.ModelForm):
    class Meta:
        model = TemplateMensagem
        fields = ['titulo', 'gatilho', 'conteudo', 'horario_envio', 'ativo']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'gatilho': forms.Select(attrs={'class': 'form-control'}),
            'conteudo': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'horario_envio': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
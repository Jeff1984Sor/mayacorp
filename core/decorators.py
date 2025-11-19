from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def possui_produto(slug_produto):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 1. Se não tá logado, manda pro login
            if not request.user.is_authenticated:
                return redirect('login')
            
            # 2. Se é superusuário (você), libera tudo
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # 3. Verifica se ele tem o produto na lista
            if request.user.produtos.filter(slug=slug_produto).exists():
                return view_func(request, *args, **kwargs)
            
            # 4. Se não tiver, avisa e manda pra home (ou página de venda)
            messages.error(request, "Você não tem acesso a esta ferramenta. Faça um upgrade!")
            return redirect('home')
            
        return _wrapped_view
    return decorator
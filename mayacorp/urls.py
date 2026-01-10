from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import debug_auth

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Adicionando namespaces para bater com os links da Sidebar
    path('', include('core.urls', namespace='core')),       
    path('cadastros/', include('cadastros_fit.urls', namespace='cadastros')), 
    path('agenda/', include('agenda_fit.urls', namespace='agenda')),
    path('financeiro/', include('financeiro_fit.urls', namespace='financeiro')),
    path('contratos/', include('contratos_fit.urls', namespace='contratos')),
    path('comunicacao/', include('comunicacao_fit.urls', namespace='comunicacao')), 
    path('termos/', include('termos_fit.urls', namespace='termos')),
    
    # Outros Apps
    path('tools/pdf/', include('pdf_tools.urls', namespace='pdf_tools')),
    path('app/', include('portal_aluno.urls', namespace='portal_aluno')), 
    path('debug-login/', debug_auth),
    
    # Rota necessária para o Tailwind atualizar a página sozinho (Live Reload)
    path("__reload__/", include("django_browser_reload.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
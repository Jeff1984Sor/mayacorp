from django.apps import AppConfig


class ComunicacaoFitConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'comunicacao_fit'

    def ready(self):
        # Isso garante que os sinais sejam registrados quando o Django iniciar
        import comunicacao_fit.signals

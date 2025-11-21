from django.apps import AppConfig


class FinanceiroFitConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'financeiro_fit'

    def ready(self):
        import financeiro_fit.signals # <--- Adicione isso!

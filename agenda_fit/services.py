from datetime import timedelta
from django.utils import timezone
from agenda_fit.models import Aula, Presenca

def gerar_agenda_contrato(contrato):
    print(f"--- INICIANDO GERAÇÃO PARA CONTRATO {contrato.id} ---")
    
    horarios = contrato.horarios_fixos.all()
    if not horarios:
        print("ERRO: Nenhum horário fixo encontrado.")
        return

    print(f"Horários encontrados: {horarios.count()}")
    for h in horarios:
        print(f" - Dia: {h.get_dia_semana_display()} ({h.dia_semana}) às {h.horario}")

    data_atual = contrato.data_inicio
    data_final = contrato.data_fim
    
    print(f"Período: {data_atual} até {data_final}")
    
    aulas_criadas = 0
    
    while data_atual <= data_final:
        dia_semana = data_atual.weekday() # 0=Segunda
        # print(f"Checando dia {data_atual} (Dia da semana: {dia_semana})") 
        
        for h in horarios:
            if h.dia_semana == dia_semana:
                print(f" >> MATCH! Dia {data_atual} bate com horário {h}")
                
                inicio = timezone.make_aware(timezone.datetime.combine(data_atual, h.horario))
                fim = inicio + timedelta(hours=1)
                
                try:
                    aula, created = Aula.objects.get_or_create(
                        data_hora_inicio=inicio,
                        profissional=h.profissional,
                        defaults={
                            'organizacao': contrato.plano.organizacao,
                            'unidade': contrato.unidade,
                            'data_hora_fim': fim,
                            'status': 'AGENDADA'
                        }
                    )
                    
                    if created:
                        print(f"    [NOVA] Aula criada: {aula}")
                    else:
                        print(f"    [EXISTE] Usando aula existente: {aula}")

                    if not aula.presencas.filter(aluno=contrato.aluno).exists():
                        Presenca.objects.create(aula=aula, aluno=contrato.aluno)
                        aulas_criadas += 1
                        print(f"    [PRESENÇA] Aluno adicionado!")
                    else:
                        print(f"    [INFO] Aluno já estava na lista.")
                        
                except Exception as e:
                    print(f"    [ERRO CRÍTICO] {e}")

        data_atual += timedelta(days=1)

    print(f"--- FIM. Total agendado: {aulas_criadas} ---")
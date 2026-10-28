# Exportação do cartão de ponto: de onde vem a coluna "atrasos"

- Serviço: `app/application/services/rh_ponto_export_service.py` (montado em `get_rh_ponto_export_service`, `app/http/dependencies/services.py`).
- Repositórios opcionais no construtor (`abono_repo`, `ferias_repo`, `atestado_repo`, `tipo_atestado_repo`, `evento_calendario_repo`) são **ignorados em silêncio quando ficam `None`**. Até out/2026 a injeção de dependência não passava nenhum deles, então abonos lançados pelo RH não chegavam à planilha (o commit af4fa81 adicionou abonos ao serviço, mas não à injeção de dependência).
- A regra de abono precisa bater com `RhAbonoService.listar_faltas` e `RhFolhaService._calcular_componentes_folha`:
  - férias APROVADO/EM_ANDAMENTO, atestado ENTREGUE de tipo `abona_falta`, abono manual de dia inteiro e eventos FERIADO/PONTO_FACULTATIVO/ABONO abonam o dia;
  - abono parcial (minutos) abate a dívida do dia, sem nunca passar dela;
  - LIBERACAO_ANTECIPADA reduz a jornada esperada (`minutos_liberacao`).
- Dia posterior a hoje (fuso local) não gera atraso na exportação.
- No dia abonado, a exportação usa esperado=0, então uma batida nesse dia aparece como HE (diferente do resumo da folha, que zera o dia abonado).

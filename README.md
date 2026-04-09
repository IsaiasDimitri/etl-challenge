# Delfos Energy — ETL IoT com FastAPI + Dagster

Pipeline completo de extração, transformação e carga de dados IoT. Sistema simulado com dois bancos Postgres (fonte e alvo), API FastAPI como conector de leitura, ETL diário consumindo dados via HTTP e agregando em janelas de 10 minutos, orquestrado com Dagster.

## Arquitetura

```
┌─────────────────┐
│  Banco Fonte    │  (dados brutos IoT, 1-min)
│   (Postgres)    │
└────────┬────────┘
         │
         │ API (FastAPI)
         ▼
┌─────────────────┐
│   ETL (Python)  │  ← httpx + pandas
└────────┬────────┘   ← janela 10-min (mean, min, max, std)
         │
         ▼
┌─────────────────┐
│  Banco Alvo     │  (dados agregados)
│   (Postgres)    │
└─────────────────┘
         ▲
         │ Dagster (orquestração diária)
         │ asset particionado + schedule
```

## Pré-requisitos

- **Docker** e **docker-compose** (v20.10+)
- **Linux/macOS** com bash disponível

## Subir a stack

### 1. Clone ou navegue para o diretório do projeto

```bash
cd /home/isaias/workspace/personal/delfos-energy
```

### 2. Configure variáveis de ambiente (opcional)

Copie `.env.example` para `.env` se precisar alterar valores padrão:

```bash
cp .env.example .env
```

Os valores padrão já funcionam para rodar localmente:
- Banco fonte: `iot` / `iot`
- Banco alvo: `etl` / `etl`
- API: `http://localhost:8000`

### 3. Construa as imagens e inicie os serviços

```bash
docker compose up -d --build
```

Isso vai:
1. Construir a imagem Docker com dependências Python
2. Subir dois containers Postgres (porta 5433 para fonte, 5434 para alvo)
3. Executar API FastAPI (porta 8000)
4. Executar bootstrap que carrega 10 dias de dados (14.400 registros na fonte)
5. Subir Dagster webserver (porta 3000) e daemon
6. Inicializar schema do banco alvo com catálogo de sinais

**Tempo esperado**: ~2-3 minutos na primeira execução.

### 4. Valide que tudo está rodando

```bash
docker compose ps
```

Você deve ver 6 containers em estado "Up":
- `db_source` (healthy)
- `db_target` (healthy)
- `source_api` (running)
- `bootstrap_source` (exited com código 0)
- `dagster_webserver` (running)
- `dagster_daemon` (running)

## Como usar

### Consultar dados da API

A API expõe a rota `/data` para ler dados do banco fonte com filtros:

```bash
# Buscar wind_speed e power do primeiro dia
curl -sS "http://localhost:8000/data?start=2026-03-30T00:00:00Z&end=2026-03-30T23:59:59Z&signals=wind_speed&signals=power" | jq .
```

**Parâmetros:**
- `start` (ISO 8601, UTC): data/hora início (inclusive)
- `end` (ISO 8601, UTC): data/hora fim (exclusive)
- `signals` (repetido): variáveis desejadas — `wind_speed`, `power`, `ambient_temprature`

**Resposta:**
```json
{
  "count": 60,
  "signals": ["wind_speed", "power"],
  "data": [
    {
      "timestamp": "2026-03-30T00:00:00Z",
      "wind_speed": 5.23,
      "power": 60.38
    },
    ...
  ]
}
```

**Health check:**
```bash
curl -sS http://localhost:8000/health
```

### Executar ETL manualmente para uma data

```bash
# ETL para hoje (UTC)
docker compose run --rm api python -m app.scripts.run_etl --date $(date -u +%F)

# ETL para uma data específica
docker compose run --rm api python -m app.scripts.run_etl --date 2026-03-30
```

Saída esperada:
```
Loaded 656 rows for 2026-03-30
```

Isso:
1. Consulta a API para wind_speed e power do dia inteiro
2. Agrega em janelas de 10 minutos (mean, min, max, std)
3. Grava no banco alvo (delete+insert diário para garantir idempotência)

### Materializar partição Dagster manualmente

```bash
# Materializar partição de ontem
PART=$(date -u -d 'yesterday' +%F)
docker compose run --rm dagster_webserver dagster asset materialize \
  --select daily_iot_etl \
  --partition "$PART" \
  -m app.orchestration.definitions
```

### Acessar Dagster UI

Abra no navegador:

```
http://localhost:3000
```

Lá você verá:
- **Assets**: `daily_iot_etl` (particionado por dia)
- **Jobs**: `daily_iot_etl_job` (executa o asset)
- **Schedules**: `daily_iot_etl_schedule` (executa 01:05 UTC diariamente)

Para materializar via UI:
1. Clique no asset `daily_iot_etl`
2. Selecione a partição desejada
3. Clique **Materialize selected**

## Estrutura de diretórios

```
delfos-energy/
├── README.md                       # Este arquivo
├── docker-compose.yaml             # Orquestração dos serviços
├── Dockerfile                      # Imagem Python
├── requirements.txt                # Dependências
├── .env.example                    # Template de envs
├── .gitignore
│
└── app/
    ├── __init__.py
    ├── config.py                   # Variáveis de ambiente
    ├── db.py                       # Engines e sessions SQLAlchemy
    │
    ├── api/
    │   ├── __init__.py
    │   └── main.py                 # FastAPI app + rota /data
    │
    ├── models/
    │   ├── __init__.py
    │   ├── source.py               # ORM banco fonte
    │   └── target.py               # ORM banco alvo
    │
    ├── etl/
    │   ├── __init__.py
    │   └── daily.py                # Extract, Transform, Load
    │
    ├── orchestration/
    │   ├── __init__.py
    │   └── definitions.py          # Dagster assets, jobs, schedules
    │
    └── scripts/
        ├── __init__.py
        ├── init_source.py          # Criar schema fonte
        ├── init_target.py          # Criar schema alvo + sinais
        ├── bootstrap_source.py     # Seed 10 dias 1-min
        └── run_etl.py              # Executar ETL manual
```

## Dados

### Banco Fonte (`source_db`)

Tabela `data`:
- `timestamp` (DateTime, UTC): chave primária, frequência 1-minuto
- `wind_speed` (float): velocidade do vento (m/s)
- `power` (float): potência (kW)
- `ambient_temprature` (float): temperatura ambiente (°C)

**Bootstrap**: 10 dias completos (2026-03-30 a 2026-04-08), 14.400 registros.

### Banco Alvo (`target_db`)

Tabela `signal`:
- `id` (int): chave primária
- `name` (str): nome do sinal (ex: `wind_speed_mean`, `power_std`)

Tabela `data`:
- `timestamp` (DateTime, UTC): chave primária composta
- `signal_id` (int): chave estrangeira para signal
- `value` (float): valor agregado

**Sinais armazenados**: 8 por dia (wind_speed_mean/min/max/std, power_mean/min/max/std)

## Validação rápida

```bash
# 1. API responde
curl -sS http://localhost:8000/health

# 2. Banco fonte tem dados
docker exec -i db_source psql -U iot -d source_db -c "SELECT COUNT(*) FROM data;"
# Esperado: 14400

# 3. Banco alvo tem sinais
docker exec -i db_target psql -U etl -d target_db -c "SELECT name FROM signal;"
# Esperado: 8 sinais

# 4. ETL carregou
docker exec -i db_target psql -U etl -d target_db -c "SELECT COUNT(*) FROM data;"
# Esperado: > 0 (aumenta conforme você executa ETL)
```

## Limpeza e reset

### Parar a stack

```bash
docker compose down
```

### Remover volumes (reset completo)

```bash
# ⚠️ Isso apaga todos os dados
docker compose down -v
```

Depois reinicie com:
```bash
docker compose up -d --build
```

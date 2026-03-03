# pgvector-bedrock-demo

Sistema completo di **semantic search + RAG chat** con pgvector su AWS RDS, embeddings e LLM via AWS Bedrock.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![AWS](https://img.shields.io/badge/AWS-RDS%20%7C%20ECS%20%7C%20Bedrock-orange.svg)](https://aws.amazon.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-blue.svg)](https://github.com/dpadeletti/pgvector-bedrock-demo/actions)

## Cosa fa questo progetto

Sistema end-to-end di RAG (Retrieval-Augmented Generation) con pipeline di retrieval avanzata:

- Salva embeddings vettoriali (1024 dimensioni) in PostgreSQL con pgvector + indice HNSW
- Genera embeddings con AWS Bedrock Titan Embeddings V2
- **Hybrid search**: combina ricerca semantica (pgvector cosine) e full-text (PostgreSQL tsvector) via Reciprocal Rank Fusion
- **Reranking**: riordina i candidati con Nova Micro come cross-encoder per massimizzare la rilevanza
- **Query expansion**: genera 3 varianti della query con Nova Micro per aumentare la copertura semantica
- Risponde a domande in IT/EN usando i documenti come contesto (RAG) via Amazon Nova Lite
- Chat UI dark terminal servita direttamente dall'API su `/`
- REST API con FastAPI deployata su AWS ECS Fargate
- CI/CD automatizzato con GitHub Actions (push → test → ECR → ECS)
- Secrets gestiti con AWS Secrets Manager
- **16.667 chunk**: Wikipedia (250 topic EN + 50 IT) + arXiv (10K abstract ML/AI)

## Prerequisiti

- Account AWS con accesso a: RDS, Bedrock (Titan Embeddings + Amazon Nova), ECS Fargate + ECR, Secrets Manager
- Python 3.11+
- AWS CLI configurata
- Docker

## Architettura

```
  GitHub Actions (CI/CD)
        │
        │ push to main
        ▼
  ┌─────────────┐     build & push     ┌─────────┐
  │   GitHub    │ ──────────────────── │   ECR   │
  │  (Actions)  │                      │ (image) │
  └─────────────┘                      └────┬────┘
                                            │ pull
                                            ▼
  ┌──────────┐   HTTP    ┌─────────────────────────────┐
  │ Browser  │ ────────► │   ALB (eu-north-1)          │
  │ / Client │           └──────────────┬──────────────┘
  └──────────┘                          │
                                        ▼
                         ┌──────────────────────────────┐
                         │   ECS Fargate                │
                         │   FastAPI + uvicorn :8000    │
                         │   Chat UI su /               │
                         └──────┬──────────────┬────────┘
                                │              │
                    ┌───────────▼──┐    ┌──────▼───────────────────┐
                    │  RDS         │    │  Bedrock                  │
                    │  pgvector    │    │  Titan V2   (embeddings)  │
                    │  HNSW index  │    │  Nova Micro (rerank+expand)│
                    │  tsvector    │    │  Nova Lite  (RAG answer)  │
                    │  16.667 docs │    └──────────────────────────┘
                    └──────────────┘
                         +
                    ┌──────────────┐
                    │  Secrets     │
                    │  Manager     │
                    │ (DB_PASSWORD)│
                    └──────────────┘
```

## Pipeline RAG completa

```
Query utente
      │
      ├─► [expand=true] Nova Micro genera 3 varianti della query
      │
      ▼
Embedding (Titan V2) per query + varianti
      │
      ▼
Hybrid Retrieve (per ogni query)
  ├── Semantic:  pgvector cosine similarity  →  top-N chunk
  └── Full-text: PostgreSQL tsvector rank    →  top-N chunk
      │
      ▼
RRF Merge — Reciprocal Rank Fusion su tutte le liste
      │
      ├─► [rerank=true] Nova Micro riordina per rilevanza semantica
      │
      ▼
Top-K chunk → Prompt con contesto numerato [1]...[K]
      │
      ▼
Nova Lite → risposta in IT/EN con citazioni + fonti Wikipedia/arXiv
```

**Modalità search_mode** nella risposta:
| Modalità | Parametri |
|----------|-----------|
| `semantic` | `hybrid=false` |
| `hybrid` | `hybrid=true` |
| `hybrid+rerank` | `hybrid=true, rerank=true` |
| `hybrid+expand` | `hybrid=true, expand=true` |
| `hybrid+expand+rerank` | `hybrid=true, expand=true, rerank=true` |

## Quick Start (locale)

```bash
# 1. Clona il repository
git clone https://github.com/dpadeletti/pgvector-bedrock-demo.git
cd pgvector-bedrock-demo

# 2. Installa dipendenze
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configura .env
cp .env.example .env
# Inserisci endpoint RDS, password, region

# 4. Inizializza DB
python3 init_db.py

# 5. Migrazione hybrid search (tsvector + indice GIN)
psql -h YOUR-RDS-ENDPOINT -U postgres -d postgres -f migrate_hybrid_search.sql

# 6. Popola il DB (Wikipedia + arXiv)
python3 populate_db.py --source wikipedia
python3 populate_db.py --source arxiv --arxiv-limit 10000

# 7. Ricrea indice HNSW dopo popolamento
psql -h YOUR-RDS-ENDPOINT -U postgres -d postgres << 'SQL'
DROP INDEX IF EXISTS documents_embedding_hnsw_idx;
CREATE INDEX documents_embedding_hnsw_idx
  ON documents USING hnsw (embedding vector_cosine_ops)
  WITH (m=16, ef_construction=64);
SQL

# 8. Avvia API
uvicorn api:app --reload
# → http://localhost:8000        (Chat UI)
# → http://localhost:8000/docs   (Swagger)
```

## API Live

```
Base URL: http://pgvector-alb-1618965750.eu-north-1.elb.amazonaws.com

GET  /          → Chat UI (interfaccia browser)
GET  /health    → Health check (DB + Bedrock)
GET  /docs      → Swagger UI
GET  /stats     → Statistiche documenti
GET  /documents → Lista documenti (paginata)
POST /documents → Crea nuovo documento con embedding
POST /search    → Ricerca ibrida (semantic + fulltext + rerank + expand)
POST /chat      → RAG chat
```

### Esempio ricerca ibrida completa

```bash
curl -X POST http://pgvector-alb-1618965750.eu-north-1.elb.amazonaws.com/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "LoRA fine-tuning large language models",
    "limit": 5,
    "hybrid": true,
    "rerank": true,
    "expand": false
  }'
```

### Esempio RAG chat

```bash
curl -X POST http://pgvector-alb-1618965750.eu-north-1.elb.amazonaws.com/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Come funziona il machine learning?",
    "limit": 5,
    "rerank": true,
    "expand": false
  }'
```

La risposta include `answer`, `sources` (titolo, URL, similarity), `model_id`, `reranked`, `search_mode`.

## Modelli Bedrock

| Modello | Uso nel sistema | Note |
|---------|----------------|------|
| `amazon.titan-embed-text-v2:0` | Embeddings (sempre) | 1024 dim |
| `amazon.nova-micro-v1:0` | Reranking + Query expansion | Veloce, economico |
| `amazon.nova-lite-v1:0` | RAG answer (default) | Bilanciato |
| `amazon.nova-pro-v1:0` | RAG answer (opzionale) | Più preciso |
| `anthropic.claude-3-haiku-20240307-v1:0` | RAG answer (opzionale) | Richiede approvazione Bedrock |

## Sorgenti dati

| Sorgente | Chunk | Lingua | Contenuto |
|----------|-------|--------|-----------|
| Wikipedia EN | ~5.500 | EN | 250 topic AI/ML/NLP/MLOps |
| Wikipedia IT | ~1.200 | IT | 50 topic AI/ML |
| arXiv | ~10.000 | EN | Abstract paper cs.LG, cs.AI, cs.NE, cs.CL, cs.CV, stat.ML |
| **Totale** | **~16.700** | | |

## Popolamento DB

```bash
# Wikipedia
python3 populate_db.py --source wikipedia           # tutti i topic
python3 populate_db.py --source wikipedia --lang en  # solo EN
python3 populate_db.py --source wikipedia --limit 5  # test rapido

# arXiv
python3 populate_db.py --source arxiv --arxiv-limit 10000  # ~10K paper
python3 populate_db.py --source arxiv --arxiv-limit 200    # test rapido

# Tutto insieme
python3 populate_db.py --source all --dry-run  # stima senza inserire
```

Resume automatico: i chunk già presenti nel DB vengono saltati via hash.

## CI/CD

Ogni push su `main` attiva:

```
1. Test     → pytest (validation tests, no infra richiesta)
2. Build    → docker build + push su ECR
3. Deploy   → ECS force-new-deployment + wait stable
```

```
GitHub → Settings → Secrets → Actions:
  AWS_ACCESS_KEY_ID     → IAM access key
  AWS_SECRET_ACCESS_KEY → IAM secret key
```

## Struttura Progetto

```
pgvector-bedrock-demo/
├── README.md
├── Dockerfile
├── requirements.txt
├── .env.example
│
├── api.py                    # FastAPI: /search, /chat, /documents, /stats, /health
├── chat_ui.html              # Chat UI dark terminal (servita su /)
├── config.py                 # Configurazione DB e AWS
├── embeddings.py             # Client Bedrock Titan V2
├── init_db.py                # Crea tabelle + estensione pgvector
├── populate_db.py            # Popola DB da Wikipedia (250 EN+IT) + arXiv (10K)
├── create_hnsw_index.sql     # Indice HNSW per semantic search veloce
├── migrate_hybrid_search.sql # Aggiunge tsvector + GIN per full-text search
│
├── tests/
│   ├── test_api.py           # Test pytest automatici (CI)
│   ├── test_rag_quality.py   # Test qualità RAG pipeline (hybrid, rerank, expand)
│   ├── test_client.py        # Client Python interattivo
│   └── manual_test.sh        # Test rapidi con curl
│
├── infra/
│   ├── setup_aws_infra.sh    # IaC: crea intera infrastruttura da zero
│   └── INFRA_GUIDE.md        # Guida dettagliata all'architettura
│
└── .github/workflows/deploy.yml
```

## Configurazione (.env)

```bash
DB_HOST=pgvector-demo-db.xxxxx.eu-north-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=YourSecurePassword123   # Solo locale — in ECS viene da Secrets Manager

AWS_REGION=eu-north-1
AWS_BEDROCK_MODEL_ID=amazon.titan-embed-text-v2:0
```

## Costi AWS

| Servizio | Tipo | Costo/mese | Free Tier |
|----------|------|------------|-----------|
| RDS PostgreSQL | db.t3.micro | ~$12 | 750 ore/mese (12 mesi) |
| ECS Fargate | 256 CPU / 512 MB | ~$5 | No |
| ALB | Load Balancer | ~$16 | No |
| ECR | Storage immagini | ~$0.50 | No |
| Bedrock Titan | Embeddings | ~$0.01/1K chunk | Pay per use |
| Bedrock Nova | Chat + Rerank + Expand | ~$0.001/query | Pay per use |
| Secrets Manager | 1 secret | ~$0.40 | No |
| **Totale** | | **~$34/mese** | |

Per risparmiare ~$17/mese: stoppa RDS e scala ECS a 0.

```bash
# Stop
aws rds stop-db-instance --db-instance-identifier pgvector-demo-db --region eu-north-1
aws ecs update-service --cluster pgvector-demo-cluster --service pgvector-demo-service --desired-count 0 --region eu-north-1

# Riavvia
aws rds start-db-instance --db-instance-identifier pgvector-demo-db --region eu-north-1
aws ecs update-service --cluster pgvector-demo-cluster --service pgvector-demo-service --desired-count 1 --region eu-north-1
```

## Troubleshooting

**`extension vector does not exist`**
```bash
psql -h YOUR-RDS-ENDPOINT -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

**`Connection timed out` (RDS)**
```bash
aws ec2 authorize-security-group-ingress \
  --group-id sg-029573f0998e11be5 --protocol tcp --port 5432 \
  --cidr $(curl -s https://checkip.amazonaws.com)/32 --region eu-north-1
```

**`password authentication failed`**
```bash
aws secretsmanager get-secret-value \
  --secret-id pgvector-demo/db-password --region eu-north-1 --query "SecretString"
```

**`Access denied` (Bedrock)**
```
AWS Console → Bedrock → Model access → Richiedi accesso al modello
```

**`SyntaxError` con `python populate_db.py`**
```bash
# Usa python3, non python (che su Mac è Python 2)
python3 populate_db.py
```

## Risorse

- [pgvector](https://github.com/pgvector/pgvector)
- [AWS Bedrock Titan Embeddings](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)
- [Amazon Nova Models](https://docs.aws.amazon.com/bedrock/latest/userguide/amazon-nova.html)
- [Reciprocal Rank Fusion (paper)](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
- [FastAPI](https://fastapi.tiangolo.com/)
- [AWS ECS Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)

## Autore

**Davide Padeletti** — [GitHub](https://github.com/dpadeletti)

---

Fatto con curiosità per esplorare semantic search e RAG con pgvector + AWS Bedrock.

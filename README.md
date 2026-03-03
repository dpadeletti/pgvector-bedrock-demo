# pgvector-bedrock-demo

Sistema completo di **semantic search + RAG chat** con pgvector su AWS RDS, embeddings e LLM via AWS Bedrock.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![AWS](https://img.shields.io/badge/AWS-RDS%20%7C%20ECS%20%7C%20Bedrock-orange.svg)](https://aws.amazon.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-blue.svg)](https://github.com/dpadeletti/pgvector-bedrock-demo/actions)

## Cosa fa questo progetto

Sistema end-to-end di RAG (Retrieval-Augmented Generation) che:

- Salva embeddings vettoriali (1024 dimensioni) in PostgreSQL con pgvector + indice HNSW
- Genera embeddings con AWS Bedrock Titan Embeddings V2
- Ricerca documenti simili via similarità coseno (operatore pgvector `<=>`)
- Risponde a domande in linguaggio naturale (IT/EN) usando i documenti come contesto (RAG)
- Chat UI dark terminal servita direttamente dall'API su `/`
- REST API con FastAPI deployata su AWS ECS Fargate
- CI/CD automatizzato con GitHub Actions (push → test → ECR → ECS)
- Secrets gestiti con AWS Secrets Manager
- 1928 chunk Wikipedia su AI/ML/Data Science (EN + IT) con indice HNSW

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
                    ┌───────────▼──┐    ┌──────▼───────────────┐
                    │  RDS         │    │  Bedrock              │
                    │  pgvector    │    │  Titan V2 (embed)     │
                    │  HNSW index  │    │  Nova Lite (LLM/RAG)  │
                    │  1928 chunk  │    └──────────────────────┘
                    └──────────────┘
                         +
                    ┌──────────────┐
                    │  Secrets     │
                    │  Manager     │
                    │ (DB_PASSWORD)│
                    └──────────────┘
```

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
python init_db.py

# 5. Popola con Wikipedia (63 topic AI/ML, ~1900 chunk, ~15-20 min)
pip install tqdm
python populate_db.py

# 6. Crea indice HNSW (dopo popolamento)
psql -h YOUR-RDS-ENDPOINT -U postgres -d postgres -f create_hnsw_index.sql

# 7. Avvia API
uvicorn api:app --reload
# → http://localhost:8000  (Chat UI)
# → http://localhost:8000/docs  (Swagger)
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
POST /search    → Ricerca semantica
POST /chat      → RAG chat (domanda → retrieval → LLM → risposta + fonti)
```

### Esempio ricerca semantica

```bash
curl -X POST http://pgvector-alb-1618965750.eu-north-1.elb.amazonaws.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning", "limit": 3}'
```

### Esempio RAG chat

```bash
curl -X POST http://pgvector-alb-1618965750.eu-north-1.elb.amazonaws.com/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Come funziona il machine learning?", "limit": 5}'
```

La risposta include `answer` (testo LLM), `sources` (chunk usati con titolo, URL, similarity score) e `model_id`.

## Come funziona il RAG

```
Domanda utente
      │
      ▼
Embedding (Titan V2)
      │
      ▼
Ricerca pgvector HNSW  ──→  Top-5 chunk più simili
      │
      ▼
Prompt = system + contesto numerato [1]...[5] + domanda
      │
      ▼
Amazon Nova Lite (via Bedrock)
      │
      ▼
Risposta in IT/EN con citazioni [1], [2], ecc. + fonti linkate
```

**Modelli supportati** (selezionabili dalla UI):
| Modello | Uso | Note |
|---------|-----|------|
| `amazon.nova-lite-v1:0` | Default | Veloce, economico |
| `amazon.nova-micro-v1:0` | Più veloce | Risposte più brevi |
| `amazon.nova-pro-v1:0` | Più preciso | Costo maggiore |
| `anthropic.claude-3-haiku-20240307-v1:0` | Opzionale | Richiede approvazione Anthropic su Bedrock |

## Indice HNSW

Dopo aver popolato il database con 1000+ documenti, crea l'indice HNSW per ricerche in O(log n):

```bash
psql -h YOUR-RDS-ENDPOINT -U postgres -d postgres -f create_hnsw_index.sql
```

Parametri usati: `m=16` (connessioni per nodo), `ef_construction=64` (qualità build), `vector_cosine_ops`.

## Popolamento DB (Wikipedia)

```bash
# Preview (dry run)
python populate_db.py --dry-run

# Test con 5 topic
python populate_db.py --limit 5

# Popolamento completo (63 topic, ~15-20 min, resume automatico)
python populate_db.py

# Solo articoli in italiano
python populate_db.py --lang it
```

63 topic su AI, Machine Learning, Deep Learning, NLP, Data Science, MLOps (EN + IT).
Output: ~1900 chunk · ~5MB · indice HNSW ~46MB totale.

## CI/CD

Ogni push su `main` attiva:

```
1. Test     → pytest (validation tests, no infra richiesta)
2. Build    → docker build + push su ECR
3. Deploy   → ECS force-new-deployment + wait stable
```

Configura su un nuovo repo:
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
├── api.py               # FastAPI: /search, /chat, /documents, /stats, /health
├── chat_ui.html         # Chat UI (servita su /)
├── config.py            # Configurazione DB e AWS
├── embeddings.py        # Client Bedrock Titan V2
├── init_db.py           # Crea tabelle + estensione pgvector
├── populate_db.py       # Popola DB da Wikipedia (63 topic EN/IT)
├── create_hnsw_index.sql
│
├── infra/
│   ├── setup_aws_infra.sh   # IaC: crea intera infrastruttura da zero
│   └── INFRA_GUIDE.md       # Guida dettagliata all'architettura
│
├── tests/
│   ├── test_api.py
│   ├── test_client.py
│   └── manual_test.sh
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
| Bedrock Titan | Embeddings | ~$0.01 per 1000 chunk | Pay per use |
| Bedrock Nova Lite | Chat RAG | ~$0.0001/1K token | Pay per use |
| Secrets Manager | 1 secret | ~$0.40 | No |
| **Totale** | | **~$34/mese** | |

Per risparmiare ~$17/mese: stoppa RDS e scala ECS a 0 quando non usi il progetto.

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

**`403 Forbidden` (Wikipedia API)**
```python
# Assicurati che populate_db.py includa il header User-Agent nella richiesta requests.get()
headers = {"User-Agent": "pgvector-bedrock-demo/1.0 (educational project)"}
```

## Risorse

- [pgvector](https://github.com/pgvector/pgvector)
- [AWS Bedrock Titan Embeddings](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)
- [Amazon Nova Models](https://docs.aws.amazon.com/bedrock/latest/userguide/amazon-nova.html)
- [FastAPI](https://fastapi.tiangolo.com/)
- [AWS ECS Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)

## Autore

**Davide Padeletti** — [GitHub](https://github.com/dpadeletti)

---

Fatto con curiosità per esplorare semantic search e RAG con pgvector + AWS Bedrock.

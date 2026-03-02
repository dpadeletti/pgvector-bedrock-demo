# pgvector-bedrock-demo

Progetto demo di **semantic search** con pgvector su AWS RDS e embeddings generati con AWS Bedrock Titan V2.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![AWS](https://img.shields.io/badge/AWS-RDS%20%7C%20ECS%20%7C%20Bedrock-orange.svg)](https://aws.amazon.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-blue.svg)](https://github.com/dpadeletti/pgvector-bedrock-demo/actions)

## 🎯 Cosa fa questo progetto

Sistema completo di semantic search che:
- ✅ Salva embeddings vettoriali (1024 dimensioni) in PostgreSQL con pgvector
- ✅ Genera embeddings usando AWS Bedrock Titan Embeddings V2
- ✅ Ricerca documenti simili usando similarità coseno (operatore pgvector `<=>`)
- ✅ REST API con FastAPI deployata su AWS ECS Fargate
- ✅ CI/CD automatizzato con GitHub Actions (push → test → ECR → ECS)
- ✅ Secrets gestiti con AWS Secrets Manager

## 📋 Prerequisiti

- **Account AWS** con accesso a:
  - RDS (PostgreSQL 16+)
  - Bedrock (Titan Embeddings)
  - ECS Fargate + ECR
  - Secrets Manager
- **Python 3.11+**
- **AWS CLI** configurata con credenziali
- **Docker** (per build locale)

## 🏗️ Architettura

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
  │  Client  │ ────────► │   ALB (eu-north-1)          │
  └──────────┘           └──────────────┬──────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │   ECS Fargate                │
                         │   FastAPI + uvicorn :8000    │
                         └──────┬──────────────┬────────┘
                                │              │
                    ┌───────────▼──┐    ┌──────▼───────────┐
                    │  RDS         │    │  Bedrock          │
                    │ (pgvector)   │    │  Titan V2         │
                    └──────────────┘    └──────────────────┘
                         +
                    ┌──────────────┐
                    │  Secrets     │
                    │  Manager     │
                    │ (DB_PASSWORD)│
                    └──────────────┘
```

## 🚀 Quick Start (locale)

```bash
# 1. Clona il repository
git clone https://github.com/dpadeletti/pgvector-bedrock-demo.git
cd pgvector-bedrock-demo

# 2. Installa dipendenze Python
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Configura .env
cp .env.example .env
nano .env  # Inserisci endpoint RDS, password, region

# 4. Inizializza DB e inserisci dati di esempio
python init_db.py
python insert_data.py

# 5. Testa la ricerca
python search.py "machine learning"
```

## 🌍 API Live

L'API è deployata su AWS ECS Fargate:

```
Base URL: http://pgvector-alb-1618965750.eu-north-1.elb.amazonaws.com

GET  /          → Info API
GET  /health    → Health check (DB + Bedrock)
GET  /docs      → Swagger UI
GET  /stats     → Statistiche documenti
GET  /documents → Lista documenti (paginata)
POST /documents → Crea nuovo documento
POST /search    → Ricerca semantic
```

### Esempio ricerca

```bash
curl -X POST http://pgvector-alb-1618965750.eu-north-1.elb.amazonaws.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning", "limit": 3}'
```

## 🔄 CI/CD

Ogni push su `main` attiva automaticamente:

```
1. Test     → pytest (validation tests, no infra richiesta)
2. Build    → docker build + push su ECR
3. Deploy   → ECS force-new-deployment + wait stable
```

Per configurare su un nuovo repo:

```
GitHub → Settings → Secrets → Actions:
  AWS_ACCESS_KEY_ID     → IAM access key
  AWS_SECRET_ACCESS_KEY → IAM secret key
```

L'utente IAM deve avere: `AmazonECS_FullAccess` + `AmazonEC2ContainerRegistryPowerUser`.

## 📁 Struttura Progetto

```
pgvector-bedrock-demo/
├── README.md                        # Questa guida
├── Dockerfile                       # Build immagine (python:3.11-slim)
├── requirements.txt                 # Dipendenze Python
├── .env.example                     # Template configurazione locale
├── .gitignore
├── LICENSE
│
├── api.py                           # FastAPI app (endpoints REST)
├── config.py                        # Configurazione DB e AWS
├── embeddings.py                    # Client AWS Bedrock Titan V2
├── init_db.py                       # Crea tabelle + estensione pgvector
├── insert_data.py                   # Inserisce documenti di esempio
├── search.py                        # Ricerca similarity da CLI
│
├── tests/
│   ├── test_api.py                  # Test pytest automatici
│   ├── test_client.py               # Client Python interattivo
│   ├── manual_test.sh               # Test rapidi con curl
│   └── README.md                    # Guida test
│
└── .github/
    └── workflows/
        └── deploy.yml               # Pipeline CI/CD GitHub Actions
```

## 📝 Configurazione (.env)

```bash
# Database (RDS endpoint)
DB_HOST=pgvector-demo-db.xxxxx.eu-north-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=YourSecurePassword123   # Solo per uso locale

# AWS Bedrock
AWS_REGION=eu-north-1
AWS_BEDROCK_MODEL_ID=amazon.titan-embed-text-v2:0
```

> In produzione (ECS) `DB_PASSWORD` è gestita da **AWS Secrets Manager** e non è mai in chiaro nella task definition.

## 🔍 Come Funziona

### Flusso Dati

1. **Input**: Documento testuale
2. **Embedding**: Bedrock Titan V2 → vettore 1024 dimensioni
3. **Storage**: PostgreSQL + pgvector salva documento + embedding
4. **Query**: Testo query → embedding → ricerca similarità coseno con `<=>`
5. **Output**: Top-K documenti più simili (ordinati per score)

### Dettagli Tecnici

- **Embeddings**: Titan Text Embeddings V2 (1024 dim)
- **Database**: PostgreSQL 16.6 + pgvector 0.8.0
- **Similarità**: Coseno via operatore pgvector `<=>` (in-database)
- **Region AWS**: eu-north-1 (Stockholm)
- **ECS**: Fargate 256 CPU / 512 MB

## 🧪 Test

```bash
# Test automatici (non richiedono DB/Bedrock)
pytest tests/test_api.py -v -k "validation or test_root or test_docs"

# Test completi (richiede API running in locale)
uvicorn api:app --reload &
pytest tests/test_api.py -v

# Test manuali con curl
cd tests && ./manual_test.sh

# Client interattivo
python tests/test_client.py --interactive
```

## 💰 Costi AWS (Stima)

| Servizio | Tipo | Costo/mese | Free Tier |
|----------|------|------------|-----------|
| RDS PostgreSQL | db.t3.micro | ~$12 | ✅ 750 ore/mese (12 mesi) |
| ECS Fargate | 256 CPU / 512 MB | ~$5 | ❌ |
| ECR | Storage immagini | ~$0.50 | ❌ |
| Bedrock Titan | Embeddings | ~$0.10 | ❌ Pay per use |
| Secrets Manager | 1 secret | ~$0.40 | ❌ |
| ALB | Load Balancer | ~$16 | ❌ |

**Totale stimato**: ~$34/mese (senza free tier)  
**Con free tier attivo** (RDS + prime 750h): ~$22/mese

> Per ridurre i costi: stoppa RDS e scala ECS a 0 quando non usi il progetto.

```bash
# Stop risorse
aws rds stop-db-instance --db-instance-identifier pgvector-demo-db --region eu-north-1
aws ecs update-service --cluster pgvector-demo-cluster --service pgvector-demo-service --desired-count 0 --region eu-north-1

# Riavvia
aws rds start-db-instance --db-instance-identifier pgvector-demo-db --region eu-north-1
aws ecs update-service --cluster pgvector-demo-cluster --service pgvector-demo-service --desired-count 1 --region eu-north-1
```

## 🛠️ Troubleshooting

### Errore: `extension vector does not exist`
```bash
psql -h YOUR-RDS-ENDPOINT -U postgres -d postgres
CREATE EXTENSION IF NOT EXISTS vector;
```

### Errore: `Connection timed out` (RDS)
```bash
# Aggiungi il tuo IP al security group RDS
aws ec2 authorize-security-group-ingress \
    --group-id sg-029573f0998e11be5 \
    --protocol tcp --port 5432 \
    --cidr $(curl -s https://checkip.amazonaws.com)/32 \
    --region eu-north-1
```

### Errore: `password authentication failed`
```bash
# Verifica il secret in Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id pgvector-demo/db-password \
  --region eu-north-1 --query "SecretString"

# Aggiorna se necessario
aws secretsmanager put-secret-value \
  --secret-id pgvector-demo/db-password \
  --secret-string "NUOVA-PASSWORD" --region eu-north-1
```

### Errore: `Access denied` (Bedrock)
```
AWS Console → Bedrock → Model access → Richiedi accesso a: Amazon Titan Text Embeddings V2
```

### Errore: `expected 1536 dimensions, not 1024`
```bash
python init_db.py --reset  # Scrivi SI quando chiede conferma
```

## 📚 Risorse

- [pgvector](https://github.com/pgvector/pgvector)
- [AWS Bedrock Titan Embeddings](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)
- [FastAPI](https://fastapi.tiangolo.com/)
- [AWS ECS Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)

## 🤝 Contribuire

1. Fork il progetto
2. Crea un branch (`git checkout -b feature/AmazingFeature`)
3. Commit (`git commit -m 'Add AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Apri una Pull Request

## 📄 License

Distribuito sotto licenza MIT. Vedi [LICENSE](LICENSE) per dettagli.

## 👨‍💻 Autore

**Davide Padeletti** - [GitHub](https://github.com/dpadeletti)

---

**Fatto con ❤️ per esplorare semantic search con pgvector + AWS Bedrock**

⭐ Se ti è utile, lascia una stella su GitHub!

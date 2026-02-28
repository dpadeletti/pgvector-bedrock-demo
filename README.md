# pgvector-bedrock-demo

Progetto demo di **semantic search** con pgvector su AWS RDS e embeddings generati con AWS Bedrock Titan V2.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![AWS](https://img.shields.io/badge/AWS-RDS%20%7C%20Bedrock%20%7C%20EC2-orange.svg)](https://aws.amazon.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 🎯 Cosa fa questo progetto

Sistema completo di semantic search che:
- ✅ Salva embeddings vettoriali (1024 dimensioni) in PostgreSQL con pgvector
- ✅ Genera embeddings usando AWS Bedrock Titan Embeddings V2
- ✅ Ricerca documenti simili usando similarità coseno
- ✅ Deploy automatizzato su AWS (RDS + EC2)
- ✅ Script pronti per setup completo in < 15 minuti

## 📋 Prerequisiti

- **Account AWS** con accesso a:
  - RDS (PostgreSQL 16+)
  - Bedrock (Titan Embeddings)
  - EC2 (opzionale, per deployment)
- **Python 3.11+** (o 3.12)
- **AWS CLI** configurata con credenziali
- **Credito free tier AWS** (consigliato per testing)

## 🚀 Quick Start (3 opzioni)

### ✅ Opzione 1: Setup Automatico Completo (Consigliato)

```bash
# 1. Clona il repository
git clone https://github.com/dpadeletti/pgvector-bedrock-demo.git
cd pgvector-bedrock-demo

# 2. Crea RDS PostgreSQL (7-10 minuti)
chmod +x setup_rds.sh
./setup_rds.sh

# 3. Installa dipendenze Python
python3.11 -m venv venv
source venv/bin/activate  # Su Windows: venv\Scripts\activate
pip install -r requirements.txt

# 4. Configura .env con l'endpoint RDS che ti ha dato lo script
cp .env.example .env
nano .env  # Inserisci endpoint, password, region

# 5. Inizializza e testa
python init_db.py
python insert_data.py
python search.py "machine learning"
```

### 🌍 Opzione 2: Deploy su EC2

```bash
# 1. Crea istanza EC2 (2-3 minuti)
chmod +x create_ec2.sh
./create_ec2.sh

# 2. SSH nell'istanza
ssh -i pgvector-demo-key.pem ubuntu@<IP-PUBBLICO>

# 3. Setup su EC2
git clone https://github.com/dpadeletti/pgvector-bedrock-demo.git
cd pgvector-bedrock-demo
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Configura .env e testa
cp .env.example .env
nano .env
python search.py "machine learning"
```

### 🔧 Opzione 3: Setup Manuale

Vedi le guide dettagliate:
- **[Setup RDS](EC2_DEPLOYMENT.md#step-1-crea-rds-postgresql)**
- **[Deploy EC2](EC2_DEPLOYMENT.md)**

## 📁 Struttura Progetto

```
pgvector-bedrock-demo/
├── README.md              # Questa guida
├── EC2_DEPLOYMENT.md      # Guida deployment EC2 completa
├── GITHUB_SETUP.md        # Guida push su GitHub
├── requirements.txt       # Dipendenze Python
├── setup.sql             # Script SQL inizializzazione
├── .env.example          # Template configurazione
├── .gitignore            # File da ignorare
├── LICENSE               # Licenza MIT
│
├── config.py             # Configurazione DB e AWS
├── embeddings.py         # Client AWS Bedrock
├── init_db.py            # Crea tabelle + pgvector
├── insert_data.py        # Inserisce documenti di esempio
├── search.py             # Ricerca similarity (numpy)
├── check_aws_setup.py    # Verifica setup AWS
│
├── setup_rds.sh          # Script automatico RDS
└── create_ec2.sh         # Script automatico EC2
```

## 🔍 Come Funziona

### Architettura

```
┌─────────────┐
│   Python    │
│   (locale   │
│   o EC2)    │
└──────┬──────┘
       │
       ├──────────────┐
       │              │
       ▼              ▼
  ┌─────────┐   ┌──────────┐
  │   RDS   │   │ Bedrock  │
  │(pgvector)│  │ (Titan)  │
  └─────────┘   └──────────┘
  eu-north-1    eu-north-1
```

### Flusso Dati

1. **Input**: Documento testuale (es: "Il machine learning...")
2. **Embedding**: Bedrock Titan V2 → vettore 1024 dimensioni
3. **Storage**: PostgreSQL + pgvector salva documento + embedding
4. **Query**: Testo query → embedding → ricerca similarità coseno
5. **Output**: Top-K documenti più simili (ordinati per score)

### Dettagli Tecnici

- **Embeddings**: Titan Text Embeddings V2 (1024 dim)
- **Database**: PostgreSQL 16.6 con estensione pgvector 0.8.0
- **Similarità**: Coseno (calcolata in Python con numpy)
- **Region AWS**: eu-north-1 (Stockholm)
- **Instance Classes**: db.t3.micro (RDS), t3.micro (EC2)

## 📝 Configurazione (.env)

```bash
# Database (RDS endpoint)
DB_HOST=pgvector-demo-db.xxxxx.eu-north-1.rds.amazonaws.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=YourSecurePassword123

# AWS Bedrock
AWS_REGION=eu-north-1
AWS_BEDROCK_MODEL_ID=amazon.titan-embed-text-v2:0
```

## 🧪 Esempi di Utilizzo

### Ricerca Interattiva

```bash
python search.py --interactive

Query: machine learning
# Output:
# 1. [ID: 2] Similarita: 0.601
#    Il machine learning è un sottoinsieme dell'intelligenza artificiale...
# 2. [ID: 4] Similarita: 0.324
#    Python è uno dei linguaggi più popolari per ML...
```

### Da Codice Python

```python
from embeddings import get_embedding
from config import get_db_connection
import numpy as np

# Genera embedding
text = "L'intelligenza artificiale è affascinante"
vector = get_embedding(text)  # 1024 dimensioni

# Inserisci nel database
conn = get_db_connection()
cur = conn.cursor()
cur.execute(
    "INSERT INTO documents (content, embedding) VALUES (%s, %s)",
    (text, vector)
)
conn.commit()

# Ricerca similarity
from search import search
results = search("AI e machine learning", top_k=5)

# Output: [(id, content, similarity, metadata), ...]
for doc_id, content, sim, meta in results:
    print(f"[{sim:.3f}] {content[:80]}")
```

### Inserimento Custom

```bash
# Aggiungi singoli documenti
python insert_data.py --custom "Il tuo testo qui"

# Batch di 10 documenti di esempio (IT/ML topics)
python insert_data.py
```

## 💰 Costi AWS (Stima)

| Servizio | Tipo | Costo/mese | Free Tier |
|----------|------|------------|-----------|
| RDS PostgreSQL | db.t3.micro | ~$12 | ✅ 750 ore/mese (12 mesi) |
| EC2 | t3.micro | ~$8 | ✅ 750 ore/mese (12 mesi) |
| Bedrock Titan | Embeddings | ~$0.10 | ❌ Pay per use |
| Storage | 20GB | ~$2 | Incluso |

**Totale per testing**: < $1/mese con free tier attivo  
**Totale senza free tier**: ~$22/mese

## 🛠️ Troubleshooting

### Errore: `extension vector does not exist`
```bash
# Soluzione: Installa pgvector
psql -h YOUR-RDS-ENDPOINT -U postgres -d postgres
CREATE EXTENSION IF NOT EXISTS vector;
```

### Errore: `Connection timed out` (RDS)
```bash
# Problema: Security group non permette connessioni
# Soluzione: Aggiungi il tuo IP al security group RDS
aws ec2 authorize-security-group-ingress \
    --group-id sg-XXXXX \
    --protocol tcp \
    --port 5432 \
    --cidr $(curl -s https://checkip.amazonaws.com)/32 \
    --region eu-north-1
```

### Errore: `InvalidParameterCombination` (versione PostgreSQL)
```bash
# Problema: Versione non disponibile in eu-north-1
# Soluzione: Usa versione disponibile
aws rds describe-db-engine-versions \
    --engine postgres \
    --region eu-north-1 \
    --query "DBEngineVersions[].EngineVersion"
# Usa una versione dall'output (es: 16.6)
```

### Errore: `Access denied` (Bedrock)
```bash
# Problema: Modello non abilitato
# Soluzione: Vai su AWS Console → Bedrock → Model access
# Richiedi accesso a: Amazon Titan Text Embeddings V2
```

### Errore: `expected 1536 dimensions, not 1024`
```bash
# Problema: Tabella creata per Titan V1 (1536 dim)
# Soluzione: Ricrea con dimensioni corrette
python init_db.py --reset  # Scrivi SI quando chiede conferma
```

## 📚 Risorse e Link

- **Documentazione**:
  - [pgvector](https://github.com/pgvector/pgvector) - Extension PostgreSQL per vector similarity
  - [AWS Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html) - Titan Embeddings
  - [RDS PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/postgresql-extensions.html) - Extension support

- **Guide Interne**:
  - [EC2_DEPLOYMENT.md](EC2_DEPLOYMENT.md) - Deployment completo
  - [GITHUB_SETUP.md](GITHUB_SETUP.md) - Push su GitHub

## 🚀 Next Steps

Questo progetto è un'ottima base per:

1. **Aggiungere più documenti** (scale to 1000+)
2. **Creare API REST** (FastAPI + Uvicorn)
3. **Containerizzare** (Docker + Docker Compose)
4. **Setup CI/CD** (GitHub Actions)
5. **Ottimizzare search** (usare pgvector `<=>` invece di numpy)
6. **Aggiungere UI** (Streamlit o React)

## 🤝 Contribuire

Contribuzioni benvenute! 

1. Fork il progetto
2. Crea un branch (`git checkout -b feature/AmazingFeature`)
3. Commit (`git commit -m 'Add AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Apri una Pull Request

## 📄 License

Distribuito sotto licenza MIT. Vedi [LICENSE](LICENSE) per dettagli.

## 🐛 Issues

Usa [GitHub Issues](https://github.com/dpadeletti/pgvector-bedrock-demo/issues) per:
- 🐛 Bug reports
- 💡 Feature requests
- 📖 Domande e supporto

## 👨‍💻 Autore

**Davide Padeletti** - [GitHub](https://github.com/dpadeletti)

---

**Fatto con ❤️ per esplorare semantic search con pgvector + AWS Bedrock**

⭐ Se ti è utile, lascia una stella su GitHub!
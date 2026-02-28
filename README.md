# pgvector-bedrock-demo

Progetto demo per testare **semantic search** con pgvector su AWS RDS e embeddings generati con AWS Bedrock Titan.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![AWS](https://img.shields.io/badge/AWS-RDS%20%7C%20Bedrock-orange.svg)](https://aws.amazon.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📋 Prerequisiti

- Account AWS con accesso a:
  - RDS (PostgreSQL)
  - Bedrock (modello Titan Embeddings)
- Python 3.8+
- AWS CLI configurata con credenziali

## 🚀 Setup Rapido

### Opzione A: Sviluppo Locale

1. **Crea RDS PostgreSQL** su AWS (db.t3.micro per free tier)
2. **Attiva Bedrock** e richiedi accesso a Titan Embeddings
3. **Copia `.env.example` → `.env`** e inserisci le tue credenziali
4. **Installa**: `pip install -r requirements.txt`
5. **Setup DB**: `python init_db.py`
6. **Test rapido**: `python quick_test.py`
7. **Inserisci dati**: `python insert_data.py`
8. **Ricerca**: `python search.py --interactive`

### Opzione B: Deployment su EC2

Per deployare su istanza EC2, segui la guida completa: **[EC2_DEPLOYMENT.md](EC2_DEPLOYMENT.md)**

**Quick start EC2:**
```bash
# Su EC2, esegui:
curl -O https://raw.githubusercontent.com/TUO-USERNAME/pgvector-bedrock-demo/main/setup_ec2.sh
chmod +x setup_ec2.sh
./setup_ec2.sh
```

### Verifica Setup AWS

Prima di iniziare, verifica cosa hai già configurato:

```bash
python check_aws_setup.py
```

Questo script controlla:
- ✅ Credenziali AWS configurate
- ✅ Istanze RDS PostgreSQL
- ✅ Accesso a Bedrock e Titan Embeddings
- ✅ Istanze EC2 (se presenti)

```bash
# Via AWS Console:
# - Engine: PostgreSQL 15+
# - Template: Free tier (per test) o Production
# - DB instance identifier: pgvector-test
# - Master username: postgres
# - Master password: [scegli una password]
# - Public access: Yes (per test locale)
# - Security group: consenti connessioni sulla porta 5432 dal tuo IP
```

Oppure via AWS CLI:

```bash
aws rds create-db-instance \
    --db-instance-identifier pgvector-test \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --master-username postgres \
    --master-password TuaPasswordSicura123 \
    --allocated-storage 20 \
    --publicly-accessible \
    --backup-retention-period 0
```

### 2. Attiva pgvector su RDS

Una volta creata l'istanza, connettiti e installa l'estensione:

```bash
# Ottieni l'endpoint RDS dalla console AWS
psql -h tuo-endpoint.rds.amazonaws.com -U postgres -d postgres

# Nel prompt psql, esegui:
CREATE EXTENSION IF NOT EXISTS vector;
```

Oppure usa lo script SQL fornito:

```bash
psql -h tuo-endpoint.rds.amazonaws.com -U postgres -d postgres -f setup.sql
```

### 3. Configura AWS Bedrock

Assicurati di avere accesso al modello Titan Embeddings:

```bash
# Nella console AWS Bedrock, vai su "Model access"
# Richiedi accesso a: Amazon Titan Embeddings G1 - Text
```

### 4. Installa dipendenze Python

```bash
pip install -r requirements.txt
```

### 5. Configura variabili d'ambiente

Crea un file `.env`:

```bash
# Database
DB_HOST=tuo-endpoint.rds.amazonaws.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=TuaPasswordSicura123

# AWS
AWS_REGION=us-east-1
AWS_BEDROCK_MODEL_ID=amazon.titan-embed-text-v1
```

### 6. Esegui il progetto

```bash
# Inizializza il database
python init_db.py

# Inserisci documenti di esempio con embeddings
python insert_data.py

# Esegui query di similarity search
python search.py "come funziona il machine learning?"
```

## 📁 Struttura Progetto

```
.
├── README.md              # Questa guida
├── requirements.txt       # Dipendenze Python
├── setup.sql             # Script inizializzazione DB
├── config.py             # Configurazione
├── embeddings.py         # Generazione embeddings con Bedrock
├── init_db.py            # Crea tabelle
├── insert_data.py        # Inserisce dati di esempio
└── search.py             # Ricerca similarity
```

## 🔍 Come Funziona

1. **Embeddings**: I testi vengono convertiti in vettori (1536 dimensioni) usando AWS Bedrock Titan
2. **Storage**: I vettori vengono salvati in PostgreSQL con l'estensione pgvector
3. **Search**: Le query usano la similarità del coseno per trovare i documenti più rilevanti

## 💰 Costi Stimati (per test)

- **RDS db.t3.micro**: ~$0.017/ora (~$12/mese, free tier 750 ore/mese)
- **Bedrock Titan Embeddings**: ~$0.0001 per 1000 token input
- **Storage RDS**: minimo per test (<$1)

**Totale per testing**: < $5/mese se usi free tier

## 🧪 Esempio di Utilizzo

```python
from embeddings import get_embedding
from config import get_db_connection

# Genera embedding
text = "L'intelligenza artificiale è affascinante"
vector = get_embedding(text)

# Inserisci nel database
conn = get_db_connection()
cur = conn.cursor()
cur.execute(
    "INSERT INTO documents (content, embedding) VALUES (%s, %s)",
    (text, vector)
)
conn.commit()

# Cerca documenti simili
query_vector = get_embedding("AI e machine learning")
cur.execute(
    """
    SELECT content, 1 - (embedding <=> %s::vector) as similarity
    FROM documents
    ORDER BY embedding <=> %s::vector
    LIMIT 5
    """,
    (query_vector, query_vector)
)
results = cur.fetchall()
for content, similarity in results:
    print(f"{similarity:.3f} - {content}")
```

## 🛠️ Troubleshooting

**Errore: "extension vector does not exist"**
- Soluzione: Esegui `CREATE EXTENSION vector;` nel database

**Errore: "connection refused"**
- Soluzione: Verifica security group RDS e che public access sia abilitato

**Errore: "access denied" su Bedrock**
- Soluzione: Richiedi accesso al modello nella console Bedrock

## 📚 Risorse

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [AWS Bedrock Embeddings](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)
- [pgvector su RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/postgresql-extensions.html)

## 🤝 Contribuire

Contribuzioni benvenute! 

1. Fork il progetto
2. Crea un branch (`git checkout -b feature/AmazingFeature`)
3. Commit le modifiche (`git commit -m 'Add AmazingFeature'`)
4. Push al branch (`git push origin feature/AmazingFeature`)
5. Apri una Pull Request

## 📄 License

Distribuito sotto licenza MIT. Vedi `LICENSE` per maggiori informazioni.

## 🐛 Bug Reports & Feature Requests

Usa GitHub Issues per segnalare bug o richiedere nuove feature.

## 📞 Contatti

Per domande o supporto, apri una issue su GitHub.

---

**Fatto con ❤️ per testare pgvector + AWS Bedrock**

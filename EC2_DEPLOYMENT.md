# 🚀 Deployment su EC2 - pgvector-bedrock-demo

Guida completa per deployare il progetto su un'istanza EC2.

## 📋 Prerequisiti

- Account AWS con crediti attivi
- AWS CLI configurato localmente
- Istanza RDS PostgreSQL già creata e configurata
- Accesso a Bedrock (Titan Embeddings)

## 🎯 Architettura

```
Internet
    │
    ▼
┌─────────────────┐
│  EC2 Instance   │
│  Ubuntu/Amazon  │
│  Linux          │
│                 │
│  Python App     │
└────┬────────┬───┘
     │        │
     │        └──────────┐
     ▼                   ▼
┌─────────┐         ┌──────────┐
│   RDS   │         │ Bedrock  │
│(pgvector)│         │ (Titan)  │
└─────────┘         └──────────┘
```

## 📝 Step 1: Crea istanza EC2

### Via AWS Console:

1. **EC2 Dashboard** → Launch Instance
2. **Configurazione:**
   - Name: `pgvector-demo-server`
   - AMI: Ubuntu Server 24.04 LTS (o Amazon Linux 2023)
   - Instance type: `t2.micro` (free tier) o `t3.small`
   - Key pair: Crea o usa esistente (scarica il .pem!)
   - Security Group:
     - SSH (22) dal tuo IP
     - HTTP (80) ovunque (opzionale per API)
     - HTTPS (443) ovunque (opzionale)
   - Storage: 20 GB gp3

3. **Launch instance**

### Via AWS CLI:

```bash
# Crea security group
aws ec2 create-security-group \
    --group-name pgvector-demo-sg \
    --description "Security group for pgvector demo"

# Ottieni il tuo IP
MY_IP=$(curl -s https://checkip.amazonaws.com)

# Aggiungi regola SSH
aws ec2 authorize-security-group-ingress \
    --group-name pgvector-demo-sg \
    --protocol tcp \
    --port 22 \
    --cidr $MY_IP/32

# Crea key pair
aws ec2 create-key-pair \
    --key-name pgvector-demo-key \
    --query 'KeyMaterial' \
    --output text > pgvector-demo-key.pem

chmod 400 pgvector-demo-key.pem

# Lancia istanza
aws ec2 run-instances \
    --image-id ami-0c7217cdde317cfec \
    --instance-type t2.micro \
    --key-name pgvector-demo-key \
    --security-groups pgvector-demo-sg \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=pgvector-demo-server}]'
```

## 📝 Step 2: Configura IAM Role per EC2

L'istanza EC2 deve poter accedere a Bedrock e RDS.

### Via Console:

1. **IAM** → Roles → Create role
2. **Trusted entity**: AWS service → EC2
3. **Permissions**: Aggiungi policy:
   - `AmazonBedrockFullAccess` (o custom limitata)
   - `AmazonRDSFullAccess` (o custom limitata)
4. Nome role: `pgvector-demo-ec2-role`
5. **EC2** → Seleziona istanza → Actions → Security → Modify IAM role
6. Seleziona `pgvector-demo-ec2-role`

### Policy Custom (più sicura):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:ListFoundationModels"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "rds:DescribeDBInstances"
      ],
      "Resource": "*"
    }
  ]
}
```

## 📝 Step 3: Connettiti e setup EC2

```bash
# Ottieni IP pubblico dell'istanza
aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=pgvector-demo-server" \
    --query "Reservations[0].Instances[0].PublicIpAddress" \
    --output text

# Connettiti
ssh -i pgvector-demo-key.pem ubuntu@<IP-PUBBLICO>
```

Una volta connesso, esegui lo script di setup automatico:

```bash
# Scarica lo script di setup
curl -O https://raw.githubusercontent.com/TUO-USERNAME/pgvector-bedrock-demo/main/setup_ec2.sh

# Rendilo eseguibile
chmod +x setup_ec2.sh

# Esegui
./setup_ec2.sh
```

**Oppure setup manuale** (vedi sotto).

## 📝 Step 4: Setup Manuale EC2

```bash
# Aggiorna sistema
sudo apt update && sudo apt upgrade -y

# Installa Python 3.11+
sudo apt install -y python3.11 python3.11-venv python3-pip

# Installa PostgreSQL client
sudo apt install -y postgresql-client

# Installa git
sudo apt install -y git

# Clona repository
git clone https://github.com/TUO-USERNAME/pgvector-bedrock-demo.git
cd pgvector-bedrock-demo

# Crea virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Installa dipendenze
pip install -r requirements.txt

# Configura .env
cp .env.example .env
nano .env  # Modifica con i tuoi valori
```

## 📝 Step 5: Configura .env su EC2

```bash
nano .env
```

Inserisci:

```bash
# Database (RDS endpoint)
DB_HOST=tuo-rds-endpoint.rds.amazonaws.com
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=tua-password-sicura

# AWS (usa la region dell'istanza)
AWS_REGION=us-east-1
AWS_BEDROCK_MODEL_ID=amazon.titan-embed-text-v1
```

**Nota**: Non serve specificare credenziali AWS perché l'EC2 usa l'IAM role!

## 📝 Step 6: Inizializza Database

```bash
# Test connessione
python3 config.py

# Inizializza database
python3 init_db.py

# Inserisci dati di esempio
python3 insert_data.py

# Test ricerca
python3 search.py "machine learning"
```

## 📝 Step 7: Esegui come Servizio (Opzionale)

Se vuoi creare un'API o servizio sempre attivo:

```bash
# Crea file servizio systemd
sudo nano /etc/systemd/system/pgvector-demo.service
```

Contenuto:

```ini
[Unit]
Description=pgvector Bedrock Demo Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/pgvector-bedrock-demo
Environment="PATH=/home/ubuntu/pgvector-bedrock-demo/venv/bin"
ExecStart=/home/ubuntu/pgvector-bedrock-demo/venv/bin/python3 search.py --interactive

Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
# Abilita e avvia servizio
sudo systemctl daemon-reload
sudo systemctl enable pgvector-demo
sudo systemctl start pgvector-demo

# Check status
sudo systemctl status pgvector-demo

# Logs
sudo journalctl -u pgvector-demo -f
```

## 🔒 Security Best Practices

1. **Security Group**: Limita SSH solo al tuo IP
2. **RDS**: Non esporre pubblicamente (usa VPC)
3. **IAM**: Usa policy minime necessarie
4. **Secrets**: Mai committare .env su GitHub
5. **Updates**: Mantieni sistema aggiornato

```bash
# Setup automatico aggiornamenti
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

## 💰 Costi Stimati

- **EC2 t2.micro**: Free tier (750h/mese) o ~$8/mese
- **RDS db.t3.micro**: Free tier (750h/mese) o ~$12/mese
- **Bedrock**: ~$0.0001 per 1000 token
- **Storage/Traffic**: Minimo

**Totale**: Free tier per 12 mesi, poi ~$20/mese

## 🐛 Troubleshooting

### EC2 non si connette a RDS
```bash
# Verifica security group RDS
# Deve permettere connessioni dalla security group EC2 sulla porta 5432
```

### Errore Bedrock "Access Denied"
```bash
# Verifica IAM role EC2
aws sts get-caller-identity  # Deve mostrare il role
```

### Python import error
```bash
# Assicurati di attivare venv
source venv/bin/activate
pip install -r requirements.txt
```

## 📚 Comandi Utili

```bash
# Monitora risorse
htop

# Spazio disco
df -h

# Logs sistema
journalctl -f

# Connessione RDS da EC2
psql -h YOUR-RDS-ENDPOINT -U postgres -d postgres
```

## 🎉 Next Steps

Una volta funzionante:
- [ ] Crea API REST (FastAPI/Flask)
- [ ] Aggiungi autenticazione
- [ ] Setup NGINX come reverse proxy
- [ ] Configura SSL con Let's Encrypt
- [ ] Setup CI/CD con GitHub Actions

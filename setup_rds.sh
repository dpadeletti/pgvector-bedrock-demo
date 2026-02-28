#!/bin/bash
#
# Setup automatico RDS PostgreSQL per pgvector-bedrock-demo
# Crea un'istanza db.t3.micro (free tier eligible) con pgvector
#

set -e

echo "=================================="
echo "🗄️  RDS PostgreSQL Setup"
echo "=================================="
echo ""

# Configurazione
DB_INSTANCE_ID="pgvector-demo-db"
DB_NAME="postgres"
DB_USER="postgres"
DB_ENGINE="postgres"
DB_ENGINE_VERSION="16.3"  # Supporta pgvector
ALLOCATED_STORAGE=20  # GB minimo
REGION="eu-north-1"  # Stockholm

# Chiedi password
read -sp "🔐 Scegli una password per il database (min 8 caratteri): " DB_PASSWORD
echo ""
echo ""

if [ ${#DB_PASSWORD} -lt 8 ]; then
    echo "❌ Password troppo corta (minimo 8 caratteri)"
    exit 1
fi

# Ottieni IP pubblico per security group
echo "🌍 Ottengo il tuo IP pubblico..."
MY_IP=$(curl -s https://checkip.amazonaws.com)
echo "   Il tuo IP: $MY_IP"
echo ""

# Crea security group
echo "🔒 Creo security group per RDS..."
SG_ID=$(aws ec2 create-security-group \
    --group-name pgvector-demo-db-sg \
    --description "Security group for pgvector demo database" \
    --region $REGION \
    --output text \
    --query 'GroupId' 2>/dev/null || \
    aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=pgvector-demo-db-sg" \
        --region $REGION \
        --query 'SecurityGroups[0].GroupId' \
        --output text)

echo "   Security Group ID: $SG_ID"

# Aggiungi regola PostgreSQL dal tuo IP
echo "🔓 Configuro accesso PostgreSQL dal tuo IP..."
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 5432 \
    --cidr $MY_IP/32 \
    --region $REGION 2>/dev/null || echo "   (Regola già esistente)"

echo ""
echo "🚀 Creo istanza RDS PostgreSQL..."
echo "   Questo può richiedere 5-10 minuti..."
echo ""

# Crea istanza RDS
aws rds create-db-instance \
    --db-instance-identifier $DB_INSTANCE_ID \
    --db-instance-class $DB_INSTANCE_CLASS \
    --engine $DB_ENGINE \
    --engine-version $DB_ENGINE_VERSION \
    --master-username $DB_USER \
    --master-user-password "$DB_PASSWORD" \
    --allocated-storage $ALLOCATED_STORAGE \
    --vpc-security-group-ids $SG_ID \
    --publicly-accessible \
    --backup-retention-period 0 \
    --no-multi-az \
    --region $REGION \
    --tags Key=Project,Value=pgvector-demo

echo "✅ Istanza RDS in creazione!"
echo ""
echo "⏳ Attendo che l'istanza sia disponibile..."
echo "   (questo può richiedere 5-10 minuti, puoi interrompere con Ctrl+C e controllare dopo)"
echo ""

# Attendi che sia disponibile
aws rds wait db-instance-available \
    --db-instance-identifier $DB_INSTANCE_ID \
    --region $REGION

# Ottieni endpoint
ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier $DB_INSTANCE_ID \
    --region $REGION \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text)

echo ""
echo "=================================="
echo "✅ RDS PostgreSQL PRONTO!"
echo "=================================="
echo ""
echo "📝 Informazioni connessione:"
echo ""
echo "   Endpoint: $ENDPOINT"
echo "   Port: 5432"
echo "   Database: $DB_NAME"
echo "   Username: $DB_USER"
echo "   Password: [quella che hai scelto]"
echo ""
echo "=================================="
echo ""
echo "📋 Prossimi passi:"
echo ""
echo "1. Aggiorna il file .env con queste credenziali:"
echo ""
echo "   DB_HOST=$ENDPOINT"
echo "   DB_PORT=5432"
echo "   DB_NAME=$DB_NAME"
echo "   DB_USER=$DB_USER"
echo "   DB_PASSWORD=tua-password"
echo ""
echo "2. Installa l'estensione pgvector:"
echo ""
echo "   python init_db.py"
echo ""
echo "3. Test connessione:"
echo ""
echo "   python config.py"
echo ""
echo "=================================="
echo ""
echo "💰 Costi: db.t3.micro è free tier (750 ore/mese gratis per 12 mesi)"
echo ""
echo "🗑️  Per eliminare l'istanza quando hai finito:"
echo "   aws rds delete-db-instance --db-instance-identifier $DB_INSTANCE_ID --skip-final-snapshot --region $REGION"
echo ""
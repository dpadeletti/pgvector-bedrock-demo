#!/bin/bash
#
# Setup automatico per EC2 - pgvector-bedrock-demo
# Esegui su Ubuntu 24.04 LTS o Amazon Linux 2023
#

set -e  # Exit on error

echo "=================================="
echo "🚀 pgvector-bedrock-demo Setup"
echo "=================================="
echo ""

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "❌ Cannot detect OS"
    exit 1
fi

echo "📍 OS rilevato: $OS"
echo ""

# Update system
echo "📦 Aggiornamento sistema..."
if [ "$OS" = "ubuntu" ]; then
    sudo apt update && sudo apt upgrade -y
elif [ "$OS" = "amzn" ]; then
    sudo yum update -y
fi

# Install Python 3.11+
echo ""
echo "🐍 Installazione Python..."
if [ "$OS" = "ubuntu" ]; then
    sudo apt install -y python3.11 python3.11-venv python3-pip
    PYTHON_CMD=python3.11
elif [ "$OS" = "amzn" ]; then
    sudo yum install -y python3.11 python3-pip
    PYTHON_CMD=python3.11
else
    PYTHON_CMD=python3
fi

# Install PostgreSQL client
echo ""
echo "🗄️  Installazione PostgreSQL client..."
if [ "$OS" = "ubuntu" ]; then
    sudo apt install -y postgresql-client
elif [ "$OS" = "amzn" ]; then
    sudo yum install -y postgresql15
fi

# Install Git
echo ""
echo "📂 Installazione Git..."
if [ "$OS" = "ubuntu" ]; then
    sudo apt install -y git
elif [ "$OS" = "amzn" ]; then
    sudo yum install -y git
fi

# Clone repository
echo ""
echo "📥 Clonazione repository..."
if [ ! -d "pgvector-bedrock-demo" ]; then
    read -p "Inserisci URL repository GitHub (es: https://github.com/username/pgvector-bedrock-demo.git): " REPO_URL
    git clone "$REPO_URL"
    cd pgvector-bedrock-demo
else
    echo "   ⚠️  Directory già esistente, uso quella"
    cd pgvector-bedrock-demo
    git pull
fi

# Create virtual environment
echo ""
echo "🔧 Creazione virtual environment..."
$PYTHON_CMD -m venv venv

# Activate venv
source venv/bin/activate

# Install dependencies
echo ""
echo "📚 Installazione dipendenze Python..."
pip install --upgrade pip
pip install -r requirements.txt

# Configure .env
echo ""
echo "⚙️  Configurazione .env..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "   ✅ File .env creato da template"
    echo ""
    echo "   ⚠️  IMPORTANTE: Configura .env con i tuoi valori!"
    echo "   Esegui: nano .env"
    echo ""
    read -p "Vuoi configurare .env ora? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        nano .env
    fi
else
    echo "   ⚠️  .env già esistente, non sovrascritto"
fi

# Test setup
echo ""
echo "🧪 Test configurazione..."
python3 check_aws_setup.py

echo ""
echo "=================================="
echo "✅ Setup completato!"
echo "=================================="
echo ""
echo "📝 Prossimi passi:"
echo ""
echo "1. Configura .env se non l'hai fatto:"
echo "   nano .env"
echo ""
echo "2. Attiva virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "3. Test connessione database:"
echo "   python3 config.py"
echo ""
echo "4. Inizializza database:"
echo "   python3 init_db.py"
echo ""
echo "5. Inserisci dati di esempio:"
echo "   python3 insert_data.py"
echo ""
echo "6. Esegui ricerca:"
echo "   python3 search.py --interactive"
echo ""
echo "=================================="

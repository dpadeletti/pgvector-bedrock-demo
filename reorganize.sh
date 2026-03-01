#!/bin/bash
# Script per riorganizzare la struttura del progetto

echo "=========================================="
echo "📁 Riorganizzazione Progetto KISS"
echo "=========================================="
echo ""

# Crea le cartelle
echo "📂 Creazione cartelle..."
mkdir -p scripts
mkdir -p deployment

# Sposta file in scripts/
echo "📦 Spostamento script..."
mv insert_data.py scripts/ 2>/dev/null || echo "   insert_data.py già spostato o non presente"
mv load_wikipedia.py scripts/ 2>/dev/null || echo "   load_wikipedia.py già spostato o non presente"
mv check_aws_setup.py scripts/ 2>/dev/null || echo "   check_aws_setup.py già spostato o non presente"
mv quick_test.py scripts/ 2>/dev/null || echo "   quick_test.py già spostato o non presente"

# Sposta file in deployment/
echo "🚀 Spostamento deployment scripts..."
mv setup_rds.sh deployment/ 2>/dev/null || echo "   setup_rds.sh già spostato o non presente"
mv create_ec2.sh deployment/ 2>/dev/null || echo "   create_ec2.sh già spostato o non presente"
mv setup_ec2.sh deployment/ 2>/dev/null || echo "   setup_ec2.sh già spostato o non presente"

# File da tenere nella root
echo ""
echo "✅ Struttura finale:"
echo ""
echo "pgvector-bedrock-demo/"
echo "├── api.py                  # FastAPI app"
echo "├── config.py               # Configurazione"
echo "├── embeddings.py           # Bedrock client"
echo "├── init_db.py              # Setup database"
echo "├── search.py               # CLI search tool"
echo "├── scripts/"
echo "│   ├── insert_data.py"
echo "│   ├── load_wikipedia.py"
echo "│   ├── check_aws_setup.py"
echo "│   └── quick_test.py"
echo "└── deployment/"
echo "    ├── setup_rds.sh"
echo "    ├── create_ec2.sh"
echo "    └── setup_ec2.sh"
echo ""
echo "✅ Riorganizzazione completata!"
echo ""
echo "📝 Prossimi passi:"
echo "1. pip install fastapi uvicorn  # O usa requirements.txt"
echo "2. uvicorn api:app --reload     # Avvia l'API"
echo "3. Apri http://localhost:8000/docs  # Swagger UI"
echo ""

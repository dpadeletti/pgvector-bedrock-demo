"""
Configurazione del progetto pgvector + Bedrock
"""
import os
from dotenv import load_dotenv
import psycopg2
from pgvector.psycopg2 import register_vector

# Carica variabili d'ambiente da .env
load_dotenv()

# Configurazione Database
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'postgres'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

# Configurazione AWS Bedrock
AWS_REGION = os.getenv('AWS_REGION', 'eu-north-1')
BEDROCK_MODEL_ID = os.getenv('AWS_BEDROCK_MODEL_ID', 'amazon.titan-embed-text-v2:0')

# Dimensioni vettore (Titan V2 = 1024)
EMBEDDING_DIMENSION = 1024


def get_db_connection():
    """
    Crea connessione al database PostgreSQL con supporto pgvector
    
    Returns:
        psycopg2.connection: Connessione al database
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        # Registra il tipo vettore per pgvector
        register_vector(conn)
        return conn
    except Exception as e:
        print(f"❌ Errore connessione database: {e}")
        print(f"   Verifica che RDS sia attivo e accessibile")
        print(f"   Endpoint: {DB_CONFIG['host']}")
        raise


def test_connection():
    """
    Testa la connessione al database
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verifica estensione pgvector
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        result = cur.fetchone()
        
        if result:
            print(f"✅ Connessione OK - pgvector versione: {result[0]}")
        else:
            print("⚠️  pgvector non installato. Esegui setup.sql")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Test connessione fallito: {e}")
        return False


if __name__ == "__main__":
    print("🔍 Test configurazione...")
    print(f"📍 Database: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    print(f"🌍 AWS Region: {AWS_REGION}")
    print(f"🤖 Bedrock Model: {BEDROCK_MODEL_ID}")
    print()
    test_connection()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Carica articoli Wikipedia e li indicizza nel database
"""
import requests
import json
import time
from config import get_db_connection
from embeddings import get_embedding

# Topic da scaricare (in inglese per più contenuto)
WIKIPEDIA_TOPICS = [
    "Machine learning",
    "Artificial intelligence",
    "Deep learning",
    "Neural network",
    "Natural language processing",
    "Computer vision",
    "Reinforcement learning",
    "Supervised learning",
    "Unsupervised learning",
    "Convolutional neural network",
    "Recurrent neural network",
    "Transformer (machine learning)",
    "BERT (language model)",
    "GPT-3",
    "Large language model",
    "Python (programming language)",
    "PostgreSQL",
    "Docker (software)",
    "Kubernetes",
    "Amazon Web Services",
    "Cloud computing",
    "Database",
    "NoSQL",
    "MongoDB",
    "Redis",
    "Apache Kafka",
    "TensorFlow",
    "PyTorch",
    "Scikit-learn",
    "Pandas (software)",
    "NumPy",
    "Data science",
    "Big data",
    "Apache Spark",
    "Hadoop",
    "Vector database",
    "Semantic search",
    "Information retrieval",
    "Search engine",
    "REST API",
    "FastAPI",
    "Flask (web framework)",
    "Django (web framework)",
    "Microservices",
    "DevOps",
    "Continuous integration",
    "Git",
    "GitHub",
    "Linux",
    "Ubuntu",
    "Containerization"
]


def get_wikipedia_article(title, lang='en'):
    """
    Scarica un articolo Wikipedia
    
    Args:
        title: Titolo dell'articolo
        lang: Lingua (default: en)
        
    Returns:
        dict con title, url, extract (prime 500 parole)
    """
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
    
    # Wikipedia richiede User-Agent header
    headers = {
        'User-Agent': 'PgvectorBedrockDemo/1.0 (Educational Project; Python/requests)'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return {
            'title': data.get('title', title),
            'url': data.get('content_urls', {}).get('desktop', {}).get('page', ''),
            'extract': data.get('extract', ''),
            'description': data.get('description', '')
        }
    except Exception as e:
        print(f"   ⚠️  Errore scaricando '{title}': {e}")
        return None


def load_wikipedia_articles(topics=None, limit=None):
    """
    Carica articoli Wikipedia nel database
    
    Args:
        topics: Lista di topic (default: WIKIPEDIA_TOPICS)
        limit: Numero massimo di articoli (default: tutti)
    """
    if topics is None:
        topics = WIKIPEDIA_TOPICS
    
    if limit:
        topics = topics[:limit]
    
    print(f"📚 Caricamento {len(topics)} articoli Wikipedia...")
    print()
    
    # Connetti al database
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Verifica quanti documenti esistono già
    cur.execute("SELECT COUNT(*) FROM documents")
    existing_count = cur.fetchone()[0]
    print(f"   Documenti esistenti nel DB: {existing_count}")
    print()
    
    inserted = 0
    skipped = 0
    errors = 0
    
    for i, topic in enumerate(topics, 1):
        print(f"[{i}/{len(topics)}] {topic}...", end=' ')
        
        # Scarica articolo
        article = get_wikipedia_article(topic)
        
        if not article or not article['extract']:
            print("❌ Saltato")
            skipped += 1
            continue
        
        # Crea contenuto combinando titolo + descrizione + estratto
        content = f"{article['title']}\n\n"
        if article['description']:
            content += f"{article['description']}\n\n"
        content += article['extract']
        
        # Verifica se non è troppo corto
        if len(content) < 100:
            print("⚠️  Troppo corto, saltato")
            skipped += 1
            continue
        
        try:
            # Genera embedding
            embedding = get_embedding(content)
            
            # Metadata
            metadata = {
                'source': 'wikipedia',
                'title': article['title'],
                'url': article['url'],
                'language': 'en',
                'category': 'Technology'
            }
            
            # Inserisci nel database
            cur.execute(
                """
                INSERT INTO documents (content, embedding, metadata)
                VALUES (%s, %s, %s)
                """,
                (content, embedding, json.dumps(metadata))
            )
            conn.commit()
            
            print(f"✅ ({len(content)} chars)")
            inserted += 1
            
            # Rate limiting per non sovraccaricare API
            time.sleep(0.5)
            
        except Exception as e:
            print(f"❌ Errore: {e}")
            errors += 1
            continue
    
    # Statistiche finali
    cur.execute("SELECT COUNT(*) FROM documents")
    total_count = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    print()
    print("=" * 60)
    print("📊 RIEPILOGO")
    print("=" * 60)
    print(f"✅ Articoli inseriti: {inserted}")
    print(f"⚠️  Articoli saltati: {skipped}")
    print(f"❌ Errori: {errors}")
    print(f"📚 Totale documenti nel DB: {total_count}")
    print("=" * 60)
    
    return inserted


if __name__ == "__main__":
    import sys
    
    # Permetti di specificare un limite da command line
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            print(f"📌 Limite impostato: {limit} articoli\n")
        except ValueError:
            print("Uso: python load_wikipedia.py [numero_articoli]")
            sys.exit(1)
    
    load_wikipedia_articles(limit=limit)

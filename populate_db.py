#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
populate_db.py -- Popolamento massivo DB da Wikipedia (AI/ML/Data Science)

Uso:
  python populate_db.py                  # Esecuzione completa
  python populate_db.py --dry-run        # Mostra quanti chunk verrebbero creati
  python populate_db.py --lang en        # Solo articoli in inglese
  python populate_db.py --lang it        # Solo articoli in italiano
  python populate_db.py --limit 10       # Solo i primi 10 topic (test)

Requisiti aggiuntivi:
  pip install tqdm
"""

import argparse
import hashlib
import json
import time
import re
from typing import Optional

import requests
from tqdm import tqdm

from config import get_db_connection, EMBEDDING_DIMENSION
from embeddings import get_embedding

# =============================================================================
# CONFIGURAZIONE
# =============================================================================

CHUNK_SIZE      = 500   # Token approssimativi per chunk (1 token ~ 4 caratteri)
CHUNK_OVERLAP   = 50    # Overlap tra chunk consecutivi
BEDROCK_DELAY   = 0.3   # Pausa tra chiamate Bedrock (evita throttling)
WIKIPEDIA_DELAY = 0.5   # Pausa tra chiamate Wikipedia
MAX_RETRIES     = 3     # Tentativi in caso di errore Bedrock

# =============================================================================
# TOPIC AI/ML/DATA SCIENCE -- EN + IT
# =============================================================================

TOPICS = {
    "en": [
        # Core AI/ML
        ("Artificial intelligence",             "AI"),
        ("Machine learning",                    "ML"),
        ("Deep learning",                       "Deep Learning"),
        ("Neural network (machine learning)",   "Neural Networks"),
        ("Convolutional neural network",        "Deep Learning"),
        ("Recurrent neural network",            "Deep Learning"),
        ("Transformer (machine learning)",      "NLP"),
        ("Attention mechanism",                 "NLP"),
        ("Generative adversarial network",      "Generative AI"),
        ("Variational autoencoder",             "Generative AI"),
        ("Diffusion model",                     "Generative AI"),
        ("Large language model",                "LLM"),
        ("GPT-4",                               "LLM"),
        ("BERT (language model)",               "NLP"),
        ("Reinforcement learning",              "ML"),
        ("Transfer learning",                   "ML"),
        ("Federated learning",                  "ML"),
        ("Explainable artificial intelligence", "AI Ethics"),
        ("AI safety",                           "AI Ethics"),
        ("Artificial general intelligence",     "AI"),
        # NLP
        ("Natural language processing",         "NLP"),
        ("Word embedding",                      "NLP"),
        ("Word2vec",                            "NLP"),
        ("Sentiment analysis",                  "NLP"),
        ("Named-entity recognition",            "NLP"),
        ("Text summarization",                  "NLP"),
        ("Question answering",                  "NLP"),
        ("Information retrieval",               "Search"),
        ("Semantic search",                     "Search"),
        ("Vector database",                     "Search"),
        # Data Science
        ("Data science",                        "Data Science"),
        ("Feature engineering",                 "Data Science"),
        ("Dimensionality reduction",            "Data Science"),
        ("Principal component analysis",        "Data Science"),
        ("Cluster analysis",                    "Data Science"),
        ("Random forest",                       "ML"),
        ("Gradient boosting",                   "ML"),
        ("Support vector machine",              "ML"),
        ("Logistic regression",                 "ML"),
        ("Overfitting",                         "ML"),
        ("Cross-validation (statistics)",       "Data Science"),
        ("Hyperparameter optimization",         "ML"),
        # Infrastructure / MLOps
        ("MLOps",                               "MLOps"),
        ("Apache Spark",                        "Data Engineering"),
        ("Apache Kafka",                        "Data Engineering"),
        ("PostgreSQL",                          "Database"),
        ("Vector space model",                  "Search"),
        ("Retrieval-augmented generation",      "LLM"),
    ],
    "it": [
        ("Intelligenza artificiale",                "AI"),
        ("Apprendimento automatico",                "ML"),
        ("Apprendimento profondo",                  "Deep Learning"),
        ("Rete neurale artificiale",                "Neural Networks"),
        ("Elaborazione del linguaggio naturale",    "NLP"),
        ("Riconoscimento vocale",                   "NLP"),
        ("Visione artificiale",                     "Computer Vision"),
        ("Robotica",                                "AI"),
        ("Algoritmo",                               "Computer Science"),
        ("Big data",                                "Data Science"),
        ("Data mining",                             "Data Science"),
        ("Statistica",                              "Data Science"),
        ("Regressione lineare",                     "ML"),
        ("Albero decisionale",                      "ML"),
        ("Clustering",                              "ML"),
    ],
}

WIKI_API = {
    "en": "https://en.wikipedia.org/w/api.php",
    "it": "https://it.wikipedia.org/w/api.php",
}


# =============================================================================
# WIKIPEDIA
# =============================================================================

def fetch_wikipedia_article(title: str, lang: str) -> Optional[dict]:
    """Scarica il testo completo di un articolo Wikipedia."""
    params = {
        "action":          "query",
        "titles":          title,
        "prop":            "extracts",
        "explaintext":     True,
        "exsectionformat": "plain",
        "redirects":       True,
        "format":          "json",
    }
    try:
        headers = {
            "User-Agent": "pgvector-bedrock-demo/1.0 (https://github.com/dpadeletti/pgvector-bedrock-demo; educational project)"
        }
        resp = requests.get(WIKI_API[lang], params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        page  = next(iter(pages.values()))

        if "missing" in page:
            return None
        text = page.get("extract", "")
        if not text or len(text) < 100:
            return None

        base = ("https://en.wikipedia.org/wiki/"
                if lang == "en" else "https://it.wikipedia.org/wiki/")
        return {
            "title": page.get("title", title),
            "text":  text,
            "url":   base + title.replace(" ", "_"),
            "lang":  lang,
        }
    except Exception as e:
        print(f"  [WARN] Errore fetch '{title}' ({lang}): {e}")
        return None


# =============================================================================
# CHUNKING
# =============================================================================

def chunk_text(text: str,
               chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list:
    """
    Spezza il testo in chunk rispettando i paragrafi Wikipedia.
    1 token ~ 4 caratteri (stima rapida senza tokenizer).
    """
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text).strip()
    paragraphs    = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks        = []
    current_chunk = []
    current_size  = 0

    for para in paragraphs:
        para_size = len(para) // 4

        if para_size > chunk_size:
            # Paragrafo lungo: spezza per frasi
            for sent in re.split(r'(?<=[.!?])\s+', para):
                sent_size = len(sent) // 4
                if current_size + sent_size > chunk_size and current_chunk:
                    chunks.append(' '.join(current_chunk))
                    overlap_text  = ' '.join(current_chunk[-3:])
                    current_chunk = [overlap_text]
                    current_size  = len(overlap_text) // 4
                current_chunk.append(sent)
                current_size += sent_size
        else:
            if current_size + para_size > chunk_size and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = current_chunk[-1:] if overlap > 0 else []
                current_size  = len(current_chunk[0]) // 4 if current_chunk else 0
            current_chunk.append(para)
            current_size += para_size

    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))

    return [c for c in chunks if len(c) >= 50]


# =============================================================================
# DATABASE
# =============================================================================

def get_existing_hashes(conn) -> set:
    cur = conn.cursor()
    cur.execute(
        "SELECT metadata->>'chunk_hash' FROM documents "
        "WHERE metadata->>'chunk_hash' IS NOT NULL"
    )
    result = {row[0] for row in cur.fetchall() if row[0]}
    cur.close()
    return result


def get_processed_titles(conn) -> set:
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT metadata->>'title' FROM documents "
        "WHERE metadata->>'title' IS NOT NULL"
    )
    result = {row[0] for row in cur.fetchall() if row[0]}
    cur.close()
    return result


def insert_chunk(conn, content: str, metadata: dict) -> int:
    embedding = get_embedding(content)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO documents (content, embedding, metadata, created_at)
        VALUES (%s, %s, %s, NOW())
        RETURNING id
        """,
        (content, embedding, json.dumps(metadata))
    )
    doc_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return doc_id


# =============================================================================
# MAIN
# =============================================================================

def run(dry_run: bool = False,
        lang_filter: Optional[str] = None,
        limit: Optional[int] = None):

    print("\n" + "=" * 60)
    print("  Wikipedia -> pgvector Bulk Importer")
    print("=" * 60)

    languages  = [lang_filter] if lang_filter else list(TOPICS.keys())
    all_topics = []
    for lang in languages:
        for title, category in TOPICS[lang]:
            all_topics.append((title, category, lang))

    if limit:
        all_topics = all_topics[:limit]

    print(f"\n  Topic da processare : {len(all_topics)}")
    print(f"  Lingue              : {', '.join(languages)}")
    print(f"  Chunk size          : ~{CHUNK_SIZE} token | overlap: {CHUNK_OVERLAP}")

    if dry_run:
        print("\n  DRY RUN -- nessun inserimento nel DB\n")

    conn             = None
    existing_hashes  = set()
    processed_titles = set()

    if not dry_run:
        conn             = get_db_connection()
        existing_hashes  = get_existing_hashes(conn)
        processed_titles = get_processed_titles(conn)
        print(f"  Chunk gia nel DB    : {len(existing_hashes)}")
        print(f"  Topic gia processati: {len(processed_titles)}")

    stats = {
        "topics_ok": 0, "topics_skip": 0, "topics_error": 0,
        "chunks_inserted": 0, "chunks_duplicate": 0, "bedrock_errors": 0,
    }

    print(f"\n{'─' * 60}\n")

    for title, category, lang in tqdm(all_topics, desc="Articoli", unit="art"):

        if title in processed_titles:
            tqdm.write(f"  Skip: [{lang}] {title}")
            stats["topics_skip"] += 1
            continue

        tqdm.write(f"\n  [{lang.upper()}] {title} ({category})")

        article = fetch_wikipedia_article(title, lang)
        time.sleep(WIKIPEDIA_DELAY)

        if not article:
            tqdm.write(f"  Articolo non trovato")
            stats["topics_error"] += 1
            continue

        chunks = chunk_text(article["text"])
        tqdm.write(f"  {len(chunks)} chunk ({len(article['text'])} caratteri)")

        if dry_run:
            stats["topics_ok"]       += 1
            stats["chunks_inserted"] += len(chunks)
            continue

        for i, chunk in enumerate(tqdm(chunks, desc="    Chunk", leave=False, unit="chunk")):
            chunk_hash = hashlib.md5(chunk.encode()).hexdigest()

            if chunk_hash in existing_hashes:
                stats["chunks_duplicate"] += 1
                continue

            metadata = {
                "title":       article["title"],
                "url":         article["url"],
                "language":    lang,
                "category":    category,
                "source":      "wikipedia",
                "chunk_index": i,
                "chunk_total": len(chunks),
                "chunk_hash":  chunk_hash,
            }

            for attempt in range(MAX_RETRIES):
                try:
                    insert_chunk(conn, chunk, metadata)
                    existing_hashes.add(chunk_hash)
                    stats["chunks_inserted"] += 1
                    time.sleep(BEDROCK_DELAY)
                    break
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        wait = 2 ** attempt
                        tqdm.write(f"  Retry {attempt+1} (attendo {wait}s): {e}")
                        time.sleep(wait)
                    else:
                        tqdm.write(f"  Chunk fallito: {e}")
                        stats["bedrock_errors"] += 1

        stats["topics_ok"] += 1

    # Riepilogo
    print(f"\n{'=' * 60}")
    print("  COMPLETATO")
    print(f"{'=' * 60}")
    print(f"  Topic processati  : {stats['topics_ok']}")
    print(f"  Topic saltati     : {stats['topics_skip']} (gia nel DB)")
    print(f"  Topic con errori  : {stats['topics_error']}")
    print(f"  Chunk inseriti    : {stats['chunks_inserted']}")
    print(f"  Chunk duplicati   : {stats['chunks_duplicate']}")
    print(f"  Errori Bedrock    : {stats['bedrock_errors']}")

    if not dry_run and conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM documents")
        total = cur.fetchone()[0]
        cur.close()
        conn.close()
        print(f"\n  Totale documenti nel DB: {total}")
    print()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Popola il DB con articoli Wikipedia AI/ML")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra statistiche senza inserire nel DB")
    parser.add_argument("--lang", choices=["en", "it"],
                        help="Processa solo una lingua")
    parser.add_argument("--limit", type=int,
                        help="Processa solo i primi N topic (test)")
    args = parser.parse_args()
    run(dry_run=args.dry_run, lang_filter=args.lang, limit=args.limit)

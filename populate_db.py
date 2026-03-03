#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
populate_db.py -- Popolamento DB da Wikipedia + arXiv (~50K chunk)

Sorgenti:
  - Wikipedia EN: ~250 topic AI/ML/Data Science/MLOps
  - Wikipedia IT: ~50  topic AI/ML
  - arXiv:        abstract di paper ML/AI (cs.LG, cs.AI, cs.NE, cs.CL, cs.CV, stat.ML)

Uso:
  python populate_db.py                        # Tutto (Wikipedia + arXiv)
  python populate_db.py --source wikipedia     # Solo Wikipedia
  python populate_db.py --source arxiv         # Solo arXiv
  python populate_db.py --dry-run              # Stima senza inserire
  python populate_db.py --lang en              # Solo Wikipedia EN
  python populate_db.py --limit 10             # Solo i primi 10 topic Wikipedia (test)
  python populate_db.py --arxiv-limit 1000     # Solo 1000 paper arXiv (test)

Resume automatico: i chunk gia presenti nel DB (by hash) vengono saltati.

Requisiti:
  pip install tqdm requests
"""

import argparse
import hashlib
import json
import time
import re
import xml.etree.ElementTree as ET
from typing import Optional

import requests
from tqdm import tqdm

from config import get_db_connection, EMBEDDING_DIMENSION
from embeddings import get_embedding

# =============================================================================
# CONFIGURAZIONE
# =============================================================================

CHUNK_SIZE      = 500   # Token approssimativi per chunk (1 token ~ 4 char)
CHUNK_OVERLAP   = 50    # Overlap tra chunk consecutivi
BEDROCK_DELAY   = 0.25  # Pausa tra chiamate Bedrock embedding
WIKIPEDIA_DELAY = 0.5   # Pausa tra chiamate Wikipedia API
ARXIV_DELAY     = 3.0   # Pausa tra chiamate arXiv API (rispetta rate limit)
MAX_RETRIES     = 3     # Tentativi in caso di errore

ARXIV_CATEGORIES = ["cs.LG", "cs.AI", "cs.NE", "cs.CL", "cs.CV", "stat.ML"]
ARXIV_BATCH_SIZE = 500  # Paper per chiamata API arXiv (max 1000)
ARXIV_DEFAULT_LIMIT = 40000  # Paper totali arXiv di default

# =============================================================================
# WIKIPEDIA TOPICS -- EN (~250) + IT (~50)
# =============================================================================

TOPICS = {
    "en": [
        # --- Core AI / ML ---
        ("Artificial intelligence",               "AI"),
        ("Machine learning",                      "ML"),
        ("Deep learning",                         "Deep Learning"),
        ("Neural network (machine learning)",     "Neural Networks"),
        ("Supervised learning",                   "ML"),
        ("Unsupervised learning",                 "ML"),
        ("Semi-supervised learning",              "ML"),
        ("Self-supervised learning",              "ML"),
        ("Online machine learning",               "ML"),
        ("Multi-task learning",                   "ML"),
        ("Meta-learning (computer science)",      "ML"),
        ("Few-shot learning",                     "ML"),
        ("Zero-shot learning",                    "ML"),
        ("Transfer learning",                     "ML"),
        ("Federated learning",                    "ML"),
        ("Curriculum learning",                   "ML"),
        ("Active learning (machine learning)",    "ML"),
        ("Ensemble learning",                     "ML"),
        ("Reinforcement learning",                "ML"),
        ("Deep reinforcement learning",           "ML"),
        ("Multi-agent system",                    "AI"),
        ("Explainable artificial intelligence",   "AI Ethics"),
        ("AI safety",                             "AI Ethics"),
        ("Artificial general intelligence",       "AI"),
        ("AI alignment",                          "AI Ethics"),
        ("Algorithmic bias",                      "AI Ethics"),
        # --- Neural Network Architectures ---
        ("Convolutional neural network",          "Deep Learning"),
        ("Recurrent neural network",              "Deep Learning"),
        ("Long short-term memory",                "Deep Learning"),
        ("Gated recurrent unit",                  "Deep Learning"),
        ("Transformer (machine learning)",        "NLP"),
        ("Attention mechanism",                   "NLP"),
        ("BERT (language model)",                 "NLP"),
        ("GPT-4",                                 "LLM"),
        ("GPT-3",                                 "LLM"),
        ("T5 (language model)",                   "NLP"),
        ("Encoder-decoder architecture",          "Deep Learning"),
        ("Residual neural network",               "Deep Learning"),
        ("Generative adversarial network",        "Generative AI"),
        ("Variational autoencoder",               "Generative AI"),
        ("Autoencoder",                           "Deep Learning"),
        ("Diffusion model",                       "Generative AI"),
        ("Flow-based generative model",           "Generative AI"),
        ("Boltzmann machine",                     "Deep Learning"),
        ("Restricted Boltzmann machine",          "Deep Learning"),
        ("Capsule neural network",                "Deep Learning"),
        ("Graph neural network",                  "Deep Learning"),
        ("Spiking neural network",                "Deep Learning"),
        ("Liquid state machine",                  "Deep Learning"),
        ("Echo state network",                    "Deep Learning"),
        ("Hopfield network",                      "Deep Learning"),
        ("Perceptron",                            "Deep Learning"),
        ("Multilayer perceptron",                 "Deep Learning"),
        ("U-Net",                                 "Computer Vision"),
        ("Vision transformer",                    "Computer Vision"),
        # --- Training & Optimization ---
        ("Backpropagation",                       "Deep Learning"),
        ("Stochastic gradient descent",           "Optimization"),
        ("Adam (optimization algorithm)",         "Optimization"),
        ("Gradient descent",                      "Optimization"),
        ("Learning rate",                         "Optimization"),
        ("Batch normalization",                   "Deep Learning"),
        ("Layer normalization",                   "Deep Learning"),
        ("Dropout (neural networks)",             "Deep Learning"),
        ("Regularization (mathematics)",          "ML"),
        ("Early stopping",                        "ML"),
        ("Overfitting",                           "ML"),
        ("Bias–variance tradeoff",                "ML"),
        ("Loss function",                         "ML"),
        ("Cross-entropy",                         "ML"),
        ("Activation function",                   "Deep Learning"),
        ("Rectifier (neural networks)",           "Deep Learning"),
        ("Sigmoid function",                      "Deep Learning"),
        ("Softmax function",                      "Deep Learning"),
        ("Vanishing gradient problem",            "Deep Learning"),
        ("Exploding gradient problem",            "Deep Learning"),
        ("Weight initialization",                 "Deep Learning"),
        ("Knowledge distillation",                "Deep Learning"),
        ("Pruning (artificial neural network)",   "Deep Learning"),
        ("Quantization (machine learning)",       "MLOps"),
        # --- NLP ---
        ("Natural language processing",           "NLP"),
        ("Large language model",                  "LLM"),
        ("Word embedding",                        "NLP"),
        ("Word2vec",                              "NLP"),
        ("GloVe (machine learning)",              "NLP"),
        ("Sentence embedding",                    "NLP"),
        ("Tokenization (machine learning)",       "NLP"),
        ("Byte pair encoding",                    "NLP"),
        ("Sentiment analysis",                    "NLP"),
        ("Named-entity recognition",              "NLP"),
        ("Text summarization",                    "NLP"),
        ("Machine translation",                   "NLP"),
        ("Question answering",                    "NLP"),
        ("Coreference resolution",                "NLP"),
        ("Dependency parsing",                    "NLP"),
        ("Part-of-speech tagging",                "NLP"),
        ("Speech recognition",                    "NLP"),
        ("Text-to-speech",                        "NLP"),
        ("Optical character recognition",         "NLP"),
        ("Chatbot",                               "NLP"),
        ("Dialogue system",                       "NLP"),
        ("Prompt engineering",                    "LLM"),
        ("Retrieval-augmented generation",        "LLM"),
        ("In-context learning (machine learning)","LLM"),
        ("Hallucination (artificial intelligence)","LLM"),
        # --- Computer Vision ---
        ("Computer vision",                       "Computer Vision"),
        ("Object detection",                      "Computer Vision"),
        ("Image segmentation",                    "Computer Vision"),
        ("Face recognition",                      "Computer Vision"),
        ("Optical flow",                          "Computer Vision"),
        ("Image classification",                  "Computer Vision"),
        ("Generative art",                        "Generative AI"),
        ("DALL-E",                                "Generative AI"),
        ("Stable Diffusion",                      "Generative AI"),
        ("CLIP (machine learning)",               "Computer Vision"),
        # --- Data Science & Statistics ---
        ("Data science",                          "Data Science"),
        ("Feature engineering",                   "Data Science"),
        ("Feature selection",                     "Data Science"),
        ("Dimensionality reduction",              "Data Science"),
        ("Principal component analysis",          "Data Science"),
        ("t-distributed stochastic neighbor embedding", "Data Science"),
        ("UMAP",                                  "Data Science"),
        ("Cluster analysis",                      "Data Science"),
        ("K-means clustering",                    "Data Science"),
        ("DBSCAN",                                "Data Science"),
        ("Hierarchical clustering",               "Data Science"),
        ("Gaussian mixture model",                "Data Science"),
        ("Anomaly detection",                     "Data Science"),
        ("Outlier",                               "Data Science"),
        ("Imputation (statistics)",               "Data Science"),
        ("Data augmentation",                     "Data Science"),
        ("Class imbalance",                       "Data Science"),
        ("Cross-validation (statistics)",         "Data Science"),
        ("Hyperparameter optimization",           "ML"),
        ("Bayesian optimization",                 "Optimization"),
        ("Grid search",                           "ML"),
        ("Random search",                         "ML"),
        # --- Classical ML ---
        ("Random forest",                         "ML"),
        ("Gradient boosting",                     "ML"),
        ("XGBoost",                               "ML"),
        ("LightGBM",                              "ML"),
        ("Support vector machine",                "ML"),
        ("Logistic regression",                   "ML"),
        ("Linear regression",                     "ML"),
        ("Decision tree",                         "ML"),
        ("Naive Bayes classifier",                "ML"),
        ("K-nearest neighbors algorithm",         "ML"),
        ("Bayesian network",                      "ML"),
        ("Hidden Markov model",                   "ML"),
        ("Expectation–maximization algorithm",    "ML"),
        ("Gaussian process",                      "ML"),
        ("Kernel method",                         "ML"),
        ("Lasso (statistics)",                    "ML"),
        ("Ridge regression",                      "ML"),
        ("Elastic net regularization",            "ML"),
        # --- Search & Vector DB ---
        ("Information retrieval",                 "Search"),
        ("Semantic search",                       "Search"),
        ("Vector database",                       "Search"),
        ("Vector space model",                    "Search"),
        ("Approximate nearest neighbor search",   "Search"),
        ("Locality-sensitive hashing",            "Search"),
        ("Inverted index",                        "Search"),
        ("TF-IDF",                                "Search"),
        ("BM25",                                  "Search"),
        ("Dense retrieval",                       "Search"),
        ("Sentence-BERT",                         "Search"),
        ("Cosine similarity",                     "Search"),
        ("Euclidean distance",                    "Search"),
        # --- MLOps & Infrastructure ---
        ("MLOps",                                 "MLOps"),
        ("Model deployment",                      "MLOps"),
        ("Model monitoring",                      "MLOps"),
        ("Data pipeline",                         "MLOps"),
        ("Feature store",                         "MLOps"),
        ("A/B testing",                           "MLOps"),
        ("Continuous integration",                "MLOps"),
        ("Containerization",                      "MLOps"),
        ("Docker (software)",                     "MLOps"),
        ("Kubernetes",                            "MLOps"),
        ("Apache Spark",                          "Data Engineering"),
        ("Apache Kafka",                          "Data Engineering"),
        ("Apache Airflow",                        "Data Engineering"),
        ("dbt (software)",                        "Data Engineering"),
        ("PostgreSQL",                            "Database"),
        ("Redis",                                 "Database"),
        ("Elasticsearch",                         "Search"),
        ("Amazon Web Services",                   "Cloud"),
        ("Google Cloud Platform",                 "Cloud"),
        ("Microsoft Azure",                       "Cloud"),
        ("Amazon SageMaker",                      "MLOps"),
        # --- Evaluation & Metrics ---
        ("Precision and recall",                  "ML"),
        ("F-score",                               "ML"),
        ("Receiver operating characteristic",     "ML"),
        ("Confusion matrix",                      "ML"),
        ("Mean squared error",                    "ML"),
        ("BLEU",                                  "NLP"),
        ("ROUGE (metric)",                        "NLP"),
        ("Perplexity",                            "NLP"),
        ("Accuracy and precision",                "ML"),
        # --- Probability & Math ---
        ("Probability theory",                    "Math"),
        ("Bayes theorem",                         "Math"),
        ("Maximum likelihood estimation",         "Math"),
        ("Expectation (mathematics)",             "Math"),
        ("Entropy (information theory)",          "Math"),
        ("Kullback–Leibler divergence",           "Math"),
        ("Monte Carlo method",                    "Math"),
        ("Markov chain",                          "Math"),
        ("Linear algebra",                        "Math"),
        ("Matrix (mathematics)",                  "Math"),
        ("Eigenvalues and eigenvectors",          "Math"),
        ("Convex optimization",                   "Optimization"),
        ("Lagrange multiplier",                   "Optimization"),
        # --- Specialized Topics ---
        ("Federated learning",                    "ML"),
        ("Continual learning",                    "ML"),
        ("Causal inference",                      "Data Science"),
        ("Time series",                           "Data Science"),
        ("Recommendation system",                 "ML"),
        ("Collaborative filtering",               "ML"),
        ("Knowledge graph",                       "AI"),
        ("Ontology (information science)",        "AI"),
        ("Symbolic artificial intelligence",      "AI"),
        ("Fuzzy logic",                           "AI"),
        ("Genetic algorithm",                     "Optimization"),
        ("Evolutionary algorithm",                "Optimization"),
        ("Swarm intelligence",                    "AI"),
        ("Model compression",                     "Deep Learning"),
        ("Neural architecture search",            "Deep Learning"),
        ("AutoML",                                "MLOps"),
        ("Mixture of experts",                    "Deep Learning"),
        ("Sparse attention",                      "NLP"),
        ("Flash attention",                       "NLP"),
        ("Parameter-efficient fine-tuning",       "LLM"),
        ("Instruction tuning",                    "LLM"),
        ("RLHF",                                  "LLM"),
    ],
    "it": [
        ("Intelligenza artificiale",              "AI"),
        ("Apprendimento automatico",              "ML"),
        ("Apprendimento profondo",                "Deep Learning"),
        ("Rete neurale artificiale",              "Neural Networks"),
        ("Elaborazione del linguaggio naturale",  "NLP"),
        ("Riconoscimento vocale",                 "NLP"),
        ("Visione artificiale",                   "Computer Vision"),
        ("Robotica",                              "AI"),
        ("Algoritmo",                             "Computer Science"),
        ("Big data",                              "Data Science"),
        ("Data mining",                           "Data Science"),
        ("Statistica",                            "Data Science"),
        ("Regressione lineare",                   "ML"),
        ("Albero decisionale",                    "ML"),
        ("Clustering",                            "ML"),
        ("Rete bayesiana",                        "ML"),
        ("Logica fuzzy",                          "AI"),
        ("Algoritmo genetico",                    "Optimization"),
        ("Apprendimento per rinforzo",            "ML"),
        ("Reti neurali ricorrenti",               "Deep Learning"),
        ("Reti neurali convoluzionali",           "Deep Learning"),
        ("Trasformatore (machine learning)",      "NLP"),
        ("Riconoscimento delle immagini",         "Computer Vision"),
        ("Rilevamento oggetti",                   "Computer Vision"),
        ("Sistema di raccomandazione",            "ML"),
        ("Analisi dei dati",                      "Data Science"),
        ("Riduzione della dimensionalità",        "Data Science"),
        ("Analisi delle componenti principali",   "Data Science"),
        ("Regressione logistica",                 "ML"),
        ("Macchina a vettori di supporto",        "ML"),
        ("Foresta casuale",                       "ML"),
        ("Gradient boosting",                     "ML"),
        ("Overfitting",                           "ML"),
        ("Validazione incrociata",                "Data Science"),
        ("Ottimizzazione",                        "Optimization"),
        ("Funzione di perdita",                   "Deep Learning"),
        ("Backpropagation",                       "Deep Learning"),
        ("Discesa del gradiente",                 "Optimization"),
        ("Normalizzazione dei dati",              "Data Science"),
        ("Transfer learning",                     "ML"),
        ("Generative adversarial network",        "Generative AI"),
        ("Etica dell'intelligenza artificiale",   "AI Ethics"),
        ("Bias algoritmico",                      "AI Ethics"),
        ("Spiegabilità dell'IA",                  "AI Ethics"),
        ("Internet delle cose",                   "AI"),
        ("Cloud computing",                       "Cloud"),
        ("PostgreSQL",                            "Database"),
        ("Apache Spark",                          "Data Engineering"),
        ("Sicurezza informatica",                 "AI"),
        ("Apprendimento federato",                "ML"),
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
        headers = {"User-Agent": "pgvector-bedrock-demo/1.0 (educational project)"}
        resp    = requests.get(WIKI_API[lang], params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        pages   = resp.json().get("query", {}).get("pages", {})
        page    = next(iter(pages.values()))
        if "missing" in page:
            return None
        text = page.get("extract", "")
        if not text or len(text) < 100:
            return None
        base = "https://en.wikipedia.org/wiki/" if lang == "en" else "https://it.wikipedia.org/wiki/"
        return {
            "title":  page.get("title", title),
            "text":   text,
            "url":    base + title.replace(" ", "_"),
            "lang":   lang,
            "source": "wikipedia",
        }
    except Exception as e:
        print(f"  [WARN] Errore fetch Wikipedia '{title}' ({lang}): {e}")
        return None


# =============================================================================
# ARXIV
# =============================================================================

ARXIV_NS = "http://www.w3.org/2005/Atom"

def fetch_arxiv_batch(category: str, start: int, max_results: int) -> list:
    """
    Scarica un batch di abstract arXiv per una categoria.
    Ritorna lista di dict: {title, abstract, url, authors, published, category}
    """
    url    = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"cat:{category}",
        "start":        start,
        "max_results":  max_results,
        "sortBy":       "submittedDate",
        "sortOrder":    "descending",
    }
    try:
        headers = {"User-Agent": "pgvector-bedrock-demo/1.0 (educational project)"}
        resp    = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()

        root    = ET.fromstring(resp.content)
        papers  = []

        for entry in root.findall(f"{{{ARXIV_NS}}}entry"):
            title_el    = entry.find(f"{{{ARXIV_NS}}}title")
            summary_el  = entry.find(f"{{{ARXIV_NS}}}summary")
            id_el       = entry.find(f"{{{ARXIV_NS}}}id")
            pub_el      = entry.find(f"{{{ARXIV_NS}}}published")
            authors_el  = entry.findall(f"{{{ARXIV_NS}}}author")

            if title_el is None or summary_el is None:
                continue

            title    = re.sub(r'\s+', ' ', title_el.text or "").strip()
            abstract = re.sub(r'\s+', ' ', summary_el.text or "").strip()
            arxiv_id = (id_el.text or "").strip()
            pub_date = (pub_el.text or "")[:10]
            authors  = [
                (a.find(f"{{{ARXIV_NS}}}name").text or "").strip()
                for a in authors_el[:3]
                if a.find(f"{{{ARXIV_NS}}}name") is not None
            ]

            if not abstract or len(abstract) < 50:
                continue

            papers.append({
                "title":     title,
                "abstract":  abstract,
                "url":       arxiv_id,
                "authors":   ", ".join(authors),
                "published": pub_date,
                "category":  category,
                "source":    "arxiv",
            })

        return papers

    except Exception as e:
        print(f"  [WARN] Errore fetch arXiv {category} start={start}: {e}")
        return []


def format_arxiv_chunk(paper: dict) -> str:
    """
    Formatta il contenuto del chunk arXiv come:
    Title: ...
    Authors: ...
    Abstract: ...
    Questo aiuta il full-text search (tsvector) a trovare titoli e parole chiave.
    """
    parts = [f"Title: {paper['title']}"]
    if paper.get("authors"):
        parts.append(f"Authors: {paper['authors']}")
    parts.append(f"Abstract: {paper['abstract']}")
    return "\n".join(parts)


# =============================================================================
# CHUNKING
# =============================================================================

def chunk_text(text: str,
               chunk_size: int = CHUNK_SIZE,
               overlap: int    = CHUNK_OVERLAP) -> list:
    """Spezza il testo in chunk rispettando paragrafi. 1 token ~ 4 char."""
    text       = re.sub(r'\n{3,}', '\n\n', text)
    text       = re.sub(r' {2,}', ' ', text).strip()
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks        = []
    current_chunk = []
    current_size  = 0

    for para in paragraphs:
        para_size = len(para) // 4
        if para_size > chunk_size:
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
# WIKIPEDIA RUNNER
# =============================================================================

def run_wikipedia(dry_run: bool, lang_filter: Optional[str],
                  limit: Optional[int], conn, existing_hashes: set,
                  processed_titles: set, stats: dict):

    languages  = [lang_filter] if lang_filter else list(TOPICS.keys())
    all_topics = []
    for lang in languages:
        for title, category in TOPICS[lang]:
            all_topics.append((title, category, lang))

    if limit:
        all_topics = all_topics[:limit]

    total_en = len([t for t in all_topics if t[2] == "en"])
    total_it = len([t for t in all_topics if t[2] == "it"])
    print(f"\n  Wikipedia: {len(all_topics)} topic ({total_en} EN + {total_it} IT)")

    for title, category, lang in tqdm(all_topics, desc="Wikipedia", unit="art"):
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
        tqdm.write(f"  {len(chunks)} chunk ({len(article['text'])} char)")

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
                        time.sleep(2 ** attempt)
                    else:
                        tqdm.write(f"  Chunk fallito: {e}")
                        stats["bedrock_errors"] += 1
        stats["topics_ok"] += 1


# =============================================================================
# ARXIV RUNNER
# =============================================================================

def run_arxiv(dry_run: bool, arxiv_limit: int, conn,
              existing_hashes: set, stats: dict):
    """
    Scarica abstract arXiv dalle categorie ML/AI e li inserisce nel DB.
    Ogni abstract = 1 chunk (sono gia brevi, ~200 parole).
    Resume automatico via chunk_hash (hash dell abstract).
    """
    papers_per_cat = arxiv_limit // len(ARXIV_CATEGORIES)
    total_inserted = 0
    total_skip     = 0

    print(f"\n  arXiv: ~{arxiv_limit} paper totali "
          f"({papers_per_cat} per categoria × {len(ARXIV_CATEGORIES)} categorie)")
    print(f"  Categorie: {', '.join(ARXIV_CATEGORIES)}")

    for cat in ARXIV_CATEGORIES:
        cat_inserted = 0
        start        = 0
        pbar = tqdm(total=papers_per_cat, desc=f"arXiv {cat}", unit="paper")

        while cat_inserted < papers_per_cat:
            batch_size = min(ARXIV_BATCH_SIZE, papers_per_cat - cat_inserted)
            papers     = fetch_arxiv_batch(cat, start, batch_size)
            time.sleep(ARXIV_DELAY)

            if not papers:
                break

            for paper in papers:
                content    = format_arxiv_chunk(paper)
                chunk_hash = hashlib.md5(content.encode()).hexdigest()

                if chunk_hash in existing_hashes:
                    total_skip += 1
                    pbar.update(1)
                    continue

                if dry_run:
                    stats["chunks_inserted"] += 1
                    existing_hashes.add(chunk_hash)
                    cat_inserted += 1
                    total_inserted += 1
                    pbar.update(1)
                    continue

                metadata = {
                    "title":      paper["title"],
                    "url":        paper["url"],
                    "authors":    paper.get("authors", ""),
                    "published":  paper.get("published", ""),
                    "language":   "en",
                    "category":   paper["category"],
                    "source":     "arxiv",
                    "chunk_index": 0,
                    "chunk_total": 1,
                    "chunk_hash": chunk_hash,
                }
                for attempt in range(MAX_RETRIES):
                    try:
                        insert_chunk(conn, content, metadata)
                        existing_hashes.add(chunk_hash)
                        stats["chunks_inserted"] += 1
                        cat_inserted  += 1
                        total_inserted += 1
                        time.sleep(BEDROCK_DELAY)
                        pbar.update(1)
                        break
                    except Exception as e:
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(2 ** attempt)
                        else:
                            tqdm.write(f"  arXiv chunk fallito: {e}")
                            stats["bedrock_errors"] += 1

            start += batch_size
            if len(papers) < batch_size:
                break  # Fine dei risultati

        pbar.close()
        tqdm.write(f"  {cat}: {cat_inserted} paper inseriti")

    tqdm.write(f"\n  arXiv totale: {total_inserted} inseriti, {total_skip} gia presenti")


# =============================================================================
# MAIN
# =============================================================================

def run(dry_run: bool = False,
        source: str = "all",
        lang_filter: Optional[str] = None,
        limit: Optional[int] = None,
        arxiv_limit: int = ARXIV_DEFAULT_LIMIT):

    print("\n" + "=" * 60)
    print("  pgvector DB Importer -- Wikipedia + arXiv")
    print("=" * 60)
    print(f"\n  Sorgente  : {source}")
    print(f"  Dry run   : {dry_run}")
    print(f"  Chunk size: ~{CHUNK_SIZE} token | overlap: {CHUNK_OVERLAP}")

    conn             = None
    existing_hashes  = set()
    processed_titles = set()

    if not dry_run:
        conn             = get_db_connection()
        existing_hashes  = get_existing_hashes(conn)
        processed_titles = get_processed_titles(conn)
        print(f"  Chunk nel DB    : {len(existing_hashes)}")
        print(f"  Titoli nel DB   : {len(processed_titles)}")

    stats = {
        "topics_ok": 0, "topics_skip": 0, "topics_error": 0,
        "chunks_inserted": 0, "chunks_duplicate": 0, "bedrock_errors": 0,
    }

    # ── Wikipedia ──────────────────────────────────────────────────────────────
    if source in ("wikipedia", "all") and not lang_filter == "arxiv":
        print(f"\n{'─' * 60}")
        print("  SORGENTE: Wikipedia")
        print(f"{'─' * 60}")
        run_wikipedia(dry_run, lang_filter, limit, conn,
                      existing_hashes, processed_titles, stats)

    # ── arXiv ──────────────────────────────────────────────────────────────────
    if source in ("arxiv", "all") and lang_filter is None:
        print(f"\n{'─' * 60}")
        print("  SORGENTE: arXiv")
        print(f"{'─' * 60}")
        run_arxiv(dry_run, arxiv_limit, conn, existing_hashes, stats)

    # ── Riepilogo ──────────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  COMPLETATO")
    print(f"{'=' * 60}")
    print(f"  Chunk inseriti   : {stats['chunks_inserted']}")
    print(f"  Chunk duplicati  : {stats['chunks_duplicate']}")
    print(f"  Errori Bedrock   : {stats['bedrock_errors']}")
    print(f"  Topic Wikipedia  : {stats['topics_ok']} ok, "
          f"{stats['topics_skip']} skip, {stats['topics_error']} errori")

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
    parser = argparse.ArgumentParser(
        description="Popola il DB con Wikipedia AI/ML + abstract arXiv (~50K chunk)"
    )
    parser.add_argument(
        "--source", choices=["all", "wikipedia", "arxiv"], default="all",
        help="Sorgente dati (default: all)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Mostra statistiche senza inserire nel DB"
    )
    parser.add_argument(
        "--lang", choices=["en", "it"],
        help="Solo Wikipedia in questa lingua (ignorato per arXiv)"
    )
    parser.add_argument(
        "--limit", type=int,
        help="Processa solo i primi N topic Wikipedia (test)"
    )
    parser.add_argument(
        "--arxiv-limit", type=int, default=ARXIV_DEFAULT_LIMIT,
        dest="arxiv_limit",
        help=f"Numero massimo di paper arXiv (default: {ARXIV_DEFAULT_LIMIT})"
    )
    args = parser.parse_args()
    run(
        dry_run     = args.dry_run,
        source      = args.source,
        lang_filter = args.lang,
        limit       = args.limit,
        arxiv_limit = args.arxiv_limit,
    )

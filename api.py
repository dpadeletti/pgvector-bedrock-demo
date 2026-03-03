#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI REST API per semantic search + RAG chat con pgvector + AWS Bedrock
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import boto3
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from config import get_db_connection, EMBEDDING_DIMENSION
from embeddings import get_embedding


# ============================================================================
# Pydantic Models
# ============================================================================

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(5, ge=1, le=50)
    hybrid: bool = Field(
        True,
        description="Se True usa ricerca ibrida (semantica + full-text BM25 via RRF). "
                    "Se False usa solo ricerca semantica pgvector."
    )
    rerank: bool = Field(
        False,
        description="Se True applica reranking LLM (Nova Micro) sui candidati. "
                    "Migliora la qualita ma aggiunge ~1s di latenza."
    )
    expand: bool = Field(
        False,
        description="Se True genera 3 riformulazioni della query (Nova Micro) "
                    "ed esegue ricerche parallele. Aumenta la copertura semantica."
    )

    class Config:
        json_schema_extra = {
            "example": {"query": "machine learning", "limit": 5, "hybrid": True, "rerank": False, "expand": False}
        }


class SearchResult(BaseModel):
    id: int
    content: str
    similarity: float
    rank_score: Optional[float] = None   # RRF score (solo modalita ibrida)
    match_type: Optional[str]   = None   # "semantic" | "fulltext" | "both"
    metadata: Optional[dict]    = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    count: int
    search_mode: str   # "hybrid" | "hybrid+rerank" | "hybrid+expand" | "hybrid+expand+rerank" | "semantic"
    timestamp: str


class DocumentCreate(BaseModel):
    content: str = Field(..., min_length=10)
    metadata: Optional[dict] = None

    class Config:
        json_schema_extra = {
            "example": {
                "content": "FastAPI is a modern web framework for building APIs with Python",
                "metadata": {"category": "Web Framework", "source": "manual", "language": "en"}
            }
        }


class DocumentResponse(BaseModel):
    id: int
    content: str
    metadata: Optional[dict]
    created_at: str


class Document(BaseModel):
    id: int
    content: str
    metadata: Optional[dict]


class DocumentsListResponse(BaseModel):
    documents: List[Document]
    total: int
    limit: int
    offset: int


class StatsResponse(BaseModel):
    total_documents: int
    categories: dict
    embedding_dimension: int


class HealthResponse(BaseModel):
    status: str
    database: str
    bedrock: str
    timestamp: str


# --- Chat / RAG ---

class ChatRequest(BaseModel):
    question: str = Field(..., description="Domanda in linguaggio naturale", min_length=3)
    limit: int    = Field(5, description="Chunk di contesto da usare", ge=1, le=10)
    rerank: bool  = Field(
        True,
        description="Se True applica reranking LLM prima di passare il contesto al modello."
    )
    expand: bool  = Field(
        False,
        description="Se True espande la query con varianti prima del retrieval."
    )
    model_id: str = Field(
        "amazon.nova-lite-v1:0",
        description="Modello Bedrock"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Come funziona il machine learning?",
                "limit": 5
            }
        }


class ChatSource(BaseModel):
    id: int
    title: str
    url: Optional[str] = None
    similarity: float
    chunk_index: int


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: List[ChatSource]
    model_id: str
    context_chunks: int
    reranked: bool
    timestamp: str


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Pgvector Semantic Search API",
    description="Semantic search + RAG chat con PostgreSQL pgvector e AWS Bedrock",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# RAG Helper
# ============================================================================

def call_llm(question: str, context_chunks: list, model_id: str) -> str:
    """
    Chiama un LLM via Bedrock con il contesto recuperato da pgvector.

    Supporta:
    - Amazon Nova  (amazon.nova-*)
    - Anthropic Claude (anthropic.claude-*)

    Prompt design:
    - System: ruolo + regola "rispondi SOLO dal contesto"
    - User:   contesto numerato [1]...[N] + domanda
    - Il modello cita le fonti con [1], [2] ecc.
    """
    context_text = ""
    for i, chunk in enumerate(context_chunks, 1):
        title   = chunk.get("title", "Unknown")
        content = chunk["content"]
        context_text += f"[{i}] Fonte: {title}\n{content}\n\n"

    system_prompt = (
        "Sei un assistente esperto in AI, Machine Learning e Data Science. "
        "Rispondi alle domande basandoti ESCLUSIVAMENTE sui documenti forniti nel contesto. "
        "Se il contesto non contiene informazioni sufficienti, dillo esplicitamente senza inventare. "
        "Cita le fonti usando i numeri [1], [2] ecc. quando usi informazioni specifiche. "
        "Rispondi nella stessa lingua della domanda (italiano o inglese)."
    )

    user_message = (
        f"Contesto (documenti recuperati dal database):\n\n"
        f"{context_text}"
        f"---\n"
        f"Domanda: {question}\n\n"
        f"Rispondi in modo chiaro e completo basandoti sul contesto fornito."
    )

    bedrock = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "eu-north-1")
    )

    # Amazon Nova
    if model_id.startswith("amazon.nova"):
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": user_message}]}],
            "system":   [{"text": system_prompt}],
            "inferenceConfig": {"max_new_tokens": 1024, "temperature": 0.1}
        })
        response = bedrock.invoke_model(modelId=model_id, body=body)
        result   = json.loads(response["body"].read())
        return result["output"]["message"]["content"][0]["text"]

    # Anthropic Claude
    elif model_id.startswith("anthropic.claude"):
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "system":     system_prompt,
            "messages":   [{"role": "user", "content": user_message}]
        })
        response = bedrock.invoke_model(modelId=model_id, body=body)
        result   = json.loads(response["body"].read())
        return result["content"][0]["text"]

    else:
        raise ValueError(f"Modello non supportato: {model_id}. Usa amazon.nova-* o anthropic.claude-*")


# ============================================================================
# Hybrid Retrieval — Reciprocal Rank Fusion (RRF)
# ============================================================================

def hybrid_retrieve(query: str, query_embedding: list, limit: int) -> list:
    """
    Ricerca ibrida: combina risultati semantici (pgvector) e full-text (tsvector)
    usando Reciprocal Rank Fusion (RRF).

    Formula RRF: score(doc) = sum( 1 / (k + rank_i) )  con k=60 (standard)

    Flusso:
      1. Semantic: top-(limit*4) via cosine similarity pgvector
      2. Full-text: top-(limit*4) via ts_rank PostgreSQL (config 'simple')
      3. RRF: merge scores, ordina, restituisce top-limit

    Vantaggi rispetto a solo semantica:
      - Cattura query corte/keyword ("HNSW", "Adam optimizer") dove il
        full-text e superiore
      - Robusto su termini tecnici/nomi propri non ben rappresentati
        negli embedding space
    """
    conn = get_db_connection()
    cur  = conn.cursor()
    k    = 60          # RRF constant — standard value
    pool = limit * 4   # candidati iniziali per lista

    # --- Lista 1: Semantic (pgvector cosine) ---
    cur.execute(
        """
        SELECT id, content, metadata,
               1 - (embedding <=> %s::vector) AS score
        FROM documents
        ORDER BY score DESC
        LIMIT %s
        """,
        (query_embedding, pool)
    )
    semantic_rows = cur.fetchall()

    # --- Lista 2: Full-text (ts_rank su tsvector) ---
    # plainto_tsquery gestisce query multiparola senza operatori booleani
    # config 'simple' funziona per IT e EN senza stemming aggressivo
    cur.execute(
        """
        SELECT id, content, metadata,
               ts_rank(content_tsv, plainto_tsquery('simple', %s)) AS score
        FROM documents
        WHERE content_tsv @@ plainto_tsquery('simple', %s)
        ORDER BY score DESC
        LIMIT %s
        """,
        (query, query, pool)
    )
    fulltext_rows = cur.fetchall()
    cur.close()
    conn.close()

    # --- RRF Merge ---
    rrf_scores  = {}   # doc_id -> rrf_score
    doc_data    = {}   # doc_id -> (content, metadata, best_semantic_score)
    match_types = {}   # doc_id -> set of match types

    for rank, (doc_id, content, metadata, score) in enumerate(semantic_rows, start=1):
        rrf_scores[doc_id]  = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank)
        doc_data[doc_id]    = (content, metadata, float(score))
        match_types[doc_id] = {"semantic"}

    for rank, (doc_id, content, metadata, score) in enumerate(fulltext_rows, start=1):
        rrf_scores[doc_id]  = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank)
        match_types[doc_id] = match_types.get(doc_id, set()) | {"fulltext"}
        if doc_id not in doc_data:
            doc_data[doc_id] = (content, metadata, 0.0)

    # Ordina per RRF score decrescente
    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:limit]

    results = []
    for doc_id, rrf_score in ranked:
        content, metadata, sem_score = doc_data[doc_id]
        meta = metadata if isinstance(metadata, dict) else (json.loads(metadata) if metadata else {})
        mtype = match_types.get(doc_id, set())
        results.append({
            "id":         doc_id,
            "content":    content,
            "similarity": sem_score,
            "rank_score": round(rrf_score, 6),
            "match_type": "both" if len(mtype) == 2 else list(mtype)[0],
            "metadata":   meta,
        })
    return results



# ============================================================================
# Reranking -- LLM-based Cross-Encoder (Nova Micro)
# ============================================================================

def rerank_with_llm(query: str, candidates: list, top_k: int) -> list:
    """
    Reranking dei candidati con Nova Micro come cross-encoder leggero.

    Flusso:
    - Invia query + tutti i chunk numerati in UNA sola chiamata Bedrock
    - Nova Micro restituisce un array JSON di indici ordinati per rilevanza
    - Riordina candidates secondo quegli indici, ritorna top_k

    Vantaggi sul solo RRF:
    - Capisce il significato della query (sinonimi, parafrasi, contesto)
    - Disambigua query ambigue
    - Usa Nova Micro (modello piu leggero) per minimizzare latenza e costo

    Fallback silenzioso: se la chiamata LLM fallisce, ritorna
    i candidati nell ordine RRF originale senza errori.
    """
    import re as _re

    if not candidates:
        return candidates

    chunks_text = ""
    for i, c in enumerate(candidates):
        snippet = c["content"][:300].replace("\n", " ").strip()
        chunks_text += f"[{i}] {snippet}\n\n"

    prompt = (
        f'You are a relevance ranking assistant.\n\n'
        f'Query: "{query}"\n\n'
        f'Below are {len(candidates)} text chunks labeled [0] to [{len(candidates)-1}].\n'
        f'Return ONLY a JSON array of indices ordered from MOST to LEAST relevant.\n'
        f'Include ALL indices. Example: [3, 0, 7, 1, 2]\n\n'
        f'Chunks:\n{chunks_text}\n'
        f'Return only the JSON array, nothing else.'
    )

    try:
        bedrock = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_REGION", "eu-north-1")
        )
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"max_new_tokens": 256, "temperature": 0.0}
        })
        response   = bedrock.invoke_model(modelId="amazon.nova-micro-v1:0", body=body)
        raw        = json.loads(response["body"].read())
        raw_text   = raw["output"]["message"]["content"][0]["text"].strip()

        match = _re.search(r'\[([\d,\s]+)\]', raw_text)
        if not match:
            return candidates[:top_k]

        indices = [int(x.strip()) for x in match.group(1).split(",") if x.strip().isdigit()]

        seen, valid = set(), []
        for idx in indices:
            if 0 <= idx < len(candidates) and idx not in seen:
                valid.append(idx)
                seen.add(idx)
        for i in range(len(candidates)):
            if i not in seen:
                valid.append(i)

        return [candidates[i] for i in valid][:top_k]

    except Exception:
        return candidates[:top_k]



# ============================================================================
# Query Expansion -- genera varianti della query con Nova Micro
# ============================================================================

def expand_query(query: str) -> list:
    """
    Genera 3 riformulazioni della query originale usando Nova Micro.

    Obiettivo: aumentare la copertura semantica del retrieval catturando
    documenti rilevanti che usano terminologia diversa dalla query originale.

    Esempi:
      "backpropagation gradient descent"
        → "how neural networks learn using chain rule"
        → "weight update algorithm in deep learning training"
        → "error propagation optimization for neural network weights"

    Ritorna: [query_originale, variante1, variante2, variante3]
    Fallback: se la chiamata LLM fallisce, ritorna solo [query_originale]
    """
    prompt = (
        f'Generate 3 alternative phrasings of this search query that cover different\n'
        f'aspects and terminology, to maximize document retrieval coverage.\n\n'
        f'Original query: "{query}"\n\n'
        f'Return ONLY a JSON array of 3 strings, no explanation.\n'
        f'Example: ["phrasing 1", "phrasing 2", "phrasing 3"]\n'
        f'The phrasings should be in the same language as the original query.'
    )

    try:
        import re as _re
        bedrock = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_REGION", "eu-north-1")
        )
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"max_new_tokens": 128, "temperature": 0.7}
        })
        response = bedrock.invoke_model(modelId="amazon.nova-micro-v1:0", body=body)
        raw      = json.loads(response["body"].read())
        text     = raw["output"]["message"]["content"][0]["text"].strip()

        # Estrai array JSON dalla risposta
        match = _re.search(r'\[(.+?)\]', text, _re.DOTALL)
        if not match:
            return [query]

        # Parse manuale robusto: split su virgole tra virgolette
        inner   = match.group(1)
        strings = _re.findall(r'"([^"]+)"', inner)

        if not strings:
            return [query]

        # Rimuovi duplicati e la query originale se presente, poi anteponi originale
        seen = {query.lower()}
        variants = []
        for s in strings[:3]:
            if s.lower() not in seen:
                variants.append(s)
                seen.add(s.lower())

        return [query] + variants

    except Exception:
        return [query]


def hybrid_retrieve_expanded(query: str, query_embedding: list,
                              limit: int, n_variants: int = 3) -> list:
    """
    Retrieval ibrido con query expansion.

    Flusso:
    1. Genera N varianti della query con expand_query()
    2. Per ogni variante genera embedding e esegue hybrid_retrieve() con pool ridotto
    3. Applica RRF su tutte le liste combinate (originale + varianti)
    4. Ritorna top-limit risultati unificati

    Il pool per variante e ridotto (limit*2 invece di limit*4) per bilanciare
    il numero totale di candidati e la latenza aggiuntiva.
    """
    queries = expand_query(query)

    # Genera embedding per le varianti (la query originale ce l ha gia)
    embeddings = [query_embedding]
    bedrock_emb = boto3.client(
        "bedrock-runtime",
        region_name=os.environ.get("AWS_REGION", "eu-north-1")
    )
    for variant in queries[1:]:
        try:
            emb = get_embedding(variant)
            embeddings.append(emb)
        except Exception:
            pass  # Salta la variante se embedding fallisce

    # Retrieval per ogni query (pool piu piccolo per bilanciare latenza)
    pool_per_query = max(limit * 2, 10)
    all_lists      = []

    conn = get_db_connection()
    cur  = conn.cursor()

    for i, (q, emb) in enumerate(zip(queries, embeddings)):
        k = 60

        # Semantic
        cur.execute(
            """
            SELECT id, content, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM documents
            ORDER BY score DESC
            LIMIT %s
            """,
            (emb, pool_per_query)
        )
        sem_rows = cur.fetchall()

        # Full-text
        cur.execute(
            """
            SELECT id, content, metadata,
                   ts_rank(content_tsv, plainto_tsquery('simple', %s)) AS score
            FROM documents
            WHERE content_tsv @@ plainto_tsquery('simple', %s)
            ORDER BY score DESC
            LIMIT %s
            """,
            (q, q, pool_per_query)
        )
        ft_rows = cur.fetchall()

        # RRF per questa query
        rrf_q = {}
        doc_q = {}
        match_q = {}

        for rank, (doc_id, content, metadata, score) in enumerate(sem_rows, 1):
            rrf_q[doc_id]   = rrf_q.get(doc_id, 0.0) + 1.0 / (k + rank)
            doc_q[doc_id]   = (content, metadata, float(score))
            match_q[doc_id] = {"semantic"}

        for rank, (doc_id, content, metadata, score) in enumerate(ft_rows, 1):
            rrf_q[doc_id]   = rrf_q.get(doc_id, 0.0) + 1.0 / (k + rank)
            match_q[doc_id] = match_q.get(doc_id, set()) | {"fulltext"}
            if doc_id not in doc_q:
                doc_q[doc_id] = (content, metadata, 0.0)

        all_lists.append((rrf_q, doc_q, match_q))

    cur.close()
    conn.close()

    # Merge RRF globale su tutte le liste
    # Peso leggermente maggiore alla query originale (lista 0)
    weights = [1.0] + [0.8] * (len(all_lists) - 1)
    global_rrf  = {}
    global_data = {}
    global_match = {}

    for (rrf_q, doc_q, match_q), w in zip(all_lists, weights):
        # Converti i punteggi RRF di questa lista in ranking, poi applica RRF globale
        ranked = sorted(rrf_q.items(), key=lambda x: x[1], reverse=True)
        for rank, (doc_id, _) in enumerate(ranked, 1):
            global_rrf[doc_id]  = global_rrf.get(doc_id, 0.0) + w / (60 + rank)
            global_match[doc_id] = global_match.get(doc_id, set()) | match_q.get(doc_id, set())
            if doc_id not in global_data:
                global_data[doc_id] = doc_q[doc_id]

    # Top-limit finale
    ranked_final = sorted(global_rrf.items(), key=lambda x: x[1], reverse=True)[:limit]
    results = []
    for doc_id, rrf_score in ranked_final:
        content, metadata, sem_score = global_data[doc_id]
        meta  = metadata if isinstance(metadata, dict) else (json.loads(metadata) if metadata else {})
        mtype = global_match.get(doc_id, set())
        results.append({
            "id":         doc_id,
            "content":    content,
            "similarity": sem_score,
            "rank_score": round(rrf_score, 6),
            "match_type": "both" if len(mtype) == 2 else list(mtype)[0],
            "metadata":   meta,
        })
    return results


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/", response_class=HTMLResponse, tags=["General"])
async def root():
    """Serve la Chat UI."""
    ui_path = Path(__file__).parent / "chat_ui.html"
    if ui_path.exists():
        return HTMLResponse(content=ui_path.read_text(encoding="utf-8"))
    # Fallback JSON se il file non esiste
    return HTMLResponse(content="<h1>Chat UI not found — make sure chat_ui.html is in the same folder as api.py</h1>", status_code=404)


@app.get("/dashboard", response_class=HTMLResponse, tags=["General"])
async def dashboard():
    """Serve il RAG Evaluation Dashboard."""
    ui_path = Path(__file__).parent / "rag_eval_dashboard.html"
    if ui_path.exists():
        return HTMLResponse(content=ui_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Dashboard not found — make sure rag_eval_dashboard.html is present</h1>", status_code=404)


@app.get("/ping", tags=["General"])
async def ping():
    return {"status": "ok"}


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    db_status      = "unknown"
    bedrock_status = "unknown"

    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    try:
        test_emb = get_embedding("test")
        bedrock_status = "available" if len(test_emb) == EMBEDDING_DIMENSION else f"error: wrong dim {len(test_emb)}"
    except Exception as e:
        bedrock_status = f"error: {str(e)}"

    overall = "healthy" if db_status == "connected" and bedrock_status == "available" else "degraded"
    return {"status": overall, "database": db_status, "bedrock": bedrock_status,
            "timestamp": datetime.utcnow().isoformat()}


@app.post("/search", response_model=SearchResponse, tags=["Search"])
async def search_documents(request: SearchRequest):
    """
    Ricerca documenti.

    - **hybrid=true** (default): combina ricerca semantica (pgvector cosine) e
      full-text (PostgreSQL tsvector) via Reciprocal Rank Fusion. Ottimale per
      query miste testo/keyword.
    - **hybrid=false**: solo ricerca semantica pgvector. Piu veloce, preferibile
      per query in linguaggio naturale puro.

    Il campo **match_type** nel risultato indica se il documento e stato trovato
    da "semantic", "fulltext" o "both".
    """
    try:
        query_embedding = get_embedding(request.query)

        if request.hybrid:
            if request.expand:
                results = hybrid_retrieve_expanded(
                    request.query, query_embedding, request.limit
                )
                mode = "hybrid+expand"
            else:
                results = hybrid_retrieve(request.query, query_embedding, request.limit)
                mode    = "hybrid"
        else:
            conn = get_db_connection()
            cur  = conn.cursor()
            cur.execute(
                """
                SELECT id, content, metadata,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM documents
                ORDER BY similarity DESC
                LIMIT %s
                """,
                (query_embedding, request.limit)
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
            results = [
                {
                    "id":         doc_id,
                    "content":    content,
                    "similarity": float(similarity),
                    "rank_score": None,
                    "match_type": "semantic",
                    "metadata":   metadata if isinstance(metadata, dict) else (json.loads(metadata) if metadata else None)
                }
                for doc_id, content, metadata, similarity in rows
            ]
            mode = "semantic"

        # Reranking opzionale
        if request.rerank and results:
            results = rerank_with_llm(request.query, results, request.limit)
            mode    = mode + "+rerank"

        return {
            "query":       request.query,
            "results":     results,
            "count":       len(results),
            "search_mode": mode,
            "timestamp":   datetime.utcnow().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Errore ricerca: {str(e)}")


@app.post("/chat", tags=["Chat"])
async def chat(request: ChatRequest):
    """
    RAG Chat -- risponde a domande in linguaggio naturale usando i documenti nel DB.

    Flusso:
    1. Embedding della domanda
    2. Recupera i chunk piu simili via pgvector
    3. Passa contesto + domanda a Claude 3 Haiku via Bedrock
    4. Ritorna risposta strutturata + fonti

    - **question**: Domanda in IT o EN
    - **limit**: Numero di chunk di contesto (default 5, max 10)
    - **model_id**: Modello Bedrock da usare
    """
    try:
        # Step 1 -- embedding domanda
        query_embedding = get_embedding(request.question)

        # Step 2 -- recupera chunk rilevanti (hybrid + opzionale query expansion)
        if request.expand:
            rows = hybrid_retrieve_expanded(
                request.question, query_embedding, request.limit
            )
        else:
            rows = hybrid_retrieve(request.question, query_embedding, request.limit)

        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nessun documento nel DB. Esegui prima populate_db.py."
            )

        context_chunks = []
        sources        = []

        for row in rows:
            doc_id   = row["id"]
            content  = row["content"]
            meta     = row["metadata"] or {}
            sim      = row["similarity"]
            context_chunks.append({
                "content":    content,
                "title":      meta.get("title", "Unknown"),
                "url":        meta.get("url"),
                "similarity": sim,
            })
            sources.append(ChatSource(
                id          = doc_id,
                title       = meta.get("title", "Unknown"),
                url         = meta.get("url"),
                similarity  = sim,
                chunk_index = meta.get("chunk_index", 0),
            ))

        # Step 3 -- Reranking opzionale
        if request.rerank and len(rows) > 1:
            rows = rerank_with_llm(request.question, rows, len(rows))
            context_chunks, sources = [], []
            for row in rows:
                meta = row["metadata"] or {}
                context_chunks.append({
                    "content":    row["content"],
                    "title":      meta.get("title", "Unknown"),
                    "url":        meta.get("url"),
                    "similarity": row["similarity"],
                })
                sources.append(ChatSource(
                    id          = row["id"],
                    title       = meta.get("title", "Unknown"),
                    url         = meta.get("url"),
                    similarity  = row["similarity"],
                    chunk_index = meta.get("chunk_index", 0),
                ))

        # Step 4 -- LLM RAG
        answer = call_llm(request.question, context_chunks, request.model_id)

        return ChatResponse(
            question       = request.question,
            answer         = answer,
            sources        = sources,
            model_id       = request.model_id,
            context_chunks = len(context_chunks),
            reranked       = request.rerank,
            timestamp      = datetime.utcnow().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Errore chat: {str(e)}")


@app.post("/documents", response_model=DocumentResponse,
          status_code=status.HTTP_201_CREATED, tags=["Documents"])
async def create_document(document: DocumentCreate):
    """Crea un nuovo documento con embedding."""
    try:
        embedding = get_embedding(document.content)
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute(
            """
            INSERT INTO documents (content, embedding, metadata, created_at)
            VALUES (%s, %s, %s, NOW())
            RETURNING id, created_at
            """,
            (document.content, embedding,
             json.dumps(document.metadata) if document.metadata else None)
        )
        doc_id, created_at = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return {"id": doc_id, "content": document.content,
                "metadata": document.metadata, "created_at": created_at.isoformat()}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Errore creazione documento: {str(e)}")


@app.get("/documents", response_model=DocumentsListResponse, tags=["Documents"])
async def list_documents(limit: int = 10, offset: int = 0, category: Optional[str] = None):
    """Lista documenti paginata, con filtro opzionale per categoria."""
    if limit > 100:
        limit = 100
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        if category:
            cur.execute("SELECT COUNT(*) FROM documents WHERE metadata->>'category' = %s", (category,))
        else:
            cur.execute("SELECT COUNT(*) FROM documents")
        total = cur.fetchone()[0]

        if category:
            cur.execute(
                "SELECT id, content, metadata FROM documents "
                "WHERE metadata->>'category' = %s ORDER BY id DESC LIMIT %s OFFSET %s",
                (category, limit, offset)
            )
        else:
            cur.execute(
                "SELECT id, content, metadata FROM documents ORDER BY id DESC LIMIT %s OFFSET %s",
                (limit, offset)
            )
        documents = [
            {"id": doc_id, "content": content,
             "metadata": metadata if isinstance(metadata, dict) else (json.loads(metadata) if metadata else None)}
            for doc_id, content, metadata in cur.fetchall()
        ]
        cur.close()
        conn.close()
        return {"documents": documents, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Errore recupero documenti: {str(e)}")


@app.get("/stats", response_model=StatsResponse, tags=["Stats"])
async def get_stats():
    """Statistiche: totale documenti, categorie, dimensione embedding."""
    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM documents")
        total = cur.fetchone()[0]
        cur.execute("""
            SELECT metadata->>'category' AS category, COUNT(*) AS count
            FROM documents
            WHERE metadata IS NOT NULL AND metadata->>'category' IS NOT NULL
            GROUP BY category ORDER BY count DESC
        """)
        categories = {cat: count for cat, count in cur.fetchall() if cat}
        cur.close()
        conn.close()
        return {"total_documents": total, "categories": categories,
                "embedding_dimension": EMBEDDING_DIMENSION}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Errore statistiche: {str(e)}")


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

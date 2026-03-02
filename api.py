#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI REST API per semantic search + RAG chat con pgvector + AWS Bedrock
"""
import json
import os
from datetime import datetime
from typing import List, Optional

import boto3
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import get_db_connection, EMBEDDING_DIMENSION
from embeddings import get_embedding


# ============================================================================
# Pydantic Models
# ============================================================================

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(5, ge=1, le=50)

    class Config:
        json_schema_extra = {"example": {"query": "machine learning", "limit": 5}}


class SearchResult(BaseModel):
    id: int
    content: str
    similarity: float
    metadata: Optional[dict] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    count: int
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
# Endpoints
# ============================================================================

@app.get("/", tags=["General"])
async def root():
    return {
        "name": "Pgvector Semantic Search API",
        "version": "2.0.0",
        "endpoints": {
            "docs":      "/docs",
            "health":    "/health",
            "search":    "POST /search",
            "chat":      "POST /chat",
            "documents": "GET/POST /documents",
            "stats":     "GET /stats"
        }
    }


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
    """Ricerca semantic tramite similarita coseno (pgvector <=>)."""
    try:
        query_embedding = get_embedding(request.query)
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
                "metadata":   metadata if isinstance(metadata, dict) else (json.loads(metadata) if metadata else None)
            }
            for doc_id, content, metadata, similarity in rows
        ]
        return {"query": request.query, "results": results, "count": len(results),
                "timestamp": datetime.utcnow().isoformat()}

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

        # Step 2 -- chunk piu rilevanti
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

        if not rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nessun documento nel DB. Esegui prima populate_db.py."
            )

        context_chunks = []
        sources        = []

        for doc_id, content, metadata, similarity in rows:
            meta = metadata if isinstance(metadata, dict) else (json.loads(metadata) if metadata else {})
            context_chunks.append({
                "content":    content,
                "title":      meta.get("title", "Unknown"),
                "url":        meta.get("url"),
                "similarity": float(similarity),
            })
            sources.append(ChatSource(
                id          = doc_id,
                title       = meta.get("title", "Unknown"),
                url         = meta.get("url"),
                similarity  = float(similarity),
                chunk_index = meta.get("chunk_index", 0),
            ))

        # Step 3 -- LLM RAG
        answer = call_llm(request.question, context_chunks, request.model_id)

        return ChatResponse(
            question       = request.question,
            answer         = answer,
            sources        = sources,
            model_id       = request.model_id,
            context_chunks = len(context_chunks),
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

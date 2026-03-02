#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI REST API per semantic search con pgvector + AWS Bedrock
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import json
from datetime import datetime

from config import get_db_connection, EMBEDDING_DIMENSION
from embeddings import get_embedding


# ============================================================================
# Pydantic Models (Request/Response)
# ============================================================================

class SearchRequest(BaseModel):
    """Request per ricerca semantic"""
    query: str = Field(..., description="Testo della query di ricerca", min_length=1)
    limit: int = Field(5, description="Numero massimo di risultati", ge=1, le=50)

    class Config:
        json_schema_extra = {
            "example": {
                "query": "machine learning",
                "limit": 5
            }
        }


class SearchResult(BaseModel):
    """Singolo risultato di ricerca"""
    id: int
    content: str
    similarity: float
    metadata: Optional[dict] = None


class SearchResponse(BaseModel):
    """Response della ricerca"""
    query: str
    results: List[SearchResult]
    count: int
    timestamp: str


class DocumentCreate(BaseModel):
    """Request per creare nuovo documento"""
    content: str = Field(..., description="Contenuto testuale del documento", min_length=10)
    metadata: Optional[dict] = Field(None, description="Metadata opzionali (categoria, source, etc)")

    class Config:
        json_schema_extra = {
            "example": {
                "content": "FastAPI is a modern, fast web framework for building APIs with Python",
                "metadata": {
                    "category": "Web Framework",
                    "source": "manual",
                    "language": "en"
                }
            }
        }


class DocumentResponse(BaseModel):
    """Response dopo creazione documento"""
    id: int
    content: str
    metadata: Optional[dict]
    created_at: str


class Document(BaseModel):
    """Documento nel database"""
    id: int
    content: str
    metadata: Optional[dict]


class DocumentsListResponse(BaseModel):
    """Lista documenti"""
    documents: List[Document]
    total: int
    limit: int
    offset: int


class StatsResponse(BaseModel):
    """Statistiche database"""
    total_documents: int
    categories: dict
    embedding_dimension: int


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    database: str
    bedrock: str
    timestamp: str


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="Pgvector Semantic Search API",
    description="REST API per semantic search usando PostgreSQL pgvector e AWS Bedrock Titan Embeddings",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS (per permettere chiamate da frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In produzione: specifica domini precisi
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/", tags=["General"])
async def root():
    """Root endpoint con info API"""
    return {
        "name": "Pgvector Semantic Search API",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "search": "POST /search",
            "documents": "GET/POST /documents",
            "stats": "GET /stats"
        }
    }

@app.get("/ping", tags=["General"])
async def ping():
    return {"status": "ok"}

@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """Health check — verifica connessione a database e Bedrock"""
    db_status = "unknown"
    bedrock_status = "unknown"

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    try:
        test_emb = get_embedding("test")
        if len(test_emb) == EMBEDDING_DIMENSION:
            bedrock_status = "available"
        else:
            bedrock_status = f"error: wrong dimension {len(test_emb)}"
    except Exception as e:
        bedrock_status = f"error: {str(e)}"

    overall_status = "healthy" if db_status == "connected" and bedrock_status == "available" else "degraded"

    return {
        "status": overall_status,
        "database": db_status,
        "bedrock": bedrock_status,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/search", response_model=SearchResponse, tags=["Search"])
async def search_documents(request: SearchRequest):
    """
    Ricerca semantic di documenti

    - **query**: Testo della query di ricerca
    - **limit**: Numero massimo di risultati (default: 5, max: 50)

    Ritorna i documenti più simili ordinati per similarità coseno, calcolata
    direttamente in PostgreSQL tramite l'operatore pgvector <=>
    """
    try:
        # Genera embedding della query
        query_embedding = get_embedding(request.query)

        # Query pgvector: <=> = cosine distance → similarity = 1 - distance
        conn = get_db_connection()  # register_vector già chiamato qui
        cur = conn.cursor()
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
                "id": doc_id,
                "content": content,
                "similarity": float(similarity),
                "metadata": metadata if isinstance(metadata, dict) else (json.loads(metadata) if metadata else None)
            }
            for doc_id, content, metadata, similarity in rows
        ]

        return {
            "query": request.query,
            "results": results,
            "count": len(results),
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante la ricerca: {str(e)}"
        )


@app.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED, tags=["Documents"])
async def create_document(document: DocumentCreate):
    """
    Crea un nuovo documento con embedding

    - **content**: Testo del documento (minimo 10 caratteri)
    - **metadata**: Metadata opzionali (categoria, source, language, etc)
    """
    try:
        embedding = get_embedding(document.content)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO documents (content, embedding, metadata, created_at)
            VALUES (%s, %s, %s, NOW())
            RETURNING id, created_at
            """,
            (
                document.content,
                embedding,
                json.dumps(document.metadata) if document.metadata else None
            )
        )
        doc_id, created_at = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()

        return {
            "id": doc_id,
            "content": document.content,
            "metadata": document.metadata,
            "created_at": created_at.isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante la creazione del documento: {str(e)}"
        )


@app.get("/documents", response_model=DocumentsListResponse, tags=["Documents"])
async def list_documents(
    limit: int = 10,
    offset: int = 0,
    category: Optional[str] = None
):
    """
    Lista documenti nel database

    - **limit**: Numero massimo di documenti (default: 10, max: 100)
    - **offset**: Offset per paginazione (default: 0)
    - **category**: Filtra per categoria (opzionale)
    """
    if limit > 100:
        limit = 100

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if category:
            cur.execute(
                "SELECT COUNT(*) FROM documents WHERE metadata->>'category' = %s",
                (category,)
            )
        else:
            cur.execute("SELECT COUNT(*) FROM documents")
        total = cur.fetchone()[0]

        if category:
            cur.execute(
                """
                SELECT id, content, metadata
                FROM documents
                WHERE metadata->>'category' = %s
                ORDER BY id DESC
                LIMIT %s OFFSET %s
                """,
                (category, limit, offset)
            )
        else:
            cur.execute(
                """
                SELECT id, content, metadata
                FROM documents
                ORDER BY id DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset)
            )

        documents = [
            {
                "id": doc_id,
                "content": content,
                "metadata": metadata if isinstance(metadata, dict) else (json.loads(metadata) if metadata else None)
            }
            for doc_id, content, metadata in cur.fetchall()
        ]

        cur.close()
        conn.close()

        return {
            "documents": documents,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante il recupero dei documenti: {str(e)}"
        )


@app.get("/stats", response_model=StatsResponse, tags=["Stats"])
async def get_stats():
    """Statistiche sul database — totale documenti, categorie, dimensione embedding"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM documents")
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT metadata->>'category' AS category, COUNT(*) AS count
            FROM documents
            WHERE metadata IS NOT NULL AND metadata->>'category' IS NOT NULL
            GROUP BY category
            ORDER BY count DESC
        """)
        categories = {cat: count for cat, count in cur.fetchall() if cat}

        cur.close()
        conn.close()

        return {
            "total_documents": total,
            "categories": categories,
            "embedding_dimension": EMBEDDING_DIMENSION
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante il recupero delle statistiche: {str(e)}"
        )


# ============================================================================
# Main (per test locale)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test suite per FastAPI endpoints
Esegui: pytest tests/test_api.py -v
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

# Aggiungi parent directory al path per importare api
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api import app

# Test client
client = TestClient(app)


# ============================================================================
# Test Endpoints Generali
# ============================================================================

def test_root():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert "version" in data  # verifica solo che il campo esista
    assert "endpoints" in data  # verifica solo che il campo esista


def test_health():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "bedrock" in data
    assert data["status"] in ["healthy", "degraded"]


def test_docs():
    """Test che Swagger UI sia accessibile"""
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi():
    """Test OpenAPI schema"""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "info" in data
    assert data["info"]["title"] == "Pgvector Semantic Search API"


# ============================================================================
# Test Stats Endpoint
# ============================================================================

def test_stats():
    """Test stats endpoint"""
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_documents" in data
    assert "categories" in data
    assert "embedding_dimension" in data
    assert isinstance(data["total_documents"], int)
    assert data["total_documents"] >= 0
    assert data["embedding_dimension"] == 1024


# ============================================================================
# Test Documents Endpoints
# ============================================================================

def test_list_documents_default():
    """Test lista documenti con parametri default"""
    response = client.get("/documents")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert isinstance(data["documents"], list)


def test_list_documents_with_limit():
    """Test lista documenti con limite custom"""
    response = client.get("/documents?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["documents"]) <= 5
    assert data["limit"] == 5


def test_list_documents_with_offset():
    """Test lista documenti con offset"""
    response = client.get("/documents?offset=10")
    assert response.status_code == 200
    data = response.json()
    assert data["offset"] == 10


def test_list_documents_max_limit():
    """Test che il limite massimo sia 100"""
    response = client.get("/documents?limit=200")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 100  # Capped at 100


def test_create_document():
    """Test creazione nuovo documento"""
    new_doc = {
        "content": "This is a test document for the API testing suite",
        "metadata": {
            "category": "Test",
            "source": "pytest",
            "language": "en"
        }
    }
    
    response = client.post("/documents", json=new_doc)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert "content" in data
    assert "metadata" in data
    assert "created_at" in data
    assert data["content"] == new_doc["content"]
    assert data["metadata"]["category"] == "Test"


def test_create_document_without_metadata():
    """Test creazione documento senza metadata"""
    new_doc = {
        "content": "Test document without metadata for pytest suite"
    }
    
    response = client.post("/documents", json=new_doc)
    assert response.status_code == 201
    data = response.json()
    assert data["metadata"] is None


def test_create_document_validation_short_content():
    """Test che contenuto troppo corto venga rifiutato"""
    new_doc = {
        "content": "Short"  # Meno di 10 caratteri
    }
    
    response = client.post("/documents", json=new_doc)
    assert response.status_code == 422  # Validation error


def test_create_document_validation_missing_content():
    """Test che documento senza content venga rifiutato"""
    new_doc = {
        "metadata": {"test": "value"}
    }
    
    response = client.post("/documents", json=new_doc)
    assert response.status_code == 422


# ============================================================================
# Test Search Endpoint
# ============================================================================

def test_search_basic():
    """Test ricerca base"""
    search_request = {
        "query": "machine learning",
        "limit": 5
    }
    
    response = client.post("/search", json=search_request)
    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert "results" in data
    assert "count" in data
    assert "timestamp" in data
    assert data["query"] == "machine learning"
    assert isinstance(data["results"], list)
    assert len(data["results"]) <= 5


def test_search_single_result():
    """Test ricerca con limite 1"""
    search_request = {
        "query": "neural networks",
        "limit": 1
    }
    
    response = client.post("/search", json=search_request)
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) <= 1


def test_search_results_structure():
    """Test struttura risultati ricerca"""
    search_request = {
        "query": "python programming",
        "limit": 3
    }
    
    response = client.post("/search", json=search_request)
    assert response.status_code == 200
    data = response.json()
    
    if len(data["results"]) > 0:
        result = data["results"][0]
        assert "id" in result
        assert "content" in result
        assert "similarity" in result
        assert isinstance(result["similarity"], float)
        assert 0.0 <= result["similarity"] <= 1.0


def test_search_similarity_ordering():
    """Test che i risultati siano ordinati per similarità"""
    search_request = {
        "query": "artificial intelligence",
        "limit": 5
    }
    
    response = client.post("/search", json=search_request)
    assert response.status_code == 200
    data = response.json()
    
    if len(data["results"]) > 1:
        similarities = [r["similarity"] for r in data["results"]]
        # Verifica che sia ordinato dal più alto al più basso
        assert similarities == sorted(similarities, reverse=True)


def test_search_validation_empty_query():
    """Test che query vuota venga rifiutata"""
    search_request = {
        "query": "",
        "limit": 5
    }
    
    response = client.post("/search", json=search_request)
    assert response.status_code == 422


def test_search_validation_missing_query():
    """Test che richiesta senza query venga rifiutata"""
    search_request = {
        "limit": 5
    }
    
    response = client.post("/search", json=search_request)
    assert response.status_code == 422


def test_search_limit_validation():
    """Test validazione limiti di ricerca"""
    # Limite troppo basso
    search_request = {"query": "test", "limit": 0}
    response = client.post("/search", json=search_request)
    assert response.status_code == 422
    
    # Limite troppo alto (max 50)
    search_request = {"query": "test", "limit": 100}
    response = client.post("/search", json=search_request)
    assert response.status_code == 422


# ============================================================================
# Test Integration
# ============================================================================

def test_create_and_search_document():
    """Test integrazione: crea documento e poi cercalo"""
    # Crea documento unico
    unique_content = "PostgreSQL is the best open source database for semantic search with pgvector extension"
    new_doc = {
        "content": unique_content,
        "metadata": {"category": "Integration Test"}
    }
    
    create_response = client.post("/documents", json=new_doc)
    assert create_response.status_code == 201
    created_doc = create_response.json()
    
    # Cerca il documento appena creato
    search_request = {
        "query": "PostgreSQL pgvector semantic search",
        "limit": 5
    }
    
    search_response = client.post("/search", json=search_request)
    assert search_response.status_code == 200
    search_data = search_response.json()
    
    # Verifica che il documento creato sia tra i risultati
    doc_ids = [r["id"] for r in search_data["results"]]
    assert created_doc["id"] in doc_ids


# ============================================================================
# Test Performance / Load
# ============================================================================

def test_multiple_searches():
    """Test prestazioni con ricerche multiple"""
    queries = [
        "machine learning",
        "neural networks",
        "cloud computing",
        "database systems",
        "python programming"
    ]
    
    for query in queries:
        response = client.post("/search", json={"query": query, "limit": 5})
        assert response.status_code == 200


# ============================================================================
# Main (per eseguire con python test_api.py)
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

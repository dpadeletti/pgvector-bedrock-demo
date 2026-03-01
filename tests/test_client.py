#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Client Python interattivo per testare l'API
Uso: python tests/test_client.py
"""
import requests
import json
from typing import Optional, Dict, List


class APIClient:
    """Client per interagire con l'API Pgvector Semantic Search"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def health_check(self) -> dict:
        """Check health dell'API"""
        response = self.session.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def get_stats(self) -> dict:
        """Ottieni statistiche database"""
        response = self.session.get(f"{self.base_url}/stats")
        response.raise_for_status()
        return response.json()
    
    def search(self, query: str, limit: int = 5) -> dict:
        """
        Ricerca semantic
        
        Args:
            query: Testo da cercare
            limit: Numero massimo risultati
        """
        response = self.session.post(
            f"{self.base_url}/search",
            json={"query": query, "limit": limit}
        )
        response.raise_for_status()
        return response.json()
    
    def create_document(self, content: str, metadata: Optional[dict] = None) -> dict:
        """
        Crea nuovo documento
        
        Args:
            content: Contenuto del documento
            metadata: Metadata opzionali
        """
        data = {"content": content}
        if metadata:
            data["metadata"] = metadata
        
        response = self.session.post(
            f"{self.base_url}/documents",
            json=data
        )
        response.raise_for_status()
        return response.json()
    
    def list_documents(self, limit: int = 10, offset: int = 0, category: Optional[str] = None) -> dict:
        """
        Lista documenti
        
        Args:
            limit: Numero documenti da recuperare
            offset: Offset per paginazione
            category: Filtra per categoria (opzionale)
        """
        params = {"limit": limit, "offset": offset}
        if category:
            params["category"] = category
        
        response = self.session.get(
            f"{self.base_url}/documents",
            params=params
        )
        response.raise_for_status()
        return response.json()


# ============================================================================
# Test Functions
# ============================================================================

def print_section(title: str):
    """Print sezione colorata"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_health(client: APIClient):
    """Test health check"""
    print_section("TEST: Health Check")
    result = client.health_check()
    print(json.dumps(result, indent=2))
    
    if result["status"] == "healthy":
        print("\n✅ API is healthy!")
    else:
        print("\n⚠️  API is degraded")


def test_stats(client: APIClient):
    """Test statistiche"""
    print_section("TEST: Statistiche Database")
    result = client.get_stats()
    print(json.dumps(result, indent=2))
    print(f"\n📊 Totale documenti: {result['total_documents']}")
    print(f"📏 Embedding dimension: {result['embedding_dimension']}")


def test_search(client: APIClient):
    """Test ricerca"""
    print_section("TEST: Ricerca Semantic")
    
    queries = [
        "machine learning",
        "neural networks",
        "cloud computing"
    ]
    
    for query in queries:
        print(f"\n🔍 Query: '{query}'")
        result = client.search(query, limit=3)
        
        print(f"   Trovati {result['count']} risultati:")
        for i, doc in enumerate(result['results'], 1):
            print(f"   {i}. [Similarità: {doc['similarity']:.3f}] {doc['content'][:80]}...")


def test_create_document(client: APIClient):
    """Test creazione documento"""
    print_section("TEST: Creazione Documento")
    
    content = "Docker is a platform for developing, shipping, and running applications in containers"
    metadata = {
        "category": "DevOps",
        "source": "test_client",
        "language": "en"
    }
    
    result = client.create_document(content, metadata)
    print(json.dumps(result, indent=2))
    print(f"\n✅ Documento creato con ID: {result['id']}")


def test_list_documents(client: APIClient):
    """Test lista documenti"""
    print_section("TEST: Lista Documenti")
    
    result = client.list_documents(limit=5)
    print(f"Totale documenti nel DB: {result['total']}")
    print(f"Mostrati: {len(result['documents'])}\n")
    
    for i, doc in enumerate(result['documents'], 1):
        category = doc['metadata'].get('category', 'N/A') if doc['metadata'] else 'N/A'
        print(f"{i}. [ID: {doc['id']}] [{category}] {doc['content'][:80]}...")


def test_integration(client: APIClient):
    """Test integrazione: crea e cerca"""
    print_section("TEST: Integrazione (Crea + Cerca)")
    
    # Crea documento unico
    content = "Kubernetes is an open-source container orchestration platform for automating deployment and scaling"
    print(f"1. Creo documento: '{content[:50]}...'")
    
    created = client.create_document(content, {"category": "Container Orchestration"})
    print(f"   ✅ Creato con ID: {created['id']}")
    
    # Cerca il documento
    print(f"\n2. Cerco: 'kubernetes container orchestration'")
    search_result = client.search("kubernetes container orchestration", limit=5)
    
    # Verifica che sia nei risultati
    found = False
    for i, doc in enumerate(search_result['results'], 1):
        if doc['id'] == created['id']:
            print(f"   ✅ Trovato in posizione {i} con similarità {doc['similarity']:.3f}")
            found = True
            break
    
    if not found:
        print("   ⚠️  Documento non trovato nei primi risultati")


# ============================================================================
# Main Test Runner
# ============================================================================

def run_all_tests():
    """Esegui tutti i test"""
    print("\n" + "=" * 60)
    print("  🧪 API Test Suite - Python Client")
    print("=" * 60)
    
    client = APIClient()
    
    try:
        # Test in sequenza
        test_health(client)
        test_stats(client)
        test_list_documents(client)
        test_create_document(client)
        test_search(client)
        test_integration(client)
        
        print("\n" + "=" * 60)
        print("  ✅ Tutti i test completati con successo!")
        print("=" * 60)
        print()
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Errore: API non raggiungibile!")
        print("   Assicurati che l'API sia avviata: uvicorn api:app --reload")
    except Exception as e:
        print(f"\n❌ Errore durante i test: {e}")


# ============================================================================
# Interactive Mode
# ============================================================================

def interactive_mode():
    """Modalità interattiva"""
    client = APIClient()
    
    print("\n" + "=" * 60)
    print("  🔧 Modalità Interattiva API Client")
    print("=" * 60)
    print("\nComandi disponibili:")
    print("  1. health    - Check health API")
    print("  2. stats     - Statistiche database")
    print("  3. search    - Ricerca semantic")
    print("  4. create    - Crea documento")
    print("  5. list      - Lista documenti")
    print("  6. test      - Esegui tutti i test")
    print("  7. exit      - Esci")
    print()
    
    while True:
        try:
            cmd = input("Comando> ").strip().lower()
            
            if cmd == "exit":
                print("Ciao! 👋")
                break
            
            elif cmd == "health":
                result = client.health_check()
                print(json.dumps(result, indent=2))
            
            elif cmd == "stats":
                result = client.get_stats()
                print(json.dumps(result, indent=2))
            
            elif cmd == "search":
                query = input("Query: ").strip()
                if query:
                    result = client.search(query, limit=5)
                    for i, doc in enumerate(result['results'], 1):
                        print(f"{i}. [{doc['similarity']:.3f}] {doc['content'][:100]}")
            
            elif cmd == "create":
                content = input("Contenuto: ").strip()
                if content:
                    category = input("Categoria (opzionale): ").strip()
                    metadata = {"category": category} if category else None
                    result = client.create_document(content, metadata)
                    print(f"✅ Creato documento ID: {result['id']}")
            
            elif cmd == "list":
                result = client.list_documents(limit=5)
                print(f"Totale: {result['total']}\n")
                for i, doc in enumerate(result['documents'], 1):
                    print(f"{i}. [ID: {doc['id']}] {doc['content'][:80]}")
            
            elif cmd == "test":
                run_all_tests()
            
            else:
                print("Comando non riconosciuto. Usa: health, stats, search, create, list, test, exit")
            
            print()
        
        except KeyboardInterrupt:
            print("\n\nCiao! 👋")
            break
        except Exception as e:
            print(f"Errore: {e}\n")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    else:
        run_all_tests()

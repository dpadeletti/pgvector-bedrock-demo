#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple search usando similarita coseno calcolata in Python
"""
import numpy as np
import json
from embeddings import get_embedding
from config import get_db_connection

def cosine_similarity(a, b):
    """Calcola similarita coseno tra due vettori"""
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def search(query, top_k=5):
    print(f"Ricerca: '{query}'")
    
    # Genera embedding della query
    print("   Genero embedding...")
    query_emb = np.array(get_embedding(query))
    
    # Recupera tutti i documenti
    print("   Carico documenti dal database...")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, content, embedding, metadata FROM documents")
    
    # Calcola similarita per ogni documento
    results = []
    for doc_id, content, embedding, metadata in cur.fetchall():
        doc_emb = np.array(embedding)
        similarity = cosine_similarity(query_emb, doc_emb)
        results.append((doc_id, content, similarity, metadata))
    
    cur.close()
    conn.close()
    
    # Ordina per similarita
    results.sort(key=lambda x: x[2], reverse=True)
    
    # Mostra top risultati
    print(f"\nTop {top_k} risultati:\n")
    for i, (doc_id, content, sim, metadata) in enumerate(results[:top_k], 1):
        print(f"{i}. [ID: {doc_id}] Similarita: {sim:.3f}")
        if metadata:
            meta = metadata if isinstance(metadata, dict) else json.loads(metadata)
            category = meta.get('category', 'N/A')
            print(f"   Categoria: {category}")
        print(f"   {content}")
        print()
    
    return results[:top_k]

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        search(query)
    else:
        # Modalita interattiva
        print("Ricerca Interattiva (scrivi 'exit' per uscire)\n")
        while True:
            try:
                query = input("Query: ").strip()
                if not query:
                    continue
                if query.lower() == 'exit':
                    print("Ciao!")
                    break
                search(query)
            except KeyboardInterrupt:
                print("\nCiao!")
                break

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Semantic search usando pgvector <=> operator (cosine distance) via SQL
"""
import json
from embeddings import get_embedding
from config import get_db_connection


def search(query, top_k=5):
    print(f"Ricerca: '{query}'")

    # Genera embedding della query
    print("   Genero embedding...")
    query_emb = get_embedding(query)  # lista di float, register_vector la gestisce

    # Query pgvector: <=> = cosine distance, similarity = 1 - distance
    print("   Cerco nel database...")
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
        (query_emb, top_k)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # Mostra risultati
    print(f"\nTop {top_k} risultati:\n")
    results = []
    for i, (doc_id, content, metadata, similarity) in enumerate(rows, 1):
        print(f"{i}. [ID: {doc_id}] Similarità: {similarity:.3f}")
        if metadata:
            meta = metadata if isinstance(metadata, dict) else json.loads(metadata)
            category = meta.get('category', 'N/A')
            print(f"   Categoria: {category}")
        print(f"   {content}")
        print()
        results.append((doc_id, content, similarity, metadata))

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        search(query)
    else:
        # Modalità interattiva
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
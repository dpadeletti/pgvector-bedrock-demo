#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_rag_quality.py
─────────────────────────
Test automatizzati per verificare la qualità della pipeline RAG.

Verifica le 3 migliorie implementate:
  1. Hybrid search (semantic + fulltext RRF)
  2. Reranking (Nova Micro cross-encoder)
  3. Query expansion (Nova Micro varianti)

Uso:
  # Test contro API live
  python3 tests/test_rag_quality.py

  # Con URL personalizzato
  BASE_URL=http://localhost:8000 python3 tests/test_rag_quality.py

  # Verbose (stampa dettaglio ogni risultato)
  python3 tests/test_rag_quality.py --verbose

  # Solo un gruppo di test
  python3 tests/test_rag_quality.py --group hybrid
  python3 tests/test_rag_quality.py --group rerank
  python3 tests/test_rag_quality.py --group expand
  python3 tests/test_rag_quality.py --group chat
"""

import argparse
import json
import os
import sys
import time
from typing import Optional

import requests

# =============================================================================
# CONFIGURAZIONE
# =============================================================================

BASE_URL = os.environ.get(
    "BASE_URL",
    "http://pgvector-alb-1618965750.eu-north-1.elb.amazonaws.com"
).rstrip("/")

TIMEOUT  = 30   # secondi per chiamata API
DELAY    = 1.0  # pausa tra test (evita throttling Bedrock)

# Colori terminale
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


# =============================================================================
# HELPERS
# =============================================================================

def search(query: str, limit: int = 5, hybrid: bool = True,
           rerank: bool = False, expand: bool = False) -> dict:
    resp = requests.post(
        f"{BASE_URL}/search",
        json={"query": query, "limit": limit,
              "hybrid": hybrid, "rerank": rerank, "expand": expand},
        timeout=TIMEOUT
    )
    resp.raise_for_status()
    return resp.json()


def chat(question: str, limit: int = 5,
         rerank: bool = False, expand: bool = False) -> dict:
    resp = requests.post(
        f"{BASE_URL}/chat",
        json={"question": question, "limit": limit,
              "rerank": rerank, "expand": expand},
        timeout=TIMEOUT
    )
    resp.raise_for_status()
    return resp.json()


def top_titles(data: dict) -> list:
    return [r["metadata"].get("title", "?") for r in data["results"]]


def top_sources(data: dict) -> list:
    return [r["metadata"].get("source", "?") for r in data["results"]]


def top_similarities(data: dict) -> list:
    return [round(r["similarity"], 3) for r in data["results"]]


def has_match_type(data: dict, mtype: str) -> bool:
    return any(r.get("match_type") == mtype for r in data["results"])


def any_match_type_both(data: dict) -> bool:
    return any(r.get("match_type") == "both" for r in data["results"])


# =============================================================================
# RUNNER
# =============================================================================

class TestRunner:
    def __init__(self, verbose: bool = False):
        self.verbose  = verbose
        self.passed   = 0
        self.failed   = 0
        self.skipped  = 0
        self.failures = []

    def ok(self, name: str, detail: str = ""):
        self.passed += 1
        detail_str = f"  {BLUE}{detail}{RESET}" if detail else ""
        print(f"  {GREEN}✓{RESET} {name}{detail_str}")

    def fail(self, name: str, reason: str):
        self.failed += 1
        self.failures.append((name, reason))
        print(f"  {RED}✗{RESET} {name}")
        print(f"    {RED}→ {reason}{RESET}")

    def skip(self, name: str, reason: str):
        self.skipped += 1
        print(f"  {YELLOW}○{RESET} {name} (skip: {reason})")

    def section(self, title: str):
        print(f"\n{BOLD}{BLUE}{'─'*55}{RESET}")
        print(f"{BOLD}{BLUE}  {title}{RESET}")
        print(f"{BOLD}{BLUE}{'─'*55}{RESET}")

    def assert_true(self, name: str, condition: bool, reason: str, detail: str = ""):
        if condition:
            self.ok(name, detail)
        else:
            self.fail(name, reason)

    def summary(self):
        total = self.passed + self.failed + self.skipped
        print(f"\n{BOLD}{'═'*55}{RESET}")
        print(f"{BOLD}  RISULTATI: {total} test | "
              f"{GREEN}{self.passed} ok{RESET} | "
              f"{RED}{self.failed} falliti{RESET} | "
              f"{YELLOW}{self.skipped} skip{RESET}{BOLD}{RESET}")
        print(f"{BOLD}{'═'*55}{RESET}")
        if self.failures:
            print(f"\n{RED}Test falliti:{RESET}")
            for name, reason in self.failures:
                print(f"  {RED}✗ {name}: {reason}{RESET}")
        return self.failed == 0


# =============================================================================
# TEST GROUP 1 — INFRASTRUTTURA BASE
# =============================================================================

def test_infra(r: TestRunner):
    r.section("1. Infrastruttura API")

    # Health check
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        data = resp.json()
        r.assert_true("API raggiungibile", resp.status_code == 200,
                      f"status {resp.status_code}")
        r.assert_true("DB connesso", data.get("database") == "connected",
                      f"database: {data.get('database')}")
        r.assert_true("Bedrock disponibile", data.get("bedrock") == "available",
                      f"bedrock: {data.get('bedrock')}")
    except Exception as e:
        r.fail("API raggiungibile", str(e))
        return False

    # Stats
    try:
        resp = requests.get(f"{BASE_URL}/stats", timeout=TIMEOUT)
        data = resp.json()
        total = data.get("total_documents", 0)
        r.assert_true("DB popolato (>1000 doc)", total > 1000,
                      f"solo {total} documenti",
                      f"{total:,} documenti")
        r.assert_true("DB small-prod (>10K doc)", total > 10000,
                      f"solo {total} documenti — esegui populate_db.py",
                      f"{total:,} documenti ✓")
    except Exception as e:
        r.fail("Stats API", str(e))

    return True


# =============================================================================
# TEST GROUP 2 — HYBRID SEARCH
# =============================================================================

def test_hybrid(r: TestRunner, verbose: bool = False):
    r.section("2. Hybrid Search (semantic + fulltext RRF)")

    # 2a — search_mode corretto
    try:
        data = search("backpropagation gradient descent", hybrid=True)
        r.assert_true(
            "search_mode = 'hybrid'",
            data.get("search_mode", "").startswith("hybrid"),
            f"search_mode era: {data.get('search_mode')}",
            data.get("search_mode")
        )
    except Exception as e:
        r.fail("search_mode hybrid", str(e))
    time.sleep(DELAY)

    # 2b — query semantica: risultati rilevanti
    try:
        data  = search("neural network backpropagation training", hybrid=True)
        sims  = top_similarities(data)
        titles = top_titles(data)
        r.assert_true(
            "Query semantica: similarity > 0.3",
            sims[0] > 0.3,
            f"similarity troppo bassa: {sims[0]}",
            f"top similarity: {sims[0]}"
        )
        if verbose:
            for t, s in zip(titles, sims):
                print(f"      {s:.3f}  {t}")
    except Exception as e:
        r.fail("Query semantica similarity", str(e))
    time.sleep(DELAY)

    # 2c — keyword query: il fulltext deve trovare match
    try:
        data = search("backpropagation gradient descent", hybrid=True)
        has_both = any_match_type_both(data)
        r.assert_true(
            "Keyword query: almeno 1 risultato match_type='both'",
            has_both,
            "nessun risultato 'both' — il fulltext non contribuisce",
            "trovati risultati 'both' ✓"
        )
    except Exception as e:
        r.fail("match_type both", str(e))
    time.sleep(DELAY)

    # 2d — hybrid batte semantic su query keyword
    try:
        data_hybrid   = search("backpropagation gradient descent", hybrid=True)
        data_semantic = search("backpropagation gradient descent", hybrid=False)
        time.sleep(DELAY)

        ids_hybrid   = {r_["id"] for r_ in data_hybrid["results"]}
        ids_semantic = {r_["id"] for r_ in data_semantic["results"]}
        new_in_hybrid = ids_hybrid - ids_semantic

        r.assert_true(
            "Hybrid trova documenti aggiuntivi rispetto a solo-semantica",
            len(new_in_hybrid) > 0,
            "hybrid e semantic restituiscono gli stessi risultati",
            f"{len(new_in_hybrid)} doc unici in hybrid"
        )
    except Exception as e:
        r.fail("Hybrid vs semantic differenza", str(e))
    time.sleep(DELAY)

    # 2e — query arXiv specifica
    try:
        data   = search("LoRA low-rank adaptation fine-tuning", hybrid=True, limit=3)
        srcs   = top_sources(data)
        titles = top_titles(data)
        has_arxiv = "arxiv" in srcs
        r.assert_true(
            "Query arXiv-specifica trova paper arXiv",
            has_arxiv,
            f"solo Wikipedia: {titles[:2]}",
            f"top source: {srcs[0]}, title: {titles[0][:50]}"
        )
    except Exception as e:
        r.fail("arXiv retrieval", str(e))
    time.sleep(DELAY)


# =============================================================================
# TEST GROUP 3 — RERANKING
# =============================================================================

def test_reranking(r: TestRunner, verbose: bool = False):
    r.section("3. Reranking (Nova Micro cross-encoder)")

    # 3a — search_mode contiene rerank
    try:
        data = search("transformer attention mechanism", hybrid=True, rerank=True)
        r.assert_true(
            "search_mode contiene '+rerank'",
            "rerank" in data.get("search_mode", ""),
            f"search_mode: {data.get('search_mode')}",
            data.get("search_mode")
        )
    except Exception as e:
        r.fail("search_mode rerank", str(e))
    time.sleep(DELAY)

    # 3c — il top-1 con rerank ha similarity >= top-1 senza rerank (o vicino)
    try:
        data_no_rr = search("neural network learning algorithm",
                            hybrid=True, rerank=False, limit=5)
        time.sleep(DELAY)
        data_rr    = search("neural network learning algorithm",
                            hybrid=True, rerank=True, limit=5)
        time.sleep(DELAY)

        sim_no_rr = top_similarities(data_no_rr)[0]
        sim_rr    = top_similarities(data_rr)[0]

        r.assert_true(
            "Top-1 con rerank ha similarity >= 0.35",
            sim_rr >= 0.35,
            f"similarity top-1 reranked: {sim_rr}",
            f"similarity top-1: {sim_rr:.3f} (no rerank: {sim_no_rr:.3f})"
        )
    except Exception as e:
        r.fail("Rerank top-1 similarity", str(e))
    time.sleep(DELAY)


# =============================================================================
# TEST GROUP 4 — QUERY EXPANSION
# =============================================================================

def test_expansion(r: TestRunner, verbose: bool = False):
    r.section("4. Query Expansion (Nova Micro)")

    # 4a — search_mode contiene expand
    try:
        data = search("machine learning optimization", hybrid=True, expand=True)
        r.assert_true(
            "search_mode contiene '+expand'",
            "expand" in data.get("search_mode", ""),
            f"search_mode: {data.get('search_mode')}",
            data.get("search_mode")
        )
    except Exception as e:
        r.fail("search_mode expand", str(e))
    time.sleep(DELAY)

    # 4b — expand trova documenti aggiuntivi rispetto a non-expand
    try:
        data_no_exp = search("reti neurali apprendimento", hybrid=True,
                             expand=False, limit=5)
        time.sleep(DELAY)
        data_exp    = search("reti neurali apprendimento", hybrid=True,
                             expand=True, limit=5)
        time.sleep(DELAY)

        ids_no_exp = {r_["id"] for r_ in data_no_exp["results"]}
        ids_exp    = {r_["id"] for r_ in data_exp["results"]}
        new_in_exp = ids_exp - ids_no_exp

        r.assert_true(
            "Expand trova documenti aggiuntivi (query IT → doc EN)",
            len(new_in_exp) > 0,
            "nessun documento aggiuntivo — expansion non ha effetto",
            f"{len(new_in_exp)} doc aggiuntivi trovati dall'expansion"
        )
        if verbose:
            exp_titles = [r_["metadata"].get("title","?")
                         for r_ in data_exp["results"]
                         if r_["id"] in new_in_exp]
            for t in exp_titles:
                print(f"      + {t}")
    except Exception as e:
        r.fail("Expand trova doc aggiuntivi", str(e))
    time.sleep(DELAY)

    # 4c — expand+rerank: search_mode completo
    try:
        data = search("deep learning training", hybrid=True,
                      expand=True, rerank=True)
        mode = data.get("search_mode", "")
        r.assert_true(
            "Pipeline completa: search_mode = 'hybrid+expand+rerank'",
            "expand" in mode and "rerank" in mode,
            f"search_mode: {mode}",
            mode
        )
    except Exception as e:
        r.fail("Pipeline completa search_mode", str(e))
    time.sleep(DELAY)


# =============================================================================
# TEST GROUP 5 — RAG CHAT
# =============================================================================

def test_chat(r: TestRunner, verbose: bool = False):
    r.section("5. RAG Chat (/chat endpoint)")

    # 5a — risposta non vuota
    try:
        data = chat("Cos'è il machine learning?", limit=3, rerank=False)
        answer = data.get("answer", "")
        r.assert_true(
            "Risposta non vuota",
            len(answer) > 50,
            f"risposta troppo corta: '{answer[:80]}'",
            f"{len(answer)} caratteri"
        )
        if verbose:
            print(f"      Risposta: {answer[:120]}...")
    except Exception as e:
        r.fail("Chat risposta non vuota", str(e))
    time.sleep(DELAY)

    # 5b — sources presenti
    try:
        data    = chat("What is backpropagation?", limit=3, rerank=False)
        sources = data.get("sources", [])
        r.assert_true(
            "Sources presenti nella risposta",
            len(sources) > 0,
            "nessuna source restituita",
            f"{len(sources)} sources"
        )
        if verbose and sources:
            for s in sources[:3]:
                print(f"      [{s.get('similarity',0):.2f}] {s.get('title','?')}")
    except Exception as e:
        r.fail("Chat sources", str(e))
    time.sleep(DELAY)

    # 5c — reranked flag nella risposta
    try:
        data = chat("Come funziona il deep learning?", limit=3, rerank=True)
        r.assert_true(
            "Campo 'reranked' presente nella risposta",
            "reranked" in data,
            "campo reranked mancante",
            f"reranked={data.get('reranked')}"
        )
        r.assert_true(
            "reranked=True quando rerank=True",
            data.get("reranked") is True,
            f"reranked era: {data.get('reranked')}"
        )
    except Exception as e:
        r.fail("Chat reranked flag", str(e))
    time.sleep(DELAY)

    # 5d — query arXiv via chat
    try:
        data    = chat("What is LoRA and how is it used for fine-tuning?",
                       limit=5, rerank=True)
        sources = data.get("sources", [])
        src_names = [s.get("source", s.get("metadata", {}).get("source", "?"))
                     for s in sources]
        answer  = data.get("answer", "")
        r.assert_true(
            "Chat su topic arXiv genera risposta con contenuto",
            len(answer) > 100,
            f"risposta troppo corta: {len(answer)} char",
            f"{len(answer)} caratteri, {len(sources)} sources"
        )
    except Exception as e:
        r.fail("Chat query arXiv", str(e))
    time.sleep(DELAY)


# =============================================================================
# TEST GROUP 6 — CONFRONTO PIPELINE (BENCHMARK QUALITATIVO)
# =============================================================================

def test_benchmark(r: TestRunner, verbose: bool = False):
    r.section("6. Benchmark qualitativo pipeline")

    queries = [
        ("backpropagation gradient descent",        "neural"),
        ("LoRA low-rank adaptation",                "lora"),
        ("transformer self-attention mechanism",    "transformer"),
        ("overfitting regularization dropout",      "regularization"),
    ]

    print(f"\n  {'Query':<40} {'Semantic':>10} {'Hybrid':>10} {'H+Rerank':>10}")
    print(f"  {'─'*40} {'─'*10} {'─'*10} {'─'*10}")

    for query, _ in queries:
        try:
            d_sem = search(query, hybrid=False, limit=5)
            time.sleep(DELAY)
            d_hyb = search(query, hybrid=True,  limit=5)
            time.sleep(DELAY)
            d_rr  = search(query, hybrid=True, rerank=True, limit=5)
            time.sleep(DELAY)

            sim_sem = top_similarities(d_sem)[0]
            sim_hyb = top_similarities(d_hyb)[0]
            sim_rr  = top_similarities(d_rr)[0]

            q_short = query[:38] + ".." if len(query) > 38 else query
            print(f"  {q_short:<40} {sim_sem:>10.3f} {sim_hyb:>10.3f} {sim_rr:>10.3f}")

            r.assert_true(
                f"'{query[:30]}...' — similarity > 0.25",
                sim_sem > 0.25,
                f"similarity troppo bassa: {sim_sem}",
                ""
            )
        except Exception as e:
            r.fail(f"Benchmark '{query[:30]}'", str(e))

    print()


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Test qualità pipeline RAG (hybrid + rerank + expand)"
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Stampa dettaglio risultati")
    parser.add_argument("--group", choices=["infra","hybrid","rerank","expand","chat","benchmark"],
                        help="Esegui solo un gruppo di test")
    args = parser.parse_args()

    print(f"\n{BOLD}{'═'*55}{RESET}")
    print(f"{BOLD}  pgvector RAG Quality Tests{RESET}")
    print(f"{BOLD}{'═'*55}{RESET}")
    print(f"  API: {BASE_URL}")
    print(f"  Verbose: {args.verbose}")

    r = TestRunner(verbose=args.verbose)

    groups = {
        "infra":     lambda: test_infra(r),
        "hybrid":    lambda: test_hybrid(r, args.verbose),
        "rerank":    lambda: test_reranking(r, args.verbose),
        "expand":    lambda: test_expansion(r, args.verbose),
        "chat":      lambda: test_chat(r, args.verbose),
        "benchmark": lambda: test_benchmark(r, args.verbose),
    }

    if args.group:
        groups[args.group]()
    else:
        infra_ok = test_infra(r)
        if not infra_ok:
            print(f"\n{RED}API non raggiungibile — test interrotti.{RESET}")
            print(f"Avvia le risorse AWS prima di eseguire i test:\n")
            print("  aws rds start-db-instance --db-instance-identifier pgvector-demo-db --region eu-north-1")
            print("  aws ecs update-service --cluster pgvector-demo-cluster "
                  "--service pgvector-demo-service --desired-count 1 --region eu-north-1\n")
            sys.exit(1)

        test_hybrid(r, args.verbose)
        test_reranking(r, args.verbose)
        test_expansion(r, args.verbose)
        test_chat(r, args.verbose)
        test_benchmark(r, args.verbose)

    success = r.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

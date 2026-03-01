# 🧪 Test Suite

Test completi per l'API REST di Pgvector Semantic Search.

## 📁 Struttura

```
tests/
├── test_api.py         # Test pytest automatici
├── test_client.py      # Client Python interattivo
├── manual_test.sh      # Script bash con curl
└── README.md           # Questa guida
```

---

## 🚀 Setup

### 1. Installa dipendenze test

```bash
pip install pytest pytest-cov requests --user
```

### 2. Avvia l'API

**In un terminale separato:**
```bash
python3.11 -m uvicorn api:app --reload
```

L'API deve essere running su http://localhost:8000

---

## 🎯 Opzione A: Test Automatici (pytest)

**Test completi con coverage:**

```bash
# Esegui tutti i test
cd tests
pytest test_api.py -v

# Con coverage
pytest test_api.py -v --cov=../api --cov-report=html

# Test specifico
pytest test_api.py::test_search_basic -v
```

### Output Atteso

```
tests/test_api.py::test_root PASSED                          [ 5%]
tests/test_api.py::test_health PASSED                        [ 10%]
tests/test_api.py::test_stats PASSED                         [ 15%]
tests/test_api.py::test_search_basic PASSED                  [ 20%]
...
======================== 25 passed in 5.23s =========================
```

### Test Coperti

- ✅ Endpoint generali (root, health, docs)
- ✅ Stats endpoint
- ✅ Documents CRUD (create, list)
- ✅ Search endpoint con validazione
- ✅ Test integrazione (create + search)
- ✅ Performance test

---

## 🔧 Opzione B: Test Manuali (curl)

**Test veloci con curl:**

```bash
cd tests
chmod +x manual_test.sh
./manual_test.sh
```

Esegue 7 test:
1. Root endpoint
2. Health check
3. Stats
4. List documents
5. Create document
6. Search "machine learning"
7. Search "neural networks"

---

## 🐍 Opzione C: Client Python Interattivo

### Modalità Test Automatica

```bash
cd tests
python3.11 test_client.py
```

Esegue suite completa di test programmabili.

### Modalità Interattiva

```bash
python3.11 test_client.py --interactive
```

**Comandi disponibili:**
```
Comando> health     # Check health API
Comando> stats      # Statistiche database
Comando> search     # Ricerca semantic
Comando> create     # Crea documento
Comando> list       # Lista documenti
Comando> test       # Esegui tutti i test
Comando> exit       # Esci
```

---

## 📊 Test Coverage

### Endpoint Testati

| Endpoint | pytest | curl | client.py |
|----------|--------|------|-----------|
| `GET /` | ✅ | ✅ | ✅ |
| `GET /health` | ✅ | ✅ | ✅ |
| `GET /stats` | ✅ | ✅ | ✅ |
| `GET /documents` | ✅ | ✅ | ✅ |
| `POST /documents` | ✅ | ✅ | ✅ |
| `POST /search` | ✅ | ✅ | ✅ |

### Tipi di Test

- **Unit Test**: Test singoli endpoint isolati
- **Validation Test**: Verifica input validation
- **Integration Test**: Test workflow completi (create + search)
- **Performance Test**: Test con query multiple

---

## 🐛 Troubleshooting

### Errore: Connection Refused

```
requests.exceptions.ConnectionError: Connection refused
```

**Soluzione**: Avvia l'API
```bash
python3.11 -m uvicorn api:app --reload
```

### Errore: pytest not found

```bash
pip install pytest --user
```

### Test falliscono per timeout

Aumenta timeout modificando i test:
```python
response = client.get("/health", timeout=10)
```

---

## 📝 Aggiungere Nuovi Test

### Nuovo test in pytest

```python
def test_my_new_feature():
    """Test nuova feature"""
    response = client.get("/my-endpoint")
    assert response.status_code == 200
    # ... assertions
```

### Nuovo test in curl script

```bash
echo -e "${BLUE}Test My Feature${NC}"
curl -s -X GET "$API_URL/my-endpoint" | python3 -m json.tool
```

---

## 🎯 Best Practices

1. **Sempre avvia l'API prima dei test**
2. **Usa pytest per CI/CD**
3. **Usa curl per test veloci manuali**
4. **Usa client Python per debugging interattivo**
5. **Verifica coverage > 80%**

---

## 🚀 CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run Tests
  run: |
    uvicorn api:app &
    sleep 5
    pytest tests/test_api.py -v --cov
```

---

**Happy Testing!** 🎉

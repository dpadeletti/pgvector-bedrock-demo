#!/bin/bash
# Script per test manuali rapidi dell'API con curl

API_URL="http://localhost:8000"

echo "=========================================="
echo "🧪 Test API Manuale (curl)"
echo "=========================================="
echo ""

# Colori
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# ============================================================================
# Test 1: Root
# ============================================================================
echo -e "${BLUE}[1/7] Test Root Endpoint${NC}"
curl -s -X GET "$API_URL/" | python3 -m json.tool
echo ""
echo ""

# ============================================================================
# Test 2: Health
# ============================================================================
echo -e "${BLUE}[2/7] Test Health Check${NC}"
curl -s -X GET "$API_URL/health" | python3 -m json.tool
echo ""
echo ""

# ============================================================================
# Test 3: Stats
# ============================================================================
echo -e "${BLUE}[3/7] Test Stats${NC}"
curl -s -X GET "$API_URL/stats" | python3 -m json.tool
echo ""
echo ""

# ============================================================================
# Test 4: List Documents
# ============================================================================
echo -e "${BLUE}[4/7] Test List Documents (limit 3)${NC}"
curl -s -X GET "$API_URL/documents?limit=3" | python3 -m json.tool
echo ""
echo ""

# ============================================================================
# Test 5: Create Document
# ============================================================================
echo -e "${BLUE}[5/7] Test Create Document${NC}"
curl -s -X POST "$API_URL/documents" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "FastAPI is a modern, fast (high-performance) web framework for building APIs with Python 3.7+ based on standard Python type hints",
    "metadata": {
      "category": "Web Framework",
      "source": "manual_test",
      "language": "en"
    }
  }' | python3 -m json.tool
echo ""
echo ""

# ============================================================================
# Test 6: Search - Machine Learning
# ============================================================================
echo -e "${BLUE}[6/7] Test Search: 'machine learning'${NC}"
curl -s -X POST "$API_URL/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning",
    "limit": 3
  }' | python3 -m json.tool
echo ""
echo ""

# ============================================================================
# Test 7: Search - Neural Networks
# ============================================================================
echo -e "${BLUE}[7/7] Test Search: 'neural networks'${NC}"
curl -s -X POST "$API_URL/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "neural networks",
    "limit": 3
  }' | python3 -m json.tool
echo ""
echo ""

# ============================================================================
# Summary
# ============================================================================
echo "=========================================="
echo -e "${GREEN}✅ Test Completati!${NC}"
echo "=========================================="
echo ""
echo "📝 Per test interattivi:"
echo "   - Swagger UI: http://localhost:8000/docs"
echo "   - ReDoc: http://localhost:8000/redoc"
echo ""
echo "🔧 Per test automatici:"
echo "   cd tests && pytest test_api.py -v"
echo ""

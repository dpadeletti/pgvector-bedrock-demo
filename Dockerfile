# Python 3.11 slim — psycopg2 incompatibile con 3.13
FROM python:3.11-slim

# Evita prompt interattivi durante apt
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dipendenze di sistema (necessarie per psycopg2-binary e build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installa dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia codice applicazione e UI
COPY api.py config.py embeddings.py init_db.py chat_ui.html ./

# Espone porta 8000
EXPOSE 8000

# Avvia uvicorn
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]

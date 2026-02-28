# 📦 Setup GitHub - pgvector-bedrock-demo

Guida per pushare il progetto su GitHub e configurarlo correttamente.

## 📋 Prerequisiti

- Account GitHub
- Git installato localmente
- Progetto scaricato in locale

## 🚀 Step 1: Crea Repository su GitHub

### Via GitHub Web:

1. Vai su https://github.com/new
2. **Repository name**: `pgvector-bedrock-demo`
3. **Description**: `Semantic search con pgvector su AWS RDS + Bedrock embeddings`
4. **Visibility**: Public (o Private se preferisci)
5. **❌ NON** aggiungere README, .gitignore o license (li abbiamo già!)
6. Click **Create repository**

### Via GitHub CLI (opzionale):

```bash
# Installa GitHub CLI: https://cli.github.com/
gh repo create pgvector-bedrock-demo --public --description "Semantic search con pgvector su AWS RDS + Bedrock embeddings"
```

## 🚀 Step 2: Inizializza Git Localmente

Apri il terminale nella cartella del progetto (dove hai i file):

```bash
# Vai nella cartella del progetto
cd /path/to/pgvector-bedrock-demo

# Inizializza repository Git
git init

# Aggiungi tutti i file
git add .

# Verifica cosa verrà committato
git status

# Primo commit
git commit -m "Initial commit: pgvector + AWS Bedrock demo"
```

## 🚀 Step 3: Collega a GitHub e Push

```bash
# Aggiungi remote (sostituisci TUO-USERNAME con il tuo username GitHub)
git remote add origin https://github.com/TUO-USERNAME/pgvector-bedrock-demo.git

# Verifica remote
git remote -v

# Push al repository
git branch -M main
git push -u origin main
```

Se richiede autenticazione:
- **Username**: tuo username GitHub
- **Password**: usa un **Personal Access Token** (non la password!):
  1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
  2. Generate new token (classic)
  3. Seleziona scope: `repo`
  4. Copia il token e usalo come password

## ⚙️ Step 4: Configura Repository Settings

### A. Aggiungi Topics

Nel repository GitHub:
1. **Settings** → clicca su ⚙️ accanto ad "About"
2. Aggiungi topics: `pgvector`, `aws-bedrock`, `semantic-search`, `python`, `postgresql`, `embeddings`

### B. Proteggi Branch Main (opzionale)

1. **Settings** → **Branches**
2. **Add branch protection rule**
3. Branch name: `main`
4. Abilita: "Require pull request reviews before merging"

### C. GitHub Secrets (per EC2 deployment automatico)

Se vuoi usare GitHub Actions per deploy automatico:

1. **Settings** → **Secrets and variables** → **Actions**
2. **New repository secret**
3. Aggiungi:
   - `AWS_ACCESS_KEY_ID`: tua access key
   - `AWS_SECRET_ACCESS_KEY`: tua secret key
   - `DB_HOST`: endpoint RDS
   - `DB_PASSWORD`: password database

⚠️ **Non committare mai credenziali nel codice!**

## 📝 Step 5: Verifica .gitignore

Il file `.gitignore` deve contenere:

```gitignore
# Environment variables
.env
.env.local

# Python
__pycache__/
*.py[cod]
venv/
.venv

# IDEs
.vscode/
.idea/

# Secrets
*.pem
*.key
```

**Verifica che .env NON sia tracciato:**

```bash
git status

# Se .env appare, rimuovilo:
git rm --cached .env
git commit -m "Remove .env from tracking"
```

## 🔄 Step 6: Workflow Quotidiano

### Modifiche Locali

```bash
# Controlla stato
git status

# Aggiungi modifiche
git add .

# Commit
git commit -m "Descrizione delle modifiche"

# Push a GitHub
git push
```

### Pull da GitHub (se hai modifiche remote)

```bash
git pull origin main
```

### Crea Branch per Feature

```bash
# Crea e passa a nuovo branch
git checkout -b feature/nome-feature

# Lavora sul branch...
git add .
git commit -m "Add feature"

# Push del branch
git push origin feature/nome-feature

# Su GitHub, crea Pull Request
```

## 📋 Step 7: README Badges (opzionale)

Aggiungi badge carini al README. Nel tuo README.md (già presenti):

```markdown
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![AWS](https://img.shields.io/badge/AWS-RDS%20%7C%20Bedrock-orange.svg)](https://aws.amazon.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
```

## 🤖 Step 8: GitHub Actions (CI/CD opzionale)

Crea `.github/workflows/test.yml` per test automatici:

```yaml
name: Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Lint with flake8
      run: |
        pip install flake8
        flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
```

## 🔗 Aggiorna Link nei File

Dopo il push, aggiorna questi link nei file con il tuo username GitHub:

**In EC2_DEPLOYMENT.md:**
```bash
# Trova e sostituisci:
TUO-USERNAME → il-tuo-username-github
```

**In setup_ec2.sh:**
```bash
# Stessa cosa
```

**Oppure usa find & replace in Cursor:**
1. Cmd/Ctrl + Shift + F
2. Cerca: `TUO-USERNAME`
3. Sostituisci: `il-tuo-username-github`
4. Replace All

## ✅ Checklist Finale

- [ ] Repository creato su GitHub
- [ ] Codice pushato su `main`
- [ ] `.env` NON committato (verifica con `git status`)
- [ ] README.md aggiornato con link corretti
- [ ] Topics aggiunti al repository
- [ ] LICENSE presente
- [ ] .gitignore configurato correttamente
- [ ] (Opzionale) Branch protection abilitato
- [ ] (Opzionale) GitHub Actions configurato

## 🎉 Fatto!

Il tuo progetto è ora su GitHub! 

**URL repository**: `https://github.com/TUO-USERNAME/pgvector-bedrock-demo`

Puoi condividerlo, ricevere contributi e usarlo come portfolio! 🚀

## 📞 Comandi Git Utili

```bash
# Clona repository (per altre persone)
git clone https://github.com/TUO-USERNAME/pgvector-bedrock-demo.git

# Vedi history
git log --oneline --graph

# Annulla ultimo commit (senza perdere modifiche)
git reset --soft HEAD~1

# Scarta modifiche locali
git restore file.py

# Vedi differenze
git diff

# Crea .gitignore per file già tracciato
git rm --cached file
```

## 🐛 Troubleshooting

### "fatal: not a git repository"
```bash
cd /path/to/correct/folder
git init
```

### "Permission denied (publickey)"
Usa HTTPS invece di SSH:
```bash
git remote set-url origin https://github.com/TUO-USERNAME/pgvector-bedrock-demo.git
```

### File .env committato per errore
```bash
git rm --cached .env
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Remove .env from tracking"
git push
```

Poi vai su GitHub → quel commit → ⋯ → Delete commit (se necessario)

# pgvector-bedrock-demo -- Session Summary

## Architettura attuale (operativa)
- **API**: FastAPI + pgvector su ECS Fargate (1 task, 256 CPU / 512 MB)
- **DB**: RDS PostgreSQL 16.6 + pgvector 0.8.0 + indice HNSW
- **Immagini**: ECR `216571348735.dkr.ecr.eu-north-1.amazonaws.com/pgvector-bedrock-demo:latest`
- **DNS**: `http://pgvector-alb-1618965750.eu-north-1.elb.amazonaws.com`
- **Region**: eu-north-1
- **UI**: Chat UI disponibile su `/` (servita da FastAPI)

## Risorse AWS
| Risorsa | ID/Nome |
|---------|---------|
| ECS Cluster | pgvector-demo-cluster |
| ECS Service | pgvector-demo-service |
| Task Definition | pgvector-demo-task:3 |
| RDS | pgvector-demo-db.c5y0ukeko14j.eu-north-1.rds.amazonaws.com |
| ECR | 216571348735.dkr.ecr.eu-north-1.amazonaws.com/pgvector-bedrock-demo |
| ALB | pgvector-alb / pgvector-alb-1618965750.eu-north-1.elb.amazonaws.com |
| Target Group | pgvector-tg / arn:aws:elasticloadbalancing:eu-north-1:216571348735:targetgroup/pgvector-tg/cfb9b95e34e6176d |
| VPC | vpc-051851638dc1e5f2b |
| Subnet A | subnet-021f615661a4659 (eu-north-1a) |
| Subnet B | subnet-0292c613618930ca8 (eu-north-1c) |
| Subnet C | subnet-0164c756bb8d43cd2 (eu-north-1b) |
| SG ECS | sg-00d310b017ab153e7 |
| SG ALB | sg-01b9c5dba5e5b6151 |
| SG RDS | sg-029573f0998e11be5 |
| IAM Role | pgvector-ecs-task-role |
| Secret | arn:aws:secretsmanager:eu-north-1:216571348735:secret:pgvector-demo/db-password-hOQbOd |

## CI/CD
- **GitHub Actions**: `.github/workflows/deploy.yml`
- **Trigger**: push su `main`
- **Pipeline**: test (validation only) -> build + push ECR -> force-new-deployment ECS -> wait stable
- **Secrets GitHub**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (utente IAM: davide-dev)

## Endpoints API
| Endpoint | Descrizione |
|----------|-------------|
| `GET /` | Chat UI (HTML) |
| `GET /ping` | Health rapido (usato da ALB) |
| `GET /health` | Health check DB + Bedrock |
| `GET /stats` | Statistiche documenti |
| `GET /documents` | Lista documenti paginata |
| `POST /documents` | Crea documento con embedding |
| `POST /search` | Semantic search pgvector |
| `POST /chat` | RAG chat (pgvector + Nova Lite) |
| `GET /docs` | Swagger UI |

## Database
- **Documenti**: 1928 chunk da Wikipedia (AI/ML/Data Science EN + IT)
- **Indice**: HNSW (m=16, ef_construction=64) su colonna embedding
- **Dimensione tabella**: ~46 MB
- **Embedding**: Titan Text Embeddings V2 (1024 dim)
- **Script popolamento**: `populate_db.py` (63 topic, resume automatico)
- **Script indice**: `create_hnsw_index.sql`

## Modelli Bedrock
- **Embeddings**: `amazon.titan-embed-text-v2:0` (sempre usato)
- **Chat default**: `amazon.nova-lite-v1:0` (attivo)
- **Chat opzioni UI**: Nova Micro, Nova Pro, Claude 3 Haiku (richiede approvazione Anthropic)

## Secrets Manager
- `DB_PASSWORD` in AWS Secrets Manager (non in chiaro nella task definition)
- `.env` locale mantiene la password per uso locale (non committato)

## Per riavviare le risorse
```bash
aws rds start-db-instance --db-instance-identifier pgvector-demo-db --region eu-north-1

aws ecs update-service --cluster pgvector-demo-cluster --service pgvector-demo-service --desired-count 1 --region eu-north-1
```

## Per stoppare e risparmiare (~$17/mese)
```bash
aws rds stop-db-instance --db-instance-identifier pgvector-demo-db --region eu-north-1

aws ecs update-service --cluster pgvector-demo-cluster --service pgvector-demo-service --desired-count 0 --region eu-north-1
```

## Completato
- Dockerfile senza HEALTHCHECK
- GitHub Actions CI/CD (push -> test -> ECR -> ECS)
- DB_PASSWORD in Secrets Manager
- Popolamento DB: 1928 chunk Wikipedia AI/ML EN+IT
- Indice HNSW per ricerca veloce su larga scala
- Endpoint RAG /chat (pgvector + Amazon Nova Lite)
- Chat UI dark terminal servita su /
- Markdown rendering nella UI
- Font size ottimizzato (16px base, 17px AI bubble)

## Prossimi step
- Claude 3 Haiku: richiedere approvazione su AWS Console -> Bedrock -> Model access
- HTTPS con ACM (richiede acquisto dominio)
- Aggiungere piu topic al DB (populate_db.py e facilmente estendibile)

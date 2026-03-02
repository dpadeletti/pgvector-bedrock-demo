# pgvector-bedrock-demo — Session Summary

## Architettura attuale (operativa)
- **API**: FastAPI + pgvector su ECS Fargate (1 task, 256 CPU / 512 MB)
- **DB**: RDS PostgreSQL 16.6 + pgvector 0.8.0
- **Immagini**: ECR `216571348735.dkr.ecr.eu-north-1.amazonaws.com/pgvector-bedrock-demo:latest`
- **DNS**: `http://pgvector-alb-1618965750.eu-north-1.elb.amazonaws.com`
- **Region**: eu-north-1

## Risorse AWS
| Risorsa | ID/Nome |
|---------|---------|
| ECS Cluster | pgvector-demo-cluster |
| ECS Service | pgvector-demo-service |
| Task Definition | pgvector-demo-task:2 |
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
| SG EC2 | sg-0d2b46cc2e119bfb6 |
| IAM Role | pgvector-ecs-task-role |

## Per riavviare le risorse
```bash
aws rds start-db-instance --db-instance-identifier pgvector-demo-db --region eu-north-1aws rds startte-service --cluster pgvector-demo-cluster --service pgvector-demo-service --desired-count 1 --region eu-north-1
```

## Prossimi step
1. Rimuovi HEALTHCHECK dal Dockerfile (rebuild + push + redeploy)
2. GitHub Actions CI/CD (push → ECR → ECS auto-deploy)
3. Secrets Manager per DB_PASSWORD
4. Opzionale: HTTPS ACM

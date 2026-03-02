# INFRA_GUIDE.md — Guida all'Infrastruttura AWS

Questa guida spiega **perché** ogni pezzo dell'infrastruttura esiste e come
riutilizzare lo schema per nuovi progetti.

---

## Panoramica dell'architettura

```
Internet
   │
   ▼
[ALB] ← unico punto di ingresso pubblico (porta 80)
   │
   ▼
[ECS Fargate] ← container con la tua app (porta 8000, privata)
   │        └─── pull immagine da [ECR]
   │        └─── legge secret da [Secrets Manager]
   │        └─── scrive log su [CloudWatch]
   │
   ├──► [RDS PostgreSQL] ← database privato (mai esposto a internet)
   └──► [Bedrock] ← API AWS managed (embeddings)

[GitHub Actions] → build → push ECR → deploy ECS (su ogni push a main)
```

**Regola di sicurezza fondamentale**: solo l'ALB è esposto a internet.
ECS e RDS sono in subnet private e comunicano solo tra loro.

---

## I 10 step spiegati

### STEP 1 — VPC + Networking

**Cos'è**: Una rete virtuale isolata dentro AWS. Senza VPC ogni risorsa
sarebbe su reti condivise con altri account AWS.

**Cosa creiamo**:
- **VPC** (10.0.0.0/16): la rete principale, contiene tutto
- **3 Subnet** in 3 Availability Zone diverse: se una AZ va giù, le altre
  continuano a funzionare (alta disponibilità)
- **Internet Gateway**: il "router" che collega la VPC a internet
- **Route Table**: dice al traffico "per uscire su internet, passa dall'IGW"

**Perché 3 subnet?** L'ALB richiede almeno 2 AZ. Usiamo 3 per copertura
completa e per soddisfare il requisito del DB Subnet Group RDS.

**`map-public-ip-on-launch`**: i task ECS Fargate in subnet pubblica hanno
bisogno di un IP pubblico per fare il pull dell'immagine da ECR.
Alternativa più sicura (ma complessa): VPC Endpoints o NAT Gateway.

---

### STEP 2 — Security Groups

I Security Group sono firewall a livello di risorsa. La regola chiave è la
**catena di trust**: ogni SG accetta traffico solo dalla risorsa precedente.

```
Internet → SG_ALB (80) → SG_ECS (8000) → SG_RDS (5432)
```

| Security Group | Accetta da | Porta |
|---------------|-----------|-------|
| SG_ALB | 0.0.0.0/0 (internet) | 80 |
| SG_ECS | SG_ALB | 8000 (APP_PORT) |
| SG_RDS | SG_ECS | 5432 |

**Risultato**: RDS non è mai raggiungibile da internet, solo da ECS.

---

### STEP 3 — RDS PostgreSQL

**`--no-publicly-accessible`**: l'endpoint RDS risolve solo dentro la VPC.
Anche se qualcuno scoprisse l'hostname, non potrebbe connettersi dall'esterno.

**DB Subnet Group**: dice a RDS in quali subnet può creare le istanze.
Ne usiamo 3 per permettere failover automatico in caso di Multi-AZ
(anche se qui usiamo Single-AZ per ridurre i costi).

**Nota sui costi**: `db.t3.micro` è coperto dal free tier per 12 mesi
(750 ore/mese). Dopo, costa ~$12/mese. Stoppa l'istanza quando non usi
il progetto:
```bash
aws rds stop-db-instance --db-instance-identifier ${PROJECT_NAME}-db --region $AWS_REGION
```

---

### STEP 4 — ECR (Elastic Container Registry)

Il registry privato Docker di AWS. ECS fa il pull dell'immagine da qui,
non da Docker Hub, quindi le credenziali rimangono dentro AWS.

**Flusso**:
```
git push main → GitHub Actions → docker build → docker push ECR → ECS pull
```

Il login ECR usa un token temporaneo (valido 12h) generato da:
```bash
aws ecr get-login-password | docker login --username AWS --password-stdin ...
```

---

### STEP 5 — IAM Role

**Perché serve**: i container ECS devono poter chiamare altri servizi AWS
(ECR per il pull, CloudWatch per i log, Bedrock per gli embeddings,
Secrets Manager per la password). Senza il role, le chiamate vengono rifiutate.

**Task Role vs Execution Role**: qui usiamo lo stesso role per entrambi.
In produzione è meglio separarli:
- **Execution Role**: solo permessi per avviare il task (ECR pull, log)
- **Task Role**: permessi per quello che fa l'app (Bedrock, Secrets Manager)

**Policy assegnate**:
| Policy | Serve per |
|--------|-----------|
| AmazonEC2ContainerRegistryReadOnly | Pull immagine da ECR |
| CloudWatchLogsFullAccess | Scrivere log |
| AmazonBedrockFullAccess | Chiamate a Titan Embeddings |
| Policy inline Secrets Manager | Leggere DB_PASSWORD |

---

### STEP 6 — Secrets Manager

La password del DB non deve mai apparire in chiaro nella task definition
(visibile sulla console AWS e nei log di CloudWatch).

**Come funziona**:
1. Il secret viene creato con il valore della password
2. Nella task definition si mette solo l'ARN del secret (non il valore)
3. ECS, al lancio del container, chiama Secrets Manager e inietta il
   valore come variabile d'ambiente — **solo dentro il container**
4. Il valore non appare mai nei log o nella console

**Costo**: $0.40/mese per secret + $0.05 per 10.000 chiamate API.

---

### STEP 7 — CloudWatch Log Group

Raccoglie tutti i log dei container ECS. Senza questo, i log `stdout`
del container andrebbero persi.

**Come vedere i log**:
```bash
aws logs tail /ecs/${PROJECT_NAME} --follow --region $AWS_REGION
```

---

### STEP 8 — ECS Cluster + Task Definition + Service

**Cluster**: contenitore logico per i task. Non ha costo di per sé.

**Task Definition**: il "manifesto" del container — quale immagine,
quante CPU/RAM, variabili d'ambiente, secrets, log. Ogni modifica crea
una nuova revision (`:1`, `:2`, ...). Le vecchie revision restano
disponibili per rollback.

**Service**: mantiene sempre N task running. Se un task crasha, il
service ne avvia uno nuovo automaticamente. Gestisce anche il rolling
update durante i deploy.

**`--launch-type FARGATE`**: non devi gestire le EC2 sottostanti.
AWS gestisce l'infrastruttura, tu paghi solo le risorse usate dal task.

**Parametri CPU/Memory Fargate validi**:
| CPU | Memory |
|-----|--------|
| 256 | 512, 1024, 2048 |
| 512 | 1024–4096 |
| 1024 | 2048–8192 |
| 2048 | 4096–16384 |

---

### STEP 9 — ALB + Target Group + Listener

**ALB** (Application Load Balancer): distribuisce il traffico HTTP/HTTPS
ai container ECS. È l'unico punto esposto a internet.

**Target Group**: il gruppo di "destinazioni" a cui l'ALB manda il traffico.
Con ECS Fargate e `target-type ip`, ECS registra/deregistra automaticamente
gli IP dei container al loro avvio/spegnimento.

**Health Check su `/ping`**: l'ALB chiama questo endpoint ogni 30 secondi.
Se il container non risponde, viene escluso dal pool. Usiamo `/ping`
invece di `/health` perché `/health` chiama Bedrock (lento), mentre
`/ping` risponde subito con `{"status": "ok"}`.

**Listener**: regola "sulla porta 80, manda tutto al target group".
In futuro, con un dominio, si aggiunge un listener HTTPS su 443 con
certificato ACM e redirect da 80 → 443.

---

### STEP 10 — Init Database

RDS non è pubblicamente accessibile, quindi non puoi connetterti
direttamente dal tuo Mac. Le opzioni sono:

1. **Apertura temporanea SG** (come nello script): aggiungi il tuo IP,
   esegui `init_db.py`, rimuovi l'IP. Semplice per setup iniziale.

2. **Bastion host** (più sicuro): una EC2 nella stessa VPC da cui
   fare SSH tunnel. Per progetti production.

3. **SSM Session Manager** (il più sicuro): accesso al DB tramite
   AWS Systems Manager senza aprire porte. Zero esposizione.

---

## Adattare lo script a un nuovo progetto

Modifica solo la sezione `⚙️ CONFIGURAZIONE` in cima allo script:

```bash
PROJECT_NAME="mio-nuovo-progetto"   # Cambia questo
AWS_REGION="eu-west-1"              # Cambia region se serve
DB_PASSWORD="AltraPassword456"      # Password sicura
ECS_CPU="512"                       # Più CPU se l'app è pesante
ECS_MEMORY="1024"                   # Più RAM se necessario
```

Tutti i nomi delle risorse AWS vengono generati automaticamente
dal `PROJECT_NAME`, quindi non ci sono conflitti tra progetti diversi.

---

## Comandi utili post-deploy

```bash
# Verifica health API
curl http://${ALB_DNS}/health

# Vedi log in tempo reale
aws logs tail /ecs/${PROJECT_NAME} --follow --region $AWS_REGION

# Forza nuovo deploy (dopo push immagine)
aws ecs update-service \
  --cluster ${PROJECT_NAME}-cluster \
  --service ${PROJECT_NAME}-service \
  --force-new-deployment \
  --region $AWS_REGION

# Stop per ridurre costi (non elimina le risorse)
aws rds stop-db-instance \
  --db-instance-identifier ${PROJECT_NAME}-db --region $AWS_REGION
aws ecs update-service \
  --cluster ${PROJECT_NAME}-cluster \
  --service ${PROJECT_NAME}-service \
  --desired-count 0 --region $AWS_REGION

# Riavvia
aws rds start-db-instance \
  --db-instance-identifier ${PROJECT_NAME}-db --region $AWS_REGION
aws ecs update-service \
  --cluster ${PROJECT_NAME}-cluster \
  --service ${PROJECT_NAME}-service \
  --desired-count 1 --region $AWS_REGION
```

---

## Teardown completo (elimina tutto)

```bash
# ⚠️  ATTENZIONE: elimina tutte le risorse e i dati

# 1. ECS
aws ecs update-service --cluster ${PROJECT_NAME}-cluster \
  --service ${PROJECT_NAME}-service --desired-count 0 --region $AWS_REGION
aws ecs delete-service --cluster ${PROJECT_NAME}-cluster \
  --service ${PROJECT_NAME}-service --region $AWS_REGION
aws ecs delete-cluster --cluster ${PROJECT_NAME}-cluster --region $AWS_REGION

# 2. ALB
aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN --region $AWS_REGION
aws elbv2 delete-target-group --target-group-arn $TG_ARN --region $AWS_REGION

# 3. RDS (--skip-final-snapshot se non vuoi backup)
aws rds delete-db-instance \
  --db-instance-identifier ${PROJECT_NAME}-db \
  --skip-final-snapshot --region $AWS_REGION
aws rds wait db-instance-deleted \
  --db-instance-identifier ${PROJECT_NAME}-db --region $AWS_REGION
aws rds delete-db-subnet-group \
  --db-subnet-group-name ${PROJECT_NAME}-subnet-group --region $AWS_REGION

# 4. ECR
aws ecr delete-repository --repository-name $PROJECT_NAME \
  --force --region $AWS_REGION

# 5. Secrets Manager
aws secretsmanager delete-secret \
  --secret-id ${PROJECT_NAME}/db-password \
  --force-delete-without-recovery --region $AWS_REGION

# 6. IAM
aws iam detach-role-policy --role-name ${PROJECT_NAME}-ecs-task-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess
aws iam detach-role-policy --role-name ${PROJECT_NAME}-ecs-task-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
aws iam detach-role-policy --role-name ${PROJECT_NAME}-ecs-task-role \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess
aws iam detach-role-policy --role-name ${PROJECT_NAME}-ecs-task-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
aws iam delete-role-policy --role-name ${PROJECT_NAME}-ecs-task-role \
  --policy-name AllowSecretsManagerRead
aws iam delete-role --role-name ${PROJECT_NAME}-ecs-task-role

# 7. VPC (ordine importante)
aws ec2 delete-security-group --group-id $SG_ECS --region $AWS_REGION
aws ec2 delete-security-group --group-id $SG_RDS --region $AWS_REGION
aws ec2 delete-security-group --group-id $SG_ALB --region $AWS_REGION
aws ec2 delete-subnet --subnet-id $SUBNET_A --region $AWS_REGION
aws ec2 delete-subnet --subnet-id $SUBNET_B --region $AWS_REGION
aws ec2 delete-subnet --subnet-id $SUBNET_C --region $AWS_REGION
aws ec2 delete-route-table --route-table-id $RT_ID --region $AWS_REGION
aws ec2 detach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID --region $AWS_REGION
aws ec2 delete-internet-gateway --internet-gateway-id $IGW_ID --region $AWS_REGION
aws ec2 delete-vpc --vpc-id $VPC_ID --region $AWS_REGION
```

---

## Costi stimati

| Risorsa | Costo/mese | Note |
|---------|-----------|------|
| RDS db.t3.micro | ~$12 | Free tier: 750h/mese per 12 mesi |
| ECS Fargate 256/512 | ~$5 | Pay per use effettivo |
| ALB | ~$16 | Voce di costo principale |
| ECR | ~$0.50 | $0.10/GB storage |
| Secrets Manager | ~$0.40 | $0.40/secret/mese |
| CloudWatch Logs | ~$0.50 | $0.50/GB ingestito |
| **Totale** | **~$34/mese** | Senza free tier |

**Tip**: stoppa RDS e scala ECS a 0 quando non usi il progetto per
risparmiare ~$17/mese (RDS + ECS). L'ALB è la voce fissa più grande.

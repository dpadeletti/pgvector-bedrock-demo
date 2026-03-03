#!/bin/bash
# =============================================================================
# setup_aws_infra.sh
#
# Script per creare da zero l'intera infrastruttura AWS per un progetto
# FastAPI + pgvector + Bedrock su ECS Fargate.
#
# USO:
#   chmod +x setup_aws_infra.sh
#   ./setup_aws_infra.sh
#
# COSA CREA:
#   VPC + Subnets + Internet Gateway + Route Tables
#   Security Groups (ALB, ECS, RDS)
#   RDS PostgreSQL 16 + pgvector
#   ECR Repository
#   IAM Role per ECS
#   Secrets Manager (DB_PASSWORD)
#   ECS Cluster + Task Definition + Service
#   ALB + Target Group + Listener
#
# REQUISITI:
#   - AWS CLI configurata (aws configure)
#   - Docker installato e running
#   - jq installato (brew install jq)
#   Il tuo progetto deve avere: Dockerfile, api.py, config.py, embeddings.py, init_db.py, chat_ui.html# =============================================================================

set -e  # Esci subito se un comando fallisce

# =============================================================================
# ⚙️  CONFIGURAZIONE — Modifica questi valori per ogni nuovo progetto
# =============================================================================

PROJECT_NAME="pgvector-bedrock-demo"   # Nome base per tutte le risorse
AWS_REGION="eu-north-1"               # Region AWS
DB_NAME="postgres"                    # Nome database
DB_USER="postgres"                    # Username database
DB_PASSWORD="YourSecurePassword123"   # Password database (verrà messa in Secrets Manager)
DB_INSTANCE_CLASS="db.t3.micro"       # Classe RDS
DB_ENGINE_VERSION="16.6"              # Versione PostgreSQL
ECS_CPU="256"                         # CPU ECS task (256 = 0.25 vCPU)
ECS_MEMORY="512"                      # RAM ECS task (MB)
APP_PORT="8000"                       # Porta applicazione
BEDROCK_MODEL_ID="amazon.titan-embed-text-v2:0"

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

log()     { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
section() { echo -e "\n${BLUE}══════════════════════════════════════${NC}"; echo -e "${BLUE}  $1${NC}"; echo -e "${BLUE}══════════════════════════════════════${NC}"; }

# Ottieni Account ID AWS
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
log "Account AWS: $AWS_ACCOUNT_ID | Region: $AWS_REGION | Progetto: $PROJECT_NAME"

# =============================================================================
# STEP 1 — VPC + NETWORKING
# =============================================================================
section "STEP 1 — VPC + Networking"

log "Creo VPC..."
VPC_ID=$(aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --region $AWS_REGION \
  --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=${PROJECT_NAME}-vpc}]" \
  --query "Vpc.VpcId" --output text)
success "VPC creato: $VPC_ID"

# Abilita DNS hostname (necessario per RDS)
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames --region $AWS_REGION
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-support --region $AWS_REGION

log "Creo Internet Gateway..."
IGW_ID=$(aws ec2 create-internet-gateway \
  --region $AWS_REGION \
  --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=${PROJECT_NAME}-igw}]" \
  --query "InternetGateway.InternetGatewayId" --output text)
aws ec2 attach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID --region $AWS_REGION
success "Internet Gateway: $IGW_ID"

log "Creo Subnets (3 AZ)..."
# Recupera le AZ disponibili nella region
AZ_LIST=($(aws ec2 describe-availability-zones --region $AWS_REGION \
  --query "AvailabilityZones[?State=='available'].ZoneName" --output text))

SUBNET_A=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID --cidr-block 10.0.1.0/24 \
  --availability-zone ${AZ_LIST[0]} --region $AWS_REGION \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${PROJECT_NAME}-subnet-a}]" \
  --query "Subnet.SubnetId" --output text)

SUBNET_B=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID --cidr-block 10.0.2.0/24 \
  --availability-zone ${AZ_LIST[1]} --region $AWS_REGION \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${PROJECT_NAME}-subnet-b}]" \
  --query "Subnet.SubnetId" --output text)

SUBNET_C=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID --cidr-block 10.0.3.0/24 \
  --availability-zone ${AZ_LIST[2]} --region $AWS_REGION \
  --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${PROJECT_NAME}-subnet-c}]" \
  --query "Subnet.SubnetId" --output text)

success "Subnets: $SUBNET_A | $SUBNET_B | $SUBNET_C"

# Abilita auto-assign IP pubblico (necessario per ECS Fargate con pull ECR)
aws ec2 modify-subnet-attribute --subnet-id $SUBNET_A --map-public-ip-on-launch --region $AWS_REGION
aws ec2 modify-subnet-attribute --subnet-id $SUBNET_B --map-public-ip-on-launch --region $AWS_REGION
aws ec2 modify-subnet-attribute --subnet-id $SUBNET_C --map-public-ip-on-launch --region $AWS_REGION

log "Creo Route Table pubblica..."
RT_ID=$(aws ec2 create-route-table \
  --vpc-id $VPC_ID --region $AWS_REGION \
  --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=${PROJECT_NAME}-rt}]" \
  --query "RouteTable.RouteTableId" --output text)

aws ec2 create-route --route-table-id $RT_ID --destination-cidr-block 0.0.0.0/0 \
  --gateway-id $IGW_ID --region $AWS_REGION > /dev/null

aws ec2 associate-route-table --route-table-id $RT_ID --subnet-id $SUBNET_A --region $AWS_REGION > /dev/null
aws ec2 associate-route-table --route-table-id $RT_ID --subnet-id $SUBNET_B --region $AWS_REGION > /dev/null
aws ec2 associate-route-table --route-table-id $RT_ID --subnet-id $SUBNET_C --region $AWS_REGION > /dev/null
success "Route Table configurata"

# =============================================================================
# STEP 2 — SECURITY GROUPS
# =============================================================================
section "STEP 2 — Security Groups"

log "Creo Security Group ALB (porta 80 pubblica)..."
SG_ALB=$(aws ec2 create-security-group \
  --group-name "${PROJECT_NAME}-sg-alb" \
  --description "ALB - HTTP pubblico" \
  --vpc-id $VPC_ID --region $AWS_REGION \
  --query "GroupId" --output text)
aws ec2 authorize-security-group-ingress --group-id $SG_ALB \
  --protocol tcp --port 80 --cidr 0.0.0.0/0 --region $AWS_REGION > /dev/null
success "SG ALB: $SG_ALB"

log "Creo Security Group ECS (porta app dall'ALB)..."
SG_ECS=$(aws ec2 create-security-group \
  --group-name "${PROJECT_NAME}-sg-ecs" \
  --description "ECS - traffico dall'ALB" \
  --vpc-id $VPC_ID --region $AWS_REGION \
  --query "GroupId" --output text)
aws ec2 authorize-security-group-ingress --group-id $SG_ECS \
  --protocol tcp --port $APP_PORT --source-group $SG_ALB --region $AWS_REGION > /dev/null
success "SG ECS: $SG_ECS"

log "Creo Security Group RDS (porta 5432 dall'ECS)..."
SG_RDS=$(aws ec2 create-security-group \
  --group-name "${PROJECT_NAME}-sg-rds" \
  --description "RDS - accesso solo da ECS" \
  --vpc-id $VPC_ID --region $AWS_REGION \
  --query "GroupId" --output text)
aws ec2 authorize-security-group-ingress --group-id $SG_RDS \
  --protocol tcp --port 5432 --source-group $SG_ECS --region $AWS_REGION > /dev/null
success "SG RDS: $SG_RDS"

# =============================================================================
# STEP 3 — RDS PostgreSQL
# =============================================================================
section "STEP 3 — RDS PostgreSQL"

log "Creo DB Subnet Group..."
aws rds create-db-subnet-group \
  --db-subnet-group-name "${PROJECT_NAME}-subnet-group" \
  --db-subnet-group-description "Subnet group per ${PROJECT_NAME}" \
  --subnet-ids $SUBNET_A $SUBNET_B $SUBNET_C \
  --region $AWS_REGION > /dev/null
success "DB Subnet Group creato"

log "Creo istanza RDS (questo richiede 5-10 minuti)..."
aws rds create-db-instance \
  --db-instance-identifier "${PROJECT_NAME}-db" \
  --db-instance-class $DB_INSTANCE_CLASS \
  --engine postgres \
  --engine-version $DB_ENGINE_VERSION \
  --master-username $DB_USER \
  --master-user-password $DB_PASSWORD \
  --db-name $DB_NAME \
  --vpc-security-group-ids $SG_RDS \
  --db-subnet-group-name "${PROJECT_NAME}-subnet-group" \
  --no-publicly-accessible \
  --storage-type gp2 \
  --allocated-storage 20 \
  --region $AWS_REGION > /dev/null

log "Attendo che RDS sia disponibile..."
aws rds wait db-instance-available \
  --db-instance-identifier "${PROJECT_NAME}-db" \
  --region $AWS_REGION

DB_HOST=$(aws rds describe-db-instances \
  --db-instance-identifier "${PROJECT_NAME}-db" \
  --region $AWS_REGION \
  --query "DBInstances[0].Endpoint.Address" --output text)
success "RDS pronto: $DB_HOST"

# =============================================================================
# STEP 4 — ECR Repository
# =============================================================================
section "STEP 4 — ECR Repository"

log "Creo repository ECR..."
ECR_URI=$(aws ecr create-repository \
  --repository-name $PROJECT_NAME \
  --region $AWS_REGION \
  --query "repository.repositoryUri" --output text)
success "ECR: $ECR_URI"

log "Build e push immagine Docker..."
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker build -t "${ECR_URI}:latest" .
docker push "${ECR_URI}:latest"
success "Immagine pushata su ECR"

# =============================================================================
# STEP 5 — IAM Role per ECS
# =============================================================================
section "STEP 5 — IAM Role"

log "Creo IAM Role per ECS task..."
aws iam create-role \
  --role-name "${PROJECT_NAME}-ecs-task-role" \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' > /dev/null

# Policy per ECR, CloudWatch Logs, Bedrock
aws iam attach-role-policy \
  --role-name "${PROJECT_NAME}-ecs-task-role" \
  --policy-arn "arn:aws:iam::aws:policy/AmazonECS_FullAccess"

aws iam attach-role-policy \
  --role-name "${PROJECT_NAME}-ecs-task-role" \
  --policy-arn "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"

aws iam attach-role-policy \
  --role-name "${PROJECT_NAME}-ecs-task-role" \
  --policy-arn "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"

aws iam attach-role-policy \
  --role-name "${PROJECT_NAME}-ecs-task-role" \
  --policy-arn "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"

TASK_ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/${PROJECT_NAME}-ecs-task-role"
success "IAM Role: $TASK_ROLE_ARN"

# =============================================================================
# STEP 6 — Secrets Manager
# =============================================================================
section "STEP 6 — Secrets Manager"

log "Salvo DB_PASSWORD in Secrets Manager..."
SECRET_ARN=$(aws secretsmanager create-secret \
  --name "${PROJECT_NAME}/db-password" \
  --secret-string "$DB_PASSWORD" \
  --region $AWS_REGION \
  --query "ARN" --output text)

# Permesso al task role di leggere il secret
aws iam put-role-policy \
  --role-name "${PROJECT_NAME}-ecs-task-role" \
  --policy-name "AllowSecretsManagerRead" \
  --policy-document "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Action\": [\"secretsmanager:GetSecretValue\"],
      \"Resource\": \"${SECRET_ARN}\"
    }]
  }"
success "Secret ARN: $SECRET_ARN"

# =============================================================================
# STEP 7 — CloudWatch Log Group
# =============================================================================
section "STEP 7 — CloudWatch Logs"

aws logs create-log-group \
  --log-group-name "/ecs/${PROJECT_NAME}" \
  --region $AWS_REGION 2>/dev/null || warn "Log group già esistente"
success "Log group: /ecs/${PROJECT_NAME}"

# =============================================================================
# STEP 8 — ECS Cluster + Task Definition + Service
# =============================================================================
section "STEP 8 — ECS"

log "Creo ECS Cluster..."
aws ecs create-cluster \
  --cluster-name "${PROJECT_NAME}-cluster" \
  --region $AWS_REGION > /dev/null
success "ECS Cluster: ${PROJECT_NAME}-cluster"

log "Registro Task Definition..."
aws ecs register-task-definition \
  --family "${PROJECT_NAME}-task" \
  --task-role-arn $TASK_ROLE_ARN \
  --execution-role-arn $TASK_ROLE_ARN \
  --network-mode awsvpc \
  --requires-compatibilities FARGATE \
  --cpu $ECS_CPU \
  --memory $ECS_MEMORY \
  --container-definitions "[
    {
      \"name\": \"${PROJECT_NAME}-api\",
      \"image\": \"${ECR_URI}:latest\",
      \"cpu\": 0,
      \"essential\": true,
      \"portMappings\": [{
        \"containerPort\": ${APP_PORT},
        \"hostPort\": ${APP_PORT},
        \"protocol\": \"tcp\"
      }],
      \"environment\": [
        {\"name\": \"AWS_REGION\",           \"value\": \"${AWS_REGION}\"},
        {\"name\": \"DB_PORT\",              \"value\": \"5432\"},
        {\"name\": \"DB_USER\",              \"value\": \"${DB_USER}\"},
        {\"name\": \"DB_NAME\",              \"value\": \"${DB_NAME}\"},
        {\"name\": \"DB_HOST\",              \"value\": \"${DB_HOST}\"},
        {\"name\": \"AWS_BEDROCK_MODEL_ID\", \"value\": \"${BEDROCK_MODEL_ID}\"}
      ],
      \"secrets\": [{
        \"name\": \"DB_PASSWORD\",
        \"valueFrom\": \"${SECRET_ARN}\"
      }],
      \"logConfiguration\": {
        \"logDriver\": \"awslogs\",
        \"options\": {
          \"awslogs-group\": \"/ecs/${PROJECT_NAME}\",
          \"awslogs-region\": \"${AWS_REGION}\",
          \"awslogs-stream-prefix\": \"ecs\"
        }
      }
    }
  ]" \
  --region $AWS_REGION > /dev/null
success "Task Definition registrata"

# =============================================================================
# STEP 9 — ALB + Target Group + Listener
# =============================================================================
section "STEP 9 — Application Load Balancer"

log "Creo ALB..."
ALB_ARN=$(aws elbv2 create-load-balancer \
  --name "${PROJECT_NAME}-alb" \
  --subnets $SUBNET_A $SUBNET_B $SUBNET_C \
  --security-groups $SG_ALB \
  --region $AWS_REGION \
  --query "LoadBalancers[0].LoadBalancerArn" --output text)

ALB_DNS=$(aws elbv2 describe-load-balancers \
  --load-balancer-arns $ALB_ARN \
  --region $AWS_REGION \
  --query "LoadBalancers[0].DNSName" --output text)
success "ALB: $ALB_DNS"

log "Creo Target Group..."
TG_ARN=$(aws elbv2 create-target-group \
  --name "${PROJECT_NAME}-tg" \
  --protocol HTTP \
  --port $APP_PORT \
  --vpc-id $VPC_ID \
  --target-type ip \
  --health-check-path "/ping" \
  --health-check-interval-seconds 30 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3 \
  --region $AWS_REGION \
  --query "TargetGroups[0].TargetGroupArn" --output text)
success "Target Group: $TG_ARN"

log "Creo Listener HTTP:80..."
aws elbv2 create-listener \
  --load-balancer-arn $ALB_ARN \
  --protocol HTTP --port 80 \
  --default-actions "Type=forward,TargetGroupArn=${TG_ARN}" \
  --region $AWS_REGION > /dev/null
success "Listener HTTP creato"

log "Creo ECS Service..."
aws ecs create-service \
  --cluster "${PROJECT_NAME}-cluster" \
  --service-name "${PROJECT_NAME}-service" \
  --task-definition "${PROJECT_NAME}-task" \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[${SUBNET_A},${SUBNET_B},${SUBNET_C}],
    securityGroups=[${SG_ECS}],
    assignPublicIp=ENABLED
  }" \
  --load-balancers "targetGroupArn=${TG_ARN},containerName=${PROJECT_NAME}-api,containerPort=${APP_PORT}" \
  --region $AWS_REGION > /dev/null

log "Attendo che il servizio ECS si stabilizzi..."
aws ecs wait services-stable \
  --cluster "${PROJECT_NAME}-cluster" \
  --services "${PROJECT_NAME}-service" \
  --region $AWS_REGION
success "ECS Service running"

# =============================================================================
# STEP 10 — INIZIALIZZA DATABASE (pgvector)
# =============================================================================
section "STEP 10 — Init Database"

warn "Il database non è pubblicamente accessibile."
warn "Per inizializzare pgvector, aggiungi temporaneamente il tuo IP al SG RDS:"
echo ""
echo "  aws ec2 authorize-security-group-ingress \\"
echo "    --group-id $SG_RDS \\"
echo "    --protocol tcp --port 5432 \\"
echo "    --cidr \$(curl -s https://checkip.amazonaws.com)/32 \\"
echo "    --region $AWS_REGION"
echo ""
echo "  DB_HOST=$DB_HOST DB_USER=$DB_USER DB_PASSWORD=$DB_PASSWORD python init_db.py"
echo ""
echo "  # Poi rimuovi l'accesso:"
echo "  aws ec2 revoke-security-group-ingress \\"
echo "    --group-id $SG_RDS \\"
echo "    --protocol tcp --port 5432 \\"
echo "    --cidr \$(curl -s https://checkip.amazonaws.com)/32 \\"
echo "    --region $AWS_REGION"

# =============================================================================
# RIEPILOGO FINALE
# =============================================================================
section "✅ INFRASTRUTTURA CREATA"

echo ""
echo -e "${GREEN}Risorse create:${NC}"
echo "  VPC:         $VPC_ID"
echo "  Subnets:     $SUBNET_A | $SUBNET_B | $SUBNET_C"
echo "  SG ALB:      $SG_ALB"
echo "  SG ECS:      $SG_ECS"
echo "  SG RDS:      $SG_RDS"
echo "  RDS Host:    $DB_HOST"
echo "  ECR:         $ECR_URI"
echo "  Secret ARN:  $SECRET_ARN"
echo "  ECS Cluster: ${PROJECT_NAME}-cluster"
echo "  ALB DNS:     $ALB_DNS"
echo ""
echo -e "${GREEN}API disponibile su:${NC}"
echo "  http://${ALB_DNS}"
echo "  http://${ALB_DNS}/docs"
echo "  http://${ALB_DNS}/health"
echo ""

# Salva le risorse in un file per riferimento futuro
cat > infra-output.txt << EOF
# Infrastruttura ${PROJECT_NAME} — $(date)
PROJECT_NAME=${PROJECT_NAME}
AWS_REGION=${AWS_REGION}
AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID}
VPC_ID=${VPC_ID}
SUBNET_A=${SUBNET_A}
SUBNET_B=${SUBNET_B}
SUBNET_C=${SUBNET_C}
SG_ALB=${SG_ALB}
SG_ECS=${SG_ECS}
SG_RDS=${SG_RDS}
DB_HOST=${DB_HOST}
ECR_URI=${ECR_URI}
TASK_ROLE_ARN=${TASK_ROLE_ARN}
SECRET_ARN=${SECRET_ARN}
ALB_ARN=${ALB_ARN}
ALB_DNS=${ALB_DNS}
TG_ARN=${TG_ARN}
EOF

success "Output salvato in infra-output.txt"
echo ""

#!/bin/bash
# ============================================================================
# import.sh — Importa tutte le risorse AWS esistenti nello state Terraform
# Eseguire UNA SOLA VOLTA dopo terraform init
# Le risorse già importate produrranno un warning (non un errore)
# ============================================================================

set -e
echo "Importando risorse esistenti in Terraform state..."

# --- RDS (già importato nella sessione precedente, il warning è normale) ---
terraform import aws_db_instance.postgres pgvector-demo-db

# --- Security Groups ---
terraform import aws_security_group.alb sg-01b9c5dba5e5b6151
terraform import aws_security_group.rds sg-029573f0998e11be5
terraform import aws_security_group.ecs sg-00d310b017ab153e7

# --- ALB + Target Group + Listener ---
terraform import aws_lb.app \
  arn:aws:elasticloadbalancing:eu-north-1:216571348735:loadbalancer/app/pgvector-alb/d1491090043ccf91

terraform import aws_lb_target_group.app \
  arn:aws:elasticloadbalancing:eu-north-1:216571348735:targetgroup/pgvector-tg/cfb9b95e34e6176d

terraform import aws_lb_listener.http \
  arn:aws:elasticloadbalancing:eu-north-1:216571348735:listener/app/pgvector-alb/d1491090043ccf91/6c45c7c94830cb1c

# --- ECS ---
terraform import aws_ecs_cluster.main pgvector-demo-cluster
terraform import aws_ecs_service.app  pgvector-demo-cluster/pgvector-demo-service

# --- IAM Role + Policy Attachments + Inline Policy ---
terraform import aws_iam_role.ecs_task_role pgvector-ecs-task-role

terraform import aws_iam_role_policy_attachment.bedrock \
  "pgvector-ecs-task-role/arn:aws:iam::aws:policy/AmazonBedrockFullAccess"

terraform import aws_iam_role_policy_attachment.ecs_execution \
  "pgvector-ecs-task-role/arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"

terraform import aws_iam_role_policy_attachment.cloudwatch \
  "pgvector-ecs-task-role/arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"

terraform import aws_iam_role_policy.secrets_manager_read \
  "pgvector-ecs-task-role:AllowSecretsManagerRead"

# --- Secrets Manager ---
terraform import aws_secretsmanager_secret.db_password \
  arn:aws:secretsmanager:eu-north-1:216571348735:secret:pgvector-demo/db-password-hOQbOd

terraform import aws_secretsmanager_secret_version.db_password \
  "arn:aws:secretsmanager:eu-north-1:216571348735:secret:pgvector-demo/db-password-hOQbOd|AWSCURRENT"

# --- Risorse che NON vanno importate (verranno create da Terraform) ---
# aws_ecr_repository.app          → non esiste ancora
# aws_ecr_lifecycle_policy.app    → non esiste ancora
# aws_cloudwatch_log_group.ecs    → probabilmente non esiste
# aws_db_parameter_group.postgres16  → non esiste (usa default.postgres16)
# aws_db_subnet_group.default     → non esiste (usa subnet group "default" di AWS)
# aws_ecs_task_definition.app     → verrà creata nuova revisione (lifecycle gestisce il service)

echo ""
echo "✅ Import completato!"
echo "Esegui ora: terraform plan"
echo "Obiettivo: 0 to destroy, nessun -/+ sul RDS"
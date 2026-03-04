# ============================================================================
# secrets.tf — Secrets Manager
# ============================================================================

resource "aws_secretsmanager_secret" "db_password" {
  name        = "pgvector-demo/db-password"
  description = "RDS password for pgvector-bedrock-demo"

  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = var.db_password
}

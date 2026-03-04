# ============================================================================
# rds.tf — RDS PostgreSQL with pgvector
# ============================================================================

# Subnet group NUOVO (non ancora agganciato all'istanza esistente)
# Sarà usato da eventuali future istanze gestite da Terraform
resource "aws_db_subnet_group" "default" {
  name       = "pgvector-demo-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(local.tags, { Name = "pgvector-demo-subnet-group" })
}

# Parameter group NUOVO (sarà creato ma non agganciato all'istanza per ora)
# L'istanza esistente usa "default.postgres16" — non forzare il replace
resource "aws_db_parameter_group" "postgres16" {
  name   = "pgvector-demo-pg16"
  family = "postgres16"

  tags = local.tags
}

resource "aws_db_instance" "postgres" {
  identifier        = "pgvector-demo-db"
  engine            = "postgres"
  engine_version    = "16.6"
  instance_class    = var.db_instance_class
  allocated_storage = 20
  storage_type      = "gp2"

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  # ⚠️  IMPORTANTE: usiamo le risorse ESISTENTI su AWS per evitare -/+ replace
  # Il subnet group "default" e il parameter group "default.postgres16"
  # sono quelli effettivamente configurati sull'istanza RDS attuale.
  # "pgvector-demo-subnet-group" e "pgvector-demo-pg16" sono dichiarati
  # sopra ma NON ancora agganciati — li switchiamo in una sessione separata
  # solo dopo aver verificato che le nuove risorse siano state create.
  db_subnet_group_name   = "default"
  parameter_group_name   = "default.postgres16"
  vpc_security_group_ids = [aws_security_group.rds.id]

  publicly_accessible     = true
  skip_final_snapshot     = true
  deletion_protection     = false
  backup_retention_period = 0

  tags = merge(local.tags, { Name = "pgvector-demo-db" })

  lifecycle {
    # Ignora cambi su attributi che causerebbero un replacement distruttivo
    ignore_changes = [
      db_name,
      password,
      db_subnet_group_name,
      parameter_group_name,
      vpc_security_group_ids,
    ]
    # Protezione extra: blocca accidentali terraform destroy sull'istanza RDS
    prevent_destroy = true
  }
}

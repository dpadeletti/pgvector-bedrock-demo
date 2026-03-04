# ============================================================================
# security_groups.tf
# NOTA: description e name sono immutabili su AWS — devono corrispondere
# esattamente ai valori reali per evitare -/+ replace.
# I lifecycle ignore_changes su ingress/egress evitano drift con regole
# aggiunte manualmente fuori da Terraform.
# ============================================================================

# ── ALB Security Group ────────────────────────────────────────────────────────
resource "aws_security_group" "alb" {
  name        = "pgvector-alb-sg"
  description = "Security group for pgvector ALB"  # ← valore reale su AWS
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "pgvector-alb-sg" })

  lifecycle {
    # Evita diff su regole aggiunte manualmente fuori da Terraform
    ignore_changes = [ingress, egress, description]
  }
}

# ── ECS Security Group ────────────────────────────────────────────────────────
resource "aws_security_group" "ecs" {
  name        = "pgvector-ecs-sg"
  description = "Security group for ECS Fargate pgvector-demo"  # ← valore reale su AWS
  vpc_id      = var.vpc_id

  ingress {
    description     = "From ALB"
    from_port       = var.app_port
    to_port         = var.app_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "pgvector-ecs-sg" })

  lifecycle {
    ignore_changes = [ingress, egress, description]
  }
}

# ── RDS Security Group ────────────────────────────────────────────────────────
resource "aws_security_group" "rds" {
  name        = "pgvector-demo-db-sg"                       # ← nome reale su AWS
  description = "Security group for pgvector demo database" # ← descrizione reale su AWS
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from ECS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  ingress {
    description = "PostgreSQL from anywhere (dev - restrict in prod)"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "pgvector-rds-sg" })

  lifecycle {
    ignore_changes = [ingress, egress, description, name]
  }
}

# ============================================================================
# variables.tf
# ============================================================================

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-north-1"
}

variable "account_id" {
  description = "AWS Account ID"
  type        = string
  default     = "216571348735"
}

variable "vpc_id" {
  description = "Default VPC ID"
  type        = string
  default     = "vpc-051851638dc1e5f2b"
}

variable "subnet_ids" {
  description = "Default subnets (one per AZ)"
  type        = list(string)
  default     = [
    "subnet-021f61a35661a4659",  # eu-north-1a
    "subnet-0292c613618930ca8",  # eu-north-1c
    "subnet-0164c756bb8d43cd2",  # eu-north-1b
  ]
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "postgres"
}

variable "db_username" {
  description = "Database username"
  type        = string
  default     = "postgres"
}

variable "db_password" {
  description = "Database password (set via TF_VAR_db_password or terraform.tfvars)"
  type        = string
  sensitive   = true
}

variable "ecs_cpu" {
  description = "ECS task CPU units"
  type        = string
  default     = "256"
}

variable "ecs_memory" {
  description = "ECS task memory MB"
  type        = string
  default     = "512"
}

variable "app_port" {
  description = "Container port"
  type        = number
  default     = 8000
}

variable "ecr_repo_name" {
  description = "ECR repository name"
  type        = string
  default     = "pgvector-bedrock-demo"
}

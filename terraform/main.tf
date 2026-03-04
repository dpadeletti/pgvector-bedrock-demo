# ============================================================================
# main.tf — pgvector-bedrock-demo
# ============================================================================

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ── Data sources ─────────────────────────────────────────────────────────────

data "aws_vpc" "default" {
  id = var.vpc_id
}

data "aws_subnets" "default" {
  filter {
    name   = "subnet-id"
    values = var.subnet_ids
  }
}

# ============================================================================
# locals.tf
# ============================================================================

locals {
  tags = {
    Project     = "pgvector-bedrock-demo"
    ManagedBy   = "terraform"
    Environment = "demo"
  }
}

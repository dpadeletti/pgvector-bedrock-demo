# ============================================================================
# outputs.tf
# ============================================================================

output "alb_dns" {
  description = "URL pubblica dell'applicazione"
  value       = "http://${aws_lb.app.dns_name}"
}

output "ecr_repository_url" {
  description = "ECR repository URL per il CI/CD"
  value       = aws_ecr_repository.app.repository_url
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.postgres.address
}

output "rds_endpoint_full" {
  description = "RDS endpoint con porta"
  value       = "${aws_db_instance.postgres.address}:${aws_db_instance.postgres.port}"
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.app.name
}

output "secret_arn" {
  description = "Secrets Manager ARN"
  value       = aws_secretsmanager_secret.db_password.arn
}

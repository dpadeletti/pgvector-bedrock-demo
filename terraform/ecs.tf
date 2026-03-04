# ============================================================================
# ecs.tf — ECS Fargate Cluster, Task Definition, Service
# ============================================================================

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/pgvector-demo"
  retention_in_days = 7

  tags = local.tags
}

resource "aws_ecs_cluster" "main" {
  name = "pgvector-api"

  tags = local.tags
}

resource "aws_ecs_task_definition" "app" {
  family                   = "pgvector-demo-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_cpu
  memory                   = var.ecs_memory
  execution_role_arn       = aws_iam_role.ecs_task_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([{
    name      = "pgvector-demo"
    image     = "${aws_ecr_repository.app.repository_url}:latest"
    essential = true

    portMappings = [{
      containerPort = var.app_port
      protocol      = "tcp"
    }]

    environment = [
      { name = "AWS_REGION",           value = var.aws_region },
      { name = "DB_HOST",              value = aws_db_instance.postgres.address },
      { name = "DB_PORT",              value = "5432" },
      { name = "DB_NAME",              value = var.db_name },
      { name = "DB_USER",              value = var.db_username },
      { name = "AWS_BEDROCK_MODEL_ID", value = "amazon.titan-embed-text-v2:0" },
    ]

    secrets = [{
      name      = "DB_PASSWORD"
      valueFrom = aws_secretsmanager_secret.db_password.arn
    }]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  tags = local.tags
}

resource "aws_ecs_service" "app" {
  name            = "pgvector-demo-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  # Allineati ai valori reali del servizio esistente su AWS
  health_check_grace_period_seconds = 120
  availability_zone_rebalancing     = "ENABLED"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "pgvector-demo"
    container_port   = var.app_port
  }

  depends_on = [aws_lb_listener.http]

  lifecycle {
    # task_definition e desired_count: gestiti da CI/CD
    # load_balancer: immutabile dopo creazione, non forzare diff
    ignore_changes = [task_definition, desired_count, load_balancer]
  }

  tags = local.tags
}

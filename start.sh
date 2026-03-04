#!/bin/bash

aws rds start-db-instance --db-instance-identifier pgvector-demo-db --region eu-north-1
aws ecs update-service --cluster pgvector-demo-cluster --service pgvector-demo-service --desired-count 1 --region eu-north-1
echo "⏳ RDS in avvio (~3 min)..."
#!/bin/bash

aws ecs update-service --cluster pgvector-demo-cluster --service pgvector-demo-service --desired-count 0 --region eu-north-1
aws rds stop-db-instance --db-instance-identifier pgvector-demo-db --region eu-north-1
echo "💤 Infrastruttura fermata."
# Terraform — pgvector-bedrock-demo

Infrastruttura AWS gestita come codice con Terraform.

## Struttura

```
terraform/
├── main.tf                   # Provider AWS + data sources
├── variables.tf              # Variabili con default
├── locals.tf                 # Tags comuni
├── outputs.tf                # Output post-apply
├── ecr.tf                    # ECR repository
├── security_groups.tf        # SG per ALB, ECS, RDS
├── rds.tf                    # RDS PostgreSQL 16
├── secrets.tf                # Secrets Manager (DB password)
├── iam.tf                    # IAM Role ECS task
├── alb.tf                    # ALB + Target Group + Listener
├── ecs.tf                    # ECS Cluster + Task Definition + Service
├── import.sh                 # Importa risorse esistenti (esegui una volta)
├── terraform.tfvars.example  # Template variabili
└── .gitignore                # Esclude state e secrets
```

## Setup iniziale (risorse già esistenti)

```bash
cd terraform

# 1. Copia e compila le variabili
cp terraform.tfvars.example terraform.tfvars
# Inserisci db_password in terraform.tfvars

# 2. Inizializza Terraform
terraform init

# 3. Importa le risorse esistenti
./import.sh

# 4. Verifica — deve mostrare zero o poche modifiche
terraform plan

# 5. Applica eventuali diff (es. ECR nuovo)
terraform apply
```

## Uso quotidiano

```bash
# Vedere lo stato
terraform show

# Pianificare modifiche
terraform plan

# Applicare modifiche
terraform apply

# Stop risorse (risparmio costi) — NON destroy
aws rds stop-db-instance --db-instance-identifier pgvector-demo-db --region eu-north-1
aws ecs update-service --cluster pgvector-demo-cluster --service pgvector-demo-service --desired-count 0 --region eu-north-1

# Distrugge TUTTO (attento: cancella anche il DB!)
terraform destroy
```

## Modificare l'infrastruttura

Esempio — upgrade RDS da t3.micro a t3.small:
```hcl
# variables.tf
variable "db_instance_class" {
  default = "db.t3.small"   # era db.t3.micro
}
```
```bash
terraform plan    # mostra il cambio
terraform apply   # applica (~2-3 min downtime RDS)
```

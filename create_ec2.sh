#!/bin/bash
#
# Setup automatico EC2 per pgvector-bedrock-demo
# Crea un'istanza t2.micro (free tier eligible)
# ESEGUI QUESTO DA LOCALE (Mac), non su EC2!
#

set -e

echo "=================================="
echo "💻 EC2 Instance Setup"
echo "=================================="
echo ""

# Configurazione
INSTANCE_NAME="pgvector-demo-server"
INSTANCE_TYPE="t3.micro"  # Free tier
KEY_NAME="pgvector-demo-key"
REGION="eu-north-1"  # Stockholm

# Ubuntu 24.04 LTS AMI per eu-north-1
# Nota: verifica l'AMI ID più recente se necessario
AMI_ID="ami-08eb150f611ca277f"  # Ubuntu 24.04 LTS eu-north-1

# Ottieni IP pubblico
echo "🌍 Ottengo il tuo IP pubblico..."
MY_IP=$(curl -s https://checkip.amazonaws.com)
echo "   Il tuo IP: $MY_IP"
echo ""

# Crea security group
echo "🔒 Creo security group per EC2..."
SG_ID=$(aws ec2 create-security-group \
    --group-name pgvector-demo-ec2-sg \
    --description "Security group for pgvector demo EC2" \
    --region $REGION \
    --output text \
    --query 'GroupId' 2>/dev/null || \
    aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=pgvector-demo-ec2-sg" \
        --region $REGION \
        --query 'SecurityGroups[0].GroupId' \
        --output text)

echo "   Security Group ID: $SG_ID"

# Aggiungi regola SSH
echo "🔓 Configuro accesso SSH dal tuo IP..."
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 22 \
    --cidr $MY_IP/32 \
    --region $REGION 2>/dev/null || echo "   (Regola SSH già esistente)"

# Aggiungi regola HTTP
echo "🌐 Configuro accesso HTTP..."
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 80 \
    --cidr 0.0.0.0/0 \
    --region $REGION 2>/dev/null || echo "   (Regola HTTP già esistente)"

echo ""

# Crea key pair se non esiste
if [ -f "$KEY_NAME.pem" ]; then
    echo "⚠️  File $KEY_NAME.pem già esistente, lo uso"
else
    echo "🔑 Creo key pair SSH..."
    aws ec2 create-key-pair \
        --key-name $KEY_NAME \
        --region $REGION \
        --query 'KeyMaterial' \
        --output text > $KEY_NAME.pem
    
    chmod 400 $KEY_NAME.pem
    echo "   ✅ Key salvata in: $KEY_NAME.pem"
fi

echo ""

# Crea IAM role per EC2
echo "👤 Creo IAM role per accesso Bedrock..."

# Policy per Bedrock
cat > /tmp/bedrock-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:ListFoundationModels"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Trust policy
cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Crea role
aws iam create-role \
    --role-name pgvector-demo-ec2-role \
    --assume-role-policy-document file:///tmp/trust-policy.json 2>/dev/null || \
    echo "   (Role già esistente)"

# Crea policy
POLICY_ARN=$(aws iam create-policy \
    --policy-name pgvector-demo-bedrock-policy \
    --policy-document file:///tmp/bedrock-policy.json \
    --query 'Policy.Arn' \
    --output text 2>/dev/null) || \
    POLICY_ARN="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/pgvector-demo-bedrock-policy"

# Attach policy
aws iam attach-role-policy \
    --role-name pgvector-demo-ec2-role \
    --policy-arn $POLICY_ARN 2>/dev/null || \
    echo "   (Policy già attached)"

# Crea instance profile
aws iam create-instance-profile \
    --instance-profile-name pgvector-demo-ec2-profile 2>/dev/null || \
    echo "   (Instance profile già esistente)"

# Aggiungi role
aws iam add-role-to-instance-profile \
    --instance-profile-name pgvector-demo-ec2-profile \
    --role-name pgvector-demo-ec2-role 2>/dev/null || \
    echo "   (Role già nel profile)"

# Attendi
sleep 5

echo ""
echo "🚀 Lancio istanza EC2..."

# Lancia istanza
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --instance-type $INSTANCE_TYPE \
    --key-name $KEY_NAME \
    --security-group-ids $SG_ID \
    --iam-instance-profile Name=pgvector-demo-ec2-profile \
    --region $REGION \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME},{Key=Project,Value=pgvector-demo}]" \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "   Instance ID: $INSTANCE_ID"
echo ""
echo "⏳ Attendo che l'istanza sia running..."

# Attendi
aws ec2 wait instance-running \
    --instance-ids $INSTANCE_ID \
    --region $REGION

# Ottieni IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --region $REGION \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

# Cleanup
rm -f /tmp/bedrock-policy.json /tmp/trust-policy.json

echo ""
echo "=================================="
echo "✅ EC2 INSTANCE PRONTA!"
echo "=================================="
echo ""
echo "📝 Informazioni:"
echo ""
echo "   Instance ID: $INSTANCE_ID"
echo "   Public IP: $PUBLIC_IP"
echo "   Key: $KEY_NAME.pem"
echo ""
echo "📋 Connettiti con:"
echo ""
echo "   ssh -i $KEY_NAME.pem ubuntu@$PUBLIC_IP"
echo ""
echo "=================================="
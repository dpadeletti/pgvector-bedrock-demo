#!/usr/bin/env python3
"""
Verifica setup AWS - controlla cosa è già configurato
"""
import boto3
import sys
from botocore.exceptions import ClientError, NoCredentialsError


def check_aws_credentials():
    """Verifica che AWS CLI sia configurato"""
    print("🔐 Verifico credenziali AWS...")
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"   ✅ Credenziali OK")
        print(f"   Account ID: {identity['Account']}")
        print(f"   ARN: {identity['Arn']}")
        return True
    except NoCredentialsError:
        print("   ❌ Credenziali AWS non configurate")
        print("   Esegui: aws configure")
        return False
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False


def check_rds_instances():
    """Verifica istanze RDS PostgreSQL"""
    print("\n🗄️  Verifico istanze RDS PostgreSQL...")
    try:
        rds = boto3.client('rds')
        response = rds.describe_db_instances()
        
        postgres_instances = [
            db for db in response['DBInstances']
            if db['Engine'].startswith('postgres')
        ]
        
        if postgres_instances:
            print(f"   ✅ Trovate {len(postgres_instances)} istanze PostgreSQL:")
            for db in postgres_instances:
                status = db['DBInstanceStatus']
                endpoint = db.get('Endpoint', {}).get('Address', 'N/A')
                print(f"\n   📍 {db['DBInstanceIdentifier']}")
                print(f"      Status: {status}")
                print(f"      Engine: {db['Engine']} {db['EngineVersion']}")
                print(f"      Endpoint: {endpoint}")
                print(f"      Port: {db.get('Endpoint', {}).get('Port', 'N/A')}")
            return True
        else:
            print("   ⚠️  Nessuna istanza PostgreSQL trovata")
            print("   Crea una nuova istanza RDS PostgreSQL")
            return False
            
    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDenied':
            print("   ❌ Accesso negato a RDS")
            print("   Verifica permessi IAM")
        else:
            print(f"   ❌ Errore: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False


def check_bedrock_access():
    """Verifica accesso a Bedrock e modelli"""
    print("\n🤖 Verifico accesso AWS Bedrock...")
    
    # Prova diverse regioni comuni per Bedrock
    regions = ['us-east-1', 'us-west-2', 'eu-central-1']
    
    for region in regions:
        try:
            bedrock = boto3.client('bedrock', region_name=region)
            
            # Verifica accesso ai modelli
            response = bedrock.list_foundation_models()
            
            # Cerca Titan Embeddings
            titan_models = [
                m for m in response['modelSummaries']
                if 'titan' in m['modelId'].lower() and 'embed' in m['modelId'].lower()
            ]
            
            if titan_models:
                print(f"   ✅ Bedrock accessibile in {region}")
                print(f"   Modelli Titan Embeddings disponibili:")
                for model in titan_models:
                    status = "✅" if model.get('modelLifecycle', {}).get('status') == 'ACTIVE' else "⚠️"
                    print(f"      {status} {model['modelId']}")
                return True
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'AccessDeniedException':
                print(f"   ⚠️  Bedrock non accessibile in {region}")
                continue
            else:
                print(f"   ❌ Errore in {region}: {e}")
                continue
        except Exception as e:
            print(f"   ⚠️  Errore in {region}: {e}")
            continue
    
    print("   ❌ Bedrock non accessibile in nessuna regione testata")
    print("   Azioni necessarie:")
    print("      1. Vai su AWS Console → Bedrock")
    print("      2. Richiedi accesso ai modelli (Model access)")
    print("      3. Abilita: amazon.titan-embed-text-v1")
    return False


def check_ec2_instances():
    """Verifica istanze EC2"""
    print("\n💻 Verifico istanze EC2...")
    try:
        ec2 = boto3.client('ec2')
        response = ec2.describe_instances(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'stopped']}]
        )
        
        instances = []
        for reservation in response['Reservations']:
            instances.extend(reservation['Instances'])
        
        if instances:
            print(f"   ✅ Trovate {len(instances)} istanze EC2:")
            for inst in instances:
                name = 'N/A'
                for tag in inst.get('Tags', []):
                    if tag['Key'] == 'Name':
                        name = tag['Value']
                        break
                
                print(f"\n   📍 {name} ({inst['InstanceId']})")
                print(f"      State: {inst['State']['Name']}")
                print(f"      Type: {inst['InstanceType']}")
                print(f"      IP: {inst.get('PublicIpAddress', 'N/A')}")
            return True
        else:
            print("   ⚠️  Nessuna istanza EC2 trovata")
            print("   Dovrai creare un'istanza EC2 per il deployment")
            return False
            
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False


def print_summary(results):
    """Stampa riepilogo"""
    print("\n" + "="*60)
    print("📊 RIEPILOGO SETUP AWS")
    print("="*60)
    
    all_ok = all(results.values())
    
    for check, status in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {check}")
    
    print("="*60)
    
    if all_ok:
        print("🎉 Tutto pronto! Puoi procedere con il deployment")
    else:
        print("\n⚠️  Alcuni componenti mancano. Segui le istruzioni sopra.")
        print("\n📚 Prossimi passi:")
        if not results['Credenziali AWS']:
            print("   1. Configura AWS CLI: aws configure")
        if not results['RDS PostgreSQL']:
            print("   2. Crea istanza RDS PostgreSQL (vedi README)")
        if not results['Bedrock']:
            print("   3. Abilita Bedrock e richiedi accesso a Titan")
        if not results['EC2']:
            print("   4. Crea istanza EC2 (vedi EC2_DEPLOYMENT.md)")


def main():
    print("🔍 CHECK SETUP AWS - pgvector-bedrock-demo\n")
    
    results = {
        'Credenziali AWS': check_aws_credentials(),
        'RDS PostgreSQL': check_rds_instances(),
        'Bedrock': check_bedrock_access(),
        'EC2': check_ec2_instances()
    }
    
    print_summary(results)
    
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())

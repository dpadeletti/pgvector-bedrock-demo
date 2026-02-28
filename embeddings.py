"""
Generazione embeddings con AWS Bedrock Titan
"""
import json
import boto3
from typing import List
from config import AWS_REGION, BEDROCK_MODEL_ID


class BedrockEmbeddings:
    """
    Client per generare embeddings usando AWS Bedrock
    """
    
    def __init__(self, region: str = AWS_REGION, model_id: str = BEDROCK_MODEL_ID):
        """
        Inizializza client Bedrock
        
        Args:
            region: AWS region (default: us-east-1)
            model_id: ID del modello Bedrock (default: amazon.titan-embed-text-v1)
        """
        self.region = region
        self.model_id = model_id
        self.client = boto3.client('bedrock-runtime', region_name=region)
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Genera embedding per un singolo testo
        
        Args:
            text: Testo da convertire in embedding
            
        Returns:
            Lista di float rappresentante il vettore embedding
        """
        try:
            # Prepara il payload per Titan Embeddings
            payload = {
                "inputText": text
            }
            
            # Chiama Bedrock
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(payload),
                contentType='application/json',
                accept='application/json'
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            embedding = response_body.get('embedding')
            
            if not embedding:
                raise ValueError("Nessun embedding nella risposta")
            
            return embedding
            
        except Exception as e:
            print(f"❌ Errore generazione embedding: {e}")
            print(f"   Verifica accesso al modello {self.model_id} in Bedrock")
            raise
    
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Genera embeddings per multipli testi
        
        Args:
            texts: Lista di testi
            
        Returns:
            Lista di vettori embedding
        """
        embeddings = []
        for i, text in enumerate(texts):
            if i % 10 == 0 and i > 0:
                print(f"   Processati {i}/{len(texts)} embeddings...")
            embedding = self.get_embedding(text)
            embeddings.append(embedding)
        return embeddings


# Istanza globale per riuso
_bedrock_client = None

def get_bedrock_client() -> BedrockEmbeddings:
    """
    Ottiene o crea il client Bedrock singleton
    """
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = BedrockEmbeddings()
    return _bedrock_client


def get_embedding(text: str) -> List[float]:
    """
    Helper function per generare un embedding
    
    Args:
        text: Testo da convertire
        
    Returns:
        Vettore embedding
    """
    client = get_bedrock_client()
    return client.get_embedding(text)


def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Helper function per generare embeddings in batch
    
    Args:
        texts: Lista di testi
        
    Returns:
        Lista di vettori embedding
    """
    client = get_bedrock_client()
    return client.get_embeddings_batch(texts)


if __name__ == "__main__":
    # Test generazione embedding
    print("🧪 Test generazione embedding con Bedrock...")
    
    test_text = "Ciao! Questo è un test di embedding con AWS Bedrock."
    
    try:
        embedding = get_embedding(test_text)
        print(f"✅ Embedding generato con successo!")
        print(f"   Dimensioni: {len(embedding)}")
        print(f"   Prime 5 componenti: {embedding[:5]}")
    except Exception as e:
        print(f"❌ Test fallito: {e}")

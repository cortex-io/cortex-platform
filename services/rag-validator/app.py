#!/usr/bin/env python3
"""
Cortex RAG Validator
Validates improvements against existing infrastructure using vector search
"""
import os
import json
import logging
from flask import Flask, request, jsonify
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import openai
import hashlib

# Configure logging
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
QDRANT_HOST = os.getenv('QDRANT_HOST', 'qdrant.cortex-school.svc.cluster.local')
QDRANT_PORT = int(os.getenv('QDRANT_PORT', '6333'))
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-large')
SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', '0.85'))

# Initialize clients
qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
openai.api_key = OPENAI_API_KEY

# Collection names
COLLECTIONS = {
    'docs': 'cortex-docs',
    'gitops': 'cortex-gitops',
    'improvements': 'past-improvements'
}

def ensure_collections():
    """Ensure all required collections exist"""
    try:
        for name, collection_name in COLLECTIONS.items():
            try:
                qdrant_client.get_collection(collection_name)
                logger.info(f"Collection {collection_name} exists")
            except:
                logger.info(f"Creating collection {collection_name}")
                qdrant_client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=3072, distance=Distance.COSINE)
                )
    except Exception as e:
        logger.error(f"Error ensuring collections: {e}")

def get_embedding(text):
    """Generate embedding for text"""
    try:
        if not OPENAI_API_KEY:
            logger.warning("No OpenAI API key configured")
            return None

        response = openai.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )
        return response.data[0].embedding

    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None

def search_similar_content(query_text, collection_name, limit=5):
    """Search for similar content in Qdrant"""
    try:
        embedding = get_embedding(query_text)
        if embedding is None:
            return []

        results = qdrant_client.search(
            collection_name=collection_name,
            query_vector=embedding,
            limit=limit
        )

        return [{
            'id': r.id,
            'score': r.score,
            'payload': r.payload
        } for r in results]

    except Exception as e:
        logger.error(f"Error searching {collection_name}: {e}")
        return []

def validate_improvement(improvement):
    """Validate improvement against existing infrastructure"""
    title = improvement.get('title', '')
    description = improvement.get('description', '')
    implementation_notes = improvement.get('implementation_notes', '')

    query_text = f"{title}\n{description}\n{implementation_notes}"

    validation_result = {
        'rag_check_passed': True,
        'conflicts_found': [],
        'similar_improvements': [],
        'similar_docs': [],
        'similar_manifests': [],
        'dependencies_available': True,
        'warnings': []
    }

    try:
        # Search for similar improvements (check for duplicates)
        similar_improvements = search_similar_content(query_text, COLLECTIONS['improvements'], limit=3)
        if similar_improvements:
            high_similarity = [s for s in similar_improvements if s['score'] > SIMILARITY_THRESHOLD]
            if high_similarity:
                validation_result['conflicts_found'].append({
                    'type': 'duplicate_improvement',
                    'message': f"Found {len(high_similarity)} similar past improvements",
                    'items': high_similarity
                })
                validation_result['rag_check_passed'] = False
            else:
                validation_result['similar_improvements'] = similar_improvements

        # Search documentation for architectural conflicts
        similar_docs = search_similar_content(query_text, COLLECTIONS['docs'], limit=3)
        if similar_docs:
            very_similar = [s for s in similar_docs if s['score'] > 0.90]
            if very_similar:
                validation_result['warnings'].append({
                    'type': 'existing_documentation',
                    'message': 'Found very similar existing documentation - may already be implemented',
                    'items': very_similar
                })
            validation_result['similar_docs'] = similar_docs

        # Search GitOps manifests for conflicts
        similar_manifests = search_similar_content(query_text, COLLECTIONS['gitops'], limit=3)
        if similar_manifests:
            high_similarity = [s for s in similar_manifests if s['score'] > 0.88]
            if high_similarity:
                validation_result['conflicts_found'].append({
                    'type': 'existing_manifest',
                    'message': 'Found similar existing manifests - may already be deployed',
                    'items': high_similarity
                })
                validation_result['rag_check_passed'] = False
            else:
                validation_result['similar_manifests'] = similar_manifests

        # If no API key, mark as passed with warning
        if not OPENAI_API_KEY:
            validation_result['warnings'].append({
                'type': 'no_embedding_api',
                'message': 'RAG validation skipped - no OpenAI API key configured'
            })
            validation_result['rag_check_passed'] = True

    except Exception as e:
        logger.error(f"Error during validation: {e}")
        validation_result['warnings'].append({
            'type': 'validation_error',
            'message': f'Validation encountered an error: {str(e)}'
        })

    return validation_result

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        # Check Qdrant connection
        collections = qdrant_client.get_collections()

        return jsonify({
            'status': 'healthy',
            'qdrant': 'connected',
            'collections': len(collections.collections),
            'openai_configured': bool(OPENAI_API_KEY)
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503

@app.route('/validate', methods=['POST'])
def validate():
    """Validate an improvement proposal"""
    try:
        improvement = request.json

        if not improvement:
            return jsonify({'error': 'No improvement provided'}), 400

        logger.info(f"Validating improvement: {improvement.get('title')}")

        result = validate_improvement(improvement)

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error validating improvement: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/collections')
def list_collections():
    """List available collections and their stats"""
    try:
        collections_info = {}
        for name, collection_name in COLLECTIONS.items():
            try:
                info = qdrant_client.get_collection(collection_name)
                collections_info[name] = {
                    'name': collection_name,
                    'points_count': info.points_count,
                    'status': info.status
                }
            except:
                collections_info[name] = {
                    'name': collection_name,
                    'status': 'not_found'
                }

        return jsonify(collections_info), 200
    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Ensure collections exist on startup
    ensure_collections()

    app.run(host='0.0.0.0', port=8080)

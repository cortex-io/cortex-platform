#!/usr/bin/env python3
"""
Cortex MoE Router
Routes improvements to specialized expert agents using LLM-D coordination
"""
import os
import json
import logging
import requests
from flask import Flask, request, jsonify
from anthropic import Anthropic

# Configure logging
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
LLMD_ENDPOINT = os.getenv('LLMD_ENDPOINT', 'http://llmd-service.cortex.svc.cluster.local:8000')

# Expert model assignments
EXPERT_MODELS = {
    'architecture': os.getenv('EXPERT_ARCHITECTURE_MODEL', 'claude-opus-4-5'),
    'integration': os.getenv('EXPERT_INTEGRATION_MODEL', 'claude-sonnet-4-5'),
    'security': os.getenv('EXPERT_SECURITY_MODEL', 'claude-opus-4-5'),
    'database': os.getenv('EXPERT_DATABASE_MODEL', 'claude-sonnet-4-5'),
    'networking': os.getenv('EXPERT_NETWORKING_MODEL', 'claude-sonnet-4-5'),
    'monitoring': os.getenv('EXPERT_MONITORING_MODEL', 'claude-haiku-4')
}

# Initialize Anthropic client
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

def determine_expert_category(improvement):
    """Determine which expert should evaluate this improvement"""
    category = improvement.get('category', '').lower()
    imp_type = improvement.get('type', '').lower()
    description = improvement.get('description', '').lower()

    # Direct category mapping
    if category in EXPERT_MODELS:
        return category

    # Type-based mapping
    if 'integration' in imp_type or 'tool' in imp_type:
        return 'integration'

    # Keyword-based mapping
    if any(word in description for word in ['rbac', 'security', 'auth', 'encryption']):
        return 'security'
    if any(word in description for word in ['database', 'postgres', 'migration', 'schema']):
        return 'database'
    if any(word in description for word in ['network', 'ingress', 'service mesh', 'loadbalancer']):
        return 'networking'
    if any(word in description for word in ['monitor', 'metrics', 'prometheus', 'grafana']):
        return 'monitoring'

    # Default to architecture expert
    return 'architecture'

def call_expert(expert_category, improvement):
    """Call appropriate expert via LLM-D or direct API"""
    model = EXPERT_MODELS.get(expert_category, 'claude-sonnet-4-5')

    expert_prompt = f"""You are the {expert_category.upper()} expert for the Cortex infrastructure.

Evaluate this improvement proposal:

Title: {improvement.get('title')}
Category: {improvement.get('category')}
Relevance: {improvement.get('relevance')}
Description: {improvement.get('description')}
Implementation Notes: {improvement.get('implementation_notes', 'None')}

Provide your expert evaluation as JSON:

{{
  "expert": "{expert_category}",
  "evaluation": {{
    "feasibility": "high|medium|low",
    "impact": "high|medium|low",
    "risks": ["list of risks"],
    "effort": "high|medium|low",
    "priority": "high|medium|low",
    "recommendations": ["list of recommendations"],
    "dependencies": ["list of dependencies"],
    "estimated_complexity": "simple|moderate|complex"
  }}
}}

Consider:
1. Technical feasibility within Cortex architecture
2. Potential impact on existing systems
3. Security implications
4. Resource requirements
5. Integration complexity
"""

    try:
        if anthropic_client:
            # Use Anthropic API directly
            response = anthropic_client.messages.create(
                model=model,
                max_tokens=2048,
                messages=[{
                    "role": "user",
                    "content": expert_prompt
                }]
            )

            # Extract JSON from response
            content = response.content[0].text
            # Try to extract JSON from markdown code blocks
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()

            evaluation = json.loads(content)
            return evaluation

        else:
            # Use LLM-D endpoint (future implementation)
            logger.warning("No Anthropic API key, using fallback evaluation")
            return {
                "expert": expert_category,
                "evaluation": {
                    "feasibility": "medium",
                    "impact": "medium",
                    "risks": ["Not evaluated - no API key"],
                    "effort": "medium",
                    "priority": "medium",
                    "recommendations": ["Manual review required"],
                    "dependencies": [],
                    "estimated_complexity": "moderate"
                }
            }

    except Exception as e:
        logger.error(f"Error calling expert: {e}")
        return {
            "expert": expert_category,
            "evaluation": {
                "feasibility": "unknown",
                "impact": "unknown",
                "risks": [f"Evaluation failed: {str(e)}"],
                "effort": "unknown",
                "priority": "low",
                "recommendations": ["Manual review required due to evaluation failure"],
                "dependencies": [],
                "estimated_complexity": "unknown"
            },
            "error": str(e)
        }

@app.route('/health')
def health():
    """Health check endpoint"""
    api_configured = bool(ANTHROPIC_API_KEY)
    return jsonify({
        'status': 'healthy',
        'anthropic_configured': api_configured,
        'experts': list(EXPERT_MODELS.keys())
    }), 200

@app.route('/route', methods=['POST'])
def route_improvement():
    """Route improvement to appropriate expert"""
    try:
        improvement = request.json

        if not improvement:
            return jsonify({'error': 'No improvement provided'}), 400

        # Determine expert category
        expert_category = determine_expert_category(improvement)
        logger.info(f"Routing to {expert_category} expert: {improvement.get('title')}")

        # Call expert
        evaluation = call_expert(expert_category, improvement)

        return jsonify(evaluation), 200

    except Exception as e:
        logger.error(f"Error routing improvement: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/experts')
def list_experts():
    """List available experts and their models"""
    return jsonify({
        'experts': EXPERT_MODELS,
        'anthropic_configured': bool(ANTHROPIC_API_KEY)
    }), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)

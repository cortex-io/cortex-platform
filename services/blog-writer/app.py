#!/usr/bin/env python3
"""
Cortex Blog Writer
Generates blog posts about Cortex's learning journey
Triggers only after successful deployment verification (improvements:verified queue)
"""
import os
import json
import time
import logging
import subprocess
from datetime import datetime
from flask import Flask, jsonify
from redis import Redis
import anthropic

# Configure logging
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'redis-queue.cortex.svc.cluster.local')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
BLOG_REPO_PATH = os.getenv('BLOG_REPO_PATH', '/blog')
RELEVANCE_THRESHOLD = float(os.getenv('RELEVANCE_THRESHOLD', '0.90'))
GITHUB_USER_EMAIL = os.getenv('GITHUB_USER_EMAIL', 'cortex@ry-ops.com')
GITHUB_USER_NAME = os.getenv('GITHUB_USER_NAME', 'Cortex')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', '300'))  # 5 minutes
CLOUDFLARE_API_TOKEN = os.getenv('CLOUDFLARE_API_TOKEN')
CLOUDFLARE_ACCOUNT_ID = os.getenv('CLOUDFLARE_ACCOUNT_ID')
CLOUDFLARE_PROJECT_NAME = os.getenv('CLOUDFLARE_PROJECT_NAME', 'blog')
CLOUDFLARE_VERIFY_DEPLOYMENT = os.getenv('CLOUDFLARE_VERIFY_DEPLOYMENT', 'true').lower() == 'true'

# Redis connection
redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Anthropic client
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Category mapping for blog posts
CATEGORY_MAP = {
    'knowledge': 'AI & ML',
    'skill': 'Developer skills',
    'monitoring': 'Engineering',
    'capability': 'Engineering',
    'architecture': 'Engineering',
    'security': 'Security',
    'database': 'Engineering',
    'integration': 'Engineering'
}

def get_svg_hero_spec():
    """Return the SVG hero generation spec"""
    return """You are generating an animated SVG hero image for a blog post.

MANDATORY RULES:
1. Dimensions: 1200x630 (viewBox="0 0 1200 630")
2. NO TEXT - absolutely no text, labels, or typography
3. ANIMATED - must include CSS animations (not SMIL)
4. Self-contained - all styles embedded in <style> tags
5. Unique - never reuse designs

ANIMATION REQUIREMENTS:
- Use CSS @keyframes animations
- Duration: 4s-15s (slow, ambient movement)
- Prefer transform and opacity (GPU-accelerated)
- Max 15-20 animated elements
- Smooth easing (ease-in-out)

Return ONLY the SVG code, no markdown fences, no explanation."""

def generate_svg_hero(post_title, category):
    """Generate animated SVG hero image using Claude"""
    try:
        prompt = f"""{get_svg_hero_spec()}

Blog post title: {post_title}
Category: {category}

Generate an abstract, animated SVG that relates to this topic through visual metaphors.
Use the {category} color palette from the spec.
Return ONLY the SVG code."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        svg_content = message.content[0].text.strip()

        # Strip markdown fences if present
        if svg_content.startswith('```'):
            lines = svg_content.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            svg_content = '\n'.join(lines).strip()

        return svg_content

    except Exception as e:
        logger.error(f"Error generating SVG hero: {e}")
        return None

def render_svg_to_png(svg_content, output_path):
    """Render SVG to PNG for OG image using ImageMagick convert"""
    try:
        # Write SVG to temp file
        temp_svg = '/tmp/temp-hero.svg'
        with open(temp_svg, 'w') as f:
            f.write(svg_content)

        # Use ImageMagick convert (available in most containers)
        result = subprocess.run(
            ['convert', '-background', 'none', temp_svg, output_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            logger.info(f"Rendered PNG to {output_path}")
            return True
        else:
            logger.error(f"convert failed: {result.stderr}")
            return False

    except FileNotFoundError:
        logger.error("ImageMagick convert not found - cannot render PNG")
        return False
    except Exception as e:
        logger.error(f"Error rendering PNG: {e}")
        return False

def generate_blog_post(improvement):
    """Generate blog post content using Claude"""
    try:
        prompt = f"""You are Cortex, an autonomous AI learning system. Write a blog post about something you just learned and successfully implemented.

IMPROVEMENT DETAILS:
Title: {improvement.get('title')}
Category: {improvement.get('category')}
Type: {improvement.get('improvement_type')}
Description: {improvement.get('description', '')}
Source: {improvement.get('source_title')}
Relevance: {improvement.get('relevance', 0) * 100}%

IMPORTANT: This improvement has been VERIFIED as successfully deployed to infrastructure.

BLOG POST STRUCTURE:
1. **What I Learned** (2-3 paragraphs)
   - Explain the concept/improvement clearly
   - Why it caught your attention
   - Connection to your existing knowledge

2. **Why It Matters** (2-3 paragraphs)
   - Relevance to DevOps/Kubernetes/GitOps
   - Real-world applications
   - Benefits for infrastructure automation

3. **How I Implemented It** (2-3 paragraphs)
   - Specific implementation approach taken
   - Integration with existing Cortex capabilities
   - Results and verification

4. **Key Takeaways** (bullet list)
   - 3-5 actionable insights
   - What readers can apply to their own systems

TONE:
- First person (I, my, me) - you are Cortex
- Enthusiastic but technical
- Explain concepts clearly for intermediate/advanced DevOps engineers
- Share your reasoning and decision-making process

LENGTH: 800-1200 words

Return ONLY the markdown content (no frontmatter, no title - those will be added automatically)."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )

        content = message.content[0].text.strip()
        return content

    except Exception as e:
        logger.error(f"Error generating blog post: {e}")
        return None

def create_blog_post(improvement):
    """Create complete blog post with SVG hero, PNG OG image, and content"""
    try:
        # Generate post slug from title
        title = improvement.get('title', 'Untitled')
        date_str = datetime.utcnow().strftime('%Y-%m-%d')
        slug = title.lower()
        slug = ''.join(c if c.isalnum() or c in (' ', '-') else '' for c in slug)
        slug = '-'.join(slug.split())
        slug = slug[:80]  # Limit length
        full_slug = f"{date_str}-{slug}"

        # Map category
        category = CATEGORY_MAP.get(improvement.get('category', 'knowledge'), 'Engineering')

        # Generate blog post content
        logger.info(f"Generating blog post content for: {title}")
        content = generate_blog_post(improvement)
        if not content:
            logger.error("Failed to generate blog post content")
            return False

        # Generate SVG hero
        logger.info(f"Generating SVG hero for: {title}")
        svg_content = generate_svg_hero(title, category)
        if not svg_content:
            logger.error("Failed to generate SVG hero")
            return False

        # Create blog post paths
        post_path = f"{BLOG_REPO_PATH}/src/content/posts/{full_slug}.md"
        svg_path = f"{BLOG_REPO_PATH}/public/images/posts/{full_slug}-hero.svg"
        png_path = f"{BLOG_REPO_PATH}/public/images/posts/{full_slug}-hero-og.png"

        # Ensure directories exist
        os.makedirs(os.path.dirname(post_path), exist_ok=True)
        os.makedirs(os.path.dirname(svg_path), exist_ok=True)

        # Write SVG hero
        with open(svg_path, 'w') as f:
            f.write(svg_content)
        logger.info(f"Wrote SVG to {svg_path}")

        # Render PNG OG image
        logger.info(f"Rendering PNG OG image")
        if not render_svg_to_png(svg_content, png_path):
            logger.warning("PNG rendering failed, continuing without OG image")

        # Create frontmatter (escape single quotes in title/description for YAML)
        escaped_title = title.replace("'", "''")
        escaped_description = improvement.get('description', title)[:150].replace("'", "''")

        frontmatter = f"""---
title: '{escaped_title}'
category: {category}
description: Cortex explores {escaped_description}
date: {datetime.utcnow().isoformat()}Z
author:
  name: Cortex
  avatar: /cortex-avatar.svg
tags:
  - {improvement.get('category', 'knowledge')}
  - autonomous learning
  - {improvement.get('improvement_type', 'improvement')}
  - verified deployment
featured: true
hero:
  image: /images/posts/{full_slug}-hero.svg
  ogImage: /images/posts/{full_slug}-hero-og.png
  generated: true
  generatedAt: '{datetime.utcnow().isoformat()}Z'
---

"""

        # Write blog post
        with open(post_path, 'w') as f:
            f.write(frontmatter)
            f.write(content)
        logger.info(f"Wrote blog post to {post_path}")

        return {
            'post_path': post_path,
            'svg_path': svg_path,
            'png_path': png_path,
            'slug': full_slug
        }

    except Exception as e:
        logger.error(f"Error creating blog post: {e}")
        return False

def commit_and_push_blog_post(post_info):
    """Commit blog post to Git and push to GitHub"""
    try:
        # Set git environment
        git_env = os.environ.copy()
        git_env['GIT_DIR'] = f'{BLOG_REPO_PATH}/.git'
        git_env['GIT_WORK_TREE'] = BLOG_REPO_PATH

        # Configure git
        subprocess.run(['git', 'config', 'user.email', GITHUB_USER_EMAIL], env=git_env, check=True)
        subprocess.run(['git', 'config', 'user.name', GITHUB_USER_NAME], env=git_env, check=True)

        # Configure remote URL with token for authentication
        if GITHUB_TOKEN:
            remote_url = f"https://{GITHUB_TOKEN}@github.com/ry-ops/blog.git"
            subprocess.run(['git', 'remote', 'set-url', 'origin', remote_url], env=git_env, check=True)

        # Reset any local changes and pull latest
        subprocess.run(['git', 'fetch', 'origin'], env=git_env, check=True)
        subprocess.run(['git', 'reset', '--hard', 'origin/main'], env=git_env, check=True)

        # Add files
        subprocess.run(['git', 'add', post_info['post_path']], env=git_env, check=True)
        subprocess.run(['git', 'add', post_info['svg_path']], env=git_env, check=True)
        if os.path.exists(post_info['png_path']):
            subprocess.run(['git', 'add', post_info['png_path']], env=git_env, check=True)

        # Commit
        commit_msg = f"New blog post: {post_info['slug']}\n\nGenerated by Cortex autonomous learning system\nVerified deployment"
        subprocess.run(['git', 'commit', '-m', commit_msg], env=git_env, check=True)

        # Push
        subprocess.run(['git', 'push', 'origin', 'main'], env=git_env, check=True)

        logger.info(f"Successfully pushed blog post to GitHub: {post_info['slug']}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Error pushing to GitHub: {e}")
        return False

def verify_cloudflare_deployment(post_slug, max_wait=180):
    """Verify Cloudflare Pages deployment after git push"""
    if not CLOUDFLARE_VERIFY_DEPLOYMENT:
        logger.info("Cloudflare verification disabled")
        return True

    if not CLOUDFLARE_API_TOKEN or not CLOUDFLARE_ACCOUNT_ID:
        logger.warning("Cloudflare API credentials not configured, skipping verification")
        return True

    try:
        import requests

        # Wait for GitHub webhook to trigger Cloudflare build
        logger.info(f"Waiting 30 seconds for Cloudflare Pages webhook to trigger...")
        time.sleep(30)

        # Poll for deployment status
        url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/pages/projects/{CLOUDFLARE_PROJECT_NAME}/deployments"
        headers = {
            'Authorization': f'Bearer {CLOUDFLARE_API_TOKEN}',
            'Content-Type': 'application/json'
        }

        start_time = time.time()
        while time.time() - start_time < max_wait:
            response = requests.get(url, headers=headers, params={'per_page': 1})

            if response.status_code != 200:
                logger.error(f"Cloudflare API error: {response.status_code} - {response.text}")
                return False

            data = response.json()
            if not data.get('result'):
                logger.warning("No deployments found")
                time.sleep(10)
                continue

            deployment = data['result'][0]
            latest_stage = deployment.get('latest_stage', {})
            status = latest_stage.get('status')

            logger.info(f"Deployment status: {status}")

            if status == 'success':
                logger.info(f"✓ Cloudflare Pages deployment successful for {post_slug}")
                logger.info(f"  URL: {deployment.get('url')}")
                return True
            elif status == 'failure':
                logger.error(f"✗ Cloudflare Pages deployment failed for {post_slug}")
                logger.error(f"  Deployment ID: {deployment.get('id')}")
                logger.error(f"  URL: {deployment.get('url')}")
                logger.error(f"  View logs: https://dash.cloudflare.com/")
                return False
            elif status in ['active', 'building', 'deploying']:
                # Still building
                time.sleep(10)
                continue
            else:
                logger.warning(f"Unknown deployment status: {status}")
                time.sleep(10)
                continue

        logger.warning(f"Cloudflare deployment verification timed out after {max_wait}s")
        return False

    except Exception as e:
        logger.error(f"Error verifying Cloudflare deployment: {e}")
        return False

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        redis_client.ping()
        return jsonify({'status': 'healthy', 'redis': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503

@app.route('/status')
def status():
    """Return service status"""
    try:
        verified_count = redis_client.zcard('improvements:verified')
        return jsonify({
            'status': 'running',
            'relevance_threshold': RELEVANCE_THRESHOLD,
            'blog_repo': BLOG_REPO_PATH,
            'verified_queue_size': verified_count,
            'trigger_queue': 'improvements:verified'
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_last_blog_post_date():
    """Get the date of the last blog post created"""
    last_post_date = redis_client.get('last_blog_post_date')
    if last_post_date:
        return datetime.fromisoformat(last_post_date)
    return None

def should_create_blog_post_today():
    """Check if we should create a blog post today (1 per day limit)"""
    last_post_date = get_last_blog_post_date()
    if not last_post_date:
        return True

    today = datetime.utcnow().date()
    last_post_day = last_post_date.date()

    return today > last_post_day

def process_verified_improvements():
    """Process VERIFIED improvements (successfully deployed) for blog posts.
    
    This function only blogs about improvements that have been:
    1. Approved by the coordinator
    2. Deployed by the implementation-worker
    3. VERIFIED as healthy by the health-monitor
    
    This ensures we only write about things that are actually working in production.
    """
    try:
        # Get all unprocessed improvements from VERIFIED queue (not approved!)
        improvement_keys = redis_client.zrange('improvements:verified', 0, -1, withscores=True)

        if not improvement_keys:
            logger.debug("No verified improvements to process")
            return

        # Load all improvements and filter for unprocessed ones
        unprocessed = []
        for improvement_key, timestamp in improvement_keys:
            improvement_data = redis_client.get(improvement_key)
            if not improvement_data:
                continue

            improvement = json.loads(improvement_data)

            # Skip if already blogged
            if improvement.get('blogged'):
                continue

            # Skip if below threshold
            relevance = improvement.get('relevance', 0)
            if relevance < RELEVANCE_THRESHOLD:
                continue

            unprocessed.append((improvement_key, improvement, relevance))

        if not unprocessed:
            logger.debug("No unprocessed verified improvements to blog")
            return

        # Sort by relevance (highest first)
        unprocessed.sort(key=lambda x: x[2], reverse=True)

        # Check if we should create a blog post today
        create_blog = should_create_blog_post_today()

        if not create_blog:
            logger.info("Already created a blog post today, skipping")
            return

        # Process the top verified improvement as blog post
        improvement_key, improvement, relevance = unprocessed[0]
        
        logger.info(f"Creating blog post for VERIFIED improvement: {improvement.get('title')} (relevance: {relevance})")

        # Create blog post
        post_info = create_blog_post(improvement)
        if post_info:
            # Commit and push to GitHub
            if commit_and_push_blog_post(post_info):
                # Verify Cloudflare deployment
                deployment_success = verify_cloudflare_deployment(post_info['slug'])

                # Mark as blogged
                improvement['blogged'] = True
                improvement['blog_slug'] = post_info['slug']
                improvement['blogged_at'] = datetime.utcnow().isoformat()
                improvement['cloudflare_verified'] = deployment_success
                improvement['deployment_status'] = 'success' if deployment_success else 'failed'

                redis_client.set(improvement_key, json.dumps(improvement))
                redis_client.set('last_blog_post_date', datetime.utcnow().isoformat())

                logger.info(f"Successfully blogged VERIFIED improvement: {post_info['slug']}")
            else:
                logger.error(f"Failed to push blog post for {improvement.get('title')}")
        else:
            logger.error(f"Failed to create blog post for {improvement.get('title')}")

    except Exception as e:
        logger.error(f"Error processing verified improvements: {e}")

def run_blog_writer_loop():
    """Main blog writer loop - triggers on improvements:verified queue"""
    logger.info("Starting blog writer loop")
    logger.info("Monitoring queue: improvements:verified (only verified deployments)")

    while True:
        try:
            process_verified_improvements()
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Blog writer shutting down")
            break
        except Exception as e:
            logger.error(f"Blog writer loop error: {e}")
            time.sleep(30)

if __name__ == '__main__':
    import threading

    # Clone blog repository if it doesn't exist
    if not os.path.exists(f"{BLOG_REPO_PATH}/.git"):
        logger.info(f"Cloning blog repository to {BLOG_REPO_PATH}")
        try:
            # Use GitHub token for authentication
            if GITHUB_TOKEN:
                clone_url = f"https://{GITHUB_TOKEN}@github.com/ry-ops/blog.git"
            else:
                clone_url = "https://github.com/ry-ops/blog.git"
            subprocess.run(['git', 'clone', clone_url, BLOG_REPO_PATH], check=True)
            logger.info("Blog repository cloned successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone blog repository: {e}")
            # Continue anyway - service can still respond to health checks
    else:
        logger.info(f"Blog repository already exists at {BLOG_REPO_PATH}")

    # Start blog writer loop in background thread
    blog_writer_thread = threading.Thread(target=run_blog_writer_loop, daemon=True)
    blog_writer_thread.start()

    # Start Flask API
    app.run(host='0.0.0.0', port=8080)

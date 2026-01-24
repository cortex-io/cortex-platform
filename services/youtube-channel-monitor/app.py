#!/usr/bin/env python3
"""
YouTube Channel Monitor Service
Automatically monitors YouTube channels for new videos and submits them for analysis.
Supports configurable channels, rate limiting, and autonomous daily processing.
"""
import os
import json
import time
import logging
import hashlib
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from redis import Redis
import requests

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'redis-queue')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', '')
INGESTION_URL = os.getenv('INGESTION_URL', 'http://youtube-ingestion:8080')
DAILY_LIMIT = int(os.getenv('DAILY_LIMIT', '10'))
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '3600'))  # 1 hour default
CHANNELS_KEY = 'youtube:monitored_channels'
PROCESSED_KEY = 'youtube:processed_videos'
DAILY_COUNT_KEY = 'youtube:daily_count'
LAST_CHECK_KEY = 'youtube:last_check'

# Redis connection
redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# YouTube API base URL
YOUTUBE_API_BASE = 'https://www.googleapis.com/youtube/v3'


def get_channel_videos(channel_id: str, max_results: int = 10) -> list:
    """Fetch recent videos from a YouTube channel using the Data API."""
    if not YOUTUBE_API_KEY:
        logger.warning("No YouTube API key configured, using RSS feed fallback")
        return get_channel_videos_rss(channel_id, max_results)

    try:
        # First, get the uploads playlist ID
        channel_url = f"{YOUTUBE_API_BASE}/channels"
        params = {
            'part': 'contentDetails',
            'id': channel_id,
            'key': YOUTUBE_API_KEY
        }
        response = requests.get(channel_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data.get('items'):
            logger.error(f"Channel not found: {channel_id}")
            return []

        uploads_playlist = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        # Now get videos from the uploads playlist
        playlist_url = f"{YOUTUBE_API_BASE}/playlistItems"
        params = {
            'part': 'snippet',
            'playlistId': uploads_playlist,
            'maxResults': max_results,
            'key': YOUTUBE_API_KEY
        }
        response = requests.get(playlist_url, params=params, timeout=10)
        response.raise_for_status()
        playlist_data = response.json()

        videos = []
        for item in playlist_data.get('items', []):
            snippet = item.get('snippet', {})
            videos.append({
                'video_id': snippet.get('resourceId', {}).get('videoId'),
                'title': snippet.get('title', ''),
                'description': snippet.get('description', '')[:500],  # Truncate
                'published_at': snippet.get('publishedAt', ''),
                'channel_id': channel_id,
                'channel_title': snippet.get('channelTitle', '')
            })

        return videos

    except Exception as e:
        logger.error(f"Error fetching videos for channel {channel_id}: {e}")
        return []


def get_channel_videos_rss(channel_id: str, max_results: int = 10) -> list:
    """Fallback: Fetch videos using YouTube RSS feed (no API key required)."""
    try:
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        response = requests.get(rss_url, timeout=10)
        response.raise_for_status()

        # Simple XML parsing without external deps
        import re
        videos = []

        # Extract entries
        entries = re.findall(r'<entry>(.*?)</entry>', response.text, re.DOTALL)

        for entry in entries[:max_results]:
            video_id_match = re.search(r'<yt:videoId>([^<]+)</yt:videoId>', entry)
            title_match = re.search(r'<title>([^<]+)</title>', entry)
            published_match = re.search(r'<published>([^<]+)</published>', entry)

            if video_id_match:
                videos.append({
                    'video_id': video_id_match.group(1),
                    'title': title_match.group(1) if title_match else '',
                    'description': '',  # RSS doesn't include description
                    'published_at': published_match.group(1) if published_match else '',
                    'channel_id': channel_id,
                    'channel_title': ''
                })

        return videos

    except Exception as e:
        logger.error(f"Error fetching RSS for channel {channel_id}: {e}")
        return []


def is_video_processed(video_id: str) -> bool:
    """Check if a video has already been processed."""
    return redis_client.sismember(PROCESSED_KEY, video_id)


def mark_video_processed(video_id: str):
    """Mark a video as processed."""
    redis_client.sadd(PROCESSED_KEY, video_id)
    # Keep processed videos set from growing indefinitely (keep last 10000)
    if redis_client.scard(PROCESSED_KEY) > 10000:
        # This is a simple cleanup - in production might want smarter logic
        pass


def get_daily_count() -> int:
    """Get the number of videos processed today."""
    today = datetime.utcnow().strftime('%Y-%m-%d')
    count_key = f"{DAILY_COUNT_KEY}:{today}"
    count = redis_client.get(count_key)
    return int(count) if count else 0


def increment_daily_count() -> int:
    """Increment and return the daily count."""
    today = datetime.utcnow().strftime('%Y-%m-%d')
    count_key = f"{DAILY_COUNT_KEY}:{today}"
    count = redis_client.incr(count_key)
    # Set expiry for 48 hours to auto-cleanup
    redis_client.expire(count_key, 172800)
    return count


def submit_video_for_analysis(video: dict) -> bool:
    """Submit a video to the youtube-ingestion service for analysis."""
    try:
        response = requests.post(
            f"{INGESTION_URL}/analyze",
            json={
                'video_id': video['video_id'],
                'title': video['title'],
                'description': video['description']
            },
            timeout=120  # Analysis can take a while
        )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"Analyzed video '{video['title']}': relevance={result.get('relevance', 0)}, improvements={result.get('improvements', {})}")
            return True
        else:
            logger.error(f"Failed to analyze video {video['video_id']}: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"Error submitting video {video['video_id']}: {e}")
        return False


def process_channels():
    """Process all monitored channels and submit new videos."""
    channels = get_monitored_channels()
    if not channels:
        logger.info("No channels configured for monitoring")
        return {'processed': 0, 'channels': 0}

    daily_count = get_daily_count()
    if daily_count >= DAILY_LIMIT:
        logger.info(f"Daily limit reached ({daily_count}/{DAILY_LIMIT})")
        return {'processed': 0, 'channels': len(channels), 'limit_reached': True}

    processed_count = 0
    remaining = DAILY_LIMIT - daily_count

    # Calculate videos per channel
    videos_per_channel = max(1, remaining // len(channels))

    for channel in channels:
        channel_id = channel.get('id')
        channel_name = channel.get('name', channel_id)

        if daily_count + processed_count >= DAILY_LIMIT:
            break

        logger.info(f"Checking channel: {channel_name} ({channel_id})")

        videos = get_channel_videos(channel_id, max_results=videos_per_channel + 5)

        for video in videos:
            if daily_count + processed_count >= DAILY_LIMIT:
                break

            video_id = video.get('video_id')
            if not video_id:
                continue

            if is_video_processed(video_id):
                logger.debug(f"Skipping already processed video: {video_id}")
                continue

            logger.info(f"Processing new video: {video['title']}")

            if submit_video_for_analysis(video):
                mark_video_processed(video_id)
                increment_daily_count()
                processed_count += 1

            # Rate limit between submissions
            time.sleep(2)

    # Update last check time
    redis_client.set(LAST_CHECK_KEY, datetime.utcnow().isoformat())

    return {
        'processed': processed_count,
        'channels': len(channels),
        'daily_total': daily_count + processed_count,
        'daily_limit': DAILY_LIMIT
    }


def get_monitored_channels() -> list:
    """Get list of monitored channels from Redis."""
    channels_json = redis_client.get(CHANNELS_KEY)
    if channels_json:
        return json.loads(channels_json)
    return []


def set_monitored_channels(channels: list):
    """Set the list of monitored channels."""
    redis_client.set(CHANNELS_KEY, json.dumps(channels))


# Flask routes

@app.route('/health')
def health():
    """Health check endpoint."""
    try:
        redis_client.ping()
        return jsonify({
            'status': 'healthy',
            'redis': 'connected',
            'api_key_configured': bool(YOUTUBE_API_KEY)
        }), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503


@app.route('/status')
def status():
    """Get service status."""
    try:
        channels = get_monitored_channels()
        daily_count = get_daily_count()
        last_check = redis_client.get(LAST_CHECK_KEY)
        processed_total = redis_client.scard(PROCESSED_KEY)

        return jsonify({
            'status': 'running',
            'channels_monitored': len(channels),
            'channels': [{'id': c.get('id'), 'name': c.get('name', c.get('id'))} for c in channels],
            'daily_count': daily_count,
            'daily_limit': DAILY_LIMIT,
            'last_check': last_check,
            'total_videos_processed': processed_total,
            'check_interval_seconds': CHECK_INTERVAL,
            'api_key_configured': bool(YOUTUBE_API_KEY)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/channels', methods=['GET'])
def list_channels():
    """List monitored channels."""
    channels = get_monitored_channels()
    return jsonify({'channels': channels}), 200


@app.route('/channels', methods=['POST'])
def add_channel():
    """Add a channel to monitor."""
    data = request.json
    channel_id = data.get('channel_id')
    channel_name = data.get('name', channel_id)

    if not channel_id:
        return jsonify({'error': 'channel_id required'}), 400

    channels = get_monitored_channels()

    # Check if already exists
    if any(c.get('id') == channel_id for c in channels):
        return jsonify({'error': 'Channel already monitored'}), 409

    channels.append({
        'id': channel_id,
        'name': channel_name,
        'added_at': datetime.utcnow().isoformat()
    })

    set_monitored_channels(channels)

    logger.info(f"Added channel for monitoring: {channel_name} ({channel_id})")

    return jsonify({
        'success': True,
        'channel': {'id': channel_id, 'name': channel_name}
    }), 201


@app.route('/channels/<channel_id>', methods=['DELETE'])
def remove_channel(channel_id):
    """Remove a channel from monitoring."""
    channels = get_monitored_channels()
    channels = [c for c in channels if c.get('id') != channel_id]
    set_monitored_channels(channels)

    return jsonify({'success': True}), 200


@app.route('/check', methods=['POST'])
def trigger_check():
    """Manually trigger a channel check."""
    result = process_channels()
    return jsonify(result), 200


@app.route('/process-video', methods=['POST'])
def process_single_video():
    """Process a single video by ID."""
    data = request.json
    video_id = data.get('video_id')
    title = data.get('title', f'Video {video_id}')
    description = data.get('description', '')

    if not video_id:
        return jsonify({'error': 'video_id required'}), 400

    if is_video_processed(video_id):
        return jsonify({'error': 'Video already processed', 'video_id': video_id}), 409

    daily_count = get_daily_count()
    if daily_count >= DAILY_LIMIT:
        return jsonify({'error': 'Daily limit reached', 'daily_count': daily_count}), 429

    video = {
        'video_id': video_id,
        'title': title,
        'description': description
    }

    if submit_video_for_analysis(video):
        mark_video_processed(video_id)
        increment_daily_count()
        return jsonify({'success': True, 'video_id': video_id}), 200
    else:
        return jsonify({'error': 'Analysis failed'}), 500


def background_monitor():
    """Background thread for periodic channel checking."""
    import threading

    def monitor_loop():
        logger.info(f"Background monitor started (interval: {CHECK_INTERVAL}s)")

        # Initial delay to let services start
        time.sleep(30)

        while True:
            try:
                logger.info("Running scheduled channel check...")
                result = process_channels()
                logger.info(f"Channel check complete: {result}")
            except Exception as e:
                logger.error(f"Error in background monitor: {e}")

            time.sleep(CHECK_INTERVAL)

    thread = threading.Thread(target=monitor_loop, daemon=True)
    thread.start()


if __name__ == '__main__':
    logger.info("YouTube Channel Monitor starting...")
    logger.info(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    logger.info(f"Ingestion URL: {INGESTION_URL}")
    logger.info(f"Daily limit: {DAILY_LIMIT}")
    logger.info(f"Check interval: {CHECK_INTERVAL}s")
    logger.info(f"API key configured: {bool(YOUTUBE_API_KEY)}")

    # Start background monitor
    background_monitor()

    # Start Flask API
    app.run(host='0.0.0.0', port=8080)

#!/usr/bin/env python3
"""
Simple YouTube transcript extractor using youtube-transcript-api
Outputs JSON to stdout for Node.js consumption
"""

import sys
import json
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

def extract_transcript(video_id, language='en'):
    """Extract transcript and return as JSON"""
    try:
        # Fetch using instance method
        api = YouTubeTranscriptApi()
        data = api.fetch(video_id, [language])
        
        # Convert to our format (attributes are: text, start, duration)
        result = {
            'success': True,
            'segments': [
                {
                    'text': item.text,
                    'offset': int(item.start * 1000),  # Convert seconds to ms
                    'duration': int(item.duration * 1000)  # Convert seconds to ms
                }
                for item in data
            ],
            'language': language
        }
        print(json.dumps(result))
        return 0
    except TranscriptsDisabled:
        print(json.dumps({'success': False, 'error': 'Transcripts are disabled for this video'}))
        return 1
    except NoTranscriptFound:
        print(json.dumps({'success': False, 'error': f'No transcript found for language: {language}'}))
        return 1
    except Exception as e:
        print(json.dumps({'success': False, 'error': str(e)}))
        return 1

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'success': False, 'error': 'Usage: extract_transcript.py <video_id> [language]'}))
        sys.exit(1)
    
    video_id = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else 'en'
    
    sys.exit(extract_transcript(video_id, language))

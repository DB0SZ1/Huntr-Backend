import json
import os
import hashlib
from functools import wraps
import time
import requests

CONFIG_FILE = 'config.json'

def load_config():
    """Load user configuration from config.json"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading config: {e}")
    
    # Default config if file doesn't exist
    return {
        "preferences": {
            "role_categories": ["developer", "designer", "community", "marketing", "wordpress", "no_code"],
            "min_confidence": 50,
            "urgency_levels": ["high", "medium", "low"],
            "blocked_keywords": [],
            "required_keywords": [],
            "platforms": []
        },
        "notification": {
            "whatsapp_enabled": True,
            "email_enabled": True,
            "max_per_scan": 20
        }
    }

def matches_preferences(opportunity, analysis):
    """Filter opportunities based on user preferences"""
    config = load_config()
    prefs = config.get('preferences', {})
    
    # Role category filter
    allowed_roles = prefs.get('role_categories', [])
    if allowed_roles and analysis.get('role_category') not in allowed_roles:
        return False, "Role not in preferences"
    
    # Confidence filter
    min_confidence = prefs.get('min_confidence', 50)
    if analysis.get('confidence', 0) < min_confidence:
        return False, f"Confidence below {min_confidence}%"
    
    # Urgency filter
    allowed_urgency = prefs.get('urgency_levels', ['high', 'medium', 'low'])
    if analysis.get('urgency') not in allowed_urgency:
        return False, "Urgency not in preferences"
    
    # Platform filter
    allowed_platforms = prefs.get('platforms', [])
    if allowed_platforms and opportunity.get('platform') not in allowed_platforms:
        return False, "Platform not in preferences"
    
    # Keyword filters
    text = f"{opportunity.get('title', '')} {opportunity.get('description', '')}".lower()
    
    blocked = prefs.get('blocked_keywords', [])
    if any(keyword.lower() in text for keyword in blocked):
        return False, "Contains blocked keyword"
    
    required = prefs.get('required_keywords', [])
    if required and not any(keyword.lower() in text for keyword in required):
        return False, "Missing required keyword"
    
    return True, "Passed all filters"

def normalize_opportunity(opp):
    """Create content hash to detect duplicates across platforms"""
    # Use title + first 200 chars of description for hash
    content = f"{opp.get('title', '')} {opp.get('description', '')[:200]}"
    # Normalize text
    content = content.lower().strip()
    # Create hash
    return hashlib.md5(content.encode()).hexdigest()

def retry_on_failure(max_retries=3, delay=5, backoff=2):
    """Retry decorator with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    if attempt == max_retries - 1:
                        print(f"❌ {func.__name__} failed after {max_retries} attempts: {str(e)}")
                        return []
                    
                    wait_time = delay * (backoff ** attempt)
                    print(f"⏳ {func.__name__} attempt {attempt + 1} failed, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                except Exception as e:
                    print(f"❌ {func.__name__} unexpected error: {str(e)}")
                    return []
            return []
        return wrapper
    return decorator

def format_number(num):
    """Format large numbers for readability"""
    if num >= 1_000_000_000:
        return f"{num / 1_000_000_000:.1f}B"
    elif num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    else:
        return str(int(num))

def truncate_text(text, max_length=100):
    """Truncate text to max length with ellipsis"""
    if not text:
        return ""
    text = str(text)
    return text[:max_length] + "..." if len(text) > max_length else text

def validate_url(url):
    """Validate if string is a valid URL"""
    if not url:
        return False
    return url.startswith('http://') or url.startswith('https://')

def extract_domain(url):
    """Extract domain from URL"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc
    except:
        return url
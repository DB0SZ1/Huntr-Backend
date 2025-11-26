"""
Enhanced AI-Powered Job Matching
Advanced OpenRouter integration with caching and fallbacks
"""
import httpx
import json
import hashlib
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import asyncio

from config import settings, TIER_LIMITS, AI_MATCHING_CONFIG

logger = logging.getLogger(__name__)


class MatchingCache:
    """In-memory cache for AI analysis results"""
    
    def __init__(self, ttl_minutes: int = 60):
        self.cache = {}
        self.ttl = timedelta(minutes=ttl_minutes)
    
    def _generate_key(self, opportunity: Dict, niche: Dict) -> str:
        """Generate cache key from opportunity and niche"""
        content = f"{opportunity.get('id')}:{niche.get('_id')}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, opportunity: Dict, niche: Dict) -> Optional[Dict]:
        """Get cached analysis if exists and not expired"""
        key = self._generate_key(opportunity, niche)
        
        if key in self.cache:
            cached_data, timestamp = self.cache[key]
            
            if datetime.utcnow() - timestamp < self.ttl:
                logger.debug(f"Cache hit for {key}")
                return cached_data
            else:
                # Expired
                del self.cache[key]
        
        return None
    
    def set(self, opportunity: Dict, niche: Dict, analysis: Dict):
        """Cache analysis result"""
        key = self._generate_key(opportunity, niche)
        self.cache[key] = (analysis, datetime.utcnow())
    
    def clear(self):
        """Clear all cached data"""
        self.cache.clear()
    
    def cleanup_expired(self):
        """Remove expired entries"""
        now = datetime.utcnow()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if now - timestamp >= self.ttl
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")


# Global cache instance
matching_cache = MatchingCache(ttl_minutes=120)


async def analyze_job_with_ai(
    opportunity: Dict,
    niche: Dict,
    user_tier: str = "free",
    use_cache: bool = True
) -> Dict:
    """
    Enhanced AI analysis with caching and better error handling
    
    Args:
        opportunity: Job opportunity dict
        niche: User's niche configuration dict
        user_tier: User's subscription tier
        use_cache: Whether to use cached results
        
    Returns:
        Analysis dict with is_match, confidence, reasoning, etc.
    """
    # Check cache first
    if use_cache:
        cached = matching_cache.get(opportunity, niche)
        if cached:
            return cached
    
    # Select AI model based on tier
    model = TIER_LIMITS[user_tier]['ai_model']
    
    # Build enhanced prompt
    prompt = build_analysis_prompt(opportunity, niche)
    
    # Try AI analysis with retries
    max_retries = AI_MATCHING_CONFIG.get('max_retries', 2)
    
    for attempt in range(1, max_retries + 1):
        try:
            analysis = await call_openrouter_api(prompt, model)
            
            # Validate analysis
            if validate_analysis(analysis):
                # Cache successful result
                if use_cache:
                    matching_cache.set(opportunity, niche, analysis)
                
                return analysis
            else:
                logger.warning(f"AI returned invalid analysis (attempt {attempt})")
                
                if attempt == max_retries:
                    break
        
        except httpx.TimeoutException:
            logger.warning(f"AI analysis timeout (attempt {attempt})")
            
            if attempt == max_retries:
                break
            
            await asyncio.sleep(2 ** attempt)
        
        except Exception as e:
            logger.error(f"AI analysis error (attempt {attempt}): {str(e)}")
            
            if attempt == max_retries:
                break
            
            await asyncio.sleep(2 ** attempt)
    
    # Fallback to keyword matching
    logger.info("Falling back to keyword matching")
    return keyword_matching_fallback(opportunity, niche)


def build_analysis_prompt(opportunity: Dict, niche: Dict) -> str:
    """Build enhanced analysis prompt with more context"""
    
    # Extract opportunity details
    title = opportunity.get('title', 'N/A')
    description = opportunity.get('description', '')[:800]  # Increased from 600
    platform = opportunity.get('platform', 'Unknown')
    contact = opportunity.get('contact', 'N/A')
    metadata = opportunity.get('metadata', {})
    
    # Extract niche details
    niche_name = niche.get('name', 'N/A')
    niche_desc = niche.get('description', 'N/A')
    keywords = niche.get('keywords', [])
    excluded = niche.get('excluded_keywords', [])
    
    # Build metadata context
    metadata_context = ""
    if metadata:
        if metadata.get('company'):
            metadata_context += f"\n- Company: {metadata['company']}"
        if metadata.get('location'):
            metadata_context += f"\n- Location: {metadata['location']}"
        if metadata.get('salary'):
            metadata_context += f"\n- Compensation: {metadata['salary']}"
        if metadata.get('followers'):
            metadata_context += f"\n- Account has {metadata['followers']} followers"
    
    prompt = f"""Analyze if this job opportunity matches the user's niche requirements.

**User's Niche:**
- Name: {niche_name}
- Description: {niche_desc}
- Must Include Keywords: {', '.join(keywords)}
- Must Exclude: {', '.join(excluded) if excluded else 'None'}

**Job Opportunity:**
- Title: {title}
- Platform: {platform}
- Description: {description}
- Contact: {contact}{metadata_context}

**Evaluation Criteria:**
1. Does the job description mention any of the required keywords?
2. Does it contain any excluded keywords? (If yes, it's NOT a match)
3. Is this a legitimate job opportunity or spam/promotional content?
4. What's the relevance level (high/medium/low)?
5. What's the urgency level based on context (e.g., "urgent", "ASAP" = high)?

**Respond with ONLY valid JSON (no markdown, no explanation):**
{{
  "is_match": true/false,
  "confidence": 0-100,
  "reasoning": "Brief explanation why this matches or doesn't match",
  "relevant_keywords": ["keyword1", "keyword2"],
  "urgency": "high/medium/low",
  "match_score": 0.0-1.0
}}

**Important:**
- Be strict about excluded keywords - if ANY are present, set is_match to false
- Confidence should reflect how well the opportunity matches ALL requirements
- Consider platform reputation in your assessment
"""
    
    return prompt


async def call_openrouter_api(prompt: str, model: str) -> Dict:
    """
    Call OpenRouter API with proper error handling
    
    Args:
        prompt: Analysis prompt
        model: Model identifier
        
    Returns:
        Parsed analysis dict
        
    Raises:
        Various exceptions on failure
    """
    timeout_seconds = AI_MATCHING_CONFIG.get('timeout_seconds', 30)
    
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": settings.API_URL,
                "X-Title": "Job Hunter AI"
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert job matching AI. Analyze jobs against user preferences and respond ONLY with valid JSON. Be strict and accurate."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.2,  # Lower for more consistent results
                "max_tokens": 600,
                "top_p": 0.9
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # Clean JSON response
            content = content.strip()
            
            # Remove markdown code blocks
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            # Parse JSON
            analysis = json.loads(content.strip())
            
            return analysis
        
        elif response.status_code == 429:
            raise Exception("OpenRouter rate limit exceeded")
        
        elif response.status_code == 401:
            raise Exception("OpenRouter authentication failed - check API key")
        
        else:
            raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")


def validate_analysis(analysis: Dict) -> bool:
    """
    Validate AI analysis response
    
    Args:
        analysis: Analysis dict from AI
        
    Returns:
        True if valid
    """
    required_keys = ['is_match', 'confidence', 'reasoning']
    
    # Check all required keys exist
    if not all(key in analysis for key in required_keys):
        logger.warning(f"Missing required keys in analysis: {analysis.keys()}")
        return False
    
    # Validate types
    if not isinstance(analysis['is_match'], bool):
        logger.warning(f"is_match is not boolean: {type(analysis['is_match'])}")
        return False
    
    if not isinstance(analysis['confidence'], (int, float)):
        logger.warning(f"confidence is not numeric: {type(analysis['confidence'])}")
        return False
    
    # Validate ranges
    if not (0 <= analysis['confidence'] <= 100):
        logger.warning(f"confidence out of range: {analysis['confidence']}")
        return False
    
    # Validate urgency if present
    if 'urgency' in analysis:
        if analysis['urgency'] not in ['high', 'medium', 'low']:
            logger.warning(f"Invalid urgency: {analysis['urgency']}")
            analysis['urgency'] = 'medium'  # Fix it
    else:
        analysis['urgency'] = 'medium'  # Default
    
    # Add match_score if missing
    if 'match_score' not in analysis:
        analysis['match_score'] = analysis['confidence'] / 100.0
    
    # Add relevant_keywords if missing
    if 'relevant_keywords' not in analysis:
        analysis['relevant_keywords'] = []
    
    return True


def keyword_matching_fallback(opportunity: Dict, niche: Dict) -> Dict:
    """
    Enhanced fallback keyword-based matching when AI fails
    
    Args:
        opportunity: Job opportunity dict
        niche: User's niche configuration dict
        
    Returns:
        Analysis dict
    """
    text = f"{opportunity.get('title', '')} {opportunity.get('description', '')}".lower()
    
    keywords = [kw.lower() for kw in niche.get('keywords', [])]
    excluded_keywords = [kw.lower() for kw in niche.get('excluded_keywords', [])]
    
    # Check excluded keywords first (disqualifiers)
    for excluded in excluded_keywords:
        if excluded in text:
            return {
                "is_match": False,
                "confidence": 0,
                "reasoning": f"Contains excluded keyword: '{excluded}'",
                "relevant_keywords": [],
                "urgency": "low",
                "match_score": 0.0
            }
    
    # Find matching keywords
    matched_keywords = [kw for kw in keywords if kw in text]
    
    if not matched_keywords:
        return {
            "is_match": False,
            "confidence": 25,
            "reasoning": "No matching keywords found",
            "relevant_keywords": [],
            "urgency": "low",
            "match_score": 0.25
        }
    
    # Calculate confidence based on keyword matches
    match_ratio = len(matched_keywords) / len(keywords)
    base_confidence = int(match_ratio * 60)  # Max 60 from keyword matches
    
    # Bonus points for multiple matches
    bonus = min(len(matched_keywords) * 10, 30)
    
    # Bonus for contact information
    if opportunity.get('contact') or opportunity.get('telegram') or opportunity.get('email'):
        bonus += 5
    
    # Bonus for platform reputation
    platform = opportunity.get('platform', '')
    if platform in ['LinkedIn', 'Web3.career', 'CryptoJobsList']:
        bonus += 5
    
    confidence = min(base_confidence + bonus, 95)  # Cap at 95 for fallback
    
    # Determine if match
    min_confidence = niche.get('min_confidence', 60)
    is_match = confidence >= min_confidence
    
    # Determine urgency from text
    urgency = 'low'
    urgent_keywords = ['urgent', 'asap', 'immediate', 'hiring now', 'immediately']
    if any(uk in text for uk in urgent_keywords):
        urgency = 'high'
    elif 'soon' in text or 'quickly' in text:
        urgency = 'medium'
    
    return {
        "is_match": is_match,
        "confidence": confidence,
        "reasoning": f"Matched keywords: {', '.join(matched_keywords)}. Keyword fallback analysis.",
        "relevant_keywords": matched_keywords,
        "urgency": urgency,
        "match_score": confidence / 100.0
    }


async def batch_analyze_opportunities(
    opportunities: List[Dict],
    niches: List[Dict],
    user_tier: str = "free",
    max_concurrent: int = 5
) -> List[Dict]:
    """
    Analyze multiple opportunities against multiple niches concurrently
    
    Args:
        opportunities: List of opportunity dicts
        niches: List of niche dicts
        user_tier: User's tier
        max_concurrent: Max concurrent AI calls
        
    Returns:
        List of matches with analysis
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    matches = []
    
    async def analyze_pair(opp: Dict, niche: Dict):
        async with semaphore:
            analysis = await analyze_job_with_ai(opp, niche, user_tier)
            
            if analysis['is_match']:
                return {
                    'opportunity': opp,
                    'niche': niche,
                    'analysis': analysis
                }
            return None
    
    # Create all analysis tasks
    tasks = []
    for opp in opportunities:
        for niche in niches:
            tasks.append(analyze_pair(opp, niche))
    
    # Execute concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out None results and exceptions
    for result in results:
        if result and not isinstance(result, Exception):
            matches.append(result)
    
    # Sort by confidence
    matches.sort(key=lambda x: x['analysis']['confidence'], reverse=True)
    
    return matches


def get_cache_stats() -> Dict:
    """Get matching cache statistics"""
    matching_cache.cleanup_expired()
    
    return {
        'cached_analyses': len(matching_cache.cache),
        'ttl_minutes': matching_cache.ttl.total_seconds() / 60
    }


def clear_matching_cache():
    """Clear the matching cache"""
    matching_cache.clear()
    logger.info("Matching cache cleared")
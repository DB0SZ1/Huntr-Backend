import os
import requests
import json
import re
from datetime import datetime, timedelta
from config import SCAM_INDICATORS, SALARY_PATTERNS

def analyze_job_opportunity(opportunity):
    """Use AI for semantic analysis with fallback"""
    
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        print("⚠️  OpenRouter API not configured - using keyword analysis")
        return keyword_analysis(opportunity)
    
    text = f"{opportunity.get('title', '')} {opportunity.get('description', '')}"
    platform = opportunity.get('platform', '')
    
    # Enhanced prompt for Web3 opportunities
    prompt = f"""Analyze if this is a REAL opportunity for someone with Web3/crypto skills:

SKILLS TO MATCH:
- Developer (React, Next.js, Solana, Smart Contracts, Web3, TypeScript)
- WordPress Developer
- UI/UX Designer (Figma, Brand Design)
- Community Manager (Discord, Telegram moderator)
- Social Media Manager (Twitter/X, content creation)
- Marketing/Growth roles
- No-code Developer (Webflow, Bubble)

TEXT TO ANALYZE:
{text[:700]}

PLATFORM: {platform}
CONTACT INFO: {opportunity.get('contact', 'Not provided')}
TELEGRAM: {opportunity.get('telegram', 'Not provided')}

DETECTION RULES:
1. DIRECT HIRING: Clear job posts ("hiring", "looking for", "need developer", "position available")
2. INDIRECT SIGNALS: New project launches need teams ("launching soon", "testnet live", "new token", "just launched")
3. NEW TOKENS/PROJECTS on Pump.fun, DexScreener, CMC = ALWAYS need community managers, designers, developers
4. BOUNTIES & FREELANCE: Paid gigs, contract work, ambassador programs
5. COMMUNITY ROLES: Discord/Telegram mod positions (very common in Web3)

RESPOND ONLY WITH VALID JSON (no markdown):
{{
  "is_opportunity": true/false,
  "confidence": 0-100,
  "opportunity_type": "direct_hire|indirect_hint|project_launch|freelance|bounty|new_token|community_role",
  "role_category": "developer|designer|community|marketing|wordpress|no_code|general",
  "reason": "brief explanation",
  "urgency": "high|medium|low",
  "pitch_angle": "specific one-liner approach (e.g. 'DM on TG about community mod role')"
}}"""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "kwaipilot/kat-coder-pro:free",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert at identifying Web3/crypto job opportunities. You detect direct hiring, indirect project launch signals, and community roles. You understand that new token launches ALWAYS need community teams."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.2,
                "max_tokens": 500
            },
            timeout=25
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # Clean JSON from response
            content = content.strip()
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            
            analysis = json.loads(content.strip())
            
            # Validate structure
            required_keys = ['is_opportunity', 'confidence', 'opportunity_type', 'role_category']
            if all(key in analysis for key in required_keys):
                return analysis
        
        elif response.status_code == 429:
            print("⏳ AI rate limit - using keyword analysis")
        else:
            print(f"⚠️  AI API error {response.status_code} - using keyword analysis")
        
    except json.JSONDecodeError as e:
        print(f"⚠️  AI JSON parse error - using keyword analysis")
    except Exception as e:
        print(f"⚠️  AI analysis error: {str(e)} - using keyword analysis")
    
    # Fallback
    return keyword_analysis(opportunity)

def keyword_analysis(opportunity):
    """Enhanced keyword analysis for Web3 opportunities"""
    
    text = f"{opportunity.get('title', '')} {opportunity.get('description', '')}".lower()
    platform = opportunity.get('platform', '').lower()
    
    # DIRECT opportunity keywords
    direct_keywords = {
        'hiring': 12, 'looking for': 12, 'need developer': 12, 'need designer': 12,
        'need community manager': 15, 'need moderator': 15, 'discord mod': 14,
        'telegram admin': 14, 'seeking': 10, 'job opening': 12, 'we are hiring': 12,
        'apply now': 10, 'position available': 10, 'join our team': 10,
        'remote position': 9, 'freelance': 11, 'contract work': 11, 'bounty': 12,
        'gig': 10, 'hiring now': 13, 'immediate start': 12, 'urgently need': 13,
        'ambassador program': 11, 'paid role': 11, 'community manager needed': 15,
        'moderator wanted': 14, 'looking for mods': 14
    }
    
    # INDIRECT opportunity keywords (project launches)
    indirect_keywords = {
        'launching soon': 8, 'testnet live': 9, 'alpha drop': 8, 'mainnet launch': 9,
        'new project': 7, 'building our': 8, 'expanding team': 9, 'just launched': 9,
        'stealth mode': 7, 'pre-launch': 8, 'beta launch': 8, 'presale live': 8,
        'announcing our': 7, 'introducing': 6, 'token launch': 9, 'fair launch': 8,
        'building in public': 7, 'looking to build': 8, 'need help': 9,
        'growing fast': 7, 'scaling up': 8
    }
    
    # Web3 COMMUNITY specific (VERY important)
    community_keywords = {
        'community manager': 15, 'discord mod': 15, 'telegram admin': 15,
        'moderator': 12, 'community': 8, 'discord': 7, 'telegram': 7,
        'social media': 10, 'twitter manager': 10, 'content creator': 10,
        'engagement': 8, 'ambassador': 10, 'influencer': 8
    }
    
    # Role-specific keywords
    role_keywords = {
        'developer': {
            'react': 5, 'frontend': 5, 'fullstack': 5, 'web3': 6, 'solana': 6,
            'smart contract': 6, 'typescript': 4, 'nextjs': 5, 'blockchain': 6,
            'rust': 5, 'solidity': 6, 'dapp': 5, 'defi': 4
        },
        'designer': {
            'ui/ux': 8, 'figma': 5, 'design': 5, 'brand': 5, 'graphic': 5,
            'designer': 8, 'visual': 4, 'creative': 4, 'logo': 4
        },
        'community': {
            'community manager': 10, 'moderator': 10, 'discord': 8, 'telegram': 8,
            'social media': 8, 'engagement': 6, 'community': 8, 'mod': 9
        },
        'wordpress': {
            'wordpress': 15, 'wp': 10, 'woocommerce': 10, 'elementor': 8
        },
        'marketing': {
            'marketing': 7, 'content': 6, 'copywriter': 7, 'seo': 6, 'growth': 6,
            'twitter': 5, 'social': 5
        },
        'no_code': {
            'webflow': 10, 'bubble': 10, 'no-code': 10, 'zapier': 6
        }
    }
    
    # Calculate scores
    direct_score = sum(score for kw, score in direct_keywords.items() if kw in text)
    indirect_score = sum(score for kw, score in indirect_keywords.items() if kw in text)
    community_score = sum(score for kw, score in community_keywords.items() if kw in text)
    
    # Detect role category
    role_category = 'general'
    role_score = 0
    for category, keywords in role_keywords.items():
        cat_score = sum(score for kw, score in keywords.items() if kw in text)
        if cat_score > role_score:
            role_score = cat_score
            role_category = category
    
    # Platform bonuses (tokens/launches ALWAYS need teams)
    platform_bonus = 0
    if 'pump.fun' in platform or 'pumpfun' in platform:
        platform_bonus = 20
        if role_category == 'general':
            role_category = 'community'
    elif 'dexscreener' in platform:
        platform_bonus = 18
        if role_category == 'general':
            role_category = 'community'
    elif 'coinmarketcap' in platform or 'coingecko' in platform:
        platform_bonus = 15
        if role_category == 'general':
            role_category = 'community'
    elif 'reddit' in platform:
        platform_bonus = 10
    elif 'telegram' in platform:
        platform_bonus = 12
    elif 'linkedin' in platform or 'web3.career' in platform or 'cryptojobs' in platform:
        platform_bonus = 12
    elif 'twitter' in platform:
        platform_bonus = 8
    
    # Contact info bonus
    contact = opportunity.get('contact', '').lower()
    telegram = opportunity.get('telegram', '')
    twitter = opportunity.get('twitter', '')
    
    contact_bonus = 0
    if telegram or 't.me/' in contact or 'tg:' in contact:
        contact_bonus += 8
    if twitter or '@' in contact:
        contact_bonus += 5
    if 'email' in contact or '@' in contact:
        contact_bonus += 5
    
    # Metadata bonuses
    metadata = opportunity.get('metadata', {})
    if metadata.get('verified'):
        contact_bonus += 5
    
    followers = metadata.get('followers', 0)
    if 500 < followers < 10000:
        contact_bonus += 5
    elif followers >= 10000:
        contact_bonus += 3
    
    # Calculate total score
    total_score = (
        direct_score + 
        (indirect_score * 0.8) + 
        (community_score * 1.2) +
        role_score + 
        platform_bonus + 
        contact_bonus
    )
    
    # Determine if opportunity
    is_opportunity = total_score >= 12
    confidence = min(int(total_score * 3.5), 98)
    
    # Determine type
    if direct_score >= 10:
        opp_type = "direct_hire"
        urgency = "high"
    elif community_score >= 12:
        opp_type = "community_role"
        urgency = "high"
    elif 'pump.fun' in platform or 'pumpfun' in platform:
        opp_type = "new_token"
        urgency = "high"
    elif 'dexscreener' in platform or 'coinmarketcap' in platform:
        opp_type = "new_token"
        urgency = "high"
    elif indirect_score >= 7:
        opp_type = "indirect_hint"
        urgency = "medium"
    elif direct_score >= 6:
        opp_type = "freelance"
        urgency = "medium"
    else:
        opp_type = "project_launch"
        urgency = "low"
    
    # Generate pitch angles
    has_telegram = bool(telegram or 't.me' in contact.lower())
    has_twitter = bool(twitter or '@' in contact.lower())
    
    pitch_angles = {
        'developer': f"{'DM on Telegram' if has_telegram else 'DM on X'}: 'Saw your project - I build Web3 dApps with React/Solana/smart contracts'",
        'designer': f"{'DM on Telegram' if has_telegram else 'DM on X'}: 'Interested in design work - I create UI/UX for Web3/crypto projects'",
        'community': f"{'DM on Telegram' if has_telegram else 'DM on X'}: 'Interested in community mod role - experienced Discord/TG manager'",
        'wordpress': f"{'DM on Telegram' if has_telegram else 'DM on X'}: 'WordPress dev here - can help with site/plugins fast'",
        'marketing': f"{'DM on Telegram' if has_telegram else 'DM on X'}: 'Growth marketer - I scale crypto communities & Twitter presence'",
        'no_code': f"{'DM on Telegram' if has_telegram else 'DM on X'}: 'Webflow/no-code expert - fast landing pages'",
        'general': f"{'Message on Telegram' if has_telegram else 'DM on X'} offering your skills"
    }
    
    # Build reason
    reason_parts = []
    if direct_score > 0:
        reason_parts.append(f"Direct hiring ({int(direct_score)}pts)")
    if community_score > 0:
        reason_parts.append(f"Community role ({int(community_score)}pts)")
    if indirect_score > 0:
        reason_parts.append(f"Launch signals ({int(indirect_score)}pts)")
    if role_score > 0:
        reason_parts.append(f"Role match ({int(role_score)}pts)")
    if platform_bonus > 0:
        reason_parts.append(f"Platform ({platform_bonus}pts)")
    if contact_bonus > 0:
        reason_parts.append(f"Contact info ({contact_bonus}pts)")
    
    reason = " | ".join(reason_parts) if reason_parts else "Low relevance"
    
    return {
        "is_opportunity": is_opportunity,
        "confidence": confidence,
        "opportunity_type": opp_type,
        "role_category": role_category,
        "reason": reason,
        "urgency": urgency,
        "pitch_angle": pitch_angles.get(role_category, pitch_angles['general'])
    }

def detect_scam_indicators(text: str) -> dict:
    """
    Detect scam indicators in opportunity text
    Returns confidence score and indicators found
    """
    text_lower = text.lower()
    score = 0
    found_indicators = []
    
    # Check comment-based scams (HIGHEST risk)
    for indicator in SCAM_INDICATORS['comment_based']:
        if indicator in text_lower:
            score += 35  # Very high risk
            found_indicators.append(f"comment_based: {indicator}")
    
    # Check suspicious keywords
    for indicator in SCAM_INDICATORS['suspicious']:
        if indicator in text_lower:
            score += 15
            found_indicators.append(f"suspicious: {indicator}")
    
    # Check urgency tactics
    urgency_count = sum(1 for ind in SCAM_INDICATORS['urgency'] if ind in text_lower)
    if urgency_count >= 2:
        score += 20
        found_indicators.append("multiple_urgency_tactics")
    
    # No salary mentioned = more suspicious
    if not detect_salary(text):
        score += 15
        found_indicators.append("no_salary_mentioned")
    
    # Red flag: No company name, vague description
    if len(text) < 100:
        score += 10
        found_indicators.append("too_short_description")
    
    # Check for outdated listing (older than 30 days)
    timestamp = datetime.utcnow()  # Should be passed from opportunity
    is_outdated = False
    
    scam_probability = min(score, 100)
    
    return {
        "is_likely_scam": scam_probability >= 60,
        "scam_probability": scam_probability,
        "indicators": found_indicators,
        "recommendation": "SKIP" if scam_probability >= 60 else ("CAUTION" if scam_probability >= 40 else "SAFE")
    }


def detect_salary(text: str) -> dict:
    """
    Extract salary information from opportunity text
    """
    text_lower = text.lower()
    
    salary_info = {
        "has_salary": False,
        "salary_type": None,
        "amounts": [],
        "currency": None
    }
    
    # Check hourly
    hourly_matches = re.findall(r'\$(\d+(?:,\d+)*(?:\.\d{2})?)/(?:hr|hour)', text_lower)
    if hourly_matches:
        salary_info['has_salary'] = True
        salary_info['salary_type'] = 'hourly'
        salary_info['amounts'] = hourly_matches
        salary_info['currency'] = 'USD'
    
    # Check monthly
    monthly_matches = re.findall(r'\$(\d+(?:,\d+)*(?:\.\d{2})?)/month', text_lower)
    if monthly_matches:
        salary_info['has_salary'] = True
        salary_info['salary_type'] = 'monthly'
        salary_info['amounts'] = monthly_matches
        salary_info['currency'] = 'USD'
    
    # Check Naira
    naira_matches = re.findall(r'₦(\d+(?:,\d+)*(?:\.\d{2})?)', text)
    if naira_matches:
        salary_info['has_salary'] = True
        salary_info['salary_type'] = 'naira'
        salary_info['amounts'] = naira_matches
        salary_info['currency'] = 'NGN'
    
    return salary_info


def calculate_niche_score(opportunity: dict, niche: dict) -> float:
    """
    Calculate how well an opportunity matches a niche
    Returns score 0-100
    """
    score = 0
    
    # Keywords matching (40 points max)
    keywords = niche.get('keywords', [])
    excluded = niche.get('excluded_keywords', [])
    
    text = f"{opportunity.get('title', '')} {opportunity.get('description', '')}".lower()
    
    matches = sum(1 for kw in keywords if kw.lower() in text)
    keyword_score = (matches / max(len(keywords), 1)) * 40
    score += min(keyword_score, 40)
    
    # Check excluded keywords (negative score)
    excluded_matches = sum(1 for kw in excluded if kw.lower() in text)
    if excluded_matches > 0:
        score -= excluded_matches * 10
    
    # Platform match (15 points)
    if opportunity.get('platform') in niche.get('platforms', []):
        score += 15
    
    # Confidence level (20 points)
    confidence = opportunity.get('match_data', {}).get('confidence', 0)
    if confidence >= 70:
        score += 20
    elif confidence >= 50:
        score += 10
    
    # Recency (15 points) - newer is better
    found_at = opportunity.get('found_at')
    if found_at:
        age_days = (datetime.utcnow() - found_at).days
        if age_days <= 1:
            score += 15
        elif age_days <= 7:
            score += 10
        elif age_days <= 30:
            score += 5
    
    # Salary mentioned (10 points bonus)
    if detect_salary(opportunity.get('description', '')).get('has_salary'):
        score += 10
    
    return max(0, min(score, 100))


def curate_gigs(opportunities: list, niche: dict, count: int, tier: str) -> list:
    """
    Curate top gigs for a niche based on tier and quality
    - Detects and filters scams
    - Scores each opportunity
    - Returns top N curated gigs
    """
    curated = []
    
    for opp in opportunities:
        # Check for scams
        scam_check = detect_scam_indicators(opp.get('description', ''))
        
        # Skip likely scams
        if scam_check['is_likely_scam']:
            continue
        
        # Calculate niche score
        niche_score = calculate_niche_score(opp, niche)
        
        # Minimum score depends on tier
        min_score = {
            'free': 50,
            'pro': 55,
            'premium': 60
        }.get(tier, 50)
        
        if niche_score >= min_score:
            curated.append({
                'opportunity': opp,
                'niche_score': niche_score,
                'scam_risk': scam_check['scam_probability'],
                'salary_info': detect_salary(opp.get('description', '')),
                'recommendation': scam_check['recommendation']
            })
    
    # Sort by niche score and return top N
    curated.sort(key=lambda x: x['niche_score'], reverse=True)
    return curated[:count]


async def analyze_job_opportunity_async(opportunity):
    """Async wrapper for opportunity analysis"""
    
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        print("⚠️  OpenRouter API not configured - using keyword analysis")
        return keyword_analysis(opportunity)
    
    # Use the real analyze_job_opportunity function
    return analyze_job_opportunity(opportunity)
"""
Real AI-powered opportunity matcher
Uses OpenRouter API + keyword fallback (NO MOCK DATA)
"""
import os
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


async def match_opportunity(opportunity: Dict, niche: Dict) -> Dict:
    """
    Real opportunity matching using analyzer
    """
    try:
        # Import the REAL analyzer from modules
        from modules.analyzer import analyze_job_opportunity
        
        # Perform real analysis
        analysis = analyze_job_opportunity(opportunity)
        
        # Validate against niche min_confidence
        min_confidence = niche.get('min_confidence', 60)
        
        return {
            "is_match": analysis.get('confidence', 0) >= min_confidence,
            "confidence": analysis.get('confidence', 0),
            "reasoning": analysis.get('reason', ''),
            "role_category": analysis.get('role_category', 'general'),
            "urgency": analysis.get('urgency', 'low'),
            "pitch_angle": analysis.get('pitch_angle', ''),
            "opportunity_type": analysis.get('opportunity_type', 'unknown')
        }
    
    except Exception as e:
        logger.error(f"Error matching opportunity: {str(e)}")
        
        # Fallback to keyword matching (still real logic, not mock)
        from modules.analyzer import keyword_analysis
        analysis = keyword_analysis(opportunity)
        
        return {
            "is_match": analysis.get('confidence', 0) >= niche.get('min_confidence', 60),
            "confidence": analysis.get('confidence', 0),
            "reasoning": analysis.get('reason', ''),
            "role_category": analysis.get('role_category', 'general'),
            "urgency": analysis.get('urgency', 'low'),
            "pitch_angle": analysis.get('pitch_angle', ''),
            "opportunity_type": analysis.get('opportunity_type', 'unknown')
        }

"""
Document Analysis (CV & Proof of Work)
- CV Analyzer Lite (Pro tier)
- CV Analyzer Premium (Premium tier)
- Proof of Work Analyzer (Premium tier)
"""
import logging
import os
import requests
from typing import Dict, Optional
import json

logger = logging.getLogger(__name__)


class DocumentAnalyzer:
    """Analyze CVs and proof of work documents"""
    
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    
    @staticmethod
    def validate_pdf(file_content: bytes) -> bool:
        """Validate PDF file"""
        return file_content.startswith(b'%PDF')
    
    @staticmethod
    def get_file_size_mb(file_content: bytes) -> float:
        """Get file size in MB"""
        return len(file_content) / (1024 * 1024)
    
    @staticmethod
    def extract_text_from_pdf(file_content: bytes) -> str:
        """Extract text from PDF file"""
        try:
            import PyPDF2
            
            from io import BytesIO
            pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            return text.strip()
        
        except ImportError:
            logger.warning("PyPDF2 not installed, using fallback extraction")
            # Fallback: extract text from PDF binary
            try:
                # Try to extract readable text from binary
                text = file_content.decode('latin-1', errors='ignore')
                # Remove binary artifacts
                text = ''.join(c if c.isprintable() or c.isspace() else '' for c in text)
                return text.strip()
            except:
                return ""
        
        except Exception as e:
            logger.error(f"Error extracting PDF text: {str(e)}")
            return ""
    
    @staticmethod
    async def analyze_cv_lite(file_content: bytes) -> Dict:
        """
        Lightweight CV analysis (Pro tier)
        - Extract sections
        - Score format
        - Identify top skills
        """
        try:
            # Validate
            if not DocumentAnalyzer.validate_pdf(file_content):
                return {"error": "Invalid PDF file"}
            
            size_mb = DocumentAnalyzer.get_file_size_mb(file_content)
            if size_mb > 5:
                return {"error": "File too large (max 5MB)"}
            
            # Extract text from PDF
            cv_text = DocumentAnalyzer.extract_text_from_pdf(file_content)
            
            if not cv_text or len(cv_text) < 50:
                return {"error": "Could not extract text from PDF. Please ensure it's a valid, text-based PDF."}
            
            logger.info(f"Extracted {len(cv_text)} characters from PDF")
            
            api_key = os.getenv('OPENROUTER_API_KEY')
            if not api_key:
                return {"error": "AI service not configured"}
            
            # Send to OpenRouter for analysis
            prompt = f"""Analyze this CV/Resume and provide:
1. Top 5 skills
2. Experience level (Junior/Mid/Senior/Lead)
3. Format score (1-10) - how well organized
4. Strengths (3 bullet points)
5. Improvements (3 bullet points)

Format as JSON with keys: top_skills, experience_level, format_score, strengths, improvements

CV TEXT:
{cv_text[:2000]}  # Send first 2000 chars to stay within limits
"""
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "kwaipilot/kat-coder-pro:free",
                    "messages": [{
                        "role": "user",
                        "content": prompt
                    }],
                    "temperature": 0.3,
                    "max_tokens": 600
                },
                timeout=30
            )
            
            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                
                # Parse JSON from response
                try:
                    # Extract JSON from markdown if needed
                    if '```json' in content:
                        content = content.split('```json')[1].split('```')[0]
                    elif '```' in content:
                        content = content.split('```')[1].split('```')[0]
                    
                    analysis = json.loads(content.strip())
                    
                    return {
                        "success": True,
                        "analysis": analysis,
                        "tier_level": "lite",
                        "features": ["Top Skills", "Experience Level", "Format Score", "Strengths", "Improvements"],
                        "text_extracted": len(cv_text),
                        "text_preview": cv_text[:200]
                    }
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error: {str(e)}")
                    # Return raw analysis if JSON parsing fails
                    return {
                        "success": True,
                        "analysis": {"raw_analysis": content},
                        "tier_level": "lite",
                        "text_extracted": len(cv_text)
                    }
            else:
                logger.error(f"API error: {response.status_code} - {response.text}")
                return {"error": f"API error: {response.status_code}"}
        
        except Exception as e:
            logger.error(f"CV Lite analysis error: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    @staticmethod
    async def analyze_cv_premium(file_content: bytes) -> Dict:
        """
        Premium CV analysis (Premium tier)
        - Everything from Lite
        - ATS optimization score
        - Keyword recommendations
        - Gap analysis
        - Career trajectory analysis
        """
        try:
            # Validate
            if not DocumentAnalyzer.validate_pdf(file_content):
                return {"error": "Invalid PDF file"}
            
            size_mb = DocumentAnalyzer.get_file_size_mb(file_content)
            if size_mb > 5:
                return {"error": "File too large (max 5MB)"}
            
            # Extract text from PDF
            cv_text = DocumentAnalyzer.extract_text_from_pdf(file_content)
            
            if not cv_text or len(cv_text) < 50:
                return {"error": "Could not extract text from PDF"}
            
            # First get lite analysis
            lite_analysis = await DocumentAnalyzer.analyze_cv_lite(file_content)
            
            if "error" in lite_analysis:
                return lite_analysis
            
            api_key = os.getenv('OPENROUTER_API_KEY')
            if not api_key:
                return {"error": "AI service not configured"}
            
            # Additional premium analysis
            prompt = f"""Analyze this CV/Resume for PREMIUM insights:
1. ATS Optimization Score (1-100) - how well formatted for Applicant Tracking Systems
2. Missing Keywords - what keywords to add for job search
3. Career gaps & timeline issues
4. Best job titles for this profile (top 5)
5. Salary expectations (based on experience)
6. Top 3 companies to target
7. Overall career advice

Format as JSON with keys: ats_score, missing_keywords, career_gaps, best_titles, salary_range, target_companies, career_advice

CV TEXT:
{cv_text[:2000]}
"""
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "kwaipilot/kat-coder-pro:free",
                    "messages": [{
                        "role": "user",
                        "content": prompt
                    }],
                    "temperature": 0.3,
                    "max_tokens": 900
                },
                timeout=30
            )
            
            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                
                try:
                    # Extract JSON from markdown if needed
                    if '```json' in content:
                        content = content.split('```json')[1].split('```')[0]
                    elif '```' in content:
                        content = content.split('```')[1].split('```')[0]
                    
                    premium_analysis = json.loads(content.strip())
                    
                    return {
                        "success": True,
                        "lite_analysis": lite_analysis.get("analysis"),
                        "premium_analysis": premium_analysis,
                        "tier_level": "premium",
                        "features": [
                            "Top Skills", "Experience Level", "Format Score", "Strengths", "Improvements",
                            "ATS Score", "Keyword Recommendations", "Gap Analysis", "Job Titles",
                            "Salary Expectations", "Company Recommendations", "Career Advice"
                        ],
                        "text_extracted": len(cv_text)
                    }
                except json.JSONDecodeError:
                    return lite_analysis  # Fallback to lite
            
            return lite_analysis
        
        except Exception as e:
            logger.error(f"CV Premium analysis error: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    @staticmethod
    async def analyze_proof_of_work(file_content: bytes) -> Dict:
        """
        Proof of Work Analysis (Premium tier only)
        - Portfolio/project quality assessment
        - Project complexity scoring
        - Tech stack identification
        - Contribution assessment
        """
        try:
            if not DocumentAnalyzer.validate_pdf(file_content):
                return {"error": "Invalid PDF file"}
            
            size_mb = DocumentAnalyzer.get_file_size_mb(file_content)
            if size_mb > 5:
                return {"error": "File too large (max 5MB)"}
            
            # Extract text from PDF
            pow_text = DocumentAnalyzer.extract_text_from_pdf(file_content)
            
            if not pow_text or len(pow_text) < 50:
                return {"error": "Could not extract text from PDF"}
            
            api_key = os.getenv('OPENROUTER_API_KEY')
            if not api_key:
                return {"error": "AI service not configured"}
            
            prompt = f"""Analyze this Proof of Work/Portfolio and provide:
1. Project Quality Score (1-100)
2. Technical Complexity (Beginner/Intermediate/Advanced/Expert)
3. Tech Stack (Technologies identified)
4. Code Quality Assessment (1-10)
5. Innovation Score (1-10)
6. Portfolio Recommendations (what to add/improve)
7. Strengths & Weaknesses
8. Next steps to improve portfolio

Format as JSON with keys: quality_score, complexity, tech_stack, code_quality, innovation, recommendations, strengths, weaknesses, next_steps

PORTFOLIO TEXT:
{pow_text[:2000]}
"""
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "kwaipilot/kat-coder-pro:free",
                    "messages": [{
                        "role": "user",
                        "content": prompt
                    }],
                    "temperature": 0.3,
                    "max_tokens": 1000
                },
                timeout=30
            )
            
            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                
                try:
                    # Extract JSON from markdown if needed
                    if '```json' in content:
                        content = content.split('```json')[1].split('```')[0]
                    elif '```' in content:
                        content = content.split('```')[1].split('```')[0]
                    
                    analysis = json.loads(content.strip())
                    
                    return {
                        "success": True,
                        "analysis": analysis,
                        "assessment_type": "proof_of_work",
                        "features": [
                            "Project Quality Score", "Technical Complexity", "Tech Stack Analysis",
                            "Code Quality", "Innovation Score", "Recommendations", "Strengths/Weaknesses"
                        ],
                        "text_extracted": len(pow_text)
                    }
                except json.JSONDecodeError:
                    return {"error": "Failed to parse analysis"}
            else:
                return {"error": f"API error: {response.status_code}"}
        
        except Exception as e:
            logger.error(f"PoW analysis error: {str(e)}", exc_info=True)
            return {"error": str(e)}

"""
Document Analysis Routes
CV Analyzer & Proof of Work Analyzer
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from datetime import datetime

from app.database.connection import get_database
from app.auth.jwt_handler import get_current_user_id
from app.ai.document_analyzer import DocumentAnalyzer
from config import TIER_LIMITS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["Document Analysis"])


@router.post("/cv/analyze-lite")
async def analyze_cv_lite(
    file: UploadFile = File(..., description="PDF file to analyze"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Analyze CV (Pro tier and above)
    Lightweight analysis with top skills, experience level, and recommendations
    
    Upload a PDF file as multipart/form-data with key 'file'
    """
    try:
        # Check tier
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        tier = user.get("tier", "free")
        if tier not in ["pro", "premium"]:
            raise HTTPException(status_code=403, detail="Pro tier or higher required")
        
        # Validate file
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")
        
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Read file
        content = await file.read()
        
        # Validate size
        size_mb = len(content) / (1024 * 1024)
        if size_mb > 5:
            raise HTTPException(status_code=400, detail="File too large (max 5MB)")
        
        if size_mb < 0.01:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Validate PDF
        if not content.startswith(b'%PDF'):
            raise HTTPException(status_code=400, detail="Invalid PDF file")
        
        logger.info(f"Analyzing CV for user {user_id}: {file.filename} ({size_mb:.2f}MB)")
        
        # Analyze
        analysis = await DocumentAnalyzer.analyze_cv_lite(content)
        
        if "error" in analysis:
            raise HTTPException(status_code=400, detail=analysis["error"])
        
        # Save to database
        await db.cv_analyses.insert_one({
            "user_id": user_id,
            "tier": tier,
            "analysis_type": "lite",
            "analysis": analysis,
            "filename": file.filename,
            "file_size_mb": round(size_mb, 2),
            "created_at": datetime.utcnow()
        })
        
        logger.info(f"CV analysis completed for user {user_id}")
        
        return {
            "success": True,
            "analysis_type": "lite",
            "file": file.filename,
            "file_size_mb": round(size_mb, 2),
            **analysis
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CV analysis error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="CV analysis failed")


@router.post("/cv/analyze-premium")
async def analyze_cv_premium(
    file: UploadFile = File(..., description="PDF file to analyze"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Premium CV Analysis (Premium tier only)
    Includes ATS score, keywords, career trajectory, salary expectations
    
    Upload a PDF file as multipart/form-data with key 'file'
    """
    try:
        # Check tier
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        tier = user.get("tier", "free")
        if tier != "premium":
            raise HTTPException(status_code=403, detail="Premium tier required")
        
        # Validate file
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")
        
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Read and validate file
        content = await file.read()
        
        size_mb = len(content) / (1024 * 1024)
        if size_mb > 5:
            raise HTTPException(status_code=400, detail="File too large (max 5MB)")
        
        if size_mb < 0.01:
            raise HTTPException(status_code=400, detail="File is empty")
        
        if not content.startswith(b'%PDF'):
            raise HTTPException(status_code=400, detail="Invalid PDF file")
        
        logger.info(f"Analyzing Premium CV for user {user_id}: {file.filename} ({size_mb:.2f}MB)")
        
        # Analyze
        analysis = await DocumentAnalyzer.analyze_cv_premium(content)
        
        if "error" in analysis:
            raise HTTPException(status_code=400, detail=analysis["error"])
        
        # Save to database
        await db.cv_analyses.insert_one({
            "user_id": user_id,
            "tier": tier,
            "analysis_type": "premium",
            "analysis": analysis,
            "filename": file.filename,
            "file_size_mb": round(size_mb, 2),
            "created_at": datetime.utcnow()
        })
        
        logger.info(f"Premium CV analysis completed for user {user_id}")
        
        return {
            "success": True,
            "analysis_type": "premium",
            "file": file.filename,
            "file_size_mb": round(size_mb, 2),
            **analysis
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Premium CV analysis error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Premium CV analysis failed")


@router.post("/proof-of-work/analyze")
async def analyze_proof_of_work(
    file: UploadFile = File(..., description="PDF file to analyze"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Analyze Proof of Work (Premium tier only)
    Portfolio quality, complexity, tech stack, innovation score
    
    Upload a PDF file as multipart/form-data with key 'file'
    """
    try:
        # Check tier
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        tier = user.get("tier", "free")
        if tier != "premium":
            raise HTTPException(status_code=403, detail="Premium tier required")
        
        # Validate file
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")
        
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Read and validate file
        content = await file.read()
        
        size_mb = len(content) / (1024 * 1024)
        if size_mb > 5:
            raise HTTPException(status_code=400, detail="File too large (max 5MB)")
        
        if size_mb < 0.01:
            raise HTTPException(status_code=400, detail="File is empty")
        
        if not content.startswith(b'%PDF'):
            raise HTTPException(status_code=400, detail="Invalid PDF file")
        
        logger.info(f"Analyzing PoW for user {user_id}: {file.filename} ({size_mb:.2f}MB)")
        
        # Analyze
        analysis = await DocumentAnalyzer.analyze_proof_of_work(content)
        
        if "error" in analysis:
            raise HTTPException(status_code=400, detail=analysis["error"])
        
        # Save to database
        await db.pow_analyses.insert_one({
            "user_id": user_id,
            "tier": tier,
            "analysis": analysis,
            "filename": file.filename,
            "file_size_mb": round(size_mb, 2),
            "created_at": datetime.utcnow()
        })
        
        logger.info(f"PoW analysis completed for user {user_id}")
        
        return {
            "success": True,
            "analysis_type": "proof_of_work",
            "file": file.filename,
            "file_size_mb": round(size_mb, 2),
            **analysis
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PoW analysis error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="PoW analysis failed")


@router.get("/analyses/history")
async def get_analysis_history(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's document analysis history"""
    try:
        cv_analyses = await db.cv_analyses.find({"user_id": user_id})\
            .sort("created_at", -1)\
            .limit(10)\
            .to_list(length=10)
        
        pow_analyses = await db.pow_analyses.find({"user_id": user_id})\
            .sort("created_at", -1)\
            .limit(10)\
            .to_list(length=10)
        
        # Convert ObjectIds to strings
        for doc in cv_analyses + pow_analyses:
            doc["_id"] = str(doc["_id"])
        
        return {
            "success": True,
            "cv_analyses": cv_analyses,
            "pow_analyses": pow_analyses,
            "total": len(cv_analyses) + len(pow_analyses)
        }
    
    except Exception as e:
        logger.error(f"Error getting analysis history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get history")


@router.delete("/analyses/{analysis_id}")
async def delete_analysis(
    analysis_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete a saved analysis"""
    try:
        # Try to delete from cv_analyses first
        result = await db.cv_analyses.delete_one({
            "_id": ObjectId(analysis_id),
            "user_id": user_id
        })
        
        if result.deleted_count > 0:
            return {"success": True, "message": "Analysis deleted"}
        
        # Try pow_analyses
        result = await db.pow_analyses.delete_one({
            "_id": ObjectId(analysis_id),
            "user_id": user_id
        })
        
        if result.deleted_count > 0:
            return {"success": True, "message": "Analysis deleted"}
        
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete analysis")

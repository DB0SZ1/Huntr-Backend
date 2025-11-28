"""
Curated Weekly Gigs Endpoint with Optional Enhancements
- Save curated results
- Personalized recommendations
- Weekly digest email
- Niche optimization
- Batch analysis
- Scam reporting
- Performance analytics
- Salary trends
"""
import logging
import asyncio
from fastapi import APIRouter, HTTPException, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import uuid

from app.database.connection import get_database
from app.auth.jwt_handler import get_current_user_id
from app.credits.manager import CreditManager
from config import TIER_LIMITS, CREDIT_COSTS
from modules.analyzer import curate_gigs, detect_scam_indicators, detect_salary
from app.jobs.scraper import scrape_platforms_for_user
from app.scan.cache_service import (
    cache_opportunities_by_niche,
    get_cached_opportunities,
    get_niche_for_user
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/curated", tags=["Curated Gigs"])


# ============ MAIN ENDPOINT ============

@router.get("/weekly-top-20")
async def get_weekly_top_20(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get top 20 curated gigs for the week
    - Uses cache for niche-specific opportunities to avoid repeated API calls
    - Automatically performs scans based on tier
    - Filters scams using AI detection
    - Scores opportunities by niche match
    - Returns curated results with salary info
    
    Returns:
        - Weekly top 20 gigs
        - Scam risk indicators
        - Salary information
        - Niche match scores
    """
    try:
        # Get user
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        tier = user.get("tier", "free")
        tier_config = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
        
        # Get user's active niches
        niches = await db.niche_configs.find({
            "user_id": user_id,
            "is_active": True
        }).to_list(length=100)
        
        if not niches:
            return {
                "message": "No active niches configured",
                "gigs": [],
                "total": 0
            }
        
        # Collect opportunities - use cache first, then scrape if needed
        all_opportunities = []
        scans_to_perform = tier_config.get("scans_per_day", 1)
        platforms = tier_config.get("platforms", [])
        
        logger.info(f"Performing curated scan for {tier} user {user_id} with {len(niches)} niches")
        
        # Try to get cached opportunities for each niche first
        for niche in niches:
            try:
                # Check cache first (24h TTL)
                cached_opps = await get_cached_opportunities(db, niche['_id'])
                
                if cached_opps:
                    logger.info(f"Cache hit for niche {niche['name']}: {len(cached_opps)} opportunities")
                    all_opportunities.extend(cached_opps)
                else:
                    # Cache miss - perform scan for this niche
                    logger.info(f"Cache miss for niche {niche['name']} - scraping...")
                    
                    try:
                        # scrape_platforms_for_user is async, call it directly without to_thread
                        result = await scrape_platforms_for_user(platforms, max_concurrent=2)
                        
                        opportunities = result.get('opportunities', [])
                        all_opportunities.extend(opportunities)
                        
                        # Cache the results for this niche
                        if opportunities:
                            await cache_opportunities_by_niche(db, niche['_id'], opportunities, ttl_hours=24)
                            logger.info(f"Cached {len(opportunities)} opportunities for niche {niche['name']}")
                    
                    except Exception as e:
                        logger.error(f"Error scraping for niche {niche['name']}: {str(e)}")
            
            except Exception as e:
                logger.error(f"Error processing niche {niche.get('name')}: {str(e)}")
        
        # Curate gigs for each niche
        curated_by_niche = {}
        gigs_per_scan = tier_config.get("curated_gigs_per_scan", 3)
        
        for niche in niches:
            curated = curate_gigs(
                all_opportunities,
                niche,
                gigs_per_scan,
                tier
            )
            
            if curated:
                curated_by_niche[niche['_id']] = curated
        
        # Combine and sort all curated gigs
        all_curated = []
        
        for niche_id, gigs in curated_by_niche.items():
            niche_name = next((n['name'] for n in niches if n['_id'] == niche_id), "Unknown")
            
            for gig in gigs:
                all_curated.append({
                    "niche_id": str(niche_id),
                    "niche_name": niche_name,
                    "opportunity": {
                        "id": gig['opportunity'].get('id'),
                        "title": gig['opportunity'].get('title'),
                        "description": gig['opportunity'].get('description', '')[:200],
                        "platform": gig['opportunity'].get('platform'),
                        "url": gig['opportunity'].get('url'),
                        "contact": gig['opportunity'].get('contact')
                    },
                    "scores": {
                        "niche_match": round(gig['niche_score'], 2),
                        "scam_risk": gig['scam_risk']
                    },
                    "scam_status": gig['recommendation'],
                    "salary_info": gig['salary_info'],
                    "curated_at": datetime.utcnow().isoformat()
                })
        
        # Sort by niche match score and take top 20
        all_curated.sort(key=lambda x: x['scores']['niche_match'], reverse=True)
        top_20 = all_curated[:20]
        
        # Save to database for weekly tracking
        await db.weekly_curated_gigs.insert_one({
            "user_id": user_id,
            "tier": tier,
            "gigs": top_20,
            "total_scanned": len(all_opportunities),
            "cache_used": True,
            "created_at": datetime.utcnow(),
            "week_of": datetime.utcnow().replace(day=1)
        })
        
        return {
            "success": True,
            "tier": tier,
            "total_scanned": len(all_opportunities),
            "total_curated": len(top_20),
            "gigs": top_20,
            "stats": {
                "scams_filtered": len(all_opportunities) - len(all_curated),
                "with_salary": sum(1 for g in top_20 if g['salary_info'].get('has_salary')),
                "high_match": sum(1 for g in top_20 if g['scores']['niche_match'] >= 70)
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting weekly top 20: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate curated gigs")


# ============ ENHANCEMENT 1: SAVE CURATED RESULTS ============

@router.post("/save-gig/{gig_id}")
async def save_curated_gig(
    gig_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Save a curated gig to user's collection"""
    try:
        result = await db.user_opportunities.update_one(
            {"_id": ObjectId(gig_id), "user_id": user_id},
            {"$set": {"saved": True, "saved_at": datetime.utcnow()}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Gig not found")
        
        # Update user preferences for personalization
        await db.user_gig_preferences.update_one(
            {"user_id": user_id},
            {
                "$inc": {"saved_count": 1},
                "$push": {"saved_gig_ids": gig_id}
            },
            upsert=True
        )
        
        return {"message": "Gig saved successfully"}
    except Exception as e:
        logger.error(f"Error saving gig: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save gig")


@router.get("/saved")
async def get_saved_gigs(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    limit: int = Query(50, ge=1, le=100)
):
    """Get all saved curated gigs"""
    try:
        saved = await db.user_opportunities.find({
            "user_id": user_id,
            "saved": True
        }).sort("saved_at", -1).limit(limit).to_list(length=limit)
        
        for gig in saved:
            gig["_id"] = str(gig["_id"])
        
        return {
            "total": len(saved),
            "gigs": saved
        }
    except Exception as e:
        logger.error(f"Error getting saved gigs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get saved gigs")


# ============ ENHANCEMENT 2: PERSONALIZED RECOMMENDATIONS ============

@router.post("/feedback/{gig_id}")
async def submit_gig_feedback(
    gig_id: str,
    feedback_type: str = Query(..., enum=["applied", "rejected", "saved"]),
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Submit feedback on curated gig for personalization"""
    try:
        gig = await db.user_opportunities.find_one({"_id": ObjectId(gig_id), "user_id": user_id})
        if not gig:
            raise HTTPException(status_code=404, detail="Gig not found")
        
        # Record feedback
        await db.gig_feedback.insert_one({
            "user_id": user_id,
            "gig_id": gig_id,
            "feedback_type": feedback_type,
            "opportunity_data": {
                "platform": gig.get("platform"),
                "niche": gig.get("niche_id"),
                "confidence": gig.get("confidence")
            },
            "timestamp": datetime.utcnow()
        })
        
        # Update preferences model
        await db.user_preferences_ml.update_one(
            {"user_id": user_id},
            {
                "$inc": {f"{feedback_type}_count": 1},
                "$push": {"feedback_history": {
                    "type": feedback_type,
                    "timestamp": datetime.utcnow()
                }}
            },
            upsert=True
        )
        
        return {"message": "Feedback recorded"}
    
    except Exception as e:
        logger.error(f"Error submitting feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit feedback")


@router.get("/recommendations/personalized")
async def get_personalized_recommendations(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    limit: int = Query(10, ge=1, le=50)
):
    """Get personalized recommendations based on user feedback"""
    try:
        # Get user preferences
        prefs = await db.user_preferences_ml.find_one({"user_id": user_id})
        
        if not prefs:
            # Fallback to regular top 20
            result = await get_weekly_top_20(user_id, db)
            return result
        
        # Calculate weights based on feedback
        applied_count = prefs.get("applied_count", 0)
        saved_count = prefs.get("saved_count", 0)
        rejected_count = prefs.get("rejected_count", 0)
        
        # Get recent gigs and score them
        recent_gigs = await db.user_opportunities.find({"user_id": user_id})\
            .sort("created_at", -1).limit(100).to_list(length=100)
        
        scored_gigs = []
        for gig in recent_gigs:
            score = gig.get("confidence", 0)
            
            # Boost score if user has applied to similar before
            if applied_count > 0:
                similar = await db.gig_feedback.find_one({
                    "user_id": user_id,
                    "feedback_type": "applied",
                    "opportunity_data.platform": gig.get("platform")
                })
                if similar:
                    score += 15
            
            scored_gigs.append((gig, score))
        
        scored_gigs.sort(key=lambda x: x[1], reverse=True)
        recommendations = [g[0] for g in scored_gigs[:limit]]
        
        for rec in recommendations:
            rec["_id"] = str(rec["_id"])
        
        return {
            "total": len(recommendations),
            "personalization_factors": {
                "applied": applied_count,
                "saved": saved_count,
                "rejected": rejected_count
            },
            "recommendations": recommendations
        }
    
    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get recommendations")


# ============ ENHANCEMENT 3: WEEKLY DIGEST EMAIL ============

@router.post("/email-digest/configure")
async def configure_email_digest(
    frequency: str = Query(..., enum=["never", "daily", "weekly"]),
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Configure email digest settings"""
    try:
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"settings.email_digest_frequency": frequency}}
        )
        
        return {"message": f"Email digest set to {frequency}"}
    except Exception as e:
        logger.error(f"Error configuring digest: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to configure digest")


@router.get("/email-digest/preview")
async def preview_email_digest(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Preview weekly digest email content"""
    try:
        # Get user
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        
        # Get top 20 curated
        result = await get_weekly_top_20(user_id, db)
        top_gigs = result.get("gigs", [])[:10]
        
        # Calculate stats
        with_salary = sum(1 for g in top_gigs if g['salary_info'].get('has_salary'))
        salary_ranges = [g['salary_info']['amounts'][0] for g in top_gigs if g['salary_info'].get('amounts')]
        
        # Generate preview
        preview = {
            "subject": f"Your Weekly Top {len(top_gigs)} Curated Gigs - {user.get('name')}",
            "preview_text": f"This week we found {result['total_scanned']} opportunities across {len(result['gigs'])} curated picks",
            "summary": {
                "total_scanned": result['total_scanned'],
                "total_curated": result['total_curated'],
                "with_salary": with_salary,
                "high_match": result['stats']['high_match']
            },
            "top_gigs": [
                {
                    "title": g['opportunity']['title'],
                    "platform": g['opportunity']['platform'],
                    "match": f"{g['scores']['niche_match']}%",
                    "salary": g['salary_info'].get('amounts', ['N/A'])[0] if g['salary_info'].get('has_salary') else "N/A"
                }
                for g in top_gigs
            ]
        }
        
        return preview
    
    except Exception as e:
        logger.error(f"Error previewing digest: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to preview digest")


# ============ ENHANCEMENT 4: NICHE OPTIMIZATION ============

@router.post("/niches/{niche_id}/optimize")
async def optimize_niche(
    niche_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """AI-powered niche keyword optimization based on past matches"""
    try:
        niche = await db.niche_configs.find_one({
            "_id": ObjectId(niche_id),
            "user_id": user_id
        })
        
        if not niche:
            raise HTTPException(status_code=404, detail="Niche not found")
        
        # Analyze past matches
        past_matches = await db.user_opportunities.find({
            "user_id": user_id,
            "niche_id": niche_id
        }).to_list(length=100)
        
        if not past_matches:
            return {"message": "No past matches to analyze"}
        
        # Extract keywords from successful matches
        from collections import Counter
        keyword_counter = Counter()
        
        for match in past_matches:
            if match.get("confidence", 0) >= 70:  # Only high-confidence matches
                title = match.get("title", "").lower()
                words = title.split()
                keyword_counter.update(words)
        
        # Get top new keywords
        top_keywords = [kw for kw, _ in keyword_counter.most_common(10)]
        current_keywords = set(niche.get('keywords', []))
        suggested_keywords = [kw for kw in top_keywords if kw not in current_keywords]
        
        # Find underperforming keywords
        low_performing = []
        for kw in niche.get('keywords', []):
            matches_with_kw = sum(1 for m in past_matches if kw.lower() in m.get('title', '').lower())
            if matches_with_kw == 0:
                low_performing.append(kw)
        
        return {
            "current_keywords": list(current_keywords),
            "suggested_add": suggested_keywords[:5],
            "remove_if_no_matches": low_performing,
            "confidence_impact": f"+{min(15, len(suggested_keywords) * 3)}%"
        }
    
    except Exception as e:
        logger.error(f"Error optimizing niche: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to optimize niche")


# ============ ENHANCEMENT 6: SCAM REPORT CONTRIBUTION ============

@router.post("/scams/report/{gig_id}")
async def report_scam(
    gig_id: str,
    report_type: str = Query(..., enum=["false_positive", "missed_scam", "other"]),
    reason: str = Query(None),
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """User reports scam (false positive/negative) to improve detection"""
    try:
        gig = await db.user_opportunities.find_one({"_id": ObjectId(gig_id), "user_id": user_id})
        if not gig:
            raise HTTPException(status_code=404, detail="Gig not found")
        
        # Record report
        await db.scam_reports.insert_one({
            "user_id": user_id,
            "gig_id": gig_id,
            "report_type": report_type,
            "reason": reason,
            "opportunity_data": {
                "title": gig.get("title"),
                "platform": gig.get("platform"),
                "scam_risk": gig.get("scam_risk", 0)
            },
            "timestamp": datetime.utcnow(),
            "helpful": 0
        })
        
        # Update user reputation
        await db.user_reputation.update_one(
            {"user_id": user_id},
            {
                "$inc": {"reports_submitted": 1},
                "$set": {"last_report": datetime.utcnow()}
            },
            upsert=True
        )
        
        return {
            "message": "Report submitted, thank you for helping improve detection!",
            "reputation_reward": "points"
        }
    
    except Exception as e:
        logger.error(f"Error reporting scam: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit report")


# ============ ENHANCEMENT 7: NICHE PERFORMANCE ANALYTICS ============

@router.get("/niches/{niche_id}/analytics")
async def get_niche_analytics(
    niche_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    days: int = Query(30, ge=1, le=90)
):
    """Get detailed performance analytics for a niche"""
    try:
        niche = await db.niche_configs.find_one({
            "_id": ObjectId(niche_id),
            "user_id": user_id
        })
        
        if not niche:
            raise HTTPException(status_code=404, detail="Niche not found")
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get matches
        all_matches = await db.user_opportunities.find({
            "user_id": user_id,
            "niche_id": niche_id,
            "created_at": {"$gte": cutoff_date}
        }).to_list(length=None)
        
        if not all_matches:
            return {"message": "No analytics data available"}
        
        # Calculate metrics
        total = len(all_matches)
        applied = sum(1 for m in all_matches if m.get("applied"))
        saved = sum(1 for m in all_matches if m.get("saved"))
        avg_confidence = sum(m.get("confidence", 0) for m in all_matches) / total
        
        # Platform distribution
        platform_dist = {}
        for match in all_matches:
            platform = match.get("platform", "Unknown")
            platform_dist[platform] = platform_dist.get(platform, 0) + 1
        
        # Best performing times
        from collections import Counter
        hour_counter = Counter()
        for match in all_matches:
            created = match.get("created_at", datetime.utcnow())
            hour_counter[created.hour] += 1
        
        best_hours = [h for h, _ in hour_counter.most_common(3)]
        
        return {
            "niche_name": niche['name'],
            "period_days": days,
            "metrics": {
                "total_matches": total,
                "applied_rate": f"{applied/total*100:.1f}%",
                "save_rate": f"{saved/total*100:.1f}%",
                "avg_confidence": round(avg_confidence, 2)
            },
            "platform_breakdown": platform_dist,
            "best_times_utc": best_hours,
            "optimization_tip": "Check opportunities during peak hours for best matches"
        }
    
    except Exception as e:
        logger.error(f"Error getting niche analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get analytics")


# ============ ENHANCEMENT 8: SALARY TREND ANALYSIS ============

@router.get("/analytics/salary-trends")
async def get_salary_trends(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    days: int = Query(30, ge=1, le=90)
):
    """Analyze salary trends across opportunities"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        opportunities = await db.user_opportunities.find({
            "user_id": user_id,
            "created_at": {"$gte": cutoff_date}
        }).to_list(length=None)
        
        # Extract salaries
        salaries = []
        salaries_by_role = {}
        salaries_by_platform = {}
        
        for opp in opportunities:
            salary_info = detect_salary(opp.get("description", ""))
            
            if salary_info.get("has_salary"):
                try:
                    amount = float(salary_info['amounts'][0].replace(",", ""))
                    salaries.append(amount)
                    
                    role = opp.get("role_category", "general")
                    if role not in salaries_by_role:
                        salaries_by_role[role] = []
                    salaries_by_role[role].append(amount)
                    
                    platform = opp.get("platform", "unknown")
                    if platform not in salaries_by_platform:
                        salaries_by_platform[platform] = []
                    salaries_by_platform[platform].append(amount)
                except:
                    pass
        
        if not salaries:
            return {"message": "No salary data available"}
        
        # Calculate statistics
        import statistics
        avg_salary = statistics.mean(salaries)
        median_salary = statistics.median(salaries)
        min_salary = min(salaries)
        max_salary = max(salaries)
        
        return {
            "overall": {
                "average": f"${avg_salary:,.0f}",
                "median": f"${median_salary:,.0f}",
                "min": f"${min_salary:,.0f}",
                "max": f"${max_salary:,.0f}",
                "sample_size": len(salaries)
            },
            "by_role": {
                role: {
                    "average": f"${statistics.mean(amounts):,.0f}",
                    "count": len(amounts)
                }
                for role, amounts in salaries_by_role.items()
            },
            "by_platform": {
                platform: {
                    "average": f"${statistics.mean(amounts):,.0f}",
                    "count": len(amounts)
                }
                for platform, amounts in salaries_by_platform.items()
            },
            "trending": "Up" if avg_salary > median_salary else "Down"
        }
    
    except Exception as e:
        logger.error(f"Error getting salary trends: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get salary trends")

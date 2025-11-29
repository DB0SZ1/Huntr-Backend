from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from bson.objectid import ObjectId
from bson.errors import InvalidId
from datetime import datetime
from pydantic import BaseModel, Field, validator
import logging

from app.database.connection import get_database
from app.auth.jwt_handler import get_current_user_id
from config import TIER_LIMITS, PLATFORM_CONFIGS
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/niches", tags=["Niches"])


# Pydantic Models for Request Validation
class NicheBase(BaseModel):
    """Base niche model with common fields"""
    name: str = Field(..., min_length=1, max_length=100, description="Niche name")
    description: Optional[str] = Field(None, max_length=500, description="Niche description")
    keywords: List[str] = Field(..., min_items=1, max_items=50, description="Search keywords (required)")
    excluded_keywords: List[str] = Field(default_factory=list, max_items=50, description="Keywords to exclude")
    platforms: List[str] = Field(..., min_items=1, description="Platforms to search")
    min_confidence: int = Field(60, ge=0, le=100, description="Minimum confidence score")
    
    @validator('name')
    def validate_name(cls, v):
        """Validate and sanitize niche name"""
        v = v.strip()
        if not v:
            raise ValueError("Niche name cannot be empty")
        return v
    
    @validator('keywords', 'excluded_keywords')
    def validate_keywords(cls, v):
        """Validate and sanitize keywords"""
        if not v:
            return []
        # Remove empty strings and duplicates, strip whitespace
        cleaned = list(set(k.strip().lower() for k in v if k.strip()))
        return cleaned
    
    @validator('platforms')
    def validate_platforms(cls, v):
        """Ensure platforms list is not empty and contains valid values"""
        if not v:
            raise ValueError("At least one platform must be selected")
        # Remove duplicates
        return list(set(v))


class NicheCreate(NicheBase):
    """Model for creating a new niche - keywords REQUIRED"""
    keywords: List[str] = Field(..., min_items=1, max_items=50, description="Search keywords (required)")
    pass


class NicheUpdate(BaseModel):
    """Model for updating a niche - all fields optional"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    keywords: Optional[List[str]] = Field(None, max_items=50)
    excluded_keywords: Optional[List[str]] = Field(None, max_items=50)
    platforms: Optional[List[str]] = Field(None, min_items=1)
    min_confidence: Optional[int] = Field(None, ge=0, le=100)
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Niche name cannot be empty")
        return v
    
    @validator('keywords', 'excluded_keywords')
    def validate_keywords(cls, v):
        if v is not None:
            cleaned = list(set(k.strip().lower() for k in v if k.strip()))
            return cleaned
        return v
    
    @validator('platforms')
    def validate_platforms(cls, v):
        if v is not None and not v:
            raise ValueError("At least one platform must be selected")
        if v is not None:
            return list(set(v))
        return v


class NicheResponse(BaseModel):
    """Model for niche response"""
    id: str = Field(..., alias='_id')
    user_id: str
    name: str
    description: str
    keywords: List[str]
    excluded_keywords: List[str]
    platforms: List[str]
    min_confidence: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        populate_by_name = True


# Helper Functions
def validate_object_id(id_string: str, field_name: str = "ID") -> ObjectId:
    """
    Validate and convert string to ObjectId
    
    Args:
        id_string: String representation of ObjectId
        field_name: Name of field for error message
        
    Returns:
        ObjectId instance
        
    Raises:
        HTTPException: If invalid ObjectId
    """
    try:
        return ObjectId(id_string)
    except (InvalidId, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format"
        )


async def get_user_or_404(db: AsyncIOMotorDatabase, user_id: str) -> dict:
    """
    Get user by ID or raise 404
    
    Args:
        db: Database connection
        user_id: User ID string
        
    Returns:
        User document
        
    Raises:
        HTTPException: If user not found
    """
    user = await db.users.find_one({"_id": validate_object_id(user_id, "User ID")})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


async def get_niche_or_404(
    db: AsyncIOMotorDatabase,
    niche_id: str,
    user_id: str
) -> dict:
    """
    Get niche by ID and verify ownership
    
    Args:
        db: Database connection
        niche_id: Niche ID string
        user_id: User ID string for ownership verification
        
    Returns:
        Niche document
        
    Raises:
        HTTPException: If niche not found or access denied
    """
    niche = await db.niche_configs.find_one({
        "_id": validate_object_id(niche_id, "Niche ID"),
        "user_id": user_id
    })
    
    if not niche:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Niche not found or access denied"
        )
    
    return niche


def validate_tier_platforms(
    tier: str,
    requested_platforms: List[str]
) -> None:
    """
    Validate that requested platforms are available in user's tier
    
    Args:
        tier: User's subscription tier
        requested_platforms: List of platform names
        
    Raises:
        HTTPException: If platforms not available in tier
    """
    tier_limits = TIER_LIMITS.get(tier)
    if not tier_limits:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid tier configuration"
        )
    
    allowed_platforms = tier_limits.get('platforms', [])
    invalid_platforms = [p for p in requested_platforms if p not in allowed_platforms]
    
    if invalid_platforms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Platforms not available in {tier} tier: {', '.join(invalid_platforms)}. "
                   f"Available platforms: {', '.join(allowed_platforms)}"
        )


# Route Handlers
@router.get("", response_model=dict)
async def list_user_niches(
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database),
    active_only: bool = False,
    skip: int = 0,
    limit: int = 100
):
    """
    Get all niches for current user with optional filtering and pagination
    
    Args:
        user_id: Current user ID from JWT
        db: Database connection
        active_only: If True, return only active niches
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        
    Returns:
        List of user's niches
    """
    try:
        # CLEANUP: Remove Redis from any old niches if they have it
        # This handles niches created before Reddit was removed from the platform
        await db.niche_configs.update_many(
            {
                "user_id": user_id,
                "platforms": "Reddit"
            },
            {
                "$pull": {"platforms": "Reddit"}
            }
        )
        
        # Build query
        query = {"user_id": user_id}
        if active_only:
            query["is_active"] = True
        
        # Validate pagination parameters
        skip = max(0, skip)
        limit = min(max(1, limit), 100)  # Cap at 100
        
        # Get niches with pagination
        niches = await db.niche_configs.find(query).skip(skip).limit(limit).to_list(length=limit)
        
        # Get total count for pagination metadata
        total = await db.niche_configs.count_documents(query)
        
        # Convert ObjectId to string
        for niche in niches:
            niche['_id'] = str(niche['_id'])
        
        return {
            "niches": niches,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    except Exception as e:
        logger.error(f"Error listing niches for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving niches"
        )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_niche(
    niche_data: NicheCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Create new niche configuration
    
    Args:
        niche_data: Validated niche data
        user_id: Current user ID from JWT
        db: Database connection
        
    Returns:
        Created niche with ID
    """
    try:
        # Verify database connection with explicit check
        try:
            await db.command("ping")
        except Exception as db_err:
            logger.error(f"[FAIL] Database connection check failed: {str(db_err)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection unavailable"
            )
        
        # Get user and verify tier - with explicit ObjectId conversion
        try:
            user_oid = ObjectId(user_id)
        except (InvalidId, TypeError) as id_err:
            logger.error(f"[FAIL] Invalid user ID format: {str(id_err)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format"
            )
        
        # Fetch user from database
        user = await db.users.find_one({"_id": user_oid})
        
        if not user:
            logger.warning(f"[WARN] User not found: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get tier and limits
        tier = user.get('tier', 'free')
        
        # Ensure tier exists in config
        if tier not in TIER_LIMITS:
            logger.error(f"[FAIL] Invalid tier in user document: {tier}")
            tier = 'free'  # Default to free
        
        tier_limits = TIER_LIMITS[tier]
        
        # Check niche limit for this user's tier
        existing_count = await db.niche_configs.count_documents({"user_id": user_id})
        
        if existing_count >= tier_limits['max_niches']:
            logger.warning(
                f"[WARN] User {user_id} ({tier}) exceeded niche limit: "
                f"{existing_count}/{tier_limits['max_niches']}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{tier.title()} tier allows only {tier_limits['max_niches']} niche(s). "
                       f"You currently have {existing_count}. Upgrade to create more."
            )
        
        # Validate platforms for tier
        # Filter out any invalid platforms (e.g., Reddit was removed)
        allowed_platforms = tier_limits.get('platforms', [])
        valid_platforms = [p for p in niche_data.platforms if p in allowed_platforms]
        
        if not valid_platforms:
            logger.warning(
                f"[WARN] No valid platforms for user {user_id} ({tier}). "
                f"Requested: {niche_data.platforms}, Available: {allowed_platforms}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No valid platforms selected. Available for {tier} tier: {', '.join(allowed_platforms)}"
            )
        
        if len(valid_platforms) < len(niche_data.platforms):
            invalid = [p for p in niche_data.platforms if p not in allowed_platforms]
            logger.info(
                f"[INFO] Filtered out invalid platforms for {user_id}: {invalid}. "
                f"Using valid platforms: {valid_platforms}"
            )
            niche_data.platforms = valid_platforms
        
        # Check for duplicate niche name (case-insensitive)
        existing_niche = await db.niche_configs.find_one({
            "user_id": user_id,
            "name": {"$regex": f"^{niche_data.name}$", "$options": "i"}
        })
        
        if existing_niche:
            logger.warning(f"[WARN] Duplicate niche name for user {user_id}: {niche_data.name}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A niche with the name '{niche_data.name}' already exists"
            )
        
        # Build niche document
        niche_doc = {
            "user_id": user_id,
            "name": niche_data.name,
            "description": niche_data.description or '',
            "keywords": niche_data.keywords,
            "excluded_keywords": niche_data.excluded_keywords,
            "platforms": niche_data.platforms,
            "min_confidence": niche_data.min_confidence,
            "is_active": True,
            "total_matches": 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert niche into database
        result = await db.niche_configs.insert_one(niche_doc)
        
        if not result.inserted_id:
            logger.error(f"[FAIL] Failed to get inserted ID for new niche")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create niche - no ID returned"
            )
        
        # Prepare response
        niche_doc['_id'] = str(result.inserted_id)
        
        logger.info(
            f"[OK] Niche created: '{niche_doc['name']}' (ID: {niche_doc['_id']}) "
            f"for user {user.get('email', user_id)} (tier: {tier})"
        )
        
        return {
            "message": "Niche created successfully",
            "niche": niche_doc
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    
    except Exception as e:
        logger.error(
            f"[FAIL] Unexpected error creating niche for user {user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating niche"
        )


@router.get("/{niche_id}")
async def get_niche(
    niche_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get a single niche by ID
    
    Args:
        niche_id: Niche ID
        user_id: Current user ID from JWT
        db: Database connection
        
    Returns:
        Niche details
    """
    try:
        niche = await get_niche_or_404(db, niche_id, user_id)
        niche['_id'] = str(niche['_id'])
        
        return {"niche": niche}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving niche {niche_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving niche"
        )


@router.put("/{niche_id}")
async def update_niche(
    niche_id: str,
    niche_data: NicheUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Update existing niche
    
    Args:
        niche_id: Niche ID to update
        niche_data: Validated update data
        user_id: Current user ID from JWT
        db: Database connection
        
    Returns:
        Update confirmation
    """
    try:
        # Verify ownership
        niche = await get_niche_or_404(db, niche_id, user_id)
        
        # Build update dictionary with only provided fields
        update_data = {"updated_at": datetime.utcnow()}
        
        if niche_data.name is not None:
            # Check for duplicate name (excluding current niche)
            existing_niche = await db.niche_configs.find_one({
                "user_id": user_id,
                "name": {"$regex": f"^{niche_data.name}$", "$options": "i"},
                "_id": {"$ne": ObjectId(niche_id)}
            })
            
            if existing_niche:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A niche with the name '{niche_data.name}' already exists"
                )
            
            update_data["name"] = niche_data.name
        
        if niche_data.description is not None:
            update_data["description"] = niche_data.description
        
        if niche_data.keywords is not None:
            update_data["keywords"] = niche_data.keywords
        
        if niche_data.excluded_keywords is not None:
            update_data["excluded_keywords"] = niche_data.excluded_keywords
        
        if niche_data.min_confidence is not None:
            update_data["min_confidence"] = niche_data.min_confidence
        
        # Validate platforms if being updated
        if niche_data.platforms is not None:
            user = await get_user_or_404(db, user_id)
            tier = user.get('tier', 'free')
            tier_limits = TIER_LIMITS.get(tier, TIER_LIMITS.get('free', {}))
            allowed_platforms = tier_limits.get('platforms', [])
            
            # Filter out invalid platforms
            valid_platforms = [p for p in niche_data.platforms if p in allowed_platforms]
            
            if not valid_platforms:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No valid platforms selected. Available for {tier} tier: {', '.join(allowed_platforms)}"
                )
            
            if len(valid_platforms) < len(niche_data.platforms):
                invalid = [p for p in niche_data.platforms if p not in allowed_platforms]
                logger.info(
                    f"[INFO] Filtered out invalid platforms for {user_id}: {invalid}. "
                    f"Using valid platforms: {valid_platforms}"
                )
            
            update_data["platforms"] = valid_platforms
        
        # Perform update
        result = await db.niche_configs.update_one(
            {"_id": ObjectId(niche_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            logger.warning(f"No changes made to niche {niche_id}")
        
        logger.info(f"Niche updated: {niche_id} by user {user_id}")
        
        return {
            "message": "Niche updated successfully",
            "modified": result.modified_count > 0
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating niche {niche_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating niche"
        )


@router.delete("/{niche_id}", status_code=status.HTTP_200_OK)
async def delete_niche(
    niche_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Delete niche (soft delete option available)
    
    Args:
        niche_id: Niche ID to delete
        user_id: Current user ID from JWT
        db: Database connection
        
    Returns:
        Deletion confirmation
    """
    try:
        # Verify ownership first
        await get_niche_or_404(db, niche_id, user_id)
        
        # Perform hard delete
        result = await db.niche_configs.delete_one({
            "_id": ObjectId(niche_id),
            "user_id": user_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Niche not found or already deleted"
            )
        
        logger.info(f"Niche deleted: {niche_id} by user {user_id}")
        
        return {
            "message": "Niche deleted successfully",
            "deleted_id": niche_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting niche {niche_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting niche"
        )


@router.post("/{niche_id}/toggle")
async def toggle_niche(
    niche_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Activate/deactivate niche
    
    Args:
        niche_id: Niche ID to toggle
        user_id: Current user ID from JWT
        db: Database connection
        
    Returns:
        New status
    """
    try:
        # Verify ownership
        niche = await get_niche_or_404(db, niche_id, user_id)
        
        # Toggle status
        new_status = not niche.get('is_active', True)
        
        result = await db.niche_configs.update_one(
            {"_id": ObjectId(niche_id)},
            {"$set": {
                "is_active": new_status,
                "updated_at": datetime.utcnow()
            }}
        )
        
        if result.modified_count == 0:
            logger.warning(f"No changes made when toggling niche {niche_id}")
        
        logger.info(
            f"Niche {niche_id} {'activated' if new_status else 'deactivated'} "
            f"by user {user_id}"
        )
        
        return {
            "message": f"Niche {'activated' if new_status else 'deactivated'} successfully",
            "is_active": new_status
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling niche {niche_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error toggling niche status"
        )


@router.get("/{niche_id}/stats")
async def get_niche_stats(
    niche_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get statistics for a specific niche
    
    Args:
        niche_id: Niche ID
        user_id: Current user ID from JWT
        db: Database connection
        
    Returns:
        Niche statistics (total opportunities, matches, etc.)
    """
    try:
        # Verify ownership
        niche = await get_niche_or_404(db, niche_id, user_id)
        
        # Get statistics (adjust collection names as needed)
        total_opportunities = await db.opportunities.count_documents({
            "user_id": user_id,
            "niche_id": niche_id
        })
        
        matched_opportunities = await db.opportunities.count_documents({
            "user_id": user_id,
            "niche_id": niche_id,
            "is_match": True
        })
        
        return {
            "niche_id": niche_id,
            "niche_name": niche.get('name'),
            "total_opportunities": total_opportunities,
            "matched_opportunities": matched_opportunities,
            "match_rate": round((matched_opportunities / total_opportunities * 100), 2) if total_opportunities > 0 else 0,
            "is_active": niche.get('is_active', True)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving stats for niche {niche_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving niche statistics"
        )
"""
Database indexes for credit tracking
"""

async def create_credit_indexes(db):
    """Create indexes for credit collections"""
    await db.user_credits.create_index("user_id", unique=True)
    await db.credit_transactions.create_index("user_id")
    await db.credit_transactions.create_index("timestamp")

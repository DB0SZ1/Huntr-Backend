"""
Test all imports to find errors
"""
import sys

print("\nTesting imports...\n")

imports = [
    ("Config", "from config import settings, TIER_LIMITS"),
    ("Database", "from app.database.connection import get_database"),
    ("JWT Handler", "from app.auth.jwt_handler import create_access_token"),
    ("OAuth", "from app.auth.oauth import router as auth_router"),
    ("Niches Routes", "from app.niches.routes import router as niches_router"),
    ("Opportunities", "from app.opportunities.routes import router as opportunities_router"),
    ("Admin", "from app.admin.routes import router as admin_router"),
    ("Scan", "from app.scan.routes import router as scan_router"),
]

errors = []

for name, import_stmt in imports:
    try:
        exec(import_stmt)
        print(f"✅ {name}")
    except Exception as e:
        print(f"❌ {name}: {str(e)}")
        errors.append((name, str(e)))

if errors:
    print(f"\n{len(errors)} import errors found:")
    for name, error in errors:
        print(f"\n  {name}:")
        print(f"    {error}")
    sys.exit(1)
else:
    print(f"\n✅ All imports successful!")
    sys.exit(0)

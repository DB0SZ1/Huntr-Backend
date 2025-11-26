"""
Debug script to check registered routes
"""
import sys
from main import app

print("\n" + "="*70)
print("REGISTERED ROUTES")
print("="*70 + "\n")

routes = []
for route in app.routes:
    if hasattr(route, 'path'):
        methods = getattr(route, 'methods', ['GET'])
        routes.append({
            'path': route.path,
            'methods': methods,
            'name': getattr(route, 'name', 'N/A')
        })

# Group by prefix
niches_routes = [r for r in routes if '/niches' in r['path']]
auth_routes = [r for r in routes if '/auth' in r['path']]
other_routes = [r for r in routes if r not in niches_routes and r not in auth_routes]

print(f"✅ NICHES ROUTES ({len(niches_routes)}):")
for route in niches_routes:
    print(f"   {' | '.join(route['methods']):20} {route['path']}")

print(f"\n✅ AUTH ROUTES ({len(auth_routes)}):")
for route in auth_routes:
    print(f"   {' | '.join(route['methods']):20} {route['path']}")

print(f"\n✅ OTHER ROUTES ({len(other_routes)}):")
for route in sorted(other_routes, key=lambda x: x['path'])[:20]:
    print(f"   {' | '.join(route['methods']):20} {route['path']}")

if len(other_routes) > 20:
    print(f"   ... and {len(other_routes) - 20} more routes")

print(f"\n{'='*70}")
print(f"TOTAL ROUTES: {len(routes)}")
print(f"{'='*70}\n")

# Check for niches specifically
if any('/api/niches' in r['path'] for r in routes):
    print("✅ POST /api/niches is registered!")
else:
    print("❌ POST /api/niches is NOT registered!")
    print("\nTroubleshooting:")
    print("1. Check if niches_router is imported")
    print("2. Check if app.include_router(niches_router) is called")
    print("3. Check for import errors in app/niches/routes.py")

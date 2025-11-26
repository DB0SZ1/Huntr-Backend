"""
Test Suite Using Real User Data
Tests all endpoints with actual authenticated user
"""
import asyncio
import httpx
from datetime import datetime
from bson import ObjectId

BASE_URL = "http://localhost:8000"

# Real user data from your database
REAL_USER = {
    "id": "691f849ca723e68e55dbfed0",
    "google_id": "107413909121602718483",
    "email": "dbsc2008@gmail.com",
    "name": "D Boss",
    "tier": "pro"
}


async def test_real_user():
    """Test suite with real authenticated user"""
    
    print("\n" + "="*70)
    print(" REAL USER TEST SUITE")
    print("="*70)
    print(f"\nUser: {REAL_USER['name']} ({REAL_USER['email']})")
    print(f"ID: {REAL_USER['id']}")
    print(f"Tier: {REAL_USER['tier']}")
    print(f"Time: {datetime.utcnow().isoformat()}\n")
    
    try:
        # Generate JWT token for real user
        from app.auth.jwt_handler import create_access_token
        
        token = create_access_token(REAL_USER['id'])
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        print(f"Token: {token[:50]}...\n")
        
        async with httpx.AsyncClient(timeout=30) as client:
            
            # TEST 1: Get current user
            print("="*70)
            print("TEST 1: Get Current User")
            print("="*70)
            
            response = await client.get(f"{BASE_URL}/api/auth/me", headers=headers)
            print(f"Status: {response.status_code}\n")
            
            if response.status_code == 200:
                user = response.json()
                print("✅ User profile retrieved:")
                print(f"  Email: {user.get('email')}")
                print(f"  Name: {user.get('name')}")
                print(f"  Tier: {user.get('tier')}")
                print(f"  Created: {user.get('created_at')}")
                print(f"  Active niches: {user.get('active_niches', 0)}")
                print(f"  Opportunities sent: {user.get('usage', {}).get('opportunities_sent', 0)}")
                print(f"  Scans: {user.get('usage', {}).get('scans_completed', 0)}")
            else:
                print(f"❌ Error: {response.json()}")
            
            # TEST 2: Get subscription
            print("\n" + "="*70)
            print("TEST 2: Get Current Subscription")
            print("="*70)
            
            response = await client.get(f"{BASE_URL}/api/payments/subscription/current", 
                                       headers=headers)
            print(f"Status: {response.status_code}\n")
            
            if response.status_code == 200:
                sub = response.json()
                print("✅ Subscription details:")
                print(f"  Tier: {sub.get('tier')}")
                print(f"  Status: {sub.get('status')}")
                print(f"  Auto-renew: {sub.get('auto_renew', 'N/A')}")
                print(f"  Period end: {sub.get('current_period_end', 'N/A')}")
                print(f"  Max niches: {sub.get('limits', {}).get('max_niches')}")
                print(f"  Daily credits: {sub.get('limits', {}).get('daily_credits')}")
            else:
                print(f"❌ Error: {response.json()}")
            
            # TEST 3: Get niches
            print("\n" + "="*70)
            print("TEST 3: Get User's Niches")
            print("="*70)
            
            response = await client.get(f"{BASE_URL}/api/niches", headers=headers)
            print(f"Status: {response.status_code}\n")
            
            if response.status_code == 200:
                data = response.json()
                niches = data.get('niches', [])
                print(f"✅ Found {len(niches)} niches:")
                
                for niche in niches[:5]:  # Show first 5
                    print(f"\n  Niche: {niche.get('name')}")
                    print(f"    ID: {niche.get('_id')}")
                    print(f"    Active: {niche.get('is_active')}")
                    print(f"    Keywords: {', '.join(niche.get('keywords', [])[:3])}")
                    print(f"    Platforms: {', '.join(niche.get('platforms', []))}")
                    print(f"    Min confidence: {niche.get('min_confidence')}%")
                
                if len(niches) > 5:
                    print(f"\n  ... and {len(niches) - 5} more niches")
            else:
                print(f"❌ Error: {response.json()}")
            
            # TEST 4: Get opportunities
            print("\n" + "="*70)
            print("TEST 4: Get Opportunities")
            print("="*70)
            
            response = await client.get(f"{BASE_URL}/api/opportunities?page=1&per_page=5", 
                                       headers=headers)
            print(f"Status: {response.status_code}\n")
            
            if response.status_code == 200:
                data = response.json()
                opps = data.get('opportunities', [])
                print(f"✅ Found {len(opps)} opportunities on page 1:")
                
                for opp in opps[:3]:  # Show first 3
                    print(f"\n  {opp.get('title')}")
                    print(f"    Platform: {opp.get('platform')}")
                    print(f"    Company: {opp.get('company', 'N/A')}")
                    print(f"    Confidence: {opp.get('match_confidence', 'N/A')}%")
                    print(f"    Saved: {opp.get('saved', False)}")
                    print(f"    Applied: {opp.get('applied', False)}")
                
                if len(opps) > 3:
                    print(f"\n  ... and {len(opps) - 3} more")
                
                # Get pagination info
                pagination = data.get('pagination', {})
                print(f"\n  Total: {pagination.get('total')} opportunities")
                print(f"  Pages: {pagination.get('pages')}")
            else:
                print(f"❌ Error: {response.json()}")
            
            # TEST 5: Get opportunities stats
            print("\n" + "="*70)
            print("TEST 5: Opportunities Statistics")
            print("="*70)
            
            response = await client.get(f"{BASE_URL}/api/opportunities/stats/summary", 
                                       headers=headers)
            print(f"Status: {response.status_code}\n")
            
            if response.status_code == 200:
                stats = response.json()
                print("✅ Opportunity statistics:")
                print(f"  Total: {stats.get('total_opportunities')}")
                print(f"  Saved: {stats.get('saved_opportunities')}")
                print(f"  Applied: {stats.get('applied_opportunities')}")
                print(f"  By platform:")
                for platform, count in stats.get('by_platform', {}).items():
                    print(f"    - {platform}: {count}")
            else:
                print(f"❌ Error: {response.json()}")
            
            # TEST 6: Get credits balance
            print("\n" + "="*70)
            print("TEST 6: Credits Balance")
            print("="*70)
            
            response = await client.get(f"{BASE_URL}/api/credits/balance", headers=headers)
            print(f"Status: {response.status_code}\n")
            
            if response.status_code == 200:
                data = response.json()
                credits = data.get('data', {})
                print("✅ Credit balance:")
                print(f"  Available: {credits.get('daily_credits_remaining')}/{credits.get('daily_credits_total')}")
                print(f"  Used today: {credits.get('daily_credits_used')}")
                print(f"  Tier: {credits.get('tier')}")
                print(f"  Last refill: {credits.get('last_refill_date')}")
                print(f"  Next refill: {credits.get('next_refill_time')}")
            else:
                print(f"❌ Error: {response.json()}")
            
            # TEST 7: Get dashboard stats
            print("\n" + "="*70)
            print("TEST 7: Dashboard Statistics")
            print("="*70)
            
            response = await client.get(f"{BASE_URL}/api/dashboard/stats", headers=headers)
            print(f"Status: {response.status_code}\n")
            
            if response.status_code == 200:
                stats = response.json()
                print("✅ Dashboard stats:")
                print(f"  Total opportunities: {stats.get('total_opportunities')}")
                print(f"  This week: {stats.get('opportunities_this_week')}")
                print(f"  This month: {stats.get('opportunities_this_month')}")
                print(f"  Applications sent: {stats.get('applications_sent')}")
                print(f"  This month: {stats.get('applications_this_month')}")
                print(f"  Match rate: {stats.get('match_rate')}%")
            else:
                print(f"❌ Error: {response.json()}")
            
            # TEST 8: Get recent activity
            print("\n" + "="*70)
            print("TEST 8: Recent Activity")
            print("="*70)
            
            response = await client.get(f"{BASE_URL}/api/dashboard/activity?limit=5", 
                                       headers=headers)
            print(f"Status: {response.status_code}\n")
            
            if response.status_code == 200:
                data = response.json()
                activities = data.get('data', {}).get('activities', [])
                print(f"✅ Recent activity ({len(activities)} items):")
                
                for activity in activities[:5]:
                    print(f"\n  {activity.get('type')}")
                    print(f"    Time: {activity.get('timestamp')}")
                    if 'title' in activity:
                        print(f"    Title: {activity.get('title')}")
                    if 'platform' in activity:
                        print(f"    Platform: {activity.get('platform')}")
            else:
                print(f"❌ Error: {response.json()}")
            
            # TEST 9: Check credits for scan
            print("\n" + "="*70)
            print("TEST 9: Check Credits for Scan")
            print("="*70)
            
            response = await client.get(f"{BASE_URL}/api/credits/check/scan", 
                                       headers=headers)
            print(f"Status: {response.status_code}\n")
            
            if response.status_code == 200:
                data = response.json()
                check = data.get('data', {})
                print("✅ Scan credit check:")
                print(f"  Can scan: {check.get('has_enough_credits')}")
                print(f"  Current balance: {check.get('current_balance')}")
                print(f"  Required: {check.get('required_credits')}")
                print(f"  Message: {check.get('message')}")
            else:
                print(f"❌ Error: {response.json()}")
            
            # TEST 10: Get tier limits
            print("\n" + "="*70)
            print("TEST 10: Tier Limits & Features")
            print("="*70)
            
            response = await client.get(f"{BASE_URL}/api/credits/tier-limits", 
                                       headers=headers)
            print(f"Status: {response.status_code}\n")
            
            if response.status_code == 200:
                data = response.json()
                limits = data.get('data', {})
                
                print("✅ Tier limits comparison:")
                for tier, limit_info in limits.items():
                    is_current = "📌" if tier == REAL_USER['tier'] else "  "
                    print(f"\n{is_current} {tier.upper()}")
                    print(f"    Daily credits: {limit_info.get('daily_credits')}")
                    print(f"    Max niches: {limit_info.get('max_niches')}")
                    print(f"    Auto scan interval: {limit_info.get('scan_interval_minutes')} minutes")
                    print(f"    Features:")
                    for feature in limit_info.get('features', [])[:3]:
                        print(f"      • {feature}")
            else:
                print(f"❌ Error: {response.json()}")
    
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_real_user())

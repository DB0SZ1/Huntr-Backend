import requests
import os
from datetime import datetime, timedelta
import hashlib
import time
import re
import logging
import asyncio
from modules.utils import retry_on_failure, normalize_opportunity
from modules.analyzer import analyze_job_opportunity

# ============= LOGGING SETUP =============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============= TWITTER/X SCRAPING =============

@retry_on_failure(max_retries=2, delay=3)
def scrape_twitter_comprehensive():
    """Comprehensive Twitter/X scraping with better rate limit handling"""
    logger.info("Starting Twitter/X scraping...")
    opportunities = []
    
    bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
    if not bearer_token:
        logger.warning("Twitter API not configured - skipping")
        print("⚠️  Twitter API not configured - skipping")
        return opportunities
    
    headers = {"Authorization": f"Bearer {bearer_token}"}
    
    search_queries = [
        "hiring web3", "crypto job", "web3 developer",
        "community manager needed", "blockchain hiring",
        "launching soon crypto", "new token launch",
        "need designer", "freelance web3", "bounty program"
    ]
    
    seen_ids = set()
    logger.info(f"Twitter: Will search {len(search_queries[:5])} queries")
    
    for idx, query in enumerate(search_queries[:5], 1):
        try:
            logger.info(f"Twitter query {idx}/5: '{query}'")
            
            start_time = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%dT%H:%M:%SZ')
            
            search_url = "https://api.twitter.com/2/tweets/search/recent"
            params = {
                'query': f'{query} -is:retweet lang:en',
                'max_results': 10,
                'start_time': start_time,
                'tweet.fields': 'created_at,author_id,public_metrics',
                'expansions': 'author_id',
                'user.fields': 'username,name,public_metrics,description'
            }
            
            response = requests.get(search_url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 429:
                logger.warning("Twitter rate limited - skipping remaining queries")
                print(f"⏳ Twitter rate limited - skipping remaining queries")
                break
            
            if response.status_code == 200:
                data = response.json()
                tweet_count = len(data.get('data', []))
                logger.info(f"Twitter: Found {tweet_count} tweets for '{query}'")
                
                users = {}
                if 'includes' in data and 'users' in data['includes']:
                    users = {u['id']: u for u in data['includes']['users']}
                
                for tweet in data.get('data', []):
                    if tweet['id'] in seen_ids:
                        continue
                    seen_ids.add(tweet['id'])
                    
                    author = users.get(tweet['author_id'], {})
                    username = author.get('username', 'unknown')
                    followers = author.get('public_metrics', {}).get('followers_count', 0)
                    
                    telegram = extract_telegram(tweet['text'], author.get('description', ''))
                    
                    contact_info = f"@{username} (DM on X)"
                    if telegram:
                        contact_info = f"TG: {telegram} | X: @{username}"
                    
                    opportunities.append({
                        'id': f"twitter_{tweet['id']}",
                        'title': tweet['text'][:120],
                        'description': tweet['text'],
                        'platform': 'Twitter/X',
                        'url': f"https://twitter.com/{username}/status/{tweet['id']}",
                        'contact': contact_info,
                        'telegram': telegram,
                        'twitter': f"@{username}",
                        'website': None,
                        'timestamp': tweet.get('created_at'),
                        'metadata': {
                            'author': author.get('name', 'Unknown'),
                            'followers': followers,
                            'verified': author.get('verified', False)
                        }
                    })
                    logger.debug(f"Twitter: Added tweet from @{username}")
            
            elif response.status_code == 401:
                logger.error("Twitter authentication failed - check bearer token")
                print(f"❌ Twitter authentication failed - check bearer token")
                break
            
            elif response.status_code == 403:
                logger.error("Twitter access forbidden - token may lack permissions")
                print(f"❌ Twitter access forbidden - token may lack permissions")
                break
            
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"Twitter search '{query}' error: {str(e)}")
            print(f"❌ Twitter search '{query}' error: {str(e)}")
    
    logger.info(f"Twitter: Completed with {len(opportunities)} opportunities")
    return opportunities

# ============= REDDIT SCRAPING =============

@retry_on_failure(max_retries=3, delay=5)
# ============= ENHANCED TELEGRAM SCRAPING =============

def is_genuine_job_post(text):
    """
    Advanced filtering to identify genuine job posts with high confidence.
    Returns a score from 0-100 indicating likelihood of being a real job post.
    """
    text_lower = text.lower()
    score = 0
    
    # STRONG job indicators (high value)
    strong_indicators = [
        'we are hiring', 'we\'re hiring', 'now hiring', 'actively hiring',
        'join our team', 'join us', 'career opportunity', 'job opening',
        'apply now', 'send cv', 'send resume', 'submit application',
        'salary range', 'compensation', 'remote position', 'full-time position',
        'part-time position', 'contract role', 'freelance opportunity',
        'looking to hire', 'seeking candidates', 'recruiting for',
        'open position', 'vacancy', 'immediate hire', 'urgent hiring'
    ]
    
    for indicator in strong_indicators:
        if indicator in text_lower:
            score += 20
    
    # Job role keywords (medium value)
    role_keywords = [
        'developer', 'engineer', 'designer', 'manager', 'marketer',
        'community manager', 'social media', 'content writer', 'moderator',
        'analyst', 'consultant', 'specialist', 'coordinator', 'administrator',
        'lead', 'senior', 'junior', 'intern', 'freelancer', 'contractor'
    ]
    
    for keyword in role_keywords:
        if keyword in text_lower:
            score += 10
            break  # Only count once
    
    # Requirements/qualifications indicators
    requirement_keywords = [
        'requirements', 'qualifications', 'skills required', 'must have',
        'experience with', 'years of experience', 'preferred skills',
        'responsibilities', 'you will', 'looking for someone'
    ]
    
    for keyword in requirement_keywords:
        if keyword in text_lower:
            score += 15
            break
    
    # Application process indicators
    application_keywords = [
        'how to apply', 'apply here', 'application process', 'dm to apply',
        'email your', 'send your portfolio', 'interested candidates'
    ]
    
    for keyword in application_keywords:
        if keyword in text_lower:
            score += 15
    
    # Contact information presence (indicates serious post)
    if extract_email(text) or extract_telegram(text, ''):
        score += 10
    
    # Negative indicators (reduce score for spam/promotions)
    spam_indicators = [
        'buy now', 'click here', 'limited time', 'don\'t miss',
        'pump', 'moon', '100x', 'guaranteed profit', 'investment opportunity',
        'airdrop', 'giveaway', 'free tokens', 'join channel for'
    ]
    
    for spam in spam_indicators:
        if spam in text_lower:
            score -= 30
    
    # Minimum length requirement (genuine job posts are usually detailed)
    if len(text) < 100:
        score -= 20
    elif len(text) > 300:
        score += 10
    
    return max(0, min(100, score))  # Clamp between 0-100


def scrape_telegram_channels():
    """
    ENHANCED: Monitor 200+ Telegram job channels globally with smart filtering
    ✅ FIXED FOR RENDER: Uses pre-generated session file, no interactive login needed
    """
    logger.info("Starting ENHANCED Telegram scraping...")
    opportunities = []
    
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    phone = os.getenv('TELEGRAM_PHONE')  # Add phone to env vars
    
    if not api_id or not api_hash:
        logger.warning("Telegram API not configured - skipping")
        print("⚠️  Telegram API not configured - skipping")
        return opportunities
    
    # Check if session file exists
    session_file = 'job_bot_session.session'
    if not os.path.exists(session_file):
        logger.error(f"❌ Session file '{session_file}' not found. Run generate_session.py locally first!")
        print(f"❌ Session file missing. Please run 'python generate_session.py' locally, then upload the .session file to Render.")
        return opportunities
    
    try:
        # ✅ FIX: Create event loop for thread context
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # No event loop in thread - create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Import telethon components
        from telethon.sync import TelegramClient
        from telethon.tl.functions.messages import GetHistoryRequest
        from telethon.errors import ChannelPrivateError, UsernameNotOccupiedError, FloodWaitError
        
        # CLEANED CHANNEL LIST - REMOVED DORMANT/INACTIVE CHANNELS
        channels = {
            # === USER'S REQUESTED CHANNEL (HIGH PRIORITY) ===
            'user_requested': [
                '@web3_jobs_crypto_vazima'  # User's specific channel
            ],
            
            # === CRYPTO & WEB3 JOBS - VERIFIED ACTIVE ===
            'crypto_web3': [
                '@cryptojobslist', '@web3jobs', '@defi_jobs',
                '@solanajobs', '@crypto_careers',
                '@cryptocurrencyjobs',
                '@cryptojobsdaily', '@blockchaincareer',
                '@web3hiring', '@cryptohiring', '@nftcareers', '@metaversejobs',
                '@web3remote', '@decentralizedjobs', '@smartcontractjobs',
                '@rustblockchain',
                '@avalanchejobs', '@polygondevs'
            ],
            
            # === TECH & SOFTWARE DEVELOPMENT - VERIFIED ACTIVE ===
            'tech_dev': [
                '@devjobs', '@pythonjobs', '@javascriptjobs',
                '@fullstackjobs',
                '@mobilejobs', '@iosjobs',
                '@angularjobs',
                '@swiftjobs',
                '@djangojobs', '@laravel_jobs',
                '@cppjobs'
            ],
            
            # === DESIGN & CREATIVE - VERIFIED ACTIVE ===
            'design_creative': [
                '@designjobs'
            ],
            
            # === MARKETING & GROWTH - VERIFIED ACTIVE ===
            'marketing_growth': [
                '@contentwriterjobs',
                '@seojobs'
            ],
            
            # === COMMUNITY & SOCIAL MEDIA - VERIFIED ACTIVE ===
            'community_social': [
                '@moderatorjobs'
            ],
            
            # === DATA & AI - VERIFIED ACTIVE ===
            'data_ai': [
                '@datajobs', '@datasciencejobs',
                '@dataanalystjobs',
                '@machinelearningjobs'
            ],
            
            # === PRODUCT & MANAGEMENT (EXPANDED) ===
            'product_mgmt': [
                '@tpmjobs', '@programmanagement', '@productops',
                '@productleadership'
            ],
            
            # === SALES & BUSINESS DEV - VERIFIED ACTIVE ===
            'sales_business': [
                '@salesjobs', '@b2bjobs',
                '@techsalesjobs'
            ],
            
            # === BLOCKCHAIN ECOSYSTEMS - VERIFIED ACTIVE ===
            'blockchain_ecosystems': [
            ],
            
            # === DEFI & DAPPS - VERIFIED ACTIVE ===
            'defi_dapps': [
            ],
            
            # === NFT & GAMING - VERIFIED ACTIVE ===
            'nft_gaming': [
            ],
            
            # === REGIONAL - NORTH AMERICA - VERIFIED ACTIVE ===
            'regional_north_america': [
            ],
            
            # === REGIONAL - EUROPE - VERIFIED ACTIVE ===
            'regional_europe': [
            ],
            
            # === REGIONAL - ASIA PACIFIC - VERIFIED ACTIVE ===
            'regional_asia_pacific': [
                '@jobssingapore'
            ],
            
            # === REGIONAL - LATIN AMERICA - VERIFIED ACTIVE ===
            'regional_latam': [
            ],
            
            # === REGIONAL - AFRICA & MIDDLE EAST ===
            'regional_africa_mena': [
                '@lagostechjobs'
            ],
            
            # === CYBERSECURITY (NEW CATEGORY) ===
            'cybersecurity': [
                '@cybersecurityjobs'
            ],
            
            # === CLOUD & DEVOPS - VERIFIED ACTIVE ===
            'cloud_devops': [
            ],
            
            # === QA & TESTING - VERIFIED ACTIVE ===
            'qa_testing': [
            ],
            
            # === FINTECH - VERIFIED ACTIVE ===
            'fintech': [
            ],
            
            # === HEALTHTECH & BIOTECH - VERIFIED ACTIVE ===
            'healthtech': [
            ],
            
            # === EDTECH - VERIFIED ACTIVE ===
            'edtech': [
            ],
            
            # === STARTUPS & VENTURE - VERIFIED ACTIVE ===
            'startup_venture': [
            ],
            
            # === NO-CODE & LOW-CODE - VERIFIED ACTIVE ===
            'nocode_lowcode': [
            ],
            
            # === WRITING & CONTENT - VERIFIED ACTIVE ===
            'writing_content': [
            ],
            
            # === BLOCKCHAIN SECURITY - VERIFIED ACTIVE ===
            'blockchain_security': [
            ],
            
            # === INTERNATIONAL GENERAL - VERIFIED ACTIVE ===
            'international_general': [
            ]
        }
        
        # Flatten all channels with category tracking
        all_channels = []
        for category, channel_list in channels.items():
            for channel in channel_list:
                all_channels.append({
                    'channel': channel, 
                    'category': category,
                    'priority': 1 if category == 'user_requested' else 0
                })
        
        # Sort by priority (user requested channels first)
        all_channels.sort(key=lambda x: x['priority'], reverse=True)
        
        logger.info(f"Telegram: Monitoring {len(all_channels)} channels across {len(channels)} categories")
        print(f"📱 Telegram: Scanning {len(all_channels)} PREMIUM job channels globally...")
        print(f"   Including user-requested: @web3_jobs_crypto_vazima")
        
        with TelegramClient('job_bot_session', int(api_id), api_hash) as client:
            successful = 0
            failed = 0
            total_jobs_found = 0
            high_quality_jobs = 0
            
            for idx, channel_data in enumerate(all_channels, 1):
                channel = channel_data['channel']
                category = channel_data['category']
                
                try:
                    logger.info(f"Telegram [{idx}/{len(all_channels)}]: Checking {channel} ({category})")
                    
                    entity = client.get_entity(channel)
                    
                    # Fetch last 20 messages for better coverage
                    messages = client(GetHistoryRequest(
                        peer=entity,
                        limit=20,
                        offset_date=None,
                        offset_id=0,
                        max_id=0,
                        min_id=0,
                        add_offset=0,
                        hash=0
                    ))
                    
                    msg_count = 0
                    for msg in messages.messages:
                        if msg.message:
                            text = msg.message
                            
                            # Use enhanced filtering with confidence score
                            job_score = is_genuine_job_post(text)
                            
                            # Only include posts with score >= 40 (medium-high confidence)
                            if job_score >= 40:
                                msg_count += 1
                                total_jobs_found += 1
                                
                                if job_score >= 70:
                                    high_quality_jobs += 1
                                
                                telegram_handle = extract_telegram(text, '')
                                email = extract_email(text)
                                
                                contact_parts = [f"Check {channel}"]
                                if telegram_handle:
                                    contact_parts.insert(0, f"TG: {telegram_handle}")
                                if email:
                                    contact_parts.insert(0 if not telegram_handle else 1, f"Email: {email}")
                                
                                opportunities.append({
                                    'id': f"tg_{msg.id}_{channel.replace('@', '')}",
                                    'title': text[:120],
                                    'description': text,
                                    'platform': f'Telegram {channel}',
                                    'url': f"https://t.me/{channel.replace('@', '')}/{msg.id}",
                                    'contact': " | ".join(contact_parts),
                                    'telegram': telegram_handle or channel,
                                    'twitter': None,
                                    'website': None,
                                    'timestamp': msg.date.isoformat(),
                                    'metadata': {
                                        'channel': channel,
                                        'category': category,
                                        'views': getattr(msg, 'views', 0),
                                        'confidence_score': job_score,
                                        'is_high_quality': job_score >= 70
                                    }
                                })
                    
                    if msg_count > 0:
                        logger.info(f"Telegram {channel}: Found {msg_count} quality job posts")
                    successful += 1
                    
                    # Adaptive rate limiting based on progress
                    if idx < 50:
                        time.sleep(1.5)
                    else:
                        time.sleep(2.5)
                    
                except FloodWaitError as e:
                    wait_time = e.seconds
                    logger.warning(f"Telegram rate limit hit, waiting {wait_time}s...")
                    print(f"⏳ Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time + 5)
                    failed += 1
                    
                except (ChannelPrivateError, UsernameNotOccupiedError):
                    logger.warning(f"Telegram {channel}: Channel not accessible")
                    failed += 1
                    
                except Exception as e:
                    logger.error(f"Telegram {channel} error: {str(e)}")
                    failed += 1
                
                # Progress update every 20 channels
                if idx % 20 == 0:
                    print(f"   Progress: {idx}/{len(all_channels)} channels | {total_jobs_found} jobs found ({high_quality_jobs} high-quality)...")
        
        logger.info(f"Telegram: Completed - {successful} successful, {failed} failed")
        logger.info(f"Telegram: Total: {total_jobs_found} jobs ({high_quality_jobs} high-quality) from {len(opportunities)} messages")
        print(f"\n✅ Telegram Complete: {len(opportunities)} opportunities from {successful}/{len(all_channels)} channels")
        print(f"   📊 Quality Stats: {high_quality_jobs} high-confidence job posts")
        
    except ImportError:
        logger.error("Telethon not installed. Run: pip install telethon")
        print("⚠️  Telethon not installed. Run: pip install telethon")
    except RuntimeError as e:
        if "no current event loop" in str(e).lower():
            logger.error(f"Telegram failed: Event loop issue - {str(e)}")
            print(f"❌ Telegram scraper failed (event loop error)")
        else:
            logger.error(f"Telegram scraping error: {str(e)}")
            print(f"❌ Telegram scraping error: {str(e)}")
    except Exception as e:
        logger.error(f"Telegram scraping error: {str(e)}")
        print(f"❌ Telegram scraping error: {str(e)}")
    
    logger.info(f"Telegram: Completed with {len(opportunities)} opportunities")
    return opportunities

def scrape_telegram_channels_async():
    """
    Wrapper for async compatibility - calls the sync Telegram scraper.
    ✅ FIXED: This function runs in asyncio.to_thread() context on Render
    - Telethon sync client works fine when executed in thread pool
    - No event loop conflicts in thread context
    - Kept for backward compatibility with async code
    """
    # Simply call the sync version - it works in thread context
    return scrape_telegram_channels()


# ============= PUMP.FUN SCRAPING =============

@retry_on_failure(max_retries=3, delay=5)
def scrape_pumpfun():
    """Scrape Pump.fun for NEW token launches"""
    logger.info("Starting Pump.fun scraping...")
    opportunities = []
    
    try:
        url = "https://frontend-api.pump.fun/coins?offset=0&limit=50&sort=created_timestamp&order=DESC"
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Pump.fun: Got {len(data)} tokens")
            
            fresh_count = 0
            for token in data[:20]:
                created = datetime.fromtimestamp(token.get('created_timestamp', 0) / 1000)
                age_hours = (datetime.now() - created).total_seconds() / 3600
                
                if age_hours < 24:
                    fresh_count += 1
                    twitter = token.get('twitter')
                    telegram = token.get('telegram')
                    website = token.get('website')
                    
                    contact_parts = []
                    if telegram:
                        contact_parts.append(f"TG: https://t.me/{telegram}")
                    if twitter:
                        contact_parts.append(f"X: {twitter}")
                    if website:
                        contact_parts.append(f"Web: {website}")
                    
                    contact = " | ".join(contact_parts) if contact_parts else "Check Pump.fun page"
                    
                    opportunity = {
                        'id': f"pumpfun_{token.get('mint', hashlib.md5(str(token).encode()).hexdigest())}",
                        'title': f"🚀 FRESH TOKEN: ${token.get('symbol', 'UNKNOWN')} - {token.get('name', 'Unknown')}",
                        'description': f"Launched {int(age_hours)}h ago on Pump.fun. {token.get('description', '')[:200]}. Market Cap: ${token.get('usd_market_cap', 0):,.0f}. NEW PROJECTS NEED: Community managers, Discord/TG mods, Social media help, Graphic designers.",
                        'platform': 'Pump.fun',
                        'url': f"https://pump.fun/{token.get('mint', '')}",
                        'contact': contact,
                        'telegram': f"https://t.me/{telegram}" if telegram else None,
                        'twitter': twitter,
                        'website': website,
                        'timestamp': created.isoformat(),
                        'metadata': {
                            'market_cap': token.get('usd_market_cap', 0),
                            'creator': token.get('creator', 'Unknown')[:8] + '...',
                            'age_hours': int(age_hours)
                        }
                    }
                    
                    # Add AI analysis for community opportunities
                    try:
                        analysis = analyze_job_opportunity(opportunity)
                        if analysis:
                            opportunity['analysis'] = {
                                'confidence': analysis.get('confidence', 0),
                                'opportunity_type': analysis.get('opportunity_type', 'new_token'),
                                'role_category': analysis.get('role_category', 'community'),
                                'pitch_angle': analysis.get('pitch_angle', f"New Pump.fun token needs community & moderation help"),
                                'reason': analysis.get('reason', 'Fresh token launch needs team support')
                            }
                    except Exception as e:
                        logger.debug(f"Pump.fun analysis error: {e}")
                        # Continue without analysis
                    
                    opportunities.append(opportunity)
                    logger.debug(f"Pump.fun: Fresh token ${token.get('symbol')} ({int(age_hours)}h old)")
            
            logger.info(f"Pump.fun: Found {fresh_count} tokens < 24h old")
        
    except Exception as e:
        logger.error(f"Pump.fun scrape error: {str(e)}")
        print(f"❌ Pump.fun scrape error: {str(e)}")
    
    logger.info(f"Pump.fun: Completed with {len(opportunities)} opportunities")
    return opportunities

# ============= COINMARKETCAP SCRAPING =============

@retry_on_failure(max_retries=3, delay=5)
def scrape_coinmarketcap_new():
    """Scrape CoinMarketCap for newly listed tokens"""
    logger.info("Starting CoinMarketCap scraping...")
    opportunities = []
    
    api_key = os.getenv('CMC_API_KEY')
    if not api_key:
        logger.warning("CoinMarketCap API not configured - skipping")
        print("⚠️  CoinMarketCap API not configured - skipping")
        return opportunities
    
    try:
        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        headers = {
            'X-CMC_PRO_API_KEY': api_key,
            'Accept': 'application/json'
        }
        params = {
            'start': '1',
            'limit': '100',
            'sort': 'date_added',
            'sort_dir': 'desc',
            'convert': 'USD'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"CMC: Got {len(data.get('data', []))} listings")
            
            recent_count = 0
            for coin in data.get('data', [])[:30]:
                date_added = datetime.strptime(coin.get('date_added', '')[:10], '%Y-%m-%d')
                age_days = (datetime.now() - date_added).days
                
                if age_days <= 7:
                    recent_count += 1
                    info_url = f"https://pro-api.coinmarketcap.com/v2/cryptocurrency/info"
                    info_params = {'id': coin['id']}
                    info_response = requests.get(info_url, headers=headers, params=info_params, timeout=10)
                    
                    urls_data = {}
                    if info_response.status_code == 200:
                        info = info_response.json().get('data', {}).get(str(coin['id']), {})
                        urls_data = info.get('urls', {})
                    
                    twitter = extract_from_list(urls_data.get('twitter', []))
                    telegram = extract_from_list(urls_data.get('chat', []))
                    website = extract_from_list(urls_data.get('website', []))
                    
                    contact_parts = []
                    if telegram:
                        contact_parts.append(f"TG: {telegram}")
                    if twitter:
                        contact_parts.append(f"X: {twitter}")
                    if website:
                        contact_parts.append(f"Web: {website}")
                    
                    contact = " | ".join(contact_parts) if contact_parts else "Check CMC listing"
                    
                    opportunity = {
                        'id': f"cmc_{coin.get('id')}",
                        'title': f"💎 NEW CMC LISTING: ${coin.get('symbol')} - {coin.get('name')}",
                        'description': f"Listed {age_days} days ago. Market Cap: ${coin.get('quote', {}).get('USD', {}).get('market_cap', 0):,.0f}. Volume 24h: ${coin.get('quote', {}).get('USD', {}).get('volume_24h', 0):,.0f}. Getting CMC listed = growing project = hiring community managers, social media, designers.",
                        'platform': 'CoinMarketCap',
                        'url': f"https://coinmarketcap.com/currencies/{coin.get('slug', '')}",
                        'contact': contact,
                        'telegram': telegram,
                        'twitter': twitter,
                        'website': website,
                        'timestamp': date_added.isoformat(),
                        'metadata': {
                            'market_cap': coin.get('quote', {}).get('USD', {}).get('market_cap', 0),
                            'rank': coin.get('cmc_rank'),
                            'age_days': age_days
                        }
                    }
                    
                    # Add AI analysis for community opportunities
                    try:
                        analysis = analyze_job_opportunity(opportunity)
                        if analysis:
                            opportunity['analysis'] = {
                                'confidence': analysis.get('confidence', 0),
                                'opportunity_type': analysis.get('opportunity_type', 'new_token'),
                                'role_category': analysis.get('role_category', 'community'),
                                'pitch_angle': analysis.get('pitch_angle', f"New CMC listing needs community support"),
                                'reason': analysis.get('reason', 'CMC listing indicates project growth and hiring')
                            }
                    except Exception as e:
                        logger.debug(f"CMC analysis error: {e}")
                        # Continue without analysis
                    
                    opportunities.append(opportunity)
                    logger.debug(f"CMC: New listing ${coin.get('symbol')} ({age_days}d old)")
                    
                    time.sleep(1)
            
            logger.info(f"CMC: Found {recent_count} listings < 7 days old")
        
    except Exception as e:
        logger.error(f"CoinMarketCap scrape error: {str(e)}")
        print(f"❌ CoinMarketCap scrape error: {str(e)}")
    
    logger.info(f"CMC: Completed with {len(opportunities)} opportunities")
    return opportunities

# ============= DEXSCREENER SCRAPING =============

@retry_on_failure(max_retries=3, delay=5)
def scrape_dexscreener_enhanced():
    """Enhanced DexScreener scraping - find trading opportunities"""
    logger.info("Starting DexScreener scraping...")
    opportunities = []
    
    try:
        chains = ['solana', 'ethereum', 'bsc']
        logger.info(f"DexScreener: Checking {len(chains)} chains")
        
        for chain in chains:
            logger.info(f"DexScreener: Searching {chain}")
            url = f"https://api.dexscreener.com/latest/dex/search?q={chain}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                pairs = data.get('pairs', [])
                logger.info(f"DexScreener {chain}: Got {len(pairs)} pairs")
                
                # Include ALL pairs, not just < 48h (better chance of finding opportunities)
                for i, pair in enumerate(pairs[:15]):
                    if not pair.get('pairAddress'):
                        continue
                    
                    created = None
                    age_hours = 0
                    
                    if pair.get('pairCreatedAt'):
                        try:
                            created = datetime.fromtimestamp(pair['pairCreatedAt'] / 1000)
                            age_hours = (datetime.now() - created).total_seconds() / 3600
                        except:
                            created = datetime.now()
                            age_hours = 0
                    else:
                        # No creation date - use current time
                        created = datetime.now()
                        age_hours = 0
                    
                    info = pair.get('info', {})
                    socials = info.get('socials', [])
                    
                    telegram = None
                    twitter = None
                    website = None
                    
                    for social in socials:
                        if social.get('type') == 'telegram':
                            telegram = social.get('url')
                        elif social.get('type') == 'twitter':
                            twitter = social.get('url')
                        elif social.get('type') == 'website':
                            website = social.get('url')
                    
                    contact_parts = []
                    if telegram:
                        contact_parts.append(f"TG: {telegram}")
                    if twitter:
                        contact_parts.append(f"X: {twitter}")
                    if website:
                        contact_parts.append(f"Web: {website}")
                    
                    contact = " | ".join(contact_parts) if contact_parts else f"Check pair"
                    
                    base_token = pair.get('baseToken', {})
                    quote_token = pair.get('quoteToken', {})
                    
                    opportunity = {
                        'id': f"dex_{pair.get('pairAddress', hashlib.md5(str(pair).encode()).hexdigest())}",
                        'title': f"Trading Opportunity: {base_token.get('symbol', 'TOKEN')}/{quote_token.get('symbol', 'USD')} on {pair.get('dexId', chain).upper()}",
                        'description': f"Age: {int(age_hours)}h. Liquidity: ${pair.get('liquidity', {}).get('usd', 0):,.0f}. Volume 24h: ${pair.get('volume', {}).get('h24', 0):,.0f}. Chain: {chain.upper()}. Trading pair information and community resources available.",
                        'platform': 'DexScreener',
                        'url': pair.get('url', f"https://dexscreener.com/{chain}/{pair.get('pairAddress', '')}"),
                        'contact': contact,
                        'telegram': telegram,
                        'twitter': twitter,
                        'website': website,
                        'timestamp': created.isoformat(),
                        'metadata': {
                            'liquidity': pair.get('liquidity', {}).get('usd', 0),
                            'volume_24h': pair.get('volume', {}).get('h24', 0),
                            'chain': pair.get('chainId', 'unknown'),
                            'age_hours': int(age_hours)
                        }
                    }
                    
                    # Add AI analysis for project/community opportunities
                    try:
                        analysis = analyze_job_opportunity(opportunity)
                        if analysis:
                            opportunity['analysis'] = {
                                'confidence': analysis.get('confidence', 0),
                                'opportunity_type': analysis.get('opportunity_type', 'new_token'),
                                'role_category': analysis.get('role_category', 'community'),
                                'pitch_angle': analysis.get('pitch_angle', f"New token launch needs community support"),
                                'reason': analysis.get('reason', 'New token with trading data')
                            }
                    except Exception as e:
                        logger.debug(f"DexScreener analysis error: {e}")
                        # Continue without analysis
                    
                    opportunities.append(opportunity)
                    logger.debug(f"DexScreener: Added pair on {chain} ({int(age_hours)}h old)")
                
                logger.info(f"DexScreener {chain}: Processed {len([p for p in pairs[:15] if p.get('pairAddress')])} pairs")
            
            time.sleep(2)
        
    except Exception as e:
        logger.error(f"DexScreener enhanced scrape error: {str(e)}")
        print(f"❌ DexScreener enhanced scrape error: {str(e)}")
    
    logger.info(f"DexScreener: Completed with {len(opportunities)} opportunities")
    return opportunities

# ============= COINGECKO SCRAPING =============

@retry_on_failure(max_retries=2, delay=5)
def scrape_coingecko_new():
    """Scrape CoinGecko for newly added tokens (inclusive - all recent coins)"""
    logger.info("Starting CoinGecko scraping...")
    opportunities = []
    
    try:
        url = "https://api.coingecko.com/api/v3/coins/list?include_platform=true"
        headers = {'Accept': 'application/json'}
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            coins = response.json()
            # Check more recent coins (last 30 instead of last 50, then first 30)
            recent_coins = coins[-30:]
            logger.info(f"CoinGecko: Checking {len(recent_coins)} recent coins")
            
            opportunity_count = 0
            for coin in recent_coins:
                try:
                    detail_url = f"https://api.coingecko.com/api/v3/coins/{coin['id']}"
                    detail_response = requests.get(detail_url, headers=headers, timeout=10)
                    
                    if detail_response.status_code == 200:
                        data = detail_response.json()
                        
                        # Try to get age if genesis date exists, otherwise include it anyway
                        age_days = None
                        genesis_date = None
                        
                        try:
                            genesis = data.get('genesis_date')
                            if genesis:
                                genesis_date = datetime.strptime(genesis, '%Y-%m-%d')
                                age_days = (datetime.now() - genesis_date).days
                        except:
                            pass
                        
                        # Include coins regardless of age (removed < 30 days filter)
                        # If we have no genesis date, use current time as timestamp
                        if genesis_date is None:
                            genesis_date = datetime.now()
                        
                        opportunity_count += 1
                        links = data.get('links', {})
                        
                        telegram = links.get('telegram_channel_identifier')
                        twitter = links.get('twitter_screen_name')
                        homepage = links.get('homepage', [''])[0]
                        
                        contact_parts = []
                        if telegram:
                            tg_link = f"https://t.me/{telegram}"
                            contact_parts.append(f"TG: {tg_link}")
                        if twitter:
                            twitter_link = f"https://twitter.com/{twitter}"
                            contact_parts.append(f"X: {twitter_link}")
                        if homepage:
                            contact_parts.append(f"Web: {homepage}")
                        
                        contact = " | ".join(contact_parts) if contact_parts else "Check CoinGecko page"
                        
                        # Build title without emoji (Windows console issue)
                        age_str = f" ({age_days}d old)" if age_days else ""
                        symbol = data.get('symbol', 'UNK').upper()
                        
                        opportunities.append({
                            'id': f"coingecko_{coin['id']}",
                            'title': f"CoinGecko Token: ${symbol} - {data.get('name')}{age_str}",
                            'description': f"Token on CoinGecko. {data.get('description', {}).get('en', '')[:200]}. Market Cap: ${data.get('market_data', {}).get('market_cap', {}).get('usd', 0):,.0f}. New listings on CoinGecko need community growth, social presence, and content creators.",
                            'platform': 'CoinGecko',
                            'url': f"https://www.coingecko.com/en/coins/{coin['id']}",
                            'contact': contact,
                            'telegram': f"https://t.me/{telegram}" if telegram else None,
                            'twitter': f"https://twitter.com/{twitter}" if twitter else None,
                            'website': homepage,
                            'timestamp': genesis_date.isoformat(),
                            'metadata': {
                                'age_days': age_days,
                                'market_cap': data.get('market_data', {}).get('market_cap', {}).get('usd', 0)
                            }
                        })
                        logger.debug(f"CoinGecko: Added coin {coin['id']}")
                    
                    time.sleep(1)  # Reduced from 2s to 1s
                    
                except Exception as e:
                    logger.debug(f"CoinGecko: Skipping {coin.get('id')} - {str(e)}")
                    continue
            
            logger.info(f"CoinGecko: Found {opportunity_count} coins")
        
    except Exception as e:
        logger.error(f"CoinGecko scrape error: {str(e)}")
        print(f"CoinGecko scrape error: {str(e)}")
    
    logger.info(f"CoinGecko: Completed with {len(opportunities)} opportunities")
    return opportunities

# ============= WEB3.CAREER SCRAPING =============

@retry_on_failure(max_retries=3, delay=5)
def scrape_web3_jobs():
    """Enhanced Web3.career scraper"""
    logger.info("Starting Web3.career scraping...")
    opportunities = []
    
    try:
        url = "https://web3.career/api/jobs"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            jobs = data.get('jobs', [])
            logger.info(f"Web3.career: Got {len(jobs)} jobs")
            
            for job in jobs[:30]:
                description = job.get('description', '')
                apply_url = job.get('apply_url', '')
                
                telegram = extract_telegram(description, '')
                email = extract_email(description)
                
                contact_parts = [f"Apply: {apply_url}"]
                if telegram:
                    contact_parts.insert(0, f"TG: {telegram}")
                if email:
                    contact_parts.insert(0 if not telegram else 1, f"Email: {email}")
                
                opportunities.append({
                    'id': f"web3career_{job.get('id')}",
                    'title': job.get('title'),
                    'description': description[:350],
                    'platform': 'Web3.career',
                    'url': f"https://web3.career/job/{job.get('id')}",
                    'contact': " | ".join(contact_parts),
                    'telegram': telegram,
                    'twitter': None,
                    'website': None,
                    'timestamp': job.get('created_at'),
                    'metadata': {
                        'company': job.get('company_name'),
                        'location': job.get('location', 'Remote'),
                        'salary': job.get('salary_range')
                    }
                })
                logger.debug(f"Web3.career: Added job '{job.get('title')[:50]}'")
            
            logger.info(f"Web3.career: Found {len(opportunities)} jobs")
    
    except Exception as e:
        logger.error(f"Web3.career scrape error: {str(e)}")
        print(f"❌ Web3.career scrape error: {str(e)}")
    
    logger.info(f"Web3.career: Completed with {len(opportunities)} opportunities")
    return opportunities

# ============= HELPER FUNCTIONS =============

def extract_telegram(text, bio=''):
    """Extract Telegram username/link from text"""
    combined = f"{text} {bio}"
    
    patterns = [
        r't\.me/([a-zA-Z0-9_]{5,32})',
        r'telegram[:\s@]+([a-zA-Z0-9_]{5,32})',
        r'@([a-zA-Z0-9_]{5,32})\s*\(telegram\)',
        r'tg[:\s@]+([a-zA-Z0-9_]{5,32})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            username = match.group(1)
            result = f"https://t.me/{username}" if not username.startswith('http') else username
            logger.debug(f"Extracted Telegram: {result}")
            return result
    
    return None

def extract_email(text):
    """Extract email from text"""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(pattern, text)
    if match:
        logger.debug(f"Extracted email: {match.group(0)}")
        return match.group(0)
    return None

def extract_urls(tweet):
    """Extract URLs from tweet entities"""
    urls = []
    entities = tweet.get('entities', {})
    for url_obj in entities.get('urls', []):
        expanded = url_obj.get('expanded_url', url_obj.get('url'))
        if expanded:
            urls.append(expanded)
    return urls

def extract_from_list(url_list):
    """Extract first URL from list"""
    return url_list[0] if url_list and len(url_list) > 0 else None

# ============= USER REPORTING SYSTEM =============

def flag_opportunity_as_suspicious(opportunity_id, user_id, reason, report_details=None):
    """
    Flag an opportunity as suspicious for review
    
    Args:
        opportunity_id: ID of the opportunity to flag
        user_id: ID of the user reporting
        reason: Reason for flagging (scam, spam, misleading, etc.)
        report_details: Optional dict with additional details
    
    Returns:
        dict with report status and ID
    """
    logger.warning(f"[REPORT] User {user_id} flagged opportunity {opportunity_id} as: {reason}")
    
    report = {
        'opportunity_id': opportunity_id,
        'reporter_user_id': user_id,
        'reason': reason,
        'details': report_details or {},
        'flagged_at': datetime.utcnow().isoformat(),
        'status': 'pending_review',
        'review_notes': None
    }
    
    # Log to file for monitoring
    logger.info(f"[REPORT] {reason}: {opportunity_id} (reported by {user_id})")
    
    return {
        'success': True,
        'report_id': f"report_{opportunity_id}_{int(datetime.utcnow().timestamp())}",
        'message': f'Opportunity reported for review. Thank you for helping keep the community safe.',
        'report': report
    }


def mark_channel_as_rogue(channel_name, reason):
    """
    Mark a Telegram channel as rogue/high-risk for internal tracking
    
    Args:
        channel_name: Name of the channel
        reason: Why it's marked as rogue
    
    Returns:
        dict with status
    """
    logger.warning(f"[ROGUE] Channel {channel_name} marked as rogue: {reason}")
    return {
        'success': True,
        'channel': channel_name,
        'marked_as_rogue': True,
        'reason': reason,
        'timestamp': datetime.utcnow().isoformat()
    }


def get_opportunity_abuse_metrics(opportunity_id):
    """
    Get abuse/report metrics for an opportunity
    
    Args:
        opportunity_id: ID of the opportunity
    
    Returns:
        dict with report counts and risk assessment
    """
    # In production, would query database for reports on this opportunity
    return {
        'opportunity_id': opportunity_id,
        'total_reports': 0,
        'scam_reports': 0,
        'spam_reports': 0,
        'misleading_reports': 0,
        'risk_level': 'low',  # low, medium, high
        'needs_review': False
    }

# ============= MAIN AGGREGATOR =============

def scrape_all_platforms():
    """Aggregate ALL platform scrapers with comprehensive logging"""
    logger.info("="*60)
    logger.info("STARTING COMPREHENSIVE WEB3 JOB SCAN")
    logger.info("="*60)
    
    all_opportunities = []
    seen_hashes = set()
    
    print("\n" + "="*60)
    print("🚀 STARTING COMPREHENSIVE WEB3 JOB SCAN")
    print("="*60 + "\n")
    
    # ALL scrapers in priority order
    scrapers = [
        ("Pump.fun", scrape_pumpfun),
        ("Web3.career", scrape_web3_jobs),
        ("Twitter/X", scrape_twitter_comprehensive),
        ("Telegram", scrape_telegram_channels),  # NOW ENABLED WITH 85+ ACTIVE CHANNELS
        ("CoinMarketCap", scrape_coinmarketcap_new),
        ("DexScreener", scrape_dexscreener_enhanced),
        ("CoinGecko", scrape_coingecko_new)
    ]
    
    start_time = time.time()
    
    for name, scraper_func in scrapers:
        platform_start = time.time()
        logger.info(f"Starting {name} scraper...")
        print(f"🔍 Scanning {name}...")
        
        try:
            opps = scraper_func()
            
            # Deduplicate
            unique_opps = []
            for opp in opps:
                content_hash = normalize_opportunity(opp)
                if content_hash not in seen_hashes:
                    unique_opps.append(opp)
                    seen_hashes.add(content_hash)
            
            all_opportunities.extend(unique_opps)
            dupes = len(opps) - len(unique_opps)
            
            platform_time = time.time() - platform_start
            logger.info(f"{name}: Found {len(opps)} total, {len(unique_opps)} unique ({dupes} duplicates) in {platform_time:.2f}s")
            
            if dupes > 0:
                print(f"   ✅ Found {len(unique_opps)} unique ({dupes} duplicates removed)")
            else:
                print(f"   ✅ Found {len(unique_opps)} opportunities")
                
        except Exception as e:
            logger.error(f"{name} scraper failed: {str(e)}", exc_info=True)
            print(f"   ❌ Error: {str(e)}")
    
    total_time = time.time() - start_time
    
    print("\n" + "="*60)
    print(f"✅ TOTAL UNIQUE OPPORTUNITIES: {len(all_opportunities)}")
    print(f"⏱️  Total scan time: {total_time:.2f}s")
    print("="*60 + "\n")
    
    logger.info("="*60)
    logger.info(f"SCAN COMPLETE: {len(all_opportunities)} unique opportunities in {total_time:.2f}s")
    logger.info("="*60)
    
    # Log platform breakdown
    platform_stats = {}
    for opp in all_opportunities:
        platform = opp.get('platform', 'Unknown')
        platform_stats[platform] = platform_stats.get(platform, 0) + 1
    
    logger.info("Platform breakdown:")
    for platform, count in sorted(platform_stats.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {platform}: {count} opportunities")
    
    return all_opportunities

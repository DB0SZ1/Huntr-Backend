/**
 * pages.js - Navigation system for Niche Finder Dashboard
 * COMPLETE REWRITE - All data from real API calls
 */

// Current page state
let currentPage = 'dashboard';
let currentOpportunityData = null;

// Page rendering functions
async function renderOpportunitiesPage() {
    const mainContent = document.querySelector('.dashboard-content');
    mainContent.innerHTML = `
        <div class="loading-container">
            <div class="spinner"></div>
            <p>Loading opportunities...</p>
        </div>
    `;
    
    try {
        const data = await API.getOpportunities(1, 20);
        
        let html = `
            <div class="page-header" style="margin-bottom: 32px;">
                <h2 class="page-title">Opportunities (${data.pagination.total})</h2>
                <div class="breadcrumb">Home / Opportunities</div>
            </div>

            <div class="opportunities-grid">
        `;
        
        if (data.opportunities.length === 0) {
            html += `
                <div class="empty-state">
                    <i class="fas fa-inbox" style="font-size: 64px; opacity: 0.3; margin-bottom: 16px;"></i>
                    <h3>No opportunities yet</h3>
                    <p>Start a scan to find opportunities matching your niches</p>
                    <button onclick="document.getElementById('startScanBtn').click()" class="btn-primary">Start Scanning</button>
                </div>
            `;
        } else {
            data.opportunities.forEach(opp => {
                const timeAgo = getTimeAgo(new Date(opp.created_at));
                const confidence = opp.match_data?.confidence || 0;
                const saved = opp.match_data?.saved || false;
                
                html += `
                    <div class="opportunity-card glass-card" onclick="openOpportunityModal('${opp._id}')">
                        <div class="opp-header">
                            <div class="opp-platform">${opp.platform}</div>
                            <div class="opp-time">${timeAgo}</div>
                        </div>
                        <h3 class="opp-title">${opp.title}</h3>
                        <div class="opp-company">${opp.contact || 'Contact available'}</div>
                        <div class="opp-details">
                            <span><i class="fas fa-chart-line"></i> ${confidence}% match</span>
                            ${saved ? '<span><i class="fas fa-bookmark"></i> Saved</span>' : ''}
                        </div>
                        <div class="opp-tags">
                            ${opp.metadata?.tags ? opp.metadata.tags.slice(0, 3).map(tag => 
                                `<span class="opp-tag">${tag}</span>`
                            ).join('') : ''}
                        </div>
                        <div class="opp-footer">
                            <button class="opp-view-btn" onclick="event.stopPropagation(); openOpportunityModal('${opp._id}')">
                                View Details <i class="fas fa-arrow-right"></i>
                            </button>
                        </div>
                    </div>
                `;
            });
        }
        
        html += '</div>';
        mainContent.innerHTML = html;
        
    } catch (error) {
        console.error('Failed to load opportunities:', error);
        mainContent.innerHTML = `
            <div class="error-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Failed to load opportunities</h3>
                <p>${error.message}</p>
                <button onclick="renderOpportunitiesPage()" class="btn-primary">Retry</button>
            </div>
        `;
    }
}

async function renderFiltersPage() {
    const mainContent = document.querySelector('.dashboard-content');
    mainContent.innerHTML = `
        <div class="loading-container">
            <div class="spinner"></div>
            <p>Loading filters...</p>
        </div>
    `;
    
    try {
        const niches = await API.getNiches();
        const user = await API.getCurrentUser();
        
        let html = `
            <div class="page-header" style="margin-bottom: 32px;">
                <h2 class="page-title">Filters & Niches</h2>
                <div class="breadcrumb">Home / Filters</div>
            </div>

            <div class="filters-container">
                <div class="glass-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
                        <h3 class="card-title">Your Niches</h3>
                        <button onclick="showCreateNicheModal()" class="btn-primary">
                            <i class="fas fa-plus"></i> Add Niche
                        </button>
                    </div>
                    <div class="niches-list">
        `;
        
        if (niches.length === 0) {
            html += `
                <div class="empty-state">
                    <p>No niches configured yet. Add your first niche to start finding opportunities.</p>
                </div>
            `;
        } else {
            niches.forEach(niche => {
                html += `
                    <div class="niche-item ${niche.is_active ? 'active' : 'inactive'}">
                        <div class="niche-info">
                            <h4>${niche.name}</h4>
                            <p>${niche.description || 'No description'}</p>
                            <div class="niche-keywords">
                                ${niche.keywords.map(kw => `<span class="keyword-tag">${kw}</span>`).join('')}
                            </div>
                            <div class="niche-stats">
                                <span><i class="fas fa-bullseye"></i> ${niche.total_matches || 0} matches</span>
                                <span><i class="fas fa-layer-group"></i> ${niche.platforms?.length || 0} platforms</span>
                            </div>
                        </div>
                        <div class="niche-actions">
                            <button onclick="toggleNiche('${niche._id}')" class="btn-icon" title="${niche.is_active ? 'Deactivate' : 'Activate'}">
                                <i class="fas fa-${niche.is_active ? 'pause' : 'play'}"></i>
                            </button>
                            <button onclick="editNiche('${niche._id}')" class="btn-icon" title="Edit">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button onclick="deleteNiche('${niche._id}')" class="btn-icon btn-danger" title="Delete">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                `;
            });
        }
        
        html += `
                    </div>
                    <div class="niche-limit-info">
                        <span>Niches used: ${niches.length} / ∞</span>
                    </div>
                </div>

                <div class="glass-card" style="margin-top: 24px;">
                    <h3 class="card-title" style="margin-bottom: 24px;">Notification Settings</h3>
                    <div class="filter-options">
                        <label class="filter-checkbox">
                            <input type="checkbox" ${user.settings?.whatsapp_notifications ? 'checked' : ''} 
                                   onchange="updateNotificationSetting('whatsapp', this.checked)">
                            <span>WhatsApp Notifications</span>
                        </label>
                        <label class="filter-checkbox">
                            <input type="checkbox" ${user.settings?.email_notifications ? 'checked' : ''} 
                                   onchange="updateNotificationSetting('email', this.checked)">
                            <span>Email Alerts</span>
                        </label>
                    </div>
                </div>
            </div>
        `;
        
        mainContent.innerHTML = html;
        
    } catch (error) {
        console.error('Failed to load filters:', error);
        mainContent.innerHTML = `
            <div class="error-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Failed to load filters</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

async function renderHistoryPage() {
    const mainContent = document.querySelector('.dashboard-content');
    mainContent.innerHTML = `
        <div class="loading-container">
            <div class="spinner"></div>
            <p>Loading opportunities...</p>
        </div>
    `;
    
    try {
        // Load all saved/applied opportunities from the API
        const allOpportunities = await API.getOpportunities(1, 100, { viewed: true });
        
        let html = `
            <div class="page-header" style="margin-bottom: 32px;">
                <h2 class="page-title">Your Opportunities</h2>
                <div class="breadcrumb">Home / Opportunities</div>
            </div>

            <div class="history-stats">
                <div class="glass-card stats-card">
                    <div class="stats-icon"><i class="fas fa-briefcase"></i></div>
                    <div class="stats-value">${allOpportunities.pagination?.total || 0}</div>
                    <div class="stats-label">Total Opportunities</div>
                    <div class="stats-description">Viewed</div>
                </div>
            </div>

            <div class="glass-card" style="margin-top: 32px;">
                <h3 class="card-title" style="margin-bottom: 24px;">Opportunities</h3>
                <div class="history-table">
        `;
        
        if (!allOpportunities.opportunities || allOpportunities.opportunities.length === 0) {
            html += `
                <div class="empty-state">
                    <p>No opportunities viewed yet. Start exploring opportunities to see them here.</p>
                </div>
            `;
        } else {
            allOpportunities.opportunities.forEach(opp => {
                const date = new Date(opp.created_at);
                const dateStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
                
                html += `
                    <div class="history-row" onclick="openOpportunityModal('${opp._id}')">
                        <div><strong>${opp.title}</strong></div>
                        <div>${opp.platform}</div>
                        <div>${dateStr}</div>
                        <div>${opp.match_data?.saved ? '<i class="fas fa-bookmark"></i> Saved' : 'Not saved'}</div>
                    </div>
                `;
            });
        }
        
        html += `
                </div>
            </div>
        `;
        
        mainContent.innerHTML = html;
        
    } catch (error) {
        console.error('Failed to load opportunities:', error);
        mainContent.innerHTML = `
            <div class="error-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Failed to load opportunities</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

async function renderSettingsPage() {
    const mainContent = document.querySelector('.dashboard-content');
    mainContent.innerHTML = `
        <div class="loading-container">
            <div class="spinner"></div>
            <p>Loading settings...</p>
        </div>
    `;
    
    try {
        const user = await API.getCurrentUser();
        
        let html = `
            <div class="page-header" style="margin-bottom: 32px;">
                <h2 class="page-title">Settings</h2>
                <div class="breadcrumb">Home / Settings</div>
            </div>

            <div class="settings-container">
                <div class="glass-card">
                    <h3 class="card-title" style="margin-bottom: 24px;">Profile Settings</h3>
                    <div class="settings-form">
                        <div class="form-group">
                            <label>Full Name</label>
                            <input type="text" class="form-input" id="settingsName" value="${user.name}">
                        </div>
                        <div class="form-group">
                            <label>Email Address</label>
                            <input type="email" class="form-input" value="${user.email}" disabled>
                            <small>Email cannot be changed (linked to Google account)</small>
                        </div>
                        <div class="form-group">
                            <label>WhatsApp Number</label>
                            <input type="tel" class="form-input" id="settingsWhatsapp" 
                                   value="${user.settings?.whatsapp_number || ''}" 
                                   placeholder="+234 XXX XXX XXXX">
                        </div>
                    </div>
                </div>

                <div class="glass-card" style="margin-top: 24px;">
                    <h3 class="card-title" style="margin-bottom: 24px;">Account & Billing</h3>
                    <div class="settings-info">
                        <div class="info-row">
                            <span>Current Plan</span>
                            <strong style="text-transform: capitalize;">${user.tier}</strong>
                        </div>
                        <div class="info-row">
                            <span>Member Since</span>
                            <strong>${new Date(user.created_at).toLocaleDateString()}</strong>
                        </div>
                        <div class="info-row">
                            <span>Subscription Status</span>
                            <strong style="text-transform: capitalize;">${user.subscription?.status || 'Free'}</strong>
                        </div>
                        ${user.tier !== 'premium' ? `
                        <button class="upgrade-settings-btn" onclick="openUpgradeModal()">
                            <i class="fas fa-crown"></i> Upgrade Plan
                        </button>
                        ` : ''}
                    </div>
                </div>

                <button class="save-settings-btn" onclick="saveSettings()">
                    <i class="fas fa-save"></i> Save Changes
                </button>
            </div>
        `;
        
        mainContent.innerHTML = html;
        
    } catch (error) {
        console.error('Failed to load settings:', error);
        mainContent.innerHTML = `
            <div class="error-state">
                <i class="fas fa-exclamation-triangle"></i>
                <h3>Failed to load settings</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

function renderDashboardPage() {
    // Return to original dashboard
    location.reload();
}

// Opportunity Modal
async function openOpportunityModal(opportunityId) {
    try {
        // FIX: Validate opportunity ID exists
        if (!opportunityId || opportunityId === 'undefined') {
            console.error('Invalid opportunity ID:', opportunityId);
            alert('Invalid opportunity ID');
            return;
        }
        
        console.log('Loading opportunity:', opportunityId);
        const data = await API.getOpportunity(opportunityId);
        const opportunity = data.opportunity;
        currentOpportunityData = opportunity;
        
        const modalHTML = `
            <div class="modal-overlay opportunity-modal active" id="opportunityModal">
                <div class="modal-content opportunity-modal-content">
                    <button class="modal-close" onclick="closeOpportunityModal()">
                        <i class="fas fa-times"></i>
                    </button>
                    
                    <div class="opp-modal-header">
                        <div class="opp-modal-platform">${opportunity.platform}</div>
                        <h2 class="opp-modal-title">${opportunity.title}</h2>
                        <div class="opp-modal-company">${opportunity.contact || 'Contact available'}</div>
                    </div>

                    <div class="opp-modal-meta">
                        <div class="opp-modal-meta-item">
                            <i class="fas fa-chart-line"></i>
                            <span>${opportunity.match_data?.confidence || 0}% match</span>
                        </div>
                        <div class="opp-modal-meta-item">
                            <i class="fas fa-clock"></i>
                            <span>${getTimeAgo(new Date(opportunity.created_at))}</span>
                        </div>
                    </div>

                    <div class="opp-modal-section">
                        <h3>Description</h3>
                        <p>${opportunity.description || 'No description provided'}</p>
                    </div>

                    ${opportunity.metadata?.requirements ? `
                    <div class="opp-modal-section">
                        <h3>Requirements</h3>
                        <ul>
                            ${opportunity.metadata.requirements.map(req => `<li>${req}</li>`).join('')}
                        </ul>
                    </div>
                    ` : ''}

                    <div class="opp-modal-actions">
                        <button class="opp-apply-btn" onclick="window.open('${opportunity.url}', '_blank')">
                            <i class="fas fa-external-link-alt"></i> View Opportunity
                        </button>
                        <button class="opp-save-btn" onclick="saveOpportunity('${opportunity._id || opportunity.id}')">
                            <i class="fas fa-bookmark"></i> ${opportunity.match_data?.saved ? 'Unsave' : 'Save'}
                        </button>
                        <button class="opp-apply-btn" onclick="markAsApplied('${opportunity._id || opportunity.id}')">
                            <i class="fas fa-check"></i> Mark as Applied
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
    } catch (error) {
        console.error('Failed to load opportunity:', error);
        alert('Failed to load opportunity: ' + error.message);
    }
}

function closeOpportunityModal() {
    const modal = document.getElementById('opportunityModal');
    if (modal) {
        modal.classList.remove('active');
        setTimeout(() => modal.remove(), 300);
    }
}

async function saveOpportunity(opportunityId) {
    try {
        // FIX: Ensure ID is valid
        if (!opportunityId || opportunityId === 'undefined') {
            console.error('Invalid ID for save:', opportunityId);
            return;
        }
        
        console.log('Saving opportunity:', opportunityId);
        await API.saveOpportunity(opportunityId);
        closeOpportunityModal();
        if (currentPage === 'opportunities') {
            await renderOpportunitiesPage();
        }
    } catch (error) {
        console.error('Failed to save opportunity:', error);
        alert('Failed to save opportunity');
    }
}

async function markAsApplied(opportunityId) {
    try {
        // FIX: Ensure ID is valid
        if (!opportunityId || opportunityId === 'undefined') {
            console.error('Invalid ID for apply:', opportunityId);
            return;
        }
        
        console.log('Marking as applied:', opportunityId);
        await API.markApplied(opportunityId);
        closeOpportunityModal();
        alert('Marked as applied!');
        if (currentPage === 'opportunities') {
            await renderOpportunitiesPage();
        }
    } catch (error) {
        console.error('Failed to mark as applied:', error);
        alert('Failed to mark as applied');
    }
}

// Niche management functions
async function toggleNiche(nicheId) {
    try {
        await API.toggleNiche(nicheId);
        await renderFiltersPage();
    } catch (error) {
        console.error('Failed to toggle niche:', error);
        alert('Failed to toggle niche');
    }
}

async function deleteNiche(nicheId) {
    if (!confirm('Are you sure you want to delete this niche?')) return;
    
    try {
        await API.deleteNiche(nicheId);
        await renderFiltersPage();
    } catch (error) {
        console.error('Failed to delete niche:', error);
        alert('Failed to delete niche');
    }
}

async function saveSettings() {
    const name = document.getElementById('settingsName').value;
    const whatsapp = document.getElementById('settingsWhatsapp').value;
    
    try {
        await API.updateProfile({ name, whatsapp_number: whatsapp });
        alert('Settings saved successfully!');
    } catch (error) {
        console.error('Failed to save settings:', error);
        alert('Failed to save settings');
    }
}

async function updateNotificationSetting(type, enabled) {
    try {
        const updateData = {};
        if (type === 'whatsapp') {
            updateData.whatsapp_notifications = enabled;
        } else if (type === 'email') {
            updateData.email_notifications = enabled;
        }
        
        await API.updateProfile(updateData);
    } catch (error) {
        console.error('Failed to update notification setting:', error);
    }
}

function openUpgradeModal() {
    document.getElementById('upgradeModal').classList.add('active');
}

// Helper function
function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    
    let interval = seconds / 31536000;
    if (interval > 1) return Math.floor(interval) + ' years ago';
    
    interval = seconds / 2592000;
    if (interval > 1) return Math.floor(interval) + ' months ago';
    
    interval = seconds / 86400;
    if (interval > 1) return Math.floor(interval) + ' days ago';
    
    interval = seconds / 3600;
    if (interval > 1) return Math.floor(interval) + ' hours ago';
    
    interval = seconds / 60;
    if (interval > 1) return Math.floor(interval) + ' minutes ago';
    
    return Math.floor(seconds) + ' seconds ago';
}

// Navigation handler
function navigateToPage(pageName) {
    const mainContent = document.querySelector('.dashboard-content');
    
    // Update active nav item
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    event.target.closest('.nav-item').classList.add('active');
    
    currentPage = pageName;

    // Render appropriate page
    switch(pageName) {
        case 'dashboard':
            renderDashboardPage();
            return;
        case 'opportunities':
            renderOpportunitiesPage();
            break;
        case 'filters':
            renderFiltersPage();
            break;
        case 'history':
            renderHistoryPage();
            break;
        case 'settings':
            renderSettingsPage();
            break;
    }

    // Close sidebar on mobile
    if (window.innerWidth <= 1024) {
        document.getElementById('sidebar').classList.remove('visible');
        document.getElementById('sidebar').classList.add('hidden');
        document.getElementById('sidebarOverlay').classList.remove('active');
    }

    window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function checkCanCreateNiche() {
    const user = await API.getCurrentUser();
    const niches = await API.getNiches();
    const plans = await API.getSubscriptionPlans();
    
    // Find the current plan for the user's tier
    const currentPlan = plans.find(p => p.tier === user.tier);
    const currentNicheCount = niches.length;
    
    if (currentNicheCount >= currentPlan.max_niches) {
        alert(`You've reached the maximum of ${currentPlan.max_niches} niches for your ${user.tier} plan. Upgrade to add more!`);
        openUpgradeModal();
        return false;
    }
    
    return true;
}

// Use before showing create niche form
async function showCreateNicheModal() {
    const canCreate = await checkCanCreateNiche();
    if (!canCreate) return;
    
    // Show modal...
}

async function renderPlatformSelectors() {
    const user = await API.getCurrentUser();
    const plans = await API.getSubscriptionPlans();
    
    const currentPlan = plans.find(p => p.tier === user.tier);
    const availablePlatforms = currentPlan.platforms;
    
    const allPlatforms = ['Twitter/X', 'Reddit', 'Web3.career', 'Pump.fun', 
                         'DexScreener', 'CoinMarketCap', 'CoinGecko', 'Telegram'];
    
    const container = document.getElementById('platformSelectors');
    container.innerHTML = '';
    
    allPlatforms.forEach(platform => {
        const isAvailable = availablePlatforms.includes(platform);
        const isPro = ['DexScreener', 'CoinMarketCap', 'CoinGecko', 'Telegram'].includes(platform);
        
        const label = document.createElement('label');
        label.className = 'platform-checkbox' + (!isAvailable ? ' disabled' : '');
        
        label.innerHTML = `
            <input type="checkbox" 
                   value="${platform}" 
                   ${!isAvailable ? 'disabled' : ''}>
            <span>${platform}</span>
            ${!isAvailable && isPro ? '<span class="pro-badge">PRO</span>' : ''}
        `;
        
        container.appendChild(label);
    });
}
async function showUsageLimits() {
    const user = await API.getCurrentUser();
    const plans = await API.getSubscriptionPlans();
    
    const currentPlan = plans.find(p => p.tier === user.tier);
    const monthlyLimit = currentPlan.monthly_opportunities_limit;
    const currentUsage = user.usage?.opportunities_sent || 0;
    
    const limitElement = document.getElementById('monthlyLimit');
    
    if (monthlyLimit === -1) {
        limitElement.innerHTML = `
            <div class="limit-unlimited">
                <i class="fas fa-infinity"></i>
                <span>Unlimited Opportunities</span>
            </div>
        `;
    } else {
        const percentage = (currentUsage / monthlyLimit) * 100;
        const remaining = monthlyLimit - currentUsage;
        
        limitElement.innerHTML = `
            <div class="limit-bar">
                <div class="limit-progress" style="width: ${percentage}%"></div>
            </div>
            <div class="limit-text">
                ${currentUsage} / ${monthlyLimit} opportunities used
                ${remaining > 0 ? `(${remaining} remaining)` : '(Limit reached)'}
            </div>
            ${remaining <= 0 ? `
                <button onclick="openUpgradeModal()" class="btn-upgrade">
                    Upgrade for More
                </button>
            ` : ''}
        `;
    }
}
async function showScanInterval() {
    const user = await API.getCurrentUser();
    const plans = await API.getSubscriptionPlans();
    
    const currentPlan = plans.find(p => p.tier === user.tier);
    const intervalMinutes = currentPlan.scan_interval_minutes;
    
    let intervalText;
    if (intervalMinutes >= 60) {
        intervalText = `${intervalMinutes / 60} hour${intervalMinutes > 60 ? 's' : ''}`;
    } else {
        intervalText = `${intervalMinutes} minutes`;
    }
    
    document.getElementById('scanInterval').textContent = 
        `Scans run automatically every ${intervalText}`;
}
// Initialize navigation
document.addEventListener('DOMContentLoaded', function() {
    const pages = ['dashboard', 'filters', 'opportunities', 'history', 'settings'];
    document.querySelectorAll('.nav-item').forEach((item, index) => {
        if (index < pages.length) {
            item.addEventListener('click', function(e) {
                e.preventDefault();
                navigateToPage(pages[index]);
            });
        }
    });
});

// Export functions
window.navigateToPage = navigateToPage;
window.openOpportunityModal = openOpportunityModal;
window.closeOpportunityModal = closeOpportunityModal;
window.openUpgradeModal = openUpgradeModal;
window.toggleNiche = toggleNiche;
window.deleteNiche = deleteNiche;
window.saveSettings = saveSettings;
window.updateNotificationSetting = updateNotificationSetting;
window.saveOpportunity = saveOpportunity;
window.markAsApplied = markAsApplied;
/**
 * Twitter Follow Modal Manager
 * Handles follow modal popup on first login or periodically
 */

class FollowModalManager {
    constructor() {
        this.baseUrl = 'http://localhost:8000/api/auth/follow';
        this.twitterUrl = 'https://x.com/db0sz1';
        this.isOpen = false;
    }
    
    /**
     * Initialize - check follow status on page load
     */
    async init() {
        try {
            // Only check if user is authenticated
            if (!TokenManager.isAuthenticated()) {
                return;
            }
            
            console.log('[FOLLOW] Initializing follow modal check...');
            
            // Get follow status
            const status = await this.getFollowStatus();
            
            // Show modal if needed
            if (status.should_show_modal) {
                console.log('[FOLLOW] Should show modal - displaying popup');
                this.showModal(status);
            } else {
                console.log('[FOLLOW] User already followed or modal dismissed recently');
            }
        } catch (error) {
            console.error('[FOLLOW] Init error:', error);
            // Don't break the app if follow modal fails
        }
    }
    
    /**
     * Get user's follow status
     */
    async getFollowStatus() {
        try {
            const response = await fetch(`${this.baseUrl}/status`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${TokenManager.getAccessToken()}`
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('[FOLLOW] Failed to get follow status:', error);
            throw error;
        }
    }
    
    /**
     * Show the follow modal
     */
    showModal(status) {
        const html = `
            <div class="follow-modal-overlay active" id="followModalOverlay">
                <div class="follow-modal" id="followModal">
                    <!-- Close button disabled - user must follow or explicitly close -->
                    
                    <div class="follow-modal-content">
                        <div class="follow-modal-header">
                            <div class="follow-modal-icon">
                                <i class="fab fa-x-twitter"></i>
                            </div>
                            <h2>Stay Updated!</h2>
                            <p>Follow us for exclusive opportunities and updates</p>
                        </div>
                        
                        <div class="follow-modal-body">
                            <div class="follow-info">
                                <div class="info-item">
                                    <i class="fas fa-bell"></i>
                                    <span>Get real-time job alerts</span>
                                </div>
                                <div class="info-item">
                                    <i class="fas fa-star"></i>
                                    <span>Exclusive opportunities</span>
                                </div>
                                <div class="info-item">
                                    <i class="fas fa-rocket"></i>
                                    <span>Product updates & tips</span>
                                </div>
                            </div>
                            
                            <div class="follow-twitter-preview">
                                <div class="twitter-card">
                                    <div class="twitter-header">
                                        <div class="twitter-avatar">
                                            <img src="https://pbs.twimg.com/profile_images/1445764532/twitter-bird-blue-on-white_normal.png" alt="@db0sz1">
                                        </div>
                                        <div class="twitter-info">
                                            <div class="twitter-name">Job Hunter Updates</div>
                                            <div class="twitter-handle">@db0sz1</div>
                                        </div>
                                    </div>
                                    <div class="twitter-bio">
                                        Your gateway to amazing opportunities. Follow for job alerts, tips, and exclusive content! 🚀
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="follow-modal-footer">
                            <button class="follow-btn-primary" id="followBtn" onclick="followModalManager.handleFollowClick()">
                                <i class="fab fa-x-twitter"></i>
                                Follow @db0sz1
                            </button>
                            
                            <button class="follow-btn-secondary" id="dismissBtn" onclick="followModalManager.dismissModal()">
                                Maybe Later
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Add modal to DOM
        document.body.insertAdjacentHTML('beforeend', html);
        
        // Add styles dynamically if not already in CSS
        this.addModalStyles();
        
        // Set up event listeners
        this.setupEventListeners();
        
        this.isOpen = true;
    }
    
    /**
     * Handle follow button click
     */
    async handleFollowClick() {
        try {
            console.log('[FOLLOW] Follow button clicked - opening Twitter');
            
            // Disable button to prevent double-clicks
            const btn = document.getElementById('followBtn');
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Opening...';
            
            // Open Twitter in new window
            const width = 500;
            const height = 700;
            const left = (window.innerWidth - width) / 2;
            const top = (window.innerHeight - height) / 2;
            
            const popup = window.open(
                this.twitterUrl,
                'followTwitter',
                `width=${width},height=${height},left=${left},top=${top}`
            );
            
            if (!popup) {
                alert('Please allow popups to follow on Twitter');
                btn.disabled = false;
                btn.innerHTML = '<i class="fab fa-x-twitter"></i> Follow @db0sz1';
                return;
            }
            
            // Focus the popup
            popup.focus();
            
            // Wait a bit for user to follow, then mark as followed
            // In production, you could use postMessage or check via API
            setTimeout(async () => {
                try {
                    // Mark user as followed
                    const response = await fetch(`${this.baseUrl}/mark-followed`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${TokenManager.getAccessToken()}`
                        },
                        body: JSON.stringify({ followed: true })
                    });
                    
                    if (response.ok) {
                        console.log('[FOLLOW] User marked as followed');
                        this.handleFollowSuccess();
                    }
                } catch (error) {
                    console.error('[FOLLOW] Error marking as followed:', error);
                }
            }, 2000);
            
        } catch (error) {
            console.error('[FOLLOW] Error in follow click:', error);
            const btn = document.getElementById('followBtn');
            btn.disabled = false;
            btn.innerHTML = '<i class="fab fa-x-twitter"></i> Follow @db0sz1';
            alert('Failed to open Twitter. Please try again.');
        }
    }
    
    /**
     * Handle successful follow
     */
    handleFollowSuccess() {
        const btn = document.getElementById('followBtn');
        const dismissBtn = document.getElementById('dismissBtn');
        
        // Update button state
        btn.disabled = true;
        btn.classList.add('followed');
        btn.innerHTML = '<i class="fas fa-check"></i> Following!';
        
        // Hide dismiss button
        dismissBtn.style.display = 'none';
        
        // Show success message
        const footer = document.querySelector('.follow-modal-footer');
        const successMsg = document.createElement('div');
        successMsg.className = 'follow-success-message';
        successMsg.innerHTML = `
            <i class="fas fa-check-circle"></i>
            <span>Thanks for following! Check your mentions for exclusive updates.</span>
        `;
        footer.appendChild(successMsg);
        
        // Close modal after 2 seconds
        setTimeout(() => {
            this.closeModal();
        }, 2000);
    }
    
    /**
     * Dismiss modal (maybe later)
     */
    async dismissModal() {
        try {
            console.log('[FOLLOW] Dismissing modal');
            
            // Notify backend
            await fetch(`${this.baseUrl}/dismiss-modal`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${TokenManager.getAccessToken()}`
                }
            });
            
            this.closeModal();
        } catch (error) {
            console.error('[FOLLOW] Error dismissing modal:', error);
            this.closeModal(); // Close anyway
        }
    }
    
    /**
     * Close the modal
     */
    closeModal() {
        const overlay = document.getElementById('followModalOverlay');
        if (overlay) {
            overlay.classList.remove('active');
            setTimeout(() => {
                overlay.remove();
            }, 300);
        }
        this.isOpen = false;
    }
    
    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Close on overlay click (optional - can remove if you want modal to be sticky)
        const overlay = document.getElementById('followModalOverlay');
        if (overlay) {
            // Don't close on overlay click - modal is persistent until followed
            // overlay.addEventListener('click', (e) => {
            //     if (e.target === overlay) {
            //         this.dismissModal();
            //     }
            // });
        }
        
        // Prevent closing with ESC key initially
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                // Don't close - user must follow or click "Maybe Later"
                e.preventDefault();
            }
        });
    }
    
    /**
     * Add modal styles to document
     */
    addModalStyles() {
        if (document.getElementById('followModalStyles')) {
            return; // Already added
        }
        
        const styles = `
            <style id="followModalStyles">
                .follow-modal-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: rgba(0, 0, 0, 0.7);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    z-index: 9999;
                    opacity: 0;
                    transition: opacity 0.3s ease;
                    pointer-events: none;
                }
                
                .follow-modal-overlay.active {
                    opacity: 1;
                    pointer-events: all;
                }
                
                .follow-modal {
                    background: white;
                    border-radius: 16px;
                    max-width: 500px;
                    width: 90%;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                    animation: slideUp 0.3s ease;
                    overflow: hidden;
                }
                
                @keyframes slideUp {
                    from {
                        transform: translateY(20px);
                        opacity: 0;
                    }
                    to {
                        transform: translateY(0);
                        opacity: 1;
                    }
                }
                
                .follow-modal-content {
                    display: flex;
                    flex-direction: column;
                }
                
                .follow-modal-header {
                    background: linear-gradient(135deg, #1DA1F2 0%, #1a91da 100%);
                    color: white;
                    padding: 40px 30px;
                    text-align: center;
                }
                
                .follow-modal-icon {
                    font-size: 48px;
                    margin-bottom: 16px;
                    animation: bounce 0.6s ease;
                }
                
                @keyframes bounce {
                    0%, 100% { transform: translateY(0); }
                    50% { transform: translateY(-10px); }
                }
                
                .follow-modal-header h2 {
                    font-size: 28px;
                    font-weight: 700;
                    margin: 0 0 8px 0;
                    font-family: 'Poppins', sans-serif;
                }
                
                .follow-modal-header p {
                    font-size: 14px;
                    opacity: 0.95;
                    margin: 0;
                }
                
                .follow-modal-body {
                    padding: 30px;
                }
                
                .follow-info {
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                    margin-bottom: 24px;
                }
                
                .info-item {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    font-size: 14px;
                    color: #333;
                }
                
                .info-item i {
                    color: #1DA1F2;
                    font-size: 18px;
                    flex-shrink: 0;
                }
                
                .follow-twitter-preview {
                    background: #f7f9fa;
                    padding: 16px;
                    border-radius: 12px;
                    border: 1px solid #e1e8ed;
                }
                
                .twitter-card {
                    background: white;
                    padding: 12px;
                    border-radius: 8px;
                }
                
                .twitter-header {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    margin-bottom: 8px;
                }
                
                .twitter-avatar {
                    width: 40px;
                    height: 40px;
                    border-radius: 50%;
                    overflow: hidden;
                    flex-shrink: 0;
                }
                
                .twitter-avatar img {
                    width: 100%;
                    height: 100%;
                    object-fit: cover;
                }
                
                .twitter-info {
                    flex: 1;
                    min-width: 0;
                }
                
                .twitter-name {
                    font-weight: 600;
                    font-size: 14px;
                    color: #0f1419;
                }
                
                .twitter-handle {
                    font-size: 13px;
                    color: #536471;
                }
                
                .twitter-bio {
                    font-size: 13px;
                    color: #0f1419;
                    line-height: 1.4;
                }
                
                .follow-modal-footer {
                    padding: 20px 30px;
                    border-top: 1px solid #eee;
                    display: flex;
                    flex-direction: column;
                    gap: 12px;
                }
                
                .follow-btn-primary,
                .follow-btn-secondary {
                    padding: 12px 24px;
                    border: none;
                    border-radius: 24px;
                    font-size: 14px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    font-family: inherit;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 8px;
                }
                
                .follow-btn-primary {
                    background: #1DA1F2;
                    color: white;
                }
                
                .follow-btn-primary:hover:not(:disabled) {
                    background: #1a91da;
                    transform: translateY(-2px);
                    box-shadow: 0 8px 20px rgba(29, 161, 242, 0.3);
                }
                
                .follow-btn-primary:disabled {
                    opacity: 0.7;
                    cursor: not-allowed;
                }
                
                .follow-btn-primary.followed {
                    background: #31a24c;
                }
                
                .follow-btn-secondary {
                    background: #f7f9fa;
                    color: #0f1419;
                    border: 1px solid #ccc;
                }
                
                .follow-btn-secondary:hover {
                    background: #eee;
                }
                
                .follow-success-message {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 12px;
                    background: #d4f8d4;
                    color: #31a24c;
                    border-radius: 8px;
                    font-size: 13px;
                    text-align: center;
                    animation: slideDown 0.3s ease;
                }
                
                @keyframes slideDown {
                    from {
                        opacity: 0;
                        transform: translateY(-10px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }
                
                .follow-success-message i {
                    font-size: 16px;
                }
                
                /* Dark mode support */
                @media (prefers-color-scheme: dark) {
                    .follow-modal {
                        background: #1a1a1a;
                    }
                    
                    .follow-modal-body {
                        color: #e0e0e0;
                    }
                    
                    .info-item {
                        color: #e0e0e0;
                    }
                    
                    .follow-modal-footer {
                        border-top-color: #333;
                    }
                    
                    .follow-twitter-preview {
                        background: #222;
                        border-color: #333;
                    }
                    
                    .twitter-card {
                        background: #1a1a1a;
                    }
                    
                    .twitter-name,
                    .twitter-bio {
                        color: #e0e0e0;
                    }
                    
                    .follow-btn-secondary {
                        background: #222;
                        color: #e0e0e0;
                        border-color: #444;
                    }
                }
            </style>
        `;
        
        document.head.insertAdjacentHTML('beforeend', styles);
    }
}

// Initialize follow modal manager
const followModalManager = new FollowModalManager();

// Auto-initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    followModalManager.init();
});

// Export for global use
window.followModalManager = followModalManager;

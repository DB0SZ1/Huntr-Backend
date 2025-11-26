/**
 * Promo redemption functionality
 * User provides X handle + phone number to claim trial
 */

class PromoManager {
    constructor() {
        this.baseUrl = 'http://localhost:8000/api/promo';
    }
    
    async validatePromo(twitterHandle, phoneNumber) {
        """Validate if user is eligible for promo"""
        try {
            const response = await fetch(`${this.baseUrl}/validate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    twitter_handle: twitterHandle,
                    phone_number: phoneNumber
                })
            });
            
            return await response.json();
        } catch (error) {
            console.error('Validation error:', error);
            return {
                valid: false,
                message: 'Error validating promo',
                error: error.message
            };
        }
    }
    
    async redeemPromo(twitterHandle, phoneNumber) {
        """Redeem promo (one-time use)"""
        try {
            const token = TokenManager.getAccessToken();
            
            const response = await fetch(`${this.baseUrl}/redeem`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    twitter_handle: twitterHandle,
                    phone_number: phoneNumber
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Failed to redeem promo');
            }
            
            return {
                success: true,
                ...data
            };
        } catch (error) {
            console.error('Redemption error:', error);
            return {
                success: false,
                message: error.message
            };
        }
    }
}

const promo = new PromoManager();

async function showPromoModal() {
    const html = `
        <div class="modal-overlay promo-modal active" id="promoModal">
            <div class="modal-content promo-modal-content">
                <button class="modal-close" onclick="closePromoModal()">
                    <i class="fas fa-times"></i>
                </button>
                
                <div class="promo-header">
                    <h2>Claim Your Free Trial</h2>
                    <p>Enter your X handle and phone number to claim 14 days of PRO access</p>
                </div>
                
                <div class="promo-body">
                    <div class="form-group">
                        <label>X Handle</label>
                        <input type="text" id="promoXHandle" 
                               placeholder="@yourhandle" 
                               class="form-input"
                               autocomplete="off">
                        <small>Your X/Twitter handle (with or without @)</small>
                    </div>
                    
                    <div class="form-group">
                        <label>Phone Number</label>
                        <input type="tel" id="promoPhoneNumber" 
                               placeholder="+234-803-123-4567" 
                               class="form-input"
                               autocomplete="off">
                        <small>Phone number used during registration</small>
                    </div>
                    
                    <button class="btn-primary" onclick="validateAndRedeemPromo()">
                        <i class="fas fa-check"></i> Claim Trial
                    </button>
                    
                    <div id="promoMessage"></div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', html);
}

function closePromoModal() {
    const modal = document.getElementById('promoModal');
    if (modal) {
        modal.classList.remove('active');
        setTimeout(() => modal.remove(), 300);
    }
}

async function validateAndRedeemPromo() {
    const handle = document.getElementById('promoXHandle').value.trim();
    const phone = document.getElementById('promoPhoneNumber').value.trim();
    const messageDiv = document.getElementById('promoMessage');
    
    if (!handle || !phone) {
        messageDiv.innerHTML = `
            <div class="alert-error">
                <i class="fas fa-exclamation-circle"></i>
                Please enter both X handle and phone number
            </div>
        `;
        return;
    }
    
    // Show validating
    messageDiv.innerHTML = `
        <div class="alert-info">
            <i class="fas fa-spinner fa-spin"></i>
            Checking eligibility...
        </div>
    `;
    
    try {
        // Validate first
        const validation = await promo.validatePromo(handle, phone);
        
        if (!validation.valid) {
            messageDiv.innerHTML = `
                <div class="alert-error">
                    <i class="fas fa-times-circle"></i>
                    ${validation.message}
                </div>
            `;
            return;
        }
        
        // Now redeem
        messageDiv.innerHTML = `
            <div class="alert-info">
                <i class="fas fa-spinner fa-spin"></i>
                Activating your trial...
            </div>
        `;
        
        const redemption = await promo.redeemPromo(handle, phone);
        
        if (!redemption.success) {
            messageDiv.innerHTML = `
                <div class="alert-error">
                    <i class="fas fa-times-circle"></i>
                    ${redemption.message}
                </div>
            `;
            return;
        }
        
        // Success!
        messageDiv.innerHTML = `
            <div class="alert-success">
                <i class="fas fa-check-circle"></i>
                <strong>🎉 Success!</strong><br>
                Your ${redemption.tier.toUpperCase()} trial is now active!<br>
                Enjoy ${redemption.duration_days} days of premium features<br>
                <small>Expires: ${new Date(redemption.expires_at).toLocaleDateString()}</small>
            </div>
        `;
        
        // Reload after success
        setTimeout(() => {
            closePromoModal();
            location.reload();
        }, 2500);
    
    } catch (error) {
        messageDiv.innerHTML = `
            <div class="alert-error">
                <i class="fas fa-exclamation-circle"></i>
                Error: ${error.message}
            </div>
        `;
    }
}

// Export for use
window.promoManager = promo;
window.showPromoModal = showPromoModal;
window.closePromoModal = closePromoModal;
window.validateAndRedeemPromo = validateAndRedeemPromo;

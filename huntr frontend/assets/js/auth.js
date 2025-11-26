/**
 * Authentication JavaScript - COMPLETE REWRITE
 * Real Google OAuth integration, NO mock data
 */

// API Base URL
const API_BASE_URL = 'http://localhost:8000';

// Tab switching
const signupTab = document.getElementById('signupTab');
const signinTab = document.getElementById('signinTab');
const signupForm = document.getElementById('signupForm');
const signinForm = document.getElementById('signinForm');

if (signupTab && signinTab) {
    signupTab.addEventListener('click', () => {
        signupTab.classList.add('active');
        signinTab.classList.remove('active');
        signupForm.style.display = 'block';
        signinForm.style.display = 'none';
    });

    signinTab.addEventListener('click', () => {
        signinTab.classList.add('active');
        signupTab.classList.remove('active');
        signinForm.style.display = 'block';
        signupForm.style.display = 'none';
    });
}

// Real Google OAuth Login
function loginWithGoogle() {
    // Redirect to backend OAuth endpoint
    window.location.href = `${API_BASE_URL}/api/auth/google/login`;
}

// Attach Google login to all Google buttons
document.addEventListener('DOMContentLoaded', () => {
    const googleButtons = document.querySelectorAll('.social-btn');
    googleButtons.forEach(btn => {
        if (btn.textContent.includes('Google')) {
            btn.onclick = loginWithGoogle;
        }
    });
});

// Traditional form submissions (disabled - we only use OAuth)
const signupFormElement = document.getElementById('signupFormElement');
const signinFormElement = document.getElementById('signinFormElement');

if (signupFormElement) {
    signupFormElement.addEventListener('submit', (e) => {
        e.preventDefault();
        alert('Please use Google Sign In for authentication');
    });
}

if (signinFormElement) {
    signinFormElement.addEventListener('submit', (e) => {
        e.preventDefault();
        alert('Please use Google Sign In for authentication');
    });
}

// Traditional Signup
const signupForm = document.getElementById('traditionalSignupForm');
if (signupForm) {
    signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const name = document.getElementById('signupName').value;
        const email = document.getElementById('signupEmail').value;
        const password = document.getElementById('signupPassword').value;
        
        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/signup`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, password })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                alert('Signup successful! Check your email for verification link.');
                window.location.href = '/auth/check-email.html?email=' + encodeURIComponent(email);
            } else {
                alert(data.detail || 'Signup failed');
            }
        } catch (error) {
            alert('Signup error: ' + error.message);
        }
    });
}

// Traditional Login
const loginForm = document.getElementById('traditionalLoginForm');
if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;
        
        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);
                window.location.href = '/dashboard.html';
            } else {
                alert(data.detail || 'Login failed');
            }
        } catch (error) {
            alert('Login error: ' + error.message);
        }
    });
}

// Check if already authenticated
if (localStorage.getItem('access_token')) {
    // Already logged in, redirect to dashboard
    window.location.href = '/dashboard.html';
}

function switchToSignup() {
    document.getElementById('signupTab').click();
}

function switchToSignin() {
    document.getElementById('signinTab').click();
}

// Google Login Callback
async function handleGoogleLogin(response) {
    try {
        const { credential } = response;
        
        // Send to backend
        const result = await API.loginWithGoogle(credential);
        
        if (result.access_token) {
            // Store token
            TokenManager.setTokens(result.access_token, result.refresh_token);
            
            // Get user info to check if admin
            const user = await API.getCurrentUser();
            
            // Route based on role
            if (user.is_admin || user.settings?.is_admin) {
                // Admin user - redirect to admin panel
                console.log("Admin user detected, redirecting to admin panel...");
                window.location.href = '/admin/index.html';  // ← ADMIN REDIRECT
            } else {
                // Regular user - redirect to dashboard
                console.log("Regular user, redirecting to dashboard...");
                window.location.href = '/dashboard.html';
            }
        } else {
            showError("Login failed");
        }
    } catch (error) {
        console.error("Google login error:", error);
        showError("Login error: " + error.message);
    }
}
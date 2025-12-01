// assets/scripts/auth-utils.js - Authentication utility functions
class AuthUtils {
    /**
     * Check if user is authenticated and optionally redirect to login
     * @param {boolean} redirectToLogin - Whether to redirect if not authenticated
     * @returns {boolean} - Authentication status
     */
    static checkAuthentication(redirectToLogin = true) {
        const isAuth = APIClient.isAuthenticated();
        
        if (!isAuth && redirectToLogin) {
            console.log('User not authenticated, redirecting to login...');
            // Store the current page to redirect back after login
            sessionStorage.setItem('redirect_after_login', window.location.pathname);
            window.location.href = '/login';
            return false;
        }
        
        return isAuth;
    }

    /**
     * Get current user data from sessionStorage
     * @returns {Object|null} - User data object or null
     */
    static getCurrentUser() {
        try {
            const userData = sessionStorage.getItem('user_data');
            return userData ? JSON.parse(userData) : null;
        } catch (error) {
            console.error('Error retrieving user data:', error);
            return null;
        }
    }

    /**
     * Store user profile data in sessionStorage
     * @param {Object} userData - User data to store
     */
    static setCurrentUser(userData) {
        try {
            if (userData) {
                sessionStorage.setItem('user_data', JSON.stringify(userData));
                console.log('User data stored in sessionStorage');
            }
        } catch (error) {
            console.error('Error storing user data:', error);
        }
    }

    /**
     * Update user profile data
     * @param {Object} userData - Updated user data
     */
    static updateUserProfile(userData) {
        this.setCurrentUser(userData);
    }

    /**
     * Clear user data from storage
     */
    static clearUserData() {
        try {
            sessionStorage.removeItem('user_data');
            console.log('User data cleared');
        } catch (error) {
            console.error('Error clearing user data:', error);
        }
    }

    /**
     * Require authentication - fetch user profile if authenticated
     * @returns {Promise<Object>} - Resolves with user data or redirects to login
     */
    static async requireAuth() {
        return new Promise(async (resolve, reject) => {
            // Check if we have tokens
            if (!APIClient.isAuthenticated()) {
                console.log('No access token, checking for refresh token...');
                
                // Try to use refresh token
                if (APIClient.getRefreshToken()) {
                    try {
                        // Attempt to fetch profile (will auto-refresh token if expired)
                        const response = await APIClient.getProfile();
                        const userData = response.user || response;
                        
                        // Store user data
                        this.setCurrentUser(userData);
                        
                        console.log('Authentication successful via refresh');
                        resolve(userData);
                    } catch (error) {
                        console.error('Token refresh failed:', error);
                        // Store current page for redirect after login
                        sessionStorage.setItem('redirect_after_login', window.location.pathname);
                        window.location.href = '/login';
                        reject(new Error('Authentication failed'));
                    }
                } else {
                    console.log('No refresh token available');
                    sessionStorage.setItem('redirect_after_login', window.location.pathname);
                    window.location.href = '/login';
                    reject(new Error('Not authenticated'));
                }
            } else {
                // We have access token, fetch user data
                try {
                    const response = await APIClient.getProfile();
                    const userData = response.user || response;
                    
                    // Store user data
                    this.setCurrentUser(userData);
                    
                    console.log('Authentication verified');
                    resolve(userData);
                } catch (error) {
                    console.error('Failed to fetch user profile:', error);
                    
                    // If profile fetch fails, try to use cached data
                    const cachedUser = this.getCurrentUser();
                    if (cachedUser) {
                        console.log('Using cached user data');
                        resolve(cachedUser);
                    } else {
                        // Clear tokens and redirect
                        APIClient.clearTokens();
                        sessionStorage.setItem('redirect_after_login', window.location.pathname);
                        window.location.href = '/login';
                        reject(error);
                    }
                }
            }
        });
    }

    /**
     * Check if user has a specific permission or role
     * @param {string} permission - Permission/role to check
     * @returns {boolean} - Whether user has permission
     */
    static hasPermission(permission) {
        const user = this.getCurrentUser();
        if (!user) return false;
        
        // Check if user has the permission
        // Adjust this based on your user object structure
        if (user.permissions && Array.isArray(user.permissions)) {
            return user.permissions.includes(permission);
        }
        
        // Check for admin/staff status
        if (permission === 'admin') {
            return user.is_staff || user.is_superuser;
        }
        
        return false;
    }

    /**
     * Logout user and clear all data
     * @param {string} redirectUrl - URL to redirect after logout (default: '/login')
     */
    static async logout(redirectUrl = '/login') {
        try {
            // Call logout endpoint
            await APIClient.post('/auth/logout/', {
                refresh_token: APIClient.getRefreshToken()
            });
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            // Clear tokens and user data
            APIClient.clearTokens();
            this.clearUserData();
            
            // Redirect
            window.location.href = redirectUrl;
        }
    }

    /**
     * Handle redirect after successful login
     */
    static handleLoginRedirect() {
        const redirectUrl = sessionStorage.getItem('redirect_after_login');
        
        if (redirectUrl && redirectUrl !== '/login' && redirectUrl !== '/register') {
            sessionStorage.removeItem('redirect_after_login');
            window.location.href = redirectUrl;
        } else {
            window.location.href = '/dashboard';
        }
    }

    /**
     * Get user's display name
     * @returns {string} - User's display name
     */
    static getUserDisplayName() {
        const user = this.getCurrentUser();
        if (!user) return 'Guest';
        
        // Try different name fields
        if (user.first_name && user.last_name) {
            return `${user.first_name} ${user.last_name}`;
        }
        if (user.first_name) {
            return user.first_name;
        }
        if (user.username) {
            return user.username;
        }
        if (user.email) {
            return user.email.split('@')[0];
        }
        
        return 'User';
    }

    /**
     * Get user's email
     * @returns {string|null} - User's email or null
     */
    static getUserEmail() {
        const user = this.getCurrentUser();
        return user ? user.email : null;
    }

    /**
     * Check if user's profile is complete
     * @returns {boolean} - Whether profile is complete
     */
    static isProfileComplete() {
        const user = this.getCurrentUser();
        if (!user) return false;
        
        // Check if user has profile data
        if (user.profile) {
            return user.profile.is_complete || false;
        }
        
        // Basic completeness check
        return !!(user.first_name && user.last_name && user.phone_number);
    }

    /**
     * Initialize auth utilities (call on page load)
     */
    static async init() {
        console.log('AuthUtils initialized');
        
        // Check if we're on a public page
        const publicPages = ['/login', '/register', '/forgot-password', '/reset-password'];
        const currentPath = window.location.pathname;
        
        if (publicPages.some(page => currentPath.startsWith(page))) {
            console.log('On public page, skipping auth check');
            return;
        }
        
        // For protected pages, verify authentication
        if (APIClient.isAuthenticated()) {
            try {
                // Fetch and cache user data
                await this.requireAuth();
                console.log('User authenticated and data cached');
            } catch (error) {
                console.error('Auth initialization failed:', error);
            }
        }
    }

    /**
     * Refresh user data from server
     * @returns {Promise<Object>} - Updated user data
     */
    static async refreshUserData() {
        try {
            const response = await APIClient.getProfile();
            const userData = response.user || response;
            this.setCurrentUser(userData);
            console.log('User data refreshed');
            return userData;
        } catch (error) {
            console.error('Failed to refresh user data:', error);
            throw error;
        }
    }
}

// Make AuthUtils globally available
window.AuthUtils = AuthUtils;

// Auto-initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        AuthUtils.init();
    });
} else {
    AuthUtils.init();
}

// Export for module systems (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AuthUtils;
}

console.log('AuthUtils loaded successfully');
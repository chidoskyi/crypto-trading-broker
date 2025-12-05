// assets/scripts/api.js - Axios version with secure token handling
console.log('APIConnector loaded');

// NOTE: Ensure 'axios' is loaded in your environment before this script runs.

class APIConnector {
    constructor(baseUrl = '/api/v1') {
        this.baseUrl = baseUrl;
        this.accessToken = null;
        this.refreshToken = null;
        this.isRefreshing = false;
        this.failedQueue = [];

        // Load tokens from storage on initialization
        this.loadTokensFromStorage();

        // Create axios instance
        this.client = axios.create({
            baseURL: baseUrl,
            headers: {
                // Default to application/json, but this will be removed by the interceptor for FormData
                'Content-Type': 'application/json', 
            },
            withCredentials: true,
        });

        this.setupInterceptors();
    }

    // --- Token & Storage Management ---

    // Load tokens from sessionStorage
    loadTokensFromStorage() {
        try {
            this.accessToken = sessionStorage.getItem('access_token');
            this.refreshToken = sessionStorage.getItem('refresh_token');
            console.log('Loaded tokens from storage:', {
                hasAccessToken: !!this.accessToken,
                hasRefreshToken: !!this.refreshToken
            });
        } catch (error) {
            console.error('Error loading tokens from storage:', error);
            this.clearTokens();
        }
    }

    // Token management with sessionStorage persistence
    setTokens(accessToken, refreshToken) {
        this.accessToken = accessToken;
        this.refreshToken = refreshToken;

        // Store in sessionStorage for page navigation
        try {
            if (accessToken) {
                sessionStorage.setItem('access_token', accessToken);
            }
            if (refreshToken) {
                sessionStorage.setItem('refresh_token', refreshToken);
            }
            console.log('Tokens stored in sessionStorage');
        } catch (error) {
            console.error('Error storing tokens:', error);
        }
    }

    clearTokens() {
        this.accessToken = null;
        this.refreshToken = null;
        try {
            sessionStorage.removeItem('access_token');
            sessionStorage.removeItem('refresh_token');
            console.log('Tokens cleared from storage');
        } catch (error) {
            console.error('Error clearing tokens:', error);
        }
    }

    getAccessToken() {
        return this.accessToken;
    }

    getRefreshToken() {
        return this.refreshToken;
    }

    // CSRF Token function (for Django protection)
    getCSRFToken() {
        // First try to get from meta tag
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            return metaTag.getAttribute('content');
        }

        // Fallback to cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return decodeURIComponent(value);
            }
        }
        return '';
    }

    // --- Interceptor Setup ---

    // Setup request/response interceptors
    setupInterceptors() {
        // Request interceptor: Adds tokens, CSRF, and handles FormData header
        this.client.interceptors.request.use(
            (config) => {
                // Add CSRF token
                const csrfToken = this.getCSRFToken();
                if (csrfToken) {
                    config.headers['X-CSRFToken'] = csrfToken;
                }

                // Add Authorization header if token exists
                if (this.accessToken) {
                    config.headers['Authorization'] = `Bearer ${this.accessToken}`;
                }
                
                // 🌟 FIX FOR FILE UPLOADS (MULTIPART/FORM-DATA) 🌟
                // If the data is a FormData instance, remove the default 'Content-Type' header.
                // The browser will automatically set the correct 'multipart/form-data' header.
                if (config.data instanceof FormData) {
                    delete config.headers['Content-Type'];
                }

                return config;
            },
            (error) => {
                return Promise.reject(error);
            }
        );

        // Response interceptor: Handles 401 token refresh logic
        this.client.interceptors.response.use(
            (response) => response,
            async (error) => {
                const originalRequest = error.config;

                // Handle 401 and token refresh
                if (error.response?.status === 401 && !originalRequest._retry && this.refreshToken) {
                    if (this.isRefreshing) {
                        // Queue the request
                        return new Promise((resolve, reject) => {
                            this.failedQueue.push({ resolve, reject });
                        }).then(() => {
                            return this.client(originalRequest);
                        });
                    }

                    originalRequest._retry = true;
                    this.isRefreshing = true;

                    try {
                        const response = await axios.post(
                            `${this.baseUrl}/token/refresh/`,
                            { refresh: this.refreshToken },
                            {
                                withCredentials: true,
                                headers: {
                                    'X-CSRFToken': this.getCSRFToken()
                                }
                            }
                        );

                        const { access, refresh } = response.data;
                        this.setTokens(access, refresh || this.refreshToken);

                        // Update the authorization header for the original request
                        originalRequest.headers['Authorization'] = `Bearer ${access}`;

                        // Retry all queued requests
                        this.failedQueue.forEach(({ resolve }) => resolve());
                        this.failedQueue = [];

                        // Retry the original request
                        return this.client(originalRequest);
                    } catch (refreshError) {
                        this.failedQueue.forEach(({ reject }) => reject(refreshError));
                        this.failedQueue = [];
                        this.clearTokens();

                        // Redirect to login
                        console.error('Token refresh failed, redirecting to login');
                        // Consider using history.push('/login') in an SPA
                        window.location.href = '/login'; 
                        return Promise.reject(refreshError);
                    } finally {
                        this.isRefreshing = false;
                    }
                }

                return Promise.reject(this.handleError(error));
            }
        );
    }

    // --- Error Handling ---

    // Standardized error handling function
    handleError(error) {
        let message = 'An error occurred';

        if (error.response) {
            const data = error.response.data;

            if (data.detail) {
                message = data.detail;
            } else if (data.message) {
                message = data.message;
            } else if (typeof data === 'object' && !Array.isArray(data)) {
                // Handle field errors
                const fieldErrors = Object.entries(data)
                    .filter(([key]) => key !== 'success') 
                    .map(([field, errors]) => {
                        const errorMsg = Array.isArray(errors) ? errors.join(', ') : errors;
                        return `${field}: ${errorMsg}`;
                    })
                    .join('; ');
                message = fieldErrors || message;
            }
        } else if (error.request) {
            message = 'Network error. Please check your connection.';
        }

        const customError = new Error(message);
        customError.status = error.response?.status;
        customError.response = error.response;
        return customError;
    }

    // --- Public API Wrapper Methods ---

    async get(endpoint, config = {}) {
        const response = await this.client.get(endpoint, config);
        return response;
    }

    async post(endpoint, data = null, config = {}) {
        const response = await this.client.post(endpoint, data, config);
        return response;
    }

    async put(endpoint, data = null, config = {}) {
        const response = await this.client.put(endpoint, data, config);
        return response;
    }

    async patch(endpoint, data = null, config = {}) {
        const response = await this.client.patch(endpoint, data, config);
        return response;
    }

    async delete(endpoint, config = {}) {
        const response = await this.client.delete(endpoint, config);
        return response;
    }

    // Check if user is authenticated
    isAuthenticated() {
        return !!this.accessToken;
    }

    /**
     * Helper to extract data from paginated API responses
     * @param {Object} responseData - The raw response data
     * @returns {Array|Object} - Extracted data
     */
    extractFromPagination(responseData) {
        if (responseData && Array.isArray(responseData.results)) {
            console.log('Extracting from paginated response, count:', responseData.results.length);
            return responseData.results;
        }
        return responseData;
    }

    /**
     * Helper to extract single item from paginated API responses
     * @param {Object} responseData - The raw response data
     * @param {number} index - Index to extract (default: 0)
     * @returns {Object|null} - Extracted item or null
     */
    extractSingleFromPagination(responseData, index = 0) {
        if (responseData && Array.isArray(responseData.results)) {
            if (responseData.results.length > index) {
                return responseData.results[index];
            } else if (responseData.results.length > 0) {
                console.warn(`Index ${index} out of bounds, returning first item`);
                return responseData.results[0];
            }
            console.warn('Empty results array');
            return null;
        }
        return responseData;
    }

    /**
     * Login a user.
     * Maps to: POST /auth/login/
     * @param {Object} credentials - The user credentials containing the username and password.
     * @returns {Promise}
     */
    async login(credentials) {
        try {
            const response = await this.post('/auth/login/', credentials);
            const data = response.data;

            if (data.tokens) {
                this.setTokens(data.tokens.access, data.tokens.refresh);
            } else if (data.access && data.refresh) {
                this.setTokens(data.access, data.refresh);
            }

            return data;
        } catch (error) {
            throw error;
        }
    }

    /**
     * Logout the current user.
     * Maps to: POST /auth/logout/
     * @returns {Promise}
     */
    async logout() {
        try {
            await this.post('/auth/logout/');
        } finally {
            this.clearTokens();
        }
    }

    /**
     * Register a new user.
     * Maps to: POST /auth/register/
     * @param {Object} userData - The user data containing the username, email, and password.
     * @returns {Promise}
     */
    async register(userData) {
        try {
            const response = await this.post('/auth/register/', userData);
            const data = response.data;

            if (data.tokens) {
                this.setTokens(data.tokens.access, data.tokens.refresh);
            }

            return data;
        } catch (error) {
            throw error;
        }
    }

    /**
     * Change the current authenticated user's password.
     * Maps to: POST /auth/change-password/
     * @param {Object} passwordData - The user data containing the new password.
     * @returns {Promise}
     */
    async changePassword(passwordData) {
        const response = await this.post('/auth/change-password/', passwordData);
        const data = response.data;
        console.log('Password Changed:', data);
        return data;
    }

    /**
     * Request a password reset for a user.
     * Maps to: POST /auth/password/reset/
     * @param {string} email - The user's email address.
     * @returns {Promise}
     */
    async requestPasswordReset(email) {
            console.log('🔐 [Password Reset] Requesting reset for email:', email);
            
            // Send email directly as the value, not wrapped in an object
            const response = await this.post('/auth/password/reset/', { email: email });
            
            console.log('✅ [Password Reset] Request successful:', response.data);
            return response.data;
    }

    /**
     * Validate a password reset token.
     * Maps to: GET /auth/password/reset/validate/{uidb64}/{token}/
     * @param {string} uidb64 - The user ID in base64 format.
     * @param {string} token - The reset token.
     * @returns {Promise}
     */
    async requestPasswordResetValidate(uidb64, token) {
            console.log('🔐 [Password Reset] Requesting reset for email:', email);
            
            // Send email directly as the value, not wrapped in an object
            const response = await this.post('/auth/password/reset/', { email: email });
            
            console.log('✅ [Password Reset] Request successful:', response.data);
            return response.data;
    }

    /**
     * Validate a password reset token.
     * Maps to: GET /auth/password/reset/validate/{uidb64}/{token}/
     * @param {string} uidb64 - The user ID in base64 format.
     * @param {string} token - The reset token.
     * @returns {Promise}
     */
    async passwordResetValidate(uidb64, token) {

        const response = await this.get(`/auth/password/reset/validate/${uidb64}/${token}/`);
        return response.data;
    }

    /**
     * Reset the current authenticated user's password.
     * Maps to: POST /auth/password/reset/confirm/{uidb64}/{token}/
     * @param {string} uidb64 - The user ID in base64 format.
     * @param {string} token - The reset token.
     * @param {Object} data - The new password data.
     * @returns {Promise}
     */
    async resetPassword(uidb64, token, data) {
        const response = await this.post(`/auth/password/reset/confirm/${uidb64}/${token}/`, data);
        return response.data;
    }

    /**
     * Get the country list
     * Maps to: GET /auth/countries/
     * @returns {Promise<Array>} Array of countries
     */
    async getCountryList() {
        try {
            const response = await this.get('/auth/countries/');
            console.log('Country List API Response:', response.data);
            return this.extractFromPagination(response.data);
        } catch (error) {
            console.error('Error in getCountryList:', error);
            throw error;
        }
    }

    // ===== PROFILE =====

    /**
     * Get the current authenticated user's profile and core user data.
     * Maps to: GET /profile/
     * @returns {Promise<Object>} The user profile object
     */
    async getMyProfile() {
        try {
            const response = await this.get('/profile/');
            console.log('My Profile API Response:', response.data);
            
            // Use the helper to extract single profile
            const profile = this.extractSingleFromPagination(response.data);
            
            if (!profile) {
                throw new Error('No profile data found');
            }
            
            console.log('Profile extracted:', profile);
            return profile;
        } catch (error) {
            console.error('Error in getMyProfile:', error);
            throw error;
        }
    }
    
/**
 * Update the current user's profile
 * Maps to: PUT /profile/update_profile/
 * @param {Object} data - Profile data to update
 * @returns {Promise<Object>} Updated profile
 */
    async updateMyProfile(data) {
        try {
            const formData = new FormData();
            
            // Add all the data fields to FormData
            Object.keys(data).forEach(key => {
                const value = data[key];
                
                // Skip null, undefined, or empty string values
                if (value === null || value === undefined || value === '') {
                    return;
                }
                // Handle country object - send just the name
                else if (key === 'country' && typeof value === 'object') {
                    formData.append(key, value.name);
                }
                // Handle all other values
                else {
                    formData.append(key, value);
                }
            });
            
            // Log what we're sending for debugging
            console.log('Sending profile update with data:');
            for (let pair of formData.entries()) {
                console.log(pair[0] + ': ' + pair[1]);
            }
            
            const response = await this.patch('/profile/update_profile/', formData);
            console.log('Update Profile Response:', response.data);
            return response.data;
        } catch (error) {
            console.error('Error in updateMyProfile:', error);
            throw error;
        }
    }

    /**
     * Get a user's public profile by username.
     * Maps to: GET /profile/get_by_username/?username=...
     * @param {string} username - The username of the profile to fetch.
     * @returns {Promise}
     */
    async getProfileByUsername(username) {
        if (!username) {
            throw new Error("Username is required to fetch profile.");
        }
        const response = await this.get('/profile/get_by_username/', { username });
        console.log(`Profile for ${username}:`, response.data);
        return response.data;
    }

    /**
     * Upload or update the current user's profile picture.
     * Maps to: POST /profile/upload_profile_picture/
     * @param {File} profilePictureFile - The file object to upload.
     * @returns {Promise}
     */
    async uploadProfilePicture(profilePictureFile) {
        const formData = new FormData();
        formData.append('profile_picture', profilePictureFile);
        
        const response = await this.post('/profile/upload_profile_picture/', formData);
        console.log('Picture Uploaded:', response.data);
        return response.data;
    }
    
    /**
     * Delete the current user's profile picture.
     * Maps to: DELETE /profile/delete_profile_picture/
     * @returns {Promise}
     */
    async deleteProfilePicture() {
        const response = await this.delete('/profile/delete_profile_picture/');
        console.log('Picture Deleted:', response.data);
        return response.data;
    }
    
    /**
     * Check the completeness status of the current user's profile.
     * Maps to: GET /profile/check_completeness/
     * @returns {Promise}
     */
    async checkProfileCompleteness() {
        const response = await this.get('/profile/check_completeness/');
        console.log('Profile Completeness:', response.data);
        return response.data;
    }



    // Check if user is authenticated
    isAuthenticated() {
        return !!this.accessToken;
    }

    // // Get user profile
    // async getProfile() {
    //     const response = await this.get('/auth/profile/');
    //     return response.data;
    // }

    // // Complete profile (for profile completion page)
    // async completeProfile(formData) {
    //     try {
    //         const response = await this.post('/auth/profile/complete/', formData, {
    //             headers: {
    //                 'Content-Type': 'multipart/form-data'
    //             }
    //         });
    //         return response;
    //     } catch (error) {
    //         throw error;
    //     }
    // }

    // ===== DEPOSITS =====
    
    /**
     * Create a new deposit.
     * Maps to: POST /deposits/
     * @param {Object} depositData - The deposit data to create.
     * @returns {Promise}
     */
    async createDeposit(depositData) {
        const response = await this.post(`/deposits/`, depositData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            },
        });
        console.log(response.data);
        return response.data;
    }

    
    async getWallet(currency) {
            const response = await this.get(`wallets/by-currency/${currency}/`);
            console.log(response.data);
            return response.data;
    }

    async getAdminWallet() {
            const response = await this.get('wallets/admin_wallet/');
            console.log(response.data);
            return response.data;
    }

    async getPaymentMethods() {
            const response = await this.get('payment-methods/');
            console.log(response.data);
            return response.data;
    }

    // ===== INVESTMENT =====

    async getInvestmentPlans() {
        const response = await this.get('plans/');
        console.log(response.data);
        return response.data;
    }

    async getInvestments() {
        const response = await this.get('investment/');
        console.log(response.data);
        return response.data;
    }

    async getActiveInvestments() {
        const response = await this.get('investment/active/');
        console.log(response.data);
        return response.data;
    }

    async getCompletedInvestments() {
        const response = await this.get('investment/completed/');
        console.log(response.data);
        return response.data;
    }

    async createInvestment(investmentData) {
        const response = await this.post(`/investment/create_investment/`, investmentData);
        console.log(response.data);
        return response.data;
    }

    // ===== TRADING PAIRS =====

    /**
     * Get all trading pairs with optional filters
     * @param {Object} params - Query parameters (search, market_type, asset_category, etc.)
     */
    async getTradingPairs(params) {
        const response = await this.get(`/trading-pairs/`, params);
        console.log('Trading pairs:', response.data);
        return response.data;
    }
    /**
     * Get all trading pairs with optional filters
     * @param {number} pairId - Trading pair ID
     */
    async getTickerData(pairId) {
        const response = await this.get(`/trading-pairs/${pairId}/ticker/`);
        console.log('Ticker data:', response.data);
        return response.data;
    }

    
    async getTradingConfig() {
        const response = await this.get('/trading/config/');
        console.log('Trading config:', response.data);
        return response.data;
    }

    /**
     * Get a single trading pair by ID
     * @param {number} pairId - Trading pair ID
     */
    async getTradingPair(pairId) {
        const response = await this.get(`/trading-pairs/${pairId}/`);
        console.log('Trading pair:', response.data);
        return response.data;
    }

    /**
     * Get trading pairs grouped by category
     */
    async getTradingPairsByCategory() {
        const response = await this.get(`/trading-pairs/by_category/`);
        console.log('Pairs by category:', response.data);
        return response.data;
    }

    /**
     * Get cryptocurrency pairs
     */
    async getCryptoPairs() {
        const response = await this.get(`/trading-pairs/crypto/`);
        console.log('Crypto pairs:', response.data);
        return response.data;
    }

    /**
     * Get stock pairs
     */
    async getStockPairs() {
        const response = await this.get(`/trading-pairs/stocks/`);
        console.log('Stock pairs:', response.data);
        return response.data;
    }

    /**
     * Get forex pairs
     */
    async getForexPairs() {
        const response = await this.get(`/trading-pairs/forex/`);
        console.log('Forex pairs:', response.data);
        return response.data;
    }

    /**
     * Get commodity pairs
     */
    async getCommodityPairs() {
        const response = await this.get(`/trading-pairs/commodities/`);
        console.log('Commodity pairs:', response.data);
        return response.data;
    }

    /**
     * Get bond pairs
     */
    async getBondPairs() {
        const response = await this.get(`/trading-pairs/bonds/`);
        console.log('Bond pairs:', response.data);
        return response.data;
    }

    /**
     * Get real-time market data for a trading pair
     * @param {number} pairId - Trading pair ID
     */
    async getMarketData(pairId) {
        const response = await this.get(`/trading-pairs/${pairId}/market_data/`);
        console.log('Market data:', response.data);
        return response.data;
    }

    /**
     * Get status of all markets
     */
    async getMarketStatus() {
        const response = await this.get(`/trading-pairs/market_status/`);
        console.log('Market status:', response.data);
        return response.data;
    }

    /**
     * Get all asset categories
     */
    async getAssetCategories() {
        const response = await this.get(`/asset-categories/`);
        console.log('Asset categories:', response.data);
        return response.data;
    }

    // ===== ORDERS =====

    /**
     * Create a new order
     * @param {Object} orderData - Order details
     */
    async createOrder(orderData) {
        const response = await this.post(`/orders/`, orderData);
        console.log('Order created:', response.data);
        return response.data;
    }

    /**
     * Get all orders with optional filters
     * @param {Object} params - Query parameters (status, trading_pair, side)
     * @param {string} params.status - Order status (open, closed, all)
     * @param {number} params.trading_pair - Trading pair ID
     * @param {string} params.side - Order side (buy, sell)
     */
    async getOrders(params) {
        const response = await this.get(`/orders/`, params);
        console.log('Orders:', response.data);
        return response.data;
    }

    /**
     * Get a single order by ID
     * @param {number} orderId - Order ID
     */
    async getOrder(orderId) {
        const response = await this.get(`/orders/${orderId}/`);
        console.log('Order:', response.data);
        return response.data;
    }

    /**
     * Cancel an open order
     * @param {number} orderId - Order ID
     */
    async cancelOrder(orderId) {
        const response = await this.post(`/orders/${orderId}/cancel/`);
        console.log('Order cancelled:', response.data);
        return response.data;
    }
    /**
     * Cancel an open order
    
    //  */
    // async tradingSummary() {
    //     const response = await this.get(`/orders/trading_summary`);
    //     console.log('Trading summary:', response.data);
    //     return response.data;
    // }

    // ===== POSITIONS =====

    /**
     * Get all positions for the current user
     * @param {Object} params - Query parameters (status, side)
     * @param {string} params.status - Position status (open, closed, all)
     * @param {string} params.side - Position side (buy, sell)
     */
    async getPositions(params) {
        const response = await this.get(`/positions/`, { params });
        console.log('Positions:', response.data);
        return response.data;
    }

    /**
     * get position summary
     */
    async getPositionSummary() {
        const response = await this.get(`/positions/summary/`);
        console.log('Position summary:', response.data);
        return response.data;
    }
    /**
     * close position summary
     */
    async closePositionSummary(positionId) {
        const response = await this.post(`/positions/${positionId}/close/`);
        console.log('Position summary:', response.data);
        return response.data;
    }

    /**
     * Get a single position by ID
     * @param {number} positionId - Position ID
     */
    async getPosition(positionId) {
        const response = await this.get(`/positions/${positionId}/`);
        console.log('Position:', response.data);
        return response.data;
    }

    /**
     * Close a position
     * @param {number} positionId - Position ID
     */
    async closePosition(positionId) {
        const response = await this.post(`/positions/${positionId}/close/`);
        console.log('Position closed:', response.data);
        return response.data;
    }

    /**
     * Update stop loss for a position
     * @param {number} positionId - Position ID
     * @param {number} stopLoss - Stop loss price
     */
    async updateStopLoss(positionId, stopLoss) {  // ✅ FIXED: Was updateStopAndLoss
        const response = await this.post(`/positions/${positionId}/update_stop_loss/`, {
            stop_loss: stopLoss
        });
        console.log('Stop loss updated:', response.data);
        return response.data;
    }


    /**
     * Update take profit for a position
     * @param {number} positionId - Position ID
     * @param {number} takeProfit - Take profit price
     */
    async updateTakeProfit(positionId, takeProfit) {
        const response = await this.post(`/positions/${positionId}/update_take_profit/`, {
            take_profit: takeProfit
        });
        console.log('Take profit updated:', response.data);
        return response.data;
    }

    // ===== TRADES =====

    /**
     * Get trade history for the current user
     * @param {object} params - Query parameters (status, trading_pair, side)
     */
    async getTrades(params) {
        const response = await this.get(`/trades/`, params);
        console.log('Trades:', response.data);
        return response.data;
    }
    /**
     * Get trade history statistics
     */
    async getTradeStatistics() {
        const response = await this.get(`/trades/statistics/`);
        console.log('Trade statistics:', response.data);
        return response.data;
    }


    /**
     * Get trading summary
     */
    async getTradingSummary() {
    const response = await this.get(`/orders/trading_summary/`);  
    return response.data;
}


    // ===== TRADING FLOW HELPERS =====

    /**
     * Buy with market order
     * @param {number} tradingPairId - Trading pair ID
     * @param {number} quantity - Quantity to buy
     * @param {number} leverage - Leverage to use
     */
    async marketBuy(tradingPairId, quantity, leverage = 1) {
        return this.createOrder({
            trading_pair: tradingPairId,
            order_type: 'market',
            side: 'buy',
            quantity: quantity,
            leverage: leverage.toString()
        });
    }

    /**
     * Sell with market order
     * @param {number} tradingPairId - Trading pair ID
     * @param {number} quantity - Quantity to sell
     * @param {number} leverage - Leverage to use
     */
    async marketSell(tradingPairId, quantity, leverage = 1) {
        return this.createOrder({
            trading_pair: tradingPairId,
            order_type: 'market',
            side: 'sell',
            quantity: quantity,
            leverage: leverage.toString()
        });
    }

    /**
     * Close LONG position (sell)
     * @param {number} tradingPairId - Trading pair ID
     * @param {number} quantity - Quantity to sell  
     */
    async closeLongPosition(tradingPairId, quantity) {
        return this.createOrder({
            trading_pair: tradingPairId,
            order_type: 'market', 
            side: 'sell',
            quantity: quantity
        });
    }

    /**
     * Close SHORT position (buy back)
     * @param {number} tradingPairId - Trading pair ID
     * @param {number} quantity - Quantity to buy
     */
    async closeShortPosition(tradingPairId, quantity) {
        return this.createOrder({   
            trading_pair: tradingPairId,
            order_type: 'market',
            side: 'buy',  // Buying to cover short position
            quantity: quantity
        });
    }

    /**
     * Buy with limit order
     * @param {number} tradingPairId - Trading pair ID
     * @param {number} quantity - Quantity to buy
     * @param {number} price - Limit price
     */
    async limitBuy(tradingPairId, quantity, price) {
        return this.createOrder({
            trading_pair: tradingPairId,
            order_type: 'limit',
            side: 'buy',
            quantity: quantity,
            price: price
        });
    }

    /**
     * Sell with limit order
     * @param {number} tradingPairId - Trading pair ID
     * @param {number} quantity - Quantity to sell
     * @param {number} price - Limit price
     */
    async limitSell(tradingPairId, quantity, price) {
        return this.createOrder({
            trading_pair: tradingPairId,
            order_type: 'limit',
            side: 'sell',
            quantity: quantity,
            price: price
        });
    }

    /**
     * Set stop loss
     * @param {number} tradingPairId - Trading pair ID
     * @param {number} quantity - Quantity
     * @param {number} stopPrice - Stop price
     */
    async setStopLoss(tradingPairId, quantity, stopPrice) {
        return this.createOrder({
            trading_pair: tradingPairId,
            order_type: 'stop_loss',
            side: 'sell',
            quantity: quantity,
            stop_price: stopPrice
        });
    }

    /**
     * Set take profit
     * @param {number} tradingPairId - Trading pair ID
     * @param {number} quantity - Quantity
     * @param {number} takeProfitPrice - Take profit price
     */
    async setTakeProfit(tradingPairId, quantity, takeProfitPrice) {
        return this.createOrder({
            trading_pair: tradingPairId,
            order_type: 'take_profit',
            side: 'sell',
            quantity: quantity,
            price: takeProfitPrice
        });
    }

    /**
     * Cancel all open orders
     */
    async cancelAllOpenOrders() {
        const response = await this.getOrders({ status: 'open' });
        const orders = response.results || response;
        
        const cancelPromises = orders.map(order => this.cancelOrder(order.id));
        return Promise.all(cancelPromises);
    }

    /**
     * Close all positions
     */
    async closeAllPositions() {
        const response = await this.getPositions();
        const positions = response.results || response;
        
        const closePromises = positions.map(position => this.closePosition(position.id));
        return Promise.all(closePromises);
    }


    // Account

    /**
     * Get account balance
     */
    async getAccountBalance() {
        const response = await this.get(`/accounts/balance/`);
        console.log('Account Balance:', response.data);
        return response.data;
    }

    /**
     * Transfer from deposit to trading balance
     * @param {number} amount - Amount to transfer
     */
    async transferToTrading(amount) {
        const response = await this.post(`/accounts/transfer_to_trading/`, { amount });
        console.log('Transfer to trading:', response.data);
        return response.data;
    }
    /**
     * Transfer from deposit to investment balance
     * @param {number} amount - Amount to transfer
     */
    async transferToInvestment(amount) {
        const response = await this.post(`/accounts/transfer_to_investment/`, { amount });
        console.log('Transfer to investment:', response.data);
        return response.data;
    }
    /**
     * Transfer from trading to deposit balance
     * @param {number} amount - Amount to transfer
     */
    async transferFromTrading(amount) {
        const response = await this.post(`/accounts/transfer_from_trading/`, { amount });
        console.log('Transfer from trading:', response.data);
        return response.data;
    }
    /**
     * Transfer from investment to deposit balance
     * @param {number} amount - Amount to transfer
     */
    async transferFromInvestment(amount) {
        const response = await this.post(`/accounts/transfer_from_investment/`, { amount });
        console.log('Transfer from investment:', response.data);
        return response.data;
    }

    // ===== TRANSACTIONS =====

    /**
     * Get user transactions
     * @param {Object} params - Query parameters (trading_pair, transaction_type, balance_type, status)
     * @param {string} params.trading_pair - Trading pair ID
     * @param {string} params.transaction_type - Transaction type (e.g., 'deposit', 'position_open')
     * @param {string} params.balance_type - Balance type (e.g., 'deposit', 'trading', 'investment')
     * @param {string} params.status - Transaction status (e.g., 'pending', 'completed', 'failed')
     */
    async getTransactions(params = {}) {
        const response = await this.get('/transactions/', { params });
        console.log('Transactions:', response.data);
        return response.data;
    }

    /**
     * Get a single transaction by ID
     * @param {number} transactionId - Transaction ID
     */
    async getTransaction(transactionId) {
        const response = await this.get(`/transactions/${transactionId}/`);
        console.log('Transaction:', response.data);
        return response.data;
    }

    /**
     * Get transaction statistics
     */
    async getTransactionStatistics() {
        const response = await this.get('/transactions/statistics/');
        console.log('Transaction statistics:', response.data);
        return response.data;
    }

    /**
     * Get transactions by type
     * @param {string} transactionType - Transaction type (e.g., 'deposit', 'position_open')
     */
    async getTransactionsByType(transactionType) {
        const response = await this.get('/transactions/', { transaction_type: transactionType });
        console.log(`${transactionType} transactions:`, response.data);
        return response.data;
    }

    /**
     * Get transactions by date range
     * @param {string} startDate - Start date (YYYY-MM-DD)
     * @param {string} endDate - End date (YYYY-MM-DD)
     */
    async getTransactionsByDateRange(startDate, endDate) {
        const response = await this.get('/transactions/', {
            start_date: startDate,
            end_date: endDate
        });
        console.log('Transactions in date range:', response.data);
        return response.data;
    }

    /**
     * Get transactions for a specific trading pair
     * @param {number} tradingPairId - Trading pair ID
     */
    async getTransactionsForPair(tradingPairId) {
        const response = await this.get('/transactions/', { trading_pair: tradingPairId });
        console.log(`Transactions for pair ${tradingPairId}:`, response.data);
        return response.data;
    }

    /**
     * Export transactions as CSV
     * @param {Object} params - Query parameters for filtering transactions to export
     */
    async exportTransactions(params = {}) {
        // Note: This returns CSV data, not JSON
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `/transactions/export/?${queryString}` : '/transactions/export/';
        
        // Create a download link
        const fullUrl = `${this.baseURL}${url}`;
        const link = document.createElement('a');
        link.href = fullUrl;
        link.download = 'transactions.csv';
        link.click();
        
        console.log('Transaction export initiated');
    }

    /**
     * Get recent transactions summary
     * @returns {Promise} Last 10 transactions and total count
     */
    async getTransactionsSummary() {
        const response = await this.get('/transactions/summary/');
        console.log('Transaction summary:', response.data);
        return response.data;
    }

    // =====================================================
    // TRADERS
    // =====================================================

    /**
     * Get all available traders
     * @param {Object} params - Query parameters
     * @param {string} params.search - Search query
     * @param {string} params.ordering - Sort field
     * @param {number} params.risk_score - Filter by risk score
     * @returns {Promise}
     */
     async getTraders(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString 
            ? `/traders/?${queryString}`
            : '/traders/';
        
        const response = await this.get(url);
        console.log('Traders:', response.data);
        return response.data;
    }


    /**
     * Get specific trader details
     * @param {number} traderId 
     * @returns {Promise}
     */
    async getTrader(traderId) {
        const response = await this.get(`/traders/${traderId}/`);
        console.log('Trader:', response.data);
        return response.data;
    }

    /**
     * Get the top performing traders based on a metric.
     * Maps to: GET /traders/top_performers/?metric=profit_percentage&limit=10
     * @param {string} [metric='profit_percentage'] - The performance metric to sort by.
     * @param {number} [limit=10] - The number of traders to return.
     * @returns {Promise}
     */
    async getTopPerformers(metric = 'profit_percentage', limit = 10) {
        const response = await this.get(`/traders/top_performers/`, { metric, limit });
        console.log('Top Performers:', response.data);
        return response.data;
    }
    
    // --- Trader Self-Management Endpoints (Current User) ---
    
    /**
     * Check if the current user is an active trader.
     * Maps to: GET /traders/check_trader_status/
     * @returns {Promise}
     */
    async checkTraderStatus() {
        const response = await this.get('/traders/check_trader_status/');
        console.log('Trader Status:', response.data);
        return response.data;
    }

    /**
     * Activate the current user's trader account.
     * Maps to: POST /traders/activate_trader/
     * @param {Object} data - Activation details (display_name, risk_score, minimum_investment).
     * @returns {Promise}
     */
    async activateTrader(data) {
        const response = await this.post('/traders/activate_trader/', data);
        console.log('Trader Activated:', response.data);
        return response.data;
    }
    
    /**
     * Update the current user's trader settings.
     * Maps to: PUT /traders/update_trader/
     * @param {Object} data - Updated settings (display_name, bio, risk_score, minimum_investment).
     * @returns {Promise}
     */
    async updateTraderSettings(data) {
        // Use PUT for full replacement or PATCH if your backend accepts it for this action
        const response = await this.put('/traders/update_trader/', data);
        console.log('Trader Settings Updated:', response.data);
        return response.data;
    }

    /**
     * Deactivate the current user's trader account.
     * Maps to: POST /traders/deactivate_trader/
     * @returns {Promise}
     */
    async deactivateTrader() {
        // This is a POST action, but sends no body data
        const response = await this.post('/traders/deactivate_trader/'); 
        console.log('Trader Deactivated:', response.data);
        return response.data;
    }
    /**
     * Deactivate the current user's trader account.
     * Maps to: POST /traders/deactivate_trader/
     * @returns {Promise}
     */
    async reactivateTrader() {
        // This is a POST action, but sends no body data
        const response = await this.post('/traders/reactivate_trader/'); 
        console.log('Trader Reactivated:', response.data);
        return response.data;
    }


    /**
     * Get trader statistics
     * @param {number} traderId 
     * @returns {Promise}
     */
    async getTraderStatistics(traderId) {
        const response = await this.get(`/traders/${traderId}/statistics/`);
        console.log('Trader statistics:', response.data);
        return response.data;
    }

    /**
     * Get top performing traders
     * @param {string} metric - Metric to sort by (profit, profit_percentage, win_rate, followers)
     * @param {number} limit - Number of traders to return
     * @returns {Promise}
     */
    async getTopTraders(metric = 'profit_percentage', limit = 10) {
        const response = await this.get(`/traders/top_performers/?metric=${metric}&limit=${limit}`);
        console.log('Top traders:', response.data);
        return response.data;
    }

    // =====================================================
    // SUBSCRIPTIONS (FOLLOWING TRADERS)
    // =====================================================

    /**
     * Get user's active subscriptions
     * @returns {Promise}
     */
    async getMySubscriptions(params = {}) {
        const response = await this.get('/subscriptions/', { params });
        console.log('Subscriptions:', response.data);
        return response.data;
    }

    /**
     * Follow a trader (create subscription)
     * @param {Object} data - Subscription data
     * @param {number} data.trader - Trader ID
     * @param {string} data.sizing_mode - 'proportional' or 'fixed'
     * @param {number} data.copy_percentage - Percentage to copy (if proportional)
     * @param {number} data.fixed_amount_per_trade - Fixed amount (if fixed mode)
     * @param {string} data.execution_mode - 'auto' or 'manual'
     * @param {number} data.max_position_size - Max position size (optional)
     * @param {number} data.stop_loss_percentage - Stop loss % (optional)
     * @returns {Promise}
     */
    async followTrader(data) {
        const response = await this.post('/subscriptions/', data);
        console.log('Subscription created:', response.data);
        return response.data;
    }

    /**
     * Update subscription settings
     * @param {number} subscriptionId 
     * @param {Object} data - Updated settings
     * @returns {Promise}
     */
    async updateSubscription(subscriptionId, data) {
        const response = await this.patch(`/subscriptions/${subscriptionId}/`, data);
        console.log('Subscription updated:', response.data);
        return response.data;
    }

    /**
     * Unfollow a trader (delete subscription)
     * @param {number} subscriptionId 
     * @returns {Promise}
     */
    async unfollowTrader(subscriptionId) {
        const response = await this.delete(`/subscriptions/${subscriptionId}/`);
        console.log('Subscription deleted:', response.data);
        return response.data;
    }

    /**
     * Toggle subscription active status
     * @param {number} subscriptionId 
     * @returns {Promise}
     */
    async toggleSubscription(subscriptionId) {
        const response = await this.post(`/subscriptions/${subscriptionId}/toggle_active/`);
        console.log('Subscription toggled:', response.data);
        return response.data;
    }

    /**
     * Get subscription performance
     * @returns {Promise}
     */
    async getPerformance() {
        const response = await this.get('/subscriptions/performance/');
        console.log('Subscription performance:', response.data);
        return response.data;
    }

    /**
     * Get trade history for specific subscription
     * @param {number} subscriptionId 
     * @returns {Promise}
     */
    async getSubscriptionTrades(subscriptionId) {
        const response = await this.get(`/subscriptions/${subscriptionId}/trade_history/`);
        console.log('Subscription trades:', response.data);
        return response.data;
    }
    

    // =====================================================
    // COPIED TRADES
    // =====================================================

    /**
     * Get all copied trades
     * @param {Object} params - Query parameters
     * @param {string} params.status - Filter by status
     * @param {number} params.subscription - Filter by subscription
     * @returns {Promise}
     */
    async getCopiedTrades(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString 
            ? `/copied-trades/?${queryString}`
            : '/copied-trades/';
        
        const response = await this.get(url);
        console.log('Copied trades:', response.data);
        return response.data;
    }

    /**
     * Get pending trades (for manual execution mode)
     * @returns {Promise}
     */
    async getPendingTrades() {
        const response = await this.get('/copied-trades/pending/');
        console.log('Pending trades:', response.data);
        return response.data;
    }

    /**
     * Approve a pending trade
     * @param {number} tradeId 
     * @returns {Promise}
     */
    async approveTrade(tradeId) {
        const response = await this.post(`/copied-trades/${tradeId}/approve/`);
        console.log('Trade approved:', response.data);
        return response.data;
    }

    /**
     * Reject a pending trade
     * @param {number} tradeId 
     * @returns {Promise}
     */
    async rejectTrade(tradeId) {
        const response = await this.post(`/copied-trades/${tradeId}/reject/`);
        console.log('Trade rejected:', response.data);
        return response.data;
    }

    // =====================================================
    // UTILITY FUNCTIONS
    // =====================================================

    /**
     * Check if user is following a trader
     * @param {number} traderId 
     * @returns {Promise<boolean>}
     */
    async isFollowing(traderId) {
        try {
            const response = await this.getMySubscriptions({ trader: traderId });
            console.log('Subscriptions:', response.data);
            return response.data.some(sub => sub.trader === traderId && sub.is_active);
        } catch (error) {
            console.error('Error checking follow status:', error);
            return false;
        }
    }

    /**
     * Get subscription by trader ID
     * @param {number} traderId 
     * @returns {Promise<Object|null>}
     */
    async getSubscriptionByTrader(traderId) {
        const response = await this.getMySubscriptions({ trader: traderId });
        console.log('Subscriptions:', response.data);
        return response.data.find(sub => sub.trader === traderId) || null;
    }

    /**
    * Search traders by query
    * @param {string} query - Search query
    * @returns {Promise}
    */
    async searchTraders(query) {
        const params = { search: query };
        return this.getTraders(params);  
    }


        /**
     * Validate subscription settings before submission
     * @param {Object} settings - Subscription settings to validate
     * @returns {Object} Validation result with { valid: boolean, errors: string[] }
     */
    validateSubscriptionSettings(settings) {
        const errors = [];
        
        // Validate sizing mode
        if (!settings.sizing_mode) {
            errors.push('Sizing mode is required');
        }
        
        // Validate proportional mode
        if (settings.sizing_mode === 'proportional') {
            if (!settings.copy_percentage) {
                errors.push('Copy percentage is required for proportional mode');
            } else if (settings.copy_percentage <= 0 || settings.copy_percentage > 100) {
                errors.push('Copy percentage must be between 0 and 100');
            }
        }
        
        // Validate fixed mode
        if (settings.sizing_mode === 'fixed') {
            if (!settings.fixed_amount_per_trade) {
                errors.push('Fixed amount per trade is required for fixed mode');
            } else if (settings.fixed_amount_per_trade <= 0) {
                errors.push('Fixed amount must be greater than 0');
            }
        }
        
        // Validate execution mode
        if (!settings.execution_mode) {
            errors.push('Execution mode is required');
        }
        
        // Validate optional fields
        if (settings.max_position_size && settings.max_position_size <= 0) {
            errors.push('Max position size must be greater than 0');
        }
        
        if (settings.stop_loss_percentage) {
            if (settings.stop_loss_percentage <= 0 || settings.stop_loss_percentage > 100) {
                errors.push('Stop loss percentage must be between 0 and 100');
            }
        }
        
        return {
            valid: errors.length === 0,
            errors: errors
        };
    }



    // Message helper using Swal style
    showMessage(message, type = 'success') {
        if (typeof Swal !== "undefined") {
            const config = {
                text: message,
                toast: true,
                position: "top-end",
                showConfirmButton: false,
                timer: 5000,
                
                // Custom class for wide toast
                customClass: {
                    container: 'swal2-wide-toast' 
                }
            };

            switch(type) {
                case 'success':
                    Swal.fire({
                        icon: "success",
                        title: "Success!",
                        ...config
                    });
                    break;
                case 'danger':
                case 'error':
                    Swal.fire({
                        icon: "error",
                        title: "Error",
                        ...config
                    });
                    break;
                case 'warning':
                    Swal.fire({
                        icon: "warning",
                        title: "Warning",
                        ...config
                    });
                    break;
                case 'info':
                    Swal.fire({
                        icon: "info",
                        title: "Info",
                        ...config
                    });
                    break;
                default:
                    Swal.fire(config);
            }
        } else {
            // Fallback to custom notification system
            // Create message container if it doesn't exist
            if (!document.getElementById('api-messages')) {
                const container = document.createElement('div');
                container.id = 'api-messages';
                container.className = 'fixed top-4 right-4 max-w-sm w-full z-[999]';
                document.body.prepend(container);
            }

            const alertClass = type === 'success' ? 'bg-green-500' :
                type === 'danger' ? 'bg-red-500' :
                type === 'error' ? 'bg-red-500' :
                type === 'warning' ? 'bg-yellow-500' : 'bg-blue-500';

            const alertDiv = document.createElement('div');
            alertDiv.className = `${alertClass} text-white p-4 rounded-lg shadow-lg mb-2 transition-all duration-300`;
            alertDiv.innerHTML = `
                <div class="flex justify-between items-center">
                    <span>${message}</span>
                    <button type="button" class="text-white hover:text-gray-200">
                        <i data-lucide="x" class="w-4 h-4"></i>
                    </button>
                </div>
            `;

            alertDiv.querySelector('button').addEventListener('click', () => {
                alertDiv.remove();
            });

            document.getElementById('api-messages').appendChild(alertDiv);

            // Refresh Lucide icons
            if (window.lucide) {
                lucide.createIcons();
            }

            // Auto-dismiss after 5 seconds
            setTimeout(() => {
                alertDiv.remove();
            }, 10000);
        }
    }
}

// Create global instance and load tokens immediately
window.APIClient = new APIConnector();

// Backward compatibility wrapper
window.API = {
    baseUrl: '/api/v1',

    request(method, endpoint, data = null) {
        return APIClient.client.request({
            method,
            url: endpoint,
            data
        });
    },

    get(endpoint) {
        return APIClient.get(endpoint).then(res => res.data);
    },

    post(endpoint, data) {
        return APIClient.post(endpoint, data).then(res => res.data);
    },

    patch(endpoint, data) {
        return APIClient.patch(endpoint, data).then(res => res.data);
    },

    delete(endpoint) {
        return APIClient.delete(endpoint).then(res => res.data);
    },

    showMessage(message, type = 'success') {
        APIClient.showMessage(message, type);
    },

    handleError(error) {
        const message = error.message || 'An error occurred';
        APIClient.showMessage(message, 'danger');
    }
};
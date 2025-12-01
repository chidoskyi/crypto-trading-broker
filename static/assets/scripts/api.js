// assets/scripts/api.js - Axios version with secure token handling
console.log('APIConnector loaded');
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
                'Content-Type': 'application/json',
            },
            withCredentials: true,
        });

        this.setupInterceptors();
    }

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

    // CSRF Token function
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

    // Setup request/response interceptors
    setupInterceptors() {
        // Request interceptor
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

                return config;
            },
            (error) => {
                return Promise.reject(error);
            }
        );

        // Response interceptor
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

    // Error handling
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
                    .filter(([key]) => key !== 'success') // Exclude success field
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

    // Public API methods
    async get(endpoint, config = {}) {
        return this.client.get(endpoint, config);
    }

    async post(endpoint, data = null, config = {}) {
        return this.client.post(endpoint, data, config);
    }

    async put(endpoint, data = null, config = {}) {
        return this.client.put(endpoint, data, config);
    }

    async patch(endpoint, data = null, config = {}) {
        return this.client.patch(endpoint, data, config);
    }

    async delete(endpoint, config = {}) {
        return this.client.delete(endpoint, config);
    }

    // Check if user is authenticated
    isAuthenticated() {
        return !!this.accessToken;
    }
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

    async logout() {
        try {
            await this.post('/auth/logout/');
        } finally {
            this.clearTokens();
        }
    }

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

async requestPasswordReset(email) {
    try {
        console.log('🔐 [Password Reset] Requesting reset for email:', email);
        
        // Send email directly as the value, not wrapped in an object
        const response = await this.post('/auth/password/reset/', { email: email });
        
        console.log('✅ [Password Reset] Request successful:', response.data);
        return response.data;
    } catch (error) {
        console.error('❌ [Password Reset] Request failed:', error);
        console.log('📊 [Password Reset] Error details:', {
            status: error.status,
            statusText: error.statusText,
            response: error.response
        });
        throw error;
    }
}

    async passwordResetValidate(uidb64, token) {

        const response = await this.get(`/auth/password/reset/validate/${uidb64}/${token}/`);
        return response.data;
    }

    async resetPassword(uidb64, token, data) {
        const response = await this.post(`/auth/password/reset/confirm/${uidb64}/${token}/`, data);
        return response.data;
    }



    // Check if user is authenticated
    isAuthenticated() {
        return !!this.accessToken;
    }

    // Get user profile
    async getProfile() {
        const response = await this.get('/auth/profile/');
        return response.data;
    }

    // Complete profile (for profile completion page)
    async completeProfile(formData) {
        try {
            const response = await this.post('/auth/profile/complete/', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });
            return response;
        } catch (error) {
            throw error;
        }
    }

    // ===== DEPOSITS =====
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



    // Message helper
    showMessage(message, type = 'success') {
        // Create message container if it doesn't exist
        if (!document.getElementById('api-messages')) {
            const container = document.createElement('div');
            container.id = 'api-messages';
            container.className = 'fixed top-4 right-4 max-w-sm w-full z-[999]';
            document.body.prepend(container);
        }

        const alertClass = type === 'success' ? 'bg-green-500' :
            type === 'danger' ? 'bg-red-500' :
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
        }, 5000);
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
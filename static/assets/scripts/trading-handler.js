console.log('Trading handler loaded');

// class TradingApi {
//     constructor(apiClient) {
//         this.api = apiClient;
//     }

//     // Delegate methods to base API client
//     async get(endpoint, params) {
//         return this.api.get(endpoint, { params });
//     }

//     async post(endpoint, data) {
//         return this.api.post(endpoint, data);
//     }

//     async delete(endpoint) {
//         return this.api.delete(endpoint);
//     }

//     // ===== TRADING PAIRS =====

//     /**
//      * Get all trading pairs with optional filters
//      * @param {Object} params - Query parameters (search, market_type, asset_category, etc.)
//      */
//     async getTradingPairs(params) {
//         const response = await this.get(`/trading-pairs/`, params);
//         console.log('Trading pairs:', response.data);
//         return response.data;
//     }

//     /**
//      * Get a single trading pair by ID
//      * @param {number} pairId - Trading pair ID
//      */
//     async getTradingPair(pairId) {
//         const response = await this.get(`/trading-pairs/${pairId}/`);
//         console.log('Trading pair:', response.data);
//         return response.data;
//     }

//     /**
//      * Get trading pairs grouped by category
//      */
//     async getTradingPairsByCategory() {
//         const response = await this.get(`/trading-pairs/by_category/`);
//         console.log('Pairs by category:', response.data);
//         return response.data;
//     }

//     /**
//      * Get cryptocurrency pairs
//      */
//     async getCryptoPairs() {
//         const response = await this.get(`/trading-pairs/crypto/`);
//         console.log('Crypto pairs:', response.data);
//         return response.data;
//     }

//     /**
//      * Get stock pairs
//      */
//     async getStockPairs() {
//         const response = await this.get(`/trading-pairs/stocks/`);
//         console.log('Stock pairs:', response.data);
//         return response.data;
//     }

//     /**
//      * Get forex pairs
//      */
//     async getForexPairs() {
//         const response = await this.get(`/trading-pairs/forex/`);
//         console.log('Forex pairs:', response.data);
//         return response.data;
//     }

//     /**
//      * Get commodity pairs
//      */
//     async getCommodityPairs() {
//         const response = await this.get(`/trading-pairs/commodities/`);
//         console.log('Commodity pairs:', response.data);
//         return response.data;
//     }

//     /**
//      * Get bond pairs
//      */
//     async getBondPairs() {
//         const response = await this.get(`/trading-pairs/bonds/`);
//         console.log('Bond pairs:', response.data);
//         return response.data;
//     }

//     /**
//      * Get real-time market data for a trading pair
//      * @param {number} pairId - Trading pair ID
//      */
//     async getMarketData(pairId) {
//         const response = await this.get(`/trading-pairs/${pairId}/market_data/`);
//         console.log('Market data:', response.data);
//         return response.data;
//     }

//     /**
//      * Get status of all markets
//      */
//     async getMarketStatus() {
//         const response = await this.get(`/trading-pairs/market_status/`);
//         console.log('Market status:', response.data);
//         return response.data;
//     }

//     // ===== ORDERS =====

//     /**
//      * Create a new order
//      * @param {Object} orderData - Order details
//      */
//     async createOrder(orderData) {
//         const response = await this.post(`/orders/`, orderData);
//         console.log('Order created:', response.data);
//         return response.data;
//     }

//     /**
//      * Get all orders with optional filters
//      * @param {Object} params - Query parameters (status, trading_pair, side)
//      */
//     async getOrders(params) {
//         const response = await this.get(`/orders/`, params);
//         console.log('Orders:', response.data);
//         return response.data;
//     }

//     /**
//      * Get a single order by ID
//      * @param {number} orderId - Order ID
//      */
//     async getOrder(orderId) {
//         const response = await this.get(`/orders/${orderId}/`);
//         console.log('Order:', response.data);
//         return response.data;
//     }

//     /**
//      * Cancel an open order
//      * @param {number} orderId - Order ID
//      */
//     async cancelOrder(orderId) {
//         const response = await this.post(`/orders/${orderId}/cancel/`);
//         console.log('Order cancelled:', response.data);
//         return response.data;
//     }

//     // ===== POSITIONS =====

//     /**
//      * Get all positions for the current user
//      */
//     async getPositions() {
//         const response = await this.get(`/positions/`);
//         console.log('Positions:', response.data);
//         return response.data;
//     }

//     /**
//      * Get a single position by ID
//      * @param {number} positionId - Position ID
//      */
//     async getPosition(positionId) {
//         const response = await this.get(`/positions/${positionId}/`);
//         console.log('Position:', response.data);
//         return response.data;
//     }

//     /**
//      * Close a position
//      * @param {number} positionId - Position ID
//      */
//     async closePosition(positionId) {
//         const response = await this.post(`/positions/${positionId}/close/`);
//         console.log('Position closed:', response.data);
//         return response.data;
//     }

//     // ===== TRADES =====

//     /**
//      * Get trade history for the current user
//      */
//     async getTrades() {
//         const response = await this.get(`/trades/`);
//         console.log('Trades:', response.data);
//         return response.data;
//     }

//     // ===== ASSET CATEGORIES =====

//     /**
//      * Get all asset categories
//      */
//     async getAssetCategories() {
//         const response = await this.get(`/asset-categories/`);
//         console.log('Asset categories:', response.data);
//         return response.data;
//     }

//     // ===== TRADING FLOW HELPERS =====

//     /**
//      * Buy with market order
//      * @param {number} tradingPairId - Trading pair ID
//      * @param {number} quantity - Quantity to buy
//      */
//     async marketBuy(tradingPairId, quantity) {
//         return this.createOrder({
//             trading_pair: tradingPairId,
//             order_type: 'market',
//             side: 'buy',
//             quantity: quantity
//         });
//     }

//     /**
//      * Sell with market order
//      * @param {number} tradingPairId - Trading pair ID
//      * @param {number} quantity - Quantity to sell
//      */
//     async marketSell(tradingPairId, quantity) {
//         return this.createOrder({
//             trading_pair: tradingPairId,
//             order_type: 'market',
//             side: 'sell',
//             quantity: quantity
//         });
//     }

//     /**
//      * Buy with limit order
//      * @param {number} tradingPairId - Trading pair ID
//      * @param {number} quantity - Quantity to buy
//      * @param {number} price - Limit price
//      */
//     async limitBuy(tradingPairId, quantity, price) {
//         return this.createOrder({
//             trading_pair: tradingPairId,
//             order_type: 'limit',
//             side: 'buy',
//             quantity: quantity,
//             price: price
//         });
//     }

//     /**
//      * Sell with limit order
//      * @param {number} tradingPairId - Trading pair ID
//      * @param {number} quantity - Quantity to sell
//      * @param {number} price - Limit price
//      */
//     async limitSell(tradingPairId, quantity, price) {
//         return this.createOrder({
//             trading_pair: tradingPairId,
//             order_type: 'limit',
//             side: 'sell',
//             quantity: quantity,
//             price: price
//         });
//     }

//     /**
//      * Set stop loss
//      * @param {number} tradingPairId - Trading pair ID
//      * @param {number} quantity - Quantity
//      * @param {number} stopPrice - Stop price
//      */
//     async setStopLoss(tradingPairId, quantity, stopPrice) {
//         return this.createOrder({
//             trading_pair: tradingPairId,
//             order_type: 'stop_loss',
//             side: 'sell',
//             quantity: quantity,
//             stop_price: stopPrice
//         });
//     }

//     /**
//      * Set take profit
//      * @param {number} tradingPairId - Trading pair ID
//      * @param {number} quantity - Quantity
//      * @param {number} takeProfitPrice - Take profit price
//      */
//     async setTakeProfit(tradingPairId, quantity, takeProfitPrice) {
//         return this.createOrder({
//             trading_pair: tradingPairId,
//             order_type: 'take_profit',
//             side: 'sell',
//             quantity: quantity,
//             price: takeProfitPrice
//         });
//     }

//     /**
//      * Cancel all open orders
//      */
//     async cancelAllOpenOrders() {
//         const response = await this.getOrders({ status: 'open' });
//         const orders = response.results || response;
        
//         const cancelPromises = orders.map(order => this.cancelOrder(order.id));
//         return Promise.all(cancelPromises);
//     }

//     /**
//      * Close all positions
//      */
//     async closeAllPositions() {
//         const response = await this.getPositions();
//         const positions = response.results || response;
        
//         const closePromises = positions.map(position => this.closePosition(position.id));
//         return Promise.all(closePromises);
//     }
// }

// // Initialize with window.APIClient reference
// if (window.APIClient) {
//     window.TradingAPI = new TradingApi(window.APIClient);
//     console.log('✅ TradingAPI initialized successfully');
// } else {
//     console.error('❌ APIClient not loaded. Make sure api.js is loaded before trading-handler.js');
// }

// ===== ALPINE.JS INTEGRATION =====

/**
 * Enhanced trading markets component with API integration
 */
// Updated JavaScript function - Key changes marked with comments
function tradingMarkets() {
    return {
        instruments: [],
        selectedType: 'all',
        searchQuery: '',
        loading: true,
        error: null,
        marketStatus: {},
        autoRefresh: true,
        refreshInterval: null,
        lastRefresh: null,

        async init() {
            console.log('Initializing trading markets...');
            
            await this.loadTradingPairs();
            await this.loadMarketStatus();
            
            this.$nextTick(() => {
                if (typeof lucide !== 'undefined') {
                    lucide.createIcons();
                }
            });

            if (this.autoRefresh) {
                this.startAutoRefresh();
            }
        },

        async loadTradingPairs() {
            this.loading = true;
            this.error = null;

            try {
                // Load all pairs with large page size to ensure we get bonds too
                const response = await APIClient.getTradingPairs({ page_size: 1000 });

                // Handle paginated response or direct array
                const pairs = response.results || response;

                if (!Array.isArray(pairs)) {
                    throw new Error('Invalid response format from API');
                }

                // Transform API data to match template format
                this.instruments = pairs.map(pair => ({
                    id: pair.id,
                    symbol: pair.symbol,
                    name: pair.name || pair.symbol,
                    // Normalize market_type to lowercase
                    type: (pair.market_type || '').toLowerCase(),
                    // Handle both percentage_change_24h and percent_change_24h
                    percent_change_24h: pair.percentage_change_24h || pair.percent_change_24h || 0,
                    price_change_24h: pair.price_change_24h || '0',
                    change: pair.price_change_24h || 0,
                    volume_24h: pair.volume_24h || '0',
                    volume: pair.volume_24h || '0',
                    market_cap: pair.market_cap || 0,
                    logo_url: pair.logo_url || null,
                    logo: pair.logo_url || null,
                    last_price: pair.last_price || '0',
                    price: pair.last_price || '0',
                    ...pair
                }));

                console.log(`✅ Loaded ${this.instruments.length} instruments`);
                
                // Log market type distribution
                const typeCount = {};
                this.instruments.forEach(inst => {
                    typeCount[inst.type] = (typeCount[inst.type] || 0) + 1;
                });
                console.log('📊 Market type distribution:', typeCount);
                console.log('📋 All unique types:', [...new Set(this.instruments.map(i => i.type))]);
                
                // Check if bonds are missing
                if (!typeCount.bond && !typeCount.bonds) {
                    console.warn('⚠️ WARNING: No bonds found in API response!');
                    console.log('🔍 Checking pagination - you might need to increase page_size or check backend filters');
                }
                
            } catch (error) {
                console.error('❌ Failed to load trading pairs:', error);
                this.error = error.message;
                this.showNotification('error', 'Failed to load trading pairs. Please refresh the page.');
            } finally {
                this.loading = false;
            }
        },

        async loadMarketStatus() {
            try {
                this.marketStatus = await APIClient.getMarketStatus();
                console.log('✅ Market status loaded:', this.marketStatus);
            } catch (error) {
                console.error('❌ Failed to load market status:', error);
            }
        },

        startAutoRefresh() {
            if (this.refreshInterval) {
                clearInterval(this.refreshInterval);
            }

            this.refreshInterval = setInterval(() => {
                if (document.visibilityState === 'visible') {
                    this.loadTradingPairs();
                }
            }, 30000);
        },

        stopAutoRefresh() {
            if (this.refreshInterval) {
                clearInterval(this.refreshInterval);
                this.refreshInterval = null;
            }
        },

        changeType(type) {
            console.log('Changing type to:', type);
            this.selectedType = type;
            // Re-initialize lucide icons after DOM updates
            this.$nextTick(() => {
                if (typeof lucide !== 'undefined') {
                    lucide.createIcons();
                }
            });
        },

        async forceRefresh() {
            console.log('Force refreshing data...');
            await this.loadTradingPairs();
            this.lastRefresh = new Date();
            this.showNotification('success', 'Data refreshed successfully');
        },

        goToTrade(instrumentId) {
            window.location.href = `/dashboard/trading-view/${instrumentId}/`;
        },

        showNotification(type, message) {
            console.log(`[${type.toUpperCase()}] ${message}`);
            
            if (window.Alpine && window.Alpine.store) {
                window.Alpine.store('notifications')?.add(type, message);
            }
        },

        get totalInstruments() {
            return this.instruments.length;
        },

        get filteredInstruments() {
            let filtered = this.instruments;

            if (this.searchQuery) {
                const query = this.searchQuery.toLowerCase();
                filtered = filtered.filter(instrument =>
                    instrument.name.toLowerCase().includes(query) ||
                    instrument.symbol.toLowerCase().includes(query)
                );
            }

            return filtered;
        },

        get groupedInstruments() {
            const grouped = {};
            
            this.filteredInstruments.forEach(instrument => {
                // Apply type filter
                if (this.selectedType !== 'all' && instrument.type !== this.selectedType) {
                    return;
                }
                
                if (!grouped[instrument.type]) {
                    grouped[instrument.type] = [];
                }
                grouped[instrument.type].push(instrument);
            });

            // Sort each group by volume
            Object.keys(grouped).forEach(type => {
                grouped[type].sort((a, b) => 
                    parseFloat(b.volume || 0) - parseFloat(a.volume || 0)
                );
            });

            return grouped;
        },

        getTypeDisplayName(type) {
            const names = {
                crypto: 'Cryptocurrency',
                stock: 'Stocks',
                forex: 'Foreign Exchange',
                commodity: 'Commodities',
                bond: 'Bonds',
                bonds: 'Bonds'  // Handle plural too
            };
            return names[type] || type;
        },

        formatPrice(price) {
            if (!price || price === '0') return 'N/A';
            const num = parseFloat(price);
            if (isNaN(num)) return 'N/A';
            if (num >= 1) {
                return '$' + num.toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2
                });
            } else {
                return '$' + num.toFixed(6);
            }
        },

        formatPercentage(percent) {
            if (percent === null || percent === undefined) return '0.00%';
            const num = parseFloat(percent);
            if (isNaN(num)) return '0.00%';
            return (num >= 0 ? '+' : '') + num.toFixed(2) + '%';
        },

        formatChange(change) {
            if (change === null || change === undefined) return '$0.00';
            const num = parseFloat(change);
            if (isNaN(num)) return '$0.00';
            return (num >= 0 ? '+$' : '-$') + Math.abs(num).toFixed(2);
        },

        formatVolume(volume) {
            if (!volume || volume === '0.00' || volume === '0') return 'N/A';
            const num = parseFloat(volume);
            if (isNaN(num) || num === 0) return 'N/A';
            if (num >= 1e9) {
                return '$' + (num / 1e9).toFixed(1) + 'B';
            } else if (num >= 1e6) {
                return '$' + (num / 1e6).toFixed(1) + 'M';
            } else if (num >= 1e3) {
                return '$' + (num / 1e3).toFixed(1) + 'K';
            }
            return '$' + num.toLocaleString();
        },

        destroy() {
            this.stopAutoRefresh();
        }
    };
}
// Re-initialize icons after Alpine updates
document.addEventListener('alpine:updated', () => {
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (window.tradingMarketsComponent) {
        window.tradingMarketsComponent.destroy();
    }
});

// Export for global use
window.tradingMarkets = tradingMarkets;
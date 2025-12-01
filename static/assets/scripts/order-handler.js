console.log('OrderHandler.js loaded');

// OrderHandler.js - Comprehensive trading order management
class OrderHandler {
    constructor() {
        this.currentPositions = [];
        this.openOrders = [];
        this.accountBalance = null;
    }

    /**
     * Initialize the order handler with account data
     */
    async initialize() {
        try {
            console.log('🔄 Initializing OrderHandler...');
            
            // Check if APIClient is available
            if (typeof APIClient === 'undefined') {
                throw new Error('APIClient is not loaded. Make sure api-client.js is included before order-handler.js');
            }
            
            // Load account balance and positions
            await this.loadAccountData();
            await this.loadOpenPositions();
            await this.loadOpenOrders();
            
            console.log('✅ OrderHandler initialized successfully');
            return true;
        } catch (error) {
            console.error('❌ OrderHandler initialization failed:', error);
            throw error;
        }
    }

    /**
     * Load account balance and trading summary
     */
    async loadAccountData() {
        try {
            const summary = await APIClient.getTradingSummary();
            this.accountBalance = summary.account;
            console.log('💰 Account loaded:', {
                tradingBalance: this.accountBalance.trading_balance,
                availableBalance: this.accountBalance.available_trading_balance
            });
            return summary;
        } catch (error) {
            console.error('Failed to load account data:', error);
            throw error;
        }
    }

    /**
     * Load current open positions
     */
    async loadOpenPositions() {
        try {
            const positions = await APIClient.getPositions(
                { status: 'open' }
                
            );
            this.currentPositions = positions.results || positions;
            console.log(`📊 Loaded ${this.currentPositions.length} open positions`);
            return this.currentPositions;
        } catch (error) {
            console.error('Failed to load positions:', error);
            throw error;
        }
    }




    /**
     * Load current open orders
     */
    async loadOpenOrders() {
        try {
            const orders = await APIClient.getOrders(
                { status: 'open, pending, partially_filled' },
                { trading_pair: this.tradingPairId },
                { side: 'buy, sell' }
            );
            this.openOrders = orders.results || orders;
            console.log(`📋 Loaded ${this.openOrders.length} open orders`);
            return this.openOrders;
        } catch (error) {
            console.error('Failed to load open orders:', error);
            throw error;
        }
    }

    /**
     * Complete trading flow with market analysis and order placement
     * @param {Object} config - Trading configuration
     */
    async executeTradingFlow(config = {}) {
        const {
            tradingPairId,
            investmentAmount,
            leverage = 1,
            orderType = 'market',
            side = 'buy',
            price = null,
            stopPrice = null,
            expiration = null,
            stopLossPercent = 5,
            takeProfitPercent = 10,
            autoSetRiskManagement = true
        } = config;

        try {
            console.log('🎯 Starting automated trading flow...');

            // Step 1: Validate inputs
            if (!tradingPairId) {
                throw new Error('Trading pair ID is required');
            }
            if (!investmentAmount || investmentAmount <= 0) {
                throw new Error('Valid investment amount is required');
            }

            // Step 2: Check account status
            console.log('1. Checking account status...');
            await this.validateAccountBalance(investmentAmount);

            // Step 3: Get market data and analyze
            console.log('2. Analyzing market...');
            const marketAnalysis = await this.analyzeMarket(tradingPairId);
            
            if (!marketAnalysis.isTradable) {
                console.warn(`⚠️ Market warning: ${marketAnalysis.reason}`);
                // Don't throw error, just warn - let user decide
            }

            // Step 4: Calculate position sizing
            console.log('3. Calculating position size...');
            const currentPrice = price || marketAnalysis.currentPrice;
            const positionSize = this.calculatePositionSize(
                investmentAmount, 
                leverage, 
                currentPrice
            );

            // Step 5: Build order data
            const orderData = {
                trading_pair: tradingPairId,
                order_type: orderType,
                side: side,
                quantity: parseFloat(positionSize.quantity),
                leverage: leverage.toString() // Keep as string to match Django CharField
            };

            // Add price for limit orders
            if (orderType === 'limit' && price) {
                orderData.price = parseFloat(price);
            }
            
            // Add stop_price for stop orders
            if ((orderType === 'stop_loss' || orderType === 'stop' || orderType === 'take_profit') && stopPrice) {
                orderData.stop_price = parseFloat(stopPrice);
            }
            
            // Add expiration if provided
            if (expiration) {
                orderData.expiration_type = expiration;
            }

            // Step 6: Execute order using APIClient.createOrder
            console.log('4. Executing order...');
            console.log('Order data:', orderData);
            
            const result = await APIClient.createOrder(orderData);
            
            console.log(`✅ Order executed:`, result.order);

            // Step 7: Set risk management if order filled and enabled
            let riskManagement = null;
            if (autoSetRiskManagement && result.position && result.order.status === 'filled') {
                console.log('5. Setting risk management...');
                riskManagement = await this.setRiskManagement({
                    positionId: result.position.id,
                    entryPrice: parseFloat(result.order.average_price),
                    quantity: parseFloat(result.order.quantity),
                    stopLossPercent,
                    takeProfitPercent,
                    side: side
                });
            }

            // Step 8: Reload data
            await this.loadOpenPositions();
            await this.loadAccountData();

            console.log('✅ Trading flow completed successfully!');
            
            return {
                success: true,
                order: result.order,
                position: result.position,
                riskManagement,
                accountBalance: result.account_balance
            };

        } catch (error) {
            console.error('❌ Trading flow failed:', error);
            
            return {
                success: false,
                error: error.message || 'Unknown error occurred',
                step: 'trading_flow'
            };
        }
    }

    /**
     * Validate if account has sufficient balance
     */
    async validateAccountBalance(requiredAmount) {
        if (!this.accountBalance) {
            await this.loadAccountData();
        }

        const availableBalance = parseFloat(this.accountBalance.available_trading_balance);
        
        if (availableBalance < requiredAmount) {
            throw new Error(
                `Insufficient trading balance. Required: $${requiredAmount}, Available: $${availableBalance.toFixed(2)}`
            );
        }

        console.log(`✅ Sufficient balance: $${availableBalance.toFixed(2)}`);
        return true;
    }

    /**
     * Analyze market conditions for trading
     */
    async analyzeMarket(tradingPairId) {
        try {
            // Get current ticker data
            const ticker = await APIClient.getTickerData(tradingPairId);
            const currentPrice = parseFloat(ticker.ticker.last_price);
            
            // Simple market analysis
            const analysis = {
                currentPrice,
                priceChange24h: parseFloat(ticker.ticker.price_change_24h) || 0,
                volume24h: parseFloat(ticker.ticker.volume_24h) || 0,
                isTradable: true,
                reason: '',
                recommendation: 'NEUTRAL'
            };

            // Basic trading filters
            if (Math.abs(analysis.priceChange24h) > 15) {
                analysis.isTradable = false;
                analysis.reason = '24h price change too high (>15%)';
                analysis.recommendation = 'AVOID';
            } else if (analysis.volume24h > 0 && analysis.volume24h < 1000000) {
                analysis.isTradable = false;
                analysis.reason = 'Trading volume too low';
                analysis.recommendation = 'AVOID';
            } else if (analysis.priceChange24h > 5) {
                analysis.recommendation = 'BULLISH';
            } else if (analysis.priceChange24h < -5) {
                analysis.recommendation = 'BEARISH';
            }

            console.log(`📈 Market analysis: ${analysis.recommendation} - ${analysis.reason || 'Favorable conditions'}`);
            return analysis;

        } catch (error) {
            console.error('Market analysis failed:', error);
            // Return basic analysis with current price if available
            return {
                currentPrice: 0,
                priceChange24h: 0,
                volume24h: 0,
                isTradable: true,
                reason: 'Could not fetch market data',
                recommendation: 'NEUTRAL'
            };
        }
    }

    /**
     * Calculate position size based on risk management
     */
    calculatePositionSize(investmentAmount, leverage, currentPrice) {
        const totalValue = investmentAmount * leverage;
        const quantity = totalValue / currentPrice;
        
        console.log(`📏 Position size: ${quantity.toFixed(8)} units ($${totalValue} value with ${leverage}x leverage)`);
        
        return {
            investmentAmount,
            leverage,
            totalValue,
            quantity: quantity.toFixed(8),
            pricePerUnit: currentPrice
        };
    }

    /**
     * Set stop loss and take profit for a position
     */
    async setRiskManagement(riskConfig) {
        const {
            positionId,
            entryPrice,
            quantity,
            stopLossPercent = 5,
            takeProfitPercent = 10,
            side = 'buy'
        } = riskConfig;

        try {
            if (!positionId) {
                console.warn('⚠️ No position ID provided, skipping risk management setup');
                return null;
            }

            // Calculate stop loss and take profit based on position side
            let stopLossPrice, takeProfitPrice;
            
            if (side === 'buy' || side === 'long') {
                // Long position: SL below, TP above
                stopLossPrice = entryPrice * (1 - stopLossPercent / 100);
                takeProfitPrice = entryPrice * (1 + takeProfitPercent / 100);
            } else {
                // Short position: SL above, TP below
                stopLossPrice = entryPrice * (1 + stopLossPercent / 100);
                takeProfitPrice = entryPrice * (1 - takeProfitPercent / 100);
            }

            console.log(`🛡️ Setting risk management for ${side} position:`);
            console.log(`   Entry Price: $${entryPrice.toFixed(2)}`);
            console.log(`   Stop Loss: $${stopLossPrice.toFixed(2)} (${stopLossPercent}%)`);
            console.log(`   Take Profit: $${takeProfitPrice.toFixed(2)} (${takeProfitPercent}%)`);

            // Update position with stop loss and take profit
            await APIClient.updateStopLoss(positionId, stopLossPrice);
            await APIClient.updateTakeProfit(positionId, takeProfitPrice);

            return {
                stopLoss: stopLossPrice,
                takeProfit: takeProfitPrice,
                stopLossPercent,
                takeProfitPercent,
                riskToReward: (takeProfitPercent / stopLossPercent).toFixed(2)
            };

        } catch (error) {
            console.error('Risk management setup failed:', error);
            throw error;
        }
    }

    /**
     * Close all open positions
     */
    async closeAllPositions() {
        try {
            console.log('🔄 Closing all open positions...');
            await this.loadOpenPositions();

            if (this.currentPositions.length === 0) {
                console.log('No positions to close');
                return {
                    total: 0,
                    successful: 0,
                    failed: 0,
                    results: []
                };
            }

            const closePromises = this.currentPositions.map(position => 
                APIClient.closePosition(position.id)
            );

            const results = await Promise.allSettled(closePromises);
            
            // Count successes and failures
            const successful = results.filter(r => r.status === 'fulfilled').length;
            const failed = results.filter(r => r.status === 'rejected').length;

            console.log(`✅ Closed ${successful} positions, ${failed} failed`);
            
            // Reload positions
            await this.loadOpenPositions();
            
            return {
                total: this.currentPositions.length,
                successful,
                failed,
                results
            };

        } catch (error) {
            console.error('Failed to close all positions:', error);
            throw error;
        }
    }

    /**
     * Cancel all open orders
     */
    async cancelAllOrders() {
        try {
            console.log('🔄 Canceling all open orders...');
            await this.loadOpenOrders();

            if (this.openOrders.length === 0) {
                console.log('No orders to cancel');
                return {
                    total: 0,
                    successful: 0,
                    failed: 0,
                    results: []
                };
            }

            const cancelPromises = this.openOrders.map(order => 
                APIClient.cancelOrder(order.id)
            );

            const results = await Promise.allSettled(cancelPromises);
            
            // Count successes and failures
            const successful = results.filter(r => r.status === 'fulfilled').length;
            const failed = results.filter(r => r.status === 'rejected').length;

            console.log(`✅ Canceled ${successful} orders, ${failed} failed`);
            
            // Reload orders
            await this.loadOpenOrders();
            
            return {
                total: this.openOrders.length,
                successful,
                failed,
                results
            };

        } catch (error) {
            console.error('Failed to cancel all orders:', error);
            throw error;
        }
    }

    /**
     * Get trading performance statistics
     */
    async getPerformanceStats() {
        try {
            const trades = await APIClient.getTrades();
            const statistics = await APIClient.getTradeStatistics();
            
            return {
                totalTrades: statistics.total_trades,
                totalVolume: statistics.total_volume,
                winRate: this.calculateWinRate(trades),
                totalProfit: statistics.total_profit || 0,
                averageTrade: statistics.avg_trade_size
            };
        } catch (error) {
            console.error('Failed to get performance stats:', error);
            throw error;
        }
    }

    /**
     * Calculate win rate from trades
     */
    calculateWinRate(trades) {
        const tradeList = trades.results || trades;
        if (!tradeList.length) return 0;
        
        const winningTrades = tradeList.filter(trade => 
            parseFloat(trade.realized_pnl || 0) > 0
        );
        
        return (winningTrades.length / tradeList.length * 100).toFixed(2);
    }
}

// Export for use in browser
window.OrderHandler = OrderHandler;

console.log('✅ OrderHandler class loaded and ready to use');
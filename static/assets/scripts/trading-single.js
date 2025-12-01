console.log('Trading View loaded');

function tradingSingle() {
    return {
        instrument: null,
        orderType: 'Buy',
        tradeType: 'market',
        amount: '',
        price: '',
        loading: false,
        loadingData: true,
        activeTab: 'open',
        error: null,
        instrumentId: null,
        userBalance: 0,
        
        // Dynamic configuration options (will be populated from API)
        leverageOptions: [],
        expirationOptions: [],
        orderTypeOptions: [],
        
        selectedLeverage: '10',
        selectedExpiration: '1h',
        
        // Transfer functionality
        showTransferModal: false,
        transferDirection: 'deposit-to-trading',
        transferAmount: '',
        transferLoading: false,
        depositBalance: 0,
        tradingBalance: 0,

        // OrderHandler instance
        orderHandler: null,
        
        // Trading positions and orders
        openPositions: [],
        closedPositions: [],
        openOrders: [],
        closedOrders: [],

        // Add these new properties for transactions
        transactions: [],
        transactionsByPairId: [],
        loadingTransactions: false,
        
        // Update activeTab to include 'transactions'
        activeTab: 'open', // 'open', 'closed', 'transactions'

        async init() {
            // Load trading configuration FIRST
            await this.loadTradingConfig();
            
            // Initialize OrderHandler
            this.orderHandler = new OrderHandler();
            await this.orderHandler.initialize();

            // Get instrument ID from URL
            const pathParts = window.location.pathname.split('/');
            const idIndex = pathParts.indexOf('trading-view') + 1;
            this.instrumentId = pathParts[idIndex];

            console.log('Loading instrument ID:', this.instrumentId);

            if (!this.instrumentId) {
                this.error = 'Invalid instrument ID';
                this.loadingData = false;
                return;
            }

            // Load instrument data
            await this.loadInstrumentData();
            
            // Load user balances
            await this.loadUserBalances();
            
            // Load positions and orders for this instrument
            await this.loadPositionsAndOrders();

            // Load transactions for this instrument
            await this.loadTransactions();

            // Initialize TradingView chart after data is loaded
            this.$nextTick(() => {
                if (this.instrument) {
                    this.initTradingViewChart();
                }
                
                // Initialize Lucide icons
                if (typeof lucide !== 'undefined') {
                    lucide.createIcons();
                }
            });
        },

        async loadTradingConfig() {
            try {
                console.log('🔄 Loading trading configuration...');
                
                // Fetch configuration from API
                const config = await APIClient.getTradingConfig();
                
                this.leverageOptions = config.leverage_options || [];
                this.expirationOptions = config.expiration_options || [];
                this.orderTypeOptions = config.order_type_options || [];
                
                // Set sensible defaults
                if (this.leverageOptions.length > 0) {
                    this.selectedLeverage = this.findDefaultLeverage();
                }
                
                if (this.expirationOptions.length > 0) {
                    this.selectedExpiration = this.findDefaultExpiration();
                }
                
                console.log('✅ Trading configuration loaded:', {
                    leverage: this.leverageOptions.length,
                    expiration: this.expirationOptions.length,
                    orderTypes: this.orderTypeOptions.length
                });
                
            } catch (error) {
                console.error('❌ Failed to load trading config:', error);
                await this.loadFallbackConfig();
            }
        },

        async loadFallbackConfig() {
            console.log('🔄 Loading fallback configuration...');
            
            // Fallback configuration that matches your Django model
            this.leverageOptions = [
                { value: '1', label: '1x (No Leverage)' },
                { value: '2', label: '2x' },
                { value: '3', label: '3x' },
                { value: '5', label: '5x' },
                { value: '10', label: '10x' },
                { value: '20', label: '20x' },
                { value: '25', label: '25x' },
                { value: '50', label: '50x' },
                { value: '75', label: '75x' },
                { value: '100', label: '100x' },
                { value: '125', label: '125x' }
            ];
            
            this.expirationOptions = [
                { value: '60s', label: '60 Seconds' },
                { value: '2m', label: '2 Minutes' },
                { value: '5m', label: '5 Minutes' },
                { value: '10m', label: '10 Minutes' },
                { value: '15m', label: '15 Minutes' },
                { value: '30m', label: '30 Minutes' },
                { value: '1h', label: '1 Hour' },
                { value: '2h', label: '2 Hours' },
                { value: '4h', label: '4 Hours' },
                { value: '1d', label: '1 Day (End of Day)' },
                { value: '1w', label: '1 Week (End of Week)' },
                { value: '1M', label: '1 Month (End of Month)' },
                { value: 'gtc', label: 'Good Till Cancelled' }
            ];
            
            this.orderTypeOptions = [
                { value: 'market', label: 'Market Order', description: 'Execute immediately at current price' },
                { value: 'limit', label: 'Limit Order', description: 'Execute only at specified price or better' },
                { value: 'stop_loss', label: 'Stop Loss Order', description: 'Trigger when price reaches stop level' },
                { value: 'take_profit', label: 'Take Profit Order', description: 'Take profit at specified price level' }
            ];
            
            this.selectedLeverage = '10';
            this.selectedExpiration = '1h';
        },

        findDefaultLeverage() {
            // Prefer 10x if available, otherwise first option
            const preferred = this.leverageOptions.find(opt => opt.value === '10');
            return preferred ? preferred.value : (this.leverageOptions[0]?.value || '1');
        },

        findDefaultExpiration() {
            // Prefer 1h if available, otherwise first option
            const preferred = this.expirationOptions.find(opt => opt.value === '1h');
            return preferred ? preferred.value : (this.expirationOptions[0]?.value || '60s');
        },

        // Helper method to get order type description
        getOrderTypeDescription(orderType) {
            const option = this.orderTypeOptions.find(opt => opt.value === orderType);
            return option ? option.description : '';
        },

        getTradingViewSymbol() {
            if (!this.instrument) return 'BTCUSD'; // Default symbol without exchange prefix is not ideal

            const symbol = this.instrument.symbol;
            const type = this.instrument.market_type || this.instrument.type;
            
            if (type === 'crypto' || type === 'CRYPTO') {
                const symbolMap = {
                    'BTC/USD': 'COINBASE:BTCUSD',
                    'BTC/USDT': 'BINANCE:BTCUSDT',
                    'ETH/USD': 'COINBASE:ETHUSD',
                    'ETH/USDT': 'BINANCE:ETHUSDT',
                    'XRP/USD': 'COINBASE:XRPUSD',
                    'LTC/USD': 'COINBASE:LTCUSD',
                    'BCH/USD': 'COINBASE:BCHUSD',
                    'ADA/USD': 'COINBASE:ADAUSD',
                };
                
                if (symbolMap[symbol]) return symbolMap[symbol];
                
                // Fallback for unmapped crypto symbols
                const cleanSymbol = symbol.replace('/', '');
                return 'COINBASE:' + cleanSymbol; 
                
            } else if (type === 'stock' || type === 'STOCK') {
                const symbolMap = {
                    'AAPL': 'NASDAQ:AAPL',
                    'TSLA': 'NASDAQ:TSLA',
                    'GOOGL': 'NASDAQ:GOOGL',
                    'AMZN': 'NASDAQ:AMZN',
                    'MSFT': 'NASDAQ:MSFT',
                    'IBM': 'NYSE:IBM',
                    'JPM': 'NYSE:JPM',
                    'T':   'NYSE:T',
                    'CRM': 'NYSE:CRM',
                    'META': 'NASDAQ:META', // Added META for completeness
                };
                
                const cleanSymbol = symbol.split('/')[0];

                // 1. Check the explicit map first
                if (symbolMap[cleanSymbol]) return symbolMap[cleanSymbol];

                // 2. Use the new helper function for the fallback exchange
                // Assumes 'this.determineStockExchange' is available in the component context
                const exchange = this.determineStockExchange ? this.determineStockExchange(cleanSymbol) : 'NASDAQ';
                return exchange + ':' + cleanSymbol;
                
            } else if (type === 'forex' || type === 'FOREX') {
                return 'FX:' + symbol.replace('/', '');
                
            } else if (type === 'commodity' || type === 'COMMODITY') {
                const symbolMap = {
                    'GOLD': 'TVC:GOLD',
                    'SILVER': 'TVC:SILVER',
                    'OIL': 'TVC:USOIL',
                    'XAU/USD': 'TVC:GOLD',
                    'XAG/USD': 'TVC:SILVER',
                };
                
                const cleanSymbol = symbol.split('/')[0];
                return symbolMap[cleanSymbol] || symbolMap[symbol] || 'TVC:' + cleanSymbol;
                
            } else if (type === 'bond' || type === 'BOND') {
                // Expanded bond map for better coverage
                const symbolMap = {
                    'US10Y': 'TVC:US10Y',
                    'US30Y': 'TVC:US30Y',
                    'US05Y': 'TVC:US05Y',
                    'US02Y': 'TVC:US02Y',
                    'GERMANY10Y': 'TVC:DE10YDE', // Added
                    'UK10Y': 'TVC:UK10Y',       // Added
                    'JAPAN10Y': 'TVC:JP10YJ',     // Added
                };
                
                const cleanSymbol = symbol.split('/')[0];
                return symbolMap[cleanSymbol] || symbolMap[symbol] || 'TVC:US10Y';
            }

            // Final catch-all fallback (should include an exchange prefix)
            return 'NASDAQ:' + symbol.replace('/', '');
        },

        // New helper function to determine the stock exchange for generic symbols
        determineStockExchange(symbol) {
            // List of common NYSE and NASDAQ stocks (expand this list for better accuracy)
            const nyseStocks = [
                'IBM', 'JPM', 'T', 'CRM', 'V', 'MA', 'WMT', 'JNJ', 'PG', 'XOM',
                'CVX', 'KO', 'PEP', 'DIS', 'BA', 'CAT', 'GE', 'MMM', 'UNH', 'HD',
                'MCD', 'GS', 'AXP', 'TRV', 'UTX', 'DOW', 'RTX', 'HON', 'SPG'
            ];
            
            const nasdaqStocks = [
                'AAPL', 'TSLA', 'GOOGL', 'AMZN', 'MSFT', 'META', 'NFLX', 'NVDA',
                'ADBE', 'CSCO', 'INTC', 'AMD', 'QCOM', 'INTU', 'PYPL', 'SBUX',
                'CMCSA', 'ISRG', 'REGN', 'GILD', 'VRTX', 'BIIB', 'ALGN', 'MNST'
            ];
            
            const cleanSymbol = symbol.toUpperCase(); 

            // 1. Check if the symbol is in a known list
            if (nyseStocks.includes(cleanSymbol)) {
                return 'NYSE';
            } else if (nasdaqStocks.includes(cleanSymbol)) {
                return 'NASDAQ';
            }
            
            // 2. Fallback heuristic (less reliable)
            // NASDAQ symbols are typically 4+ characters, NYSE 1-3
            if (cleanSymbol.length <= 3) {
                return 'NYSE'; 
            } else {
                return 'NASDAQ'; 
            }
        },

        initTradingViewChart() {
            const container = document.getElementById('tradingview_chart');
            if (!container) return;
            
            container.innerHTML = '';

            const symbol = this.getTradingViewSymbol();
            console.log('Initializing TradingView chart for:', symbol);

            try {
                new TradingView.widget({
                    // Core Settings
                    "autosize": true,
                    "symbol": symbol,
                    "interval": "D",
                    "timezone": "Etc/UTC",
                    "theme": "dark",
                    "style": "1", // Candlestick
                    "locale": "en",
                    
                    // Container
                    "container_id": "tradingview_chart",
                    "height": 600,
                    "width": "100%",
                    
                    // THIS IS THE FIX - Set initial visible range
                    "range": "12M", // Show 12 months of data initially
                    
                    // Features
                    "toolbar_bg": "#131722",
                    "enable_publishing": false,
                    "allow_symbol_change": true,
                    "hide_side_toolbar": false,
                    "hide_top_toolbar": false,
                    "save_image": true,
                    "withdateranges": true,
                    "hide_legend": false,
                    
                    // Optional: Add custom timeframe buttons
                    "time_frames": [
                        { text: "1m", resolution: "1", description: "1 Month" },
                        { text: "3m", resolution: "3", description: "3 Months" },
                        { text: "6m", resolution: "6", description: "6 Months" },
                        { text: "1y", resolution: "12", description: "1 Year" },
                        { text: "5y", resolution: "60", description: "5 Years" },
                        { text: "All", resolution: "ALL", description: "All" }
                    ],
                    
                    // Chart Styling
                    "overrides": {
                        "mainSeriesProperties.style": "1", // Ensure candlestick
                        "mainSeriesProperties.showCountdown": true,
                        "paneProperties.background": "#131722",
                        "paneProperties.backgroundType": "solid",
                        "paneProperties.vertGridProperties.color": "#1a1a1a",
                        "paneProperties.horzGridProperties.color": "#1a1a1a"
                    },
                    
                    // Optional: Volume styling
                    "studies_overrides": {
                        "volume.volume.color.0": "#ef5350",
                        "volume.volume.color.1": "#26a69a"
                    }
                });
            } catch (error) {
                console.error('Failed to initialize TradingView chart:', error);
            }
        },

        async loadInstrumentData() {
            this.loadingData = true;
            this.error = null;

            try {
                const response = await APIClient.getTradingPair(this.instrumentId);
                this.instrument = response;
                this.price = this.instrument.last_price || this.instrument.price;

                console.log('✅ Loaded instrument:', this.instrument);
                await this.loadMarketData();

            } catch (error) {
                console.error('❌ Failed to load instrument:', error);
                this.error = 'Failed to load instrument data. Please try again.';
                
                Swal.fire({
                    icon: 'error',
                    title: 'Error Loading Instrument',
                    text: error.message || 'Failed to load instrument data',
                    confirmButtonColor: '#3B82F6'
                });
            } finally {
                this.loadingData = false;
            }
        },

        async loadMarketData() {
            try {
                const marketData = await APIClient.getMarketData(this.instrumentId);
                
                if (marketData) {
                    this.instrument = {
                        ...this.instrument,
                        last_price: marketData.last_price || this.instrument.last_price,
                        price: marketData.last_price || this.instrument.price,
                        high: marketData.high || this.instrument.high,
                        low: marketData.low || this.instrument.low,
                        volume_24h: marketData.volume || this.instrument.volume_24h,
                        percent_change_24h: marketData.percent_change_24h || this.instrument.percent_change_24h,
                        price_change_24h: marketData.price_change_24h || this.instrument.price_change_24h
                    };
                }

                console.log('✅ Market data updated');
            } catch (error) {
                console.warn('⚠️ Could not load real-time market data:', error.message);
            }
        },
        
        // Load positions and orders
        async loadPositionsAndOrders() {
            try {
                // Load all positions
                const positions = await this.orderHandler.loadOpenPositions();
                
                // Filter positions for this instrument
                this.openPositions = positions.filter(pos => 
                    pos.trading_pair === parseInt(this.instrumentId) && 
                    pos.status === 'open'
                );

                // Load all orders
                const orders = await this.orderHandler.loadOpenOrders();
                
                // ✅ FILTER: Only show orders that are actually open/cancellable
                this.openOrders = orders.filter(order => 
                    order.trading_pair === parseInt(this.instrumentId) && 
                    ['open', 'pending', 'partially_filled'].includes(order.status) // Only cancellable statuses
                );

                console.log(`📊 Loaded ${this.openPositions.length} positions and ${this.openOrders.length} open orders for this instrument`);
                
            } catch (error) {
                console.error('Failed to load positions/orders:', error);
            }
        },

        // Helper method to determine if order can be cancelled
        isOrderCancellable(status) {
            const cancellableStatuses = ['open', 'pending', 'partially_filled'];
            return cancellableStatuses.includes(status);
        },

        // Helper method for status badge colors
        getOrderStatusClass(status) {
            const statusClasses = {
                'open': 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
                'pending': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
                'partially_filled': 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
                'filled': 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
                'cancelled': 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400',
                'failed': 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
            };
            return statusClasses[status] || 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400';
        },

        // Add this new method to load transactions
        async loadTransactions() {
            this.loadingTransactions = true;
            
            try {
                const trading_pair_id = parseInt(this.instrumentId);
                console.log(`🔍 Loading transactions for trading pair ID: ${trading_pair_id}`);
                
                // This now works correctly with the fixed getTransactions method
                const response = await APIClient.getTransactions({
                    trading_pair: trading_pair_id
                });
                
                console.log('📊 Raw API response:', response);
                
                // Handle paginated response
                if (response && response.results && Array.isArray(response.results)) {
                    this.transactions = response.results;
                } else if (Array.isArray(response)) {
                    this.transactions = response;
                } else {
                    this.transactions = [];
                }
                
                console.log(`✅ Loaded ${this.transactions.length} transactions for trading pair ${trading_pair_id}`);
                
                if (this.transactions.length === 0) {
                    console.log('ℹ️ No transactions found for this trading pair');
                } else {
                    console.log('📊 Sample transaction:', this.transactions[0]);
                }
                
            } catch (error) {
                console.error('❌ Failed to load transactions:', error);
                this.transactions = [];
            } finally {
                this.loadingTransactions = false;
            }
        },

        // Helper methods for transactions
        getTransactionIcon(transactionType) {
            const icons = {
                'deposit': 'arrow-down-circle',
                'withdrawal': 'arrow-up-circle',
                'transfer_to_trading': 'arrow-right',
                'transfer_from_trading': 'arrow-left',
                'order_fee': 'minus-circle',
                'position_open': 'trending-up',
                'position_close': 'trending-down',
                'profit': 'plus-circle',
                'loss': 'minus-circle',
                'commission': 'percent',
                'refund': 'refresh-cw',
                'bonus': 'gift',
                'adjustment': 'edit'
            };
            return icons[transactionType] || 'circle';
        },

        getTransactionColor(transactionType, amount) {
            // Positive amounts are green, negative are red
            if (parseFloat(amount) > 0) {
                return 'text-green-600 dark:text-green-400';
            } else {
                return 'text-red-600 dark:text-red-400';
            }
        },

        formatTransactionAmount(amount) {
            const num = parseFloat(amount);
            const sign = num >= 0 ? '+' : '';
            return sign + this.formatPrice(Math.abs(num));
        },

        formatDate(dateString) {
            if (!dateString) return 'N/A';
            const date = new Date(dateString);
            return date.toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        },

        // Refresh all data (positions, orders, transactions)
        async refreshAllData() {
            await Promise.all([
                this.loadPositionsAndOrders(),
                this.loadUserBalances(),
                this.loadTransactions(),
            ]);
        },



        formatAmount() {
            if (!this.amount) return '$0.00';
            const amount = parseFloat(this.amount);
            if (isNaN(amount)) return '$0.00';
            return '$' + amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        },

        formatUnits() {
            if (!this.amount || !this.instrument) return '0';
            const amount = parseFloat(this.amount);
            if (isNaN(amount)) return '0';
            
            const price = this.tradeType === 'market' 
                ? (this.instrument.last_price || this.instrument.price)
                : (this.price || this.instrument.last_price || this.instrument.price);
            
            const priceNum = parseFloat(price);
            if (isNaN(priceNum) || priceNum === 0) return '0';
            
            const units = amount / priceNum;
            return units.toLocaleString('en-US', { minimumFractionDigits: 6, maximumFractionDigits: 6 });
        },

        formatPrice(price) {
            if (!price) return '$0.00';
            const num = parseFloat(price);
            if (isNaN(num)) return '$0.00';
            
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

        formatVolume(volume) {
            if (!volume) return 'N/A';
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

        setQuickAmount(percentage) {
            const balance = this.userBalance || 0;
            this.amount = (balance * percentage / 100).toFixed(2);
        },

        async submitOrder() {
            // Validation
            if (!this.amount || this.amount <= 0) {
                Swal.fire({
                    icon: 'error',
                    title: 'Invalid Amount',
                    text: 'Please enter a valid amount to trade.',
                    confirmButtonColor: '#3B82F6'
                });
                return;
            }

            const leverage = this.selectedLeverage;

            if (!leverage) {
                Swal.fire({
                    icon: 'error',
                    title: 'Select Leverage',
                    text: 'Please select a leverage ratio.',
                    confirmButtonColor: '#3B82F6'
                });
                return;
            }

            const total = this.formatAmount();
            const units = this.formatUnits();
            const action = this.orderType.toUpperCase();

            // Show confirmation
            const result = await Swal.fire({
                title: `Confirm ${action} Order`,
                html: `
                    <div class="text-left space-y-2">
                        <p><strong>Instrument:</strong> ${this.instrument.symbol}</p>
                        <p><strong>Action:</strong> ${action}</p>
                        <p><strong>Order Type:</strong> ${this.tradeType.toUpperCase()}</p>
                        <p><strong>Investment Amount:</strong> ${total}</p>
                        <p><strong>Units:</strong> ${units}</p>
                        <p><strong>Leverage:</strong> ${this.getLeverageLabel(leverage)}</p>
                        <p><strong>Expiration:</strong> ${this.getExpirationLabel(this.selectedExpiration)}</p>
                        ${this.tradeType !== 'market' ? `<p><strong>Price:</strong> ${this.formatPrice(this.price)}</p>` : ''}
                    </div>
                `,
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: this.orderType === 'Buy' ? '#10B981' : '#EF4444',
                cancelButtonColor: '#6B7280',
                confirmButtonText: `Yes, ${action}!`,
                cancelButtonText: 'Cancel'
            });

            if (!result.isConfirmed) return;

            this.loading = true;
            Swal.fire({
                title: 'Processing Order...',
                text: 'Please wait while we process your trade.',
                allowOutsideClick: false,
                allowEscapeKey: false,
                showConfirmButton: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });

            try {
                // Build order data using OrderHandler
                const config = {
                    tradingPairId: parseInt(this.instrumentId),
                    investmentAmount: parseFloat(this.amount),
                    leverage: leverage,
                    orderType: this.tradeType,
                    side: this.orderType.toLowerCase(),
                    expiration: this.selectedExpiration, // ✅ ADD THIS LINE
                    autoSetRiskManagement: false
                };

                // Add price for limit/stop orders
                if (this.tradeType === 'limit' && this.price) {
                    config.price = parseFloat(this.price);
                }
                if (this.tradeType === 'stop_loss' && this.price) {
                    config.stopPrice = parseFloat(this.price);
                }
                if (this.tradeType === 'take_profit' && this.price) {
                    config.stopPrice = parseFloat(this.price);
                }

                // Execute order via OrderHandler
                const orderResult = await this.orderHandler.executeTradingFlow(config);

                if (orderResult.success) {
                    await this.loadPositionsAndOrders();
                    await this.loadUserBalances();
                    await this.loadTransactions();

                    Swal.fire({
                        icon: 'success',
                        title: 'Order Placed Successfully!',
                        html: `
                            <div class="text-left space-y-2">
                                <p><strong>Order ID:</strong> #${orderResult.order.id}</p>
                                <p><strong>Type:</strong> ${orderResult.order.order_type.toUpperCase()}</p>
                                <p><strong>Side:</strong> ${orderResult.order.side.toUpperCase()}</p>
                                <p><strong>Status:</strong> ${orderResult.order.status.toUpperCase()}</p>
                                <p><strong>Quantity:</strong> ${parseFloat(orderResult.order.quantity).toFixed(8)}</p>
                                <p><strong>Leverage:</strong> ${orderResult.order.leverage_display || orderResult.order.leverage}</p>
                                <p><strong>Expiration:</strong> ${orderResult.order.expiration_display || orderResult.order.expiration_type}</p>
                                ${orderResult.order.average_price ? `<p><strong>Price:</strong> ${this.formatPrice(orderResult.order.average_price)}</p>` : ''}
                            </div>
                        `,
                        confirmButtonColor: '#3B82F6'
                    });

                    this.amount = '';
                    this.price = '';
                } else {
                    throw new Error(orderResult.error);
                }
            } catch (error) {
                console.error('Order submission failed:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Order Failed',
                    text: error.message || 'Failed to place order. Please try again.',
                    confirmButtonColor: '#3B82F6'
                });
            } finally {
                this.loading = false;
            }
        },

        // Helper to get leverage label
        getLeverageLabel(leverageValue) {
            const option = this.leverageOptions.find(opt => opt.value === leverageValue);
            return option ? option.label : `1:${leverageValue}`;
        },

        // Helper to get expiration label
        getExpirationLabel(expirationValue) {
            const option = this.expirationOptions.find(opt => opt.value === expirationValue);
            return option ? option.label : expirationValue;
        },

        async loadUserBalances() {
            try {
                const response = await APIClient.getAccountBalance();
                
                this.depositBalance = parseFloat(response.balances.deposit_balance || 0);
                this.tradingBalance = parseFloat(response.balances.trading_balance || 0);
                this.userBalance = this.tradingBalance;
                
                console.log('✅ User balances loaded:', {
                    deposit: this.depositBalance,
                    trading: this.tradingBalance
                });
            } catch (error) {
                console.error('❌ Failed to load balances:', error);
                this.depositBalance = 0;
                this.tradingBalance = 0;
                this.userBalance = 0;
            }
        },

        setTransferQuickAmount(percentage) {
            const sourceBalance = this.transferDirection === 'deposit-to-trading' 
                ? this.depositBalance 
                : this.tradingBalance;
            this.transferAmount = (sourceBalance * percentage / 100).toFixed(2);
        },

        async submitTransfer() {
            if (!this.transferAmount || this.transferAmount <= 0) {
                Swal.fire({
                    icon: 'error',
                    title: 'Invalid Amount',
                    text: 'Please enter a valid transfer amount.',
                    confirmButtonColor: '#3B82F6'
                });
                return;
            }

            const sourceBalance = this.transferDirection === 'deposit-to-trading' 
                ? this.depositBalance 
                : this.tradingBalance;

            if (parseFloat(this.transferAmount) > sourceBalance) {
                Swal.fire({
                    icon: 'error',
                    title: 'Insufficient Balance',
                    text: 'Transfer amount exceeds available balance.',
                    confirmButtonColor: '#3B82F6'
                });
                return;
            }

            const direction = this.transferDirection === 'deposit-to-trading' 
                ? 'Deposit to Trading' 
                : 'Trading to Deposit';

            Swal.fire({
                title: 'Confirm Transfer',
                html: `
                    <div class="text-left space-y-2">
                        <p><strong>Direction:</strong> ${direction}</p>
                        <p><strong>Amount:</strong> ${this.formatPrice(this.transferAmount)}</p>
                    </div>
                `,
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#3B82F6',
                cancelButtonColor: '#6B7280',
                confirmButtonText: 'Yes, Transfer!',
                cancelButtonText: 'Cancel'
            }).then(async (result) => {
                if (result.isConfirmed) {
                    this.transferLoading = true;

                    try {
                        let response;
                        
                        if (this.transferDirection === 'deposit-to-trading') {
                            response = await APIClient.transferToTrading(this.transferAmount);
                        } else {
                            response = await APIClient.transferFromTrading(this.transferAmount);
                        }

                        await this.loadUserBalances();

                        this.showTransferModal = false;
                        this.transferAmount = '';

                        Swal.fire({
                            icon: 'success',
                            title: 'Transfer Successful!',
                            text: `${this.formatPrice(this.transferAmount)} has been transferred.`,
                            confirmButtonColor: '#3B82F6'
                        });

                    } catch (error) {
                        console.error('Transfer failed:', error);
                        Swal.fire({
                            icon: 'error',
                            title: 'Transfer Failed',
                            text: error.message || 'Failed to complete the transfer. Please try again.',
                            confirmButtonColor: '#3B82F6'
                        });
                    } finally {
                        this.transferLoading = false;
                    }
                }
            });
        },

        // ===== Advanced Trading Functions =====
        
        async executeAutomatedTrade() {
            try {
                const leverage = this.selectedLeverage;
                
                if (!leverage) {
                    throw new Error('Please select a leverage ratio');
                }
                
                // Build config with all dynamic values
                const config = {
                    tradingPairId: parseInt(this.instrumentId),
                    investmentAmount: parseFloat(this.amount),
                    leverage: leverage,
                    orderType: this.tradeType,
                    side: this.orderType.toLowerCase(),
                    expiration: this.selectedExpiration,
                    stopLossPercent: 5,
                    takeProfitPercent: 10,
                    autoSetRiskManagement: true
                };

                console.log('Selected Leverage:', this.selectedLeverage);
                console.log('Selected Expiration:', this.selectedExpiration);   

                // Add price for limit/stop orders
                if (this.tradeType === 'limit' && this.price) {
                    config.price = parseFloat(this.price);
                }
                if (this.tradeType === 'stop_loss' && this.price) {
                    config.stopPrice = parseFloat(this.price);
                }
                if (this.tradeType === 'take_profit' && this.price) {
                    config.stopPrice = parseFloat(this.price);
                }

                // Execute the trade
                const result = await this.orderHandler.executeTradingFlow(config);

                if (result.success) {
                    await this.loadPositionsAndOrders();
                    await this.loadUserBalances();
                    
                    let successHtml = `
                        <div class="text-left space-y-2">
                            <p><strong>Order Type:</strong> ${result.order.order_type.toUpperCase()}</p>
                            <p><strong>Side:</strong> ${result.order.side.toUpperCase()}</p>
                            <p><strong>Quantity:</strong> ${parseFloat(result.order.quantity).toFixed(8)}</p>
                            <p><strong>Leverage:</strong> ${this.getLeverageLabel(result.order.leverage)}</p>
                            <p><strong>Expiration:</strong> ${result.order.expiration_display || result.order.expiration_type}</p>
                    `;

                    if (result.order.average_price) {
                        successHtml += `<p><strong>Entry Price:</strong> ${this.formatPrice(result.order.average_price)}</p>`;
                    }

                    if (result.riskManagement) {
                        successHtml += `
                            <p><strong>Stop Loss:</strong> ${this.formatPrice(result.riskManagement.stopLoss)}</p>
                            <p><strong>Take Profit:</strong> ${this.formatPrice(result.riskManagement.takeProfit)}</p>
                        `;
                    }

                    successHtml += `</div>`;
                    
                    Swal.fire({
                        icon: 'success',
                        title: 'Trade Executed!',
                        html: successHtml,
                        confirmButtonColor: '#3B82F6'
                    });
                    
                    this.amount = '';
                    this.price = '';
                } else {
                    throw new Error(result.error);
                }
            } catch (error) {
                Swal.fire({
                    icon: 'error',
                    title: 'Trade Failed',
                    text: error.message,
                    confirmButtonColor: '#3B82F6'
                });
            }
        },

        async closePosition(positionId) {
            const result = await Swal.fire({
                title: 'Close Position?',
                text: 'Are you sure you want to close this position?',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#EF4444',
                cancelButtonColor: '#6B7280',
                confirmButtonText: 'Yes, close it!'
            });

            if (result.isConfirmed) {
                try {
                    console.log('🔍 Closing position:', positionId);
                    
                    // ✅ FIX: Use APIClient directly like OrderHandler does
                    await APIClient.closePosition(positionId);
                    console.log('✅ Position closed successfully');
                    
                    await this.loadPositionsAndOrders();
                    await this.loadUserBalances();
                    await this.loadTransactions();
                    
                    Swal.fire({
                        icon: 'success',
                        title: 'Position Closed!',
                        text: 'Your position has been closed successfully.',
                        confirmButtonColor: '#3B82F6'
                    });
                } catch (error) {
                    console.error('❌ Failed to close position:', error);
                    Swal.fire({
                        icon: 'error',
                        title: 'Failed to close position',
                        text: error.response?.data?.message || error.message || 'Please try again.',
                        confirmButtonColor: '#3B82F6'
                    });
                }
            }
        },

        async cancelOrder(orderId) {
            try {
                await this.orderHandler.APIClient.cancelOrder(orderId);
                await this.loadPositionsAndOrders();
                await this.loadUserBalances();
                await this.loadTransactions();            
                Swal.fire({
                    icon: 'success',
                    title: 'Order Cancelled!',
                    confirmButtonColor: '#3B82F6'
                });
            } catch (error) {
                Swal.fire({
                    icon: 'error',
                    title: 'Failed to cancel order',
                    text: error.message,
                    confirmButtonColor: '#3B82F6'
                });
            }
        }
    }   
}

// Re-initialize icons after Alpine updates
document.addEventListener('alpine:updated', () => {
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
});
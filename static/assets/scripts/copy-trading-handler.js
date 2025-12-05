// // static/js/copy-trading-handler.js

// static/js/copy-trading-alpine.js

/**
 * Alpine.js Copy Trading Component
 * Works with copy-trading-api.js and integrates with templates
 */

// Experts Page Component
function copyTradingExperts() {
  return {
    // State
    traders: [],
    filteredTraders: [],
    loading: true,
    searchQuery: "",
    sortBy: "total_followers",

    // User balances
    userBalances: {
      trading: 0,
      deposit: 0,
      total: 0,
    },

    // Modal state
    showFollowModal: false,
    selectedTrader: null,
    submitting: false,

    // Follow form
    followForm: {
      sizing_mode: "proportional",
      copy_percentage: 20,
      fixed_amount_per_trade: "",
      execution_mode: "auto",
      max_position_size: "",
      stop_loss_percentage: "",
    },

    // API Client
    copyAPI: null,

    // Initialize
    async init() {
      console.log("Initializing Copy Trading Experts...");

      // Wait for APIClient to be ready
      await this.waitForAPIClient();

      // Initialize API
      this.copyAPI = APIClient;

      // Load user balances first
      await this.loadUserBalances();

      // Load traders
      await this.loadTraders();

      // Initialize Lucide icons
      this.$nextTick(() => {
        if (typeof lucide !== "undefined") {
          lucide.createIcons();
        }
      });
    },

    // Wait for APIClient to be available
    async waitForAPIClient() {
      let attempts = 0;
      while (typeof window.APIClient === "undefined" && attempts < 50) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        attempts++;
      }

      if (typeof window.APIClient === "undefined") {
        console.error("APIClient not found after waiting");
        this.showError("Failed to initialize API client");
      }
    },

    // ✅ UPDATED - Load user balances from API
    async loadUserBalances() {
      try {
        const response = await this.copyAPI.getAccountBalance();

        this.userBalances = {
          trading: parseFloat(response.balances?.trading_balance || 0),
          deposit: parseFloat(response.balances?.deposit_balance || 0),
          total: parseFloat(response.balances?.total_balance || 0),
        };

        console.log("✅ User balances loaded:", this.userBalances);
        return this.userBalances;
      } catch (error) {
        console.error("❌ Failed to load balances:", error);
        this.userBalances = { trading: 0, deposit: 0, total: 0 };
        return this.userBalances;
      }
    },

    // ✅ UPDATED - Check if user has sufficient balance for trader
    async checkUserBalance(trader) {
      try {
        // First, refresh balances from API
        await this.loadUserBalances();

        const userTradingBalance = this.userBalances.trading;
        const minimumRequired = parseFloat(trader.minimum_investment || 0);
        const needed = Math.max(0, minimumRequired - userTradingBalance);

        return {
          hasSufficient: userTradingBalance >= minimumRequired,
          userBalance: userTradingBalance,
          minimumRequired: minimumRequired,
          needed: needed,
          canTransfer: this.userBalances.deposit >= needed,
        };
      } catch (error) {
        console.error("Balance check failed:", error);
        return {
          hasSufficient: false,
          userBalance: 0,
          minimumRequired: 0,
          needed: 0,
          canTransfer: false,
        };
      }
    },

    // ✅ UPDATED - Enhanced insufficient balance handler
    async handleInsufficientBalance(trader) {
      const balanceCheck = await this.checkUserBalance(trader);

      if (balanceCheck.hasSufficient) {
        return { proceed: true };
      }

      // Show insufficient balance modal
      await this.showBalanceModal(balanceCheck);
      return { proceed: false };
    },

    // ✅ NEW - Show balance modal with options
    showBalanceModal(balanceCheck) {
      return new Promise((resolve) => {
        if (typeof Swal !== "undefined") {
          Swal.fire({
            icon: "warning",
            title: "Insufficient Trading Balance",
            html: `
                            <div class="text-left">
                                <p class="mb-3">This trader requires a minimum trading balance to start copying.</p>
                                <div class="bg-yellow-50 dark:bg-yellow-900/20 p-4 rounded-lg mb-3">
                                    <p class="text-sm mb-2">
                                        <strong>Minimum Required:</strong> $${this.formatCurrency(
                                          balanceCheck.minimumRequired
                                        )}
                                    </p>
                                    <p class="text-sm mb-2">
                                        <strong>Your Trading Balance:</strong> $${this.formatCurrency(
                                          balanceCheck.userBalance
                                        )}
                                    </p>
                                    <p class="text-sm font-semibold text-yellow-700 dark:text-yellow-300">
                                        <strong>Additional Needed:</strong> $${this.formatCurrency(
                                          balanceCheck.needed
                                        )}
                                    </p>
                                    ${
                                      balanceCheck.canTransfer
                                        ? `
                                    <p class="text-sm mt-2 text-green-600 dark:text-green-400">
                                        <i data-lucide="check-circle" class="inline w-4 h-4"></i>
                                        You have $${this.formatCurrency(
                                          this.userBalances.deposit
                                        )} available to transfer
                                    </p>
                                    `
                                        : ""
                                    }
                                </div>
                                
                                <div class="space-y-2">
                                    ${
                                      balanceCheck.canTransfer
                                        ? `
                                    <button id="transfer-btn" 
                                            class="w-full flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 text-white px-4 py-3 rounded-lg transition">
                                        <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                                        Transfer $${this.formatCurrency(
                                          balanceCheck.needed
                                        )} from Deposit
                                    </button>
                                    `
                                        : ""
                                    }
                                    
                                    <button id="deposit-btn" 
                                            class="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-3 rounded-lg transition">
                                        <i data-lucide="plus-circle" class="w-4 h-4"></i>
                                        Deposit More Funds
                                    </button>
                                    
                                    <button id="later-btn" 
                                            class="w-full border border-gray-300 hover:bg-gray-50 text-gray-700 px-4 py-3 rounded-lg transition">
                                        I'll do this later
                                    </button>
                                </div>
                                
                                <p class="text-xs text-gray-500 mt-3 text-center">
                                    Need help? <a href="/support" class="text-blue-600 hover:underline">Contact Support</a>
                                </p>
                            </div>
                        `,
            showConfirmButton: false,
            allowOutsideClick: false,
            allowEscapeKey: true,
            didOpen: () => {
              // Re-init icons in modal
              if (typeof lucide !== "undefined") {
                lucide.createIcons();
              }

              // Handle transfer button
              if (document.getElementById("transfer-btn")) {
                document
                  .getElementById("transfer-btn")
                  .addEventListener("click", async () => {
                    Swal.close();
                    await this.initiateBalanceTransfer(balanceCheck.needed);
                    resolve("transfer");
                  });
              }

              // Handle deposit button
              document
                .getElementById("deposit-btn")
                .addEventListener("click", () => {
                  Swal.close();
                  window.location.href = "/dashboard/deposit";
                  resolve("deposit");
                });

              // Handle later button
              document
                .getElementById("later-btn")
                .addEventListener("click", () => {
                  Swal.close();
                  resolve("later");
                });
            },
          }).then((result) => {
            if (result.dismiss === Swal.DismissReason.escape) {
              resolve("cancelled");
            }
          });
        } else {
          // Fallback to basic alert
          const message = `Minimum balance required: $${this.formatCurrency(
            balanceCheck.minimumRequired
          )}. You need $${this.formatCurrency(balanceCheck.needed)} more.`;
          if (confirm(message + "\n\nGo to deposit page?")) {
            window.location.href = "/dashboard/deposit";
            resolve("deposit");
          } else {
            resolve("cancelled");
          }
        }
      });
    },

    // ✅ NEW - Transfer funds from deposit to trading
    async initiateBalanceTransfer(amount) {
      try {
        if (typeof Swal !== "undefined") {
          Swal.fire({
            title: "Transferring Funds",
            text: "Please wait...",
            allowOutsideClick: false,
            showConfirmButton: false,
            didOpen: () => {
              Swal.showLoading();
            },
          });
        }

        const response = await this.copyAPI.transferBalance({
          amount: amount,
          from: "deposit",
          to: "trading",
          description: "Transfer for copy trading subscription",
        });

        // Update balances
        await this.loadUserBalances();

        if (typeof Swal !== "undefined") {
          Swal.fire({
            icon: "success",
            title: "Transfer Complete!",
            html: `
                            <div class="text-center">
                                <p class="mb-2">Successfully transferred</p>
                                <p class="text-2xl font-bold text-green-600">$${this.formatCurrency(
                                  amount
                                )}</p>
                                <p class="text-sm text-gray-600 mt-2">from Deposit to Trading Balance</p>
                            </div>
                        `,
            timer: 2000,
            showConfirmButton: false,
          });
        }

        return response;
      } catch (error) {
        console.error("Transfer failed:", error);

        if (typeof Swal !== "undefined") {
          Swal.fire({
            icon: "error",
            title: "Transfer Failed",
            text:
              error.response?.data?.error ||
              error.message ||
              "Unable to transfer funds",
            confirmButtonText: "Try Again",
            showCancelButton: true,
            cancelButtonText: "Cancel",
          }).then((result) => {
            if (result.isConfirmed) {
              this.initiateBalanceTransfer(amount);
            }
          });
        }

        throw error;
      }
    },

    // ✅ NEW - Currency formatting helper
    formatCurrency(amount) {
      return Number(amount).toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
    },

    // ✅ UPDATED - Open follow modal with balance check
    async openFollowModal(trader) {
      // Check balance before opening modal
      const balanceCheck = await this.checkUserBalance(trader);

      if (!balanceCheck.hasSufficient) {
        // Show balance modal first
        await this.showBalanceModal(balanceCheck);
        return;
      }

      // If user has sufficient balance, open the follow modal
      this.selectedTrader = trader;
      this.showFollowModal = true;

      // Reset form
      this.followForm = {
        sizing_mode: "proportional",
        copy_percentage: 20,
        fixed_amount_per_trade: "",
        execution_mode: "auto",
        max_position_size: "",
        stop_loss_percentage: "",
      };

      // Re-init icons in modal
      this.$nextTick(() => {
        if (typeof lucide !== "undefined") {
          lucide.createIcons();
        }
      });
    },

    // Helper methods for formatting
    formatCurrency(amount, showSign = false) {
      const num = parseFloat(amount) || 0;
      const sign = showSign && num !== 0 ? (num > 0 ? "+" : "") : "";
      return (
        sign +
        Math.abs(num).toLocaleString("en-US", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })
      );
    },

    formatPercent(amount, showSign = false) {
      const num = parseFloat(amount) || 0;
      const sign = showSign && num !== 0 ? (num > 0 ? "+" : "") : "";
      return sign + num.toFixed(1);
    },

    // Balance checking methods
    hasSufficientBalance(trader) {
      const tradingBalance = this.userBalances.trading;
      const minRequired = parseFloat(trader.minimum_investment || 0);
      return tradingBalance >= minRequired;
    },

    getNeededAmount(trader) {
      const tradingBalance = this.userBalances.trading;
      const minRequired = parseFloat(trader.minimum_investment || 0);
      return Math.max(0, minRequired - tradingBalance);
    },

    // Button state methods
    isTraderAvailable(trader) {
      return trader.is_active && this.hasSufficientBalance(trader);
    },

    getButtonClass(trader) {
      if (!trader.is_active) {
        return "bg-gray-400 cursor-not-allowed";
      }
      return this.hasSufficientBalance(trader)
        ? "bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800"
        : "bg-gradient-to-r from-yellow-600 to-yellow-700 hover:from-yellow-700 hover:to-yellow-800";
    },

    getButtonIcon(trader) {
      if (!trader.is_active) return "pause-circle";
      if (!this.hasSufficientBalance(trader)) return "alert-triangle";
      return "copy";
    },

    getButtonText(trader) {
      if (!trader.is_active) return "Not Accepting Followers";
      if (!this.hasSufficientBalance(trader)) return "Insufficient Balance";
      return "Start Copying";
    },

    // Main handler for follow button
    async handleTraderFollow(trader) {
      if (!trader.is_active) {
        this.showError("This trader is not currently accepting new followers");
        return;
      }

      // Check balance
      const balanceCheck = await this.checkUserBalance(trader);

      if (!balanceCheck.hasSufficient) {
        // Show enhanced balance modal
        await this.showBalanceModal(balanceCheck);
      } else {
        // Open follow modal
        this.openFollowModal(trader);
      }
    },

    // Suggest transfer from deposit
    suggestTransfer(trader) {
      const needed = this.getNeededAmount(trader);
      const canTransfer = this.userBalances.deposit >= needed;

      if (typeof Swal !== "undefined") {
        Swal.fire({
          icon: "question",
          title: "Transfer Funds",
          html: `
                <div class="text-left">
                    <p class="mb-3">You need $${this.formatCurrency(
                      needed
                    )} more to follow this trader.</p>
                    
                    ${
                      canTransfer
                        ? `
                    <div class="bg-green-50 dark:bg-green-900/20 p-3 rounded-lg mb-3">
                        <p class="text-sm font-medium text-green-700 dark:text-green-300">
                            You have sufficient funds in your deposit account!
                        </p>
                        <p class="text-sm text-green-600 dark:text-green-400">
                            Available: $${this.formatCurrency(
                              this.userBalances.deposit
                            )}
                        </p>
                    </div>
                    `
                        : `
                    <div class="bg-yellow-50 dark:bg-yellow-900/20 p-3 rounded-lg mb-3">
                        <p class="text-sm font-medium text-yellow-700 dark:text-yellow-300">
                            Insufficient deposit balance
                        </p>
                        <p class="text-sm text-yellow-600 dark:text-yellow-400">
                            Available: $${this.formatCurrency(
                              this.userBalances.deposit
                            )}
                        </p>
                    </div>
                    `
                    }
                    
                    <p class="text-sm text-gray-600 mb-3">
                        Would you like to transfer funds to your trading account?
                    </p>
                </div>
            `,
          showCancelButton: true,
          confirmButtonText: canTransfer ? "Transfer Now" : "Deposit First",
          cancelButtonText: "Cancel",
          confirmButtonColor: canTransfer ? "#10b981" : "#3b82f6",
        }).then((result) => {
          if (result.isConfirmed) {
            if (canTransfer) {
              this.initiateBalanceTransfer(needed);
            } else {
              window.location.href = "/dashboard/deposit";
            }
          }
        });
      } else {
        // Fallback alert
        const message = canTransfer
          ? `Transfer $${this.formatCurrency(
              needed
            )} from deposit to trading account?`
          : `You need $${this.formatCurrency(
              needed
            )} more. Deposit funds first?`;

        if (confirm(message)) {
          if (canTransfer) {
            this.initiateBalanceTransfer(needed);
          } else {
            window.location.href = "/dashboard/deposit";
          }
        }
      }
    },

    // ✅ UPDATED - Submit follow form with balance verification
    async submitFollow() {
      try {
        this.submitting = true;

        // Final balance check before submitting
        const finalBalanceCheck = await this.checkUserBalance(
          this.selectedTrader
        );
        if (!finalBalanceCheck.hasSufficient) {
          await this.showBalanceModal(finalBalanceCheck);
          this.submitting = false;
          return;
        }

        // Build settings object
        const settings = {
          sizing_mode: this.followForm.sizing_mode,
          execution_mode: this.followForm.execution_mode,
        };

        // Add mode-specific fields
        if (this.followForm.sizing_mode === "proportional") {
          settings.copy_percentage = this.followForm.copy_percentage;
        } else {
          settings.fixed_amount_per_trade =
            this.followForm.fixed_amount_per_trade;
        }

        // Add optional fields
        if (this.followForm.max_position_size) {
          settings.max_position_size = this.followForm.max_position_size;
        }
        if (this.followForm.stop_loss_percentage) {
          settings.stop_loss_percentage = this.followForm.stop_loss_percentage;
        }

        // Validate
        const validation = this.copyAPI.validateSubscriptionSettings(settings);
        if (!validation.valid) {
          this.showError(validation.errors.join(", "));
          return;
        }

        console.log("Following trader:", this.selectedTrader.id, settings);

        // Create subscription
        const data = {
          trader: this.selectedTrader.id,
          ...settings,
        };

        await this.copyAPI.followTrader(data);

        // Success!
        this.showSuccess("Successfully started copying trader!");

        this.closeFollowModal();

        // Redirect to copy trading dashboard after 1.5 seconds
        setTimeout(() => {
          window.location.href = "/dashboard/copy-trading";
        }, 1500);
      } catch (error) {
        console.error("Failed to follow trader:", error);

        // Check for specific error types
        const errorData = error.response?.data;

        if (
          errorData?.error?.includes("balance") ||
          errorData?.error?.includes("minimum")
        ) {
          // Handle balance-related errors
          await this.loadUserBalances(); // Refresh balances
          const balanceCheck = await this.checkUserBalance(this.selectedTrader);
          await this.showBalanceModal(balanceCheck);
        } else {
          // Handle other errors
          const errorMessage =
            errorData?.message ||
            errorData?.error ||
            error.message ||
            "Failed to follow trader";
          this.showError(errorMessage);
        }
      } finally {
        this.submitting = false;
      }
    },

    // Load traders from API
    async loadTraders() {
      try {
        this.loading = true;
        console.log("Loading traders...");

        const response = await this.copyAPI.getTraders();
        this.traders = response.results || response;
        this.filteredTraders = [...this.traders];

        console.log("Loaded traders:", this.traders.length);

        // Sort by default
        this.sortTraders();
      } catch (error) {
        console.error("Failed to load traders:", error);
        this.showError("Failed to load traders. Please refresh the page.");
      } finally {
        this.loading = false;

        // Re-init icons after render
        this.$nextTick(() => {
          if (typeof lucide !== "undefined") {
            lucide.createIcons();
          }
        });
      }
    },

    // Search traders
    async searchTraders() {
      try {
        if (!this.searchQuery.trim()) {
          // Reset to all traders
          this.filteredTraders = [...this.traders];
          this.sortTraders();
          return;
        }

        this.loading = true;
        console.log("Searching for:", this.searchQuery);

        const response = await this.copyAPI.searchTraders(this.searchQuery);
        this.filteredTraders = response.results || response;

        console.log("Search results:", this.filteredTraders.length);
      } catch (error) {
        console.error("Search failed:", error);
        this.showError("Search failed. Please try again.");
      } finally {
        this.loading = false;

        this.$nextTick(() => {
          if (typeof lucide !== "undefined") {
            lucide.createIcons();
          }
        });
      }
    },

    // Sort traders
    sortTraders() {
      this.filteredTraders = [...this.filteredTraders].sort((a, b) => {
        const aVal = parseFloat(a[this.sortBy]) || 0;
        const bVal = parseFloat(b[this.sortBy]) || 0;
        return bVal - aVal; // Descending order
      });

      console.log("Sorted by:", this.sortBy);
    },

    // Close follow modal
    closeFollowModal() {
      this.showFollowModal = false;
      this.selectedTrader = null;
    },

    // Show success message
    showSuccess(message) {
      if (typeof Swal !== "undefined") {
        Swal.fire({
          icon: "success",
          title: "Success!",
          text: message,
          timer: 3000,
          showConfirmButton: false,
          toast: true,
          position: "top-end",
        });
      } else {
        alert(message);
      }
    },

    // Show error message
    showError(message) {
      if (typeof Swal !== "undefined") {
        Swal.fire({
          icon: "error",
          title: "Error",
          text: message,
          confirmButtonColor: "#ef4444",
        });
      } else {
        alert("Error: " + message);
      }
    },

    // ✅ NEW - Get balance badge class for UI
    getBalanceClass(trader) {
      const tradingBalance = this.userBalances.trading;
      const minRequired = parseFloat(trader.minimum_investment || 0);

      if (tradingBalance >= minRequired) {
        return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300";
      } else if (tradingBalance >= minRequired * 0.5) {
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300";
      } else {
        return "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300";
      }
    },

    // ✅ NEW - Get balance status text
    getBalanceStatus(trader) {
      const tradingBalance = this.userBalances.trading;
      const minRequired = parseFloat(trader.minimum_investment || 0);
      const difference = tradingBalance - minRequired;

      if (difference >= 0) {
        return `✓ You have $${this.formatCurrency(
          difference
        )} more than required`;
      } else {
        return `⚠ Need $${this.formatCurrency(Math.abs(difference))} more`;
      }
    },
  };
}

// Dashboard Component
function copyTradingDashboard() {
  return {
    // State
    subscriptions: [],
    pendingTrades: [],
    loading: true,

    // Statistics
    stats: {
      activeSubscriptions: 0,
      totalTrades: 0,
      pendingApprovals: 0,
    },

    // API Client
    copyAPI: null,

    // Initialize
    async init() {
      console.log("Initializing Copy Trading Dashboard...");

      // Wait for APIClient
      await this.waitForAPIClient();

      // Initialize API
      this.copyAPI = APIClient;

      // Load data
      await Promise.all([
        this.loadDashboardData(),
        // this.initializeIcons()
      ]);

      // Initialize Lucide icons
      this.$nextTick(() => {
        if (typeof lucide !== "undefined") {
          lucide.createIcons();
        }
      });
    },

    // Wait for APIClient
    async waitForAPIClient() {
      let attempts = 0;
      while (typeof window.APIClient === "undefined" && attempts < 50) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        attempts++;
      }
    },

    // Load dashboard data
    async loadDashboardData() {
      try {
        this.loading = true;

        // Load subscriptions and pending trades in parallel
        const [subsResponse, tradesResponse, pendingResponse] =
          await Promise.all([
            this.copyAPI.getMySubscriptions(),
            this.copyAPI.getCopiedTrades(),
            this.copyAPI.getPendingTrades().catch(() => ({ results: [] })),
          ]);

        this.subscriptions = subsResponse.results || subsResponse;
        this.pendingTrades = pendingResponse.results || pendingResponse;
        this.trades = tradesResponse.results || tradesResponse;

        // Update statistics
        this.updateStats();

        console.log("Dashboard loaded:", {
          subscriptions: this.subscriptions.length,
          copiedTrades: this.trades.length,
          pendingTrades: this.pendingTrades.length,
        });
      } catch (error) {
        console.error("Failed to load dashboard:", error);
        APIClient.showMessage("Failed to load dashboard data", "danger");
      } finally {
        this.loading = false;

        this.$nextTick(() => {
          if (typeof lucide !== "undefined") {
            lucide.createIcons();
          }
        });
      }
    },
    // Add a retry method for failed loads
    async retryLoadData() {
      this.isLoading = true;
      try {
        await this.loadDashboardData();
        this.initializationError = null;
      } catch (error) {
        this.initializationError = error.message;
      } finally {
        this.isLoading = false;
      }
    },

    // Add data refresh capability
    async refreshData() {
      console.log("Refreshing dashboard data...");
      await this.loadDashboardData();
    },

    // Update statistics
    updateStats() {
      this.stats.activeSubscriptions = this.subscriptions.filter(
        (s) => s.is_active
      ).length;
      this.stats.pendingApprovals = this.pendingTrades.length;
      this.stats.totalTrades = this.trades.length;
    },

    // Add after the stats object:
    getSubscriptionStatus(subscription) {
      // Check if trader has any trades
      const traderHasTrades = subscription.trader_detail?.total_trades > 0;

      // Check if this subscription has copied any trades
      const hasCopiedTrades = subscription.copied_trades_count > 0;

      if (!subscription.is_active) {
        return {
          label: "Paused",
          color: "gray",
          icon: "pause-circle",
          message: "Copy trading is paused",
        };
      }

      if (!traderHasTrades) {
        return {
          label: "Waiting",
          color: "yellow",
          icon: "clock",
          message: "Waiting for trader to make their first trade",
        };
      }

      if (!hasCopiedTrades) {
        return {
          label: "Ready",
          color: "blue",
          icon: "check-circle",
          message: "Ready to copy next trade",
        };
      }

      return {
        label: "Active",
        color: "green",
        icon: "activity",
        message: "Actively copying trades",
      };
    },

    // Toggle subscription active status
    async toggleSubscription(subscriptionId) {
      try {
        const response = await this.copyAPI.toggleSubscription(subscriptionId);

        // Update local state
        const sub = this.subscriptions.find((s) => s.id === subscriptionId);
        if (sub) {
          sub.is_active = response.is_active;
        }

        this.updateStats();

        const message = response.is_active
          ? "Copy trading activated"
          : "Copy trading paused";

        APIClient.showMessage(message);
      } catch (error) {
        console.error("Failed to toggle subscription:", error);
        APIClient.showMessage("Failed to update subscription", "danger");
      }
    },

    // Unfollow trader
    async unfollowTrader(subscriptionId, traderName) {
      try {
        const confirmed = await Swal.fire({
          title: "Stop Copy Trading?",
          html: `
                        <div class="text-left">
                            <p class="mb-4">Are you sure you want to stop copying <strong>${traderName}</strong>?</p>
                            <div class="bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg">
                                <p class="text-sm text-blue-800 dark:text-blue-300">
                                    Your current positions will remain open.
                                </p>
                            </div>
                        </div>
                    `,
          icon: "warning",
          showCancelButton: true,
          confirmButtonText: "Yes, Stop Copying",
          cancelButtonText: "Cancel",
          confirmButtonColor: "#ef4444",
        });

        if (!confirmed.isConfirmed) return;

        await this.copyAPI.unfollowTrader(subscriptionId);

        // Remove from local state
        this.subscriptions = this.subscriptions.filter(
          (s) => s.id !== subscriptionId
        );
        this.updateStats();

        APIClient.showMessage("Successfully stopped copying trader");

        // Refresh page
        setTimeout(() => window.location.reload(), 1500);
      } catch (error) {
        console.error("Failed to unfollow:", error);
        APIClient.showMessage("Failed to unfollow trader", "danger");
      }
    },

    // Approve pending trade
    async approveTrade(tradeId) {
      try {
        await this.copyAPI.approveTrade(tradeId);

        // Remove from pending
        this.pendingTrades = this.pendingTrades.filter((t) => t.id !== tradeId);
        this.updateStats();

        APIClient.showMessage("Trade approved and executed");
      } catch (error) {
        console.error("Failed to approve trade:", error);
        APIClient.showMessage("Failed to approve trade", "danger");
      }
    },

    // Reject pending trade
    async rejectTrade(tradeId) {
      try {
        const confirmed = await Swal.fire({
          title: "Reject Trade?",
          text: "Are you sure you want to reject this trade?",
          icon: "warning",
          showCancelButton: true,
          confirmButtonText: "Yes, Reject",
          confirmButtonColor: "#ef4444",
        });

        if (!confirmed.isConfirmed) return;

        await this.copyAPI.rejectTrade(tradeId);

        // Remove from pending
        this.pendingTrades = this.pendingTrades.filter((t) => t.id !== tradeId);
        this.updateStats();

        APIClient.showMessage("Trade rejected");
      } catch (error) {
        console.error("Failed to reject trade:", error);
        APIClient.showMessage("Failed to reject trade", "danger");
      }
    },

    // Show success
    showSuccess(message) {
      if (typeof Swal !== "undefined") {
        Swal.fire({
          icon: "success",
          title: "Success!",
          text: message,
          timer: 3000,
          showConfirmButton: false,
          toast: true,
          position: "top-end",
        });
      }
    },

    // Show error
    showError(message) {
      if (typeof Swal !== "undefined") {
        Swal.fire({
          icon: "error",
          title: "Error",
          text: message,
          confirmButtonColor: "#ef4444",
        });
      }
    },
  };
}

// Register Alpine components globally
document.addEventListener("alpine:init", () => {
  Alpine.data("copyTradingExperts", copyTradingExperts);
  Alpine.data("copyTradingDashboard", copyTradingDashboard);
});

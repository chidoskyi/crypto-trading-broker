// script.js - Deposit Handler Class
console.log('Scripts loaded');
class DepositHandler {
    constructor() {
        this.depositForm = null;
        this.paymentForm = null;
        this.init();
    }

    init() {
        // Initialize Lucide icons
        if (window.lucide) {
            lucide.createIcons();
        }

        // Get forms
        this.depositForm = document.getElementById('deposit-form');
        this.paymentForm = document.getElementById('payment-form');

        // Bind event listeners
        if (this.depositForm) {
            // Only validate, let Django handle submission
            this.depositForm.addEventListener('submit', (e) => this.validateDepositForm(e));
        }

        if (this.paymentForm) {
            this.paymentForm.addEventListener('submit', (e) => this.handlePaymentSubmit(e));
        }

        // Initialize wallet handler if on payment page
        this.initWalletHandler();
    }

    // Validate deposit form (but let it submit to Django)
    validateDepositForm(e) {
        const formData = new FormData(this.depositForm);
        const amount = formData.get('amount');

        // Validate amount
        if (!amount || parseFloat(amount) <= 0) {
            e.preventDefault(); // Only prevent if invalid
            APIClient.showMessage('Please enter a valid amount', 'danger');
            return false;
        }

        // Valid - show message but let form submit naturally to Django
        APIClient.showMessage('Processing...', 'info');
        // Don't prevent default - let Django handle it
        return true;
    }

    // Initialize wallet handler for payment page
    initWalletHandler() {
        // Look for the hidden method field that Django renders
        const methodField = document.querySelector('input[name="method"]');
        
        if (methodField && methodField.value) {
            console.log('Loading wallet for:', methodField.value);
            // Load wallet for the pre-selected crypto from Django
            this.handlePaymentMethodChange(methodField.value);
        }
    }

    // Handle payment method change - fetch and display wallet
    async handlePaymentMethodChange(currency) {
        if (!currency) return;

        console.log('Fetching wallet for currency:', currency);

        try {
            // Show loading state
            this.showWalletLoading(true);

            // Fetch wallet data from API
            const walletData = await APIClient.getWallet(currency);

            console.log('Wallet data received:', walletData);

            // Display wallet information
            this.displayWalletInfo(walletData, currency);

        } catch (error) {
            console.error('Error fetching wallet:', error);
            APIClient.showMessage(`Failed to load ${currency.toUpperCase()} wallet: ${error.message}`, 'danger');
            this.showWalletLoading(false);
        }
    }

    // Display wallet information to user
    displayWalletInfo(walletData, currency) {
        const walletAddressElement = document.getElementById('wallet-address');
        const qrCodeElement = document.getElementById('wallet-qr-code');
        const walletInfoSection = document.getElementById('wallet-info-section');
        const cryptoNameElement = document.getElementById('crypto-name');

        if (!walletInfoSection) {
            console.error('Wallet info section not found');
            return;
        }

        // Update crypto name
        if (cryptoNameElement) {
            cryptoNameElement.textContent = walletData.currency || currency.toUpperCase();
        }

        // Update wallet address (it's an input field, not text element)
        if (walletAddressElement) {
            walletAddressElement.value = walletData.wallet_address;
            walletAddressElement.setAttribute('data-address', walletData.wallet_address);
        }

        // Update QR code
        if (qrCodeElement && walletData.qr_code) {
            qrCodeElement.src = walletData.qr_code;
            qrCodeElement.style.display = 'block';
            qrCodeElement.alt = `${currency} QR Code`;
        } else if (qrCodeElement) {
            qrCodeElement.style.display = 'none';
        }

        // Show the wallet info section
        walletInfoSection.style.display = 'block';
        
        // Hide loading state
        this.showWalletLoading(false);

        // Initialize copy functionality
        this.initCopyFunctionality();
    }

    // Show/hide wallet loading state
    showWalletLoading(show) {
        const loadingElement = document.getElementById('wallet-loading');
        const walletInfoSection = document.getElementById('wallet-info-section');

        if (loadingElement) {
            loadingElement.style.display = show ? 'block' : 'none';
        }

        if (walletInfoSection && show) {
            walletInfoSection.style.display = 'none';
        }
    }

    // Initialize copy to clipboard functionality
    initCopyFunctionality() {
        const copyBtn = document.getElementById('copy-wallet-btn');
        if (!copyBtn) return;

        // Clone to remove old listeners
        const newCopyBtn = copyBtn.cloneNode(true);
        copyBtn.parentNode.replaceChild(newCopyBtn, copyBtn);

        newCopyBtn.onclick = () => {
            const walletAddress = document.getElementById('wallet-address')?.value || 
                                 document.getElementById('wallet-address')?.getAttribute('data-address');
            
            if (walletAddress) {
                navigator.clipboard.writeText(walletAddress).then(() => {
                    APIClient.showMessage('Wallet address copied to clipboard!', 'success');
                    
                    // Visual feedback
                    const originalText = newCopyBtn.innerHTML;
                    newCopyBtn.innerHTML = `
                        <i data-lucide="check" class="w-4 h-4"></i>
                        Copied!
                    `;
                    newCopyBtn.classList.add('bg-green-600');
                    
                    setTimeout(() => {
                        newCopyBtn.innerHTML = originalText;
                        newCopyBtn.classList.remove('bg-green-600');
                        if (window.lucide) lucide.createIcons();
                    }, 2000);
                }).catch(err => {
                    console.error('Failed to copy: ', err);
                    APIClient.showMessage('Failed to copy address', 'danger');
                });
            }
        };

        // Reinitialize icons
        if (window.lucide) {
            lucide.createIcons();
        }
    }

    // Handle second step - payment proof submission
    async handlePaymentSubmit(e) {
        e.preventDefault();

        const submitBtn = this.paymentForm.querySelector('button[type="submit"]');
        const originalContent = submitBtn.innerHTML;

        try {
            // Show loading state
            this.setButtonLoading(submitBtn, true);

            // Get form data
            const formData = new FormData(this.paymentForm);
            const paymentProof = formData.get('proof');

            // Validate file
            if (!paymentProof || paymentProof.size === 0) {
                throw new Error('Please upload payment proof');
            }

            // Validate file size (max 10MB)
            if (paymentProof.size > 10 * 1024 * 1024) {
                throw new Error('File size must be less than 10MB');
            }

            // Validate file type
            if (!paymentProof.type.startsWith('image/')) {
                throw new Error('Only image files are allowed');
            }

            // Get deposit data from form
            const amount = formData.get('amount');
            const selectedCrypto = formData.get('method');
            const paymentMethodName = formData.get('payment_method');

            console.log('Submitting deposit:', {
                amount,
                selectedCrypto,
                paymentMethodName
            });

            // Prepare deposit data for API
            const depositFormData = new FormData();
            depositFormData.append('amount', amount);
            depositFormData.append('payment_proof', paymentProof);
            depositFormData.append('selected_crypto', selectedCrypto);
            depositFormData.append('payment_method_name', paymentMethodName);

            // Call API to create deposit
            const response = await APIClient.createDeposit(depositFormData);
            console.log(response);

            console.log('Deposit created successfully:', response);

            // Show success message
            APIClient.showMessage('Deposit submitted successfully! Redirecting...', 'success');

            // Store deposit details for success page
            this.storeDepositDetails(response);

            // Redirect to success page
            setTimeout(() => {
                window.location.href = '/dashboard/deposit-success/';
            }, 2000);

        } catch (error) {
            console.error('Deposit error:', error);

            // Show error message
            const errorMessage = error.message || 'Failed to submit deposit. Please try again.';
            APIClient.showMessage(errorMessage, 'danger');

            // Restore button
            this.setButtonLoading(submitBtn, false, originalContent);
        }
    }

    // Set button loading state
    setButtonLoading(button, isLoading, originalContent = '') {
        if (isLoading) {
            button.disabled = true;
            button.innerHTML = `
                <div class="flex items-center justify-center gap-3">
                    <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>Processing...</span>
                </div>
            `;
        } else {
            button.disabled = false;
            button.innerHTML = originalContent;

            // Reinitialize icons
            if (window.lucide) {
                lucide.createIcons();
            }
        }
    }

    // Store deposit details in sessionStorage (only for success page display)
    storeDepositDetails(response) {
        sessionStorage.setItem('last_deposit_id', response.deposit_id);
        sessionStorage.setItem('last_deposit_amount', response.amount);
        sessionStorage.setItem('last_deposit_crypto', response.crypto_display || response.selected_crypto);
        sessionStorage.setItem('last_deposit_status', response.status_display || response.status);
        sessionStorage.setItem('last_deposit_wallet', response.wallet_address);
        sessionStorage.setItem('last_deposit_qr', response.qr_code_url);
    }

    // Format currency
    static formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD'
        }).format(amount);
    }
}

class InvestmentHandler {
    constructor() {
        this.investmentForm = null;
        this.init();
    }

    init() {
        // Initialize Lucide icons
        if (window.lucide) {
            lucide.createIcons();
        }

        // Get forms
        this.investmentForm = document.getElementById('investment-form');

        // Bind event listeners
        if (this.investmentForm) {
            this.investmentForm.addEventListener('submit', (e) => this.handleInvestmentSubmit(e));
        }
    }

    async handleInvestmentSubmit(e) {
        e.preventDefault();
        
        const formData = new FormData(this.investmentForm);
        const planId = formData.get('plan_id');
        const amount = formData.get('amount');
        const investmentType = formData.get('investment_type');

        // Validate amount
        if (!amount || parseFloat(amount) <= 0) {
            APIClient.showMessage('Please enter a valid amount', 'danger');
            return false;
        }

        // Validate investment type
        if (!investmentType) {
            APIClient.showMessage('Please select investment type', 'danger');
            return false;
        }

        try {
            APIClient.showMessage('Processing investment...', 'info');

            const investmentData = {
                plan_id: parseInt(planId),
                amount: amount,
                investment_type: investmentType
            };

            const response = await APIClient.createInvestment(investmentData);
            
            APIClient.showMessage('Investment created successfully!', 'success');
            
            // Redirect to dashboard after 1 second
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1000);

        } catch (error) {
            console.error('Investment error:', error);
            APIClient.showMessage(
                error.message || 'Failed to create investment. Please try again.',
                'danger'
            );
        }

        return false;
    }
    
}

// Initialize DepositHandler when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    new DepositHandler();
    new InvestmentHandler();
});
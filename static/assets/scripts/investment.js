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
            this.investmentForm.addEventListener('submit', (e) => this.validateInvestmentForm(e));
        }
    }

    validateInvestmentForm(e) {
        const formData = new FormData(this.investmentForm);
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
}


// Initialize DepositHandler when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    new InvestmentHandler();
});
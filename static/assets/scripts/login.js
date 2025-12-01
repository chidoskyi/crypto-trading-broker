// assets/scripts/login.js - login handler with backend integration

class LoginHandler {
    constructor() {
        this.form = null;
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.form = document.getElementById('login-form');
            if (this.form) {
                this.setupFormHandler();
            }
        });
    }

    setupFormHandler() {
        this.form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleSubmit();
        });
    }

    async handleSubmit() {
        const submitBtn = this.form.querySelector('button[type="submit"]');
        const originalHTML = submitBtn.innerHTML;
        
        try {
            // Disable submit button
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin inline-block mr-2"></i>Logging In...';
            
            // Refresh icons
            if (window.lucide) {
                lucide.createIcons();
            }

            // Collect form data
            const formData = this.collectFormData();
            
            // Send login request
            const response = await APIClient.post('/auth/login/', formData);
            
            // Handle success
            APIClient.showMessage('Login successful! Redirecting...', 'success');
            
            // Store tokens
            if (response.data.tokens) {
                APIClient.setTokens(response.data.tokens.access, response.data.tokens.refresh); 
            }
            console.log('Logged in user:', response.data.user);
            
            // Redirect to dashboard after 1.5 seconds
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1500);
            
        } catch (error) {
            console.error('Login error:', error);
            
            // Re-enable submit button
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHTML;

            // Refresh icons
            if (window.lucide) {
                lucide.createIcons();
            }
            
            // Show error message
            let errorMessage = 'Login failed. Please try again.';
            
            if (error.response?.data) {
                const errors = error.response.data;
                
                // Handle field-specific errors
                if (typeof errors === 'object') {
                    const errorMessages = [];
                    for (const [field, messages] of Object.entries(errors)) {
                        const fieldName = this.formatFieldName(field);
                        const message = Array.isArray(messages) ? messages.join(', ') : messages;
                        errorMessages.push(`${fieldName}: ${message}`);
                    }
                    errorMessage = errorMessages.join('\n');
                } else if (typeof errors === 'string') {
                    errorMessage = errors;
                } else if (errors.detail) {
                    errorMessage = errors.detail;
                } else if (errors.message) {
                    errorMessage = errors.message;
                }
            } else if (error.message) {
                errorMessage = error.message;
            }
            
            APIClient.showMessage(errorMessage, 'danger');
        }
    }

    collectFormData() {
        const formData = {
            // Login can be username or email
            login: document.getElementById('login').value.trim(),
            password: document.getElementById('password').value,
            remember: document.getElementById('remember').checked
        };
        
        return formData;
    }

    formatFieldName(field) {
        // Format field names for better error messages
        const fieldMap = {
            'login': 'Username/Email',
            'password': 'Password'
        };
        
        return fieldMap[field] || field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
}

// Initialize login handler
const loginHandler = new LoginHandler();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = LoginHandler;
}
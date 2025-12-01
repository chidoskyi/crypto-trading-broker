// assets/scripts/auth.js - Authentication handler (Login & Registration)


class RegistrationHandler {
    constructor() {
        this.form = null;
        this.captchaKey = null;
        this.captchaCode = null;
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.form = document.getElementById('register');
            if (this.form) {
                this.setupFormHandler();
                this.loadCaptcha();
            }
        });
    }

    async loadCaptcha() {
        try {
            const response = await APIClient.get('/auth/captcha/');
            const data = response.data;
            
            this.captchaKey = data.captcha_key;
            this.captchaCode = data.captcha_code;
            
            // Update the displayed CAPTCHA code
            const captchaDisplay = document.querySelector('.text-yellow-400');
            if (captchaDisplay) {
                captchaDisplay.textContent = data.captcha_code;
            }
            
            // Store captcha key in hidden field
            let captchaKeyInput = document.querySelector('input[name="captcha_key"]');
            if (!captchaKeyInput) {
                captchaKeyInput = document.createElement('input');
                captchaKeyInput.type = 'hidden';
                captchaKeyInput.name = 'captcha_key';
                this.form.appendChild(captchaKeyInput);
            }
            captchaKeyInput.value = this.captchaKey;
            
        } catch (error) {
            console.error('Failed to load CAPTCHA:', error);
            APIClient.showMessage('Failed to load security verification. Please refresh the page.', 'danger');
        }
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
            submitBtn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin inline-block mr-2"></i>Creating Account...';
            
            // Refresh icons
            if (window.lucide) {
                lucide.createIcons();
            }

            // Collect form data
            const formData = this.collectFormData();
            
            // Validate form data
            const validation = this.validateFormData(formData);
            if (!validation.isValid) {
                throw new Error(validation.message);
            }

            // Send registration request
            const response = await APIClient.register(formData);;
            
            // Handle success
            APIClient.showMessage('Account created successfully! Redirecting...', 'success');
            
        // SAFELY check if profile needs completion with proper error handling
        let redirectUrl = '/dashboard'; // default fallback
        
        // if (response.data) {
        //     // Check if profile_complete exists and is explicitly false
        //     const profileComplete = response.data.profile_complete !== undefined 
        //         ? response.data.profile_complete 
        //         : false;
            
        //     // Use provided redirect or determine based on profile completion
        //     redirectUrl = response.data.redirect || (profileComplete ? '/dashboard' : '/complete-profile');
            
        //     console.log('Registration redirect:', {
        //         profile_complete: profileComplete,
        //         provided_redirect: response.data.redirect,
        //         final_redirect: redirectUrl
        //     });
        // } else {
        //     console.warn('No data in registration response, using default redirect');
        // }
            
            // Redirect after 1.5 seconds
            setTimeout(() => {
                window.location.href = redirectUrl;
            }, 1500);
            
        } catch (error) {
            console.error('Registration error:', error);
            
            // Re-enable submit button
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHTML;
            
            // Refresh icons
            if (window.lucide) {
                lucide.createIcons();
            }
            
            // Show error message
            let errorMessage = 'Registration failed. Please try again.';
            
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
            
            // Reload CAPTCHA on error
            await this.loadCaptcha();
            
            // Clear captcha input
            const captchaInput = document.getElementById('captcha');
            if (captchaInput) {
                captchaInput.value = '';
            }
        }
    }

    collectFormData() {
        // Get country select element
        const countrySelect = document.getElementById('country');
        const selectedCountry = countrySelect.value;
        
        // Map country name to ID (you'll need to adjust this based on your Country model)
        // For now, we'll send the country name and handle it on backend
        // Or you can fetch countries from API and map them properly
        
        const formData = {
            // Step 1: Personal Information
            username: document.getElementById('username').value.trim(),
            email: document.getElementById('email').value.trim(),
            phone_number: document.getElementById('phone').value.trim(),
            
            // Split full name into first and last name
            first_name: this.getFirstName(document.getElementById('name').value.trim()),
            last_name: this.getLastName(document.getElementById('name').value.trim()),
            
            // Step 2: Location
            country: selectedCountry, // Send country name, backend will handle mapping
            
            // Step 3: Security
            password: document.getElementById('password').value,
            password_confirmation: document.getElementById('password_confirmation').value,
            
            // CAPTCHA
            captcha_key: this.captchaKey,
            captcha_value: document.getElementById('captcha').value.trim(),
            
            // Optional: Referral code (if you want to add this field)
            // referred_by_code: document.getElementById('referral_code')?.value.trim() || ''
        };
        
        return formData;
    }

    getFirstName(fullName) {
        const parts = fullName.split(' ');
        return parts[0] || '';
    }

    getLastName(fullName) {
        const parts = fullName.split(' ');
        if (parts.length > 1) {
            return parts.slice(1).join(' ');
        }
        return '';
    }

    validateFormData(data) {
        const errors = [];

        // Username validation
        if (!data.username || data.username.length < 3) {
            errors.push('Username must be at least 3 characters');
        }

        // Email validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!data.email || !emailRegex.test(data.email)) {
            errors.push('Please enter a valid email address');
        }

        // Phone validation
        if (!data.phone_number || data.phone_number.length < 10) {
            errors.push('Please enter a valid phone number');
        }

        // Name validation
        if (!data.first_name) {
            errors.push('Please enter your full name');
        }

        // Country validation
        if (!data.country || data.country === 'Select your country') {
            errors.push('Please select your country');
        }

        // Password validation
        if (!data.password || data.password.length < 8) {
            errors.push('Password must be at least 8 characters');
        }

        if (data.password !== data.password_confirmation) {
            errors.push('Passwords do not match');
        }

        // CAPTCHA validation
        if (!data.captcha_value || data.captcha_value.length !== 6) {
            errors.push('Please enter the complete 6-character security code');
        }

        // Terms agreement
        const agreeCheckbox = document.getElementById('agree');
        if (!agreeCheckbox.checked) {
            errors.push('You must agree to the Terms and Conditions');
        }

        return {
            isValid: errors.length === 0,
            message: errors.join('\n')
        };
    }

    formatFieldName(field) {
        // Format field names for better error messages
        const fieldMap = {
            'username': 'Username',
            'email': 'Email',
            'phone_number': 'Phone Number',
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'country': 'Country',
            'password': 'Password',
            'password_confirmation': 'Password Confirmation',
            'captcha_key': 'Security Code',
            'captcha_value': 'Security Code',
            'captcha': 'Security Code'
        };
        
        return fieldMap[field] || field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
}

// Login Handler Class
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
            await this.handleLogin();
        });
    }

    async handleLogin() {
        const submitBtn = this.form.querySelector('button[type="submit"]');
        const originalHTML = submitBtn.innerHTML;
        
        try {
            // Disable submit button
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin inline-block mr-2"></i>Signing in...';
            
            // Refresh icons
            if (window.lucide) {
                lucide.createIcons();
            }

            // Collect form data
            const formData = this.collectFormData();
            
            // Validate form data
            const validation = this.validateFormData(formData);
            if (!validation.isValid) {
                throw new Error(validation.message);
            }

            // Send login request
            const response = await APIClient.login(formData);
            
            // Handle success
            APIClient.showMessage('Login successful! Redirecting...', 'success');
            
            // Store tokens
            // if (response.data.tokens) {
            //     APIClient.setTokens(response.data.tokens.access, response.data.tokens.refresh);
            // } else if (response.data.access && response.data.refresh) {
            //     APIClient.setTokens(response.data.access, response.data.refresh);
            // }
            
            // Redirect to dashboard after 1 second
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1000);
            
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
            let errorMessage = 'Login failed. Please check your credentials.';
            
            if (error.response?.data) {
                const errors = error.response.data;
                
                if (typeof errors === 'string') {
                    errorMessage = errors;
                } else if (errors.detail) {
                    errorMessage = errors.detail;
                } else if (errors.message) {
                    errorMessage = errors.message;
                } else if (errors.non_field_errors) {
                    errorMessage = Array.isArray(errors.non_field_errors) 
                        ? errors.non_field_errors.join(', ') 
                        : errors.non_field_errors;
                } else if (typeof errors === 'object') {
                    const errorMessages = [];
                    for (const [field, messages] of Object.entries(errors)) {
                        const message = Array.isArray(messages) ? messages.join(', ') : messages;
                        errorMessages.push(message);
                    }
                    if (errorMessages.length > 0) {
                        errorMessage = errorMessages.join('. ');
                    }
                }
            } else if (error.message) {
                errorMessage = error.message;
            }
            
            APIClient.showMessage(errorMessage, 'danger');
        }
    }

    collectFormData() {
        const login = document.getElementById('login').value.trim();
        const password = document.getElementById('password').value;
        const remember = document.getElementById('remember')?.checked || false;
        
        return {
            login: login,  // Can be email or username
            password: password,
            remember: remember
        };
    }

    validateFormData(data) {
        const errors = [];

        // Login validation (email or username)
        if (!data.login || data.login.length < 3) {
            errors.push('Please enter your email or username');
        }

        // Password validation
        if (!data.password) {
            errors.push('Please enter your password');
        }

        return {
            isValid: errors.length === 0,
            message: errors.join('\n')
        };
    }
}

// Profile Completion Handler Class
class ProfileCompletionHandler {
    constructor() {
        this.form = null;
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            this.form = document.getElementById('profile-form');
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
            submitBtn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin inline-block mr-2"></i>Saving Profile...';
            
            // Refresh icons
            if (window.lucide) {
                lucide.createIcons();
            }

            // Collect form data
            const formData = new FormData();
            
            // Add text fields
            const bio = document.getElementById('bio').value.trim();
            const location = document.getElementById('location').value.trim();
            const website = document.getElementById('website').value.trim();
            
            // Validate required fields before sending
            if (!bio || bio.length < 10) {
                throw new Error('Bio must be at least 10 characters long.');
            }

            if (!location) {
                throw new Error('Location is required.');
            }
            
            formData.append('bio', bio);
            formData.append('location', location);
            if (website) {
                formData.append('website', website);
            }
            
            // Add profile picture if selected
            const profilePictureInput = document.getElementById('profile_picture');
            if (profilePictureInput && profilePictureInput.files[0]) {
                formData.append('profile_picture', profilePictureInput.files[0]);
            }

            // Send profile completion request
            const response = await APIClient.profileComplete(formData);
            
            // Handle success
            const message = response.data.message || 'Profile completed successfully!';
            APIClient.showMessage(message, 'success');
            
            // Redirect
            const redirect = response.data.redirect || '/dashboard';
            setTimeout(() => {
                window.location.href = redirect;
            }, 1500);
            
        } catch (error) {
            console.error('Profile completion error:', error);
            
            // Re-enable submit button
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalHTML;

            // Refresh icons
            if (window.lucide) {
                lucide.createIcons();
            }
            
            // Show error message
            let errorMessage = 'Failed to save profile. Please try again.';
            
            if (error.response?.data) {
                const errors = error.response.data;
                
                if (typeof errors === 'object' && !Array.isArray(errors)) {
                    const errorMessages = [];
                    for (const [field, messages] of Object.entries(errors)) {
                        if (field !== 'success' && field !== 'message') {
                            const fieldName = this.formatFieldName(field);
                            const message = Array.isArray(messages) ? messages.join(', ') : messages;
                            errorMessages.push(`${fieldName}: ${message}`);
                        }
                    }
                    if (errorMessages.length > 0) {
                        errorMessage = errorMessages.join('\n');
                    } else if (errors.message) {
                        errorMessage = errors.message;
                    }
                } else if (typeof errors === 'string') {
                    errorMessage = errors;
                } else if (errors.detail) {
                    errorMessage = errors.detail;
                } else if (errors.error) {
                    errorMessage = errors.error;
                }
            } else if (error.message) {
                errorMessage = error.message;
            }
            
            APIClient.showMessage(errorMessage, 'danger');
        }
    }

    formatFieldName(field) {
        const fieldMap = {
            'bio': 'Bio',
            'location': 'Location',
            'website': 'Website',
            'profile_picture': 'Profile Picture'
        };
        return fieldMap[field] || field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
}

class PasswordResetHandler {
    constructor() {
        this.form = null;
        this.init();
    }

    init() {
        document.addEventListener('DOMContentLoaded', () => {
            // Request form
            this.form = document.getElementById('password-reset-request-form');
            if (this.form) {
                this.setupRequestHandler();
            }
            
            // Confirm form
            this.confirmForm = document.getElementById('password-reset-confirm-form');
            if (this.confirmForm) {
                this.setupConfirmHandler();
                this.validateResetToken();
            }
        });
    }

    setupRequestHandler() {
        this.form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleResetRequest();
        });
    }

    setupConfirmHandler() {
        this.confirmForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.handleResetConfirm();
        });
    }

async handleResetRequest() {
    const submitBtn = this.form.querySelector('button[type="submit"]');
    const originalHTML = submitBtn.innerHTML;
    
    try {
        // Disable submit button
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin inline-block mr-2"></i>Sending...';
        
        // Refresh icons
        if (window.lucide) {
            lucide.createIcons();
        }

        // Collect form data - FIXED: Get the email input value
        const emailInput = document.getElementById('email');
        const email = emailInput.value.trim(); // Make sure to trim the value
        
        console.log('📧 [Form] Email input value:', emailInput.value);
        console.log('🧹 [Form] Trimmed email:', email);
        
        // Validate email
        if (!email || !this.isValidEmail(email)) {
            throw new Error('Please enter a valid email address.');
        }

        // Send reset request - FIXED: Pass email directly, not as object
        const response = await APIClient.requestPasswordReset(email);
        
        // Handle success
        APIClient.showMessage(response.message || 'If an account with that email exists, a password reset link has been sent.', 'success');
        
        // Clear the form
        emailInput.value = '';
        
        // Redirect to login after 3 seconds
        setTimeout(() => {
            window.location.href = '/login';
        }, 3000);
        
    } catch (error) {
        console.error('Password reset request error:', error);
        
        // Re-enable submit button
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalHTML;
        
        // Refresh icons
        if (window.lucide) {
            lucide.createIcons();
        }
        
        // Show error message
        let errorMessage = 'Failed to send reset email. Please try again.';
        
        if (error.response?.data) {
            const errors = error.response.data;
            
            if (typeof errors === 'string') {
                errorMessage = errors;
            } else if (errors.detail) {
                errorMessage = errors.detail;
            } else if (errors.message) {
                errorMessage = errors.message;
            } else if (typeof errors === 'object') {
                const errorMessages = [];
                for (const [field, messages] of Object.entries(errors)) {
                    const message = Array.isArray(messages) ? messages.join(', ') : messages;
                    errorMessages.push(message);
                }
                if (errorMessages.length > 0) {
                    errorMessage = errorMessages.join('. ');
                }
            }
        } else if (error.message) {
            errorMessage = error.message;
        }
        
        APIClient.showMessage(errorMessage, 'danger');
    }
}

async handleResetConfirm() {
    const submitBtn = this.confirmForm.querySelector('button[type="submit"]');
    const originalHTML = submitBtn.innerHTML;
    
    try {
        // Disable submit button
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin inline-block mr-2"></i>Resetting...';
        
        // Refresh icons
        if (window.lucide) {
            lucide.createIcons();
        }

        // Collect form data
        const formData = this.collectConfirmFormData();
        
        // Validate form data
        const validation = this.validateConfirmFormData(formData);
        if (!validation.isValid) {
            throw new Error(validation.message);
        }

        // FIXED: Get token from hidden input fields instead of URL
        const uidb64 = document.getElementById('uidb64').value;
        const token = document.getElementById('token').value;
        
        console.log('🔑 [Password Reset] UID:', uidb64);
        console.log('🔑 [Password Reset] Token:', token);
        
        // Send reset confirmation
        const response = await APIClient.resetPassword(uidb64, token, formData);
        
        // Handle success
        APIClient.showMessage(response.message || 'Password has been reset successfully!', 'success');
        
        // Redirect to login after 2 seconds
        setTimeout(() => {
            window.location.href = '/login';
        }, 2000);
        
    } catch (error) {
        console.error('Password reset confirm error:', error);
        
        // Re-enable submit button
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalHTML;
        
        // Refresh icons
        if (window.lucide) {
            lucide.createIcons();
        }
        
        // Show error message
        let errorMessage = 'Failed to reset password. Please try again.';
        
        if (error.response?.data) {
            const errors = error.response.data;
            
            if (typeof errors === 'string') {
                errorMessage = errors;
            } else if (errors.detail) {
                errorMessage = errors.detail;
            } else if (errors.message) {
                errorMessage = errors.message;
            } else if (typeof errors === 'object') {
                const errorMessages = [];
                for (const [field, messages] of Object.entries(errors)) {
                    const fieldName = this.formatFieldName(field);
                    const message = Array.isArray(messages) ? messages.join(', ') : messages;
                    errorMessages.push(`${fieldName}: ${message}`);
                }
                if (errorMessages.length > 0) {
                    errorMessage = errorMessages.join('\n');
                }
            }
        } else if (error.message) {
            errorMessage = error.message;
        }
        
        APIClient.showMessage(errorMessage, 'danger');
    }
}

async validateResetToken() {
    try {
        // FIXED: Get token from hidden input fields
        const uidb64 = document.getElementById('uidb64').value;
        const token = document.getElementById('token').value;
        
        console.log('🔍 [Token Validation] Validating token...');
        
        const response = await APIClient.passwordResetValidate(uidb64, token);
        
        console.log('✅ [Token Validation] Response:', response);
        
        if (!response.success) {
            APIClient.showMessage('Invalid or expired reset link. Please request a new password reset.', 'danger');
            
            // Disable form
            const submitBtn = this.confirmForm.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            
            // Hide form and show error message
            this.confirmForm.style.display = 'none';
            document.getElementById('reset-token-error').style.display = 'block';
        }
        
    } catch (error) {
        console.error('Token validation error:', error);
        APIClient.showMessage('Invalid reset link. Please request a new password reset.', 'danger');
        
        // Disable form
        const submitBtn = this.confirmForm.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        
        // Hide form and show error message
        this.confirmForm.style.display = 'none';
        document.getElementById('reset-token-error').style.display = 'block';
    }
}

    collectConfirmFormData() {
        return {
            new_password: document.getElementById('new_password').value,
            confirm_password: document.getElementById('confirm_password').value
        };
    }

    validateConfirmFormData(data) {
        const errors = [];

        if (!data.new_password || data.new_password.length < 8) {
            errors.push('Password must be at least 8 characters long');
        }

        if (data.new_password !== data.confirm_password) {
            errors.push('Passwords do not match');
        }

        return {
            isValid: errors.length === 0,
            message: errors.join('\n')
        };
    }

    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    formatFieldName(field) {
        const fieldMap = {
            'new_password': 'New Password',
            'confirm_password': 'Confirm Password',
            'email': 'Email'
        };
        return fieldMap[field] || field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
}

// Initialize handlers
const registrationHandler = new RegistrationHandler();
const loginHandler = new LoginHandler();
const profileCompletionHandler = new ProfileCompletionHandler();
const passwordResetHandler = new PasswordResetHandler();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { RegistrationHandler, LoginHandler, ProfileCompletionHandler, PasswordResetHandler };
}
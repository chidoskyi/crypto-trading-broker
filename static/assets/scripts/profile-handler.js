// profile-handler.js - Fixed Version
console.log("profile-handler.js loaded");

const profileApi = window.APIClient;

// Register Alpine components BEFORE DOMContentLoaded
// This ensures they're available when Alpine initializes
if (typeof Alpine === "undefined") {
  console.warn(
    "Alpine.js not loaded yet. Components will be registered when Alpine loads."
  );

  // Create a function to initialize when Alpine is ready
  window.initProfileComponents = function () {
    registerAlpineComponents();
  };

  // Try to detect when Alpine loads
  document.addEventListener("alpine:init", function () {
    registerAlpineComponents();
  });
} else {
  registerAlpineComponents();
}

function registerAlpineComponents() {
    console.log("Registering Alpine components...");

    if (!Alpine || !Alpine.store || !Alpine.data) {
        console.error("Alpine.js methods not available");
        return;
    }

    // ===== GLOBAL PROFILE STORE =====
    Alpine.store("profile", {
        userProfile: null,
        traderStatus: null,
        countryList: [],
        isLoading: false,

        async loadProfile() {
        this.isLoading = true;
        try {
            const profile = await profileApi.getMyProfile();
            console.log('Full API response:', JSON.stringify(profile, null, 2));
            console.log('Country field type:', typeof profile.country);
            console.log('Country value:', profile.country);
            console.log('User profile"s:', profile);
            this.userProfile = profile;

            // Load country list
            try {
            const countryList = await profileApi.getCountryList();
            console.log("Country list:", countryList);
            this.countryList = countryList;
            } catch (error) {
            console.error("Error loading country list:", error);
            this.countryList = [];
            }

            // Load trader status
            try {
            const traderStatus = await profileApi.checkTraderStatus();
            console.log("Trader status:", traderStatus);
            this.traderStatus = traderStatus;
            } catch (error) {
            console.log("User is not a trader");
            this.traderStatus = { is_trader: false };
            }

            // Load user's copy trading status
            try {
            const getTraderStatistics = await profileApi.getTraderStatistics();
            this.copyTradingStatus = getTraderStatistics;
            } catch (error) {
            console.log("User is not a copy trader");
            this.copyTradingStatus = { is_copy_trader: false };
            }

            return profile;
        } catch (error) {
            console.error("Error loading profile:", error);
            profileApi.showMessage("Error loading profile", "dangeer");
        } finally {
            this.isLoading = false;
        }
        },

        async updateProfile(data) {
        this.isLoading = true;
        try {
            const updatedProfile = await profileApi.updateMyProfile(data);
            this.userProfile = { ...this.userProfile, ...updatedProfile };
            profileApi.showMessage("Profile updated successfully", "success");
            return updatedProfile;
        } catch (error) {
            console.error("Error updating profile:", error);
            profileApi.showMessage("Error updating profile", "error");
            throw error;
        } finally {
            this.isLoading = false;
        }
        },

        async changePassword(passwordData) {
        this.isLoading = true;
        try {
            const result = await profileApi.changePassword(passwordData);
            profileApi.showMessage("Password changed successfully", "success");
            return result;
        } catch (error) {
            console.error("Error changing password:", error);
            profileApi.showMessage("Error changing password", "error");
            throw error;
        } finally {
            this.isLoading = false;
        }
        },

        async uploadProfilePicture(file) {
        this.isLoading = true;
        try {
            const result = await profileApi.uploadProfilePicture(file);
            if (result.profile_picture_url) {
            this.userProfile.profile_picture = result.profile_picture_url;
            }
            profileApi.showMessage(
            "Profile picture uploaded successfully",
            "success"
            );
            return result;
        } catch (error) {
            console.error("Error uploading profile picture:", error);
            profileApi.showMessage("Error uploading profile picture", "error");
            throw error;
        } finally {
            this.isLoading = false;
        }
        },

        async deleteProfilePicture() {
        this.isLoading = true;
        try {
            const result = await profileApi.deleteProfilePicture();
            this.userProfile.profile_picture = null;
            profileApi.showMessage(
            "Profile picture deleted successfully",
            "success"
            );
            return result;
        } catch (error) {
            console.error("Error deleting profile picture:", error);
            profileApi.showMessage("Error deleting profile picture", "error");
            throw error;
        } finally {
            this.isLoading = false;
        }
        },

        async activateTrader(data) {
        this.isLoading = true;
        try {
            const result = await profileApi.activateTrader(data);
            this.traderStatus = result;
            profileApi.showMessage(
            "Trader account activated successfully",
            "success"
            );
            return result;
        } catch (error) {
            console.error("Error activating trader:", error);
            profileApi.showMessage("Error activating trader", "error");
            throw error;
        } finally {
            this.isLoading = false;
        }
        },

        async updateTraderSettings(data) {
        this.isLoading = true;
        try {
            const result = await profileApi.updateTraderSettings(data);
            this.traderStatus = result;
            profileApi.showMessage(
            "Trader settings updated successfully",
            "success"
            );
            return result;
        } catch (error) {
            console.error("Error updating trader settings:", error);
            profileApi.showMessage("Error updating trader settings", "error");
            throw error;
        } finally {
            this.isLoading = false;
        }
        },

        async deactivateTrader() {
        this.isLoading = true;
        try {
            await profileApi.deactivateTrader();
            this.traderStatus = { is_trader: false, is_active: false };
            profileApi.showMessage(
            "Trader account deactivated successfully",
            "success"
            );
        } catch (error) {
            console.error("Error deactivating trader:", error);
            profileApi.showMessage("Error deactivating trader", "error");
            throw error;
        } finally {
            this.isLoading = false;
        }
        },
        async reactivateTrader() {
        this.isLoading = true;
        try {
            await profileApi.reactivateTrader();
            this.traderStatus = { is_trader: true, is_active: true };
            profileApi.showMessage(
            "Trader account reactivated successfully",
            "success"
            );
        } catch (error) {
            console.error("Error reactivating trader:", error);
            profileApi.showMessage("Error reactivating trader", "error");
            throw error;
        } finally {
            this.isLoading = false;
        }
        },



        async getTraderStatistics(traderId) {
        this.isLoading = true;
        try {
            const result = await profileApi.getTraderStatistics(traderId);
            this.traderStatistics = result;
            profileApi.showMessage(
            "Trader statistics retrieved successfully",
            "success"
            );
            return result;
        } catch (error) {
            console.error("Error retrieving trader statistics:", error);
            profileApi.showMessage("Error retrieving trader statistics", "error");
            throw error;
        } finally {
            this.isLoading = false;
        }
        },

        // Helper method for notifications
        showNotification(message, type = "info") {
        const toast = document.createElement("div");
        const bgColor =
            type === "success"
            ? "bg-green-50 dark:bg-green-900/30 border-green-500 text-green-700 dark:text-green-400"
            : type === "error"
            ? "bg-red-50 dark:bg-red-900/30 border-red-500 text-red-700 dark:text-red-400"
            : "bg-blue-50 dark:bg-blue-900/30 border-blue-500 text-blue-700 dark:text-blue-400";

        toast.className = `fixed top-4 right-4 ${bgColor} border-l-4 p-4 rounded-lg shadow-lg transform transition-all duration-300 ease-out z-50 flex items-start max-w-sm`;
        toast.innerHTML = `
                        <div class="flex-shrink-0">
                            ${
                            type === "success"
                                ? '<i data-lucide="check-circle" class="h-5 w-5 text-green-500"></i>'
                                : type === "error"
                                ? '<i data-lucide="x-circle" class="h-5 w-5 text-red-500"></i>'
                                : '<i data-lucide="info" class="h-5 w-5 text-blue-500"></i>'
                            }
                        </div>
                        <div class="ml-3">
                            <p class="text-sm font-medium">${message}</p>
                        </div>
                        <div class="ml-auto pl-3">
                            <button type="button" class="inline-flex rounded-md p-1.5 focus:outline-none">
                                <span class="sr-only">Dismiss</span>
                                <i data-lucide="x" class="h-4 w-4"></i>
                            </button>
                        </div>
                    `;

        document.body.appendChild(toast);

        // Initialize Lucide icons
        if (window.lucide) {
            lucide.createIcons();
        }

        // Add entrance animation
        setTimeout(() => {
            toast.classList.add("translate-y-2");
        }, 10);

        // Remove after 5 seconds
        setTimeout(() => {
            toast.classList.remove("translate-y-2");
            toast.classList.add("-translate-y-2", "opacity-0");
            setTimeout(() => toast.remove(), 300);
        }, 5000);

        // Dismiss button
        toast.querySelector("button").addEventListener("click", () => {
            toast.classList.remove("translate-y-2");
            toast.classList.add("-translate-y-2", "opacity-0");
            setTimeout(() => toast.remove(), 300);
        });
        },
    });

    // ===== PERSONAL INFORMATION TAB COMPONENT =====
    Alpine.data('profileSettings', () => ({
        saving: false,
        formData: {
            first_name: '',
            last_name: '',
            display_name: '',
            bio: '',
            country: '',
            phone_number: '',
            website: ''
        },
        
        async init() {
            // Load profile data from store
            await Alpine.store('profile').loadProfile();
            
            const profile = Alpine.store('profile').userProfile;
            console.log("Profile settings init - Profile:", profile);
            
            if (profile) {
                // Split full_name into first_name and last_name
                const nameParts = (profile.full_name || '').split(' ');
                const firstName = nameParts[0] || '';
                const lastName = nameParts.slice(1).join(' ') || '';
                
                // Handle country - it can be either an object or a string
                let countryName = '';
                if (profile.country) {
                    if (typeof profile.country === 'object') {
                        countryName = profile.country.name || '';
                    } else {
                        countryName = profile.country;
                    }
                }
                
                this.formData = {
                    first_name: profile.first_name || firstName,
                    last_name: profile.last_name || lastName,
                    display_name: profile.profile?.display_name || '',
                    bio: profile.profile?.bio || '',
                    country: countryName,
                    phone_number: profile.phone_number || '',
                    website: profile.profile?.website || ''
                };
                
                console.log("Form data initialized:", this.formData);
            }
            
            // Wait for next tick to ensure DOM is updated, then reinitialize icons
            this.$nextTick(() => {
                if (typeof lucide !== 'undefined') {
                    lucide.createIcons();
                }
            });
        },
        
        async saveProfile() {
            this.saving = true;
            
            try {
                // Prepare the data to send
                const updateData = {
                    first_name: this.formData.first_name,
                    last_name: this.formData.last_name,
                    display_name: this.formData.display_name,
                    bio: this.formData.bio,
                    country: this.formData.country,
                    phone_number: this.formData.phone_number,
                    website: this.formData.website
                };
                
                // Remove empty values to avoid validation errors
                Object.keys(updateData).forEach(key => {
                    if (updateData[key] === '' || updateData[key] === null || updateData[key] === undefined) {
                        delete updateData[key];
                    }
                });
                
                console.log("Saving profile with data:", updateData);
                
                const result = await Alpine.store('profile').updateProfile(updateData);
                
                console.log("Profile updated successfully:", result);
                
                // Show success message
                Alpine.store('profile').profileApi.showMessage('Profile updated successfully!', 'success');
                
            } catch (error) {
                console.error('Failed to save profile:', error);
                
                // Show error message
                let errorMessage = 'Failed to update profile';
                if (error.response?.data?.error) {
                    const errors = error.response.data.error;
                    if (typeof errors === 'object') {
                        errorMessage = Object.values(errors).flat().join(', ');
                    } else {
                        errorMessage = errors;
                    }
                }
                
                Alpine.store('profile').profileApi.showMessage(errorMessage, 'error');
            } finally {
                this.saving = false;
            }
        }
    }));

    // ===== PROFILE PICTURE ======
    Alpine.data("profilePicture", () => ({
        profile_picture: "",
        isLoading: false,

        async init() {
            // Ensure profile store is loaded
            await Alpine.store("profile").loadProfile();
            const profile = Alpine.store("profile").userProfile;
            
            console.log("Profile picture init - Profile:", profile);
            console.log("Profile picture init - Profile picture:", profile?.profile?.profile_picture);

            // Get profile picture from profile data
            if (profile?.profile?.profile_picture) {
                // Make sure it's a full URL (add base URL if needed)
                let pictureUrl = profile.profile.profile_picture;
                if (pictureUrl && !pictureUrl.startsWith('http')) {
                    // Assuming your media files are served from the same domain
                    pictureUrl = window.location.origin + pictureUrl;
                }
                this.profile_picture = pictureUrl;
            }
            
            // Reinitialize icons
            this.$nextTick(() => {
                if (typeof lucide !== 'undefined') {
                    lucide.createIcons();
                }
            });
        },

        openFilePicker() {
            document.getElementById('profile-picture-input').click();
        },

        async handleFileSelect(event) {
            const file = event.target.files[0];
            if (!file) return;

            // Validate file type
            if (!file.type.match('image.*')) {
                profileApi.showMessage('Please select an image file', 'error'); // 👈 FIX
                return;
            }

            if (file.size > 2 * 1024 * 1024) {
                profileApi.showMessage('Image must be less than 2MB', 'error'); // 👈 FIX
                return;
            }

            // Show preview
            const reader = new FileReader();
            reader.onload = (e) => {
                this.profile_picture = e.target.result;
            };
            reader.readAsDataURL(file);

            // Upload to server
            await this.uploadProfilePicture(file);
            
            // Clear the input so the same file can be selected again
            event.target.value = '';
        },

        async uploadProfilePicture(file) {
            this.isLoading = true;
            try {
                const result = await Alpine.store('profile').uploadProfilePicture(file);
                if (result.profile_picture_url) {
                    // Update the profile picture URL
                    this.profile_picture = result.profile_picture_url;
                    // Also update the store
                    Alpine.store('profile').userProfile.profile.profile_picture = result.profile_picture_url;
                }
                profileApi.showMessage(
                    "Profile picture uploaded successfully",
                    "success"
                );
                return result;
            } catch (error) {
                console.error("Error uploading profile picture:", error);
                profileApi.showMessage("Error uploading profile picture", "error");
                throw error;
            } finally {
                this.isLoading = false;
            }
        },

        async deleteProfilePicture() {
            const swalResult = await Swal.fire({
                title: 'Delete Profile Picture?',
                text: "Are you sure you want to delete your profile picture?",
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#3085d6',
                cancelButtonColor: '#d33',
                confirmButtonText: 'Yes, delete!',
                cancelButtonText: 'Cancel'
            });

            if (!swalResult.isConfirmed) {
                console.log("🚫 Deletion cancelled by user");
                return;
            }

            this.isLoading = true;
            try {
                const result = await Alpine.store('profile').deleteProfilePicture();
                this.profile_picture = "";
                Alpine.store('profile').userProfile.profile.profile_picture = null;
                profileApi.showMessage(
                    "Profile picture deleted successfully",
                    "success"
                );
                return result;
            } catch (error) {
                console.error("Error deleting profile picture:", error);
                profileApi.showMessage("Error deleting profile picture", "error");
                throw error;
            } finally {
                this.isLoading = false;
            }
        }
    }));

    // ===== PHONE INPUT WITH COUNTRY CODE COMPONENT =====
    Alpine.data("phoneInput", () => ({
        selectedCountryCode: "",
        localNumber: "",

        async init() {
            // Ensure profile store is loaded
            await Alpine.store("profile").loadProfile();
            const profile = Alpine.store("profile").userProfile;
            
            console.log("Phone input init - Profile:", profile);
            console.log("Phone input init - Phone number:", profile?.phone_number);

            // 1. Try to extract from existing phone_number
            if (profile?.phone_number) {
                const match = profile.phone_number.match(/^\+\s*(\d+)\s*(.+)/);
                console.log("Phone number match result:", match);
                if (match) {
                    this.selectedCountryCode = match[1];
                    this.localNumber = match[2];
                }
            }

            // 2. Fallback: use user's country to find country code
            if (!this.selectedCountryCode && profile?.country) {
                const countryList = Alpine.store("profile").countryList;
                const userCountry = countryList.find(
                    (c) => c.name === profile.country
                );  
                console.log("User country match:", userCountry);
                if (userCountry?.phone_code) {
                    this.selectedCountryCode = userCountry.phone_code.toString();
                }
            }

            // 3. Default to US (+1)
            if (!this.selectedCountryCode) {
                this.selectedCountryCode = "1";
            }
            
            console.log("Selected country code:", this.selectedCountryCode);
            console.log("Local number:", this.localNumber);

            this.$nextTick(() => {
                if (window.lucide) lucide.createIcons();
            });
        },

        // Computed: full formatted phone number
        get fullPhoneNumber() {
            if (!this.selectedCountryCode || !this.localNumber.trim()) return "";
            return `+${this.selectedCountryCode}${this.localNumber.replace(/\D/g, "")}`;
        },
        
        // ADD THIS: Computed property for selectedCountry
        get selectedCountry() {
            const countryList = Alpine.store("profile").countryList;
            return countryList.find(
                country => country.phone_code && 
                        country.phone_code.toString() === this.selectedCountryCode
            );
        }
    }));

    // ===== SECURITY TAB COMPONENT =====
    Alpine.data("securitySettings", () => ({
        showOldPassword: false,
        showNewPassword: false,
        showConfirmPassword: false,
        passwordStrength: 0,
        passwordFeedback: "",
        changingPassword: false,
        formData: {
        old_password: "",
        new_password: "",
        confirm_password: "",
        },

        init() {
        // Watch for password changes and update icons
        this.$watch("formData.new_password", (newPassword) => {
            const password = newPassword || "";
            console.log("=== PASSWORD DEBUG ===");
            console.log("Password:", password);
            console.log(
            "Uppercase regex /[A-Z]/ test result:",
            /[A-Z]/.test(password)
            );
            console.log("Uppercase match result:", password.match(/[A-Z]/));
            console.log("Double-negated result:", !!password.match(/[A-Z]/));

            // Test with explicit character
            console.log('Contains "A"?', password.includes("A"));
            console.log("Contains any A-Z?", /[A-Z]/.test(password));
        });
        // Reinitialize icons
        this.$nextTick(() => {
            if (typeof lucide !== "undefined") {
            lucide.createIcons();
            }
        });
        },

        checkPasswordStrength(password) {
        if (!password) {
            this.passwordStrength = 0;
            this.passwordFeedback = "";
            return;
        }

        let strength = 0;

        // Length check
        if (password.length >= 8) strength += 25;

        // Character variety checks
        if (password.match(/[a-z]+/)) strength += 25;
        if (password.match(/[A-Z]+/)) strength += 25;
        if (password.match(/[0-9]+/) || password.match(/[^a-zA-Z0-9]+/))
            strength += 25;

        this.passwordStrength = strength;

        // Set feedback
        if (strength < 25) {
            this.passwordFeedback = "Very Weak";
        } else if (strength < 50) {
            this.passwordFeedback = "Weak";
        } else if (strength < 75) {
            this.passwordFeedback = "Moderate";
        } else {
            this.passwordFeedback = "Strong";
        }
        },

        async changePassword() {
        if (this.formData.new_password !== this.formData.confirm_password) {
            Alpine.store("profile").profileApi.showMessage(
            "Passwords do not match",
            "error",
            'error'
            );
            return;
        }

        if (this.formData.new_password.length < 8) {
            Alpine.store("profile").profileApi.showMessage(
            "Password must be at least 8 characters",
            "error",
            'error'
            );
            return;
        }

        this.changingPassword = true;

        try {
            await Alpine.store("profile").changePassword({
            old_password: this.formData.old_password,
            new_password: this.formData.new_password,
            confirm_password: this.formData.confirm_password,
            });

            // Reset form
            this.formData = {
            old_password: "",
            new_password: "",
            confirm_password: "",
            };
            this.passwordStrength = 0;
            this.passwordFeedback = "";
        } catch (error) {
            console.error("Password change failed:", error);
        } finally {
            this.changingPassword = false;
        }
        },
    }));

    // ===== TRADING TAB COMPONENT - TRADER SETTINGS (DEBUGGED) =====
    Alpine.data("traderSettings", () => ({
        isTrader: false,
        isActive: false,
        activating: false,
        saving: false,
        deactivating: false,

        traderData: {
            display_name: "",
            bio: "",
            risk_score: 5,
            minimum_investment: 100.0,
            total_followers: 0,
            total_trades: 0,
            win_rate: 0,
        },

        async init() {
            console.log("🔷 TraderSettings init called");
            await this.checkStatus();
            this.$nextTick(() => {
                if (typeof lucide !== "undefined") {
                    lucide.createIcons();
                }
            });
        },

        async checkStatus() {
            console.log("🔷 checkStatus called");
            try {
                const data = await profileApi.checkTraderStatus();
                console.log("📥 API Response:", JSON.stringify(data, null, 2));
                
                // Use Object.assign for proper reactivity
                Object.assign(this, {
                    isTrader: data.is_trader,
                    isActive: data.is_active
                });
                
                console.log("✅ State updated:", {
                    isTrader: this.isTrader,
                    isActive: this.isActive
                });
                
                if (data.is_trader) {
                    Object.assign(this.traderData, {
                        display_name: data.trader.display_name || "",
                        bio: data.trader.bio || "",
                        risk_score: data.trader.risk_score || 5,
                        minimum_investment: parseFloat(data.trader.minimum_investment) || 100.0,
                        total_followers: data.trader.followers_count || 0,
                        total_trades: data.trader.total_trades || 0,
                        win_rate: parseFloat(data.trader.win_rate) || 0,
                    });
                    console.log("📊 Trader data loaded:", this.traderData);
                } else {
                    Object.assign(this.traderData, {
                        display_name: "",
                        bio: "",
                        risk_score: 5,
                        minimum_investment: 100.0,
                        total_followers: 0,
                        total_trades: 0,
                        win_rate: 0,
                    });
                    console.log("🚫 No trader data (not a trader)");
                }
                
                // Refresh icons after state update
                this.$nextTick(() => {
                    console.log("🔄 Template re-evaluation triggered");
                    if (typeof lucide !== "undefined") {
                        lucide.createIcons();
                    }
                });
            } catch (error) {
                console.error("❌ Failed to check trader status:", error);
                profileApi.showMessage("Failed to check trader status", "error");
                Object.assign(this, {
                    isTrader: false,
                    isActive: false
                });
            }
        },

        async becomeTrader() {
            const swalResult = await Swal.fire({
                title: 'Activate Trader Account?',
                text: "Are you sure you want to become a trader? Others will be able to copy your trades.",
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#3085d6',
                cancelButtonColor: '#d33',
                confirmButtonText: 'Yes, activate!',
                cancelButtonText: 'Cancel'
            });

            if (!swalResult.isConfirmed) {
                console.log("🚫 Activation cancelled by user");
                return;
            }

            this.activating = true;
            console.log("🚀 Activating trader...");

            try {
                const apiResult = await profileApi.activateTrader({
                    display_name: this.traderData.display_name || "Trader" + Date.now().toString().slice(-4),
                    minimum_investment: this.traderData.minimum_investment,
                    risk_score: this.traderData.risk_score,
                    bio: this.traderData.bio || "",
                });

                console.log("📥 Activation API Response:", JSON.stringify(apiResult, null, 2));

                if (apiResult.trader) {
                    // Update state using Alpine's reactivity
                    Object.assign(this, {
                        isTrader: true,
                        isActive: true
                    });
                    
                    console.log("✅ Activation state updated:", {
                        isTrader: this.isTrader,
                        isActive: this.isActive
                    });
                    
                    // Refresh data from server to get complete trader info
                    await this.checkStatus();
                    
                    profileApi.showMessage("Trader account activated successfully!", 'success');
                    
                    // Refresh icons after DOM update
                    this.$nextTick(() => {
                        if (typeof lucide !== "undefined") {
                            lucide.createIcons();
                        }
                    });
                } else {
                    console.error("❌ No trader data in response");
                }
            } catch (error) {
                console.error("❌ Error activating trader:", error);
                profileApi.showMessage(error.message || "Failed to activate trader account", 'error');
            } finally {
                this.activating = false;
                console.log("🏁 Activation process complete");
            }
        },

        async deactivateTrader() {
            const swalResult = await Swal.fire({
                title: 'Deactivate Trader Account?',
                text: "Are you sure you want to deactivate your trader account? Your followers will no longer be able to copy your trades.",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                cancelButtonColor: '#3085d6',
                confirmButtonText: 'Yes, deactivate!',
                cancelButtonText: 'Cancel'
            });

            if (!swalResult.isConfirmed) {
                console.log("🚫 Deactivation cancelled by user");
                return;
            }

            this.deactivating = true;
            console.log("⏸️ Deactivating trader...");

            try {
                const apiResult = await profileApi.deactivateTrader();
                console.log("📥 Deactivation API Response:", JSON.stringify(apiResult, null, 2));

                if (apiResult.success) {
                    // Update state using Alpine's reactivity
                    Object.assign(this, {
                        isTrader: true,   // Profile still exists
                        isActive: false   // But inactive
                    });
                    
                    console.log("✅ Deactivation state updated:", {
                        isTrader: this.isTrader,
                        isActive: this.isActive
                    });
                    
                    profileApi.showMessage("Trader account deactivated successfully!", 'success');
                    
                    // Refresh icons after DOM update
                    this.$nextTick(() => {
                        console.log("🔄 Icons refreshed after deactivation");
                        if (typeof lucide !== "undefined") {
                            lucide.createIcons();
                        }
                    });
                } else {
                    console.error("❌ Deactivation failed - success=false");
                    profileApi.showMessage(apiResult.message || "Failed to deactivate", 'error');
                }
            } catch (error) {
                console.error("❌ Error deactivating trader:", error);
                profileApi.showMessage(error.message || "Failed to deactivate trader account", 'error');
            } finally {
                this.deactivating = false;
                console.log("🏁 Deactivation process complete");
            }
        },

        async reactivateTrader() {
            const swalResult = await Swal.fire({
                title: 'Reactivate Trader Account?',
                text: "Are you sure you want to reactivate your trader account? Your followers will be notified.",
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#3085d6',
                cancelButtonColor: '#d33',
                confirmButtonText: 'Yes, reactivate!',
                cancelButtonText: 'Cancel'
            });

            if (!swalResult.isConfirmed) {
                console.log("🚫 Reactivation cancelled by user");
                return;
            }

            this.activating = true;
            console.log("▶️ Reactivating trader...");

            try {
                const apiResult = await profileApi.reactivateTrader();
                console.log("📥 Reactivation API Response:", JSON.stringify(apiResult, null, 2));

                if (apiResult.success) {
                    // Update state using Alpine's reactivity
                    Object.assign(this, {
                        isTrader: true,
                        isActive: true
                    });
                    
                    console.log("✅ Reactivation state updated:", {
                        isTrader: this.isTrader,
                        isActive: this.isActive
                    });
                    
                    // Refresh data from server to get updated stats
                    await this.checkStatus();
                    
                    profileApi.showMessage("Trader account reactivated successfully!", 'success');
                    
                    // Refresh icons after DOM update
                    this.$nextTick(() => {
                        console.log("🔄 Icons refreshed after reactivation");
                        if (typeof lucide !== "undefined") {
                            lucide.createIcons();
                        }
                    });
                } else {
                    console.error("❌ Reactivation failed - success=false");
                    profileApi.showMessage(apiResult.message || "Failed to reactivate", 'error');
                }
            } catch (error) {
                console.error("❌ Error reactivating trader:", error);
                profileApi.showMessage(error.message || "Failed to reactivate trader account", 'error');
            } finally {
                this.activating = false;
                console.log("🏁 Reactivation process complete");
            }
        },

        async updateTraderSettings(event) {
            if (!this.isTrader) {
                console.warn("⚠️ Cannot update settings - not a trader");
                return;
            }

            this.saving = true;
            console.log("💾 Saving trader settings...");

            try {
                const result = await profileApi.updateTraderSettings({
                    display_name: this.traderData.display_name,
                    bio: this.traderData.bio,
                    risk_score: parseInt(this.traderData.risk_score),
                    minimum_investment: parseFloat(this.traderData.minimum_investment),
                });

                console.log("📥 Update API Response:", JSON.stringify(result, null, 2));

                if (result.trader) {
                    Object.assign(this.traderData, {
                        display_name: result.trader.display_name || "",
                        bio: result.trader.bio || "",
                        risk_score: result.trader.risk_score || 5,
                        minimum_investment: parseFloat(result.trader.minimum_investment) || 100.0,
                        total_followers: result.trader.followers_count || 0,
                        total_trades: result.trader.total_trades || 0,
                        win_rate: parseFloat(result.trader.win_rate) || 0,
                    });

                    console.log("✅ Settings updated successfully");
                    profileApi.showMessage("Trader settings updated successfully!", 'success');
                }
            } catch (error) {
                console.error("❌ Error updating trader settings:", error);
                profileApi.showMessage(error.message || "Failed to update settings", 'error');
            } finally {
                this.saving = false;
                console.log("🏁 Settings save complete");
            }
        },

        async getTraderStatistics(traderId) {
            try {
                const result = await profileApi.getTraderStatistics(traderId);
                this.traderStatistics = result;
            } catch (error) {
                console.error("❌ Error getting trader statistics:", error);
                profileApi.showMessage(error.message || "Failed to get trader statistics", 'error');
            }
        },
    }));

    console.log("Alpine components registered successfully");
    }

    // Initialize after DOM is loaded
    document.addEventListener("DOMContentLoaded", function () {
    console.log("DOM loaded, initializing profile handler...");

    // Load initial profile data if Alpine and store are ready
    if (
        typeof Alpine !== "undefined" &&
        Alpine.store &&
        Alpine.store("profile")
    ) {
        Alpine.store("profile").loadProfile();
    }

    // Initialize Lucide icons
    if (window.lucide) {
        lucide.createIcons();
    }
});

/**
 * BabyHelper Authentication Module
 * Reusable authentication and API communication layer
 * 
 * Usage:
 * - Include this file in your HTML: <script src="../js/auth.js"></script>
 * - Call BabyHelperAuth.init() on page load
 * - Use BabyHelperAuth.api.request() for authenticated API calls
 */

const BabyHelperAuth = (function() {
    'use strict';

    // Configuration
    const CONFIG = {
        API_TIMEOUT: 30000,
        RETRY_ATTEMPTS: 3,
        RETRY_DELAY: 1000,
        LOGIN_URL: '/',
        DASHBOARD_URL: '/dashboard',
        ONBOARDING_URL: '/onboarding'
    };

    // User state
    const userState = {
        isAuthenticated: false,
        user: {
            name: null,
            email: null,
            picture: null,
            idToken: null
        }
    };

    // Authentication methods
    const auth = {
        /**
         * Check if user is authenticated
         * @returns {boolean}
         */
        isAuthenticated() {
            const token = sessionStorage.getItem('idToken');
            return !!token;
        },

        /**
         * Get current user info
         * @returns {Object}
         */
        getCurrentUser() {
            return {
                name: sessionStorage.getItem('userName'),
                email: sessionStorage.getItem('userEmail'),
                picture: sessionStorage.getItem('userPicture'),
                idToken: sessionStorage.getItem('idToken')
            };
        },

        /**
         * Check authentication and redirect if needed
         * @param {Object} options - Configuration options
         * @param {boolean} options.requireAuth - Whether authentication is required
         * @param {string} options.redirectTo - Where to redirect if not authenticated
         * @param {boolean} options.redirectIfAuthenticated - Whether to redirect if already authenticated
         * @param {string} options.authenticatedRedirectTo - Where to redirect if authenticated (for login pages)
         * @returns {boolean} - Whether user is authenticated
         */
        checkAuth(options = {}) {
            const defaults = {
                requireAuth: true,
                redirectTo: CONFIG.LOGIN_URL,
                redirectIfAuthenticated: false,
                authenticatedRedirectTo: CONFIG.DASHBOARD_URL
            };
            const settings = { ...defaults, ...options };

            const isAuth = this.isAuthenticated();

            // Handle unauthenticated users
            if (!isAuth && settings.requireAuth) {
                // Store the intended destination
                sessionStorage.setItem('redirectAfterLogin', window.location.pathname);

                // Ensure redirect happens immediately
                console.log('User not authenticated, redirecting to:', settings.redirectTo);
                window.location.replace(settings.redirectTo);
                return false;
            }

            // Handle authenticated users on login page
            if (isAuth && settings.redirectIfAuthenticated) {
                // Check if there's a stored redirect destination
                const redirectTo = sessionStorage.getItem('redirectAfterLogin') || settings.authenticatedRedirectTo;
                sessionStorage.removeItem('redirectAfterLogin');
                window.location.replace(redirectTo);
                return true;
            }

            if (isAuth) {
                userState.isAuthenticated = true;
                userState.user = this.getCurrentUser();
            }

            return isAuth;
        },

        /**
         * Logout user
         * @param {string} redirectTo - Where to redirect after logout
         */
        logout(redirectTo = CONFIG.LOGIN_URL) {
            // Clear session storage
            sessionStorage.clear();

            // Reset user state
            userState.isAuthenticated = false;
            userState.user = {
                name: null,
                email: null,
                picture: null,
                idToken: null
            };

            // Redirect using replace to prevent back button issues
            window.location.replace(redirectTo);
        },

        /**
         * Store user session
         * @param {Object} userData - User data to store
         */
        storeSession(userData) {
            if (userData.idToken) sessionStorage.setItem('idToken', userData.idToken);
            if (userData.userName) sessionStorage.setItem('userName', userData.userName);
            if (userData.userEmail) sessionStorage.setItem('userEmail', userData.userEmail);
            if (userData.userPicture) sessionStorage.setItem('userPicture', userData.userPicture);

            // Update state
            userState.isAuthenticated = true;
            userState.user = this.getCurrentUser();
        }
    };

    // API communication layer
    const api = {
        /**
         * Get authentication token
         * @returns {string|null}
         */
        getAuthToken() {
            return sessionStorage.getItem('idToken') || window.authToken || null;
        },

        /**
         * Get API headers with authentication
         * @returns {Object}
         */
        getHeaders() {
            const token = this.getAuthToken();
            if (!token) {
                throw new Error('No authentication token found');
            }
            return {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            };
        },

        /**
         * Parse error response from API
         * @param {Response} response
         * @returns {Promise<string>}
         */
        async parseErrorResponse(response) {
            let errorMessage = `Request failed (${response.status})`;

            try {
                const errorData = await response.json();

                if (errorData.detail) {
                    if (typeof errorData.detail === 'string') {
                        errorMessage = errorData.detail;
                    } else if (Array.isArray(errorData.detail)) {
                        errorMessage = errorData.detail
                            .map(err => {
                                const field = err.loc?.[err.loc.length - 1] || 'field';
                                return `${field}: ${err.msg}`;
                            })
                            .join(', ');
                    }
                } else if (errorData.message) {
                    errorMessage = errorData.message;
                }
            } catch (e) {
                errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            }

            return errorMessage;
        },

        /**
         * Make authenticated API request with retry
         * @param {string} url - API endpoint
         * @param {Object} options - Fetch options
         * @returns {Promise<Response>}
         */
        async request(url, options = {}) {
            // Ensure user is authenticated
            if (!auth.isAuthenticated()) {
                auth.logout();
                throw new Error('User not authenticated');
            }

            const retryKey = `${options.method || 'GET'}_${url}`;
            let retryCount = 0;

            for (let attempt = 0; attempt < CONFIG.RETRY_ATTEMPTS; attempt++) {
                try {
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), CONFIG.API_TIMEOUT);

                    const response = await fetch(url, {
                        ...options,
                        headers: {
                            ...this.getHeaders(),
                            ...options.headers
                        },
                        signal: controller.signal
                    });

                    clearTimeout(timeoutId);

                    // Handle authentication errors
                    if (response.status === 401 || response.status === 403) {
                        auth.logout();
                        throw new Error('Authentication expired');
                    }

                    return response;

                } catch (error) {
                    retryCount++;

                    // Don't retry on authentication errors
                    if (error.message === 'Authentication expired') {
                        throw error;
                    }

                    // Last attempt or non-retryable error
                    if (attempt === CONFIG.RETRY_ATTEMPTS - 1 || error.name === 'AbortError') {
                        throw error;
                    }

                    // Wait before retry with exponential backoff
                    await new Promise(resolve =>
                        setTimeout(resolve, CONFIG.RETRY_DELAY * Math.pow(2, attempt))
                    );
                }
            }
        },

        /**
         * Common API endpoints
         */
        endpoints: {
            async getUserProfile() {
                const response = await api.request('/auth/me');
                if (!response.ok) {
                    const error = await api.parseErrorResponse(response);
                    throw new Error(error);
                }
                return response.json();
            },

            async updateUserProfile(data) {
                const response = await api.request('/auth/me', {
                    method: 'PUT',
                    body: JSON.stringify(data)
                });
                if (!response.ok) {
                    const error = await api.parseErrorResponse(response);
                    throw new Error(error);
                }
                return response.json();
            },

            async getBabies() {
                const response = await api.request('/baby');
                if (!response.ok) {
                    const error = await api.parseErrorResponse(response);
                    throw new Error(error);
                }
                return response.json();
            }
        }
    };

    // UI helper methods
    const ui = {
        /**
         * Update user info in UI elements
         * @param {Object} options - Element IDs to update
         */
        updateUserInfo(options = {}) {
            const defaults = {
                nameElementId: 'userName',
                emailElementId: 'userEmail',
                pictureElementId: 'userPicture'
            };
            const settings = { ...defaults, ...options };

            const user = auth.getCurrentUser();

            // Update name
            if (settings.nameElementId && user.name) {
                const nameEl = document.getElementById(settings.nameElementId);
                if (nameEl) nameEl.textContent = user.name;
            }

            // Update email
            if (settings.emailElementId && user.email) {
                const emailEl = document.getElementById(settings.emailElementId);
                if (emailEl) emailEl.textContent = user.email;
            }

            // Update picture
            if (settings.pictureElementId && user.picture) {
                const pictureEl = document.getElementById(settings.pictureElementId);
                if (pictureEl) pictureEl.src = user.picture;
            }
        },

        /**
         * Show authentication error
         * @param {string} message
         */
        showAuthError(message) {
            // You can customize this to use your toast/notification system
            console.error('Authentication Error:', message);
            // Don't use alert in production - use your notification system
            if (window.location.hostname === 'localhost') {
                alert(`Authentication Error: ${message}`);
            }
        }
    };

    // Initialization
    const init = function(options = {}) {
        const defaults = {
            requireAuth: true,
            updateUI: true,
            onAuthSuccess: null,
            onAuthFail: null,
            redirectIfAuthenticated: false,
            authenticatedRedirectTo: CONFIG.DASHBOARD_URL
        };
        const settings = { ...defaults, ...options };

        try {
            // Check authentication
            const isAuth = auth.checkAuth({
                requireAuth: settings.requireAuth,
                redirectTo: settings.redirectTo || CONFIG.LOGIN_URL,
                redirectIfAuthenticated: settings.redirectIfAuthenticated,
                authenticatedRedirectTo: settings.authenticatedRedirectTo
            });

            if (isAuth) {
                // Update UI with user info
                if (settings.updateUI) {
                    ui.updateUserInfo(settings.uiElements);
                }

                // Call success callback
                if (settings.onAuthSuccess && typeof settings.onAuthSuccess === 'function') {
                    settings.onAuthSuccess(userState.user);
                }
            } else if (!settings.requireAuth && settings.onAuthFail && typeof settings.onAuthFail === 'function') {
                // Only call fail callback if auth is not required
                settings.onAuthFail();
            }

            return isAuth;

        } catch (error) {
            console.error('Authentication initialization error:', error);
            ui.showAuthError(error.message);

            // If there's an error and auth is required, redirect to login
            if (settings.requireAuth) {
                setTimeout(() => {
                    window.location.replace(settings.redirectTo || CONFIG.LOGIN_URL);
                }, 1000);
            }

            return false;
        }
    };

    // Public API
    return {
        init,
        auth,
        api,
        ui,
        userState,
        CONFIG
    };
})();

// Auto-initialize on DOMContentLoaded if data-auto-init is present
document.addEventListener('DOMContentLoaded', function() {
    const scriptTag = document.querySelector('script[src*="auth.js"][data-auto-init="true"]');
    if (scriptTag) {
        // Prevent double initialization
        if (window.BabyHelperAuthInitialized) {
            return;
        }
        window.BabyHelperAuthInitialized = true;

        // Get configuration from data attributes
        const requireAuth = scriptTag.getAttribute('data-require-auth') !== 'false';
        const redirectTo = scriptTag.getAttribute('data-redirect-to');
        const updateUI = scriptTag.getAttribute('data-update-ui') !== 'false';
        const pageType = scriptTag.getAttribute('data-page-type') || 'protected';

        // Configure based on page type
        let initOptions = {
            requireAuth: requireAuth,
            updateUI: updateUI
        };

        if (pageType === 'login') {
            // Login page should redirect authenticated users to dashboard
            initOptions.requireAuth = false;
            initOptions.redirectIfAuthenticated = true;
            initOptions.authenticatedRedirectTo = BabyHelperAuth.CONFIG.DASHBOARD_URL;
        } else if (requireAuth && redirectTo) {
            // Protected pages redirect to specified location if not authenticated
            initOptions.redirectTo = redirectTo;
        }

        BabyHelperAuth.init(initOptions);
    }
});
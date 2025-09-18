/**
 * Sistema de Autenticação - Valida SaaS
 * Gerencia login, cadastro e validação de formulários
 */

class AuthManager {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupPasswordStrength();
        this.setupFormValidation();
    }

    setupEventListeners() {
        // Login Form
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => this.handleLogin(e));
        }

        // Register Form
        const registerForm = document.getElementById('registerForm');
        if (registerForm) {
            registerForm.addEventListener('submit', (e) => this.handleRegister(e));
        }

        // Password confirmation validation
        const confirmPassword = document.getElementById('confirmPassword');
        if (confirmPassword) {
            confirmPassword.addEventListener('input', () => this.validatePasswordMatch());
        }

        // Real-time email validation
        const emailInput = document.getElementById('email');
        if (emailInput) {
            emailInput.addEventListener('blur', () => this.validateEmail());
        }
    }

    setupPasswordStrength() {
        const passwordInput = document.getElementById('password');
        if (passwordInput) {
            passwordInput.addEventListener('input', () => this.updatePasswordStrength());
        }
    }

    setupFormValidation() {
        // Real-time validation for all inputs
        const inputs = document.querySelectorAll('input[required]');
        inputs.forEach(input => {
            input.addEventListener('blur', () => this.validateField(input));
        });
    }

    async handleLogin(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const email = formData.get('email');
        const password = formData.get('password');

        // Validate form
        if (!this.validateLoginForm(email, password)) {
            return;
        }

        try {
            this.showLoading('loginBtn', 'Entrando...');
            
            // Call login API
            const response = await this.loginUser(email, password);
            
            if (response.success) {
                this.showSuccess('Login realizado com sucesso!');
                
                // Store auth token and API key
                if (response.token) {
                    localStorage.setItem('auth_token', response.token);
                    localStorage.setItem('session_token', response.token);
                }
                
                if (response.api_key && response.api_key.startsWith('rcp_')) {
                    localStorage.setItem('api_key', response.api_key);
                }
                
                localStorage.setItem('user_email', email);
                localStorage.setItem('user_id', response.user_id || '');
                localStorage.setItem('user_name', response.name || email.split('@')[0]);
                
                // Redirect to dashboard
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 1000);
            } else {
                this.showError(response.message || 'Erro ao fazer login');
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showError(error.message || 'Erro ao fazer login. Verifique suas credenciais.');
        } finally {
            this.hideLoading('loginBtn', 'Entrar');
        }
    }

    async handleRegister(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const email = formData.get('email');
        const password = formData.get('password');
        const confirmPassword = formData.get('confirmPassword');
        const terms = formData.get('terms');

        // Validate form
        if (!this.validateRegisterForm(email, password, confirmPassword, terms)) {
            return;
        }

        try {
            this.showLoading('registerBtn', 'Criando conta...');
            
            // Call register API
            const response = await this.registerUser(email, password);
            
            if (response.success) {
                this.showSuccess(response.message || 'Conta criada com sucesso! Você ganhou 7 dias de trial.');
                
                // Store auth token and API key
                if (response.token) {
                    localStorage.setItem('auth_token', response.token);
                    localStorage.setItem('session_token', response.token);
                }
                
                if (response.api_key && response.api_key.startsWith('rcp_')) {
                    localStorage.setItem('api_key', response.api_key);
                }
                
                localStorage.setItem('user_email', email);
                localStorage.setItem('user_id', response.user_id || '');
                localStorage.setItem('user_name', response.name || email.split('@')[0]);
                
                // Redirect to dashboard
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 1500);
            } else {
                this.showError(response.message || 'Erro ao criar conta');
            }
        } catch (error) {
            console.error('Register error:', error);
            this.showError(error.message || 'Erro ao criar conta. Tente novamente.');
        } finally {
            this.hideLoading('registerBtn', 'Cadastrar');
        }
    }

    validateLoginForm(email, password) {
        let isValid = true;

        // Clear previous errors
        this.clearErrors();

        if (!email || !this.isValidEmail(email)) {
            this.showFieldError('email', 'E-mail inválido');
            isValid = false;
        }

        if (!password || password.length < 6) {
            this.showFieldError('password', 'Senha deve ter pelo menos 6 caracteres');
            isValid = false;
        }

        return isValid;
    }

    validateRegisterForm(email, password, confirmPassword, terms) {
        let isValid = true;

        // Clear previous errors
        this.clearErrors();

        // Email validation
        if (!email || !this.isValidEmail(email)) {
            this.showFieldError('email', 'E-mail inválido');
            isValid = false;
        }

        // Password validation
        if (!password || password.length < 8) {
            this.showFieldError('password', 'Senha deve ter pelo menos 8 caracteres');
            isValid = false;
        } else if (!this.isStrongPassword(password)) {
            this.showFieldError('password', 'Senha deve conter letras, números e símbolos');
            isValid = false;
        }

        // Password confirmation
        if (password !== confirmPassword) {
            this.showFieldError('confirmPassword', 'Senhas não coincidem');
            isValid = false;
        }

        // Terms validation
        if (!terms) {
            this.showError('Você deve aceitar os termos de uso');
            isValid = false;
        }

        return isValid;
    }

    validateField(input) {
        const value = input.value.trim();
        const fieldName = input.name;

        switch (fieldName) {
            case 'email':
                return this.validateEmail();
            case 'password':
                return this.validatePassword();
            case 'confirmPassword':
                return this.validatePasswordMatch();
            default:
                return true;
        }
    }

    validateEmail() {
        const emailInput = document.getElementById('email');
        const email = emailInput.value.trim();
        
        if (!email) {
            this.showFieldError('email', 'E-mail é obrigatório');
            return false;
        }
        
        if (!this.isValidEmail(email)) {
            this.showFieldError('email', 'E-mail inválido');
            return false;
        }
        
        this.clearFieldError('email');
        return true;
    }

    validatePassword() {
        const passwordInput = document.getElementById('password');
        const password = passwordInput.value;
        
        if (!password) {
            this.showFieldError('password', 'Senha é obrigatória');
            return false;
        }
        
        if (password.length < 8) {
            this.showFieldError('password', 'Senha deve ter pelo menos 8 caracteres');
            return false;
        }
        
        if (!this.isStrongPassword(password)) {
            this.showFieldError('password', 'Senha deve conter letras, números e símbolos');
            return false;
        }
        
        this.clearFieldError('password');
        return true;
    }

    validatePasswordMatch() {
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        
        if (confirmPassword && password !== confirmPassword) {
            this.showFieldError('confirmPassword', 'Senhas não coincidem');
            return false;
        }
        
        this.clearFieldError('confirmPassword');
        return true;
    }

    updatePasswordStrength() {
        const password = document.getElementById('password').value;
        const strengthBar = document.getElementById('password-strength-bar');
        
        if (!strengthBar) return;

        const strength = this.calculatePasswordStrength(password);
        
        // Remove all strength classes
        strengthBar.className = 'password-strength-bar';
        
        if (password.length === 0) {
            return;
        }
        
        if (strength < 25) {
            strengthBar.classList.add('strength-weak');
        } else if (strength < 50) {
            strengthBar.classList.add('strength-fair');
        } else if (strength < 75) {
            strengthBar.classList.add('strength-good');
        } else {
            strengthBar.classList.add('strength-strong');
        }
    }

    calculatePasswordStrength(password) {
        let strength = 0;
        
        // Length check
        if (password.length >= 8) strength += 20;
        if (password.length >= 12) strength += 10;
        
        // Character variety
        if (/[a-z]/.test(password)) strength += 10;
        if (/[A-Z]/.test(password)) strength += 10;
        if (/[0-9]/.test(password)) strength += 10;
        if (/[^A-Za-z0-9]/.test(password)) strength += 20;
        
        // Pattern checks
        if (password.length >= 8 && /[a-z]/.test(password) && /[A-Z]/.test(password) && /[0-9]/.test(password)) {
            strength += 20;
        }
        
        return Math.min(strength, 100);
    }

    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    isStrongPassword(password) {
        // At least 8 characters, 1 lowercase, 1 uppercase, 1 number
        const strongRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d@$!%*?&]{8,}$/;
        return strongRegex.test(password);
    }

    showFieldError(fieldName, message) {
        const errorElement = document.getElementById(`${fieldName}-error`);
        const inputElement = document.getElementById(fieldName);
        
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.classList.remove('hidden');
        }
        
        if (inputElement) {
            inputElement.classList.add('error');
        }
    }

    clearFieldError(fieldName) {
        const errorElement = document.getElementById(`${fieldName}-error`);
        const inputElement = document.getElementById(fieldName);
        
        if (errorElement) {
            errorElement.classList.add('hidden');
        }
        
        if (inputElement) {
            inputElement.classList.remove('error');
        }
    }

    clearErrors() {
        const errorElements = document.querySelectorAll('[id$="-error"]');
        errorElements.forEach(element => {
            element.classList.add('hidden');
        });
        
        const inputElements = document.querySelectorAll('.input-field');
        inputElements.forEach(element => {
            element.classList.remove('error');
        });
    }

    showLoading(buttonId, loadingText) {
        const button = document.getElementById(buttonId);
        if (button) {
            button.disabled = true;
            const textElement = document.getElementById(`${buttonId}Text`);
            const spinnerElement = document.getElementById(`${buttonId}Spinner`);
            
            if (textElement) textElement.classList.add('hidden');
            if (spinnerElement) spinnerElement.classList.remove('hidden');
        }
    }

    hideLoading(buttonId, normalText) {
        const button = document.getElementById(buttonId);
        if (button) {
            button.disabled = false;
            const textElement = document.getElementById(`${buttonId}Text`);
            const spinnerElement = document.getElementById(`${buttonId}Spinner`);
            
            if (textElement) textElement.classList.remove('hidden');
            if (spinnerElement) spinnerElement.classList.add('hidden');
        }
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showNotification(message, type) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 z-50 px-6 py-3 rounded-lg shadow-lg transition-all duration-300 ${
            type === 'success' 
                ? 'bg-green-600 text-white' 
                : 'bg-red-600 text-white'
        }`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    // API calls para autenticação
    async loginUser(email, password) {
        try {
            const response = await fetch('/api/v1/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email, password })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Erro ao fazer login');
            }
            
            return data;
        } catch (error) {
            console.error('Login API error:', error);
            throw error;
        }
    }

    async registerUser(email, password) {
        try {
            const response = await fetch('/api/v1/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    email, 
                    password,
                    name: email.split('@')[0] // Usar parte do email como nome
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Erro ao criar conta');
            }
            
            return data;
        } catch (error) {
            console.error('Register API error:', error);
            throw error;
        }
    }
}

// Utility functions
function closeModal() {
    // If we're in a modal context, close it
    if (window.history.length > 1) {
        window.history.back();
    } else {
        window.location.href = '/';
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new AuthManager();
});

// Handle keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // ESC key to close modal
    if (e.key === 'Escape') {
        closeModal();
    }
    
    // Ctrl+K for search (placeholder)
    if (e.ctrlKey && e.key === 'k') {
        e.preventDefault();
        console.log('Search shortcut triggered');
    }
});

/**
 * JavaScript para página de Perfil do Usuário
 * Gerencia dados pessoais, configurações e segurança
 */

class PerfilManager {
    constructor() {
        this.userData = null;
        this.isEditing = false;
        this.originalData = null;
        
        this.init();
    }

    async init() {
        console.log('🚀 Inicializando PerfilManager...');
        
        // Debug dos tokens
        this.debugTokenInfo();
        
        // Validar autenticação antes de prosseguir
        if (!this.validateAuthentication()) {
            console.error('❌ Usuário não autenticado - redirecionando para login');
            window.location.href = '/login';
            return;
        }
        
        // Verificar se a sessão ainda é válida
        const sessionValid = await this.checkUserSession();
        if (!sessionValid) {
            console.error('❌ Sessão inválida - redirecionando para login');
            window.location.href = '/login';
            return;
        }
        
        try {
            this.setupEventListeners();
            await this.loadUserData();
            this.renderProfile();
            this.setupFormValidation();
        } catch (error) {
            console.error('❌ Erro ao inicializar PerfilManager:', error);
            this.showError('Erro ao carregar dados do perfil');
        }
    }

    validateAuthentication() {
        console.log('🔐 Validando autenticação...');
        
        // Verificar se AuthUtils está disponível
        if (typeof AuthUtils === 'undefined') {
            console.error('❌ AuthUtils não está disponível');
            return false;
        }
        
        // Verificar se há token válido
        const token = AuthUtils.getAuthToken();
        if (!token) {
            console.error('❌ Nenhum token de autenticação encontrado');
            return false;
        }
        
        // Verificar se o token parece ser um JWT válido
        if (!token.includes('.') || token.split('.').length !== 3) {
            console.error('❌ Token não é um JWT válido');
            return false;
        }
        
        console.log('✅ Token de autenticação válido encontrado');
        return true;
    }

    async checkUserSession() {
        console.log('🔍 Verificando sessão do usuário...');
        
        try {
            // Tentar fazer uma requisição simples para verificar se o token ainda é válido
            const response = await AuthUtils.authenticatedFetch('/api/v1/auth/me');
            
            if (response.status === 401) {
                console.error('❌ Token expirado ou inválido');
                return false;
            }
            
            if (!response.ok) {
                console.error('❌ Erro na verificação da sessão:', response.status);
                return false;
            }
            
            console.log('✅ Sessão do usuário válida');
            return true;
            
        } catch (error) {
            console.error('❌ Erro ao verificar sessão:', error);
            return false;
        }
    }

    debugTokenInfo() {
        console.log('🔍 Informações de debug dos tokens:');
        
        const authToken = localStorage.getItem('auth_token');
        const sessionToken = localStorage.getItem('session_token');
        
        console.log('📱 auth_token:', authToken ? `${authToken.substring(0, 20)}...` : 'Não encontrado');
        console.log('📱 session_token:', sessionToken ? `${sessionToken.substring(0, 20)}...` : 'Não encontrado');
        
        if (authToken) {
            try {
                const payload = JSON.parse(atob(authToken.split('.')[1]));
                console.log('🔓 Payload do JWT:', payload);
                console.log('⏰ Expira em:', new Date(payload.exp * 1000));
                console.log('👤 Usuário:', payload.email);
            } catch (e) {
                console.error('❌ Erro ao decodificar JWT:', e);
            }
        }
    }

    setupEventListeners() {
        // Botões de edição
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-edit-profile]')) {
                this.handleEditProfile();
            }
            if (e.target.matches('[data-save-profile]')) {
                this.handleSaveProfile();
            }
            if (e.target.matches('[data-cancel-edit]')) {
                this.handleCancelEdit();
            }
            if (e.target.matches('[data-change-password]')) {
                this.handleChangePassword();
            }
            if (e.target.matches('[data-enable-2fa]')) {
                this.handleEnable2FA();
            }
            if (e.target.matches('[data-disable-2fa]')) {
                this.handleDisable2FA();
            }
            if (e.target.matches('[data-delete-account]')) {
                this.handleDeleteAccount();
            }
            if (e.target.matches('[data-logout]')) {
                this.handleLogout();
            }
        });

        // Validação em tempo real
        const nameInput = document.querySelector('[data-profile-name]');
        const emailInput = document.querySelector('[data-profile-email]');
        
        if (nameInput) {
            nameInput.addEventListener('input', () => this.validateField('name'));
        }
        if (emailInput) {
            emailInput.addEventListener('input', () => this.validateField('email'));
        }

        // Upload de avatar
        const avatarInput = document.querySelector('[data-avatar-input]');
        if (avatarInput) {
            avatarInput.addEventListener('change', (e) => this.handleAvatarUpload(e));
        }

        // Configurações de notificação
        document.addEventListener('change', (e) => {
            if (e.target.matches('[data-notification-setting]')) {
                this.handleNotificationChange(e.target);
            }
            if (e.target.matches('[data-credit-alert-threshold]')) {
                this.handleCreditAlertChange(e.target);
            }
        });
    }

    async loadUserData() {
        try {
            console.log('🔍 Carregando dados do usuário...');
            
            // Verificar autenticação novamente antes da requisição
            if (!this.validateAuthentication()) {
                throw new Error('Usuário não autenticado');
            }
            
            const data = await AuthUtils.authenticatedFetchJSON('/api/v1/auth/me');
            console.log('✅ Dados recebidos da API:', data);
            
            // Validar se os dados estão no formato esperado
            if (!data || typeof data !== 'object') {
                throw new Error('Dados inválidos recebidos da API');
            }
            
            this.userData = data;
            console.log('✅ Dados do usuário carregados:', this.userData);
            
        } catch (error) {
            console.error('❌ Erro ao carregar dados do usuário:', error);
            
            // Se for erro de autenticação, redirecionar para login
            if (error.message.includes('Token') || error.message.includes('autenticado') || error.message.includes('401')) {
                console.error('❌ Erro de autenticação - redirecionando para login');
                window.location.href = '/login';
                return;
            }
            
            this.userData = null;
            this.showErrorState('Erro ao carregar dados do perfil');
        }
    }

    renderProfile() {
        if (!this.userData) {
            console.log('❌ Nenhum dado do usuário para renderizar');
            return;
        }

        console.log('🎨 Renderizando perfil com dados:', this.userData);
        
        // Renderizar informações básicas
        this.renderBasicInfo();
        this.renderSecuritySettings();
        this.renderNotificationSettings();
        this.renderAccountStats();
        this.renderCreditSettings();
    }

    renderBasicInfo() {
        console.log('👤 Renderizando informações básicas...');
        
        const nameElement = document.querySelector('[data-profile-name]');
        const nameDisplayElement = document.querySelector('[data-profile-name-display]');
        const emailElement = document.querySelector('[data-profile-email]');
        const avatarElement = document.querySelector('[data-profile-avatar]');
        const memberSinceElement = document.querySelector('[data-member-since]');

        console.log('📝 Nome:', this.userData.name);
        console.log('📧 Email:', this.userData.email);
        console.log('📅 Criado em:', this.userData.created_at);

        if (nameElement) {
            nameElement.value = this.userData.name || '';
            nameElement.placeholder = this.userData.name ? 'Nome carregado' : 'Nome não encontrado';
        }
        if (nameDisplayElement) {
            nameDisplayElement.textContent = this.userData.name || 'Nome não encontrado';
        }
        if (emailElement) {
            emailElement.value = this.userData.email || '';
            emailElement.placeholder = this.userData.email ? 'Email carregado' : 'Email não encontrado';
        }
        if (avatarElement) {
            avatarElement.src = this.userData.avatar || this.getDefaultAvatar();
        }
        if (memberSinceElement) {
            memberSinceElement.textContent = this.userData.created_at ? this.formatDate(this.userData.created_at) : 'Data não encontrada';
        }
    }

    renderSecuritySettings() {
        const twoFactorStatus = document.querySelector('[data-2fa-status]');
        const twoFactorToggle = document.querySelector('[data-2fa-toggle]');
        const lastLoginElement = document.querySelector('[data-last-login]');

        if (twoFactorStatus) {
            twoFactorStatus.textContent = this.userData.two_factor_enabled ? 'Ativado' : 'Desativado';
            twoFactorStatus.className = this.userData.two_factor_enabled ? 'status-badge success' : 'status-badge warning';
        }

        if (twoFactorToggle) {
            twoFactorToggle.innerHTML = this.userData.two_factor_enabled ? 
                '<button class="btn btn-outline" data-disable-2fa>Desativar 2FA</button>' :
                '<button class="btn btn-primary" data-enable-2fa>Ativar 2FA</button>';
        }

        if (lastLoginElement) {
            lastLoginElement.textContent = this.formatDateTime(this.userData.last_login_at);
        }
    }

    renderNotificationSettings() {
        const settings = this.userData.notification_settings || {
            email_notifications: true,
            api_alerts: true,
            billing_alerts: true,
            security_alerts: true,
            marketing_emails: false
        };

        Object.keys(settings).forEach(key => {
            const checkbox = document.querySelector(`[data-notification-setting="${key}"]`);
            if (checkbox) {
                checkbox.checked = settings[key];
            }
        });
    }

    renderAccountStats() {
        console.log('📊 Renderizando estatísticas da conta...');
        
        // Atualizar elementos com dados reais
        const creditsAvailable = document.querySelector('[data-profile-credits-available]');
        const creditsUsed = document.querySelector('[data-profile-credits-used]');
        const monthlyQueries = document.querySelector('[data-profile-monthly-queries]');

        console.log('💰 Créditos disponíveis:', this.userData.credits_available);
        console.log('💸 Créditos usados:', this.userData.credits_used_total);
        console.log('🔍 Consultas mensais:', this.userData.monthly_queries);

        if (creditsAvailable) {
            if (this.userData.credits_available !== undefined && this.userData.credits_available !== null) {
                creditsAvailable.textContent = `R$ ${this.userData.credits_available.toFixed(2)}`;
            } else {
                creditsAvailable.textContent = 'R$ 0,00';
            }
        }
        
        if (creditsUsed) {
            if (this.userData.credits_used_total !== undefined && this.userData.credits_used_total !== null) {
                creditsUsed.textContent = `R$ ${this.userData.credits_used_total.toFixed(2)}`;
            } else {
                creditsUsed.textContent = 'R$ 0,00';
            }
        }
        
        if (monthlyQueries) {
            if (this.userData.monthly_queries !== undefined && this.userData.monthly_queries !== null) {
                monthlyQueries.textContent = this.userData.monthly_queries.toLocaleString();
            } else {
                monthlyQueries.textContent = '0';
            }
        }

        // Renderizar estatísticas adicionais se necessário
        const statsContainer = document.querySelector('[data-account-stats]');
        if (statsContainer) {
            statsContainer.innerHTML = `
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div class="bg-[#192633] rounded-lg p-4 border border-[#324d67]">
                        <div class="text-[#92adc9] text-sm">Total de Consultas</div>
                        <div class="text-white text-2xl font-bold">${(this.userData.total_queries || 0).toLocaleString()}</div>
                    </div>
                    <div class="bg-[#192633] rounded-lg p-4 border border-[#324d67]">
                        <div class="text-[#92adc9] text-sm">Chaves de API</div>
                        <div class="text-white text-2xl font-bold">${this.userData.api_keys_count || 0}</div>
                    </div>
                    <div class="bg-[#192633] rounded-lg p-4 border border-[#324d67]">
                        <div class="text-[#92adc9] text-sm">Dias de Assinatura</div>
                        <div class="text-white text-2xl font-bold">${this.userData.subscription_days || 0}</div>
                    </div>
                    <div class="bg-[#192633] rounded-lg p-4 border border-[#324d67]">
                        <div class="text-[#92adc9] text-sm">Última Consulta</div>
                        <div class="text-white text-sm">${this.userData.last_query_date ? this.formatDate(this.userData.last_query_date) : 'Nunca'}</div>
                    </div>
                </div>
            `;
        }
    }

    renderCreditSettings() {
        console.log('💰 Renderizando configurações de créditos...');
        
        // Configurar o valor do limite de alerta
        const thresholdSelect = document.querySelector('[data-credit-alert-threshold]');
        if (thresholdSelect && this.userData.credit_alert_threshold) {
            thresholdSelect.value = this.userData.credit_alert_threshold;
            console.log('Limite de alerta configurado:', this.userData.credit_alert_threshold);
        }
    }

    handleEditProfile() {
        this.isEditing = true;
        this.originalData = { ...this.userData };
        
        // Habilitar campos de edição
        const editableFields = document.querySelectorAll('[data-profile-name], [data-profile-email]');
        editableFields.forEach(field => {
            field.disabled = false;
            field.classList.add('editing');
        });

        // Mostrar botões de salvar/cancelar
        const editBtn = document.querySelector('[data-edit-profile]');
        const saveBtn = document.querySelector('[data-save-profile]');
        const cancelBtn = document.querySelector('[data-cancel-edit]');

        if (editBtn) editBtn.style.display = 'none';
        if (saveBtn) saveBtn.style.display = 'inline-block';
        if (cancelBtn) cancelBtn.style.display = 'inline-block';

        this.showSuccess('Modo de edição ativado');
    }

    async handleSaveProfile() {
        try {
            this.showLoading('Salvando alterações...');

            const formData = {
                name: document.querySelector('[data-profile-name]')?.value,
                email: document.querySelector('[data-profile-email]')?.value
            };

            // Validação
            if (!this.validateProfileForm(formData)) {
                return;
            }

            const response = await AuthUtils.authenticatedFetch('/api/v1/auth/profile', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Erro ao salvar perfil');
            }

            const data = await response.json();
            
            // Atualizar dados locais
            this.userData.name = formData.name;
            this.userData.email = formData.email;
            
            this.isEditing = false;
            this.exitEditMode();
            this.renderProfile();
            
            this.showSuccess('Perfil atualizado com sucesso!');
            
        } catch (error) {
            console.error('❌ Erro ao salvar perfil:', error);
            this.showError(`Erro ao salvar perfil: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    handleCancelEdit() {
        this.isEditing = false;
        this.userData = { ...this.originalData };
        this.exitEditMode();
        this.renderProfile();
        this.showInfo('Edição cancelada');
    }

    exitEditMode() {
        // Desabilitar campos de edição
        const editableFields = document.querySelectorAll('[data-profile-name], [data-profile-email]');
        editableFields.forEach(field => {
            field.disabled = true;
            field.classList.remove('editing');
        });

        // Mostrar botão de editar
        const editBtn = document.querySelector('[data-edit-profile]');
        const saveBtn = document.querySelector('[data-save-profile]');
        const cancelBtn = document.querySelector('[data-cancel-edit]');

        if (editBtn) editBtn.style.display = 'inline-block';
        if (saveBtn) saveBtn.style.display = 'none';
        if (cancelBtn) cancelBtn.style.display = 'none';
    }

    async handleChangePassword() {
        const currentPassword = prompt('Digite sua senha atual:');
        if (!currentPassword) return;

        const newPassword = prompt('Digite sua nova senha:');
        if (!newPassword) return;

        const confirmPassword = prompt('Confirme sua nova senha:');
        if (newPassword !== confirmPassword) {
            this.showError('As senhas não coincidem');
            return;
        }

        try {
            this.showLoading('Alterando senha...');

            const response = await AuthUtils.authenticatedFetch('/api/v1/auth/change-password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Erro ao alterar senha');
            }

            this.showSuccess('Senha alterada com sucesso!');
            
        } catch (error) {
            console.error('❌ Erro ao alterar senha:', error);
            this.showError(`Erro ao alterar senha: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    async handleEnable2FA() {
        try {
            this.showLoading('Configurando 2FA...');

            const response = await AuthUtils.authenticatedFetch('/api/v1/auth/2fa/enable', {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Erro ao ativar 2FA');
            }

            const data = await response.json();
            
            // Mostrar QR code para configuração
            this.show2FASetup(data.qr_code, data.secret);
            
        } catch (error) {
            console.error('❌ Erro ao ativar 2FA:', error);
            this.showError(`Erro ao ativar 2FA: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    async handleDisable2FA() {
        if (!confirm('Tem certeza que deseja desativar a autenticação de dois fatores?')) {
            return;
        }

        try {
            this.showLoading('Desativando 2FA...');

            const response = await AuthUtils.authenticatedFetch('/api/v1/auth/2fa/disable', {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Erro ao desativar 2FA');
            }

            this.userData.two_factor_enabled = false;
            this.renderSecuritySettings();
            this.showSuccess('2FA desativado com sucesso!');
            
        } catch (error) {
            console.error('❌ Erro ao desativar 2FA:', error);
            this.showError(`Erro ao desativar 2FA: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    async handleNotificationChange(checkbox) {
        const setting = checkbox.dataset.notificationSetting;
        const enabled = checkbox.checked;

        try {
            const response = await AuthUtils.authenticatedFetch('/api/v1/auth/notifications', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    [setting]: enabled
                })
            });

            if (!response.ok) {
                // Reverter mudança se falhou
                checkbox.checked = !enabled;
                throw new Error('Erro ao atualizar configuração');
            }

            this.showSuccess('Configuração atualizada!');
            
        } catch (error) {
            console.error('❌ Erro ao atualizar notificação:', error);
            this.showError('Erro ao atualizar configuração');
        }
    }

    async handleCreditAlertChange(select) {
        const threshold = select.value;
        const thresholdText = select.options[select.selectedIndex].text;

        try {
            const response = await AuthUtils.authenticatedFetch('/api/v1/auth/credit-alert-threshold', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    threshold_cents: parseInt(threshold)
                })
            });

            if (!response.ok) {
                // Reverter mudança se falhou
                select.value = this.userData.credit_alert_threshold || '500';
                throw new Error('Erro ao atualizar limite de alerta');
            }

            this.showSuccess(`Limite de alerta atualizado para ${thresholdText}!`);
            
        } catch (error) {
            console.error('❌ Erro ao atualizar limite de alerta:', error);
            this.showError('Erro ao atualizar limite de alerta');
        }
    }

    async handleAvatarUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        // Validação do arquivo
        if (!file.type.startsWith('image/')) {
            this.showError('Por favor, selecione uma imagem válida');
            return;
        }

        if (file.size > 5 * 1024 * 1024) { // 5MB
            this.showError('A imagem deve ter no máximo 5MB');
            return;
        }

        try {
            this.showLoading('Enviando avatar...');

            const formData = new FormData();
            formData.append('avatar', file);

            const response = await AuthUtils.authenticatedFetch('/api/v1/auth/avatar', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Erro ao enviar avatar');
            }

            const data = await response.json();
            this.userData.avatar = data.avatar_url;
            this.renderBasicInfo();
            this.showSuccess('Avatar atualizado com sucesso!');
            
        } catch (error) {
            console.error('❌ Erro ao enviar avatar:', error);
            this.showError(`Erro ao enviar avatar: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    async handleLogout() {
        if (!confirm('Tem certeza que deseja fazer logout?')) {
            return;
        }

        try {
            this.showLoading('Fazendo logout...');

            // Tentar fazer logout no servidor (opcional)
            try {
                await AuthUtils.authenticatedFetch('/api/v1/auth/logout', {
                    method: 'POST'
                });
            } catch (error) {
                console.log('⚠️ Logout no servidor falhou, continuando com logout local:', error);
            }

            // Limpar dados locais
            localStorage.removeItem('auth_token');
            localStorage.removeItem('session_token');
            localStorage.removeItem('user_data');
            
            // Limpar cookies
            document.cookie = 'auth_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
            document.cookie = 'session_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';

            this.showSuccess('Logout realizado com sucesso!');
            
            // Redirecionar para login após um breve delay
            setTimeout(() => {
                window.location.href = '/login';
            }, 1000);
            
        } catch (error) {
            console.error('❌ Erro ao fazer logout:', error);
            this.showError(`Erro ao fazer logout: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    async handleDeleteAccount() {
        const confirmText = 'DELETE';
        const userInput = prompt(`Para confirmar a exclusão da conta, digite "${confirmText}":`);
        
        if (userInput !== confirmText) {
            this.showInfo('Exclusão cancelada');
            return;
        }

        if (!confirm('ATENÇÃO: Esta ação é irreversível! Todos os seus dados serão perdidos. Tem certeza?')) {
            return;
        }

        try {
            this.showLoading('Excluindo conta...');

            const response = await AuthUtils.authenticatedFetch('/api/v1/auth/account', {
                method: 'DELETE'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Erro ao excluir conta');
            }

            this.showSuccess('Conta excluída com sucesso. Redirecionando...');
            setTimeout(() => {
                window.location.href = '/login';
            }, 2000);
            
        } catch (error) {
            console.error('❌ Erro ao excluir conta:', error);
            this.showError(`Erro ao excluir conta: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    validateProfileForm(data) {
        if (!data.name || data.name.trim().length < 2) {
            this.showError('Nome deve ter pelo menos 2 caracteres');
            return false;
        }

        if (!data.email || !this.isValidEmail(data.email)) {
            this.showError('Email inválido');
            return false;
        }

        return true;
    }

    validateField(fieldName) {
        const field = document.querySelector(`[data-profile-${fieldName}]`);
        if (!field) return;

        const value = field.value.trim();
        let isValid = true;
        let message = '';

        switch (fieldName) {
            case 'name':
                isValid = value.length >= 2;
                message = 'Nome deve ter pelo menos 2 caracteres';
                break;
            case 'email':
                isValid = this.isValidEmail(value);
                message = 'Email inválido';
                break;
        }

        field.classList.toggle('error', !isValid);
        
        // Mostrar/ocultar mensagem de erro
        let errorElement = field.parentNode.querySelector('.error-message');
        if (!isValid) {
            if (!errorElement) {
                errorElement = document.createElement('div');
                errorElement.className = 'error-message text-red-500 text-sm mt-1';
                field.parentNode.appendChild(errorElement);
            }
            errorElement.textContent = message;
        } else if (errorElement) {
            errorElement.remove();
        }

        return isValid;
    }

    setupFormValidation() {
        // Validação em tempo real
        const fields = document.querySelectorAll('[data-profile-name], [data-profile-email]');
        fields.forEach(field => {
            field.addEventListener('blur', () => {
                const fieldName = field.dataset.profileName ? 'name' : 'email';
                this.validateField(fieldName);
            });
        });
    }

    show2FASetup(qrCode, secret) {
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        modal.innerHTML = `
            <div class="bg-[#192633] rounded-lg p-6 max-w-md w-full mx-4">
                <h3 class="text-white text-lg font-bold mb-4">Configurar 2FA</h3>
                <div class="text-center mb-4">
                    <img src="${qrCode}" alt="QR Code" class="mx-auto mb-4" />
                    <p class="text-[#92adc9] text-sm mb-2">Escaneie o QR code com seu app autenticador</p>
                    <p class="text-[#92adc9] text-xs">Ou digite manualmente: <code class="bg-[#111a22] px-2 py-1 rounded">${secret}</code></p>
                </div>
                <div class="flex gap-2">
                    <button class="btn btn-primary flex-1" onclick="this.closest('.fixed').remove()">Fechar</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    formatDate(dateString) {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleDateString('pt-BR');
    }

    formatDateTime(dateString) {
        if (!dateString) return 'Nunca';
        const date = new Date(dateString);
        return date.toLocaleString('pt-BR');
    }

    getDefaultAvatar() {
        return `https://ui-avatars.com/api/?name=${encodeURIComponent(this.userData?.name || 'User')}&background=1172d4&color=fff&size=128`;
    }

    showLoading(message) {
        console.log('⏳', message);
    }

    hideLoading() {
        console.log('✅ Loading finalizado');
    }

    showSuccess(message) {
        console.log('✅', message);
        alert(message);
    }

    showError(message) {
        console.error('❌', message);
        alert(message);
    }

    showInfo(message) {
        console.log('ℹ️', message);
        alert(message);
    }

    showErrorState(message) {
        console.warn('⚠️ Estado de erro no perfil:', message);
        
        const profileContainer = document.querySelector('#profile-container');
        const basicInfoSection = document.querySelector('#basic-info');
        
        if (profileContainer) {
            profileContainer.innerHTML = `
                <div class="text-center py-12 text-red-500">
                    <i class="fas fa-exclamation-triangle text-6xl mb-6"></i>
                    <h2 class="text-2xl font-bold mb-4">Erro ao Carregar Perfil</h2>
                    <p class="mb-6">${message}</p>
                    <div class="space-x-4">
                        <button onclick="location.reload()" class="bg-red-600 text-white px-6 py-3 rounded hover:bg-red-700">
                            Tentar Novamente
                        </button>
                        <button onclick="window.location.href='/login'" class="bg-gray-600 text-white px-6 py-3 rounded hover:bg-gray-700">
                            Fazer Login Novamente
                        </button>
                    </div>
                </div>
            `;
        }
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    new PerfilManager();
});

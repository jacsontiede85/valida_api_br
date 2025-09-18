/**
 * API Keys JavaScript - SaaS Valida
 * Funcionalidades para gerenciamento de chaves de API
 */

class APIKeysManager {
    constructor() {
        this.apiBaseUrl = '/api/v1';
        this.apiKeys = [];
        this.init();
    }

    async init() {
        console.log('🔑 Inicializando gerenciador de API Keys...');
        
        // Verificar autenticação
        const token = this.getAuthToken();
        if (!token) {
            this.showLoginRequired();
            return;
        }

        this.setAuthHeader(token);
        
        // Carregar API keys
        await this.loadAPIKeys();
        
        // Configurar eventos
        this.setupEventListeners();
    }

    getAuthToken() {
        // Primeiro tentar localStorage
        let token = localStorage.getItem('auth_token') || localStorage.getItem('api_key');
        
        // Se não encontrar, usar token de desenvolvimento
        if (!token) {
            token = 'rcp_dev-key-2';
        }
        
        return token;
    }

    setAuthHeader(token) {
        this.authHeader = {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        };
    }

    async loadAPIKeys() {
        this.showLoading(true);
        
        try {
            const response = await this.fetchWithAuth(`${this.apiBaseUrl}/api-keys`);
            
            if (response.ok) {
                this.apiKeys = await response.json();
                this.renderAPIKeys();
                console.log(`✅ ${this.apiKeys.length} API keys carregadas`);
            } else {
                console.error('❌ API keys indisponíveis');
                this.showErrorState('API indisponível');
            }
        } catch (error) {
            console.error('❌ Erro ao carregar API keys:', error);
            this.showErrorState('Erro ao carregar dados');
        } finally {
            this.showLoading(false);
        }
    }

    showLoading(show) {
        const loadingOverlay = document.getElementById('loading-overlay');
        if (loadingOverlay) {
            loadingOverlay.classList.toggle('hidden', !show);
        }
    }

    showErrorState(message) {
        console.warn('⚠️ Exibindo estado de erro:', message);
        
        const tbody = document.querySelector('#api-keys-table');
        const emptyState = document.querySelector('#empty-state');
        
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center py-8 text-red-500">
                        <i class="fas fa-exclamation-triangle text-4xl mb-2"></i>
                        <p>Erro ao carregar API keys: ${message}</p>
                        <button onclick="location.reload()" class="mt-2 bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700">
                            Tentar Novamente
                        </button>
                    </td>
                </tr>
            `;
        }
        
        if (emptyState) {
            emptyState.classList.add('hidden');
        }
    }

    renderAPIKeys() {
        const tbody = document.querySelector('#api-keys-table');
        const emptyState = document.querySelector('#empty-state');
        
        if (!tbody) {
            console.error('❌ Elemento tbody não encontrado!');
            return;
        }

        if (this.apiKeys.length === 0) {
            tbody.innerHTML = '';
            emptyState.classList.remove('hidden');
            return;
        }

        emptyState.classList.add('hidden');
        tbody.innerHTML = this.apiKeys.map(key => `
            <tr class="hover:bg-gray-800 transition-colors">
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="flex items-center">
                        <div class="flex-shrink-0 h-8 w-8">
                            <div class="h-8 w-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                                <span class="material-icons text-blue-400 text-sm">vpn_key</span>
                            </div>
                        </div>
                        <div class="ml-4">
                            <div class="text-sm font-medium text-white">${key.name || 'Chave sem nome'}</div>
                            <div class="text-sm text-gray-400">${key.description || 'Sem descrição'}</div>
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="flex items-center space-x-2">
                        <code class="text-sm font-mono text-gray-300 bg-gray-800 px-2 py-1 rounded">
                            ${this.getDisplayKey(key)}
                        </code>
                        ${this.getCopyButton(key)}
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${key.is_active ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}">
                        <span class="material-icons text-xs mr-1">${key.is_active ? 'check_circle' : 'block'}</span>
                        ${key.is_active ? 'Ativa' : 'Inativa'}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                    ${new Date(key.created_at).toLocaleDateString('pt-BR')}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                    ${key.last_used ? new Date(key.last_used).toLocaleDateString('pt-BR') : 'Nunca'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    ${this.renderActions(key)}
                </td>
            </tr>
        `).join('');

        this.updateStats();
    }

    renderActions(key) {
        if (!key.is_active) {
            return `
                <div class="flex space-x-2">
                    <button onclick="apiKeysManager.showKeyDetails('${key.id}')" 
                            class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded hover:bg-gray-700 transition-colors">
                        <span class="material-icons text-sm">info</span>
                    </button>
                </div>
            `;
        }

        return `
            <div class="flex space-x-2">
                <button onclick="apiKeysManager.showKeyDetails('${key.id}')" 
                        class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded hover:bg-gray-700 transition-colors" title="Ver detalhes">
                    <span class="material-icons text-sm">info</span>
                </button>
                <button onclick="apiKeysManager.revokeKey('${key.id}')" 
                        class="text-red-400 hover:text-red-300 text-xs px-2 py-1 rounded hover:bg-gray-700 transition-colors" title="Revogar chave">
                    <span class="material-icons text-sm">block</span>
                </button>
            </div>
        `;
    }

    maskAPIKey(keyHash) {
        if (!keyHash) return 'N/A';
        return keyHash.substring(0, 8) + '...' + keyHash.substring(keyHash.length - 8);
    }

    getDisplayKey(key) {
        // Se temos a chave original (começando com rcp_)
        if (key.key && key.key.startsWith('rcp_')) {
            return this.maskAPIKey(key.key);
        }
        // Se temos apenas o hash, mostrar como "Hash: ..."
        if (key.key_hash) {
            return `Hash: ${this.maskAPIKey(key.key_hash)}`;
        }
        return 'Chave não disponível';
    }

    getCopyButton(key) {
        // Se temos a chave original (começando com rcp_)
        if (key.key && key.key.startsWith('rcp_')) {
            return `<button onclick="apiKeysManager.copyToClipboard('${key.key}')" 
                    class="text-blue-400 hover:text-blue-300 transition-colors" 
                    title="Copiar chave">
                <span class="material-icons text-sm">content_copy</span>
            </button>`;
        }
        // Se temos apenas o hash
        if (key.key_hash) {
            return `<button onclick="apiKeysManager.copyToClipboard('${key.key_hash}')" 
                    class="text-blue-400 hover:text-blue-300 transition-colors" 
                    title="Copiar hash">
                <span class="material-icons text-sm">content_copy</span>
            </button>`;
        }
        // Chave não disponível
        return `<button onclick="apiKeysManager.showKeyWarning()" 
                class="text-gray-400 hover:text-gray-300 transition-colors" 
                title="Chave não disponível">
            <span class="material-icons text-sm">visibility_off</span>
        </button>`;
    }

    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showNotification('Chave copiada para a área de transferência!', 'success');
        } catch (error) {
            console.error('❌ Erro ao copiar:', error);
            this.showNotification('Erro ao copiar chave', 'error');
        }
    }

    async revokeKey(keyId) {
        if (!confirm('Tem certeza que deseja revogar esta API key?')) {
            return;
        }

        try {
            console.log(`🗑️ Revogando API key: ${keyId}`);
            
            const response = await this.fetchWithAuth(
                `${this.apiBaseUrl}/api-keys/${keyId}`,
                { method: 'DELETE' }
            );

            if (response.ok) {
                this.showNotification('API key revogada com sucesso!', 'success');
                await this.loadAPIKeys(); // Recarregar lista
            } else {
                const error = await response.json();
                this.showNotification(`Erro: ${error.detail}`, 'error');
            }
        } catch (error) {
            console.error('❌ Erro ao revogar API key:', error);
            this.showNotification('Erro ao revogar API key', 'error');
        }
    }

    showKeyDetails(keyId) {
        const key = this.apiKeys.find(k => k.id === keyId);
        if (!key) return;

        const modal = this.createModal(`
            <div class="p-6">
                <h3 class="text-lg font-semibold mb-4">Detalhes da API Key</h3>
                <div class="space-y-3">
                    <div>
                        <label class="block text-sm font-medium text-gray-300">Nome</label>
                        <p class="text-white">${key.name}</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-300">Descrição</label>
                        <p class="text-white">${key.description || 'N/A'}</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-300">Criada em</label>
                        <p class="text-white">${new Date(key.created_at).toLocaleString('pt-BR')}</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-300">Último uso</label>
                        <p class="text-white">${key.last_used ? new Date(key.last_used).toLocaleString('pt-BR') : 'Nunca'}</p>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-300">Status</label>
                        <span class="inline-block px-2 py-1 rounded text-xs ${key.is_active ? 'bg-green-600' : 'bg-red-600'}">
                            ${key.is_active ? 'Ativa' : 'Inativa'}
                        </span>
                    </div>
                </div>
            </div>
        `);

        document.body.appendChild(modal);
    }

    async createNewKey() {
        const modal = this.createModal(`
            <div class="p-6">
                <div class="text-center mb-6">
                    <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-blue-100 mb-4">
                        <span class="material-icons text-blue-600 text-2xl">vpn_key</span>
                    </div>
                    <h3 class="text-xl font-semibold text-white mb-2">Criar Nova API Key</h3>
                    <p class="text-gray-400 text-sm">Configure uma nova chave de API para acessar os serviços</p>
                </div>
                
                <form id="new-key-form" class="space-y-6">
                    <div>
                        <label class="block text-sm font-medium text-gray-300 mb-2">
                            Nome da Chave <span class="text-red-400">*</span>
                        </label>
                        <input type="text" name="name" required
                               class="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
                               placeholder="Ex: Chave de Produção">
                        <p class="text-gray-500 text-xs mt-1">Escolha um nome descritivo para identificar esta chave</p>
                    </div>
                    
                    <div>
                        <label class="block text-sm font-medium text-gray-300 mb-2">Descrição (opcional)</label>
                        <textarea name="description" rows="3"
                                  class="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors resize-none"
                                  placeholder="Descreva o uso desta chave..."></textarea>
                        <p class="text-gray-500 text-xs mt-1">Adicione detalhes sobre onde e como esta chave será usada</p>
                    </div>
                    
                    <div class="bg-blue-900/20 border border-blue-600/30 p-4 rounded-lg">
                        <div class="flex items-start">
                            <span class="material-icons text-blue-400 text-lg mr-3 mt-0.5">info</span>
                            <div>
                                <p class="text-blue-200 font-medium text-sm mb-1">Informação importante</p>
                                <p class="text-blue-200/80 text-sm leading-relaxed">
                                    Após criar a chave, você terá apenas uma oportunidade de visualizá-la completa. 
                                    Certifique-se de salvá-la em um local seguro.
                                </p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="flex justify-end space-x-3 pt-4">
                        <button type="button" onclick="this.closest('.modal').remove()"
                                class="px-6 py-2 bg-gray-600 text-white text-sm font-medium rounded-lg hover:bg-gray-700 transition-colors">
                            Cancelar
                        </button>
                        <button type="submit"
                                class="px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors">
                            <span class="material-icons text-sm mr-2">add</span>
                            Criar Chave
                        </button>
                    </div>
                </form>
            </div>
        `);

        document.body.appendChild(modal);

        // Configurar submit do formulário
        const form = modal.querySelector('#new-key-form');
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this.submitNewKey(form);
        });
    }

    async submitNewKey(form) {
        const formData = new FormData(form);
        const keyData = {
            name: formData.get('name'),
            description: formData.get('description') || null
        };

        try {
            console.log('🔑 Criando nova API key...');
            
            const response = await this.fetchWithAuth(
                `${this.apiBaseUrl}/api-keys`,
                {
                    method: 'POST',
                    body: JSON.stringify(keyData)
                }
            );

            if (response.ok) {
                const newKey = await response.json();
                // Fechar o formulário de criação
                const createModal = form.closest('.modal');
                if (createModal) {
                    createModal.remove();
                }
                // Mostrar modal de sucesso
                this.showNewKeyModal(newKey);
                await this.loadAPIKeys(); // Recarregar lista
            } else {
                const error = await response.json();
                this.showNotification(`Erro: ${error.detail}`, 'error');
            }
        } catch (error) {
            console.error('❌ Erro ao criar API key:', error);
            this.showNotification('Erro ao criar API key', 'error');
        }
    }

    showNewKeyModal(newKey) {
        const modal = this.createModal(`
            <div class="p-6">
                <div class="text-center mb-6">
                    <div class="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100 mb-4">
                        <span class="material-icons text-green-600 text-2xl">check</span>
                    </div>
                    <h3 class="text-xl font-semibold text-green-400 mb-2">API Key Criada com Sucesso!</h3>
                    <p class="text-gray-400 text-sm">Sua nova chave de API foi gerada e está pronta para uso</p>
                </div>
                
                <div class="space-y-4">
                    <div class="bg-gray-800 border border-gray-700 p-4 rounded-lg">
                        <label class="block text-sm font-medium text-gray-300 mb-3">Sua nova API Key:</label>
                        <div class="space-y-3">
                            <div class="bg-gray-900 border border-gray-600 rounded-lg p-3">
                                <code class="text-green-400 font-mono text-sm break-all leading-relaxed block">
                                    ${newKey.key}
                                </code>
                            </div>
                            <div class="flex justify-center">
                                <button onclick="apiKeysManager.copyToClipboard('${newKey.key}')"
                                        class="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors">
                                    <span class="material-icons text-sm mr-2">content_copy</span>
                                    Copiar Chave
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <div class="bg-amber-900/20 border border-amber-600/30 p-4 rounded-lg">
                        <div class="flex items-start">
                            <span class="material-icons text-amber-400 text-lg mr-3 mt-0.5">warning</span>
                            <div>
                                <p class="text-amber-200 font-medium text-sm mb-1">Importante!</p>
                                <p class="text-amber-200/80 text-sm leading-relaxed">
                                    Esta é a única vez que você verá esta chave completa. 
                                    Salve-a em um local seguro e não a compartilhe com terceiros.
                                </p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="bg-blue-900/20 border border-blue-600/30 p-4 rounded-lg">
                        <div class="flex items-start">
                            <span class="material-icons text-blue-400 text-lg mr-3 mt-0.5">info</span>
                            <div>
                                <p class="text-blue-200 font-medium text-sm mb-1">Como usar:</p>
                                <p class="text-blue-200/80 text-sm leading-relaxed">
                                    Use esta chave no header <code class="bg-gray-800 px-1 rounded">Authorization: Bearer ${newKey.key.substring(0, 20)}...</code>
                                </p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="flex justify-end pt-4">
                        <button onclick="this.closest('.modal').remove()"
                                class="px-6 py-2 bg-gray-600 text-white text-sm font-medium rounded-lg hover:bg-gray-700 transition-colors">
                            Entendi
                        </button>
                    </div>
                </div>
            </div>
        `);

        document.body.appendChild(modal);
    }

    createModal(content) {
        const modal = document.createElement('div');
        modal.className = 'modal fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4';
        modal.innerHTML = `
            <div class="bg-gray-800 rounded-lg shadow-2xl w-full max-w-2xl mx-auto">
                ${content}
            </div>
        `;

        // Fechar modal ao clicar fora
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });

        // Fechar modal com ESC
        const handleEsc = (e) => {
            if (e.key === 'Escape') {
                modal.remove();
                document.removeEventListener('keydown', handleEsc);
            }
        };
        document.addEventListener('keydown', handleEsc);

        return modal;
    }

    setupEventListeners() {
        // Botão de criar nova chave
        const createBtn = document.querySelector('#create-key-btn');
        if (createBtn) {
            createBtn.addEventListener('click', () => this.createNewKey());
        }

        // Botão de refresh
        const refreshBtn = document.querySelector('#refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadAPIKeys());
        }

        // Campo de busca
        const searchInput = document.querySelector('#search-input');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => this.filterKeys(e.target.value));
        }

        // Filtro de status
        const statusFilter = document.querySelector('#status-filter');
        if (statusFilter) {
            statusFilter.addEventListener('change', (e) => this.filterByStatus(e.target.value));
        }
    }

    updateStats() {
        const totalKeys = this.apiKeys.length;
        const activeKeys = this.apiKeys.filter(key => key.is_active).length;
        const revokedKeys = this.apiKeys.filter(key => !key.is_active).length;

        const totalElement = document.getElementById('total-keys');
        const activeElement = document.getElementById('active-keys');
        const revokedElement = document.getElementById('revoked-keys');

        if (totalElement) totalElement.textContent = totalKeys;
        if (activeElement) activeElement.textContent = activeKeys;
        if (revokedElement) revokedElement.textContent = revokedKeys;
    }

    filterKeys(searchTerm) {
        const filteredKeys = this.apiKeys.filter(key => 
            key.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            (key.key && key.key.toLowerCase().includes(searchTerm.toLowerCase())) ||
            (key.key_hash && key.key_hash.toLowerCase().includes(searchTerm.toLowerCase())) ||
            (key.description && key.description.toLowerCase().includes(searchTerm.toLowerCase()))
        );
        
        this.renderFilteredKeys(filteredKeys);
    }

    filterByStatus(status) {
        let filteredKeys = this.apiKeys;
        
        if (status === 'active') {
            filteredKeys = this.apiKeys.filter(key => key.is_active);
        } else if (status === 'inactive') {
            filteredKeys = this.apiKeys.filter(key => !key.is_active);
        }
        
        this.renderFilteredKeys(filteredKeys);
    }

    renderFilteredKeys(keys) {
        const tbody = document.querySelector('#api-keys-table');
        const emptyState = document.querySelector('#empty-state');
        
        if (!tbody) return;

        if (keys.length === 0) {
            tbody.innerHTML = '';
            emptyState.classList.remove('hidden');
            return;
        }

        emptyState.classList.add('hidden');
        tbody.innerHTML = keys.map(key => `
            <tr class="hover:bg-gray-800 transition-colors">
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="flex items-center">
                        <div class="flex-shrink-0 h-8 w-8">
                            <div class="h-8 w-8 rounded-full bg-blue-500/20 flex items-center justify-center">
                                <span class="material-icons text-blue-400 text-sm">vpn_key</span>
                            </div>
                        </div>
                        <div class="ml-4">
                            <div class="text-sm font-medium text-white">${key.name || 'Chave sem nome'}</div>
                            <div class="text-sm text-gray-400">${key.description || 'Sem descrição'}</div>
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="flex items-center space-x-2">
                        <code class="text-sm font-mono text-gray-300 bg-gray-800 px-2 py-1 rounded">
                            ${this.getDisplayKey(key)}
                        </code>
                        ${this.getCopyButton(key)}
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${key.is_active ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}">
                        <span class="material-icons text-xs mr-1">${key.is_active ? 'check_circle' : 'block'}</span>
                        ${key.is_active ? 'Ativa' : 'Inativa'}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                    ${new Date(key.created_at).toLocaleDateString('pt-BR')}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                    ${key.last_used ? new Date(key.last_used).toLocaleDateString('pt-BR') : 'Nunca'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    ${this.renderActions(key)}
                </td>
            </tr>
        `).join('');
    }

    async fetchWithAuth(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...this.authHeader
            }
        };

        return fetch(url, { ...defaultOptions, ...options });
    }

    showLoginRequired() {
        const container = document.querySelector('.layout-content-container');
        if (container) {
            container.innerHTML = `
                <div class="flex items-center justify-center h-64">
                    <div class="text-center">
                        <h2 class="text-xl font-semibold text-white mb-4">Login Necessário</h2>
                        <p class="text-gray-400 mb-4">Você precisa fazer login para gerenciar suas API keys.</p>
                        <button onclick="window.location.href='/login'" 
                                class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                            Fazer Login
                        </button>
                    </div>
                </div>
            `;
        }
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 ${
            type === 'success' ? 'bg-green-600' : 
            type === 'error' ? 'bg-red-600' : 'bg-blue-600'
        } text-white`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    showKeyWarning() {
        this.showNotification('⚠️ A chave original não está disponível por segurança. Gere uma nova chave para obter a chave visível.', 'warning');
    }
}

// Inicializar gerenciador quando a página carregar
document.addEventListener('DOMContentLoaded', () => {
    window.apiKeysManager = new APIKeysManager();
});

/**
 * API Client v2.0 - Sistema de Integração com Backend v2.0
 * Gerencia todas as chamadas para as APIs v2.0 com sistema de créditos
 */

class ApiClientV2 {
    constructor() {
        this.baseUrl = '/api/v2';
        this.v1BaseUrl = '/api/v1';
        this.authToken = null;
        this.retryCount = 3;
        this.requestQueue = [];
        this.isProcessingQueue = false;
        this.cache = new Map();
        this.cacheTimeout = 5 * 60 * 1000; // 5 minutos
        this.init();
    }

    async init() {
        console.log('🔌 Inicializando API Client v2.0');
        
        // Carregar token de autenticação
        await this.loadAuthToken();
        
        // Configurar interceptadores de requisição
        this.setupRequestInterceptors();
        
        console.log('✅ API Client v2.0 inicializado');
    }

    async loadAuthToken() {
        // Tentar carregar token existente
        this.authToken = localStorage.getItem('auth_token') || 
                        localStorage.getItem('api_key') || 
                        localStorage.getItem('dev_token');
        
        // Se não tiver token válido, tentar obter um
        if (!this.authToken || !this.authToken.startsWith('rcp_')) {
            try {
                this.authToken = await this.obtainApiKey();
                if (this.authToken) {
                    localStorage.setItem('api_key', this.authToken);
                }
            } catch (error) {
                console.warn('⚠️ Não foi possível obter token de API:', error);
            }
        }
    }

    async obtainApiKey() {
        try {
            // Tentar API key real primeiro
            let response = await fetch(`${this.v1BaseUrl}/auth/real-api-key`);
            if (response.ok) {
                const data = await response.json();
                console.log('🔑 API key real obtida');
                return data.api_key;
            }

            // Fallback para dev API key
            response = await fetch(`${this.v1BaseUrl}/auth/dev-api-key`, { method: 'POST' });
            if (response.ok) {
                const data = await response.json();
                console.log('🔑 API key de desenvolvimento obtida');
                return data.api_key;
            }
        } catch (error) {
            console.error('❌ Erro ao obter API key:', error);
        }
        return null;
    }

    setupRequestInterceptors() {
        // Interceptar todas as requisições fetch para adicionar headers
        const originalFetch = window.fetch;
        window.fetch = async (url, options = {}) => {
            if (url.startsWith(this.baseUrl) || url.startsWith(this.v1BaseUrl)) {
                options.headers = {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.authToken}`,
                    ...options.headers
                };
            }
            return originalFetch(url, options);
        };
    }

    // ===== MÉTODOS DE DASHBOARD =====
    async getDashboardData(period = '30d') {
        const cacheKey = `dashboard_${period}`;
        const cached = this.getFromCache(cacheKey);
        if (cached) return cached;

        try {
            const response = await this.request(`${this.baseUrl}/dashboard/data?period=${period}`);
            this.setCache(cacheKey, response, 30000); // Cache por 30 segundos
            return response;
        } catch (error) {
            console.error('❌ Erro ao carregar dados do dashboard:', error);
            throw new Error('Não foi possível carregar dados do dashboard. Verifique sua conexão.');
        }
    }


    // ===== MÉTODOS DE CONSULTA =====
    async calculateConsultationCost(params) {
        try {
            const queryParams = new URLSearchParams(params).toString();
            const response = await this.request(`${this.baseUrl}/costs/calculate?${queryParams}`);
            return response;
        } catch (error) {
            console.error('❌ Erro ao calcular custos:', error);
            throw new Error('Não foi possível calcular os custos. Tente novamente.');
        }
    }


    async performConsultation(cnpj, services) {
        try {
            const response = await this.request(`${this.v1BaseUrl}/cnpj/consult`, {
                method: 'POST',
                body: JSON.stringify({
                    cnpj,
                    ...services
                })
            });
            return response;
        } catch (error) {
            console.error('❌ Erro na consulta:', error);
            throw error;
        }
    }

    // ===== MÉTODOS DE HISTÓRICO =====
    async getConsultationsHistory(page = 1, limit = 20, filters = {}) {
        try {
            const queryParams = new URLSearchParams({
                page: page.toString(),
                limit: limit.toString(),
                ...filters
            }).toString();
            
            const response = await this.request(`${this.baseUrl}/consultations/history?${queryParams}`);
            return response;
        } catch (error) {
            console.error('❌ Erro ao carregar histórico de consultas:', error);
            throw new Error('Não foi possível carregar o histórico. Verifique sua conexão.');
        }
    }


    // ===== MÉTODOS DE API KEYS =====
    async getApiKeysUsage() {
        try {
            const response = await this.request(`${this.baseUrl}/api-keys/usage`);
            return response;
        } catch (error) {
            console.error('❌ Erro ao carregar uso das API keys:', error);
            throw new Error('Não foi possível carregar dados das API keys. Tente novamente.');
        }
    }


    // ===== MÉTODOS DE ASSINATURA =====
    async getSubscriptionPlans() {
        try {
            const response = await this.request(`${this.baseUrl}/subscription/plans`);
            return response;
        } catch (error) {
            console.error('❌ Erro ao carregar planos de assinatura:', error);
            throw new Error('Não foi possível carregar os planos. Tente novamente.');
        }
    }


    // ===== MÉTODOS DE FATURAS =====
    async getInvoicesWithCredits(page = 1, limit = 20) {
        try {
            const response = await this.request(`${this.baseUrl}/invoices/credits?page=${page}&limit=${limit}`);
            return response;
        } catch (error) {
            console.error('❌ Erro ao carregar faturas:', error);
            throw new Error('Não foi possível carregar as faturas. Tente novamente.');
        }
    }


    // ===== MÉTODOS DE PERFIL =====
    async getProfileCredits() {
        try {
            const response = await this.request(`${this.baseUrl}/profile/credits`);
            return response;
        } catch (error) {
            console.error('❌ Erro ao carregar dados do perfil:', error);
            throw new Error('Não foi possível carregar dados do perfil. Tente novamente.');
        }
    }


    // ===== MÉTODOS AUXILIARES =====
    async request(url, options = {}) {
        const requestId = this.generateRequestId();
        console.log(`📡 [${requestId}] Requisição: ${options.method || 'GET'} ${url}`);
        
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.authToken}`,
                    'X-Request-ID': requestId
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log(`✅ [${requestId}] Resposta recebida:`, data);
            return data;
        } catch (error) {
            console.error(`❌ [${requestId}] Erro na requisição:`, error);
            throw error;
        }
    }

    generateRequestId() {
        return Math.random().toString(36).substr(2, 9);
    }

    // ===== CACHE =====
    getFromCache(key) {
        const cached = this.cache.get(key);
        if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
            console.log(`💾 Cache hit: ${key}`);
            return cached.data;
        }
        return null;
    }

    setCache(key, data, timeout = null) {
        this.cache.set(key, {
            data,
            timestamp: Date.now(),
            timeout: timeout || this.cacheTimeout
        });
        console.log(`💾 Cache set: ${key}`);
    }

    clearCache() {
        this.cache.clear();
        console.log('🗑️ Cache limpo');
    }

    // ===== QUEUE DE REQUISIÇÕES =====
    async addToQueue(request) {
        return new Promise((resolve, reject) => {
            this.requestQueue.push({ request, resolve, reject });
            this.processQueue();
        });
    }

    async processQueue() {
        if (this.isProcessingQueue) return;
        
        this.isProcessingQueue = true;
        
        while (this.requestQueue.length > 0) {
            const { request, resolve, reject } = this.requestQueue.shift();
            
            try {
                const result = await request();
                resolve(result);
            } catch (error) {
                reject(error);
            }
            
            // Delay entre requisições para não sobrecarregar o servidor
            await this.delay(200);
        }
        
        this.isProcessingQueue = false;
    }

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // ===== HEALTH CHECK =====
    async healthCheck() {
        try {
            const response = await fetch(`${this.v1BaseUrl}/health`);
            const data = await response.json();
            console.log('🏥 Health check:', data);
            return data;
        } catch (error) {
            console.error('❌ Health check failed:', error);
            return { status: 'error', error: error.message };
        }
    }
}

// Instância global
window.apiClientV2 = null;

// Inicializar quando a página carregar
document.addEventListener('DOMContentLoaded', () => {
    window.apiClientV2 = new ApiClientV2();
    console.log('🔌 API Client v2.0 disponível globalmente como window.apiClientV2');
});

// Exportar para uso em módulos
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ApiClientV2;
}

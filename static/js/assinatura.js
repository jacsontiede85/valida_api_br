/**
 * JavaScript para página de Assinatura
 * Gerencia planos de assinatura e upgrades/downgrades
 * Integrado com Stripe para processamento de pagamentos
 */

class AssinaturaManager {
    constructor() {
        this.stripe = null;
        this.currentPlan = null;
        this.availablePlans = [];
        this.userSubscription = null;
        this.stripePrices = {};
        this.costs = {
            protestos: 0,
            receita_federal: 0,
            outros: 0
        };
        
        this.init();
    }

    async init() {
        console.log('🚀 Inicializando AssinaturaManager com Stripe...');
        
        try {
            // Inicializar Stripe
            await this.initializeStripe();
            
            // Carregar dados
            await Promise.all([
                this.loadCosts(),
                this.loadPlans(),
                this.loadCurrentSubscription(),
                this.loadRecentTransactions(),
                this.loadUserCredits()
            ]);
            
            this.setupEventListeners();
            this.renderPlans();
            this.renderCurrentSubscription();
            this.updateAutoRenewalToggle();
            
            console.log('✅ AssinaturaManager inicializado com sucesso');
        } catch (error) {
            console.error('❌ Erro ao inicializar AssinaturaManager:', error);
            this.showError('Erro ao carregar dados da assinatura');
        }
    }

    async initializeStripe() {
        try {
            // Obter chave pública do Stripe do backend
            const response = await AuthUtils.authenticatedFetch('/api/v1/stripe/public-key');
            const data = await response.json();
            
            if (!data.public_key) {
                throw new Error('Chave pública do Stripe não encontrada');
            }
            
            this.stripe = Stripe(data.public_key);
            console.log('✅ Stripe inicializado com sucesso');
        } catch (error) {
            console.error('❌ Erro ao inicializar Stripe:', error);
            throw error;
        }
    }

    async loadCosts() {
        try {
            const data = await AuthUtils.authenticatedFetchJSON('/api/v1/stripe/costs');
            this.costs = {
                protestos: data.protestos || 0.15,
                receita_federal: data.receita_federal || 0.03,
                outros: data.outros || 0.03
            };
            console.log('✅ Custos carregados:', this.costs);
        } catch (error) {
            console.error('❌ Erro ao carregar custos:', error);
            // Usar valores padrão em caso de erro
        }
    }

    async loadPlans() {
        try {
            // Carregar planos do Stripe via backend
            const data = await AuthUtils.authenticatedFetchJSON('/api/v1/stripe/products');
            this.availablePlans = data.products || [];
            this.stripePrices = data.prices || {};
            
            console.log('✅ Planos do Stripe carregados:', this.availablePlans.length);
        } catch (error) {
            console.error('❌ Erro ao carregar planos:', error);
            this.availablePlans = [];
            this.showErrorState('Erro ao carregar planos');
        }
    }

    async loadCurrentSubscription() {
        try {
            const data = await AuthUtils.authenticatedFetchJSON('/api/v1/stripe/subscription/current');
            this.userSubscription = data.subscription;
            console.log('✅ Assinatura atual carregada:', this.userSubscription);
        } catch (error) {
            console.error('❌ Erro ao carregar assinatura:', error);
            this.userSubscription = null;
        }
    }

    async loadRecentTransactions() {
        try {
            const data = await AuthUtils.authenticatedFetchJSON('/api/v1/stripe/transactions/recent');
            this.renderRecentTransactions(data.transactions || []);
        } catch (error) {
            console.error('❌ Erro ao carregar transações:', error);
        }
    }

    setupEventListeners() {
        // Botões de planos
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-plan-button]')) {
                const button = e.target;
                const planId = button.closest('[data-plan-template]')?.dataset.planId;
                if (planId) {
                    this.handlePlanSelection(planId);
                }
            }
        });

        // Toggle de renovação automática
        const autoRenewalToggle = document.getElementById('auto-renewal-toggle');
        if (autoRenewalToggle) {
            autoRenewalToggle.addEventListener('change', (e) => {
                this.handleAutoRenewalToggle(e.target.checked);
            });
        }
    }

    renderPlans() {
        const plansContainer = document.querySelector('[data-plans-container]');
        const planTemplate = document.querySelector('[data-plan-template]');
        
        if (!plansContainer || !planTemplate) return;

        // Limpar container mantendo o template
        Array.from(plansContainer.children).forEach(child => {
            if (!child.hasAttribute('data-plan-template')) {
                child.remove();
            }
        });

        this.availablePlans.forEach(plan => {
            const planElement = planTemplate.cloneNode(true);
            planElement.classList.remove('hidden');
            planElement.dataset.planId = plan.id;
            
            const isCurrentPlan = this.userSubscription && 
                this.userSubscription.items?.data[0]?.price?.product === plan.id;
            const isPopular = plan.metadata?.popular === 'true';
            
            // Popular badge
            const popularBadge = planElement.querySelector('.popular-badge');
            if (isPopular && popularBadge) {
                popularBadge.style.display = 'block';
            }
            
            // Nome do plano
            const nameEl = planElement.querySelector('[data-plan-name]');
            if (nameEl) nameEl.textContent = plan.name;
            
            // Preço - trabalha com dados Stripe reais ou mockados
            let priceAmount = 0;
            let creditsAmount = 0;
            
            // Verificar se temos dados do Stripe real
            const price = this.stripePrices[plan.default_price];
            if (price && price.unit_amount) {
                priceAmount = price.unit_amount / 100;
                creditsAmount = priceAmount;
            } 
            // Usar dados mockados se disponível
            else if (plan.price_cents) {
                priceAmount = plan.price_cents / 100;
                creditsAmount = plan.credits_included_cents ? plan.credits_included_cents / 100 : priceAmount;
            }
            
            // Renderizar preço
            const priceEl = planElement.querySelector('[data-plan-price]');
            if (priceEl && priceAmount > 0) {
                priceEl.textContent = `R$ ${priceAmount.toFixed(2).replace('.', ',')}`;
            }
            
            // Renderizar créditos
            const creditsEl = planElement.querySelector('[data-plan-credits]');
            if (creditsEl && creditsAmount > 0) {
                creditsEl.textContent = `R$ ${creditsAmount.toFixed(2).replace('.', ',')} em créditos`;
            }
            
            // Features
            this.renderPlanFeatures(planElement, plan);
            
            // Estimativas de consultas
            this.renderPlanEstimates(planElement, plan);
            
            // Botão
            const button = planElement.querySelector('[data-plan-button]');
            if (button) {
                if (isCurrentPlan) {
                    button.textContent = 'Plano Atual';
                    button.className = 'w-full py-3 px-4 rounded-lg font-medium bg-gray-600 text-gray-400 cursor-not-allowed';
                    button.disabled = true;
                } else {
                    button.textContent = 'Selecionar Plano';
                    button.className = 'w-full py-3 px-4 rounded-lg font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors';
                    button.disabled = false;
                }
            }
            
            plansContainer.appendChild(planElement);
        });
    }

    renderPlanFeatures(planElement, plan) {
        const featuresContainer = planElement.querySelector('[data-plan-features]');
        if (!featuresContainer) return;
        
        const features = [];
        
        // Recursos baseados nos metadados do produto
        if (plan.metadata) {
            if (plan.metadata.api_keys_limit) {
                features.push({
                    icon: '🔑',
                    text: plan.metadata.api_keys_limit === '-1' ? 'API Keys ilimitadas' : `${plan.metadata.api_keys_limit} API Keys`
                });
            }
            
            if (plan.metadata.support_level) {
                features.push({
                    icon: '🛠️',
                    text: `Suporte ${plan.metadata.support_level}`
                });
            }
            
            if (plan.metadata.analytics) {
                features.push({
                    icon: '📊',
                    text: 'Analytics avançado'
                });
            }
            
            if (plan.metadata.priority_support === 'true') {
                features.push({
                    icon: '🚀',
                    text: 'Suporte prioritário'
                });
            }
        }
        
        // Recursos padrão
        features.push(
            { icon: '🔒', text: 'Acesso completo à API' },
            { icon: '📈', text: 'Relatórios detalhados' },
            { icon: '⚡', text: 'Processamento rápido' }
        );
        
        const featuresHtml = features.map(feature => `
            <div class="flex items-center text-gray-300 text-sm">
                <span class="mr-3">${feature.icon}</span>
                <span>${feature.text}</span>
            </div>
        `).join('');
        
        featuresContainer.innerHTML = featuresHtml;
    }
    
    renderPlanEstimates(planElement, plan) {
        const price = this.stripePrices[plan.default_price];
        if (!price) return;
        
        const creditsAmount = price.unit_amount / 100;
        
        // Calcular estimativas baseadas nos custos
        const protestsEstimate = Math.floor(creditsAmount / this.costs.protestos);
        const receitaEstimate = Math.floor(creditsAmount / this.costs.receita_federal);
        
        const protestsEl = planElement.querySelector('[data-plan-protests]');
        const receitaEl = planElement.querySelector('[data-plan-receita]');
        
        if (protestsEl) protestsEl.textContent = protestsEstimate.toLocaleString('pt-BR');
        if (receitaEl) receitaEl.textContent = receitaEstimate.toLocaleString('pt-BR');
    }

    renderCurrentSubscription() {
        if (!this.userSubscription) {
            this.renderNoSubscription();
            return;
        }

        // Atualizar informações da assinatura atual
        const planNameEl = document.querySelector('[data-current-plan-name]');
        const statusEl = document.querySelector('[data-current-status]');
        const priceEl = document.querySelector('[data-current-price]');
        const creditsAvailableEl = document.querySelector('[data-credits-available]');
        const creditsTotalEl = document.querySelector('[data-credits-total]');
        const creditsUsedEl = document.querySelector('[data-credits-used]');
        
        if (this.userSubscription.items?.data[0]) {
            const priceObj = this.userSubscription.items.data[0].price;
            const product = this.availablePlans.find(p => p.id === priceObj.product);
            
            if (planNameEl && product) {
                planNameEl.textContent = product.name;
            }
            
            if (priceEl && priceObj) {
                priceEl.textContent = `R$ ${(priceObj.unit_amount / 100).toFixed(2).replace('.', ',')}`;
            }
        }
        
        if (statusEl) {
            const status = this.userSubscription.status;
            const statusText = {
                'active': 'Ativa',
                'canceled': 'Cancelada',
                'past_due': 'Atrasada',
                'unpaid': 'Não paga'
            }[status] || status;
            
            const statusClass = status === 'active' ? 'bg-green-500' : 'bg-red-500';
            statusEl.textContent = statusText;
            statusEl.className = `px-2 py-1 rounded text-xs font-medium text-white ${statusClass}`;
        }
        
        // Carregar créditos do usuário
        this.loadUserCredits();
    }
    
    renderNoSubscription() {
        const planNameEl = document.querySelector('[data-current-plan-name]');
        const statusEl = document.querySelector('[data-current-status]');
        const priceEl = document.querySelector('[data-current-price]');
        
        if (planNameEl) planNameEl.textContent = 'Nenhuma assinatura ativa';
        if (statusEl) {
            statusEl.textContent = 'Inativa';
            statusEl.className = 'px-2 py-1 rounded text-xs font-medium text-white bg-gray-500';
        }
        if (priceEl) priceEl.textContent = 'R$ 0,00';
    }
    
    async loadUserCredits() {
        try {
            const data = await AuthUtils.authenticatedFetchJSON('/api/v1/stripe/user/credits');
            
            const creditsAvailableEl = document.querySelector('[data-credits-available]');
            const creditsTotalEl = document.querySelector('[data-credits-total]');
            const creditsUsedEl = document.querySelector('[data-credits-used]');
            
            if (creditsAvailableEl) {
                creditsAvailableEl.textContent = `R$ ${(data.available || 0).toFixed(2).replace('.', ',')}`;
            }
            if (creditsTotalEl) {
                creditsTotalEl.textContent = `R$ ${(data.total || 0).toFixed(2).replace('.', ',')}`;
            }
            if (creditsUsedEl) {
                creditsUsedEl.textContent = `R$ ${(data.used || 0).toFixed(2).replace('.', ',')}`;
            }
        } catch (error) {
            console.error('❌ Erro ao carregar créditos:', error);
        }
    }

    async handlePlanSelection(planId) {
        const plan = this.availablePlans.find(p => p.id === planId);
        if (!plan) return;

        try {
            this.showLoading('Redirecionando para o checkout...');

            // Criar sessão de checkout do Stripe
            const response = await AuthUtils.authenticatedFetch('/api/v1/stripe/create-checkout-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    price_id: plan.default_price || plan.id || `price_${plan.id}`, // Usar default_price (Stripe real) ou id (mockado)
                    success_url: window.location.origin + '/assinatura?session_id={CHECKOUT_SESSION_ID}',
                    cancel_url: window.location.origin + '/assinatura'
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Erro ao criar sessão de checkout');
            }

            const { session_id } = await response.json();
            
            // Redirecionar para o Stripe Checkout
            const result = await this.stripe.redirectToCheckout({
                sessionId: session_id
            });
            
            if (result.error) {
                throw new Error(result.error.message);
            }
            
        } catch (error) {
            console.error('❌ Erro ao processar plano:', error);
            this.showError(`Erro ao processar plano: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    async handleAutoRenewalToggle(enabled) {
        try {
            this.showLoading('Atualizando renovação automática...');

            const response = await AuthUtils.authenticatedFetch('/api/v1/stripe/subscription/auto-renewal', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    enabled: enabled
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Erro ao atualizar renovação automática');
            }

            const message = enabled ? 'Renovação automática ativada' : 'Renovação automática desativada';
            this.showSuccess(message);
            
        } catch (error) {
            console.error('❌ Erro ao alterar renovação automática:', error);
            this.showError(`Erro: ${error.message}`);
            
            // Reverter o toggle em caso de erro
            const toggle = document.getElementById('auto-renewal-toggle');
            if (toggle) {
                toggle.checked = !enabled;
            }
        } finally {
            this.hideLoading();
        }
    }
    
    updateAutoRenewalToggle() {
        const toggle = document.getElementById('auto-renewal-toggle');
        const autoRenewalEl = document.querySelector('[data-auto-renewal]');
        
        if (this.userSubscription && this.userSubscription.cancel_at_period_end !== null) {
            const isAutoRenewal = !this.userSubscription.cancel_at_period_end;
            
            if (toggle) toggle.checked = isAutoRenewal;
            if (autoRenewalEl) {
                autoRenewalEl.textContent = isAutoRenewal ? 'Ativa' : 'Inativa';
                autoRenewalEl.className = isAutoRenewal ? 'text-green-400' : 'text-red-400';
            }
        }
    }
    
    renderRecentTransactions(transactions) {
        const container = document.querySelector('[data-recent-transactions]');
        if (!container) return;
        
        if (!transactions || transactions.length === 0) {
            container.innerHTML = `
                <div class="p-4 text-center text-gray-400">
                    <span class="material-icons text-4xl mb-2 opacity-50">receipt</span>
                    <p>Nenhuma transação recente</p>
                </div>
            `;
            return;
        }
        
        const transactionsHtml = transactions.map(transaction => `
            <div class="p-4 flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 bg-blue-500/20 rounded-full flex items-center justify-center">
                        <span class="material-icons text-blue-400 text-sm">payment</span>
                    </div>
                    <div>
                        <div class="text-white font-medium">${transaction.description}</div>
                        <div class="text-gray-400 text-sm">${this.formatDate(transaction.created)}</div>
                    </div>
                </div>
                <div class="text-right">
                    <div class="text-white font-medium">R$ ${(transaction.amount / 100).toFixed(2).replace('.', ',')}</div>
                    <div class="text-sm ${
                        transaction.status === 'succeeded' ? 'text-green-400' : 
                        transaction.status === 'pending' ? 'text-yellow-400' : 'text-red-400'
                    }">
                        ${transaction.status === 'succeeded' ? 'Pago' : 
                          transaction.status === 'pending' ? 'Pendente' : 'Falhou'}
                    </div>
                </div>
            </div>
        `).join('');
        
        container.innerHTML = transactionsHtml;
    }

    // Verificar se há parâmetros de sucesso/erro do Stripe na URL
    checkUrlParams() {
        const urlParams = new URLSearchParams(window.location.search);
        const sessionId = urlParams.get('session_id');
        
        if (sessionId) {
            this.handleCheckoutSuccess(sessionId);
            // Limpar URL
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    }
    
    async handleCheckoutSuccess(sessionId) {
        try {
            this.showSuccess('Pagamento processado com sucesso! Atualizando dados...');
            
            // Verificar sessão de checkout
            const response = await AuthUtils.authenticatedFetch(`/api/v1/stripe/checkout-session/${sessionId}`);
            const session = await response.json();
            
            if (session.payment_status === 'paid') {
                // Recarregar dados da assinatura
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            }
            
        } catch (error) {
            console.error('❌ Erro ao verificar checkout:', error);
            this.showError('Erro ao verificar pagamento');
        }
    }

    formatDate(dateString) {
        if (!dateString) return 'N/A';
        
        const date = new Date(dateString);
        return date.toLocaleDateString('pt-BR');
    }

    showLoading(message) {
        const overlay = document.getElementById('loading-overlay') || this.createLoadingOverlay();
        const loadingText = overlay.querySelector('.loading-text');
        if (loadingText) {
            loadingText.textContent = message;
        }
        overlay.classList.remove('hidden');
        console.log('⏳', message);
    }

    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('hidden');
        }
        console.log('✅ Loading finalizado');
    }
    
    createLoadingOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        overlay.innerHTML = `
            <div class="bg-gray-800 rounded-lg p-6 flex items-center space-x-3">
                <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
                <span class="text-white loading-text">Carregando...</span>
            </div>
        `;
        document.body.appendChild(overlay);
        return overlay;
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
        console.log('✅', message);
    }

    showError(message) {
        this.showNotification(message, 'error');
        console.error('❌', message);
    }
    
    showNotification(message, type) {
        // Criar notificação toast
        const notification = document.createElement('div');
        const bgColor = type === 'success' ? 'bg-green-600' : 'bg-red-600';
        
        notification.className = `fixed top-4 right-4 ${bgColor} text-white px-6 py-3 rounded-lg shadow-lg z-50 transition-all transform translate-x-full`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Animar entrada
        setTimeout(() => {
            notification.classList.remove('translate-x-full');
        }, 10);
        
        // Remover após 5 segundos
        setTimeout(() => {
            notification.classList.add('translate-x-full');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 5000);
    }

    showErrorState(message) {
        console.warn('⚠️ Estado de erro em assinaturas:', message);
        
        const plansContainer = document.querySelector('#planos-container');
        const currentPlanSection = document.querySelector('#current-plan');
        
        if (plansContainer) {
            plansContainer.innerHTML = `
                <div class="text-center py-8 text-red-500">
                    <i class="fas fa-exclamation-triangle text-4xl mb-4"></i>
                    <h3 class="text-xl font-bold mb-2">Erro ao Carregar</h3>
                    <p>${message}</p>
                    <button onclick="location.reload()" class="mt-4 bg-red-600 text-white px-6 py-2 rounded hover:bg-red-700">
                        Tentar Novamente
                    </button>
                </div>
            `;
        }
        
        if (currentPlanSection) {
            currentPlanSection.innerHTML = `
                <div class="bg-red-50 border border-red-200 rounded-lg p-6 text-red-700">
                    <h3 class="font-bold">Erro: ${message}</h3>
                </div>
            `;
        }
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    const manager = new AssinaturaManager();
    
    // Verificar parâmetros da URL após inicialização
    setTimeout(() => {
        manager.checkUrlParams();
    }, 1000);
});

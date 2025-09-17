/**
 * JavaScript para página de Assinatura
 * Gerencia planos de assinatura e upgrades/downgrades
 */

class AssinaturaManager {
    constructor() {
        this.currentPlan = null;
        this.availablePlans = [];
        this.userSubscription = null;
        
        this.init();
    }

    async init() {
        console.log('🚀 Inicializando AssinaturaManager...');
        
        try {
            await this.loadPlans();
            await this.loadCurrentSubscription();
            this.setupEventListeners();
            this.renderPlans();
            this.renderCurrentSubscription();
        } catch (error) {
            console.error('❌ Erro ao inicializar AssinaturaManager:', error);
            this.showError('Erro ao carregar dados da assinatura');
        }
    }

    async loadPlans() {
        try {
            const response = await fetch('/api/v1/subscription-plans');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.availablePlans = data.plans || [];
            console.log('✅ Planos carregados:', this.availablePlans.length);
        } catch (error) {
            console.error('❌ Erro ao carregar planos:', error);
            // Fallback para dados mock
            this.availablePlans = this.getMockPlans();
        }
    }

    async loadCurrentSubscription() {
        try {
            const response = await fetch('/api/v1/subscription/current');
            if (!response.ok) {
                if (response.status === 401) {
                    console.log('⚠️ Usuário não autenticado, usando modo demo');
                    this.userSubscription = this.getMockSubscription();
                    return;
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.userSubscription = data.subscription;
            console.log('✅ Assinatura atual carregada:', this.userSubscription);
        } catch (error) {
            console.error('❌ Erro ao carregar assinatura:', error);
            this.userSubscription = this.getMockSubscription();
        }
    }

    setupEventListeners() {
        // Botões de upgrade/downgrade
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-plan-action]')) {
                const action = e.target.dataset.planAction;
                const planId = e.target.dataset.planId;
                this.handlePlanAction(action, planId);
            }
        });

        // Botão de cancelar assinatura
        const cancelBtn = document.querySelector('[data-cancel-subscription]');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.handleCancelSubscription());
        }

        // Botão de reativar assinatura
        const reactivateBtn = document.querySelector('[data-reactivate-subscription]');
        if (reactivateBtn) {
            reactivateBtn.addEventListener('click', () => this.handleReactivateSubscription());
        }
    }

    renderPlans() {
        const plansContainer = document.querySelector('[data-plans-container]');
        if (!plansContainer) return;

        const plansHtml = this.availablePlans.map(plan => {
            const isCurrentPlan = this.userSubscription && 
                this.userSubscription.plan_id === plan.id;
            const isRecommended = plan.name === 'Professional';
            
            return `
                <div class="plan-card ${isCurrentPlan ? 'current-plan' : ''} ${isRecommended ? 'recommended' : ''}" 
                     data-plan-id="${plan.id}">
                    ${isRecommended ? '<div class="recommended-badge">Recomendado</div>' : ''}
                    ${isCurrentPlan ? '<div class="current-badge">Plano Atual</div>' : ''}
                    
                    <div class="plan-header">
                        <h3 class="plan-name">${plan.name}</h3>
                        <div class="plan-price">
                            <span class="currency">R$</span>
                            <span class="amount">${(plan.price_cents / 100).toFixed(2).replace('.', ',')}</span>
                            <span class="period">/mês</span>
                        </div>
                    </div>
                    
                    <div class="plan-description">
                        <p>${plan.description}</p>
                    </div>
                    
                    <div class="plan-features">
                        <div class="feature">
                            <span class="feature-icon">📊</span>
                            <span class="feature-text">
                                ${plan.queries_limit ? `${plan.queries_limit} consultas/mês` : 'Consultas ilimitadas'}
                            </span>
                        </div>
                        <div class="feature">
                            <span class="feature-icon">🔑</span>
                            <span class="feature-text">
                                ${plan.api_keys_limit ? `${plan.api_keys_limit} chaves de API` : 'Chaves ilimitadas'}
                            </span>
                        </div>
                        <div class="feature">
                            <span class="feature-icon">📈</span>
                            <span class="feature-text">Analytics avançado</span>
                        </div>
                        <div class="feature">
                            <span class="feature-icon">🛡️</span>
                            <span class="feature-text">Suporte prioritário</span>
                        </div>
                    </div>
                    
                    <div class="plan-actions">
                        ${this.renderPlanAction(plan, isCurrentPlan)}
                    </div>
                </div>
            `;
        }).join('');

        plansContainer.innerHTML = plansHtml;
    }

    renderPlanAction(plan, isCurrentPlan) {
        if (isCurrentPlan) {
            return `
                <button class="btn btn-secondary" disabled>
                    Plano Atual
                </button>
            `;
        }

        const currentPlanPrice = this.userSubscription ? 
            this.availablePlans.find(p => p.id === this.userSubscription.plan_id)?.price_cents || 0 : 0;
        
        if (plan.price_cents > currentPlanPrice) {
            return `
                <button class="btn btn-primary" 
                        data-plan-action="upgrade" 
                        data-plan-id="${plan.id}">
                    Fazer Upgrade
                </button>
            `;
        } else if (plan.price_cents < currentPlanPrice) {
            return `
                <button class="btn btn-outline" 
                        data-plan-action="downgrade" 
                        data-plan-id="${plan.id}">
                    Fazer Downgrade
                </button>
            `;
        } else {
            return `
                <button class="btn btn-primary" 
                        data-plan-action="subscribe" 
                        data-plan-id="${plan.id}">
                    Assinar
                </button>
            `;
        }
    }

    renderCurrentSubscription() {
        const subscriptionContainer = document.querySelector('[data-current-subscription]');
        if (!subscriptionContainer || !this.userSubscription) return;

        const plan = this.availablePlans.find(p => p.id === this.userSubscription.plan_id);
        if (!plan) return;

        const statusClass = this.userSubscription.status === 'active' ? 'success' : 'warning';
        const statusText = this.userSubscription.status === 'active' ? 'Ativa' : 'Inativa';

        subscriptionContainer.innerHTML = `
            <div class="subscription-card">
                <div class="subscription-header">
                    <h3>Assinatura Atual</h3>
                    <span class="status-badge ${statusClass}">${statusText}</span>
                </div>
                
                <div class="subscription-details">
                    <div class="detail-row">
                        <span class="label">Plano:</span>
                        <span class="value">${plan.name}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Valor:</span>
                        <span class="value">R$ ${(plan.price_cents / 100).toFixed(2).replace('.', ',')}/mês</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Próxima cobrança:</span>
                        <span class="value">${this.formatDate(this.userSubscription.current_period_end)}</span>
                    </div>
                    <div class="detail-row">
                        <span class="label">Consultas restantes:</span>
                        <span class="value">${this.getRemainingQueries()}</span>
                    </div>
                </div>
                
                <div class="subscription-actions">
                    ${this.userSubscription.status === 'active' ? `
                        <button class="btn btn-outline" data-cancel-subscription>
                            Cancelar Assinatura
                        </button>
                    ` : `
                        <button class="btn btn-primary" data-reactivate-subscription>
                            Reativar Assinatura
                        </button>
                    `}
                </div>
            </div>
        `;
    }

    async handlePlanAction(action, planId) {
        const plan = this.availablePlans.find(p => p.id === planId);
        if (!plan) return;

        try {
            this.showLoading(`Processando ${action}...`);

            const response = await fetch('/api/v1/subscription/change', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    plan_id: planId,
                    action: action
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || `Erro ao ${action}`);
            }

            const result = await response.json();
            
            this.showSuccess(`${action} realizado com sucesso!`);
            
            // Recarregar dados
            await this.loadCurrentSubscription();
            this.renderPlans();
            this.renderCurrentSubscription();
            
        } catch (error) {
            console.error(`❌ Erro ao ${action}:`, error);
            this.showError(`Erro ao ${action}: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    async handleCancelSubscription() {
        if (!confirm('Tem certeza que deseja cancelar sua assinatura?')) {
            return;
        }

        try {
            this.showLoading('Cancelando assinatura...');

            const response = await fetch('/api/v1/subscription/cancel', {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Erro ao cancelar assinatura');
            }

            this.showSuccess('Assinatura cancelada com sucesso!');
            
            // Recarregar dados
            await this.loadCurrentSubscription();
            this.renderPlans();
            this.renderCurrentSubscription();
            
        } catch (error) {
            console.error('❌ Erro ao cancelar assinatura:', error);
            this.showError(`Erro ao cancelar assinatura: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    async handleReactivateSubscription() {
        try {
            this.showLoading('Reativando assinatura...');

            const response = await fetch('/api/v1/subscription/reactivate', {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Erro ao reativar assinatura');
            }

            this.showSuccess('Assinatura reativada com sucesso!');
            
            // Recarregar dados
            await this.loadCurrentSubscription();
            this.renderPlans();
            this.renderCurrentSubscription();
            
        } catch (error) {
            console.error('❌ Erro ao reativar assinatura:', error);
            this.showError(`Erro ao reativar assinatura: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    getRemainingQueries() {
        if (!this.userSubscription) return 'N/A';
        
        const plan = this.availablePlans.find(p => p.id === this.userSubscription.plan_id);
        if (!plan || !plan.queries_limit) return 'Ilimitadas';
        
        // Aqui você implementaria a lógica para calcular consultas restantes
        // Por enquanto, retornamos um valor mock
        return `${Math.floor(Math.random() * plan.queries_limit)} / ${plan.queries_limit}`;
    }

    formatDate(dateString) {
        if (!dateString) return 'N/A';
        
        const date = new Date(dateString);
        return date.toLocaleDateString('pt-BR');
    }

    showLoading(message) {
        // Implementar loading
        console.log('⏳', message);
    }

    hideLoading() {
        // Implementar hide loading
        console.log('✅ Loading finalizado');
    }

    showSuccess(message) {
        // Implementar notificação de sucesso
        console.log('✅', message);
        alert(message);
    }

    showError(message) {
        // Implementar notificação de erro
        console.error('❌', message);
        alert(message);
    }

    // Dados mock para desenvolvimento
    getMockPlans() {
        return [
            {
                id: '1',
                name: 'Starter',
                description: 'Plano básico para começar',
                price_cents: 2990,
                queries_limit: 100,
                api_keys_limit: 1
            },
            {
                id: '2',
                name: 'Professional',
                description: 'Plano profissional com mais recursos',
                price_cents: 9990,
                queries_limit: 1000,
                api_keys_limit: 5
            },
            {
                id: '3',
                name: 'Enterprise',
                description: 'Plano empresarial com recursos ilimitados',
                price_cents: 29990,
                queries_limit: null,
                api_keys_limit: null
            }
        ];
    }

    getMockSubscription() {
        return {
            id: 'sub-123',
            plan_id: '1',
            status: 'active',
            current_period_start: new Date().toISOString(),
            current_period_end: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
        };
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    new AssinaturaManager();
});

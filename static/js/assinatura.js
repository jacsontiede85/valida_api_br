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
        this.consultationTypes = [];  // Para tabela de preços
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
            
            // Carregar dados - ORDEM IMPORTANTE: consultation types primeiro para atualizar custos
            await this.loadConsultationTypes(); // 1º - Carregar custos REAIS da tabela
            
            await Promise.all([
                this.loadCosts(), // 2º - Carregar custos fallback (caso consultation_types falhe)
                this.loadPlans(),
                this.loadCurrentSubscription(),
                this.loadRecentTransactions(),
                this.loadUserCredits()
            ]);
            
            this.setupEventListeners();
            this.renderPlans();
            this.renderCurrentSubscription();
            this.updateAutoRenewalToggle();
            
            // ✅ CORREÇÃO: Re-renderizar assinatura após carregamento completo
            setTimeout(() => {
                console.log('🔄 Re-renderizando assinatura após carregamento completo...');
                this.renderCurrentSubscription();
            }, 500);
            
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

    async loadConsultationTypes() {
        try {
            const data = await AuthUtils.authenticatedFetchJSON('/api/v1/stripe/consultation-types');
            this.consultationTypes = data.consultation_types || [];
            
            // ✅ CORREÇÃO: Atualizar this.costs com dados REAIS da tabela consultation_types
            if (this.consultationTypes.length > 0) {
                this.consultationTypes.forEach(type => {
                    const code = type.code.toLowerCase();
                    const costInReais = type.cost_reais; // Já vem convertido do backend
                    
                    if (code === 'protestos') {
                        this.costs.protestos = costInReais;
                    } else if (code === 'receita_federal') {
                        this.costs.receita_federal = costInReais;
                    } else if (code === 'outros') {
                        this.costs.outros = costInReais;
                    }
                });
                
                console.log('✅ Custos REAIS atualizados da tabela consultation_types:', this.costs);
                
                // Re-renderizar estimativas dos planos com custos corretos
                this.renderPlans();
            }
            
            this.renderPricingTable(this.consultationTypes);
            console.log('✅ Tipos de consulta carregados:', this.consultationTypes.length);
        } catch (error) {
            console.error('❌ Erro ao carregar tipos de consulta:', error);
            this.consultationTypes = [];
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

        // ✅ CORREÇÃO: Limpar container mantendo template E card dinâmico
        Array.from(plansContainer.children).forEach(child => {
            const shouldKeep = child.hasAttribute('data-plan-template') || 
                             child.classList.contains('dynamic-product-card');
            
            if (!shouldKeep) {
                child.remove();
            }
        });
        
        console.log('🔍 DEBUG: Cards preservados no container:', {
            template: !!plansContainer.querySelector('[data-plan-template]'),
            dynamic: !!plansContainer.querySelector('.dynamic-product-card'),
            total: plansContainer.children.length
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
        
        // ✅ NOVO: Serviços específicos solicitados pelo usuário
        const availableServices = [
            { icon: 'warning', text: 'Consulta de Protestos', color: 'from-yellow-400 to-orange-500' },
            { icon: 'account_balance', text: 'Receita Federal', color: 'from-green-400 to-emerald-500' },
            { icon: 'business', text: 'Cadastro de Contribuintes (IE)', color: 'from-blue-400 to-cyan-500' },
            { icon: 'folder', text: 'Simples Nacional', color: 'from-purple-400 to-pink-500' },
            { icon: 'place', text: 'Geocodificação', color: 'from-indigo-400 to-blue-500' },
            { icon: 'help_outline', text: 'Suframa', color: 'from-teal-400 to-green-500' },
            { icon: 'web', text: 'Consultas pelo site', color: 'from-orange-400 to-red-500' },
            { icon: 'api', text: 'Consultas com API', color: 'from-cyan-400 to-blue-500' },
            { icon: 'history', text: 'Histórico detalhado de consultas', color: 'from-gray-400 to-slate-500' }
        ];
        
        // Adicionar todos os serviços solicitados
        features.push(...availableServices);
        
        // ✅ REMOVIDO: Recursos adicionais não solicitados pelo usuário
        // Apenas os serviços específicos solicitados serão exibidos
        
        const featuresHtml = features.map(feature => `
            <div class="flex items-center text-slate-300 group">
                <div class="w-6 h-6 mr-3 bg-gradient-to-r ${feature.color} rounded-full flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                    <span class="material-icons text-white text-xs">${feature.icon}</span>
                </div>
                <span class="text-sm group-hover:text-white transition-colors duration-300">${feature.text}</span>
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

        console.log('🔍 DEBUG - Renderizando assinatura:', this.userSubscription);
        console.log('🔍 DEBUG - Planos disponíveis:', this.availablePlans);

        // Atualizar informações da assinatura atual
        const planNameEl = document.querySelector('[data-current-plan-name]');
        const statusEl = document.querySelector('[data-current-status]');
        const priceEl = document.querySelector('[data-current-price]');
        const creditsAvailableEl = document.querySelector('[data-credits-available]');
        const creditsTotalEl = document.querySelector('[data-credits-total]');
        const creditsUsedEl = document.querySelector('[data-credits-used]');
        
        // ✅ CRÍTICO: Limpar elementos de loading primeiro
        this.clearLoadingStates();
        
        // ✅ CORREÇÃO: Usar dados diretos da assinatura do banco local
        if (this.userSubscription.plan_name && this.userSubscription.price_cents) {
            // Usar dados da assinatura atual do banco
            const planName = this.userSubscription.plan_name;
            const priceAmount = this.userSubscription.price_cents / 100;
            
            // Atualizar nome do plano
            if (planNameEl) {
                planNameEl.innerHTML = planName;
                planNameEl.className = 'text-white font-bold text-xl';
                console.log('✅ Plano atual definido:', planName);
            }
            
            // Atualizar valor mensal
            if (priceEl) {
                const formattedPrice = `R$ ${priceAmount.toFixed(2).replace('.', ',')}`;
                priceEl.innerHTML = formattedPrice;
                priceEl.className = 'text-white font-bold text-xl';
                console.log('✅ Valor mensal definido:', formattedPrice);
            }
        } else {
            // Fallback para dados do Stripe se não houver dados locais
            if (this.userSubscription.items?.data[0]) {
                const subscriptionItem = this.userSubscription.items.data[0];
                const priceObj = subscriptionItem.price;
                
                console.log('🔍 DEBUG - Item da assinatura:', subscriptionItem);
                console.log('🔍 DEBUG - Objeto de preço:', priceObj);
                
                // Tentar diferentes formas de encontrar o produto
                let product = null;
                if (priceObj?.product) {
                    // 1. Buscar por ID do produto
                    product = this.availablePlans.find(p => p.id === priceObj.product);
                    
                    // 2. Se não encontrar, buscar por default_price
                    if (!product) {
                        product = this.availablePlans.find(p => p.default_price === subscriptionItem.price.id);
                    }
                    
                    // 3. Se ainda não encontrar, buscar por stripe_product_id (sincronização local)
                    if (!product) {
                        product = this.availablePlans.find(p => p.stripe_product_id === priceObj.product);
                    }
                    
                    console.log('🔍 DEBUG - Produto encontrado:', product);
                }
                
                // Atualizar nome do plano
                if (planNameEl) {
                    if (product && product.name) {
                        planNameEl.innerHTML = product.name;
                        planNameEl.className = 'text-white font-bold text-xl';
                        console.log('✅ Plano atual definido:', product.name);
                    } else {
                        // Fallback: usar dados da assinatura diretamente
                        const planName = priceObj?.nickname || 
                                       `Plano ${(priceObj.unit_amount / 100).toFixed(0).replace('.', ',')}` ||
                                       (priceObj?.recurring?.interval === 'month' ? 'Plano Mensal' : 'Plano Personalizado');
                        planNameEl.innerHTML = planName;
                        planNameEl.className = 'text-white font-bold text-xl';
                        console.log('✅ Plano atual (fallback):', planName);
                    }
                }
                
                // Atualizar valor mensal
                if (priceEl && priceObj) {
                    const amount = priceObj.unit_amount / 100;
                    const formattedPrice = `R$ ${amount.toFixed(2).replace('.', ',')}`;
                    priceEl.innerHTML = formattedPrice;
                    priceEl.className = 'text-white font-bold text-xl';
                    console.log('✅ Valor mensal definido:', formattedPrice);
                }
            } else {
                console.log('⚠️ Sem itens na assinatura - usando valores padrão');
                // Fallback se não houver items na assinatura
                if (planNameEl) {
                    planNameEl.innerHTML = 'Plano Ativo';
                    planNameEl.className = 'text-white font-bold text-xl';
                }
                if (priceEl) {
                    priceEl.innerHTML = 'Consultar suporte';
                    priceEl.className = 'text-slate-400 font-bold text-xl';
                }
            }
        }
        
        // Atualizar status da assinatura
        if (statusEl) {
            const status = this.userSubscription.status;
            const statusText = {
                'active': 'Ativa',
                'canceled': 'Cancelada',
                'past_due': 'Atrasada',
                'unpaid': 'Não paga'
            }[status] || status;
            
            const statusClass = status === 'active' ? 'bg-green-400 text-green-900' : 'bg-red-400 text-red-900';
            statusEl.innerHTML = statusText;
            statusEl.className = `inline-flex px-3 py-1 rounded-full text-xs font-bold ${statusClass}`;
            console.log('✅ Status definido:', statusText);
        }
        
        // Carregar créditos do usuário
        this.loadUserCredits();
        
        console.log('✅ Renderização da assinatura concluída');
    }
    
    // ✅ NOVO MÉTODO: Limpar estados de loading
    clearLoadingStates() {
        console.log('🧹 Limpando estados de loading...');
        
        // Remover todas as divs de loading shimmer
        const loadingElements = document.querySelectorAll('.loading-shimmer');
        loadingElements.forEach(el => el.remove());
        
        // Garantir que os elementos principais estejam limpos
        const planNameEl = document.querySelector('[data-current-plan-name]');
        const priceEl = document.querySelector('[data-current-price]');
        
        if (planNameEl && planNameEl.querySelector('.loading-shimmer')) {
            planNameEl.innerHTML = '';
        }
        if (priceEl && priceEl.querySelector('.loading-shimmer')) {
            priceEl.innerHTML = '';
        }
        
        console.log('✅ Estados de loading removidos');
    }
    
    renderNoSubscription() {
        console.log('⚠️ Nenhuma assinatura encontrada - renderizando estado vazio');
        
        // ✅ Limpar estados de loading primeiro
        this.clearLoadingStates();
        
        const planNameEl = document.querySelector('[data-current-plan-name]');
        const statusEl = document.querySelector('[data-current-status]');
        const priceEl = document.querySelector('[data-current-price]');
        
        // Definir valores padrão
        if (planNameEl) {
            planNameEl.innerHTML = 'Nenhuma assinatura ativa';
            planNameEl.className = 'text-slate-400 text-xl font-medium';
        }
        if (statusEl) {
            statusEl.innerHTML = 'Inativa';
            statusEl.className = 'inline-flex px-3 py-1 rounded-full text-xs font-bold bg-gray-500 text-gray-100';
        }
        if (priceEl) {
            priceEl.innerHTML = 'R$ 0,00';
            priceEl.className = 'text-slate-400 text-xl font-medium';
        }
        
        console.log('✅ Estado "sem assinatura" renderizado');
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

    async handleCustomPlanSelection(amount) {
        try {
            this.showLoading(`Criando plano personalizado de R$ ${amount.toFixed(2).replace('.', ',')}...`);

            // Validar valor
            if (amount < 1 || amount > 10000) {
                throw new Error('Valor deve estar entre R$ 1,00 e R$ 10.000,00');
            }

            // Criar plano personalizado via API
            const response = await AuthUtils.authenticatedFetch('/api/v1/stripe/create-custom-subscription', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    amount: amount,
                    success_url: window.location.origin + '/assinatura?session_id={CHECKOUT_SESSION_ID}&custom=true',
                    cancel_url: window.location.origin + '/assinatura'
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Erro ao criar plano personalizado');
            }

            const result = await response.json();
            
            console.log('✅ Plano personalizado criado:', result);
            this.showSuccess(`Plano de R$ ${amount.toFixed(2).replace('.', ',')} criado! Redirecionando...`);
            
            // Redirecionar para checkout
            setTimeout(() => {
                window.location.href = result.checkout_url;
            }, 1000);

        } catch (error) {
            console.error('❌ Erro ao criar plano personalizado:', error);
            this.showError(`Erro ao criar plano personalizado: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    async handleDynamicPlanSelection(amount) {
        /**
         * ✅ NOVA FUNÇÃO: Cria produto dinamicamente no Stripe
         */
        try {
            this.showLoading(`Criando produto automaticamente no Stripe para R$ ${amount.toFixed(2).replace('.', ',')}...`);

            // Validar valor
            if (amount < 1 || amount > 10000) {
                throw new Error('Valor deve estar entre R$ 1,00 e R$ 10.000,00');
            }

            // Criar produto dinamicamente via API
            const response = await AuthUtils.authenticatedFetch('/api/v1/stripe/create-dynamic-product', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    amount: amount,
                    success_url: window.location.origin + '/assinatura?session_id={CHECKOUT_SESSION_ID}&dynamic=true',
                    cancel_url: window.location.origin + '/assinatura'
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Erro ao criar produto dinâmico');
            }

            const result = await response.json();
            
            console.log('✅ Produto dinâmico criado no Stripe:', result);
            this.showSuccess(`Produto R$ ${amount.toFixed(2).replace('.', ',')} criado automaticamente! Redirecionando...`);
            
            // Redirecionar para checkout
            setTimeout(() => {
                window.location.href = result.checkout_url;
            }, 1500);

        } catch (error) {
            console.error('❌ Erro ao criar produto dinâmico:', error);
            this.showError(`Erro ao criar produto dinâmico: ${error.message}`);
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
                throw new Error(error.detail || 'Erro ao atualizar renovação automática');
            }

            const result = await response.json();
            const message = enabled ? 'Renovação automática ativada' : 'Renovação automática desativada';
            this.showSuccess(message);
            
            // Atualizar UI
            const statusEl = document.querySelector('[data-auto-renewal]');
            if (statusEl) {
                statusEl.textContent = enabled ? 'Ativa' : 'Inativa';
                statusEl.className = enabled ? 'text-green-400 font-bold' : 'text-red-400 font-bold';
            }
            
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

    renderPricingTable(consultationTypes) {
        const container = document.querySelector('[data-pricing-table]');
        if (!container || !consultationTypes.length) return;
        
        const tableHtml = `
            <div class="modern-card p-6">
                <div class="flex items-center gap-4 mb-6">
                    <div class="w-12 h-12 bg-gradient-to-r from-amber-400 to-orange-500 rounded-xl flex items-center justify-center">
                        <span class="material-icons text-white text-xl">price_check</span>
                    </div>
                    <div>
                        <h3 class="text-white text-xl font-bold">Tabela de Preços</h3>
                        <p class="text-slate-400 text-sm">Custos por consulta - transparência total</p>
                    </div>
                </div>
                
                <div class="overflow-hidden rounded-xl border border-slate-600/30">
                    <div class="overflow-x-auto">
                        <table class="w-full">
                            <thead>
                                <tr class="bg-slate-700/50">
                                    <th class="text-left py-3 px-4 text-slate-300 font-semibold text-sm">Serviço</th>
                                    <th class="text-left py-3 px-4 text-slate-300 font-semibold text-sm">Descrição</th>
                                    <th class="text-center py-3 px-4 text-slate-300 font-semibold text-sm">Preço</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-600/20">
                                ${consultationTypes.map(type => {
                                    // Personalizar descrição para protestos
                                    let description = type.description;
                                    if (type.code.toLowerCase() === 'protestos') {
                                        description = 'Consulta de protestos no CenProt Nacional';
                                    }
                                    
                                    return `
                                    <tr class="hover:bg-slate-700/30 transition-colors">
                                        <td class="py-4 px-4">
                                            <div class="flex items-center gap-3">
                                                <div class="w-8 h-8 bg-gradient-to-r from-blue-400 to-cyan-500 rounded-lg flex items-center justify-center">
                                                    <span class="material-icons text-white text-sm">${this.getServiceIcon(type.code)}</span>
                                                </div>
                                                <span class="text-white font-medium">${type.name}</span>
                                            </div>
                                        </td>
                                        <td class="py-4 px-4 text-slate-300 text-sm">${description}</td>
                                         <td class="py-4 px-8 text-center"> <!-- px-8 deixa a coluna de preço mais larga -->
                                            <span class="text-emerald-400 font-bold text-base">R$ ${type.cost_reais.toFixed(2)}</span>
                                        </td>
                                    </tr>
                                `;
                                }).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
                
                <div class="mt-4 p-4 bg-amber-500/10 rounded-xl border border-amber-500/20">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="material-icons text-amber-400 text-sm">info</span>
                        <span class="text-amber-300 font-semibold text-sm">Informação Importante</span>
                    </div>
                    <p class="text-amber-200/80 text-xs">
                        Os preços são cobrados por consulta realizada e debitados automaticamente do seu saldo de créditos. 
                        Consultas com erro não são cobradas.
                    </p>
                </div>
            </div>
        `;
        
        container.innerHTML = tableHtml;
    }

    getServiceIcon(serviceCode) {
        const icons = {
            'protestos': 'warning',
            'receita_federal': 'account_balance',
            'simples_nacional': 'business',
            'cnae': 'category',
            'socios': 'people',
            'endereco': 'place'
        };
        return icons[serviceCode] || 'help_outline';
    }
    
    updateAutoRenewalToggle() {
        const toggle = document.getElementById('auto-renewal-toggle');
        const autoRenewalEl = document.querySelector('[data-auto-renewal]');
        const indicator = document.querySelector('.renewal-indicator');
        
        if (this.userSubscription && this.userSubscription.cancel_at_period_end !== null) {
            const isAutoRenewal = !this.userSubscription.cancel_at_period_end;
            
            if (toggle) {
                toggle.checked = isAutoRenewal;
            }
            
            if (autoRenewalEl) {
                autoRenewalEl.textContent = isAutoRenewal ? 'Ativa' : 'Inativa';
                if (isAutoRenewal) {
                    autoRenewalEl.className = 'text-green-400 text-sm font-bold renewal-status';
                } else {
                    autoRenewalEl.className = 'text-red-400 text-sm font-bold renewal-status inactive';
                }
            }
            
            if (indicator) {
                if (isAutoRenewal) {
                    indicator.className = 'w-2 h-2 bg-green-400 rounded-full animate-pulse renewal-indicator';
                } else {
                    indicator.className = 'w-2 h-2 bg-red-400 rounded-full animate-pulse renewal-indicator inactive';
                }
            }
        } else {
            // Estado padrão: ativo
            if (toggle) toggle.checked = true;
            if (autoRenewalEl) {
                autoRenewalEl.textContent = 'Ativa';
                autoRenewalEl.className = 'text-green-400 text-sm font-bold renewal-status';
            }
            if (indicator) {
                indicator.className = 'w-2 h-2 bg-green-400 rounded-full animate-pulse renewal-indicator';
            }
        }
    }
    
    renderRecentTransactions(transactions) {
        const container = document.querySelector('[data-recent-transactions]');
        if (!container) return;
        
        if (!transactions || transactions.length === 0) {
            container.innerHTML = `
                <div class="p-8 text-center">
                    <div class="w-16 h-16 mx-auto mb-4 glass rounded-full flex items-center justify-center">
                        <span class="material-icons text-slate-400 text-2xl">shopping_cart</span>
                    </div>
                    <p class="text-slate-400 text-lg font-medium mb-2">Nenhuma compra realizada ainda</p>
                    <p class="text-slate-500 text-sm">Suas compras de créditos aparecerão aqui quando você adquirir planos</p>
                </div>
            `;
            return;
        }
        
        const transactionsHtml = transactions.map((transaction, index) => {
            const isPositive = transaction.type === 'add' || transaction.type === 'purchase';
            const iconName = isPositive ? 'add_circle' : 'remove_circle';
            const iconColor = isPositive ? 'from-green-400 to-emerald-500' : 'from-orange-400 to-red-500';
            const amountColor = isPositive ? 'text-green-400' : 'text-orange-400';
            const amountPrefix = isPositive ? '+' : '-';
            
            return `
                <div class="p-6 hover:bg-slate-700/20 transition-colors duration-300 group">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-4">
                            <div class="w-12 h-12 bg-gradient-to-r ${iconColor} rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform duration-300">
                                <span class="material-icons text-white">${iconName}</span>
                            </div>
                            <div class="flex-1">
                                <div class="text-white font-semibold text-lg mb-1">${transaction.description}</div>
                                <div class="flex items-center gap-3 text-sm">
                                    <span class="text-slate-400">${this.formatDate(transaction.created)}</span>
                                    <div class="w-1 h-1 bg-slate-500 rounded-full"></div>
                                    <div class="flex items-center gap-1">
                                        <div class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                                        <span class="text-green-400 font-medium">Processado</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="text-right">
                            <div class="${amountColor} font-bold text-xl">
                                ${amountPrefix}R$ ${(transaction.amount || 0).toFixed(2).replace('.', ',')}
                            </div>
                            <div class="text-slate-400 text-sm">
                                ${isPositive ? 'Crédito' : 'Débito'}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
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
        overlay.className = 'fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50';
        overlay.innerHTML = `
            <div class="modern-card p-8 max-w-md mx-4">
                <div class="text-center">
                    <div class="w-16 h-16 mx-auto mb-6 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
                        <div class="w-8 h-8 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    </div>
                    <h3 class="text-white text-xl font-bold mb-2">Processando</h3>
                    <p class="text-slate-400 loading-text">Carregando...</p>
                    <div class="mt-4 w-full bg-slate-600 rounded-full h-1 overflow-hidden">
                        <div class="w-full h-full bg-gradient-to-r from-blue-500 to-purple-600 rounded-full animate-pulse"></div>
                    </div>
                </div>
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
        // Criar notificação toast moderna
        const notification = document.createElement('div');
        const isSuccess = type === 'success';
        const iconName = isSuccess ? 'check_circle' : 'error';
        const colorClasses = isSuccess ? 
            'from-green-500 to-emerald-600' : 
            'from-red-500 to-rose-600';
        
        notification.className = `fixed top-6 right-6 max-w-sm bg-gradient-to-r ${colorClasses} text-white rounded-2xl shadow-2xl z-50 transition-all transform translate-x-full opacity-0 backdrop-blur-sm`;
        
        notification.innerHTML = `
            <div class="p-4 flex items-center gap-3">
                <div class="flex-shrink-0">
                    <span class="material-icons text-2xl">${iconName}</span>
                </div>
                <div class="flex-1">
                    <p class="font-semibold text-sm">${isSuccess ? 'Sucesso!' : 'Erro!'}</p>
                    <p class="text-sm opacity-90">${message}</p>
                </div>
                <button class="flex-shrink-0 p-1 hover:bg-white/20 rounded-full transition-colors" onclick="this.parentElement.parentElement.remove()">
                    <span class="material-icons text-lg">close</span>
                </button>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Animar entrada
        setTimeout(() => {
            notification.classList.remove('translate-x-full', 'opacity-0');
            notification.classList.add('translate-x-0', 'opacity-100');
        }, 10);
        
        // Remover após 6 segundos
        setTimeout(() => {
            notification.classList.add('translate-x-full', 'opacity-0');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 6000);
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
    
    // Expor instância globalmente para acesso externo
    window.assinaturaManager = manager;
    
    // Verificar parâmetros da URL após inicialização
    setTimeout(() => {
        manager.checkUrlParams();
    }, 1000);
});

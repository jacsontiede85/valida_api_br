/**
 * Cost Calculator v2.0 - Sistema de Cálculo de Custos em Tempo Real
 * Calcula custos transparentes baseado nos serviços selecionados
 */

class CostCalculatorV2 {
    constructor() {
        this.apiBaseUrl = '/api/v2';
        this.costs = {};  // Será carregado via API
        this.currentCredits = 0;
        this.init();
    }

    async init() {
        console.log('💰 Inicializando Cost Calculator v2.0');
        
        // Carregar custos reais da API
        await this.loadConsultationCosts();
        
        // Carregar créditos atuais
        await this.loadUserCredits();
        
        // Configurar eventos
        this.setupEventListeners();
        
        // Calcular custo inicial
        this.calculateCost();
        
        console.log('✅ Cost Calculator v2.0 inicializado');
    }

    async loadConsultationCosts() {
        try {
            // ✅ Usar o mesmo endpoint que o cost_loader.js para buscar da tabela consultation_types
            const response = await fetch(`${this.apiBaseUrl}/consultation/types`, {
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                // ✅ Converter tipos reais da tabela consultation_types em objeto de custos
                this.costs = {};
                console.log('📋 Tipos de consulta recebidos da API (Calculator):', data.types);
                
                data.types?.forEach(type => {
                    const code = type.code.toLowerCase();
                    
                    // Mapear códigos da tabela para os IDs usados no calculator
                    if (code === 'protestos') {
                        this.costs.protestos = type.cost_cents;
                    } else if (code === 'receita_federal') {
                        this.costs.receita_federal = type.cost_cents;
                    } else if (code === 'simples_nacional') {
                        this.costs.simples = type.cost_cents;
                    } else if (code === 'suframa') {
                        this.costs.suframa = type.cost_cents;
                    } else if (code === 'geocodificacao') {
                        this.costs.geocoding = type.cost_cents;
                    } else if (code === 'cadastro_contribuintes') {
                        this.costs.registrations = type.cost_cents;
                    }
                });
                
                console.log('💰 Custos REAIS carregados da tabela consultation_types (Calculator):', this.costs);
            } else {
                throw new Error(`API retornou status ${response.status}`);
            }
        } catch (error) {
            console.error('❌ Erro ao carregar custos da tabela consultation_types (Calculator):', error);
            // Fallback apenas em caso de erro real
            this.costs = {
                protestos: 15,      // R$ 0,15
                receita_federal: 5, // R$ 0,05
                simples: 5,         // R$ 0,05
                suframa: 5,         // R$ 0,05
                registrations: 5,   // R$ 0,05
                geocoding: 5        // R$ 0,05
            };
            console.warn('⚠️ Usando custos fallback no Calculator - verifique conexão com o banco');
        }
    }

    async loadUserCredits() {
        try {
            const token = localStorage.getItem('auth_token') || 
                         localStorage.getItem('api_key') || 
                         localStorage.getItem('dev_token');
            
            if (!token) return;

            const response = await fetch(`${this.apiBaseUrl}/dashboard/data`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.currentCredits = this.parseCurrency(data.credits?.available || 'R$ 0,00');
                this.updateCreditsDisplay();
                console.log(`💳 Créditos atuais: R$ ${(this.currentCredits / 100).toFixed(2)}`);
            }
        } catch (error) {
            console.error('❌ Erro ao carregar créditos:', error);
            this.currentCredits = 0; // R$ 0,00 se não conseguir carregar
            this.updateCreditsDisplay();
        }
    }

    parseCurrency(currencyString) {
        return Math.round(parseFloat(currencyString.replace('R$ ', '').replace(',', '.')) * 100);
    }

    formatCurrency(cents) {
        return (cents / 100).toLocaleString('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        });
    }

    setupEventListeners() {
        // Checkboxes de serviços
        const serviceCheckboxes = [
            'protestos',
            'receita-federal',  // Checkbox principal da Receita Federal
            'simples', 
            'suframa',
            'geocoding',
            'registrations'
        ];

        serviceCheckboxes.forEach(service => {
            const checkbox = document.getElementById(service);
            if (checkbox) {
                checkbox.addEventListener('change', () => {
                    this.calculateCost();
                    this.animateChange();
                });
            }
        });

        // Campo CNPJ (para validação)
        const cnpjInput = document.getElementById('cnpj');
        if (cnpjInput) {
            cnpjInput.addEventListener('input', () => {
                this.validateCNPJ(cnpjInput.value);
            });
        }

        // Botão de consulta
        const consultButton = document.querySelector('[data-consult-btn]');
        if (consultButton) {
            consultButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.performConsultation();
            });
        }

        // Botão de calcular custo manualmente
        const calculateBtn = document.querySelector('[data-calculate-cost]');
        if (calculateBtn) {
            calculateBtn.addEventListener('click', () => {
                this.calculateCost(true);
            });
        }
    }

    calculateCost(showAnimation = false) {
        let totalCost = 0;
        let selectedServices = [];
        let breakdown = [];

        // Verificar se serviços principais estão selecionados
        const protestosCheckbox = document.getElementById('protestos');
        const receitaFederalCheckbox = document.getElementById('receita-federal');
        
        // 1. Protestos (independente)
        if (protestosCheckbox && protestosCheckbox.checked) {
            totalCost += this.costs.protestos;
            selectedServices.push('protestos');
            breakdown.push({
                name: 'Protestos',
                cost: this.costs.protestos,
                formatted: this.formatCurrency(this.costs.protestos)
            });
        }

        // 2. Receita Federal e seus serviços (dependentes)
        if (receitaFederalCheckbox && receitaFederalCheckbox.checked) {
            // Custo base da Receita Federal (dados básicos)
            totalCost += this.costs.receita_federal;
            selectedServices.push('receita-federal');
            breakdown.push({
                name: 'Receita Federal (dados básicos)',
                cost: this.costs.receita_federal,
                formatted: this.formatCurrency(this.costs.receita_federal)
            });

            // Serviços adicionais da Receita Federal
            const receitaServices = {
                simples: { name: 'Simples Nacional', cost: this.costs.simples },
                suframa: { name: 'SUFRAMA', cost: this.costs.suframa },
                geocoding: { name: 'Geolocalização', cost: this.costs.geocoding },
                registrations: { name: 'Cadastro de Contribuintes', cost: this.costs.registrations }
            };

            Object.entries(receitaServices).forEach(([serviceId, service]) => {
                const checkbox = document.getElementById(serviceId);
                if (checkbox && checkbox.checked && !checkbox.disabled) {
                    totalCost += service.cost;
                    selectedServices.push(serviceId);
                    breakdown.push({
                        name: service.name,
                        cost: service.cost,
                        formatted: this.formatCurrency(service.cost)
                    });
                }
            });
        }

        // Atualizar interface
        this.updateCostDisplay(totalCost, breakdown, selectedServices, showAnimation);
        
        return {
            totalCost,
            selectedServices,
            breakdown,
            hasSufficientCredits: this.currentCredits >= totalCost,
            willTriggerAutoRenewal: this.currentCredits < totalCost
        };
    }

    updateCostDisplay(totalCost, breakdown, selectedServices, showAnimation = false) {
        // Atualizar custo total
        const totalElement = document.querySelector('[data-total-cost]');
        if (totalElement) {
            const formattedCost = this.formatCurrency(totalCost);
            totalElement.textContent = formattedCost;
            
            if (showAnimation) {
                this.animateElement(totalElement);
            }

            // Adicionar classe visual baseada na disponibilidade de créditos
            if (this.currentCredits >= totalCost) {
                totalElement.classList.add('text-green-400');
                totalElement.classList.remove('text-red-400', 'text-yellow-400');
            } else {
                totalElement.classList.add('text-red-400');
                totalElement.classList.remove('text-green-400', 'text-yellow-400');
            }
        }

        // Atualizar breakdown de custos
        this.updateCostBreakdown(breakdown);

        // Atualizar status dos créditos
        this.updateCreditsStatus(totalCost);

        // Atualizar estimativa de consultas possíveis
        this.updateQueryEstimate(totalCost);

        console.log(`💰 Custo calculado: ${this.formatCurrency(totalCost)} para ${selectedServices.length} serviços`);
    }

    updateCostBreakdown(breakdown) {
        const container = document.querySelector('[data-cost-breakdown]');
        if (!container) return;

        if (breakdown.length === 0) {
            container.innerHTML = `
                <div class="text-gray-400 text-sm text-center py-4">
                    ⚪ Selecione os serviços para ver o detalhamento dos custos
                </div>
            `;
            return;
        }

        container.innerHTML = breakdown.map(item => `
            <div class="flex items-center justify-between py-2 px-3 bg-gray-800 rounded-lg mb-2">
                <div class="flex items-center space-x-2">
                    <span class="w-2 h-2 bg-blue-400 rounded-full"></span>
                    <span class="text-sm text-gray-200">${item.name}</span>
                </div>
                <span class="text-sm text-blue-400 font-medium">${item.formatted}</span>
            </div>
        `).join('');
    }

    updateCreditsStatus(totalCost) {
        const statusElement = document.querySelector('[data-credits-status]');
        if (!statusElement) return;

        const hasEnoughCredits = this.currentCredits >= totalCost;
        const currentCreditsFormatted = this.formatCurrency(this.currentCredits);

        if (totalCost === 0) {
            statusElement.innerHTML = `
                <div class="text-gray-400 text-sm">
                    💳 Créditos disponíveis: ${currentCreditsFormatted}
                </div>
            `;
            return;
        }

        if (hasEnoughCredits) {
            const remainingCredits = this.currentCredits - totalCost;
            statusElement.innerHTML = `
                <div class="text-green-400 text-sm">
                    ✅ Créditos suficientes (${currentCreditsFormatted})
                    <div class="text-xs text-gray-400">
                        Restará: ${this.formatCurrency(remainingCredits)}
                    </div>
                </div>
            `;
        } else {
            const deficit = totalCost - this.currentCredits;
            statusElement.innerHTML = `
                <div class="text-yellow-400 text-sm">
                    🔄 Renovação automática será ativada
                    <div class="text-xs text-gray-400">
                        Faltam: ${this.formatCurrency(deficit)}
                    </div>
                </div>
            `;
        }
    }

    updateCreditsDisplay() {
        const element = document.querySelector('[data-user-credits]');
        if (element) {
            element.textContent = this.formatCurrency(this.currentCredits);
        }
    }

    updateQueryEstimate(totalCost) {
        const element = document.querySelector('[data-query-estimate]');
        if (!element || totalCost === 0) return;

        const possibleQueries = Math.floor(this.currentCredits / totalCost);
        const message = possibleQueries > 0 
            ? `Você pode fazer ${possibleQueries} consulta${possibleQueries > 1 ? 's' : ''} com os créditos atuais`
            : 'Créditos insuficientes - renovação automática será ativada';

        element.innerHTML = `
            <div class="text-xs text-gray-400 mt-2">
                📊 ${message}
            </div>
        `;
    }

    async performConsultation() {
        const costInfo = this.calculateCost();
        const cnpjInput = document.getElementById('cnpj');
        
        if (!cnpjInput || !cnpjInput.value) {
            this.showNotification('Por favor, digite um CNPJ válido', 'error');
            return;
        }

        if (!this.isValidCNPJ(cnpjInput.value)) {
            this.showNotification('CNPJ inválido', 'error');
            return;
        }

        if (costInfo.selectedServices.length === 0) {
            this.showNotification('Selecione pelo menos um serviço', 'warning');
            return;
        }

        // Mostrar confirmação com custo
        const confirmMessage = `
            Consulta CNPJ: ${cnpjInput.value}
            Custo total: ${this.formatCurrency(costInfo.totalCost)}
            Serviços: ${costInfo.breakdown.length}
            
            ${costInfo.willTriggerAutoRenewal ? '⚠️ Esta consulta ativará a renovação automática' : ''}
            
            Confirmar consulta?
        `;

        if (!confirm(confirmMessage)) return;

        try {
            // Simular consulta (implementar integração real)
            this.showNotification('Realizando consulta...', 'info');
            
            // Atualizar créditos localmente
            this.currentCredits -= costInfo.totalCost;
            this.updateCreditsDisplay();
            this.calculateCost(); // Recalcular com novos créditos
            
            setTimeout(() => {
                this.showNotification('Consulta realizada com sucesso!', 'success');
            }, 2000);
            
        } catch (error) {
            console.error('❌ Erro na consulta:', error);
            this.showNotification('Erro ao realizar consulta', 'error');
        }
    }

    validateCNPJ(cnpj) {
        const isValid = this.isValidCNPJ(cnpj);
        const input = document.getElementById('cnpj');
        
        if (input) {
            if (cnpj.length === 0) {
                input.classList.remove('border-red-500', 'border-green-500');
            } else if (isValid) {
                input.classList.add('border-green-500');
                input.classList.remove('border-red-500');
            } else {
                input.classList.add('border-red-500');
                input.classList.remove('border-green-500');
            }
        }
        
        return isValid;
    }

    isValidCNPJ(cnpj) {
        // Remover caracteres especiais
        cnpj = cnpj.replace(/[^\d]/g, '');
        
        // Verificar se tem 14 dígitos
        if (cnpj.length !== 14) return false;
        
        // Verificar se todos os dígitos são iguais
        if (/^(\d)\1+$/.test(cnpj)) return false;
        
        // Validar dígitos verificadores
        let sum = 0;
        const weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
        
        for (let i = 0; i < 12; i++) {
            sum += parseInt(cnpj[i]) * weights1[i];
        }
        
        let remainder = sum % 11;
        const digit1 = remainder < 2 ? 0 : 11 - remainder;
        
        if (parseInt(cnpj[12]) !== digit1) return false;
        
        sum = 0;
        const weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
        
        for (let i = 0; i < 13; i++) {
            sum += parseInt(cnpj[i]) * weights2[i];
        }
        
        remainder = sum % 11;
        const digit2 = remainder < 2 ? 0 : 11 - remainder;
        
        return parseInt(cnpj[13]) === digit2;
    }

    animateChange() {
        const totalElement = document.querySelector('[data-total-cost]');
        if (totalElement) {
            this.animateElement(totalElement);
        }
    }

    animateElement(element) {
        element.classList.add('animate-pulse');
        setTimeout(() => {
            element.classList.remove('animate-pulse');
        }, 500);
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 transition-all duration-300 ${
            type === 'success' ? 'bg-green-600' : 
            type === 'error' ? 'bg-red-600' : 
            type === 'warning' ? 'bg-yellow-600' : 'bg-blue-600'
        } text-white`;
        
        const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : type === 'warning' ? '⚠️' : 'ℹ️';
        
        notification.innerHTML = `
            <div class="flex items-center space-x-2">
                <span class="text-lg">${icon}</span>
                <span class="text-sm">${message}</span>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.transform = 'translateX(100%)';
            notification.style.opacity = '0';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    // Método para atualizar custos via API (caso mudem dinamicamente)
    async updateCostsFromAPI() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/costs/current`);
            if (response.ok) {
                const data = await response.json();
                this.costs = { ...this.costs, ...data };
                this.calculateCost();
                console.log('📊 Custos atualizados via API');
            }
        } catch (error) {
            console.warn('⚠️ Erro ao atualizar custos via API:', error);
        }
    }
}

// Função utilitária para formatar CNPJ
function formatCNPJ(value) {
    value = value.replace(/\D/g, '');
    value = value.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5');
    return value;
}

// Auto-aplicar formatação no campo CNPJ
document.addEventListener('DOMContentLoaded', () => {
    const cnpjInput = document.getElementById('cnpj');
    if (cnpjInput) {
        cnpjInput.addEventListener('input', (e) => {
            e.target.value = formatCNPJ(e.target.value);
        });
    }
});

// Inicializar quando a página carregar
document.addEventListener('DOMContentLoaded', () => {
    if (document.querySelector('[data-cost-calculator]') || document.getElementById('cnpj')) {
        window.costCalculatorV2 = new CostCalculatorV2();
        console.log('💰 Cost Calculator v2.0 inicializado!');
    }
});

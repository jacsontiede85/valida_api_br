/**
 * Cost Loader - Carrega custos reais da API e atualiza elementos HTML
 * Atualiza todos os elementos com data-cost, data-cost-display e data-cost-summary
 */

class CostLoader {
    constructor() {
        this.apiBaseUrl = '/api/v2';
        this.costs = {};
        this.init();
    }

    async init() {
        console.log('💰 Inicializando Cost Loader');
        console.log('🔍 Verificando elementos na página...');
        
        const headerCosts = document.querySelectorAll('[data-header-cost]');
        console.log(`📋 Encontrados ${headerCosts.length} elementos data-header-cost`);
        
        await this.loadCosts();
        this.updateAllCostElements();
        console.log('✅ Cost Loader inicializado');
    }

    async loadCosts() {
        try {
            // ✅ Usar endpoint específico que busca DIRETAMENTE da tabela consultation_types
            const response = await fetch(`${this.apiBaseUrl}/consultation/types`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                
                // ✅ Buscar custos REAIS da tabela consultation_types
                this.costs = {};
                console.log('📋 Tipos de consulta recebidos da API:', data.types);
                
                data.types?.forEach(type => {
                    const code = type.code.toLowerCase();
                    
                    // ✅ Mapear códigos REAIS da tabela para os IDs usados no frontend
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
                    } else {
                        // Para qualquer outro tipo, considerar como "outros"
                        this.costs.outros = type.cost_cents;
                    }
                });

                // Definir valor padrão para "outros" se não tiver um tipo específico
                if (!this.costs.outros) {
                    this.costs.outros = this.costs.simples || this.costs.suframa || this.costs.geocoding || 5;
                }
                
                console.log('💰 Custos REAIS carregados da tabela consultation_types:', this.costs);
            } else {
                throw new Error(`API retornou status ${response.status}`);
            }
        } catch (error) {
            console.error('❌ Erro ao carregar custos da tabela consultation_types:', error);
            // Fallback apenas em caso de erro real
            this.costs = {
                protestos: 15,        // R$ 0,15
                receita_federal: 5,   // R$ 0,05
                outros: 5            // R$ 0,05
            };
            console.warn('⚠️ Usando custos fallback - verifique conexão com o banco');
        }
    }

    formatCurrency(cents) {
        return (cents / 100).toLocaleString('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        });
    }

    updateAllCostElements() {
        // ❌ Removido: Elementos data-cost dos cards individuais (conforme solicitação do usuário)
        // Custos agora aparecem apenas no header

        // Atualizar elementos data-cost-display (api-keys.html)
        document.querySelectorAll('[data-cost-display]').forEach(element => {
            const costType = element.getAttribute('data-cost-display');
            const cost = this.costs[costType];
            if (cost) {
                element.textContent = this.formatCurrency(cost);
                console.log(`📊 Atualizado data-cost-display="${costType}": ${this.formatCurrency(cost)}`);
            }
        });

        // Atualizar elemento data-cost-summary (api-keys.html)
        const summaryElement = document.querySelector('[data-cost-summary]');
        if (summaryElement) {
            const summary = `• Protestos: ${this.formatCurrency(this.costs.protestos)} • Receita Federal: ${this.formatCurrency(this.costs.receita_federal)} • Outros: ${this.formatCurrency(this.costs.outros)}`;
            summaryElement.textContent = summary;
            console.log('📊 Atualizado data-cost-summary');
        }

        // ✅ Atualizar custos do header (consultas.html)
        console.log('🎯 Atualizando custos do header...');
        console.log('💰 Custos disponíveis:', this.costs);
        
        const headerElements = document.querySelectorAll('[data-header-cost]');
        console.log(`📋 Elementos do header encontrados: ${headerElements.length}`);
        
        headerElements.forEach(element => {
            const costType = element.getAttribute('data-header-cost');
            const cost = this.costs[costType];
            console.log(`🔍 Processando ${costType}: custo=${cost}`);
            
            if (cost) {
                const serviceName = costType === 'protestos' ? 'Protestos' : 
                                 costType === 'receita_federal' ? 'Receita Federal' : 'Demais serviços';
                element.textContent = `● ${serviceName}: ${this.formatCurrency(cost)}`;
                console.log(`✅ Atualizado header data-header-cost="${costType}": ${this.formatCurrency(cost)}`);
            } else {
                console.warn(`⚠️ Custo não encontrado para ${costType}`);
            }
        });

        console.log('✅ Todos os elementos de custo atualizados com dados reais da tabela consultation_types');
    }

    // Método público para recarregar custos
    async reload() {
        await this.loadCosts();
        this.updateAllCostElements();
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 DOM Carregado, verificando elementos...');
    
    // Verificar se existem elementos de custo na página
    const hasCostElements = document.querySelector('[data-cost], [data-cost-display], [data-cost-summary], [data-header-cost]');
    const headerCostElements = document.querySelectorAll('[data-header-cost]');
    
    console.log(`🔍 Elementos encontrados: hasCostElements=${!!hasCostElements}, headerElements=${headerCostElements.length}`);
    
    if (hasCostElements || headerCostElements.length > 0) {
        console.log('✅ Elementos de custo encontrados, inicializando Cost Loader...');
        window.costLoader = new CostLoader();
        console.log('💰 Cost Loader ativo na página');
    } else {
        console.warn('⚠️ Nenhum elemento de custo encontrado na página');
    }
});

// Fallback - inicializar após um delay se ainda não foi inicializado
setTimeout(() => {
    if (!window.costLoader) {
        const headerElements = document.querySelectorAll('[data-header-cost]');
        if (headerElements.length > 0) {
            console.log('🔄 Inicialização tardia do Cost Loader...');
            window.costLoader = new CostLoader();
        }
    }
}, 1000);

// Exportar para uso global
window.CostLoader = CostLoader;

// Função global para debug manual
window.debugCosts = function() {
    console.log('🐛 DEBUG: Verificando estado dos custos...');
    console.log('💰 Cost Loader existe?', !!window.costLoader);
    console.log('📋 Elementos data-header-cost:', document.querySelectorAll('[data-header-cost]').length);
    console.log('🌐 Endpoint funciona?');
    
    fetch('/api/v2/consultation/types')
        .then(response => response.json())
        .then(data => {
            console.log('✅ Dados da API:', data);
            if (window.costLoader) {
                window.costLoader.reload();
            } else {
                console.warn('⚠️ Cost Loader não existe, criando...');
                window.costLoader = new CostLoader();
            }
        })
        .catch(error => console.error('❌ Erro na API:', error));
};

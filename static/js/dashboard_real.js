/**
 * Dashboard Real JavaScript - Sistema SaaS Valida
 * 🎯 DADOS 100% REAIS DO BANCO DE DADOS (SEM MOCK)
 * 
 * Integra com:
 * - /api/v2/dashboard/data (dados completos)
 * - consultation_types_service (custos reais)
 * - credit_service (saldo real)
 * - consultations/consultation_details (dados reais)
 */

class RealDashboard {
    constructor() {
        this.apiBaseUrl = '/api/v2';  // 🎯 CORRIGIDO: Apontar para os endpoints v2
        this.currentUser = null;
        this.dashboardData = null;
        this.charts = {};
        this.currentPeriod = '30d';
        this.refreshInterval = null;
        this.isLoading = false;
        this.init();
    }

    async init() {
        console.log('🚀 Inicializando Dashboard REAL v2.0 - Zero Mock Data');
        
        // Verificar autenticação
        const token = this.getAuthToken();
        if (token) {
            this.setAuthHeader(token);
        } else {
            console.warn('❌ Token não encontrado - redirecionando para login');
            window.location.href = '/login';
            return;
        }

        // Detectar período ativo
        this.detectActivePeriod();
        
        // Carregar dados reais iniciais
        await this.loadRealDashboardData();
        
        // Configurar eventos
        this.setupEventListeners();
        
        // Atualização automática (30s)
        this.startAutoRefresh();
        
        console.log('✅ Dashboard REAL v2.0 inicializado com dados do banco');
    }

    getAuthToken() {
        const authToken = localStorage.getItem('auth_token');
        const sessionToken = localStorage.getItem('session_token');
        const apiKey = localStorage.getItem('api_key');
        
        // Priorizar JWT tokens válidos
        const token = authToken || sessionToken;
        
        if (token && token.includes('.') && token.split('.').length === 3) {
            console.log('✅ Token JWT válido encontrado');
            return token;
        } else if (apiKey && apiKey.startsWith('rcp_')) {
            console.log('🔑 API Key encontrada - usando para autenticação');
            return apiKey;
        }
        
        console.warn('❌ Nenhum token válido encontrado');
        return null;
    }

    setAuthHeader(token) {
        this.authHeader = {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        };
    }

    async fetchWithAuth(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...this.authHeader
            }
        };
        
        try {
            return await fetch(url, { ...defaultOptions, ...options });
        } catch (error) {
            console.error('❌ Erro na requisição autenticada:', error);
            throw error;
        }
    }

    detectActivePeriod() {
        const activeButton = document.querySelector('[data-period].bg-gray-900, [data-period].active');
        if (activeButton) {
            this.currentPeriod = activeButton.dataset.period;
            console.log(`🔍 Período ativo detectado: ${this.currentPeriod}`);
        }
    }

    async loadRealDashboardData(period = null) {
        if (this.isLoading) return;
        
        try {
            this.isLoading = true;
            const selectedPeriod = period || this.currentPeriod;
            
            console.log(`📊 Carregando dados REAIS do dashboard (período: ${selectedPeriod})`);
            this.showLoadingState();
            
            // ✅ CORRIGIDO: Usar a rota v2 correta, sem prefixo duplicado
            const response = await this.fetchWithAuth(`${this.apiBaseUrl}/dashboard/data?period=${selectedPeriod}`);
            
            if (response.ok) {
                const data = await response.json();
                this.dashboardData = data;
                
                console.log('✅ Dados REAIS carregados:', {
                    consultas: data.usage?.total_consultations || 0,
                    custo_total: data.usage?.total_cost || 'R$ 0,00',
                    creditos: data.credits?.available || 'R$ 0,00',
                    tipos_custo: Object.keys(data.costs || {}).length,
                    graficos: Object.keys(data.charts || {}).length
                });
                
                this.updateDashboardWithRealData(data);
                this.hideLoadingState();
                
            } else if (response.status === 401) {
                console.error('❌ Token inválido - redirecionando para login');
                localStorage.clear();
                window.location.href = '/login';
            } else {
                console.error('❌ Erro na API v2:', response.status, response.statusText);
                this.showErrorState('Erro ao carregar dados do servidor');
            }
            
        } catch (error) {
            console.error('❌ Erro ao carregar dados reais:', error);
            this.showErrorState('Erro de conexão com o servidor');
        } finally {
            this.isLoading = false;
        }
    }

    updateDashboardWithRealData(data) {
        console.log('📊 Atualizando interface com dados reais...');
        
        // Atualizar créditos reais
        this.updateCreditsDisplay(data.credits);
        
        // Atualizar estatísticas de uso reais
        this.updateUsageStats(data.usage);
        
        // Atualizar custos dinâmicos
        this.updateCostsDisplay(data.costs);
        
        // Criar/atualizar gráficos com dados reais
        this.updateChartsWithRealData(data.charts);
        
        // Atualizar estatísticas adicionais dos gráficos
        this.updateChartStatistics(data.usage, data.charts);
        
        // Atualizar informações do período
        this.updatePeriodInfo(data.period, data.last_updated);
        
        console.log('✅ Interface atualizada com dados 100% reais do banco');
    }

    updateCreditsDisplay(credits) {
        if (!credits) return;
        
        // Atualizar créditos disponíveis (header + card principal)
        this.updateElement('[data-stat="creditos-header"]', credits.available || 'R$ 0,00');
        this.updateElement('[data-stat="creditos-disponiveis"]', credits.available || 'R$ 0,00');
        this.updateElement('[data-credits-available]', credits.available || 'R$ 0,00');
        
        // Atualizar créditos comprados
        this.updateElement('[data-stat="creditos-comprados"]', credits.purchased || 'R$ 0,00');
        this.updateElement('[data-credits-purchased]', credits.purchased || 'R$ 0,00');
        
        // Atualizar créditos usados
        this.updateElement('[data-stat="creditos-usados"]', credits.used || 'R$ 0,00');
        this.updateElement('[data-credits-used]', credits.used || 'R$ 0,00');
        
        // Status de renovação automática
        const renewalStatus = credits.auto_renewal ? 'Ativa' : 'Inativa';
        this.updateElement('[data-auto-renewal-status]', renewalStatus);
        this.updateElement('[data-renewal-status]', renewalStatus);
        
        // Aplicar classes visuais baseadas no saldo
        const creditsElement = document.querySelector('[data-stat="creditos-disponiveis"]');
        if (creditsElement && credits.available_raw !== undefined) {
            if (credits.available_raw < 1.0) {
                creditsElement.classList.add('text-red-400');
                creditsElement.classList.remove('text-green-400');
            } else {
                creditsElement.classList.add('text-green-400');
                creditsElement.classList.remove('text-red-400');
            }
        }
        
        console.log('💰 Créditos atualizados:', credits.available);
    }

    updateUsageStats(usage) {
        if (!usage) return;
        
        // Estatísticas principais
        this.updateElement('[data-stat="total_consultations"]', usage.total_consultations || 0);
        this.updateElement('[data-stat="total_cost"]', usage.total_cost || 'R$ 0,00');
        this.updateElement('[data-stat="consumo-periodo-total"]', usage.total_cost || 'R$ 0,00');
        
        // ✅ CORRIGIDO: Atualizar TODOS os 6 tipos de consulta
        const tipos = ['protestos', 'receita_federal', 'simples_nacional', 'cadastro_contribuintes', 'geocodificacao', 'suframa'];
        
        for (const tipo of tipos) {
            // Contadores por tipo
            this.updateElement(`[data-stat="${tipo}_count"]`, usage[`${tipo}_count`] || 0);
            
            // Custos por tipo  
            this.updateElement(`[data-stat="${tipo}_cost"]`, usage[`${tipo}_cost`] || 'R$ 0,00');
        }
        
        // Campos legados para compatibilidade (se existirem no template)
        this.updateElement('[data-stat="consultas-realizadas"]', usage.total_consultations || 0);
        this.updateElement('[data-stat="custo-total"]', usage.total_cost || 'R$ 0,00');
        this.updateElement('[data-stat="consumo-periodo"]', usage.total_cost || 'R$ 0,00');
        this.updateElement('[data-stat="consultas-protestos"]', usage.protestos_count || 0);
        this.updateElement('[data-stat="consultas-receita"]', usage.receita_federal_count || 0);
        this.updateElement('[data-stat="consumo-protestos"]', usage.protestos_cost || 'R$ 0,00');
        this.updateElement('[data-stat="consumo-receita"]', usage.receita_federal_cost || 'R$ 0,00');
        this.updateElement('[data-stat="chart-protestos"]', usage.protestos_cost || 'R$ 0,00');
        this.updateElement('[data-stat="chart-receita"]', usage.receita_federal_cost || 'R$ 0,00');
        this.updateElement('[data-stat="tipo-protestos-count"]', usage.protestos_count || 0);
        this.updateElement('[data-stat="tipo-receita-count"]', usage.receita_federal_count || 0);
        
        // Custo médio
        if (usage.total_consultations > 0 && usage.total_cost_raw) {
            const avgCost = usage.total_cost_raw / usage.total_consultations;
            this.updateElement('[data-stat="custo-medio"]', `R$ ${avgCost.toFixed(2)}`);
        } else {
            this.updateElement('[data-stat="custo-medio"]', 'R$ 0,00');
        }
        
        // 🔍 DEBUG: Verificar se elementos estão sendo atualizados
        console.log('🔍 DEBUG: Tentando atualizar total_cost:', usage.total_cost);
        console.log('🔍 DEBUG: Elemento total_cost existe?', !!document.querySelector('[data-stat="total_cost"]'));
        console.log('🔍 DEBUG: Elemento consumo-periodo-total existe?', !!document.querySelector('[data-stat="consumo-periodo-total"]'));
        
        console.log('📈 Estatísticas de uso atualizadas (TODOS OS 6 TIPOS):', {
            total: usage.total_consultations,
            custo: usage.total_cost,
            tipos_atualizados: tipos.length
        });
    }

    updateCostsDisplay(costs) {
        if (!costs) return;
        
        // Atualizar custos dinâmicos no HTML
        const costsContainer = document.querySelector('[data-dynamic-costs]');
        if (costsContainer) {
            const costElements = [];
            
            if (costs.protestos) {
                costElements.push(`Protestos ${costs.protestos.cost_formatted}`);
            }
            
            if (costs.receita_federal) {
                costElements.push(`Receita ${costs.receita_federal.cost_formatted}`);
            }
            
            costsContainer.innerHTML = costElements.join(' • ');
        }
        
        // Atualizar elementos específicos de custo
        Object.keys(costs).forEach(typeCode => {
            const cost = costs[typeCode];
            this.updateElement(`[data-cost="${typeCode}"]`, cost.cost_formatted);
        });
        
        console.log('💸 Custos dinâmicos atualizados:', Object.keys(costs).length, 'tipos');
    }

    updateChartStatistics(usage, charts) {
        // Atualizar estatísticas do gráfico de distribuição
        const volumeChart = charts.volume || {};
        const totalUsos = volumeChart.total_usos || 0;
        const totalConsultas = usage.total_consultations || 0;
        
        // Atualizar total de usos
        this.updateElement('#total-usos-tipos', `${totalUsos} usos totais`);
        
        // Calcular e mostrar média de tipos por consulta
        if (totalConsultas > 0) {
            const mediaTipos = (totalUsos / totalConsultas).toFixed(1);
            this.updateElement('#media-tipos', `${mediaTipos} tipos/consulta`);
        } else {
            this.updateElement('#media-tipos', '-');
        }
        
        console.log('📊 Estatísticas dos gráficos atualizadas:', {
            totalUsos,
            totalConsultas,
            media: totalConsultas > 0 ? (totalUsos / totalConsultas).toFixed(1) : 0
        });
    }

    updateChartsWithRealData(chartsData) {
        if (!chartsData) return;
        
        try {
            // Destruir gráficos existentes
            this.destroyExistingCharts();
            
            // Criar gráfico de consumo
            if (chartsData.consumption) {
                this.createConsumptionChart(chartsData.consumption);
            }
            
            // Criar gráfico de volume
            if (chartsData.volume) {
                this.createVolumeChart(chartsData.volume);
            }
            
            // Criar gráfico de breakdown de custos
            if (chartsData.cost_breakdown) {
                this.createCostBreakdownChart(chartsData.cost_breakdown);
            }
            
            console.log('📊 Gráficos criados com dados reais');
            
        } catch (error) {
            console.error('❌ Erro ao criar gráficos:', error);
        }
    }

    createConsumptionChart(data) {
        const ctx = document.getElementById('apiConsumptionChart');
        if (!ctx || !data.datasets) return;

        this.charts.consumption = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels || [],
                datasets: data.datasets || []
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: '#E5E7EB' }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                if (context.parsed.y === 0) {
                                    return 'Nenhuma consulta registrada';
                                }
                                return `${context.dataset.label}: R$ ${context.parsed.y.toFixed(2)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#9CA3AF' },
                        grid: { color: '#374151' }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { 
                            color: '#9CA3AF',
                            callback: function(value) {
                                return `R$ ${value.toFixed(2)}`;
                            }
                        },
                        grid: { color: '#374151' }
                    }
                }
            }
        });
    }

    createVolumeChart(data) {
        const ctx = document.getElementById('apiVolumeChart');
        if (!ctx || !data.data || data.data.length === 0) return;

        this.charts.volume = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels || [],
                datasets: [{
                    data: data.data || [],
                    backgroundColor: data.backgroundColor || [],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#E5E7EB', padding: 15 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                if (context.parsed === 0) {
                                    return 'Nenhuma consulta registrada';
                                }
                                return `${context.label}: ${context.parsed} consultas`;
                            }
                        }
                    }
                }
            }
        });
    }

    createCostBreakdownChart(data) {
        const ctx = document.getElementById('costBreakdownChart');
        if (!ctx || !data.data || data.data.length === 0) return;

        this.charts.costBreakdown = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels || [],
                datasets: [{
                    data: data.data || [],
                    backgroundColor: data.backgroundColor || [],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#E5E7EB', padding: 15 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                if (context.parsed === 0) {
                                    return `${context.label}: Nenhum custo`;
                                }
                                return `${context.label}: R$ ${context.parsed.toFixed(2)}`;
                            }
                        }
                    }
                }
            }
        });
    }

    destroyExistingCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart) {
                chart.destroy();
            }
        });
        this.charts = {};
    }

    updatePeriodInfo(period, lastUpdated) {
        // Atualizar informações do período
        const periodElement = document.querySelector('[data-current-period]');
        if (periodElement) {
            const periodNames = {
                '7d': '7 dias',
                '30d': '30 dias', 
                '90d': '90 dias'
            };
            periodElement.textContent = periodNames[period] || period;
        }
        
        // Atualizar timestamp da última atualização
        const lastUpdatedElement = document.querySelector('[data-last-updated]');
        if (lastUpdatedElement && lastUpdated) {
            const date = new Date(lastUpdated);
            lastUpdatedElement.textContent = `Atualizado: ${date.toLocaleTimeString('pt-BR')}`;
        }
    }

    updateElement(selector, value) {
        // Tentar querySelector primeiro, depois getElementById se for um ID
        let element = document.querySelector(selector);
        
        // Se não achou e começa com #, tentar getElementById
        if (!element && selector.startsWith('#')) {
            element = document.getElementById(selector.substring(1));
        }
        
        if (element) {
            const oldValue = element.textContent;
            if (typeof value === 'number') {
                element.textContent = new Intl.NumberFormat('pt-BR').format(value);
            } else {
                element.textContent = value;
            }
            
            // 🔍 DEBUG: Log apenas para total_cost
            if (selector.includes('total_cost') || selector.includes('consumo-periodo')) {
                console.log(`🔍 UPDATED: ${selector} | ${oldValue} → ${element.textContent}`);
            }
        } else {
            console.warn(`⚠️ Elemento não encontrado: ${selector}`);
        }
    }

    setupEventListeners() {
        // Botões de período
        document.querySelectorAll('[data-period]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const period = e.target.dataset.period;
                console.log(`📅 Mudando período para: ${period}`);
                this.changePeriod(period);
            });
        });

        // Botão de exportar
        const exportBtn = document.querySelector('[data-export-btn]');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportRealData());
        }

        // Botão de refresh manual
        const refreshBtn = document.querySelector('[data-refresh-btn]');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                console.log('🔄 Refresh manual solicitado');
                this.loadRealDashboardData();
            });
        }

        // Busca global (Ctrl+K)
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'k') {
                e.preventDefault();
                this.openGlobalSearch();
            }
        });
    }

    async changePeriod(period) {
        // Atualizar período atual
        this.currentPeriod = period;
        
        // Atualizar botões ativos
        document.querySelectorAll('[data-period]').forEach(btn => {
            btn.classList.remove('bg-gray-900', 'text-white');
            btn.classList.add('text-gray-400');
        });
        
        const activeBtn = document.querySelector(`[data-period="${period}"]`);
        if (activeBtn) {
            activeBtn.classList.add('bg-gray-900', 'text-white');
            activeBtn.classList.remove('text-gray-400');
        }
        
        // Carregar dados do novo período
        await this.loadRealDashboardData(period);
    }

    async exportRealData() {
        try {
            console.log('📤 Exportando dados reais do dashboard...');
            
            if (!this.dashboardData) {
                this.showNotification('Nenhum dado para exportar', 'warning');
                return;
            }
            
            const exportData = {
                timestamp: new Date().toISOString(),
                period: this.currentPeriod,
                credits: this.dashboardData.credits,
                usage: this.dashboardData.usage,
                costs: this.dashboardData.costs,
                success_rate: this.dashboardData.success_rate,
                source: 'Dashboard Real v2.0 - Dados do Banco de Dados'
            };
            
            const blob = new Blob([JSON.stringify(exportData, null, 2)], { 
                type: 'application/json' 
            });
            
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `valida-dashboard-real-${this.currentPeriod}-${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            this.showNotification('Dados exportados com sucesso!', 'success');
            
        } catch (error) {
            console.error('❌ Erro ao exportar dados:', error);
            this.showNotification('Erro ao exportar dados', 'error');
        }
    }

    showLoadingState() {
        // Mostrar indicadores de carregamento
        const loadingElements = document.querySelectorAll('[data-loading]');
        loadingElements.forEach(el => el.classList.remove('hidden'));
        
        // Adicionar classe de loading nos cartões principais
        const cards = document.querySelectorAll('.card');
        cards.forEach(card => card.classList.add('opacity-50'));
    }

    hideLoadingState() {
        // Esconder indicadores de carregamento
        const loadingElements = document.querySelectorAll('[data-loading]');
        loadingElements.forEach(el => el.classList.add('hidden'));
        
        // Remover classe de loading dos cartões
        const cards = document.querySelectorAll('.card');
        cards.forEach(card => card.classList.remove('opacity-50'));
    }

    showErrorState(message) {
        console.error('💥 Estado de erro:', message);
        
        // Mostrar mensagem de erro
        this.showNotification(message, 'error');
        
        // Atualizar elementos com estado de erro
        this.updateElement('[data-stat="creditos-disponiveis"]', 'Erro');
        this.updateElement('[data-stat="consultas-realizadas"]', 'Erro'); 
        this.updateElement('[data-stat="custo-total"]', 'Erro');
        this.updateElement('[data-stat="consumo-periodo"]', 'Erro');
        
        this.hideLoadingState();
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 transition-all duration-300 ${
            type === 'success' ? 'bg-green-600' : 
            type === 'error' ? 'bg-red-600' : 
            type === 'warning' ? 'bg-yellow-600' : 'bg-blue-600'
        } text-white`;
        
        const icon = type === 'success' ? '✅' : 
                    type === 'error' ? '❌' : 
                    type === 'warning' ? '⚠️' : 'ℹ️';
        
        notification.innerHTML = `
            <div class="flex items-center space-x-2">
                <span class="text-lg">${icon}</span>
                <span>${message}</span>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Animação de entrada
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
            notification.style.opacity = '1';
        }, 10);
        
        // Remover após 4 segundos
        setTimeout(() => {
            notification.style.transform = 'translateX(100%)';
            notification.style.opacity = '0';
            setTimeout(() => notification.remove(), 300);
        }, 4000);
    }

    openGlobalSearch() {
        const searchInput = document.querySelector('input[placeholder="Pesquisar"]');
        if (searchInput) {
            searchInput.focus();
            searchInput.select();
        }
    }

    startAutoRefresh() {
        // Atualizar dados a cada 30 segundos
        this.refreshInterval = setInterval(() => {
            console.log('🔄 Auto-refresh dos dados reais...');
            this.loadRealDashboardData();
        }, 30000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    // Cleanup ao destruir
    destroy() {
        this.stopAutoRefresh();
        this.destroyExistingCharts();
        console.log('🧹 Dashboard Real v2.0 destruído');
    }
}

// Inicializar dashboard quando a página carregar
document.addEventListener('DOMContentLoaded', () => {
    console.log('📌 DOM carregado - verificando dependências...');
    console.log('📌 Chart.js disponível?', typeof Chart !== 'undefined');
    console.log('📌 Window.location:', window.location.href);
    
    // Verificar se Chart.js está carregado
    if (typeof Chart !== 'undefined') {
        console.log('🎯 Inicializando Dashboard Real v2.0 - Dados 100% Reais');
        try {
            window.realDashboard = new RealDashboard();
            console.log('✅ Dashboard inicializado com sucesso');
        } catch (error) {
            console.error('❌ Erro ao inicializar dashboard:', error);
        }
    } else {
        console.error('❌ Chart.js não encontrado. Dashboard não pode ser iniciado.');
        // Tentar novamente após 1 segundo
        setTimeout(() => {
            if (typeof Chart !== 'undefined') {
                console.log('🔄 Chart.js carregado com atraso, iniciando dashboard...');
                window.realDashboard = new RealDashboard();
            }
        }, 1000);
    }
});

// Cleanup ao sair da página
window.addEventListener('beforeunload', () => {
    if (window.realDashboard) {
        window.realDashboard.destroy();
    }
});

/**
 * Dashboard JavaScript v2.0 - Sistema de Créditos
 * Integração com APIs v2.0 e custos transparentes
 */

class DashboardV2 {
    constructor() {
        this.apiBaseUrl = '/api/v2';
        this.apiV1BaseUrl = '/api/v1';
        this.currentUser = null;
        this.dashboardData = null;
        this.charts = {};
        this.currentPeriod = '30d';
        this.refreshInterval = null;
        this.init();
    }

    async init() {
        console.log('🚀 Inicializando Dashboard v2.0 - Sistema de Créditos');
        
        // Verificar autenticação
        const token = this.getAuthToken();
        if (token) {
            this.setAuthHeader(token);
        }

        // Carregar dados iniciais
        await this.loadDashboardData();
        
        // Configurar eventos
        this.setupEventListeners();
        
        // Atualizar dados automaticamente
        this.startAutoRefresh();
        
        console.log('✅ Dashboard v2.0 inicializado com sucesso');
    }

    getAuthToken() {
        return localStorage.getItem('auth_token') || 
               localStorage.getItem('api_key') || 
               localStorage.getItem('dev_token') ||
               null;
    }

    setAuthHeader(token) {
        this.authHeader = {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        };
    }

    async loadDashboardData() {
        try {
            console.log('📊 Carregando dados do dashboard v2.0...');
            
            // Se não tiver token, tentar obter API key
            let apiKey = this.getAuthToken();
            if (!apiKey || !apiKey.startsWith('rcp_')) {
                apiKey = await this.getApiKey();
                if (apiKey) {
                    this.setAuthHeader(apiKey);
                }
            }

            // Carregar dados do dashboard v2.0
            const response = await this.fetchWithAuth(`${this.apiBaseUrl}/dashboard/data`);
            
            if (response.ok) {
                this.dashboardData = await response.json();
                this.updateDashboard();
                console.log('✅ Dados v2.0 carregados:', this.dashboardData);
            } else {
                console.error('❌ API v2.0 indisponível');
                this.showErrorState('API indisponível');
            }
        } catch (error) {
            console.error('❌ Erro ao carregar dados v2.0:', error);
            this.showErrorState('Erro ao carregar dados');
        }
    }

    async getApiKey() {
        try {
            // Tentar API key real primeiro
            let response = await fetch(`${this.apiV1BaseUrl}/auth/real-api-key`);
            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('api_key', data.api_key);
                console.log('🔑 API key real obtida');
                return data.api_key;
            }

            // Fallback para dev API key
            response = await fetch(`${this.apiV1BaseUrl}/auth/dev-api-key`, { method: 'POST' });
            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('api_key', data.api_key);
                console.log('🔑 API key de desenvolvimento obtida');
                return data.api_key;
            }
        } catch (error) {
            console.error('❌ Erro ao obter API key:', error);
        }
        return null;
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

    updateDashboard() {
        if (!this.dashboardData) return;

        this.updateCreditsInfo();
        this.updateUsageStats();
        this.updateRenewalInfo();
        this.createCharts();
        this.updateRecentActivity();
    }

    updateCreditsInfo() {
        const { credits } = this.dashboardData;
        if (!credits) return;

        // Atualizar créditos disponíveis
        this.updateElement('[data-stat="creditos-disponiveis"]', credits.available);
        
        // Atualizar créditos comprados
        this.updateElement('[data-credits-purchased]', credits.purchased);
        
        // Atualizar créditos usados
        this.updateElement('[data-credits-used]', credits.used);
        
        // Atualizar status da renovação automática
        this.updateElement('[data-auto-renewal]', credits.auto_renewal ? 'Ativa' : 'Inativa');
        
        // Atualizar classes visuais dos créditos
        const creditsElement = document.querySelector('[data-stat="creditos-disponiveis"]');
        if (creditsElement) {
            const available = parseFloat(credits.available.replace('R$ ', '').replace(',', '.'));
            if (available < 1.0) {
                creditsElement.classList.add('text-red-400');
                creditsElement.classList.remove('text-green-400');
            } else {
                creditsElement.classList.add('text-green-400');
                creditsElement.classList.remove('text-red-400');
            }
        }
    }

    updateUsageStats() {
        const { usage } = this.dashboardData;
        if (!usage) return;

        // Atualizar estatísticas de uso
        this.updateElement('[data-stat="protestos-count"]', usage.protestos_count || 0);
        this.updateElement('[data-stat="receita-count"]', usage.receita_count || 0);
        this.updateElement('[data-stat="total-consultations"]', usage.total_consultations || 0);
        this.updateElement('[data-stat="total-cost"]', usage.total_cost || 'R$ 0,00');
        
        // Atualizar custos detalhados
        this.updateElement('[data-protestos-cost]', usage.protestos_cost || 'R$ 0,00');
        this.updateElement('[data-receita-cost]', usage.receita_cost || 'R$ 0,00');
        
        // Calcular taxa de sucesso
        const totalConsultations = usage.total_consultations || 0;
        const successfulConsultations = usage.protestos_count + usage.receita_count;
        const successRate = totalConsultations > 0 ? (successfulConsultations / totalConsultations * 100).toFixed(1) : 0;
        this.updateElement('[data-success-rate]', `${successRate}%`);
    }

    updateRenewalInfo() {
        const { renewal } = this.dashboardData;
        if (!renewal) return;

        // Atualizar status da renovação
        this.updateElement('[data-renewal-status]', renewal.status);
        this.updateElement('[data-renewal-count]', renewal.count || 0);
        
        // Atualizar última renovação
        if (renewal.last_renewal) {
            const date = new Date(renewal.last_renewal);
            this.updateElement('[data-last-renewal]', date.toLocaleDateString('pt-BR'));
        }
    }

    showErrorState(message) {
        console.warn('⚠️ Exibindo estado de erro:', message);
        
        // Atualizar elementos com estado de erro
        this.updateElement('[data-stat="creditos-disponiveis"]', 'Erro');
        this.updateElement('[data-stat="creditos-comprados"]', 'Erro');
        this.updateElement('[data-stat="creditos-usados"]', 'Erro');
        this.updateElement('[data-stat="total-consultas"]', 'Erro');
        
        // Mostrar mensagem de erro se houver container específico
        const errorContainer = document.querySelector('#dashboard-error');
        if (errorContainer) {
            errorContainer.textContent = `Erro ao carregar dados: ${message}`;
            errorContainer.style.display = 'block';
        }
    }

    updateElement(selector, value) {
        const element = document.querySelector(selector);
        if (element) {
            element.textContent = value;
        }
    }

    createCharts() {
        this.createCostBreakdownChart();
        this.createUsageTrendChart();
    }

    createCostBreakdownChart() {
        const ctx = document.getElementById('costBreakdownChart');
        if (!ctx) return;

        // Destruir gráfico existente
        if (this.charts.costChart) {
            this.charts.costChart.destroy();
        }

        const { usage } = this.dashboardData;
        const protestosCost = parseFloat((usage?.protestos_cost || 'R$ 0,00').replace('R$ ', '').replace(',', '.'));
        const receitaCost = parseFloat((usage?.receita_cost || 'R$ 0,00').replace('R$ ', '').replace(',', '.'));

        this.charts.costChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: [
                    `Protestos (${usage?.protestos_cost || 'R$ 0,00'})`,
                    `Receita Federal (${usage?.receita_cost || 'R$ 0,00'})`,
                    'Outros'
                ],
                datasets: [{
                    data: [protestosCost, receitaCost, 0],
                    backgroundColor: ['#EF4444', '#3B82F6', '#10B981'],
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
                                const value = context.parsed;
                                if (value === 0) return `${context.label}: Nenhum uso`;
                                return `${context.label}: R$ ${value.toFixed(2)}`;
                            }
                        }
                    }
                }
            }
        });
    }

    createUsageTrendChart() {
        const ctx = document.getElementById('usageTrendChart');
        if (!ctx) return;

        // Destruir gráfico existente
        if (this.charts.trendChart) {
            this.charts.trendChart.destroy();
        }

        // Gerar dados dos últimos 7 dias
        const labels = [];
        const data = [];
        for (let i = 6; i >= 0; i--) {
            const date = new Date();
            date.setDate(date.getDate() - i);
            labels.push(date.toLocaleDateString('pt-BR', { weekday: 'short' }));
            
            // Simular dados variados
            const baseValue = Math.floor(Math.random() * 5);
            data.push(baseValue);
        }

        this.charts.trendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Consultas por Dia',
                    data: data,
                    borderColor: '#10B981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        ticks: { color: '#9CA3AF' },
                        grid: { color: '#374151' }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#9CA3AF' },
                        grid: { color: '#374151' }
                    }
                }
            }
        });
    }

    updateRecentActivity() {
        // Usar atividade real dos dados do dashboard ou mostrar vazio
        const activities = this.dashboardData?.recent_activities || [];

        const container = document.querySelector('[data-recent-activities]');
        if (!container) return;

        container.innerHTML = activities.map(activity => {
            const icon = activity.type === 'renovacao' ? '🔄' : '📊';
            const description = activity.cnpj ? `Consulta CNPJ ${activity.cnpj}` : activity.description;
            
            return `
                <div class="flex items-center justify-between p-3 bg-gray-800 rounded-lg mb-2">
                    <div class="flex items-center space-x-3">
                        <span class="text-lg">${icon}</span>
                        <div>
                            <div class="text-sm text-white">${description}</div>
                            <div class="text-xs text-gray-400">${activity.time}</div>
                        </div>
                    </div>
                    <span class="text-sm text-green-400">${activity.cost}</span>
                </div>
            `;
        }).join('');
    }

    setupEventListeners() {
        // Botão de atualizar dados
        const refreshBtn = document.querySelector('[data-refresh-btn]');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadDashboardData();
                this.showNotification('Dados atualizados!', 'success');
            });
        }

        // Botão de exportar dados
        const exportBtn = document.querySelector('[data-export-btn]');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportData());
        }

        // Filtros de período
        document.querySelectorAll('[data-period]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const period = e.target.dataset.period;
                this.filterByPeriod(period);
            });
        });

        // Busca global (Ctrl+K)
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'k') {
                e.preventDefault();
                this.openGlobalSearch();
            }
        });
    }

    async exportData() {
        try {
            console.log('📤 Exportando dados do dashboard v2.0...');
            
            const exportData = {
                timestamp: new Date().toISOString(),
                credits: this.dashboardData?.credits,
                usage: this.dashboardData?.usage,
                period: this.currentPeriod
            };
            
            const blob = new Blob([JSON.stringify(exportData, null, 2)], { 
                type: 'application/json' 
            });
            const url = URL.createObjectURL(blob);
            
            const a = document.createElement('a');
            a.href = url;
            a.download = `valida-dashboard-v2-${new Date().toISOString().split('T')[0]}.json`;
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

    filterByPeriod(period) {
        console.log(`📅 Filtrando por período: ${period}`);
        this.currentPeriod = period;
        
        // Atualizar botões ativos
        document.querySelectorAll('[data-period]').forEach(btn => {
            btn.classList.remove('bg-blue-600', 'text-white');
            btn.classList.add('text-gray-400', 'hover:bg-gray-700');
        });
        
        const activeBtn = document.querySelector(`[data-period="${period}"]`);
        if (activeBtn) {
            activeBtn.classList.add('bg-blue-600', 'text-white');
            activeBtn.classList.remove('text-gray-400', 'hover:bg-gray-700');
        }
        
        // Recarregar dados
        this.loadDashboardData();
    }

    openGlobalSearch() {
        const searchModal = document.querySelector('[data-search-modal]');
        if (searchModal) {
            searchModal.classList.remove('hidden');
            const searchInput = searchModal.querySelector('input');
            if (searchInput) {
                searchInput.focus();
            }
        }
    }

    startAutoRefresh() {
        // Atualizar a cada 30 segundos
        this.refreshInterval = setInterval(() => {
            this.loadDashboardData();
        }, 30000);
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 transition-all duration-300 ${
            type === 'success' ? 'bg-green-600' : 
            type === 'error' ? 'bg-red-600' : 'bg-blue-600'
        } text-white`;
        
        notification.innerHTML = `
            <div class="flex items-center space-x-2">
                <span class="text-lg">${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span>
                <span>${message}</span>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Animação de entrada
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
            notification.style.opacity = '1';
        }, 10);
        
        // Remover após 3 segundos
        setTimeout(() => {
            notification.style.transform = 'translateX(100%)';
            notification.style.opacity = '0';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    // Cleanup ao destruir
    destroy() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.destroy();
        });
    }
}

// Inicializar dashboard v2.0 quando a página carregar
document.addEventListener('DOMContentLoaded', () => {
    // Verificar se Chart.js está carregado
    if (typeof Chart !== 'undefined') {
        window.dashboardV2 = new DashboardV2();
        console.log('🚀 Dashboard v2.0 com Sistema de Créditos iniciado!');
    } else {
        console.error('❌ Chart.js não encontrado. Verifique se está incluído na página.');
    }
});

// Cleanup ao sair da página
window.addEventListener('beforeunload', () => {
    if (window.dashboardV2) {
        window.dashboardV2.destroy();
    }
});

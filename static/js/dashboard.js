/**
 * Dashboard JavaScript - SaaS Valida
 * Funcionalidades dinâmicas para o dashboard
 */

class Dashboard {
    constructor() {
        this.apiBaseUrl = '/api/v1';
        this.currentUser = null;
        this.stats = null;
        this.charts = {};
        this.currentPeriod = '30d'; // Armazenar período atual
        this.init();
    }

    async init() {
        console.log('🚀 Inicializando Dashboard...');
        
        // Verificar se há token de autenticação
        const token = this.getAuthToken();
        if (token) {
            this.setAuthHeader(token);
        }

        // Detectar período ativo na inicialização
        this.detectActivePeriod();
        
        // Carregar dados do dashboard
        await this.loadDashboardData(this.currentPeriod);
        
        // Configurar eventos
        this.setupEventListeners();
        
        // Atualizar dados a cada 30 segundos usando o período atual
        setInterval(() => this.loadDashboardData(this.currentPeriod), 30000);
    }

    detectActivePeriod() {
        // Detectar qual período está ativo baseado no botão com classe active
        const activeButton = document.querySelector('[data-period].bg-gray-900, [data-period].active');
        if (activeButton) {
            this.currentPeriod = activeButton.dataset.period;
            console.log(`🔍 Período ativo detectado: ${this.currentPeriod}`);
        } else {
            console.log(`🔍 Nenhum período ativo detectado, usando padrão: ${this.currentPeriod}`);
        }
    }

    getAuthToken() {
        // Verificar localStorage para token - APENAS JWT tokens válidos
        const authToken = localStorage.getItem('auth_token');
        const sessionToken = localStorage.getItem('session_token');
        
        console.log('🔍 Tokens disponíveis:');
        console.log('  auth_token:', authToken ? authToken.substring(0, 20) + '...' : 'null');
        console.log('  session_token:', sessionToken ? sessionToken.substring(0, 20) + '...' : 'null');
        
        // Priorizar auth_token (JWT novo) sobre session_token (legacy)
        const token = authToken || sessionToken;
        
        // Verificar se o token parece ser um JWT (formato xxx.yyy.zzz)
        if (token && token.includes('.') && token.split('.').length === 3) {
            console.log('✅ Token JWT válido encontrado');
            return token;
        } else if (token) {
            console.warn('❌ Token encontrado mas não é um JWT válido:', token.substring(0, 20) + '...');
            // Limpar token inválido
            localStorage.removeItem('auth_token');
            localStorage.removeItem('session_token');
            localStorage.removeItem('api_key'); // Limpar possível API key antiga
            return null;
        }
        
        console.warn('❌ Nenhum token JWT válido encontrado');
        return null;
    }

    setAuthHeader(token) {
        // Configurar header de autorização para todas as requisições
        this.authHeader = {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        };
    }

    async fetchWithAuth(url, options = {}) {
        // Método para fazer requisições autenticadas
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...this.authHeader
            }
        };
        
        // Mesclar opções fornecidas com as padrão
        const finalOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...(options.headers || {})
            }
        };

        try {
            const response = await fetch(url, finalOptions);
            return response;
        } catch (error) {
            console.error('❌ Erro na requisição autenticada:', error);
            throw error;
        }
    }

    async loadDashboardData(period = '30d') {
        try {
            console.log(`📊 Carregando dados do dashboard para período: ${period}`);
            
            // Verificar se temos um token JWT válido
            const token = this.getAuthToken();
            if (!token) {
                console.error('❌ Nenhum token JWT válido encontrado - redirecionando para login');
                window.location.href = '/login';
                return;
            }
            
            // Configurar header de autorização
            this.setAuthHeader(token);
            
            console.log(`🔑 Usando token JWT para autenticação: ${token.substring(0, 30)}...`);
            
            // Carregar estatísticas do dashboard
            const response = await this.fetchWithAuth(`${this.apiBaseUrl}/dashboard/stats?period=${period}`);
            
            if (response.ok) {
                const data = await response.json();
                this.stats = data;
                this.updateDashboard(data);
                console.log('✅ Dados do dashboard carregados da API');
            } else {
                console.warn('⚠️ API retornou erro');
                this.showEmptyState();
            }
        } catch (error) {
            console.error('❌ Erro ao carregar dados:', error);
            this.showEmptyState();
        }
    }
    
    async getDevApiKey() {
        try {
            const response = await fetch('/api/v1/auth/dev-api-key', {
                method: 'POST'
            });
            
            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('api_key', data.api_key);
                console.log('🔑 API key de desenvolvimento obtida');
                return data.api_key;
            }
        } catch (error) {
            console.error('❌ Erro ao obter API key de desenvolvimento:', error);
        }
        return null;
    }
    
    async getRealApiKey() {
        try {
            const response = await fetch('/api/v1/auth/real-api-key', {
                method: 'GET'
            });
            
            if (response.ok) {
                const data = await response.json();
                localStorage.setItem('api_key', data.api_key);
                console.log('🔑 API key real obtida do banco de dados');
                return data.api_key;
            }
        } catch (error) {
            console.error('❌ Erro ao obter API key real:', error);
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

    showEmptyState() {
        // Mostrar estado vazio quando não há dados
        this.stats = {
            credits_available: 0,
            credits_renewal_date: null,
            period_consumption: 0,
            period_consumption_message: "Nenhum consumo registrado",
            total_queries: 0,
            total_queries_message: "Nenhuma consulta realizada",
            total_cost: 0.0,
            avg_cost_per_query: 0.0,
            avg_cost_message: "Custo médio por consulta: R$ 0,00",
            consumption_chart: {
                labels: [],
                data: [],
                datasets: [{
                    label: 'Consultas por Mês',
                    data: [],
                    borderColor: 'rgb(59, 130, 246)',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.1
                }]
            },
            volume_by_api: {
                labels: [],
                data: [],
                colors: []
            },
            period: '30d',
            success_rate: 0
        };
        
        this.updateDashboard(this.stats);
        console.log('📊 Estado vazio exibido - nenhum dado disponível');
    }

    updateDashboard(data) {
        this.updateStatsCards(data);
        this.updateCharts(data);
        this.createCharts(data);
    }

    updateStatsCards(data) {
        // Atualizar cartões de estatísticas
        const cards = {
            'creditos-disponiveis': data.credits_available || 0,
            'consumo-periodo': data.period_consumption || 0,
            'consultas-realizadas': data.total_queries || 0,
            'custo-total': data.total_cost || 0
        };

        Object.entries(cards).forEach(([id, value]) => {
            const element = document.querySelector(`[data-stat="${id}"]`);
            if (element) {
                if (id === 'custo-total') {
                    element.textContent = this.formatCurrency(value);
                } else {
                    element.textContent = this.formatNumber(value);
                }
            }
        });

        // Atualizar mensagens dos cartões
        this.updateCardMessages(data);

        // Atualizar data de renovação
        const renewalDate = document.querySelector('[data-renewal-date]');
        if (renewalDate && data.credits_renewal_date) {
            const date = new Date(data.credits_renewal_date);
            renewalDate.textContent = `Renovam em ${date.toLocaleDateString('pt-BR')}`;
        }
    }

    updateCardMessages(data) {
        // Atualizar mensagens dos cartões
        const messages = {
            'consumo-periodo-msg': data.period_consumption_message || 'Nenhum consumo registrado',
            'consultas-realizadas-msg': data.total_queries_message || 'Nenhuma consulta realizada',
            'custo-total-msg': data.avg_cost_message || 'Custo médio por consulta: R$ 0,00'
        };

        Object.entries(messages).forEach(([id, message]) => {
            const element = document.querySelector(`[data-msg="${id}"]`);
            if (element) {
                element.textContent = message;
            }
        });
    }

    updateUserInfo(user) {
        // Atualizar informações do usuário no header
        const userInfo = document.querySelector('[data-user-info]');
        if (userInfo) {
            userInfo.textContent = user.full_name || user.email;
        }
    }

    updateRecentRequests(requests) {
        // Atualizar lista de consultas recentes
        const container = document.querySelector('[data-recent-requests]');
        if (!container) return;

        container.innerHTML = requests.map(req => `
            <div class="flex items-center justify-between p-3 bg-gray-800 rounded-lg mb-2">
                <div class="flex items-center space-x-3">
                    <div class="w-2 h-2 bg-green-500 rounded-full"></div>
                    <span class="text-sm text-gray-300">${req.cnpj}</span>
                </div>
                <span class="text-xs text-gray-500">
                    ${new Date(req.timestamp).toLocaleTimeString('pt-BR')}
                </span>
            </div>
        `).join('');
    }

    updateCharts(data) {
        // Atualizar gráficos com novos dados
        if (this.charts.consumptionChart && data.consumption_chart) {
            this.charts.consumptionChart.data.labels = data.consumption_chart.labels;
            this.charts.consumptionChart.data.datasets[0].data = data.consumption_chart.data;
            this.charts.consumptionChart.update();
        }
        
        if (this.charts.volumeChart && data.volume_by_api) {
            this.charts.volumeChart.data.labels = data.volume_by_api.labels;
            this.charts.volumeChart.data.datasets[0].data = data.volume_by_api.data;
            this.charts.volumeChart.data.datasets[0].backgroundColor = data.volume_by_api.colors;
            this.charts.volumeChart.update();
        }
    }

    updateUsageChart(usage) {
        // Simular dados de uso por período
        const chartData = this.generateChartData(usage.requests_this_month);
        console.log('📈 Dados do gráfico de uso:', chartData);
    }

    updateVolumeChart() {
        // Simular dados de volume por API
        const volumeData = {
            'Protest Data': 45,
            'Federal Revenue': 30,
            'Simplified National': 20,
            'Geocoding': 5
        };
        console.log('📊 Dados do gráfico de volume:', volumeData);
    }

    generateChartData(totalRequests) {
        // Gerar dados simulados para os últimos 30 dias
        const days = 30;
        const data = [];
        
        for (let i = days - 1; i >= 0; i--) {
            const date = new Date();
            date.setDate(date.getDate() - i);
            
            // Simular variação nos dados
            const baseValue = totalRequests / days;
            const variation = (Math.random() - 0.5) * 0.4; // ±20% de variação
            const value = Math.max(0, Math.round(baseValue * (1 + variation)));
            
            data.push({
                date: date.toISOString().split('T')[0],
                requests: value
            });
        }
        
        return data;
    }

    calculateCost(requests) {
        // Calcular custo baseado no número de consultas
        const costPerRequest = 0.021; // R$ 0,021 por consulta
        return (requests * costPerRequest).toFixed(2);
    }

    formatNumber(num) {
        return new Intl.NumberFormat('pt-BR').format(num);
    }

    formatCurrency(value) {
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        }).format(value);
    }

    setupEventListeners() {
        // Botão de exportar
        const exportBtn = document.querySelector('[data-export-btn]');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportData());
        }

        // Filtros de período
        const periodButtons = document.querySelectorAll('[data-period]');
        console.log(`🔘 Encontrados ${periodButtons.length} botões de período`);
        periodButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const period = e.target.dataset.period;
                console.log(`🖱️ Clique no botão de período: ${period}`);
                this.filterByPeriod(period);
            });
        });

        // Busca global (Ctrl+K)
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'k') {
                e.preventDefault();
                this.openSearch();
            }
        });

        // Campo de busca
        const searchInput = document.querySelector('[data-search-input]');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.handleSearch(e.target.value);
            });
        }
    }

    async exportData() {
        try {
            console.log('📤 Exportando dados...');
            
            // Simular exportação
            const data = {
                timestamp: new Date().toISOString(),
                user: this.stats?.user?.email,
                stats: this.stats?.usage,
                period: '30d'
            };
            
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            
            const a = document.createElement('a');
            a.href = url;
            a.download = `valida-dashboard-${new Date().toISOString().split('T')[0]}.json`;
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
        
        // Salvar período atual
        this.currentPeriod = period;
        
        // Atualizar botões ativos
        document.querySelectorAll('[data-period]').forEach(btn => {
            btn.classList.remove('bg-gray-900', 'text-white');
            btn.classList.add('text-gray-400', 'hover:bg-gray-700');
        });
        
        const activeBtn = document.querySelector(`[data-period="${period}"]`);
        if (activeBtn) {
            activeBtn.classList.add('bg-gray-900', 'text-white');
            activeBtn.classList.remove('text-gray-400', 'hover:bg-gray-700');
        }
        
        // Recarregar dados com filtro
        console.log(`🔄 Recarregando dados para período: ${period}`);
        this.loadDashboardData(period);
    }

    openSearch() {
        const searchInput = document.querySelector('[data-search-input]');
        if (searchInput) {
            searchInput.focus();
            searchInput.select();
        }
    }

    handleSearch(query) {
        console.log(`🔍 Buscando: ${query}`);
        // Implementar busca em tempo real
    }

    showNotification(message, type = 'info') {
        // Criar notificação
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 p-4 rounded-lg shadow-lg z-50 ${
            type === 'success' ? 'bg-green-600' : 
            type === 'error' ? 'bg-red-600' : 'bg-blue-600'
        } text-white`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Remover após 3 segundos
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    createCharts(data) {
        this.createApiConsumptionChart(data);
        this.createApiVolumeChart(data);
    }

    createApiConsumptionChart(data) {
        const ctx = document.getElementById('apiConsumptionChart');
        if (!ctx) return;

        // Destruir gráfico existente se houver
        if (this.charts.consumptionChart) {
            this.charts.consumptionChart.destroy();
        }

        // Usar dados reais ou fallback padrão
        const chartData = data.consumption_chart || {
            labels: ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'],
            data: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        };

        this.charts.consumptionChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: 'Consultas por Mês',
                    data: chartData.data,
                    borderColor: '#3B82F6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: '#E5E7EB'
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                if (context.parsed.y === 0) {
                                    return 'Nenhuma consulta registrada';
                                }
                                return `${context.dataset.label}: ${context.parsed.y}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: '#9CA3AF'
                        },
                        grid: {
                            color: '#374151'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: '#9CA3AF'
                        },
                        grid: {
                            color: '#374151'
                        }
                    }
                }
            }
        });
    }

    createApiVolumeChart(data) {
        const ctx = document.getElementById('apiVolumeChart');
        if (!ctx) return;

        // Destruir gráfico existente se houver
        if (this.charts.volumeChart) {
            this.charts.volumeChart.destroy();
        }

        // Usar dados reais ou fallback padrão
        const chartData = data.volume_by_api || {
            labels: ['CNPJ Consult', 'Protestos', 'Histórico', 'Outros'],
            data: [0, 0, 0, 0],
            colors: ['#3B82F6', '#10B981', '#F59E0B', '#EF4444']
        };

        this.charts.volumeChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: chartData.labels,
                datasets: [{
                    data: chartData.data,
                    backgroundColor: chartData.colors,
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#E5E7EB',
                            padding: 20
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                if (context.parsed === 0) {
                                    return 'Nenhuma consulta registrada';
                                }
                                return `${context.label}: ${context.parsed}`;
                            }
                        }
                    }
                }
            }
        });
    }
}

// Inicializar dashboard quando a página carregar
document.addEventListener('DOMContentLoaded', () => {
    new Dashboard();
});

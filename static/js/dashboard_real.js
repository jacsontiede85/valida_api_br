/**
 * Dashboard Real JavaScript - Sistema SaaS Valida
 * 🎯 DADOS 100% REAIS DO BANCO DE DADOS (SEM MOCK)
 * 🚀 OTIMIZADO: Cache inteligente + Smart refresh + Rate limiting + UX Suave
 * 
 * Integra com:
 * - /api/v2/dashboard/data (dados completos)
 * - consultation_types_service (custos reais)
 * - credit_service (saldo real)
 * - consultations/consultation_details (dados reais)
 * 
 * Otimizações v2.2 UX:
 * ✅ Cache frontend com TTL de 30s
 * ✅ Smart refresh de 60s (vs 30s anterior)
 * ✅ Detecção de visibilidade da página
 * ✅ Rate limiting (max 10 requests/min)
 * ✅ Fallback inteligente para cache antigo
 * ✅ Debouncing de atualizações UI
 * ✅ Smart chart updates (só recria quando necessário)
 * ✅ Animações suaves e loading states melhorados
 * ✅ Singleton pattern para evitar múltiplas instâncias
 */

class RealDashboard {
    constructor() {
        // 🔒 SINGLETON: Evitar múltiplas instâncias
        if (RealDashboard.instance) {
            console.warn('⚠️ Dashboard já existe, retornando instância existente');
            return RealDashboard.instance;
        }
        RealDashboard.instance = this;
        
        this.apiBaseUrl = '/api/v2';
        this.currentUser = null;
        this.dashboardData = null;
        this.charts = {};
        this.currentPeriod = '30d';
        this.refreshInterval = null;
        this.isLoading = false;
        this.isUpdatingUI = false; // 🎨 Controle de atualizações UI
        
        // 🚀 CACHE OTIMIZADO: Reduzir requests desnecessários
        this.dataCache = new Map();
        this.cacheTimestamps = new Map();
        this.cacheTTL = 30000; // 30s cache no frontend
        
        // 📊 RATE LIMITING: Evitar spam de requests
        this.requestHistory = [];
        this.maxRequestsPerMinute = 10;
        
        // 🎨 UX MELHORADO: Debouncing e controle de estado
        this.updateDebounceTimer = null;
        this.pendingUpdate = null;
        this.lastChartData = null; // Para comparar se precisa recriar gráficos
        this.loadingStates = new Set(); // Múltiplos estados de loading
        
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
        
        // Expor função para refresh manual (debug/teste)
        window.refreshDashboard = () => {
            console.log('🔄 Refresh manual do dashboard solicitado');
            this.loadRealDashboardData();
        };
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
        if (this.isLoading) {
            console.log('⏳ Carregamento já em andamento, aguardando...');
            return;
        }
        
        try {
            this.isLoading = true;
            this.loadingStates.add('data-fetch');
            const selectedPeriod = period || this.currentPeriod;
            
            // 🚀 VERIFICAR CACHE PRIMEIRO
            const cachedData = this.getFromCache(selectedPeriod);
            if (cachedData) {
                console.log('📦 Usando dados do cache:', {
                    periodo: selectedPeriod,
                    age: this.getCacheAge(selectedPeriod)
                });
                this.dashboardData = cachedData;
                this.scheduleUIUpdate(cachedData, 'cache');
                this.loadingStates.delete('data-fetch');
                this.isLoading = false;
                return;
            }
            
            // ⚡ RATE LIMITING: Verificar se pode fazer request
            if (!this.canMakeRequest()) {
                console.warn('⚠️ Rate limit atingido, usando dados do cache antigo se disponível');
                const oldCache = this.dataCache.get(selectedPeriod);
                if (oldCache) {
                    this.dashboardData = oldCache;
                    this.scheduleUIUpdate(oldCache, 'rate-limited-cache');
                }
                this.loadingStates.delete('data-fetch');
                this.isLoading = false;
                return;
            }
            
            console.log(`📊 Carregando dados REAIS do dashboard (período: ${selectedPeriod})`);
            this.showLoadingState('data-fetch');
            
            // ✅ FETCH COM OTIMIZAÇÕES
            const response = await this.fetchWithAuth(`${this.apiBaseUrl}/dashboard/data?period=${selectedPeriod}`);
            
            if (response.ok) {
                const data = await response.json();
                this.dashboardData = data;
                
                // 💾 SALVAR NO CACHE
                this.setCache(selectedPeriod, data);
                
                console.log('✅ Dados REAIS carregados e cached:', {
                    consultas: data.usage?.total_consultations || 0,
                    custo_total: data.usage?.total_cost || 'R$ 0,00',
                    creditos: data.credits?.available || 'R$ 0,00',
                    tipos_custo: Object.keys(data.costs || {}).length,
                    graficos: Object.keys(data.charts || {}).length,
                    source: 'server_with_cache',
                    version: 'v2.2_ux_optimized'
                });
                
                // 🎨 AGENDAR ATUALIZAÇÃO SUAVE DA UI
                this.scheduleUIUpdate(data, 'server');
                
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
            this.loadingStates.delete('data-fetch');
            this.isLoading = false;
            this.hideLoadingState('data-fetch');
        }
    }

    scheduleUIUpdate(data, source = 'unknown') {
        /**
         * 🎨 DEBOUNCED UI UPDATE: Evita múltiplas atualizações rápidas
         * Agrupa todas as mudanças em uma única atualização suave
         */
        if (this.updateDebounceTimer) {
            clearTimeout(this.updateDebounceTimer);
        }
        
        // Armazenar dados para atualização
        this.pendingUpdate = { data, source, timestamp: Date.now() };
        
        // Debounce de 150ms para agrupar múltiplas atualizações
        this.updateDebounceTimer = setTimeout(() => {
            this.performUIUpdate();
        }, 150);
    }
    
    async performUIUpdate() {
        /**
         * 🎨 ATUALIZAÇÃO SUAVE DA UI: Executada apenas uma vez por batch
         */
        if (this.isUpdatingUI || !this.pendingUpdate) {
            return;
        }
        
        try {
            this.isUpdatingUI = true;
            const { data, source } = this.pendingUpdate;
            
            console.log(`🎨 Atualizando UI de forma suave (fonte: ${source})...`);
            
            // 🔄 BATCH DE ATUALIZAÇÕES: Todas de uma vez para evitar flickering
            await this.batchUpdateUI(data);
            
            // 📊 SMART CHART UPDATE: Só recria se necessário
            await this.smartUpdateCharts(data.charts);
            
            console.log('✅ UI atualizada de forma suave e otimizada');
            
        } catch (error) {
            console.error('❌ Erro na atualização da UI:', error);
        } finally {
            this.isUpdatingUI = false;
            this.pendingUpdate = null;
        }
    }
    
    async batchUpdateUI(data) {
        /**
         * 📦 BATCH UPDATE: Todas as atualizações de dados em lote
         */
        const startTime = performance.now();
        
        // Usar requestAnimationFrame para suavidade visual
        await new Promise(resolve => {
            requestAnimationFrame(() => {
                // Atualizar todos os dados de uma vez
                this.updateCreditsDisplay(data.credits);
                this.updateUsageStats(data.usage);
                this.updateCostsDisplay(data.costs);
                this.updateChartStatistics(data.usage, data.charts);
        this.updatePeriodInfo(data.period, data.last_updated);
        
                resolve();
            });
        });
        
        const elapsed = performance.now() - startTime;
        console.log(`⚡ Batch UI update executado em ${elapsed.toFixed(1)}ms`);
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

    async smartUpdateCharts(chartsData) {
        /**
         * 🧠 SMART CHART UPDATE: Só recria gráficos se os dados mudaram
         * Evita flickering e múltiplas animações desnecessárias
         */
        if (!chartsData) return;
        
        try {
            // Comparar dados para decidir se precisa recriar
            const chartDataChanged = this.hasChartDataChanged(chartsData);
            
            if (!chartDataChanged) {
                console.log('📊 Dados dos gráficos inalterados, mantendo gráficos existentes');
                return;
            }
            
            console.log('📊 Dados dos gráficos mudaram, atualizando de forma suave...');
            
            // Usar requestAnimationFrame para transição suave
            await new Promise(resolve => {
                requestAnimationFrame(async () => {
                    // Fade out suave antes de recriar
                    await this.fadeOutCharts();
                    
                    // Destruir e recriar com novos dados
            this.destroyExistingCharts();
                    this.createAllCharts(chartsData);
                    
                    // Fade in suave
                    await this.fadeInCharts();
                    
                    // Salvar dados atuais para próxima comparação
                    this.lastChartData = JSON.parse(JSON.stringify(chartsData));
                    
                    resolve();
                });
            });
            
            console.log('✅ Gráficos atualizados com transição suave');
            
        } catch (error) {
            console.error('❌ Erro ao atualizar gráficos:', error);
            // Fallback: recriar normalmente em caso de erro
            this.destroyExistingCharts();
            this.createAllCharts(chartsData);
        }
    }
    
    hasChartDataChanged(newData) {
        /**
         * 🔍 COMPARAÇÃO INTELIGENTE: Verifica se dados dos gráficos mudaram
         */
        if (!this.lastChartData) return true;
        
        try {
            // Comparação rápida via JSON (pode ser otimizada se necessário)
            const oldDataStr = JSON.stringify(this.lastChartData);
            const newDataStr = JSON.stringify(newData);
            return oldDataStr !== newDataStr;
        } catch (error) {
            console.warn('⚠️ Erro ao comparar dados dos gráficos, forçando recriação');
            return true;
        }
    }
    
    createAllCharts(chartsData) {
        /**
         * 📊 CRIAÇÃO DE TODOS OS GRÁFICOS: Método unificado
         */
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
    }
    
    async fadeOutCharts() {
        /**
         * 🎭 FADE OUT: Animação suave antes de recriar gráficos
         */
        const chartContainers = document.querySelectorAll('#apiConsumptionChart, #apiVolumeChart, #costBreakdownChart');
        
        return new Promise(resolve => {
            chartContainers.forEach(container => {
                if (container) {
                    container.style.transition = 'opacity 0.2s ease-out';
                    container.style.opacity = '0.3';
                }
            });
            setTimeout(resolve, 200);
        });
    }
    
    async fadeInCharts() {
        /**
         * 🎭 FADE IN: Animação suave após criar gráficos
         */
        const chartContainers = document.querySelectorAll('#apiConsumptionChart, #apiVolumeChart, #costBreakdownChart');
        
        return new Promise(resolve => {
            chartContainers.forEach(container => {
                if (container) {
                    container.style.transition = 'opacity 0.3s ease-in';
                    container.style.opacity = '1';
                }
            });
            setTimeout(resolve, 300);
        });
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

    showLoadingState(source = 'general') {
        /**
         * 🔄 SMART LOADING STATE: Múltiplos estados de loading inteligentes
         */
        this.loadingStates.add(source);
        
        // Só mostrar loader se não estiver já visível
        const loader = document.getElementById('dashboard-loader');
        if (loader && loader.classList.contains('hidden')) {
            loader.classList.remove('hidden');
            // Usar requestAnimationFrame para animação suave
            requestAnimationFrame(() => {
                loader.classList.remove('opacity-0', 'translate-y-2');
                loader.classList.add('opacity-100', 'translate-y-0');
            });
        }
        
        // Manter elementos [data-loading] se existirem (compatibilidade)
        const loadingElements = document.querySelectorAll('[data-loading]');
        loadingElements.forEach(el => el.classList.remove('hidden'));
        
        console.log(`🔄 Loading state ativado: ${source} (total: ${this.loadingStates.size})`);
    }

    hideLoadingState(source = 'general') {
        /**
         * ✅ SMART LOADING HIDE: Só esconde quando todos os loadings terminaram
         */
        this.loadingStates.delete(source);
        
        // Só esconder loader se não há mais estados de loading ativos
        if (this.loadingStates.size === 0) {
        const loader = document.getElementById('dashboard-loader');
            if (loader && !loader.classList.contains('hidden')) {
            loader.classList.remove('opacity-100', 'translate-y-0');
            loader.classList.add('opacity-0', 'translate-y-2');
            // Aguardar animação CSS terminar antes de esconder
                setTimeout(() => {
                    if (this.loadingStates.size === 0) { // Double check
                        loader.classList.add('hidden');
                    }
                }, 300);
        }
        
        // Manter elementos [data-loading] se existirem (compatibilidade)
        const loadingElements = document.querySelectorAll('[data-loading]');
        loadingElements.forEach(el => el.classList.add('hidden'));
        }
        
        console.log(`✅ Loading state removido: ${source} (restantes: ${this.loadingStates.size})`);
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

    // 🚀 MÉTODOS DE CACHE OTIMIZADO
    getFromCache(key) {
        /**
         * 📦 CACHE INTELIGENTE: Retorna dados se ainda válidos
         */
        if (!this.dataCache.has(key)) {
            return null;
        }
        
        const timestamp = this.cacheTimestamps.get(key);
        if (!timestamp) {
            return null;
        }
        
        const age = Date.now() - timestamp;
        if (age > this.cacheTTL) {
            // Cache expirado, limpar
            this.dataCache.delete(key);
            this.cacheTimestamps.delete(key);
            return null;
        }
        
        return this.dataCache.get(key);
    }
    
    setCache(key, data) {
        /**
         * 💾 SALVAR NO CACHE: Com timestamp para TTL
         */
        this.dataCache.set(key, data);
        this.cacheTimestamps.set(key, Date.now());
        
        // Limpar cache antigo para não consumir muita memória
        if (this.dataCache.size > 10) {
            const oldestKey = this.dataCache.keys().next().value;
            this.dataCache.delete(oldestKey);
            this.cacheTimestamps.delete(oldestKey);
        }
    }
    
    getCacheAge(key) {
        /**
         * 🕐 IDADE DO CACHE: Para debugging
         */
        const timestamp = this.cacheTimestamps.get(key);
        if (!timestamp) return 'N/A';
        
        const age = Math.floor((Date.now() - timestamp) / 1000);
        return `${age}s`;
    }
    
    canMakeRequest() {
        /**
         * ⚡ RATE LIMITING: Máximo de requests por minuto
         */
        const now = Date.now();
        const oneMinuteAgo = now - 60000;
        
        // Limpar requests antigos
        this.requestHistory = this.requestHistory.filter(time => time > oneMinuteAgo);
        
        // Verificar se pode fazer nova request
        if (this.requestHistory.length >= this.maxRequestsPerMinute) {
            console.warn(`⚠️ Rate limit: ${this.requestHistory.length}/${this.maxRequestsPerMinute} requests no último minuto`);
            return false;
        }
        
        // Registrar nova request
        this.requestHistory.push(now);
        return true;
    }

    startAutoRefresh() {
        // 🚀 SMART REFRESH: 60s em vez de 30s + detecção de visibilidade
        this.refreshInterval = setInterval(() => {
            // Só fazer refresh se a página estiver visível e não estiver carregando
            if (this.isPageVisible() && !this.isLoading) {
                console.log('🔄 Smart auto-refresh (página visível)...');
            this.loadRealDashboardData();
            } else {
                console.log('⏸️ Auto-refresh pausado (página não visível ou carregando)');
            }
        }, 60000); // ✅ Mudança de 30s para 60s
        
        console.log('⏰ Auto-refresh configurado: 60s com smart detection');
    }
    
    isPageVisible() {
        /**
         * 🔍 DETECÇÃO DE VISIBILIDADE: Evita refresh desnecessário
         * quando usuário não está vendo a página
         */
        return !document.hidden && document.visibilityState === 'visible';
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
        
        // Limpar timers de debounce
        if (this.updateDebounceTimer) {
            clearTimeout(this.updateDebounceTimer);
        }
        
        // Limpar estados
        this.loadingStates.clear();
        
        // Remover instância singleton
        RealDashboard.instance = null;
        
        console.log('🧹 Dashboard Real v2.2 UX otimizado destruído');
    }
}

// 🔒 INICIALIZAÇÃO SINGLETON: Evita múltiplas instâncias
function initializeDashboard() {
    if (window.realDashboard) {
        console.log('🔒 Dashboard já existe, não criando nova instância');
        return window.realDashboard;
    }
    
    if (typeof Chart !== 'undefined') {
        console.log('🎯 Inicializando Dashboard Real v2.2 UX - Dados 100% Reais');
        try {
            window.realDashboard = new RealDashboard();
            console.log('✅ Dashboard v2.2 UX inicializado com sucesso');
            return window.realDashboard;
        } catch (error) {
            console.error('❌ Erro ao inicializar dashboard:', error);
            return null;
        }
    } else {
        console.error('❌ Chart.js não encontrado. Dashboard não pode ser iniciado.');
        return null;
    }
}

// Inicializar dashboard quando a página carregar
document.addEventListener('DOMContentLoaded', () => {
    console.log('📌 DOM carregado - verificando dependências...');
    console.log('📌 Chart.js disponível?', typeof Chart !== 'undefined');
    console.log('📌 Window.location:', window.location.href);
    
    // Tentar inicializar imediatamente
    const dashboard = initializeDashboard();
    
    // Se não conseguiu (Chart.js não carregado), tentar após delay
    if (!dashboard) {
        let retries = 0;
        const maxRetries = 3;
        const retryInterval = setInterval(() => {
            const dashboard = initializeDashboard();
            retries++;
            
            if (dashboard || retries >= maxRetries) {
                clearInterval(retryInterval);
                if (!dashboard) {
                    console.error('❌ Não foi possível inicializar dashboard após múltiplas tentativas');
                }
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

/**
 * JavaScript para página de Histórico de Uso
 * Gerencia histórico de consultas com painel de detalhes
 */

class HistoryManager {
    constructor() {
        this.queryHistory = [];
        this.selectedQuery = null;
        
        this.init();
    }

    async init() {
        console.log('🚀 Inicializando HistoryManager...');
        
        try {
            this.setupEventListeners();
            await this.loadQueryHistory();
            this.renderHistory();
        } catch (error) {
            console.error('❌ Erro ao inicializar HistoryManager:', error);
            this.showError('Erro ao carregar histórico de uso');
        }
    }

    setupEventListeners() {
        // Botão refresh
        const refreshBtn = document.querySelector('[data-refresh-btn]');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshData());
        }
        
        // Botão exportar
        const exportBtn = document.querySelector('[data-export-btn]');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportData());
        }
        
        // Botão fechar detalhes
        const closeDetailBtn = document.querySelector('#close-detail');
        if (closeDetailBtn) {
            closeDetailBtn.addEventListener('click', () => this.closeDetailPanel());
        }

        // Filtros
        this.setupFilters();
    }

    setupFilters() {
        // Filtro de busca com debounce
        const searchInput = document.querySelector('[data-search-input]');
        if (searchInput) {
            searchInput.addEventListener('input', this.debounce((e) => {
                this.applyFilters();
            }, 300));
        }
        
        // Filtro de tipo
        const typeFilter = document.querySelector('[data-type-filter]');
        if (typeFilter) {
            typeFilter.addEventListener('change', () => this.applyFilters());
        }
        
        // Filtro de status
        const statusFilter = document.querySelector('[data-status-filter]');
        if (statusFilter) {
            statusFilter.addEventListener('change', () => this.applyFilters());
        }
        
        // Filtro de data
        const dateFilter = document.querySelector('[data-date-filter]');
        if (dateFilter) {
            dateFilter.addEventListener('change', () => this.applyFilters());
        }
    }

    async applyFilters() {
        const filters = this.getActiveFilters();
        this.showLoading();
        
        try {
            await this.loadQueryHistory(filters);
            this.renderHistory();
        } catch (error) {
            console.error('❌ Erro ao aplicar filtros:', error);
            this.showError('Erro ao aplicar filtros');
        }
    }

    getActiveFilters() {
        const searchInput = document.querySelector('[data-search-input]');
        const typeFilter = document.querySelector('[data-type-filter]');
        const statusFilter = document.querySelector('[data-status-filter]');
        const dateFilter = document.querySelector('[data-date-filter]');

        const filters = {};

        if (searchInput && searchInput.value.trim()) {
            filters.search = searchInput.value.trim();
        }

        if (typeFilter && typeFilter.value !== 'all') {
            filters.type = typeFilter.value;
        }

        if (statusFilter && statusFilter.value !== 'all') {
            filters.status = statusFilter.value;
        }

        if (dateFilter && dateFilter.value) {
            filters.date_from = dateFilter.value;
            filters.date_to = dateFilter.value;
        }

        return filters;
    }

    showLoading() {
        const historyContainer = document.querySelector('[data-history-container]');
        if (historyContainer) {
            historyContainer.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center text-gray-400 py-8">
                        <div class="flex items-center justify-center">
                            <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500 mr-2"></div>
                            <span>Carregando histórico...</span>
                        </div>
                    </td>
                </tr>
            `;
        }
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    async loadQueryHistory(filters = {}) {
        try {
            // Construir URL com parâmetros de filtro
            const params = new URLSearchParams();
            
            if (filters.search) params.append('search', filters.search);
            if (filters.status) params.append('status', filters.status);
            if (filters.type) params.append('type', filters.type);
            if (filters.date_from) params.append('date_from', filters.date_from);
            if (filters.date_to) params.append('date_to', filters.date_to);
            
            const url = `/api/v1/query-history${params.toString() ? '?' + params.toString() : ''}`;
            
            const data = await AuthUtils.authenticatedFetchJSON(url);
            this.queryHistory = data.data || [];
            this.pagination = data.pagination || {};
            
            console.log('✅ Histórico carregado:', this.queryHistory.length, 'registros');
            
            // Atualizar informações de paginação se existir elemento
            this.updatePaginationInfo();
            
        } catch (error) {
            console.error('❌ Erro ao carregar histórico:', error);
            this.queryHistory = [];
            this.showError('Erro ao carregar histórico de consultas');
        }
    }

    updatePaginationInfo() {
        // Implementar atualização de informações de paginação se necessário
        if (this.pagination) {
            console.log(`📄 Página ${this.pagination.page} de ${this.pagination.pages} (${this.pagination.total} total)`);
        }
    }

    renderHistory() {
        const historyContainer = document.querySelector('[data-history-container]');
        if (!historyContainer) return;

        if (this.queryHistory.length === 0) {
            historyContainer.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center text-gray-400 py-8">
                        <div class="flex items-center justify-center">
                            <span class="material-icons text-gray-500 mr-2">history</span>
                            Nenhuma consulta encontrada
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        const historyHtml = this.queryHistory.map(query => `
            <tr class="hover:bg-gray-700 cursor-pointer transition-colors" onclick="historyManager.showQueryDetails('${query.id}')">
                <td class="px-4 py-3 text-sm text-gray-300">
                    <div class="font-medium">${this.formatTime(query.created_at)}</div>
                    <div class="text-xs text-gray-500">${this.formatDate(query.created_at)}</div>
                </td>
                <td class="px-4 py-3 text-sm text-gray-300">
                    <div class="font-medium">${query.cnpj}</div>
                    <div class="text-xs text-gray-500">Consulta CNPJ</div>
                </td>
                <td class="px-4 py-3 text-sm">
                    <div class="flex flex-wrap gap-1">
                        ${this.renderConsultationTypes(query.consultation_types)}
                    </div>
                </td>
                <td class="px-4 py-3 text-sm">
                    <div class="flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full ${this.getStatusColor(query.response_status)}"></span>
                        <span class="${this.getStatusTextColor(query.status)} font-medium">
                            ${query.status_text || this.getStatusText(query.status)}
                        </span>
                    </div>
                </td>
                <td class="px-4 py-3 text-sm text-gray-300">
                    <div class="font-medium">${this.formatClientIP(query.client_ip)}</div>
                    <div class="text-xs text-gray-500">${this.getIPType(query.client_ip)}</div>
                </td>
                <td class="px-4 py-3 text-sm text-gray-300">
                    ${query.formatted_time || this.formatDuration(query.response_time_ms)}
                </td>
                <td class="px-4 py-3 text-sm text-gray-300">
                    <div class="font-medium">${query.formatted_cost || 'R$ 0,00'}</div>
                </td>
            </tr>
        `).join('');

        historyContainer.innerHTML = historyHtml;
    }

    renderConsultationTypes(types) {
        if (!types || types.length === 0) {
            return '<span class="text-xs text-gray-500">Consulta CNPJ</span>';
        }
        
        return types.map(type => {
            let color = 'bg-gray-600';
            if (type.code === 'protestos') color = 'bg-yellow-600';
            else if (type.code === 'receita_federal') color = 'bg-green-600';
            else if (type.code === 'simples_nacional') color = 'bg-blue-600';
            else if (type.code === 'cadastro_contribuintes') color = 'bg-purple-600';
            else if (type.code === 'suframa') color = 'bg-indigo-600';
            
            return `<span class="px-2 py-1 text-xs rounded ${color} text-white">${type.name}</span>`;
        }).join(' ');
    }

    showQueryDetails(queryId) {
        const query = this.queryHistory.find(q => q.id === queryId);
        if (!query) return;

        this.selectedQuery = query;
        this.renderQueryDetails(query);
        this.showDetailPanel();
    }

    renderQueryDetails(query) {
        const detailContent = document.querySelector('#detail-content');
        if (!detailContent) return;

        detailContent.innerHTML = `
            <div class="space-y-6">
                <!-- Header da Consulta -->
                <div>
                    
                    <div class="space-y-3">
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">business</span>
                            <div>
                                <div class="text-sm text-gray-400">CNPJ</div>
                                <div class="text-white font-mono text-lg">${query.cnpj}</div>
                            </div>
                        </div>
                        
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">schedule</span>
                            <div>
                                <div class="text-sm text-gray-400">Data/Hora</div>
                                <div class="text-white">${this.formatDateTime(query.created_at)}</div>
                            </div>
                        </div>
                        
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">check_circle</span>
                            <div>
                                <div class="text-sm text-gray-400">Status</div>
                                <div class="flex items-center gap-2">
                                    <span class="w-2 h-2 rounded-full ${this.getStatusColor(query.response_status)}"></span>
                                    <span class="${this.getStatusTextColor(query.status)}">${query.status_text || this.getStatusText(query.status)}</span>
                                </div>
                            </div>
                        </div>
                        
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">timer</span>
                            <div>
                                <div class="text-sm text-gray-400">Tempo de Resposta</div>
                                <div class="text-white">${query.formatted_time || this.formatDuration(query.response_time_ms)}</div>
                            </div>
                        </div>
                        
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">attach_money</span>
                            <div>
                                <div class="text-sm text-gray-400">Custo Total</div>
                                <div class="text-green-400 font-semibold">${query.formatted_cost || 'R$ 0,00'}</div>
                            </div>
                        </div>
                        
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">computer</span>
                            <div>
                                <div class="text-sm text-gray-400">IP do Cliente</div>
                                <div class="text-white font-mono">${this.formatClientIP(query.client_ip)}</div>
                                <div class="text-xs text-gray-500">${this.getIPType(query.client_ip)}</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Tipos de Consulta -->
                ${this.renderConsultationTypesDetail(query.consultation_types)}

                <!-- Informações Técnicas -->
                <div class="border-t border-gray-700 pt-6">
                    <h4 class="text-lg font-semibold text-white mb-4">Informações Técnicas</h4>
                    
                    <div class="bg-gray-900 rounded-lg p-4 space-y-2 text-sm">
                        <div class="flex justify-between">
                            <span class="text-gray-400">Endpoint:</span>
                            <span class="text-white font-mono">${query.endpoint || '/api/v1/cnpj/consult'}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">Response Status:</span>
                            <span class="text-white">${query.response_status}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">Cache Utilizado:</span>
                            <span class="text-white">${query.cache_used ? 'Sim' : 'Não'}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">ID da Consulta:</span>
                            <span class="text-white font-mono text-xs">${query.id}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-400">IP do Cliente:</span>
                            <span class="text-white font-mono">${query.client_ip || 'N/D'}</span>
                        </div>
                    </div>
                </div>

                <!-- Ações -->
                <div class="border-t border-gray-700 pt-6 pb-6">
                    <h4 class="text-lg font-semibold text-white mb-4">Ações</h4>
                    
                    <div class="flex gap-2 flex-wrap">
                        <button class="px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors flex items-center gap-2" onclick="historyManager.viewJSON('${query.id}')">
                            <span class="material-icons text-sm">code</span>
                            Ver JSON
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    renderConsultationTypesDetail(types) {
        if (!types || types.length === 0) {
            return `
                <div class="border-t border-gray-700 pt-6">
                    <h4 class="text-lg font-semibold text-white mb-4">Tipos de Consulta</h4>
                    <div class="text-gray-400 text-sm">Nenhum tipo específico registrado</div>
                </div>
            `;
        }

        const typesHtml = types.map(type => {
            let colorClass = 'bg-gray-600';
            if (type.code === 'protestos') colorClass = 'bg-yellow-600';
            else if (type.code === 'receita_federal') colorClass = 'bg-green-600';
            else if (type.code === 'simples_nacional') colorClass = 'bg-blue-600';
            else if (type.code === 'cadastro_contribuintes') colorClass = 'bg-purple-600';
            else if (type.code === 'suframa') colorClass = 'bg-indigo-600';

            return `
                <div class="flex items-center justify-between p-3 bg-gray-900 rounded-lg">
                    <div class="flex items-center gap-3">
                        <span class="px-2 py-1 text-xs rounded ${colorClass} text-white">${type.name}</span>
                        <span class="text-gray-400 text-sm">${type.code}</span>
                    </div>
                    <div class="text-right">
                        <div class="text-white font-semibold">R$ ${(type.cost_cents / 100).toFixed(2)}</div>
                        <div class="text-xs ${type.success ? 'text-green-400' : 'text-red-400'}">
                            ${type.success ? '✓ Sucesso' : '✗ Falha'}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        return `
            <div class="border-t border-gray-700 pt-6">
                <h4 class="text-lg font-semibold text-white mb-4">Tipos de Consulta</h4>
                <div class="space-y-2">
                    ${typesHtml}
                </div>
            </div>
        `;
    }

    viewJSON(queryId) {
        const query = this.queryHistory.find(q => q.id === queryId);
        if (!query) return;

        // Criar modal para exibir JSON
        const jsonModal = document.createElement('div');
        jsonModal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        jsonModal.innerHTML = `
            <div class="bg-gray-800 rounded-lg p-6 max-w-4xl max-h-96 overflow-auto">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-semibold text-white">Dados JSON da Consulta</h3>
                    <button class="text-gray-400 hover:text-white" onclick="this.closest('.fixed').remove()">
                        <span class="material-icons">close</span>
                    </button>
                </div>
                <pre class="bg-gray-900 p-4 rounded text-green-400 text-sm overflow-auto">${JSON.stringify(query, null, 2)}</pre>
            </div>
        `;
        document.body.appendChild(jsonModal);
    }

    repeatQuery(cnpj) {
        // Redirecionar para página de consultas com CNPJ preenchido
        window.location.href = `/consultas?cnpj=${cnpj}`;
    }

    showDetailPanel() {
        const detailPanel = document.querySelector('#detail-panel');
        if (detailPanel) {
            detailPanel.style.display = 'block';
            // Forçar recálculo de layout para garantir scroll
            setTimeout(() => {
                const detailContent = document.querySelector('#detail-content');
                if (detailContent) {
                    detailContent.style.overflowY = 'auto';
                }
            }, 10);
        }
    }

    closeDetailPanel() {
        const detailPanel = document.querySelector('#detail-panel');
        if (detailPanel) {
            detailPanel.style.display = 'none';
        }
        this.selectedQuery = null;
    }

    async refreshData() {
        console.log('🔄 Atualizando dados...');
        try {
        await this.loadQueryHistory();
        this.renderHistory();
            console.log('✅ Dados atualizados');
        } catch (error) {
            console.error('❌ Erro ao atualizar:', error);
            this.showError('Erro ao atualizar dados');
        }
    }

    async exportData() {
        console.log('📤 Exportando dados...');
        try {
            const data = await AuthUtils.authenticatedFetchJSON('/api/v1/query-history/export');
            
            // Criar e baixar arquivo CSV
            const csvContent = this.convertToCSV(data.data);
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);
            link.setAttribute('href', url);
            link.setAttribute('download', data.filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            this.showSuccess('Dados exportados com sucesso!');
        } catch (error) {
            console.error('❌ Erro ao exportar:', error);
            this.showError('Erro ao exportar dados');
        }
    }

    // Função auxiliar para converter para horário de Brasília
    toBrasiliaTime(dateString) {
        const date = new Date(dateString);
        // Forçar conversão para timezone do Brasil
        return new Date(date.toLocaleString("en-US", {timeZone: "America/Sao_Paulo"}));
    }

    formatTime(dateString) {
        try {
            const date = new Date(dateString);
            return date.toLocaleTimeString('pt-BR', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                timeZone: 'America/Sao_Paulo'
            });
        } catch (error) {
            console.error('Erro ao formatar horário:', error);
            return '--:--:--';
        }
    }

    formatDate(dateString) {
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('pt-BR', {
                day: '2-digit',
                month: '2-digit',
                year: 'numeric',
                timeZone: 'America/Sao_Paulo'
            });
        } catch (error) {
            console.error('Erro ao formatar data:', error);
            return '--/--/----';
        }
    }

    formatDateTime(dateString) {
        try {
            const date = new Date(dateString);
            
            // Usar Intl.DateTimeFormat para maior controle
            const formatter = new Intl.DateTimeFormat('pt-BR', {
                timeZone: 'America/Sao_Paulo',
                day: '2-digit',
                month: '2-digit', 
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            });
            
            return formatter.format(date);
        } catch (error) {
            console.error('Erro ao formatar data/hora:', error);
            return '--/--/---- --:--:--';
        }
    }

    formatDuration(ms) {
        if (!ms || ms === 0) return '0.00 s';
        if (ms < 1000) return `${ms} ms`;
        return `${(ms / 1000).toFixed(2)} s`;
    }

    getStatusColor(status) {
        if (status >= 200 && status < 300) return 'bg-green-500';
        if (status >= 400 && status < 500) return 'bg-yellow-500';
        if (status >= 500) return 'bg-red-500';
        return 'bg-gray-500';
    }

    getStatusText(status) {
        switch (status) {
            case 'success': return 'Sucesso';
            case 'error': return 'Erro';
            default: return 'Desconhecido';
        }
    }

    getStatusTextColor(status) {
        switch (status) {
            case 'success': return 'text-green-400';
            case 'error': return 'text-red-400';
            default: return 'text-gray-400';
        }
    }

    formatClientIP(ip) {
        if (!ip || ip === 'unknown') {
            return '<span class="text-gray-500">Não disponível</span>';
        }
        return ip;
    }

    getIPType(ip) {
        if (!ip || ip === 'unknown') return 'N/D';
        
        // Identificar tipo de IP
        if (ip.startsWith('127.') || ip === 'localhost') return 'Local';
        if (ip.startsWith('192.168.') || ip.startsWith('10.') || ip.startsWith('172.')) return 'Rede privada';
        if (ip.includes(':')) return 'IPv6';
        
        return 'IP público';
    }


    showSuccess(message) {
        console.log('✅', message);
        this.showNotification(message, 'success');
    }

    showError(message) {
        console.error('❌', message);
        this.showNotification(message, 'error');
    }

    showNotification(message, type = 'info') {
        // Remover notificações existentes
        const existingNotifications = document.querySelectorAll('.notification-toast');
        existingNotifications.forEach(n => n.remove());

        // Criar nova notificação
        const notification = document.createElement('div');
        notification.className = `notification-toast fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg max-w-sm transition-all duration-300`;
        
        let bgColor = 'bg-blue-600';
        let icon = 'info';
        
        if (type === 'success') {
            bgColor = 'bg-green-600';
            icon = 'check_circle';
        } else if (type === 'error') {
            bgColor = 'bg-red-600';
            icon = 'error';
        }
        
        notification.className += ` ${bgColor} text-white`;
        
        notification.innerHTML = `
            <div class="flex items-center gap-3">
                <span class="material-icons">${icon}</span>
                <span class="flex-1">${message}</span>
                <button class="text-white hover:text-gray-200" onclick="this.closest('.notification-toast').remove()">
                    <span class="material-icons text-sm">close</span>
                </button>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remover após 5 segundos
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.opacity = '0';
                notification.style.transform = 'translateX(100%)';
                setTimeout(() => notification.remove(), 300);
            }
        }, 5000);
    }

    convertToCSV(data) {
        if (!data || data.length === 0) return '';
        
        const headers = ['Data/Hora', 'CNPJ', 'Status', 'IP Cliente', 'Tipo IP', 'Tempo (ms)', 'Custo (R$)', 'Créditos Usados', 'Endpoint'];
        const rows = data.map(query => [
            query.created_at,
            query.cnpj,
            query.status_text || query.status || 'success',
            query.client_ip || 'N/D',
            this.getIPType(query.client_ip),
            query.response_time_ms || 0,
            query.formatted_cost || 'R$ 0,00',
            query.credits_used || 0,
            query.endpoint || '/api/v1/cnpj/consult'
        ]);
        
        const csvContent = [headers, ...rows]
            .map(row => row.map(field => `"${field}"`).join(','))
            .join('\n');
        
        return csvContent;
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    window.historyManager = new HistoryManager();
});

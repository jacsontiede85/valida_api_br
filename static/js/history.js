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
    }

    async loadQueryHistory() {
        try {
            const data = await AuthUtils.authenticatedFetchJSON('/api/v1/query-history');
            this.queryHistory = data.data || [];
            console.log('✅ Histórico carregado:', this.queryHistory.length, 'registros');
        } catch (error) {
            console.error('❌ Erro ao carregar histórico:', error);
            this.queryHistory = [];
            this.showError('Erro ao carregar histórico de consultas');
        }
    }

    renderHistory() {
        const historyContainer = document.querySelector('[data-history-container]');
        if (!historyContainer) return;

        if (this.queryHistory.length === 0) {
            historyContainer.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-gray-400 py-8">
                        Nenhuma consulta encontrada
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
                    <div class="flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full ${this.getStatusColor(query.response_status)}"></span>
                        <span class="${this.getStatusTextColor(query.status || 'success')} font-medium">${this.getStatusText(query.status || 'success')}</span>
                    </div>
                    <div class="text-xs text-gray-500">${query.response_status}</div>
                </td>
                <td class="px-4 py-3 text-sm text-gray-300">
                    ${this.formatDuration(query.response_time_ms)}
                </td>
                <td class="px-4 py-3 text-sm text-gray-300">
                    ${query.credits_used || 0} créditos
                </td>
            </tr>
        `).join('');

        historyContainer.innerHTML = historyHtml;
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
                    <h3 class="text-lg font-semibold text-white mb-4">Consulta CNPJ</h3>
                    
                    <div class="space-y-3">
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">business</span>
                            <div>
                                <div class="text-sm text-gray-400">CNPJ</div>
                                <div class="text-white font-mono">${query.cnpj}</div>
                            </div>
                        </div>
                        
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">schedule</span>
                            <div>
                                <div class="text-sm text-gray-400">Timestamp</div>
                                <div class="text-white">${this.formatDateTime(query.created_at)}</div>
                            </div>
                        </div>
                        
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">link</span>
                            <div>
                                <div class="text-sm text-gray-400">Endpoint</div>
                                <div class="text-white font-mono text-sm">${query.endpoint || '/api/v1/cnpj/consult'}</div>
                            </div>
                        </div>
                        
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">check_circle</span>
                            <div>
                                <div class="text-sm text-gray-400">Status</div>
                                <div class="${this.getStatusTextColor(query.status || 'success')}">${this.getStatusText(query.status || 'success')} (${query.response_status})</div>
                </div>
                </div>
                        
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">timer</span>
                            <div>
                                <div class="text-sm text-gray-400">Tempo</div>
                                <div class="text-white">${this.formatDuration(query.response_time_ms)}</div>
                </div>
            </div>
            
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">attach_money</span>
                            <div>
                                <div class="text-sm text-gray-400">Custo</div>
                                <div class="text-white">${query.credits_used || 0} créditos</div>
                            </div>
                        </div>
                </div>
            </div>

                <!-- Metadados -->
                <div class="border-t border-gray-700 pt-6">
                    <h4 class="text-lg font-semibold text-white mb-4">Metadados</h4>
                    
                    <div class="space-y-3">
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">tag</span>
                            <div>
                                <div class="text-sm text-gray-400">ID da Consulta</div>
                                <div class="text-white font-mono text-sm">${query.id}</div>
                            </div>
                        </div>
                        
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">key</span>
                            <div>
                                <div class="text-sm text-gray-400">API Key ID</div>
                                <div class="text-white font-mono text-sm">${query.api_key_id || 'N/A'}</div>
                            </div>
                        </div>
                        
                        <div class="flex items-center gap-3">
                            <span class="material-icons text-gray-400">person</span>
                            <div>
                                <div class="text-sm text-gray-400">User ID</div>
                                <div class="text-white font-mono text-sm">${query.user_id}</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Informações Técnicas -->
                <div class="border-t border-gray-700 pt-6">
                    <h4 class="text-lg font-semibold text-white mb-4">Informações Técnicas</h4>
                    
                    <div class="space-y-2">
                        <div class="flex justify-between text-sm">
                            <span class="text-gray-400">Response Status</span>
                            <span class="text-white">${query.response_status}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span class="text-gray-400">Response Time</span>
                            <span class="text-white">${this.formatDuration(query.response_time_ms)}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span class="text-gray-400">Credits Used</span>
                            <span class="text-white">${query.credits_used || 0}</span>
                        </div>
                        <div class="flex justify-between text-sm">
                            <span class="text-gray-400">Status</span>
                            <span class="${this.getStatusTextColor(query.status || 'success')}">${this.getStatusText(query.status || 'success')}</span>
                        </div>
                    </div>
                </div>

                <!-- Custo -->
                <div class="border-t border-gray-700 pt-6">
                    <h4 class="text-lg font-semibold text-white mb-4">Custo</h4>
                    
                    <div class="space-y-2">
                        <div class="flex justify-between text-sm">
                            <span class="text-gray-400">Consulta CNPJ</span>
                            <span class="text-white">${query.credits_used || 0} créditos</span>
                        </div>
                        <div class="flex justify-between text-sm font-semibold border-t border-gray-700 pt-2">
                            <span class="text-white">= Total</span>
                            <span class="text-white">${query.credits_used || 0} créditos</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    showDetailPanel() {
        const detailPanel = document.querySelector('#detail-panel');
        if (detailPanel) {
            detailPanel.style.display = 'block';
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

    formatTime(dateString) {
        const date = new Date(dateString);
        return date.toLocaleTimeString('pt-BR', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            timeZone: 'America/Sao_Paulo'
        });
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('pt-BR', {
            timeZone: 'America/Sao_Paulo'
        });
    }

    formatDateTime(dateString) {
        const date = new Date(dateString);
        return date.toLocaleString('pt-BR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            timeZone: 'America/Sao_Paulo'
        });
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


    showSuccess(message) {
        console.log('✅', message);
        // Implementar notificação de sucesso
    }


    convertToCSV(data) {
        if (!data || data.length === 0) return '';
        
        const headers = ['Data/Hora', 'CNPJ', 'Status', 'Tempo (ms)', 'Créditos Usados', 'Endpoint'];
        const rows = data.map(query => [
            query.created_at,
            query.cnpj,
            query.status || 'success',
            query.response_time_ms || 0,
            query.credits_used || 0,
            query.endpoint || '/api/v1/cnpj/consult'
        ]);
        
        const csvContent = [headers, ...rows]
            .map(row => row.map(field => `"${field}"`).join(','))
            .join('\n');
        
        return csvContent;
    }

    showError(message) {
        console.error('❌', message);
        // Implementar notificação de erro
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    window.historyManager = new HistoryManager();
});

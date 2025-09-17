/**
 * JavaScript para página de Faturas
 * Gerencia histórico de faturas, pagamentos e downloads
 */

class FaturasManager {
    constructor() {
        this.invoices = [];
        this.filters = {
            status: 'all',
            dateFrom: null,
            dateTo: null,
            search: ''
        };
        this.pagination = {
            page: 1,
            limit: 10,
            total: 0
        };
        
        this.init();
    }

    async init() {
        console.log('🚀 Inicializando FaturasManager...');
        
        try {
            this.setupEventListeners();
            await this.loadInvoices();
            this.renderInvoices();
            this.updateFilters();
        } catch (error) {
            console.error('❌ Erro ao inicializar FaturasManager:', error);
            this.showError('Erro ao carregar faturas');
        }
    }

    setupEventListeners() {
        // Filtros
        const statusFilter = document.querySelector('[data-filter-status]');
        const dateFromInput = document.querySelector('[data-filter-date-from]');
        const dateToInput = document.querySelector('[data-filter-date-to]');
        const searchInput = document.querySelector('[data-filter-search]');

        if (statusFilter) {
            statusFilter.addEventListener('change', () => this.handleFilterChange());
        }
        if (dateFromInput) {
            dateFromInput.addEventListener('change', () => this.handleFilterChange());
        }
        if (dateToInput) {
            dateToInput.addEventListener('change', () => this.handleFilterChange());
        }
        if (searchInput) {
            searchInput.addEventListener('input', () => this.handleSearchChange());
        }

        // Botões de ação
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-download-invoice]')) {
                this.handleDownloadInvoice(e.target.dataset.invoiceId);
            }
            if (e.target.matches('[data-view-invoice]')) {
                this.handleViewInvoice(e.target.dataset.invoiceId);
            }
            if (e.target.matches('[data-pay-invoice]')) {
                this.handlePayInvoice(e.target.dataset.invoiceId);
            }
            if (e.target.matches('[data-refresh-invoices]')) {
                this.handleRefresh();
            }
            if (e.target.matches('[data-clear-filters]')) {
                this.handleClearFilters();
            }
            if (e.target.matches('[data-pagination-prev]')) {
                this.handlePagination('prev');
            }
            if (e.target.matches('[data-pagination-next]')) {
                this.handlePagination('next');
            }
        });

        // Período rápido
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-period-btn]')) {
                const period = e.target.dataset.periodBtn;
                this.handleQuickPeriod(period);
            }
        });
    }

    async loadInvoices() {
        try {
            const params = new URLSearchParams({
                page: this.pagination.page,
                limit: this.pagination.limit,
                ...this.filters
            });

            const response = await fetch(`/api/v1/invoices?${params}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.invoices = data.invoices || [];
            this.pagination.total = data.total || 0;
            console.log('✅ Faturas carregadas:', this.invoices.length, 'registros');
        } catch (error) {
            console.error('❌ Erro ao carregar faturas:', error);
            // Fallback para dados mock
            this.invoices = this.getMockInvoices();
            this.pagination.total = this.invoices.length;
        }
    }

    renderInvoices() {
        const invoicesContainer = document.querySelector('[data-invoices-container]');
        if (!invoicesContainer) return;

        if (this.invoices.length === 0) {
            invoicesContainer.innerHTML = `
                <div class="text-center text-[#92adc9] py-8">
                    <p>Nenhuma fatura encontrada</p>
                    <p class="text-sm mt-2">Suas faturas aparecerão aqui</p>
                </div>
            `;
            return;
        }

        const invoicesHtml = this.invoices.map(invoice => `
            <tr class="border-t border-t-[#324d67] hover:bg-[#192633]">
                <td class="px-4 py-3 text-[#92adc9] text-sm font-normal">
                    ${this.formatDate(invoice.created_at)}
                </td>
                <td class="px-4 py-3 text-[#92adc9] text-sm font-normal">
                    ${invoice.invoice_number}
                </td>
                <td class="px-4 py-3 text-[#92adc9] text-sm font-normal">
                    R$ ${(invoice.amount / 100).toFixed(2).replace('.', ',')}
                </td>
                <td class="px-4 py-3 text-sm font-normal">
                    <span class="status-badge ${this.getStatusClass(invoice.status)}">
                        ${this.getStatusText(invoice.status)}
                    </span>
                </td>
                <td class="px-4 py-3 text-[#92adc9] text-sm font-normal">
                    ${this.formatDate(invoice.due_date)}
                </td>
                <td class="px-4 py-3 text-[#92adc9] text-sm font-normal">
                    ${this.formatDate(invoice.paid_at) || 'N/A'}
                </td>
                <td class="px-4 py-3">
                    <div class="flex gap-2">
                        ${this.renderInvoiceActions(invoice)}
                    </div>
                </td>
            </tr>
        `).join('');

        invoicesContainer.innerHTML = invoicesHtml;
        this.updatePaginationInfo();
    }

    renderInvoiceActions(invoice) {
        const actions = [];

        // Botão de visualizar
        actions.push(`
            <button class="btn btn-sm btn-outline" data-view-invoice data-invoice-id="${invoice.id}">
                Ver
            </button>
        `);

        // Botão de download
        if (invoice.status === 'paid' || invoice.status === 'overdue') {
            actions.push(`
                <button class="btn btn-sm btn-primary" data-download-invoice data-invoice-id="${invoice.id}">
                    Download
                </button>
            `);
        }

        // Botão de pagar
        if (invoice.status === 'pending' || invoice.status === 'overdue') {
            actions.push(`
                <button class="btn btn-sm btn-success" data-pay-invoice data-invoice-id="${invoice.id}">
                    Pagar
                </button>
            `);
        }

        return actions.join('');
    }

    async handleDownloadInvoice(invoiceId) {
        try {
            this.showLoading('Preparando download...');

            const response = await fetch(`/api/v1/invoices/${invoiceId}/download`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `fatura_${invoiceId}.pdf`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            this.showSuccess('Download iniciado!');
            
        } catch (error) {
            console.error('❌ Erro ao baixar fatura:', error);
            this.showError('Erro ao baixar fatura');
        } finally {
            this.hideLoading();
        }
    }

    async handleViewInvoice(invoiceId) {
        try {
            this.showLoading('Carregando fatura...');

            const response = await fetch(`/api/v1/invoices/${invoiceId}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.showInvoiceModal(data.invoice);
            
        } catch (error) {
            console.error('❌ Erro ao visualizar fatura:', error);
            this.showError('Erro ao carregar fatura');
        } finally {
            this.hideLoading();
        }
    }

    async handlePayInvoice(invoiceId) {
        try {
            this.showLoading('Processando pagamento...');

            const response = await fetch(`/api/v1/invoices/${invoiceId}/pay`, {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || 'Erro ao processar pagamento');
            }

            const data = await response.json();
            
            if (data.payment_url) {
                // Redirecionar para página de pagamento
                window.open(data.payment_url, '_blank');
            } else {
                this.showSuccess('Pagamento processado com sucesso!');
                await this.loadInvoices();
                this.renderInvoices();
            }
            
        } catch (error) {
            console.error('❌ Erro ao pagar fatura:', error);
            this.showError(`Erro ao processar pagamento: ${error.message}`);
        } finally {
            this.hideLoading();
        }
    }

    showInvoiceModal(invoice) {
        const modal = document.createElement('div');
        modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
        modal.innerHTML = `
            <div class="bg-[#192633] rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-white text-lg font-bold">Fatura ${invoice.invoice_number}</h3>
                    <button onclick="this.closest('.fixed').remove()" class="text-[#92adc9] hover:text-white">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                
                <div class="space-y-4">
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="text-[#92adc9] text-sm">Data de Emissão</label>
                            <p class="text-white">${this.formatDate(invoice.created_at)}</p>
                        </div>
                        <div>
                            <label class="text-[#92adc9] text-sm">Vencimento</label>
                            <p class="text-white">${this.formatDate(invoice.due_date)}</p>
                        </div>
                    </div>
                    
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="text-[#92adc9] text-sm">Valor</label>
                            <p class="text-white text-xl font-bold">R$ ${(invoice.amount / 100).toFixed(2).replace('.', ',')}</p>
                        </div>
                        <div>
                            <label class="text-[#92adc9] text-sm">Status</label>
                            <p class="text-white">
                                <span class="status-badge ${this.getStatusClass(invoice.status)}">
                                    ${this.getStatusText(invoice.status)}
                                </span>
                            </p>
                        </div>
                    </div>
                    
                    ${invoice.items ? `
                        <div>
                            <label class="text-[#92adc9] text-sm">Itens</label>
                            <div class="mt-2 space-y-2">
                                ${invoice.items.map(item => `
                                    <div class="flex justify-between items-center p-2 bg-[#111a22] rounded">
                                        <span class="text-white">${item.description}</span>
                                        <span class="text-[#92adc9]">R$ ${(item.amount / 100).toFixed(2).replace('.', ',')}</span>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                    
                    ${invoice.payment_method ? `
                        <div>
                            <label class="text-[#92adc9] text-sm">Método de Pagamento</label>
                            <p class="text-white">${invoice.payment_method}</p>
                        </div>
                    ` : ''}
                </div>
                
                <div class="flex gap-2 mt-6">
                    <button class="btn btn-primary flex-1" data-download-invoice data-invoice-id="${invoice.id}">
                        Download PDF
                    </button>
                    ${invoice.status === 'pending' || invoice.status === 'overdue' ? `
                        <button class="btn btn-success flex-1" data-pay-invoice data-invoice-id="${invoice.id}">
                            Pagar Agora
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    async handleFilterChange() {
        const statusFilter = document.querySelector('[data-filter-status]');
        const dateFromInput = document.querySelector('[data-filter-date-from]');
        const dateToInput = document.querySelector('[data-filter-date-to]');

        this.filters.status = statusFilter?.value || 'all';
        this.filters.dateFrom = dateFromInput?.value || null;
        this.filters.dateTo = dateToInput?.value || null;

        this.pagination.page = 1;
        await this.loadInvoices();
        this.renderInvoices();
    }

    async handleSearchChange() {
        const searchInput = document.querySelector('[data-filter-search]');
        this.filters.search = searchInput?.value || '';

        // Debounce da busca
        clearTimeout(this.searchTimeout);
        this.searchTimeout = setTimeout(async () => {
            this.pagination.page = 1;
            await this.loadInvoices();
            this.renderInvoices();
        }, 300);
    }

    async handleQuickPeriod(period) {
        const today = new Date();
        let dateFrom, dateTo;

        switch (period) {
            case 'this-month':
                dateFrom = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().split('T')[0];
                dateTo = today.toISOString().split('T')[0];
                break;
            case 'last-month':
                const lastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
                dateFrom = lastMonth.toISOString().split('T')[0];
                dateTo = new Date(today.getFullYear(), today.getMonth(), 0).toISOString().split('T')[0];
                break;
            case 'last-3-months':
                dateFrom = new Date(today.getFullYear(), today.getMonth() - 3, 1).toISOString().split('T')[0];
                dateTo = today.toISOString().split('T')[0];
                break;
            case 'last-6-months':
                dateFrom = new Date(today.getFullYear(), today.getMonth() - 6, 1).toISOString().split('T')[0];
                dateTo = today.toISOString().split('T')[0];
                break;
            case 'this-year':
                dateFrom = new Date(today.getFullYear(), 0, 1).toISOString().split('T')[0];
                dateTo = today.toISOString().split('T')[0];
                break;
            default:
                return;
        }

        this.filters.dateFrom = dateFrom;
        this.filters.dateTo = dateTo;
        this.updateFilters();
        
        this.pagination.page = 1;
        await this.loadInvoices();
        this.renderInvoices();
    }

    async handlePagination(direction) {
        if (direction === 'prev' && this.pagination.page > 1) {
            this.pagination.page--;
        } else if (direction === 'next' && this.pagination.page < Math.ceil(this.pagination.total / this.pagination.limit)) {
            this.pagination.page++;
        } else {
            return;
        }

        await this.loadInvoices();
        this.renderInvoices();
    }

    updatePaginationInfo() {
        const paginationInfo = document.querySelector('[data-pagination-info]');
        if (paginationInfo) {
            const start = (this.pagination.page - 1) * this.pagination.limit + 1;
            const end = Math.min(this.pagination.page * this.pagination.limit, this.pagination.total);
            paginationInfo.textContent = `${start}-${end} de ${this.pagination.total}`;
        }
    }

    async handleRefresh() {
        this.showLoading('Atualizando faturas...');
        try {
            await this.loadInvoices();
            this.renderInvoices();
        } catch (error) {
            this.showError('Erro ao atualizar faturas');
        } finally {
            this.hideLoading();
        }
    }

    async handleClearFilters() {
        this.filters = {
            status: 'all',
            dateFrom: null,
            dateTo: null,
            search: ''
        };
        
        this.pagination.page = 1;
        this.updateFilters();
        await this.loadInvoices();
        this.renderInvoices();
    }

    updateFilters() {
        const statusFilter = document.querySelector('[data-filter-status]');
        const dateFromInput = document.querySelector('[data-filter-date-from]');
        const dateToInput = document.querySelector('[data-filter-date-to]');
        const searchInput = document.querySelector('[data-filter-search]');

        if (statusFilter) {
            statusFilter.value = this.filters.status;
        }
        if (dateFromInput) {
            dateFromInput.value = this.filters.dateFrom || '';
        }
        if (dateToInput) {
            dateToInput.value = this.filters.dateTo || '';
        }
        if (searchInput) {
            searchInput.value = this.filters.search;
        }
    }

    getStatusClass(status) {
        switch (status) {
            case 'paid': return 'success';
            case 'pending': return 'warning';
            case 'overdue': return 'error';
            case 'cancelled': return 'info';
            default: return 'info';
        }
    }

    getStatusText(status) {
        switch (status) {
            case 'paid': return 'Pago';
            case 'pending': return 'Pendente';
            case 'overdue': return 'Vencido';
            case 'cancelled': return 'Cancelado';
            default: return 'Desconhecido';
        }
    }

    formatDate(dateString) {
        if (!dateString) return 'N/A';
        const date = new Date(dateString);
        return date.toLocaleDateString('pt-BR');
    }

    showLoading(message) {
        console.log('⏳', message);
    }

    hideLoading() {
        console.log('✅ Loading finalizado');
    }

    showSuccess(message) {
        console.log('✅', message);
        alert(message);
    }

    showError(message) {
        console.error('❌', message);
        alert(message);
    }

    // Dados mock para desenvolvimento
    getMockInvoices() {
        const statuses = ['paid', 'pending', 'overdue', 'cancelled'];
        const amounts = [2990, 9990, 29990, 4990, 14990];
        
        return Array.from({ length: 20 }, (_, i) => {
            const createdDate = new Date(Date.now() - i * 30 * 24 * 60 * 60 * 1000);
            const dueDate = new Date(createdDate.getTime() + 30 * 24 * 60 * 60 * 1000);
            const status = statuses[Math.floor(Math.random() * statuses.length)];
            const amount = amounts[Math.floor(Math.random() * amounts.length)];
            
            return {
                id: `inv-${i + 1}`,
                invoice_number: `INV-${String(i + 1).padStart(4, '0')}`,
                amount: amount,
                status: status,
                created_at: createdDate.toISOString(),
                due_date: dueDate.toISOString(),
                paid_at: status === 'paid' ? new Date(createdDate.getTime() + 15 * 24 * 60 * 60 * 1000).toISOString() : null,
                payment_method: status === 'paid' ? 'Cartão de Crédito' : null,
                items: [
                    {
                        description: 'Plano de Assinatura - Mês',
                        amount: amount
                    }
                ]
            };
        });
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    new FaturasManager();
});

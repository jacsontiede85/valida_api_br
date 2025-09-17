/**
 * JavaScript para página de Consultas
 * Gerencia consultas de CNPJ via API
 */

class ConsultasManager {
    constructor() {
        this.lastResult = null; // Para armazenar o JSON completo
        this.init();
    }

    async init() {
        console.log('🚀 Inicializando ConsultasManager...');
        
        try {
            this.setupEventListeners();
        } catch (error) {
            console.error('❌ Erro ao inicializar ConsultasManager:', error);
            this.showError('Erro ao inicializar página de consultas');
        }
    }

    setupEventListeners() {
        // Formulário de consulta
        const form = document.getElementById('consulta-form');
        if (form) {
            form.addEventListener('submit', (e) => this.handleConsulta(e));
        }

        // Botão limpar
        const limparBtn = document.getElementById('limpar-btn');
        if (limparBtn) {
            limparBtn.addEventListener('click', () => this.limparFormulario());
        }

        // Input de CNPJ com formatação automática
        const cnpjInput = document.getElementById('cnpj');
        if (cnpjInput) {
            cnpjInput.addEventListener('input', (e) => this.formatarCNPJ(e));
        }

        // Checkbox da Receita Federal para habilitar/desabilitar subopções
        const receitaFederalCheckbox = document.getElementById('receita-federal');
        if (receitaFederalCheckbox) {
            receitaFederalCheckbox.addEventListener('change', () => this.toggleReceitaFederalOptions());
        }

        // Validação em tempo real para mostrar/ocultar aviso
        const checkboxes = ['protestos', 'receita-federal'];
        checkboxes.forEach(id => {
            const checkbox = document.getElementById(id);
            if (checkbox) {
                checkbox.addEventListener('change', () => this.validateSelections());
            }
        });

        // Botão para visualizar JSON
        const btnViewJson = document.getElementById('btn-view-json');
        if (btnViewJson) {
            btnViewJson.addEventListener('click', () => this.showJsonModal());
        }

        // Botão para fechar modal JSON
        const btnCloseJson = document.getElementById('btn-close-json');
        if (btnCloseJson) {
            btnCloseJson.addEventListener('click', () => this.hideJsonModal());
        }

        // Botão para copiar JSON
        const btnCopyJson = document.getElementById('btn-copy-json');
        if (btnCopyJson) {
            btnCopyJson.addEventListener('click', () => this.copyJsonToClipboard());
        }

        // Fechar modal clicando fora
        const jsonModal = document.getElementById('json-modal');
        if (jsonModal) {
            jsonModal.addEventListener('click', (e) => {
                if (e.target === jsonModal) {
                    this.hideJsonModal();
                }
            });
        }
    }

    async handleConsulta(event) {
        event.preventDefault();
        
        const cnpjInput = document.getElementById('cnpj');
        const cnpj = cnpjInput.value.trim();
        
        if (!cnpj) {
            this.showError('Por favor, digite um CNPJ válido');
            return;
        }

        // Validar CNPJ
        if (!this.validarCNPJ(cnpj)) {
            this.showError('CNPJ inválido. Verifique o formato e tente novamente.');
            return;
        }

        // Validar seleções obrigatórias
        if (!this.validateSelections(true)) {
            return;
        }

        this.showLoading();
        
        try {
            const resultado = await this.consultarCNPJ(cnpj);
            this.lastResult = resultado; // Armazenar para visualização JSON
            this.exibirResultado(resultado);
        } catch (error) {
            console.error('❌ Erro na consulta:', error);
            this.exibirErro(error.message || 'Erro ao consultar CNPJ');
        } finally {
            this.hideLoading();
        }
    }

    toggleReceitaFederalOptions() {
        const receitaFederalCheckbox = document.getElementById('receita-federal');
        const subOptionsContainer = document.getElementById('receita-sub-options');
        const subCheckboxes = ['simples', 'registrations', 'geocoding', 'suframa'];
        const strategySelect = document.getElementById('strategy');
        
        const isEnabled = receitaFederalCheckbox.checked;
        
        // Habilitar/desabilitar subopções
        subCheckboxes.forEach(id => {
            const checkbox = document.getElementById(id);
            if (checkbox) {
                checkbox.disabled = !isEnabled;
                if (!isEnabled) {
                    checkbox.checked = false; // Desmarcar quando desabilitar
                }
                
                // Atualizar cor do label e descrição (nova estrutura aninhada)
                const containerDiv = checkbox.nextElementSibling;
                const labelElement = containerDiv?.querySelector('label');
                const descriptionElement = containerDiv?.querySelector('p');
                
                if (labelElement) {
                    labelElement.className = isEnabled 
                        ? labelElement.className.replace('text-gray-500', 'text-gray-400').replace('text-gray-400', 'text-gray-300')
                        : labelElement.className.replace('text-gray-300', 'text-gray-400').replace('text-gray-400', 'text-gray-500');
                }
                
                if (descriptionElement) {
                    descriptionElement.className = isEnabled 
                        ? descriptionElement.className.replace('text-gray-600', 'text-gray-500')
                        : descriptionElement.className.replace('text-gray-500', 'text-gray-600');
                }
            }
        });
        
        // Habilitar/desabilitar select de estratégia
        if (strategySelect) {
            strategySelect.disabled = !isEnabled;
            strategySelect.className = isEnabled
                ? strategySelect.className.replace('text-gray-400', 'text-white')
                : strategySelect.className.replace('text-white', 'text-gray-400');
        }
        
        // Alterar opacidade do container
        if (subOptionsContainer) {
            if (isEnabled) {
                subOptionsContainer.classList.remove('opacity-50');
                subOptionsContainer.classList.add('opacity-100');
            } else {
                subOptionsContainer.classList.remove('opacity-100');
                subOptionsContainer.classList.add('opacity-50');
            }
        }
    }

    validateSelections(showError = false) {
        const protestos = document.getElementById('protestos')?.checked || false;
        const receitaFederal = document.getElementById('receita-federal')?.checked || false;
        
        const isValid = protestos || receitaFederal;
        const warningElement = document.getElementById('validation-warning');
        
        if (!isValid) {
            if (warningElement) {
                warningElement.classList.remove('hidden');
            }
            if (showError) {
                this.showError('Por favor, selecione pelo menos uma opção de consulta (Protestos ou Receita Federal).');
            }
        } else {
            if (warningElement) {
                warningElement.classList.add('hidden');
            }
        }
        
        return isValid;
    }

    buildConsultationRequest(cnpj) {
        // Verificar se Receita Federal está habilitada
        const receitaFederalEnabled = document.getElementById('receita-federal')?.checked || false;
        
        // Coletar opções selecionadas
        const options = {
            cnpj: cnpj,
            api_key: 'rcp_dev-key-2', // Manter para compatibilidade
            
            // Dados jurídicos  
            protestos: document.getElementById('protestos')?.checked || false,
            
            // Dados da Receita Federal (só se a opção principal estiver habilitada)
            simples: receitaFederalEnabled ? (document.getElementById('simples')?.checked || false) : false,
            registrations: receitaFederalEnabled && document.getElementById('registrations')?.checked ? 'BR' : null,
            geocoding: receitaFederalEnabled ? (document.getElementById('geocoding')?.checked || false) : false,
            suframa: receitaFederalEnabled ? (document.getElementById('suframa')?.checked || false) : false,
            
            // Parâmetros de extração (sempre enviar quando Receita Federal está habilitada)
            extract_basic: receitaFederalEnabled,
            extract_address: receitaFederalEnabled,
            extract_contact: receitaFederalEnabled,
            extract_activities: receitaFederalEnabled,
            extract_partners: receitaFederalEnabled,
            
            // Configurações de cache (só se Receita Federal estiver habilitada)
            strategy: receitaFederalEnabled ? (document.getElementById('strategy')?.value || 'CACHE_IF_FRESH') : 'CACHE_IF_FRESH'
        };
        
        console.log('📤 Parâmetros da consulta:', {
            ...options,
            receita_federal_habilitada: receitaFederalEnabled
        });
        
        return options;
    }

    async consultarCNPJ(cnpj) {
        const cnpjLimpo = cnpj.replace(/[^\d]/g, '');
        const requestBody = this.buildConsultationRequest(cnpjLimpo);
        
        const response = await fetch('/api/v1/cnpj/consult', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer rcp_dev-key-2'
            },
            body: JSON.stringify(requestBody)
        });

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || data.error || `Erro ${response.status}: ${response.statusText}`);
        }
        
        if (data.success === false) {
            throw new Error(data.error || 'Erro na consulta');
        }

        return data;
    }

    exibirResultado(resultado) {
        const container = document.getElementById('resultado-container');
        const content = document.getElementById('resultado-content');
        const statusIndicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');

        // Mostrar container
        container.classList.remove('hidden');

        // Verificar se houve erro na consulta
        if (!resultado.success) {
            // Exibir erro
            statusIndicator.className = 'w-3 h-3 rounded-full bg-red-500';
            statusText.textContent = 'Erro na consulta';
            statusText.className = 'text-sm font-medium text-red-400';
            
            content.innerHTML = `
                <div class="bg-red-900/20 border border-red-500/30 rounded-lg p-4">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="material-icons text-red-400">error</span>
                        <h3 class="text-red-400 font-semibold">Erro na Consulta</h3>
                    </div>
                    <p class="text-red-200 text-sm">
                        ${resultado.error || 'Ocorreu um erro durante a consulta. Tente novamente.'}
                    </p>
                    <div class="mt-3 text-xs text-red-300">
                        <p><strong>CNPJ:</strong> ${resultado.cnpj || 'N/A'}</p>
                        <p><strong>Timestamp:</strong> ${resultado.timestamp || 'N/A'}</p>
                    </div>
                </div>
            `;
            return;
        }

        // Definir status de sucesso
        statusIndicator.className = 'w-3 h-3 rounded-full bg-green-500';
        statusText.textContent = 'Consulta realizada com sucesso';
        statusText.className = 'text-sm font-medium text-green-400';

        // Mostrar botão "Ver JSON"
        const btnViewJson = document.getElementById('btn-view-json');
        if (btnViewJson) {
            btnViewJson.classList.remove('hidden');
        }

        // Renderizar conteúdo unificado
        let contentHtml = '';
        
        // 1. Renderizar protestos se disponível
        if (resultado.protestos) {
            contentHtml += this.renderProtestosSection(resultado);
        }
        
        // 2. Renderizar dados da Receita Federal se disponível
        if (resultado.dados_receita) {
            contentHtml += this.renderDadosReceitaSection(resultado.dados_receita);
        }
        
        // 3. Renderizar metadados da consulta
        contentHtml += this.renderMetadadosSection(resultado);
        
        // 4. Se não há dados de nenhuma fonte
        if (!resultado.protestos && !resultado.dados_receita) {
            contentHtml = `
                <div class="bg-gray-800/20 border border-gray-500/30 rounded-lg p-4">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="material-icons text-gray-400">info</span>
                        <h3 class="text-gray-400 font-semibold">Nenhum Dado Encontrado</h3>
                    </div>
                    <p class="text-gray-300 text-sm">
                        Nenhuma fonte de dados retornou informações para este CNPJ. 
                        Verifique se o CNPJ está correto e tente novamente.
                    </p>
                </div>
            `;
        }

        content.innerHTML = contentHtml;

        // Calcular e exibir resumo se houver protestos (backward compatibility)
        if (resultado.protestos && resultado.has_protests) {
            console.log('🔍 Usando resultado.protestos para cálculo do resumo');
            this.calcularERenderizarResumo(resultado.protestos);
        }
    }

    renderResultadoContent(resultado) {
        console.log('🔍 Dados recebidos:', resultado);
        
        // Verificar se há dados e se tem protestos
        const temProtestos = resultado.data && resultado.data.has_protests;
        const totalProtestos = resultado.data ? resultado.data.total_protests : 0;
        const protestos = resultado.data ? resultado.data.protestos : null;
        
        console.log('📊 Análise dos dados:', {
            temProtestos,
            totalProtestos,
            protestos: protestos ? Object.keys(protestos) : 'N/A'
        });
        
        if (temProtestos && totalProtestos > 0) {
            return `
                <div class="space-y-4">
                    <div class="bg-yellow-900/20 border border-yellow-500/30 rounded-lg p-4">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="material-icons text-yellow-400">warning</span>
                            <h3 class="text-yellow-400 font-semibold">Protestos Encontrados</h3>
                        </div>
                        <p class="text-yellow-200 text-sm">
                            Foram encontrados ${totalProtestos} protesto(s) para este CNPJ.
                        </p>
                    </div>
                                     <!-- Resumo dos Protestos (inline) -->
                    <div id="summary-inline" class="bg-gray-800 rounded-lg p-6 border border-gray-600">
                        <h3 class="text-lg font-semibold text-white mb-6">Resumo dos Protestos</h3>
                        
                        <!-- Summary Cards Row -->
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                            <!-- Valor Total -->
                            <div class="bg-gray-700 border border-gray-600 rounded-lg p-4 hover:bg-gray-650 transition-colors">
                                <div class="flex items-center gap-3">
                                    <div class="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center">
                                        <span class="material-icons text-white text-lg">attach_money</span>
                                    </div>
                                    <div>
                                        <p class="text-gray-400 text-sm font-medium">VALOR TOTAL</p>
                                        <p id="valor-total-inline" class="text-white text-xl font-bold">R$ 0,00</p>
                                    </div>
                                </div>
                            </div>

                            <!-- Quantidade de Títulos -->
                            <div class="bg-gray-700 border border-gray-600 rounded-lg p-4 hover:bg-gray-650 transition-colors">
                                <div class="flex items-center gap-3">
                                    <div class="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center">
                                        <span class="material-icons text-white text-lg">description</span>
                                    </div>
                                    <div>
                                        <p class="text-gray-400 text-sm font-medium">QTD. TÍTULOS</p>
                                        <p id="qtd-titulos-inline" class="text-white text-xl font-bold">0</p>
                                    </div>
                                </div>
                            </div>

                            <!-- Valor Autorizado para Cancelar -->
                            <div class="bg-gray-700 border border-gray-600 rounded-lg p-4 hover:bg-gray-650 transition-colors">
                                <div class="flex items-center gap-3">
                                    <div class="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center">
                                        <span class="material-icons text-white text-lg">money</span>
                                    </div>
                                    <div>
                                        <p class="text-gray-400 text-sm font-medium">VALOR AUT. CANCELAR</p>
                                        <p id="valor-aut-cancelar-inline" class="text-white text-xl font-bold">R$ 0,00</p>
                                    </div>
                                </div>
                            </div>

                            <!-- Autorização para Cancelar -->
                            <div class="bg-gray-700 border border-gray-600 rounded-lg p-4 hover:bg-gray-650 transition-colors">
                                <div class="flex items-center gap-3">
                                    <div class="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center">
                                        <span class="material-icons text-white text-lg">check</span>
                                    </div>
                                    <div>
                                        <p class="text-gray-400 text-sm font-medium">AUT. CANCELAR</p>
                                        <p id="aut-cancelar-inline" class="text-white text-xl font-bold">0</p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Alert Box -->
                        <div id="alert-container-inline" class="bg-red-900/20 border border-red-500/30 rounded-lg p-4 hidden">
                            <div class="flex items-center gap-3">
                                <div class="w-8 h-8 bg-red-500 rounded-full flex items-center justify-center">
                                    <span class="material-icons text-white text-sm">warning</span>
                                </div>
                                <div>
                                    <p class="text-red-300 text-sm font-medium">VALOR SEM AUTORIZAÇÃO</p>
                                    <p id="valor-sem-autorizacao-inline" class="text-red-400 text-xl font-bold">R$ 0,00</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="space-y-3">
                        ${this.renderProtestosPorEstado(protestos)}
                    </div>
                </div>
            `;
        } else {
            return `
                <div class="bg-green-900/20 border border-green-500/30 rounded-lg p-4">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="material-icons text-green-400">check_circle</span>
                        <h3 class="text-green-400 font-semibold">Nenhum Protesto Encontrado</h3>
                    </div>
                    <p class="text-green-200 text-sm">
                        Este CNPJ não possui protestos registrados.
                    </p>
                </div>
            `;
        }
    }

    renderProtestosPorEstado(protestos) {
        if (!protestos) return '';
        
        let html = '';
        
        // Iterar pelos estados
        for (const [estado, cartorios] of Object.entries(protestos)) {
            html += `
                <div class="bg-gray-800 border border-gray-600 rounded-lg p-4">
                    <div class="flex items-center gap-2 mb-3">
                        <span class="material-icons text-blue-400">location_on</span>
                        <h4 class="text-blue-400 font-semibold">${estado}</h4>
                    </div>
                    
                    <div class="space-y-3">
                        ${cartorios.map(cartorio => `
                            <div class="bg-gray-700 border border-gray-500 rounded-lg p-4 hover:bg-gray-650 transition-colors">
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div class="space-y-3">
                                        <div>
                                            <span class="text-gray-400 text-sm font-medium">Cartório:</span>
                                            <p class="text-white font-semibold text-sm mt-1">${cartorio.cartorio || 'N/A'}</p>
                                        </div>
                                        <div>
                                            <span class="text-gray-400 text-sm font-medium">Cidade:</span>
                                            <p class="text-white font-medium text-sm mt-1">${cartorio.cidade || 'N/A'}</p>
                                        </div>
                                        <div>
                                            <span class="text-gray-400 text-sm font-medium">Quantidade de Títulos:</span>
                                            <p class="text-white font-medium text-sm mt-1">${cartorio.quantidadeTitulos || 'N/A'}</p>
                                        </div>
                                    </div>
                                    <div class="space-y-3">
                                        <div>
                                            <span class="text-gray-400 text-sm font-medium">Endereço:</span>
                                            <p class="text-white font-medium text-sm mt-1">${cartorio.endereco || 'N/A'}</p>
                                        </div>
                                        <div>
                                            <span class="text-gray-400 text-sm font-medium">Telefone:</span>
                                            <p class="text-white font-medium text-sm mt-1">${cartorio.telefone || 'N/A'}</p>
                                        </div>
                                    </div>
                                </div>
                                
                                ${cartorio.protestos && cartorio.protestos.length > 0 ? `
                                    <div class="mt-4 pt-4 border-t border-gray-600">
                                        <h5 class="text-white font-semibold mb-4 flex items-center gap-2">
                                            <span class="material-icons text-blue-400 text-sm">list</span>
                                            Detalhes dos Protestos
                                        </h5>
                                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                            ${cartorio.protestos.slice(0, 6).map(protesto => `
                                                <div class="bg-gray-600 border border-gray-500 rounded-lg p-3 hover:bg-gray-550 transition-colors">
                                                    <div class="flex items-center justify-between">
                                                        <div class="flex items-center gap-2">
                                                            <div class="w-6 h-6 bg-red-500 rounded-full flex items-center justify-center">
                                                                <span class="material-icons text-white text-xs">money</span>
                                                            </div>
                                                            <span class="text-gray-300 text-sm font-medium">Valor:</span>
                                                        </div>
                                                        <span class="text-white font-bold text-sm">${this.formatarMoeda(this.parseValor(protesto.valor))}</span>
                                                    </div>
                                                </div>
                                            `).join('')}
                                        </div>
                                        ${cartorio.protestos.length > 6 ? `
                                            <div class="mt-3 p-3 bg-gray-700 border border-gray-500 rounded-lg">
                                                <p class="text-gray-400 text-sm text-center">
                                                    <span class="material-icons text-gray-400 text-sm mr-1">more_horiz</span>
                                                    E mais ${cartorio.protestos.length - 6} protesto(s) não exibidos
                                                </p>
                                            </div>
                                        ` : ''}
                                    </div>
                                ` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        return html;
    }

    calcularERenderizarResumo(dados) {
        console.log('📊 Calculando resumo dos protestos:', dados);
        
        let valorTotal = 0;
        let qtdTitulos = 0;
        let valorAutorizadoCancelar = 0;
        let qtdAutorizadoCancelar = 0;
        
        // Acessar cenprotProtestos diretamente
        const cenprotProtestos = dados.cenprotProtestos;
        if (!cenprotProtestos) {
            console.warn('📊 Nenhum cenprotProtestos encontrado');
            return;
        }
        
        console.log('📊 cenprotProtestos encontrado:', cenprotProtestos);
        
        // Iterar pelos estados (BA, SP, etc.)
        for (const [estado, cartorios] of Object.entries(cenprotProtestos)) {
            console.log(`📊 Processando estado ${estado} com ${cartorios.length} cartórios`);
            
            if (Array.isArray(cartorios)) {
                for (const cartorio of cartorios) {
                    qtdTitulos += cartorio.quantidadeTitulos || 0;
                    console.log(`📊 Cartório: ${cartorio.cartorio || 'N/A'} - ${cartorio.quantidadeTitulos || 0} títulos`);
                    
                    // Verificar se há protestos individuais com valores
                    if (cartorio.protestos && Array.isArray(cartorio.protestos)) {
                        console.log(`📊 Encontrados ${cartorio.protestos.length} protestos com valores`);
                        
                        for (const protesto of cartorio.protestos) {
                            const valor = this.parseValor(protesto.valor);
                            valorTotal += valor;
                            
                            // Verificar autorização para cancelar
                            if (protesto.autorizacaoCancelamento) {
                                valorAutorizadoCancelar += valor;
                                qtdAutorizadoCancelar++;
                            }
                        }
                    } else {
                        console.log(`📊 Cartório ${cartorio.cartorio} não possui protestos detalhados`);
                    }
                }
            }
        }
        
        const valorSemAutorizacao = valorTotal - valorAutorizadoCancelar;
        
        console.log('📈 Resumo calculado:', {
            valorTotal,
            qtdTitulos,
            valorAutorizadoCancelar,
            qtdAutorizadoCancelar,
            valorSemAutorizacao
        });
        
        // Atualizar elementos do resumo inline
        const valorTotalEl = document.getElementById('valor-total-inline');
        const qtdTitulosEl = document.getElementById('qtd-titulos-inline');
        const valorAutCancelarEl = document.getElementById('valor-aut-cancelar-inline');
        const autCancelarEl = document.getElementById('aut-cancelar-inline');
        const alertContainerEl = document.getElementById('alert-container-inline');
        const valorSemAutorizacaoEl = document.getElementById('valor-sem-autorizacao-inline');
        
        if (valorTotalEl) valorTotalEl.textContent = this.formatarMoeda(valorTotal);
        if (qtdTitulosEl) qtdTitulosEl.textContent = qtdTitulos.toString();
        if (valorAutCancelarEl) valorAutCancelarEl.textContent = this.formatarMoeda(valorAutorizadoCancelar);
        if (autCancelarEl) autCancelarEl.textContent = qtdAutorizadoCancelar.toString();
        
        // Mostrar alerta se houver valor sem autorização
        if (valorSemAutorizacao > 0) {
            if (valorSemAutorizacaoEl) valorSemAutorizacaoEl.textContent = this.formatarMoeda(valorSemAutorizacao);
            if (alertContainerEl) alertContainerEl.classList.remove('hidden');
        } else {
            if (alertContainerEl) alertContainerEl.classList.add('hidden');
        }
    }

    parseValor(valorStr) {
        if (!valorStr) return 0;
        
        // Remover "R$" e espaços, substituir vírgula por ponto
        const valorLimpo = valorStr.replace(/R\$\s?/g, '').replace(/\./g, '').replace(',', '.');
        const valor = parseFloat(valorLimpo);
        
        return isNaN(valor) ? 0 : valor;
    }

    formatarMoeda(valor) {
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        }).format(valor);
    }

    exibirErro(mensagem) {
        const container = document.getElementById('resultado-container');
        const content = document.getElementById('resultado-content');
        const statusIndicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');

        // Mostrar container
        container.classList.remove('hidden');

        // Definir status de erro
        statusIndicator.className = 'w-3 h-3 rounded-full bg-red-500';
        statusText.textContent = 'Erro na consulta';
        statusText.className = 'text-sm font-medium text-red-400';

        // Renderizar erro
        content.innerHTML = `
            <div class="bg-red-900/20 border border-red-500/30 rounded-lg p-4">
                <div class="flex items-center gap-2 mb-2">
                    <span class="material-icons text-red-400">error</span>
                    <h3 class="text-red-400 font-semibold">Erro na Consulta</h3>
                </div>
                <p class="text-red-200 text-sm">${mensagem}</p>
            </div>
        `;
    }


    limparFormulario() {
        // Limpar campo CNPJ
        document.getElementById('cnpj').value = '';
        
        // Ocultar resultado
        document.getElementById('resultado-container').classList.add('hidden');
        
        // Ocultar botão JSON
        const btnViewJson = document.getElementById('btn-view-json');
        if (btnViewJson) {
            btnViewJson.classList.add('hidden');
        }
        
        // Resetar checkboxes para estado padrão
        document.getElementById('protestos').checked = true;
        document.getElementById('receita-federal').checked = false;
        
        // Desabilitar subopções da Receita Federal
        this.toggleReceitaFederalOptions();
        
        // Ocultar aviso de validação
        const warningElement = document.getElementById('validation-warning');
        if (warningElement) {
            warningElement.classList.add('hidden');
        }
        
        // Limpar último resultado
        this.lastResult = null;
    }

    formatarCNPJ(event) {
        let value = event.target.value.replace(/\D/g, '');
        
        if (value.length <= 14) {
            value = value.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5');
            event.target.value = value;
        }
    }

    validarCNPJ(cnpj) {
        const cnpjLimpo = cnpj.replace(/\D/g, '');
        
        if (cnpjLimpo.length !== 14) return false;
        
        // Verificar se todos os dígitos são iguais
        if (/^(\d)\1+$/.test(cnpjLimpo)) return false;
        
        // Algoritmo de validação do CNPJ
        let soma = 0;
        let peso = 2;
        
        for (let i = 11; i >= 0; i--) {
            soma += parseInt(cnpjLimpo.charAt(i)) * peso;
            peso = peso === 9 ? 2 : peso + 1;
        }
        
        let resto = soma % 11;
        let digito1 = resto < 2 ? 0 : 11 - resto;
        
        if (parseInt(cnpjLimpo.charAt(12)) !== digito1) return false;
        
        soma = 0;
        peso = 2;
        
        for (let i = 12; i >= 0; i--) {
            soma += parseInt(cnpjLimpo.charAt(i)) * peso;
            peso = peso === 9 ? 2 : peso + 1;
        }
        
        resto = soma % 11;
        let digito2 = resto < 2 ? 0 : 11 - resto;
        
        return parseInt(cnpjLimpo.charAt(13)) === digito2;
    }

    formatarDataHora(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleString('pt-BR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    showLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.remove('hidden');
        }
    }

    hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.add('hidden');
        }
    }

    showError(message) {
        console.error('❌', message);
        alert(`Erro: ${message}`);
    }

    showJsonModal() {
        if (!this.lastResult) {
            this.showError('Nenhum resultado disponível para visualizar.');
            return;
        }
        
        const modal = document.getElementById('json-modal');
        const jsonContent = document.getElementById('json-content');
        
        if (modal && jsonContent) {
            // Formatar JSON com indentação
            const formattedJson = JSON.stringify(this.lastResult, null, 2);
            jsonContent.textContent = formattedJson;
            
            // Mostrar modal
            modal.classList.remove('hidden');
            
            // Focar no conteúdo JSON para facilitar seleção
            jsonContent.focus();
        }
    }
    
    hideJsonModal() {
        const modal = document.getElementById('json-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
    }
    
    async copyJsonToClipboard() {
        if (!this.lastResult) {
            this.showError('Nenhum resultado disponível para copiar.');
            return;
        }
        
        try {
            const formattedJson = JSON.stringify(this.lastResult, null, 2);
            await navigator.clipboard.writeText(formattedJson);
            
            // Feedback visual
            const btnCopy = document.getElementById('btn-copy-json');
            if (btnCopy) {
                const originalText = btnCopy.innerHTML;
                btnCopy.innerHTML = '<span class="material-icons text-sm">check</span>Copiado!';
                btnCopy.classList.remove('bg-blue-600', 'hover:bg-blue-700');
                btnCopy.classList.add('bg-green-600');
                
                setTimeout(() => {
                    btnCopy.innerHTML = originalText;
                    btnCopy.classList.remove('bg-green-600');
                    btnCopy.classList.add('bg-blue-600', 'hover:bg-blue-700');
                }, 2000);
            }
        } catch (error) {
            console.error('Erro ao copiar JSON:', error);
            this.showError('Erro ao copiar JSON para a área de transferência.');
        }
    }

    renderProtestosSection(resultado) {
        const temProtestos = resultado.has_protests;
        const totalProtestos = resultado.total_protests || 0;
        const protestos = resultado.protestos?.cenprotProtestos;
        
        if (temProtestos && totalProtestos > 0) {
            return `
                <div class="space-y-4 mb-6">
                    <div class="bg-yellow-900/20 border border-yellow-500/30 rounded-lg p-4">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="material-icons text-yellow-400">warning</span>
                            <h3 class="text-yellow-400 font-semibold">Protestos Encontrados</h3>
                        </div>
                        <p class="text-yellow-200 text-sm">
                            Foram encontrados ${totalProtestos} protesto(s) para este CNPJ.
                        </p>
                    </div>
                    
                    <!-- Resumo dos Protestos (inline) -->
                    <div id="summary-inline" class="bg-gray-800 rounded-lg p-6 border border-gray-600">
                        <h3 class="text-lg font-semibold text-white mb-6">Resumo dos Protestos</h3>
                        
                        <!-- Summary Cards Row -->
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                            <!-- Valor Total -->
                            <div class="bg-gray-700 border border-gray-600 rounded-lg p-4 hover:bg-gray-650 transition-colors">
                                <div class="flex items-center gap-3">
                                    <div class="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center">
                                        <span class="material-icons text-white text-lg">attach_money</span>
                                    </div>
                                    <div>
                                        <p class="text-gray-400 text-sm font-medium">VALOR TOTAL</p>
                                        <p id="valor-total-inline" class="text-white text-xl font-bold">R$ 0,00</p>
                                    </div>
                                </div>
                            </div>

                            <!-- Quantidade de Títulos -->
                            <div class="bg-gray-700 border border-gray-600 rounded-lg p-4 hover:bg-gray-650 transition-colors">
                                <div class="flex items-center gap-3">
                                    <div class="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center">
                                        <span class="material-icons text-white text-lg">description</span>
                                    </div>
                                    <div>
                                        <p class="text-gray-400 text-sm font-medium">QTD. TÍTULOS</p>
                                        <p id="qtd-titulos-inline" class="text-white text-xl font-bold">0</p>
                                    </div>
                                </div>
                            </div>

                            <!-- Valor Autorizado para Cancelar -->
                            <div class="bg-gray-700 border border-gray-600 rounded-lg p-4 hover:bg-gray-650 transition-colors">
                                <div class="flex items-center gap-3">
                                    <div class="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center">
                                        <span class="material-icons text-white text-lg">money</span>
                                    </div>
                                    <div>
                                        <p class="text-gray-400 text-sm font-medium">VALOR AUT. CANCELAR</p>
                                        <p id="valor-aut-cancelar-inline" class="text-white text-xl font-bold">R$ 0,00</p>
                                    </div>
                                </div>
                            </div>

                            <!-- Autorização para Cancelar -->
                            <div class="bg-gray-700 border border-gray-600 rounded-lg p-4 hover:bg-gray-650 transition-colors">
                                <div class="flex items-center gap-3">
                                    <div class="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center">
                                        <span class="material-icons text-white text-lg">check</span>
                                    </div>
                                    <div>
                                        <p class="text-gray-400 text-sm font-medium">AUT. CANCELAR</p>
                                        <p id="aut-cancelar-inline" class="text-white text-xl font-bold">0</p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Alert Box -->
                        <div id="alert-container-inline" class="bg-red-900/20 border border-red-500/30 rounded-lg p-4 hidden">
                            <div class="flex items-center gap-3">
                                <div class="w-8 h-8 bg-red-500 rounded-full flex items-center justify-center">
                                    <span class="material-icons text-white text-sm">warning</span>
                                </div>
                                <div>
                                    <p class="text-red-300 text-sm font-medium">VALOR SEM AUTORIZAÇÃO</p>
                                    <p id="valor-sem-autorizacao-inline" class="text-red-400 text-xl font-bold">R$ 0,00</p>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="space-y-3">
                        ${this.renderProtestosPorEstado(protestos)}
                    </div>
                </div>
            `;
        } else {
            return `
                <div class="bg-green-900/20 border border-green-500/30 rounded-lg p-4 mb-6">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="material-icons text-green-400">check_circle</span>
                        <h3 class="text-green-400 font-semibold">Nenhum Protesto Encontrado</h3>
                    </div>
                    <p class="text-green-200 text-sm">
                        Este CNPJ não possui protestos registrados.
                    </p>
                </div>
            `;
        }
    }

    renderDadosReceitaSection(dadosReceita) {
        if (!dadosReceita) return '';
        
        let html = '<div class="space-y-4 mb-6">';
        html += '<h3 class="text-lg font-semibold text-white flex items-center gap-2 mb-4">';
        html += '<span class="material-icons text-blue-400">business</span>';
        html += 'Dados da Receita Federal</h3>';
        
        // Dados básicos
        if (dadosReceita.basico) {
            const basico = dadosReceita.basico;
            html += `
            <div class="bg-gray-800 border border-gray-600 rounded-lg p-4">
                <h4 class="text-md font-semibold text-white mb-3 flex items-center gap-2">
                    <span class="material-icons text-green-400 text-sm">info</span>
                    Informações Básicas
                </h4>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                    <div><span class="text-gray-400">Razão Social:</span> <span class="text-white font-medium">${basico.razao_social || 'N/A'}</span></div>
                    <div><span class="text-gray-400">Nome Fantasia:</span> <span class="text-white font-medium">${basico.nome_fantasia || 'N/A'}</span></div>
                    <div><span class="text-gray-400">Situação:</span> <span class="text-white font-medium">${basico.situacao || 'N/A'}</span></div>
                    <div><span class="text-gray-400">Porte:</span> <span class="text-white font-medium">${basico.porte || 'N/A'}</span></div>
                    <div><span class="text-gray-400">Capital Social:</span> <span class="text-white font-medium">${this.formatarMoeda(basico.capital_social || 0)}</span></div>
                    <div><span class="text-gray-400">Data Fundação:</span> <span class="text-white font-medium">${basico.data_fundacao || 'N/A'}</span></div>
                </div>
            </div>`;
        }
        
        // Endereço com geolocalização
        if (dadosReceita.endereco) {
            const endereco = dadosReceita.endereco;
            html += `
            <div class="bg-gray-800 border border-gray-600 rounded-lg p-4">
                <h4 class="text-md font-semibold text-white mb-3 flex items-center gap-2">
                    <span class="material-icons text-blue-400 text-sm">location_on</span>
                    Endereço ${endereco.latitude ? '(com geolocalização)' : ''}
                </h4>
                <div class="text-sm">
                    <p class="text-white">${endereco.logradouro || ''} ${endereco.numero || ''}</p>
                    <p class="text-gray-300">${endereco.bairro || ''} - ${endereco.cidade || ''} - ${endereco.uf || ''}</p>
                    <p class="text-gray-300">CEP: ${endereco.cep || 'N/A'}</p>
                    ${endereco.latitude ? `<p class="text-green-400 text-xs mt-2">📍 Lat: ${endereco.latitude}, Long: ${endereco.longitude}</p>` : ''}
                </div>
            </div>`;
        }
        
        // Simples Nacional
        if (dadosReceita.simples) {
            const simples = dadosReceita.simples;
            html += `
            <div class="bg-gray-800 border border-gray-600 rounded-lg p-4">
                <h4 class="text-md font-semibold text-white mb-3 flex items-center gap-2">
                    <span class="material-icons text-yellow-400 text-sm">business_center</span>
                    Simples Nacional / SIMEI
                </h4>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                    <div>
                        <span class="text-gray-400">Simples Nacional:</span> 
                        <span class="text-white font-medium">${simples.simples_nacional?.optante ? 'SIM' : 'NÃO'}</span>
                        ${simples.simples_nacional?.data_opcao ? `<span class="text-gray-400 ml-2">(desde ${simples.simples_nacional.data_opcao})</span>` : ''}
                    </div>
                    <div>
                        <span class="text-gray-400">SIMEI:</span> 
                        <span class="text-white font-medium">${simples.simei?.optante ? 'SIM' : 'NÃO'}</span>
                        ${simples.simei?.data_opcao ? `<span class="text-gray-400 ml-2">(desde ${simples.simei.data_opcao})</span>` : ''}
                    </div>
                </div>
            </div>`;
        }
        
        // Inscrições Estaduais  
        if (dadosReceita.registros_estaduais && dadosReceita.registros_estaduais.length > 0) {
            html += `
            <div class="bg-gray-800 border border-gray-600 rounded-lg p-4">
                <h4 class="text-md font-semibold text-white mb-3 flex items-center gap-2">
                    <span class="material-icons text-purple-400 text-sm">assignment</span>
                    Inscrições Estaduais
                </h4>
                <div class="space-y-2">`;
            
            dadosReceita.registros_estaduais.forEach(registro => {
                const statusClass = registro.ativo ? 'text-green-400' : 'text-red-400';
                html += `
                    <div class="flex items-center justify-between p-2 bg-gray-700 rounded text-sm">
                        <div>
                            <span class="text-white font-medium">${registro.uf}</span>
                            <span class="text-gray-400 ml-2">${registro.numero}</span>
                        </div>
                        <span class="${statusClass} font-medium">${registro.ativo ? 'ATIVO' : 'INATIVO'}</span>
                    </div>`;
            });
            
            html += '</div></div>';
        }
        
        // SUFRAMA
        if (dadosReceita.suframa && dadosReceita.suframa.length > 0) {
            html += `
            <div class="bg-gray-800 border border-gray-600 rounded-lg p-4">
                <h4 class="text-md font-semibold text-white mb-3 flex items-center gap-2">
                    <span class="material-icons text-orange-400 text-sm">local_shipping</span>
                    SUFRAMA
                </h4>
                <div class="space-y-3">`;
            
            dadosReceita.suframa.forEach(suframa => {
                html += `
                    <div class="p-3 bg-gray-700 rounded">
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-white font-medium">Registro: ${suframa.numero}</span>
                            <span class="text-sm ${suframa.aprovado ? 'text-green-400' : 'text-yellow-400'}">
                                ${suframa.status?.texto || 'N/A'}
                            </span>
                        </div>
                        ${suframa.incentivos && suframa.incentivos.length > 0 ? `
                            <div class="text-xs text-gray-300 mt-2">
                                <strong>Incentivos:</strong> ${suframa.incentivos.length} incentivo(s) fiscal(is)
                            </div>
                        ` : ''}
                    </div>`;
            });
            
            html += '</div></div>';
        }
        
        html += '</div>';
        return html;
    }

    renderMetadadosSection(resultado) {
        if (!resultado.sources_consulted || resultado.sources_consulted.length === 0) {
            return '';
        }
        
        return `
            <div class="mt-6 bg-gray-800 border border-gray-600 rounded-lg p-4">
                <h4 class="text-sm font-semibold text-gray-400 mb-3 flex items-center gap-2">
                    <span class="material-icons text-sm">info</span>
                    Metadados da Consulta
                </h4>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div class="flex flex-col">
                        <span class="text-gray-500 mb-1">Fontes:</span> 
                        <span class="text-gray-300 font-medium">${resultado.sources_consulted.join(', ')}</span>
                    </div>
                    <div class="flex flex-col">
                        <span class="text-gray-500 mb-1">Cache:</span> 
                        <span class="text-gray-300 font-medium">${resultado.cache_used ? 'Usado' : 'Não usado'}</span>
                    </div>
                    <div class="flex flex-col">
                        <span class="text-gray-500 mb-1">Tempo:</span> 
                        <span class="text-gray-300 font-medium">${resultado.response_time_ms || 0}ms</span>
                    </div>
                    <div class="flex flex-col">
                        <span class="text-gray-500 mb-1">Timestamp:</span> 
                        <span class="text-gray-300 font-medium">${new Date(resultado.timestamp).toLocaleTimeString()}</span>
                    </div>
                </div>
            </div>`;
    }
}

// Inicializar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
    new ConsultasManager();
});

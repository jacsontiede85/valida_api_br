/**
 * JavaScript para a página de documentação da API
 * Gerencia navegação por abas, playground interativo e funcionalidades da documentação
 */

// Global variables
let apiData = null;
let currentTab = 'overview';
let currentLang = 'javascript';

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    loadApiData();
    setupEventListeners();
});

// Load API data
async function loadApiData() {
    try {
        // Verificar se há token de autenticação
        const authToken = localStorage.getItem('auth_token') || localStorage.getItem('session_token');
        
        let response;
        
        if (authToken) {
            console.log('🔐 Token encontrado, tentando endpoint autenticado');
            try {
                response = await fetch('/documentation/api-data/authenticated', {
                    headers: {
                        'Authorization': `Bearer ${authToken}`,
                        'Content-Type': 'application/json'
                    }
                });
                
                if (response.ok) {
                    console.log('✅ Dados autenticados carregados com sucesso');
                } else {
                    console.log(`⚠️ Erro ${response.status} no endpoint autenticado, usando público`);
                    response = await fetch('/documentation/api-data');
                }
            } catch (authError) {
                console.log('⚠️ Erro na autenticação, usando endpoint público:', authError.message);
                response = await fetch('/documentation/api-data');
            }
        } else {
            console.log('👤 Nenhum token encontrado, usando endpoint público');
            response = await fetch('/documentation/api-data');
        }
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        apiData = await response.json();

        // Populate API key select
        populateApiKeySelect();

        // Populate parameters
        populateParameters();

        // Populate response example
        populateResponseExample();

        // Populate code examples
        populateCodeExamples();

        // Populate error codes
        populateErrorCodes();

        // Load pricing table from database
        await loadPricingTable();

    } catch (error) {
        console.error('Erro ao carregar dados da API:', error);
        // Fallback para dados básicos
        apiData = {
            endpoints: [],
            error_codes: {},
            rate_limits: {},
            user_api_keys: []
        };
    }
}

// Setup event listeners
function setupEventListeners() {
    // Tab navigation
    document.querySelectorAll('[data-tab]').forEach(button => {
        button.addEventListener('click', function() {
            switchTab(this.dataset.tab);
        });
    });

    // Language selection
    document.querySelectorAll('[data-lang]').forEach(button => {
        button.addEventListener('click', function() {
            switchLanguage(this.dataset.lang);
        });
    });

    // Playground test button
    const testButton = document.getElementById('test-api');
    if (testButton) {
        testButton.addEventListener('click', testApi);
    }

    // Toggle advanced options
    const toggleAdvanced = document.getElementById('toggle-advanced');
    if (toggleAdvanced) {
        toggleAdvanced.addEventListener('click', function() {
            const advanced = document.getElementById('advanced-options');
            const icon = this.querySelector('.material-icons');
            
            if (advanced.classList.contains('hidden')) {
                advanced.classList.remove('hidden');
                icon.textContent = 'expand_less';
            } else {
                advanced.classList.add('hidden');
                icon.textContent = 'expand_more';
            }
        });
    }
}

// Switch tabs
function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('[data-tab]').forEach(btn => {
        btn.classList.remove('bg-blue-600', 'text-white');
        btn.classList.add('text-gray-400', 'hover:text-white', 'hover:bg-gray-700');
    });
    
    const activeButton = document.querySelector(`[data-tab="${tabName}"]`);
    if (activeButton) {
        activeButton.classList.remove('text-gray-400', 'hover:text-white', 'hover:bg-gray-700');
        activeButton.classList.add('bg-blue-600', 'text-white');
    }

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.add('hidden');
    });
    
    const activeTab = document.getElementById(`${tabName}-tab`);
    if (activeTab) {
        activeTab.classList.remove('hidden');
        activeTab.classList.add('fade-in');
    }
    
    currentTab = tabName;
}

// Switch language
function switchLanguage(langName) {
    // Update language buttons
    document.querySelectorAll('[data-lang]').forEach(btn => {
        btn.classList.remove('bg-blue-600', 'text-white');
        btn.classList.add('text-gray-400', 'hover:text-white', 'hover:bg-gray-700');
    });
    
    const activeButton = document.querySelector(`[data-lang="${langName}"]`);
    if (activeButton) {
        activeButton.classList.remove('text-gray-400', 'hover:text-white', 'hover:bg-gray-700');
        activeButton.classList.add('bg-blue-600', 'text-white');
    }

    currentLang = langName;
    populateCodeExamples();
}

// Populate API key select
function populateApiKeySelect() {
    const select = document.getElementById('api-key-select');
    if (!select) return;
    
    select.innerHTML = '<option value="">Selecionar API Key...</option>';
    
    if (apiData && apiData.user_api_keys && apiData.user_api_keys.length > 0) {
        apiData.user_api_keys.forEach(key => {
            const option = document.createElement('option');
            option.value = key.key;
            option.textContent = `${key.name} (${key.key.substring(0, 20)}...)`;
            select.appendChild(option);
        });
    } else {
        // Adicionar opção informativa quando não há API keys
        const option = document.createElement('option');
        option.value = "";
        option.textContent = "Nenhuma API Key encontrada - Faça login para ver suas chaves";
        option.disabled = true;
        select.appendChild(option);
    }
}

// Populate parameters
function populateParameters() {
    if (!apiData || !apiData.endpoints) return;
    
    const endpoint = apiData.endpoints[0];
    const container = document.getElementById('parameters-list');
    if (!container) return;
    
    container.innerHTML = '';

    // Separar parâmetros obrigatórios e opcionais
    const requiredParams = [];
    const optionalParams = [];
    
    Object.entries(endpoint.parameters).forEach(([name, param]) => {
        if (param.required) {
            requiredParams.push([name, param]);
        } else {
            optionalParams.push([name, param]);
        }
    });

    // Renderizar parâmetros obrigatórios
    if (requiredParams.length > 0) {
        const requiredSection = document.createElement('div');
        requiredSection.className = 'mb-8';
        requiredSection.innerHTML = `
            <div class="flex items-center mb-4">
                <div class="w-8 h-8 bg-gradient-to-r from-red-400 to-pink-500 rounded-lg flex items-center justify-center mr-3">
                    <span class="material-icons text-white text-sm">priority_high</span>
                </div>
                <div>
                    <h4 class="text-lg font-semibold text-white">Parâmetros Obrigatórios</h4>
                    <p class="text-gray-400 text-sm">Estes parâmetros são necessários para a requisição</p>
                </div>
            </div>
        `;
        
        const requiredContainer = document.createElement('div');
        requiredContainer.className = 'space-y-4';
        
        requiredParams.forEach(([name, param]) => {
            requiredContainer.appendChild(createParameterCard(name, param, true));
        });
        
        requiredSection.appendChild(requiredContainer);
        container.appendChild(requiredSection);
    }

    // Renderizar parâmetros opcionais
    if (optionalParams.length > 0) {
        const optionalSection = document.createElement('div');
        optionalSection.className = 'mb-8';
        optionalSection.innerHTML = `
            <div class="flex items-center mb-4">
                <div class="w-8 h-8 bg-gradient-to-r from-blue-400 to-cyan-500 rounded-lg flex items-center justify-center mr-3">
                    <span class="material-icons text-white text-sm">settings</span>
                </div>
                <div>
                    <h4 class="text-lg font-semibold text-white">Parâmetros Opcionais</h4>
                    <p class="text-gray-400 text-sm">Configure conforme suas necessidades</p>
                </div>
            </div>
        `;
        
        const optionalContainer = document.createElement('div');
        optionalContainer.className = 'space-y-4';
        
        optionalParams.forEach(([name, param]) => {
            optionalContainer.appendChild(createParameterCard(name, param, false));
        });
        
        optionalSection.appendChild(optionalContainer);
        container.appendChild(optionalSection);
    }
}

// Create parameter card
function createParameterCard(name, param, isRequired) {
    const card = document.createElement('div');
    card.className = 'bg-gray-700 border border-gray-600 rounded-xl p-5 hover:border-gray-500 transition-colors';
    
    const typeColor = isRequired ? 'bg-red-500/20 text-red-400' : 'bg-blue-500/20 text-blue-400';
    const requiredBadge = isRequired ? '<span class="text-xs px-2 py-1 rounded bg-red-500/20 text-red-400 font-medium">Obrigatório</span>' : '<span class="text-xs px-2 py-1 rounded bg-gray-500/20 text-gray-400 font-medium">Opcional</span>';
    
    card.innerHTML = `
        <div class="flex justify-between items-start mb-3">
            <div class="flex items-center space-x-3">
                <code class="text-blue-400 font-mono text-lg font-semibold">${name}</code>
                <span class="text-xs px-2 py-1 rounded ${typeColor} font-medium">
                    ${param.type}
                </span>
                ${requiredBadge}
            </div>
        </div>
        
        <p class="text-gray-300 text-sm mb-3 leading-relaxed">${param.description}</p>
        
        <div class="space-y-2">
            ${param.default ? `
                <div class="flex items-center text-xs">
                    <span class="material-icons text-gray-500 mr-2 text-sm">settings</span>
                    <span class="text-gray-400">Padrão:</span>
                    <code class="text-green-400 ml-2 font-mono">${param.default}</code>
                </div>
            ` : ''}
            
            ${param.example ? `
                <div class="flex items-center text-xs">
                    <span class="material-icons text-gray-500 mr-2 text-sm">lightbulb</span>
                    <span class="text-gray-400">Exemplo:</span>
                    <code class="text-yellow-400 ml-2 font-mono">${param.example}</code>
                </div>
            ` : ''}
            
            ${param.options ? `
                <div class="mt-3">
                    <div class="flex items-center mb-2">
                        <span class="material-icons text-gray-500 mr-2 text-sm">list</span>
                        <span class="text-gray-400 text-xs font-medium">Opções disponíveis:</span>
                    </div>
                    <div class="bg-gray-800 rounded-lg p-3 space-y-1">
                        ${Object.entries(param.options).map(([key, value]) => `
                            <div class="flex items-start text-xs">
                                <code class="text-blue-400 font-mono mr-2 min-w-0 flex-shrink-0">${key}</code>
                                <span class="text-gray-300">${value}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            ` : ''}
        </div>
    `;
    
    return card;
}

// Populate response example
function populateResponseExample() {
    if (!apiData || !apiData.endpoints) return;
    
    const endpoint = apiData.endpoints[0];
    const container = document.getElementById('response-example');
    if (!container) return;
    
    const exampleResponse = {
        "success": true,
        "cnpj": "12345678000195",
        "has_protests": false,
        "total_protests": 0,
        "protestos": [],
        "dados_receita": {
            "razao_social": "Empresa Exemplo LTDA",
            "nome_fantasia": "Empresa Exemplo",
            "situacao": "ATIVA",
            "endereco": {
                "logradouro": "Rua Exemplo, 123",
                "bairro": "Centro",
                "cidade": "São Paulo",
                "uf": "SP",
                "cep": "01234-567"
            },
            "contatos": {
                "telefone": "(11) 1234-5678",
                "email": "contato@empresa.com"
            },
            "atividades": [
                {
                    "codigo": "6201-5/00",
                    "descricao": "Desenvolvimento de programas de computador sob encomenda"
                }
            ],
            "socios": [
                {
                    "nome": "João Silva",
                    "cpf": "123.456.789-00",
                    "qualificacao": "Administrador"
                }
            ]
        },
        "cache_used": true,
        "response_time_ms": 1250,
        "timestamp": "2025-01-25T10:30:00Z"
    };
    
    container.innerHTML = `
        <div class="space-y-4">
            <!-- Response Status -->
            <div class="flex items-center justify-between p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
                <div class="flex items-center">
                    <span class="material-icons text-green-400 mr-2">check_circle</span>
                    <span class="text-green-400 font-semibold">Resposta de Sucesso (200)</span>
                </div>
                <div class="text-sm text-gray-400">
                    Content-Type: application/json
                </div>
            </div>
            
            <!-- Response Body -->
            <div class="bg-gray-900 rounded-xl p-6 relative">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center">
                        <span class="material-icons text-gray-400 mr-2 text-sm">code</span>
                        <span class="text-gray-300 text-sm font-medium">Corpo da Resposta</span>
                    </div>
                    <button class="copy-btn" onclick="copyToClipboard('response-json')">
                        <span class="material-icons text-sm">content_copy</span>
                    </button>
                </div>
                
                <pre class="text-sm overflow-x-auto"><code id="response-json" class="language-json">${JSON.stringify(exampleResponse, null, 2)}</code></pre>
            </div>
            
            <!-- Response Fields Description -->
            <div class="bg-gray-700 rounded-xl p-6">
                <div class="flex items-center mb-4">
                    <span class="material-icons text-gray-400 mr-2 text-sm">info</span>
                    <span class="text-gray-300 text-sm font-medium">Campos da Resposta</span>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div class="space-y-2">
                        <div class="flex items-start">
                            <code class="text-blue-400 font-mono mr-2 min-w-0 flex-shrink-0">success</code>
                            <span class="text-gray-300">Indica se a consulta foi bem-sucedida</span>
                        </div>
                        <div class="flex items-start">
                            <code class="text-blue-400 font-mono mr-2 min-w-0 flex-shrink-0">cnpj</code>
                            <span class="text-gray-300">CNPJ consultado (apenas números)</span>
                        </div>
                        <div class="flex items-start">
                            <code class="text-blue-400 font-mono mr-2 min-w-0 flex-shrink-0">has_protests</code>
                            <span class="text-gray-300">Indica se foram encontrados protestos</span>
                        </div>
                        <div class="flex items-start">
                            <code class="text-blue-400 font-mono mr-2 min-w-0 flex-shrink-0">total_protests</code>
                            <span class="text-gray-300">Número total de protestos encontrados</span>
                        </div>
                    </div>
                    
                    <div class="space-y-2">
                        <div class="flex items-start">
                            <code class="text-blue-400 font-mono mr-2 min-w-0 flex-shrink-0">dados_receita</code>
                            <span class="text-gray-300">Dados completos da Receita Federal</span>
                        </div>
                        <div class="flex items-start">
                            <code class="text-blue-400 font-mono mr-2 min-w-0 flex-shrink-0">cache_used</code>
                            <span class="text-gray-300">Indica se foi usado cache</span>
                        </div>
                        <div class="flex items-start">
                            <code class="text-blue-400 font-mono mr-2 min-w-0 flex-shrink-0">response_time_ms</code>
                            <span class="text-gray-300">Tempo de resposta em milissegundos</span>
                        </div>
                        <div class="flex items-start">
                            <code class="text-blue-400 font-mono mr-2 min-w-0 flex-shrink-0">timestamp</code>
                            <span class="text-gray-300">Timestamp da consulta (ISO 8601)</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Highlight syntax
    if (typeof Prism !== 'undefined') {
        Prism.highlightAll();
    }
}

// Populate code examples
function populateCodeExamples() {
    if (!apiData || !apiData.endpoints) return;
    
    const endpoint = apiData.endpoints[0];
    const container = document.getElementById('code-examples');
    if (!container) return;
    
    const example = endpoint.examples[currentLang];
    if (example) {
        container.innerHTML = `
            <div class="bg-gray-800 border border-gray-700 rounded-lg p-6">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-semibold">${example.description}</h3>
                    <button class="copy-btn" onclick="copyToClipboard('code-example')">
                        <span class="material-icons text-sm">content_copy</span>
                    </button>
                </div>
                <div class="bg-gray-900 p-4 rounded-lg">
                    <pre><code id="code-example" class="language-${currentLang === 'curl' ? 'bash' : currentLang}">${example.code}</code></pre>
                </div>
            </div>
        `;
        
        // Highlight syntax
        if (typeof Prism !== 'undefined') {
            Prism.highlightAll();
        }
    }
}

// Populate error codes
function populateErrorCodes() {
    if (!apiData || !apiData.error_codes) return;
    
    const container = document.getElementById('error-codes-list');
    if (!container) return;
    
    container.innerHTML = '';

    Object.entries(apiData.error_codes).forEach(([code, error]) => {
        const card = document.createElement('div');
        card.className = 'bg-gray-800 border border-gray-700 rounded-lg p-6 mb-4';
        
        card.innerHTML = `
            <div class="flex items-center justify-between mb-3">
                <h3 class="text-lg font-semibold">
                    <span class="bg-red-500 text-white px-2 py-1 rounded text-sm font-mono mr-3">${code}</span>
                    ${error.description}
                </h3>
            </div>
            <div class="space-y-2">
                ${error.examples.map(example => 
                    `<div class="text-sm text-gray-300">• ${example}</div>`
                ).join('')}
            </div>
        `;
        
        container.appendChild(card);
    });
}

// Test API
async function testApi() {
    const apiKey = document.getElementById('api-key-select')?.value;
    const cnpj = document.getElementById('playground-cnpj')?.value;
    
    if (!apiKey) {
        alert('Selecione uma API Key para testar');
        return;
    }
    
    if (!cnpj) {
        alert('Digite um CNPJ para testar');
        return;
    }
    
    // Show loading
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
        loadingOverlay.classList.remove('hidden');
    }
    
    try {
        // Prepare request data
        const requestData = {
            cnpj: cnpj,
            protestos: document.getElementById('playground-protestos')?.checked || false,
            receita_federal: document.getElementById('playground-receita-federal')?.checked || false,
            simples: document.getElementById('playground-simples')?.checked || false,
            registrations: document.getElementById('playground-registrations')?.checked || false,
            geocoding: document.getElementById('playground-geocoding')?.checked || false,
            suframa: document.getElementById('playground-suframa')?.checked || false,
            strategy: document.getElementById('playground-strategy')?.value || 'CACHE_IF_FRESH',
            api_key: apiKey
        };
        
        // Get authentication token
        const authToken = localStorage.getItem('auth_token') || localStorage.getItem('session_token');
        
        // Prepare headers
        const headers = {
            'Content-Type': 'application/json'
        };
        
        // Add authorization header if token exists
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
            console.log('🔐 Enviando token de autenticação para playground');
        } else {
            console.log('⚠️ Nenhum token de autenticação encontrado');
        }
        
        // Make request
        const response = await fetch('/documentation/playground/test', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(requestData)
        });
        
        const result = await response.json();
        
        // Display result
        displayPlaygroundResult(result);
        
    } catch (error) {
        console.error('Erro ao testar API:', error);
        displayPlaygroundResult({
            success: false,
            error: error.message,
            status_code: 500
        });
    } finally {
        // Hide loading
        if (loadingOverlay) {
            loadingOverlay.classList.add('hidden');
        }
    }
}

// Display playground result
function displayPlaygroundResult(result) {
    const container = document.getElementById('playground-response');
    if (!container) return;
    
    if (result.success) {
        container.innerHTML = `
            <div class="mb-4">
                <div class="flex items-center justify-between">
                    <div class="flex items-center">
                        <span class="material-icons text-green-400 mr-2">check_circle</span>
                        <span class="text-green-400 font-semibold">Sucesso</span>
                    </div>
                    <span class="text-sm text-gray-400">Status: ${result.status_code}</span>
                </div>
            </div>
            <div class="bg-gray-900 p-4 rounded-lg">
                <pre><code class="language-json">${JSON.stringify(result.response_data, null, 2)}</code></pre>
            </div>
        `;
    } else {
        container.innerHTML = `
            <div class="mb-4">
                <div class="flex items-center justify-between">
                    <div class="flex items-center">
                        <span class="material-icons text-red-400 mr-2">error</span>
                        <span class="text-red-400 font-semibold">Erro</span>
                    </div>
                    <span class="text-sm text-gray-400">Status: ${result.status_code || 'Erro'}</span>
                </div>
            </div>
            <div class="bg-gray-900 p-4 rounded-lg">
                <pre><code class="language-json">${JSON.stringify(result, null, 2)}</code></pre>
            </div>
        `;
    }
    
    // Highlight syntax
    if (typeof Prism !== 'undefined') {
        Prism.highlightAll();
    }
}

// Load pricing table from database
async function loadPricingTable() {
    try {
        const authToken = localStorage.getItem('auth_token') || localStorage.getItem('session_token');
        
        if (!authToken) {
            console.log('⚠️ Nenhum token encontrado, usando tabela de preços estática');
            return;
        }
        
        console.log('📊 Carregando tabela de preços do banco de dados...');
        
        const response = await fetch('/api/v1/stripe/consultation-types', {
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        const consultationTypes = data.consultation_types || [];
        
        console.log('✅ Tabela de preços carregada:', consultationTypes.length, 'tipos');
        
        // Renderizar tabela de preços dinâmica
        renderPricingTable(consultationTypes);
        
    } catch (error) {
        console.error('❌ Erro ao carregar tabela de preços:', error);
        // Manter tabela estática em caso de erro
    }
}

// Render pricing table with database data
function renderPricingTable(consultationTypes) {
    const container = document.querySelector('#pricing-table-container');
    if (!container || !consultationTypes.length) return;
    
    const tableHtml = `
        <div class="overflow-x-auto">
            <table class="w-full bg-gray-900 rounded-lg overflow-hidden">
                <thead class="bg-gray-700">
                    <tr>
                        <th class="px-6 py-4 text-left text-white font-semibold">Serviço</th>
                        <th class="px-6 py-4 text-left text-white font-semibold">Descrição</th>
                        <th class="px-6 py-4 text-right text-white font-semibold">Preço</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-gray-700">
                    ${consultationTypes.map(type => {
                        // Personalizar descrição para protestos
                        let description = type.description;
                        if (type.code.toLowerCase() === 'protestos') {
                            description = 'Consulta de protestos no CenProt Nacional';
                        }
                        
                        return `
                        <tr class="hover:bg-gray-800 transition-colors">
                            <td class="px-6 py-4">
                                <div class="flex items-center">
                                    <div class="w-8 h-8 bg-gradient-to-r ${getServiceGradient(type.code)} rounded-lg flex items-center justify-center mr-3">
                                        <span class="material-icons text-white text-sm">${getServiceIcon(type.code)}</span>
                                    </div>
                                    <span class="text-white font-medium">${type.name}</span>
                                </div>
                            </td>
                            <td class="px-6 py-4 text-gray-300">${description}</td>
                            <td class="px-6 py-4 text-right">
                                <span class="text-green-400 font-bold text-lg">R$ ${type.cost_reais.toFixed(2).replace('.', ',')}</span>
                            </td>
                        </tr>
                    `;
                    }).join('')}
                </tbody>
            </table>
        </div>
        
        <!-- Informação Importante -->
        <div class="mt-6 p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
            <div class="flex items-start">
                <span class="material-icons text-yellow-400 mr-3 mt-0.5">info</span>
                <div>
                    <h4 class="text-yellow-400 font-semibold mb-1">Informação Importante</h4>
                    <p class="text-gray-300 text-sm">
                        Os preços são cobrados por consulta realizada e debitados automaticamente do seu saldo de créditos.
                        Consultas com erro não são cobradas.
                    </p>
                </div>
            </div>
        </div>
    `;
    
    container.innerHTML = tableHtml;
}

// Get service icon based on code
function getServiceIcon(serviceCode) {
    const icons = {
        'protestos': 'warning',
        'receita_federal': 'account_balance',
        'simples_nacional': 'business',
        'cnae': 'category',
        'socios': 'people',
        'endereco': 'place',
        'geocoding': 'place',
        'suframa': 'help_outline',
        'registrations': 'folder'
    };
    return icons[serviceCode.toLowerCase()] || 'help_outline';
}

// Get service gradient based on code
function getServiceGradient(serviceCode) {
    const gradients = {
        'protestos': 'from-yellow-400 to-orange-500',
        'receita_federal': 'from-green-400 to-emerald-500',
        'simples_nacional': 'from-blue-400 to-cyan-500',
        'cnae': 'from-purple-400 to-pink-500',
        'socios': 'from-indigo-400 to-blue-500',
        'endereco': 'from-teal-400 to-green-500',
        'geocoding': 'from-purple-400 to-pink-500',
        'suframa': 'from-indigo-400 to-blue-500',
        'registrations': 'from-teal-400 to-green-500'
    };
    return gradients[serviceCode.toLowerCase()] || 'from-gray-400 to-slate-500';
}

// Copy to clipboard
function copyToClipboard(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        const text = element.textContent;
        navigator.clipboard.writeText(text).then(() => {
            // Show feedback
            const button = element.parentElement.querySelector('.copy-btn');
            if (button) {
                const originalText = button.innerHTML;
                button.innerHTML = '<span class="material-icons text-sm text-green-400">check</span>';
                setTimeout(() => {
                    button.innerHTML = originalText;
                }, 2000);
            }
        }).catch(err => {
            console.error('Erro ao copiar para clipboard:', err);
        });
    }
}

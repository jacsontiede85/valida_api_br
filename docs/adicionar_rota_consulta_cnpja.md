# Plano de Ação: Integração Completa API CNPJa na Rota `/api/v1/cnpj/consult`

## Análise da Situação Atual

### 🔍 **Estado Atual do Sistema**

1. **Rota Existente**: `/api/v1/cnpj/consult` em `api/routers/saas_routes.py` (linha 203)
   - Consulta **apenas protestos** via `ScrapingService`
   - Usa modelos `ConsultationRequest` e `ConsultationResponse`
   - Autenticação via API key obrigatória
   
2. **Integração CNPJa Disponível**: `src/utils/cnpja_api.py`
   - Classe `CNPJaAPI` completamente implementada
   - Método `get_all_company_info()` com parâmetros seletivos
   - Cache inteligente e controle de rate limiting
   - Suporte a todos os parâmetros solicitados

3. **Interface Atual**: `templates/consultas.html` + `static/js/consultas.js`
   - Formulário simples com campo CNPJ único
   - JavaScript chama `/api/v1/cnpj/consult` diretamente
   - Exibe apenas resultados de protestos

4. **Arquitetura de Providers**: `src/services/consultation_service.py`
   - Sistema robusto que gerencia RPA vs API oficial
   - Já separado em providers independentes

---

## 🎯 **Objetivos da Implementação**

### **Funcionalidades Alvo**
1. **Backend**: Rota `/api/v1/cnpj/consult` aceita parâmetros seletivos
2. **Dados Combinados**: Consulta protestos + dados CNPJa em uma única requisição
3. **Interface**: Checkboxes para seleção de tipos de dados
4. **Compatibilidade**: Manter backward compatibility com requests existentes

### **Parâmetros de Consulta Solicitados**
```json
{
  "cnpj": "12.345.678/0001-90",
  "protestos": true,      // API de protestos (RPA/API oficial)
  "simples": true,        // API CNPJa - Simples Nacional
  "registrations": "BR",  // API CNPJa - Inscrições Estaduais
  "geocoding": true,      // API CNPJa - Geolocalização
  "suframa": true,        // API CNPJa - SUFRAMA  
  "strategy": "CACHE_IF_FRESH" // API CNPJa - Estratégia de cache
}
```

---

## 📋 **Análise de Dependências e Integrações**

### **Sistemas Envolvidos**

| Sistema | Status | Uso | Observações |
|---------|--------|-----|-------------|
| `ScrapingService` | ✅ Ativo | Consulta protestos | Via RPA ou API oficial |
| `CNPJaAPI` | ✅ Disponível | Dados completos CNPJ | Rate limiting 3 req/min |
| `ConsultationService` | ✅ Ativo | Provider manager | Gerencia RPA vs API |
| Auth/API Keys | ✅ Ativo | Autenticação | Sistema SaaS funcionando |
| Frontend | ✅ Básico | Interface usuário | Precisa expansão |

### **Fluxos de Dados Identificados**

1. **Fluxo Protestos**: `Request → Auth → ScrapingService → ConsultationService → Provider (RPA/API)`
2. **Fluxo CNPJa**: `Request → Auth → CNPJaAPI → Cache/HTTP → API externa`  
3. **Fluxo Combinado**: Ambos simultaneamente + merge de resultados

---

## 🚀 **Plano de Implementação Detalhado**

### **FASE 1: Extensão dos Modelos de Dados**

#### **1.1 Atualizar `ConsultationRequest`** (`api/models/saas_models.py`)
```python
class ConsultationRequest(BaseModel):
    """Modelo para requisição de consulta expandida"""
    cnpj: str
    api_key: Optional[str] = None  # Compatibilidade existente
    
    # Parâmetros de consulta (todos opcionais com defaults)
    protestos: bool = True          # Manter compatibilidade - sempre true por default
    simples: bool = False           # CNPJa - Simples Nacional  
    registrations: Optional[str] = None  # CNPJa - 'BR' para todos os estados
    geocoding: bool = False         # CNPJa - Geolocalização
    suframa: bool = False          # CNPJa - SUFRAMA
    strategy: str = "CACHE_IF_FRESH" # CNPJa - Estratégia cache
    
    # Parâmetros de extração (controle fino do que extrair)
    extract_basic: bool = True      # Dados básicos da empresa
    extract_address: bool = True    # Endereço
    extract_contact: bool = True    # Contatos  
    extract_activities: bool = True # CNAEs
    extract_partners: bool = True   # Sócios
```

#### **1.2 Expandir `ConsultationResponse`** 
```python
class ConsultationResponse(BaseModel):
    """Modelo de resposta da consulta expandida"""
    success: bool
    cnpj: str
    timestamp: datetime
    user_id: Optional[str] = None
    api_key_id: Optional[str] = None
    
    # Dados segmentados por tipo
    protestos: Optional[dict] = None      # Dados de protestos (estrutura atual)
    dados_receita: Optional[dict] = None  # Dados da Receita Federal via CNPJa
    error: Optional[str] = None
    
    # Metadados da consulta
    sources_consulted: List[str] = []     # ['protestos', 'cnpja']
    cache_used: bool = False              # Se usou cache CNPJa
    response_time_ms: Optional[int] = None
    
    # Estatísticas (para protestos)
    total_protests: Optional[int] = None
    has_protests: Optional[bool] = None
```

### **FASE 2: Criação do Serviço Unificado**

#### **2.1 Novo `UnifiedConsultationService`** (`api/services/unified_consultation_service.py`)

```python
class UnifiedConsultationService:
    """Serviço que combina consultas de protestos e dados CNPJa"""
    
    def __init__(self):
        self.scraping_service = ScrapingService()
        self.cnpja_api = CNPJaAPI()
    
    async def consultar_dados_completos(self, request: ConsultationRequest) -> ConsultationResponse:
        """Consulta dados completos baseado nos parâmetros solicitados"""
        
        start_time = time.time()
        sources_consulted = []
        protestos_data = None
        cnpja_data = None
        cache_used = False
        
        # 1. Consultar protestos se solicitado
        if request.protestos:
            try:
                protestos_result = await self.scraping_service.consultar_cnpj(request.cnpj)
                protestos_data = self._format_protestos_data(protestos_result)
                sources_consulted.append('protestos')
            except Exception as e:
                logger.error("erro_consulta_protestos", cnpj=request.cnpj, error=str(e))
        
        # 2. Consultar dados CNPJa se algum parâmetro foi solicitado  
        if any([request.simples, request.registrations, request.geocoding, request.suframa]):
            try:
                cnpja_params = self._build_cnpja_params(request)
                cnpja_result = self.cnpja_api.get_all_company_info(request.cnpj, **cnpja_params)
                cnpja_data = cnpja_result
                sources_consulted.append('cnpja')
                cache_used = request.cnpj in self.cnpja_api.cache
            except Exception as e:
                logger.error("erro_consulta_cnpja", cnpj=request.cnpj, error=str(e))
        
        # 3. Calcular estatísticas 
        total_protests, has_protests = self._calculate_protest_stats(protestos_data)
        response_time = int((time.time() - start_time) * 1000)
        
        return ConsultationResponse(
            success=True,
            cnpj=request.cnpj,
            timestamp=datetime.now(),
            protestos=protestos_data,
            dados_receita=cnpja_data,  
            sources_consulted=sources_consulted,
            cache_used=cache_used,
            response_time_ms=response_time,
            total_protests=total_protests,
            has_protests=has_protests
        )
    
    def _build_cnpja_params(self, request: ConsultationRequest) -> dict:
        """Converte parâmetros do request para formato CNPJa API"""
        params = {
            'strategy': request.strategy,
            'simples': request.simples,
            'geocoding': request.geocoding, 
            'suframa': request.suframa,
            'basic': request.extract_basic,
            'address': request.extract_address,
            'contact': request.extract_contact,
            'activities': request.extract_activities,
            'partners': request.extract_partners
        }
        
        if request.registrations:
            params['registrations'] = request.registrations
            
        return {k: v for k, v in params.items() if v is not None}
```

#### **2.2 Integração no Router** (`api/routers/saas_routes.py`)

```python
@router.post("/cnpj/consult", response_model=ConsultationResponse)
async def consult_cnpj_enhanced(
    request: ConsultationRequest,
    user: Optional[AuthUser] = Depends(get_current_user)
):
    """
    Consulta CNPJ com dados completos - protestos + receita federal
    
    Parâmetros aceitos:
    - protestos: bool - Consultar protestos (default: true) 
    - simples: bool - Dados Simples Nacional (default: false)
    - registrations: str - Inscrições estaduais 'BR' (default: None)
    - geocoding: bool - Geolocalização (default: false)
    - suframa: bool - Dados SUFRAMA (default: false)  
    - strategy: str - Cache strategy (default: 'CACHE_IF_FRESH')
    """
    
    # [Manter lógica de autenticação existente]
    
    # Usar novo serviço unificado
    from api.services.unified_consultation_service import UnifiedConsultationService
    
    unified_service = UnifiedConsultationService()
    
    try:
        result = await unified_service.consultar_dados_completos(request)
        
        # Log da consulta para histórico
        await query_logger_service.log_query(
            user_id=user.user_id,
            api_key_id=user.api_key, 
            cnpj=request.cnpj,
            endpoint="/cnpj/consult",
            success=result.success,
            response_time_ms=result.response_time_ms,
            sources=result.sources_consulted
        )
        
        return result
        
    except Exception as e:
        logger.error("erro_consulta_unificada", cnpj=request.cnpj, error=str(e))
        return ConsultationResponse(
            success=False,
            cnpj=request.cnpj, 
            error=str(e),
            timestamp=datetime.now(),
            user_id=user.user_id if user else None
        )
```

### **FASE 3: Atualização da Interface**

#### **3.1 Expansão do HTML** (`templates/consultas.html`)

```html
<!-- Após o campo CNPJ, adicionar seção de opções -->
<div class="mt-4">
    <h3 class="text-md font-semibold text-white mb-3">Dados para Consultar</h3>
    
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Coluna 1: Protestos -->
        <div class="space-y-3">
            <h4 class="text-sm font-medium text-gray-300">Dados Jurídicos</h4>
            
            <div class="flex items-center">
                <input id="protestos" name="protestos" type="checkbox" checked 
                       class="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500">
                <label for="protestos" class="ml-2 text-sm text-gray-300">
                    Protestos <span class="text-gray-500">(CenProt)</span>
                </label>
            </div>
        </div>
        
        <!-- Coluna 2: Dados Receita Federal -->  
        <div class="space-y-3">
            <h4 class="text-sm font-medium text-gray-300">Dados da Receita Federal</h4>
            
            <div class="flex items-center">
                <input id="simples" name="simples" type="checkbox" 
                       class="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500">
                <label for="simples" class="ml-2 text-sm text-gray-300">
                    Simples Nacional <span class="text-gray-500">(MEI)</span>
                </label>
            </div>
            
            <div class="flex items-center">
                <input id="registrations" name="registrations" type="checkbox" 
                       class="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500">
                <label for="registrations" class="ml-2 text-sm text-gray-300">
                    Inscrições Estaduais <span class="text-gray-500">(Todos estados)</span>
                </label>
            </div>
            
            <div class="flex items-center">
                <input id="geocoding" name="geocoding" type="checkbox" 
                       class="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500">
                <label for="geocoding" class="ml-2 text-sm text-gray-300">
                    Geolocalização <span class="text-gray-500">(Lat/Long)</span>
                </label>
            </div>
            
            <div class="flex items-center">
                <input id="suframa" name="suframa" type="checkbox" 
                       class="h-4 w-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500">
                <label for="suframa" class="ml-2 text-sm text-gray-300">
                    SUFRAMA <span class="text-gray-500">(Zona Franca)</span>
                </label>
            </div>
        </div>
    </div>
    
    <!-- Configurações Avançadas (Colapsível) -->
    <div class="mt-4">
        <button type="button" id="toggle-advanced" 
                class="text-sm text-blue-400 hover:text-blue-300 focus:outline-none">
            + Configurações Avançadas
        </button>
        
        <div id="advanced-options" class="hidden mt-3 p-3 bg-gray-800 rounded-lg border border-gray-600">
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                    <label for="strategy" class="block text-sm font-medium text-gray-300 mb-1">
                        Estratégia de Cache
                    </label>
                    <select id="strategy" name="strategy" 
                            class="form-input w-full">
                        <option value="CACHE_IF_FRESH">Cache se recente (padrão)</option>
                        <option value="ONLINE">Sempre online (sem cache)</option>
                    </select>
                </div>
            </div>
        </div>
    </div>
</div>
```

#### **3.2 Atualização do JavaScript** (`static/js/consultas.js`)

```javascript
// Adicionar após o método handleConsulta, linha ~44
buildConsultationRequest(cnpj) {
    // Coletar opções selecionadas
    const options = {
        cnpj: cnpj,
        api_key: 'rcp_dev-key-2', // Manter para compatibilidade
        
        // Dados jurídicos  
        protestos: document.getElementById('protestos')?.checked || false,
        
        // Dados da Receita Federal
        simples: document.getElementById('simples')?.checked || false,
        registrations: document.getElementById('registrations')?.checked ? 'BR' : null,
        geocoding: document.getElementById('geocoding')?.checked || false,
        suframa: document.getElementById('suframa')?.checked || false,
        
        // Configurações avançadas
        strategy: document.getElementById('strategy')?.value || 'CACHE_IF_FRESH'
    };
    
    console.log('📤 Parâmetros da consulta:', options);
    return options;
}

// Modificar método consultarCNPJ, linha ~75
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
        throw new Error(data.detail || data.error || `Erro ${response.status}`);
    }
    
    if (data.success === false) {
        throw new Error(data.error || 'Erro na consulta');
    }

    return data;
}

// Novo método para renderizar dados da Receita Federal
renderDadosReceita(dadosReceita) {
    if (!dadosReceita) return '';
    
    let html = '<div class="mt-6 space-y-4">';
    html += '<h3 class="text-lg font-semibold text-white flex items-center gap-2">';
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
    
    html += '</div>';
    return html;
}

// Modificar exibirResultado para incluir dados da Receita (linha ~105)
exibirResultado(resultado) {
    // [Manter lógica existente de protestos...]
    
    // Adicionar dados da Receita Federal ao final
    const dadosReceitaHtml = this.renderDadosReceita(resultado.dados_receita);
    if (dadosReceitaHtml) {
        content.innerHTML += dadosReceitaHtml;
    }
    
    // Adicionar metadados da consulta
    const metadataHtml = this.renderMetadados(resultado);
    if (metadataHtml) {
        content.innerHTML += metadataHtml;
    }
}

// Novo método para metadados
renderMetadados(resultado) {
    if (!resultado.sources_consulted || resultado.sources_consulted.length === 0) {
        return '';
    }
    
    return `
        <div class="mt-6 bg-gray-800 border border-gray-600 rounded-lg p-4">
            <h4 class="text-sm font-semibold text-gray-400 mb-2">Metadados da Consulta</h4>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                <div><span class="text-gray-500">Fontes:</span> <span class="text-gray-300">${resultado.sources_consulted.join(', ')}</span></div>
                <div><span class="text-gray-500">Cache:</span> <span class="text-gray-300">${resultado.cache_used ? 'Usado' : 'Não usado'}</span></div>
                <div><span class="text-gray-500">Tempo:</span> <span class="text-gray-300">${resultado.response_time_ms}ms</span></div>
                <div><span class="text-gray-500">Timestamp:</span> <span class="text-gray-300">${new Date(resultado.timestamp).toLocaleTimeString()}</span></div>
            </div>
        </div>`;
}
```

### **FASE 4: Testes e Validação**

#### **4.1 Testes de Unidade**
```python
# tests/test_unified_consultation.py

class TestUnifiedConsultation:
    
    @pytest.mark.asyncio
    async def test_consulta_apenas_protestos(self):
        """Testa consulta apenas de protestos (compatibilidade)"""
        request = ConsultationRequest(
            cnpj="12345678000190",
            protestos=True
        )
        
        service = UnifiedConsultationService()
        result = await service.consultar_dados_completos(request)
        
        assert result.success == True
        assert 'protestos' in result.sources_consulted
        assert 'cnpja' not in result.sources_consulted
        assert result.protestos is not None
        assert result.dados_receita is None
    
    @pytest.mark.asyncio  
    async def test_consulta_dados_completos(self):
        """Testa consulta completa - protestos + CNPJa"""
        request = ConsultationRequest(
            cnpj="12345678000190",
            protestos=True,
            simples=True,
            geocoding=True,
            registrations="BR"
        )
        
        service = UnifiedConsultationService()
        result = await service.consultar_dados_completos(request)
        
        assert result.success == True
        assert 'protestos' in result.sources_consulted
        assert 'cnpja' in result.sources_consulted
        assert result.protestos is not None
        assert result.dados_receita is not None
        assert result.response_time_ms is not None
```

#### **4.2 Testes de Integração**
```bash
# Teste curl para backward compatibility
curl -X POST "http://localhost:2377/api/v1/cnpj/consult" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer rcp_dev-key-2" \
     -d '{"cnpj": "12345678000190"}'

# Teste curl com parâmetros completos
curl -X POST "http://localhost:2377/api/v1/cnpj/consult" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer rcp_dev-key-2" \
     -d '{
       "cnpj": "12345678000190",
       "protestos": true,
       "simples": true,
       "geocoding": true,
       "registrations": "BR",
       "suframa": false,
       "strategy": "CACHE_IF_FRESH"
     }'
```

---

## ⚠️ **Riscos e Mitigações**

### **Riscos Identificados**

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| **Rate limiting CNPJa** | Alta | Médio | Cache inteligente + retry logic |
| **Timeout em consultas duplas** | Média | Alto | Consultas paralelas + timeout configurável |
| **Quebra compatibilidade** | Baixa | Alto | Defaults preservam comportamento atual |
| **Sobrecarga de dados** | Média | Médio | Paginação + dados opcionais |
| **Falha em uma das APIs** | Alta | Médio | Graceful degradation + fallback |

### **Estratégias de Mitigação**

1. **Rate Limiting**: Cache com TTL de 2 dias + queue de requisições
2. **Timeouts**: 30s por API, 45s total
3. **Fallback**: Se CNPJa falhar, continuar com protestos
4. **Monitoramento**: Logs estruturados + métricas por provider
5. **Circuit Breaker**: Desabilitar CNPJa temporariamente se muitas falhas

---

## 📊 **Cronograma de Implementação**

### **Sprint 1 (Semana 1)**
- ✅ **Análise completa** (documento atual)  
- 🚧 **FASE 1**: Extensão dos modelos  
- 🚧 **FASE 2**: Criação do UnifiedConsultationService  
- 🚧 Testes de unidade básicos

### **Sprint 2 (Semana 2)**  
- 🚧 **FASE 3**: Interface + JavaScript  
- 🚧 Testes de integração  
- 🚧 Ajustes e refinamentos  
- 🚧 Documentação da API

### **Sprint 3 (Semana 3)**
- 🚧 **FASE 4**: Testes completos  
- 🚧 Deploy em ambiente de desenvolvimento  
- 🚧 Testes de performance  
- 🚧 Ajustes baseados em feedback

---

## 📈 **Métricas de Sucesso**

### **Métricas Técnicas**
- ✅ **Backward Compatibility**: 100% dos requests antigos funcionam
- ✅ **Response Time**: < 45s para consulta completa
- ✅ **Availability**: 99.5% uptime considerando rate limits
- ✅ **Cache Hit Rate**: > 60% para CNPJa (dados recentes)

### **Métricas de Negócio**  
- 📊 **Adoption Rate**: % usuários usando novos parâmetros
- 📊 **Data Coverage**: % consultas com dados completos vs apenas protestos  
- 📊 **User Satisfaction**: Feedback qualitativo da interface expandida
- 📊 **API Usage**: Distribuição de parâmetros mais utilizados

---

## 🔧 **Configurações Necessárias**

### **Variáveis de Ambiente Adicionais**
```bash
# Já configuradas
API_KEY_CNPJA=<chave_cnpja>
USAR_RESOLVE_CENPROT_API_OFICIAL=true

# Novas configurações (opcionais)
CNPJA_RATE_LIMIT_PER_MINUTE=3
CNPJA_CACHE_TTL_DAYS=2  
UNIFIED_CONSULTATION_TIMEOUT_SECONDS=45
ENABLE_CONSULTATION_METRICS=true
```

### **Dependências**
- ✅ **Existentes**: FastAPI, Pydantic, structlog, requests
- ✅ **CNPJa Integration**: Já implementada em `src/utils/cnpja_api.py`
- ✅ **Auth System**: Já funcionando via API keys

---

## 🎯 **Próximos Passos Imediatos**

### **Para Começar a Implementação:**

1. **Validar Plano** ✅
   - Revisar este documento 
   - Alinhar expectativas
   - Confirmar prioridades

2. **Setup Ambiente** 
   - Criar branch `feature/unified-consultation`
   - Configurar testes locais  
   - Validar API CNPJa funcionando

3. **Implementar FASE 1** 
   - Modificar `ConsultationRequest` e `ConsultationResponse`
   - Criar testes básicos dos modelos
   - Validar serialização

4. **Primeira Iteração**
   - Implementar `UnifiedConsultationService` básico
   - Integrar na rota existente  
   - Testes de funcionamento

---

## 💡 **Considerações Finais**

### **Pontos Fortes da Abordagem**
- ✅ **Reutilização máxima** de código existente
- ✅ **Backward compatibility** garantida  
- ✅ **Flexibilidade** para usuários escolherem dados necessários
- ✅ **Performance** via cache e consultas paralelas
- ✅ **Monitoramento** e observabilidade integrados

### **Oportunidades Futuras**
- 📋 **Webhooks**: Notificações quando dados mudam
- 📋 **Bulk Queries**: Consulta de múltiplos CNPJs  
- 📋 **Data Export**: CSV/Excel dos resultados
- 📋 **Advanced Filters**: Filtros por UF, porte, etc.
- 📋 **Dashboard Analytics**: Métricas de uso por usuário

**Status**: ✅ **Pronto para implementação**
**Estimativa**: 3 semanas para implementação completa  
**Complexidade**: **Média** (reutiliza muita infraestrutura existente)

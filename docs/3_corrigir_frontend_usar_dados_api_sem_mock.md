# 🎨 Frontend: Migração de Dados Mock para APIs Reais

## 📋 Análise Atual do Frontend

**Estrutura descoberta**: Sistema frontend funcional com **15 arquivos JavaScript** e **9 templates HTML**, mas usando **dados mock hardcoded** em vez das APIs reais implementadas no backend.

### 🔍 **Situação Identificada**
- ✅ **Templates HTML**: Interface completa implementada
- ✅ **JavaScript**: Lógica de negócio funcional  
- ❌ **Problema**: Uso extensivo de métodos `getMock*()` e dados hardcoded
- ❌ **Resultado**: Frontend desconectado das APIs reais do Supabase

---

## 🛠️ Alterações por Arquivo JavaScript

### 1. 📊 **Dashboard Principal** (`dashboard.js` + `dashboard_v2.js`)

#### **Problemas Identificados:**
- Dados mock hardcoded: `"R$ 9,60"`, `"R$ 0,40"`, etc.
- Não usa dados reais do endpoint `/api/v2/dashboard/data`
- Custos fixos: `costPerRequest = 0.021` em vez dos custos reais

#### **✅ Alterações Necessárias:**

```javascript
// ❌ REMOVER - Dados mock hardcoded
showMockData() {
    const mockCredits = {
        available: "R$ 9,60",
        purchased: "R$ 10,00", 
        used: "R$ 0,40"
    };
}

// ✅ IMPLEMENTAR - Usar dados reais da API
async loadRealDashboardData() {
    try {
        const response = await this.fetchWithAuth(`${this.apiBaseUrl}/dashboard/data`);
        if (response.ok) {
            const data = await response.json();
            this.updateDashboard(data);
            return;
        }
    } catch (error) {
        console.error('Erro ao carregar dados reais:', error);
    }
    // Fallback apenas em caso de erro real
    this.showErrorState();
}
```

#### **🎯 Endpoints para Conectar:**
- `GET /api/v2/dashboard/data` → Dados reais dos créditos (R$ 10,00)
- `GET /api/v2/costs/current` → Custos reais dos 6 tipos (15¢-5¢)
- `GET /api/v2/consultations/history` → Consultas reais registradas

---

### 2. 🔑 **API Keys** (`api-keys.js`)

#### **Problemas Identificados:**
- Método `loadMockData()` com 3 chaves fake
- Fallback desnecessário para dados mock
- Não usa dados das 10 chaves API reais no Supabase

#### **✅ Alterações Necessárias:**

```javascript
// ❌ REMOVER - Todo o método loadMockData()
loadMockData() {
    this.apiKeys = [
        {
            id: "dev-key-1",
            name: "Chave Principal", // FAKE
        }
    ];
}

// ✅ IMPLEMENTAR - Conexão obrigatória com API real
async loadAPIKeys() {
    this.showLoading(true);
    
    try {
        const response = await this.fetchWithAuth(`${this.apiBaseUrl}/api-keys`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        this.apiKeys = await response.json();
        this.renderAPIKeys();
        console.log(`✅ ${this.apiKeys.length} API keys reais carregadas`);
        
    } catch (error) {
        console.error('❌ Erro crítico ao carregar API keys:', error);
        this.showErrorState('Erro ao conectar com o servidor');
    } finally {
        this.showLoading(false);
    }
}
```

#### **🎯 Dados Reais Esperados:**
- **10 chaves API** cadastradas no Supabase
- **Campos reais**: `id`, `name`, `key_hash`, `is_active`, `created_at`, `last_used`

---

### 3. 💳 **Assinaturas** (`assinatura.js`)

#### **Problemas Identificados:**
- `getMockPlans()` com planos fake
- Não conecta com os 3 planos reais do Supabase
- Preços hardcoded em vez dos valores reais

#### **✅ Alterações Necessárias:**

```javascript
// ❌ REMOVER - Planos mock
getMockPlans() {
    return [
        {
            id: 'basic',
            name: 'Básico',
            price_cents: 10000, // HARDCODED
        }
    ];
}

// ✅ IMPLEMENTAR - Conectar com planos reais
async loadPlans() {
    try {
        const response = await AuthUtils.authenticatedFetchJSON('/api/v1/subscription-plans');
        this.availablePlans = response.plans || [];
        this.renderPlans();
        console.log(`✅ ${this.availablePlans.length} planos reais carregados`);
    } catch (error) {
        console.error('❌ Erro ao carregar planos:', error);
        this.showErrorState('Não foi possível carregar os planos');
    }
}
```

#### **🎯 Dados Reais do Supabase:**
- **3 planos** ativos: `basic`, `professional`, `enterprise`
- **Valores reais**: R$ 100,00 / R$ 300,00 / R$ 500,00
- **Créditos inclusos**: Equivalente ao valor do plano

---

### 4. 🔍 **Consultas** (`consultas.js`)

#### **Problemas Identificados:**
- Valores de custo hardcoded: `R$ 0,15`, `R$ 0,05`
- Não usa a tabela `consultation_types` para custos reais
- Templates com valores fixos em vez de dinâmicos

#### **✅ Alterações Necessárias:**

```javascript
// ❌ REMOVER - Custos hardcoded no template
// <div class="text-yellow-400 font-bold text-lg">R$ 0,15</div>

// ✅ IMPLEMENTAR - Carregar custos reais da API
async loadConsultationTypes() {
    try {
        const response = await fetch('/api/v2/consultation-types');
        const types = await response.json();
        this.consultationTypes = types;
        this.updateCostDisplay();
    } catch (error) {
        console.error('Erro ao carregar tipos de consulta:', error);
    }
}

// Atualizar custos dinamicamente no DOM
updateCostDisplay() {
    const protestoCost = this.consultationTypes.find(t => t.code === 'protestos')?.cost_cents || 15;
    const receitaCost = this.consultationTypes.find(t => t.code === 'receita_federal')?.cost_cents || 5;
    
    document.querySelector('[data-protesto-cost]').textContent = this.formatCurrency(protestoCost);
    document.querySelector('[data-receita-cost]').textContent = this.formatCurrency(receitaCost);
}
```

#### **🎯 Dados Reais a Conectar:**
- **6 tipos** da tabela `consultation_types`
- **Custos específicos**: Protestos (15¢), outros (5¢ cada)

---

### 5. 📈 **Histórico** (`history.js`)

#### **Problemas Identificados:**
- Não conecta com consulta real registrada no Supabase
- Sem dados de `response_time_ms`, `cache_used`

#### **✅ Alterações Necessárias:**

```javascript
// ✅ IMPLEMENTAR - Conectar com histórico real
async loadQueryHistory() {
    try {
        const response = await fetch('/api/v1/consultations/history', {
            headers: { 'Authorization': `Bearer ${this.getAuthToken()}` }
        });
        
        if (response.ok) {
            const data = await response.json();
            this.queries = data.consultations || [];
            this.renderHistory();
        } else {
            throw new Error('Falha ao carregar histórico');
        }
    } catch (error) {
        console.error('Erro ao carregar histórico real:', error);
        this.showErrorMessage('Não foi possível carregar o histórico de consultas');
    }
}
```

#### **🎯 Dados Reais:**
- **1 consulta** registrada no Supabase
- **Tabela `consultations`** + **`consultation_details`**
- **Métricas reais**: `response_time_ms`, `total_cost_cents`, `cache_used`

---

### 6. 💰 **Faturas** (`faturas.js`)

#### **Problemas Identificados:**
- `getMockInvoices()` com dados fake
- Não conecta com `credit_transactions` real

#### **✅ Alterações Necessárias:**

```javascript
// ❌ REMOVER - Mock invoices
getMockInvoices() {
    return {
        invoices: [{
            id: 'inv-001', // FAKE
            amount: 'R$ 100,00', // FAKE
        }]
    };
}

// ✅ IMPLEMENTAR - Usar transações reais
async loadInvoices() {
    try {
        const response = await AuthUtils.authenticatedFetchJSON('/api/v2/invoices/credits');
        this.invoices = response.invoices || [];
        this.creditTransactions = response.transactions || [];
        this.renderInvoices();
    } catch (error) {
        console.error('Erro ao carregar faturas reais:', error);
        this.showErrorState();
    }
}
```

#### **🎯 Dados Reais:**
- **2 transações** na tabela `credit_transactions`
- **Tipos**: `purchase`, `usage`, `renewal`, `refund`

---

### 7. 👤 **Perfil** (`perfil.js`)

#### **Problemas Identificados:**
- `getMockUserData()` com dados fake
- Não usa dados reais dos 7 usuários cadastrados

#### **✅ Alterações Necessárias:**

```javascript
// ❌ REMOVER - Mock user data
getMockUserData() {
    return {
        name: "João Silva", // FAKE
        email: "joao@exemplo.com", // FAKE
    };
}

// ✅ IMPLEMENTAR - Dados reais do usuário
async loadUserData() {
    try {
        const userData = await AuthUtils.authenticatedFetchJSON('/api/v1/auth/me');
        this.userData = userData;
        this.renderProfile();
    } catch (error) {
        console.error('Erro ao carregar perfil real:', error);
        this.redirectToLogin();
    }
}
```

---

### 8. ⚙️ **API Client v2** (`api_client_v2.js`)

#### **Problemas Identificados:**
- **7 métodos `getMock*()`** com dados falsos
- Sistema de fallback excessivo para mock
- Não prioriza dados reais da API

#### **✅ Alterações Necessárias:**

```javascript
// ❌ REMOVER todos os métodos getMock*():
// - getMockDashboardData()
// - getMockCostCalculation() 
// - getMockHistoryData()
// - getMockApiKeysUsage()
// - getMockSubscriptionPlans()
// - getMockInvoicesData()
// - getMockProfileData()

// ✅ IMPLEMENTAR - Apenas dados reais ou erro
async getDashboardData(period = '30d') {
    try {
        const response = await this.request(`${this.baseUrl}/dashboard/data?period=${period}`);
        return response;
    } catch (error) {
        console.error('❌ API indisponível:', error);
        throw new Error('Serviço temporariamente indisponível');
    }
    // Remover completamente: return this.getMockDashboardData();
}
```

---

## 🎯 Alterações nos Templates HTML

### 1. **Dashboard** (`home.html`)

#### **❌ Elementos com Dados Mock:**
```html
<!-- Valores hardcoded que devem ser dinâmicos -->
<span data-stat="creditos-disponiveis">R$ 0,00</span>
<span data-stat="creditos-comprados" class="text-blue-400">R$ 0,00</span>
<span data-stat="creditos-usados" class="text-red-400">R$ 0,00</span>
```

#### **✅ Implementação Correta:**
- Manter elementos `data-stat`, mas garantir que JavaScript popula com dados reais
- Remover valores placeholder fixos
- Usar dados do endpoint `/api/v2/dashboard/data`

### 2. **Consultas** (`consultas.html`)

#### **❌ Custos Hardcoded:**
```html
<div class="text-yellow-400 font-bold text-lg">R$ 0,15</div>
<div class="text-green-400 font-bold text-lg">R$ 0,05</div>
```

#### **✅ Implementação Dinâmica:**
```html
<div class="text-yellow-400 font-bold text-lg" data-protesto-cost>Carregando...</div>
<div class="text-green-400 font-bold text-lg" data-receita-cost>Carregando...</div>
```

---

## 🔄 Plano de Implementação

### **Fase 1: Remoção de Dados Mock (2 horas)**

1. **Remover todos os métodos `getMock*()`** de todos os arquivos JS
2. **Comentar fallbacks para mock** temporariamente
3. **Listar endpoints que devem funcionar** para cada tela

### **Fase 2: Conexão com APIs Reais (3 horas)**

1. **Dashboard**: Conectar `/api/v2/dashboard/data` com dados reais (R$ 10,00)
2. **API Keys**: Usar endpoint real com 10 chaves do Supabase
3. **Assinaturas**: Conectar com 3 planos reais (R$ 100/300/500)
4. **Consultas**: Usar custos da tabela `consultation_types`
5. **Histórico**: Conectar com 1 consulta registrada
6. **Faturas**: Usar 2 transações reais do `credit_transactions`
7. **Perfil**: Conectar com dados dos 7 usuários reais

### **Fase 3: Tratamento de Erros (1 hora)**

1. **Remover mensagens de fallback** para mock
2. **Implementar estados de erro** informativos
3. **Adicionar loading states** adequados
4. **Teste de conectividade** com backend

---

## 📊 Mapeamento: Mock → API Real

| Arquivo JS | Método Mock | API Real | Dados Esperados |
|------------|-------------|----------|-----------------|
| `dashboard_v2.js` | `showMockData()` | `GET /api/v2/dashboard/data` | Créditos R$ 10,00 reais |
| `api-keys.js` | `loadMockData()` | `GET /api/v1/api-keys` | 10 chaves reais do Supabase |
| `assinatura.js` | `getMockPlans()` | `GET /api/v1/subscription-plans` | 3 planos (R$ 100/300/500) |
| `consultas.js` | Custos hardcoded | `GET /api/v2/consultation-types` | 6 tipos, custos 5¢-15¢ |
| `history.js` | Sem mock direto | `GET /api/v1/consultations/history` | 1 consulta registrada |
| `faturas.js` | `getMockInvoices()` | `GET /api/v2/invoices/credits` | 2 transações reais |
| `perfil.js` | `getMockUserData()` | `GET /api/v1/auth/me` | Dados dos 7 usuários |
| `api_client_v2.js` | **7 métodos mock** | **8 endpoints reais** | Todos os dados do Supabase |

---

## ⚠️ Pontos Críticos de Atenção

### 1. **Sistema de Autenticação**
- **Problema**: Alguns JS usam tokens mock
- **Solução**: Garantir token real em `localStorage.getItem('auth_token')`

### 2. **Formatação de Moeda**
- **Problema**: Valores em centavos vs reais
- **Solução**: Função consistente `formatCurrency(cents)`

### 3. **Estados de Loading**
- **Problema**: Fallback imediato para mock
- **Solução**: Loading real + erro em caso de falha

### 4. **Cache de Dados**
- **Problema**: Cache de dados mock
- **Solução**: Limpar cache ao migrar para dados reais

---

## 🚀 Comandos de Implementação

### **Buscar e Remover Todos os Mocks:**
```bash
# Encontrar todos os métodos mock
grep -r "getMock\|showMock\|loadMock" static/js/

# Encontrar dados hardcoded
grep -r "R\$ [0-9]" static/js/ static/templates/
```

### **Validar Conectividade com APIs:**
```javascript
// Script de teste para validar todas as APIs
async function validateAllAPIs() {
    const endpoints = [
        '/api/v2/dashboard/data',
        '/api/v1/api-keys', 
        '/api/v1/subscription-plans',
        '/api/v2/consultation-types',
        '/api/v1/consultations/history',
        '/api/v2/invoices/credits',
        '/api/v1/auth/me'
    ];
    
    for (const endpoint of endpoints) {
        try {
            const response = await fetch(endpoint);
            console.log(`✅ ${endpoint}: ${response.status}`);
        } catch (error) {
            console.error(`❌ ${endpoint}: ${error.message}`);
        }
    }
}
```

---

## 📋 Checklist de Validação Final

### **Telas que Devem Mostrar Dados Reais:**

- [ ] **Dashboard**: R$ 10,00 créditos reais (não R$ 9,60 mock)
- [ ] **API Keys**: 10 chaves reais do Supabase
- [ ] **Assinaturas**: 3 planos reais (R$ 100/300/500)
- [ ] **Consultas**: Custos reais (Protestos 15¢, outros 5¢)
- [ ] **Histórico**: 1 consulta registrada no banco
- [ ] **Faturas**: 2 transações reais 
- [ ] **Perfil**: Dados do usuário autenticado real

### **Funcionalidades que Devem Funcionar:**
- [ ] Criação de API keys (retorna chave real)
- [ ] Cálculo de custos (usa tabela `consultation_types`)
- [ ] Histórico de consultas (mostra dados reais)
- [ ] Sistema de créditos (R$ 10,00 inicial)
- [ ] Renovação automática (2 transações registradas)

---

## 🎯 Resultado Final Esperado

**Sistema frontend 100% conectado com dados reais do Supabase:**

- ✅ **Zero dados mock** em produção
- ✅ **34+ registros reais** sendo exibidos
- ✅ **10 tabelas do Supabase** integradas
- ✅ **APIs v2.0** funcionando completamente
- ✅ **Sistema de créditos real** operacional

**Tempo estimado total**: **6 horas** de implementação + testes

**Status**: 🚀 **Pronto para implementação imediata**

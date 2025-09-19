# 🔧 Plano de Ação: Remover Custos Hardcoded e Usar Dados Reais do BD

## 🎯 Objetivo
Substituir os custos hardcoded na rota `/api/v1/cnpj/consult` por dados dinâmicos da tabela `consultation_types`, garantindo que o histórico de consultas seja sempre gravado com os custos corretos e atualizados.

---

## 📊 Análise da Situação Atual

### ❌ **Problemas Identificados**

#### 1. **Custos Hardcoded no Código**
**Localização**: `api/services/unified_consultation_service.py`
```python
# Linha 378: Protestos hardcoded
if request.protestos:
    total_cost += 15  # ❌ HARDCODED

# Linhas 385, 389, 393, 397, 401: CNPJa hardcoded
if request.extract_basic: 
    total_cost += 5   # ❌ HARDCODED
if request.simples:
    total_cost += 5   # ❌ HARDCODED
# ... outros custos hardcoded
```

**Localização**: `api/routers/saas_routes.py`
```python
# Linha 305: Logging com custo hardcoded
"cost_cents": 15,  # ❌ HARDCODED protestos

# Linhas 318, 329, 340: Outros tipos hardcoded
"cost_cents": 5,   # ❌ HARDCODED receita_federal, simples, suframa
```

#### 2. **Dados Mock no Histórico**
**Localização**: `api/services/history_service.py`
```python
# Linhas 371, 378, 394, 395: Mock data com custos fixos
"cost_cents": 15,     # ❌ MOCK protestos
"cost_cents": 5,      # ❌ MOCK receita_federal
{"count": 25, "cost": 375},  # ❌ CÁLCULO MOCK
```

#### 3. **Inconsistência de Implementação**
- ✅ **Existe**: Endpoint `/api/v2/consultation/types` que busca dados reais
- ❌ **Problema**: Rota principal `/api/v1/cnpj/consult` não utiliza esses dados
- ❌ **Resultado**: Frontend usa dados reais, backend usa dados hardcoded

---

## 🗺️ Mapeamento de Códigos (Sistema → Banco)

| Código no Sistema | Código na Tabela `consultation_types` | Status |
|-------------------|---------------------------------------|--------|
| `protestos` | `protestos` | ✅ Match |
| `receita_federal` | `receita_federal` | ✅ Match |
| `simples_nacional` | `simples_nacional` | ✅ Match |
| `registrations` | `cadastro_contribuintes` | ⚠️ Precisa mapear |
| `geocoding` | `geocodificacao` | ⚠️ Precisa mapear |
| `suframa` | `suframa` | ✅ Match |

---

## 📋 Plano de Ação Detalhado

### **FASE 1: Criar Serviço de Tipos de Consulta**

#### 1.1 **Criar `ConsultationTypesService`**
**Arquivo**: `api/services/consultation_types_service.py`

**Funcionalidades**:
- Buscar todos os tipos ativos da tabela `consultation_types`
- Cache em memória para performance (TTL 5 minutos)
- Mapeamento de códigos do sistema para códigos do BD
- Método para obter custo por código
- Método para validar se tipo está ativo

**Métodos principais**:
```python
class ConsultationTypesService:
    async def get_all_types() -> Dict[str, Dict]
    async def get_cost_by_code(code: str) -> Optional[int]
    async def get_type_by_code(code: str) -> Optional[Dict]
    async def refresh_cache() -> None
    def _map_system_code_to_db_code(code: str) -> str
```

#### 1.2 **Implementar Cache Inteligente**
- Cache em memória com TTL de 5 minutos
- Refresh automático em caso de erro
- Fallback para custos padrão em caso de falha crítica

---

### **FASE 2: Refatorar UnifiedConsultationService**

#### 2.1 **Modificar `_calculate_consultation_cost`**
**Antes**:
```python
# ❌ Hardcoded
if request.protestos:
    total_cost += 15
```

**Depois**:
```python
# ✅ Dinâmico
if request.protestos:
    cost = await consultation_types_service.get_cost_by_code('protestos')
    total_cost += cost or 15  # fallback de segurança
```

#### 2.2 **Atualizar Logging de Tipos Consultados**
- Buscar custos reais no momento da consulta
- Manter estrutura atual do `consultation_types` array
- Preservar fallbacks de segurança

---

### **FASE 3: Refatorar saas_routes.py**

#### 3.1 **Buscar Custos Dinâmicos no Logging**
**Antes**:
```python
# ❌ Hardcoded
consultation_types.append({
    "type_code": "protestos",
    "cost_cents": 15,  # HARDCODED
    # ...
})
```

**Depois**:
```python
# ✅ Dinâmico
protestos_cost = await consultation_types_service.get_cost_by_code('protestos')
consultation_types.append({
    "type_code": "protestos", 
    "cost_cents": protestos_cost or 15,  # fallback
    # ...
})
```

#### 3.2 **Implementar Mapeamento de Códigos**
```python
# Mapeamento para códigos não coincidentes
CODE_MAPPING = {
    'registrations': 'cadastro_contribuintes',
    'geocoding': 'geocodificacao'
}
```

---

### **FASE 4: Eliminar Dados Mock**

#### 4.1 **Refatorar HistoryService**
- Remover `_generate_mock_consultations_v2`
- Remover `_generate_mock_monthly_usage`
- Usar apenas dados reais do Supabase
- Implementar mensagens apropriadas quando não há dados

#### 4.2 **Atualizar Endpoints que Usam Mock**
- Dashboard: usar dados reais ou vazio
- Histórico: usar dados reais ou mensagem "Nenhum histórico"
- Analytics: calcular com dados reais

---

### **FASE 5: Garantir Integridade do Histórico**

#### 5.1 **Validar Gravação Correta**
- Custos gravados devem ser os vigentes no momento da consulta
- `consultation_details.cost_cents` deve usar valor do BD
- Manter rastreabilidade: qual custo estava vigente quando

#### 5.2 **Testes de Consistência**
- Testar cenário: alterar custo no BD → próxima consulta deve usar novo valor
- Testar cenário: falha no BD → deve usar fallback e não quebrar
- Testar cenário: cache inválido → deve refreshar automaticamente

---

## 🔄 Ordem de Implementação

### **Sprint 1: Fundação**
1. ✅ Criar `ConsultationTypesService` com cache
2. ✅ Implementar mapeamento de códigos
3. ✅ Testes unitários do serviço

### **Sprint 2: Core Business**
1. ✅ Refatorar `UnifiedConsultationService._calculate_consultation_cost`
2. ✅ Refatorar logging em `saas_routes.py`
3. ✅ Testes de integração

### **Sprint 3: Cleanup**
1. ✅ Remover dados mock do `HistoryService`
2. ✅ Atualizar endpoints dependentes
3. ✅ Testes end-to-end

---

## ⚠️ Riscos e Mitigações

### **Risco 1: Falha de Conexão com BD**
**Problema**: BD indisponível → consultas param
**Mitigação**: 
- Cache com TTL longo em caso de erro
- Fallback para custos padrão hardcoded
- Log de alertas para monitoramento

### **Risco 2: Inconsistência Temporária**
**Problema**: Alterar custo no BD → cache desatualizado
**Mitigação**: 
- TTL curto no cache (5 minutos)
- Endpoint para forçar refresh do cache
- Monitoramento de consistência

### **Risco 3: Performance**
**Problema**: Muitas consultas ao BD por request
**Mitigação**: 
- Cache agressivo dos tipos
- Uma consulta por request (batch)
- Lazy loading com cache

---

## 📊 Critérios de Sucesso

### **Funcionais**
- ✅ Custos sempre obtidos da tabela `consultation_types`
- ✅ Histórico gravado com custos corretos
- ✅ Alterações no BD refletidas imediatamente (ou em 5 min)
- ✅ Zero dados mock em produção

### **Não Funcionais**
- ✅ Performance ≤ 100ms adicionais por consulta
- ✅ Disponibilidade 99.9% (fallbacks funcionando)
- ✅ Zero breaking changes na API
- ✅ Logs estruturados para auditoria

### **Técnicos**
- ✅ Cobertura de testes ≥ 90%
- ✅ Zero custos hardcoded no código
- ✅ Mapeamento de códigos documentado
- ✅ Cache eficiente e monitorado

---

## 🧪 Casos de Teste Críticos

### **Cenário 1: Fluxo Normal**
1. Usuário faz consulta → Sistema busca custos no BD
2. Custos são cached → Consulta é processada
3. Histórico é gravado com custos corretos

### **Cenário 2: BD Indisponível**
1. BD falha → Cache retorna último valor conhecido
2. Se cache vazio → Usar fallback hardcoded
3. Alert é enviado → Sistema continua funcionando

### **Cenário 3: Custo Alterado**
1. Admin altera custo no BD → Cache expira em 5min
2. Próxima consulta → Busca novo custo automaticamente
3. Histórico reflete novo valor → Auditoria mantida

### **Cenário 4: Código Mapeado**
1. Consulta usa `registrations` → Sistema mapeia para `cadastro_contribuintes`
2. Busca custo correto → Grava histórico com código original
3. Relatórios funcionam → Consistência mantida

---

## 🎯 Entregáveis

### **Código**
- [ ] `api/services/consultation_types_service.py`
- [ ] `api/services/unified_consultation_service.py` (refatorado)
- [ ] `api/routers/saas_routes.py` (refatorado)
- [ ] `api/services/history_service.py` (sem mock)

### **Testes**
- [ ] Testes unitários do `ConsultationTypesService`
- [ ] Testes de integração da rota `/cnpj/consult`
- [ ] Testes de cenários de falha e recovery
- [ ] Testes de performance com cache

### **Documentação**
- [ ] Atualização do README com novos serviços
- [ ] Documentação do mapeamento de códigos
- [ ] Guia de troubleshooting para custos
- [ ] Changelog das alterações

---

**📅 Deadline Estimado**: 3-5 dias úteis  
**👥 Stakeholders**: Backend Team, QA, DevOps  
**🔗 Dependências**: Banco Supabase funcional, tabela `consultation_types` populada  

---

**Status**: ⏳ Aguardando aprovação para implementação  
**Última Atualização**: 18/09/2025  
**Próximo Step**: Criar `ConsultationTypesService`

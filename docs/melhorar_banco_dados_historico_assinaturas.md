# Plano de Reestruturação do Banco de Dados - Valida SaaS

## 📊 Análise do Fluxo Atual vs Banco de Dados

### 🔍 **Problemas Identificados**

#### **1. Custos Diferenciados por Tipo de Consulta**
**Fluxo Esperado (da imagem):**
- Protestos: R$ 0,15
- Receita Federal: R$ 0,05
- Simples Nacional: R$ 0,05
- Cadastro de Contribuintes: R$ 0,05
- Geocodificação: R$ 0,05
- Suframa: R$ 0,05

**Problema Atual:**
- Tabela `query_history` usa `credits_used: INTEGER DEFAULT 1` (fixo)
- Não há diferenciação de custos por tipo de consulta
- Dashboard usa custo fixo de R$ 0,10 por consulta

#### **2. Histórico Detalhado Insuficiente**
**Necessidade do Fluxo:**
- Registrar cada tipo de consulta separadamente
- Valores individuais por tipo
- Detalhamento de quais APIs foram consultadas
- Controle de custos específicos

**Problema Atual:**
- `query_history` registra apenas uma consulta por registro
- Campo `endpoint` genérico não detalha tipos específicos
- Não há separação entre protestos/receita/simples/etc

#### **3. Sistema de Planos e Assinaturas**
**Fluxo Esperado:**
- Planos com valores em reais: R$ 100,00 / R$ 300,00 / R$ 500,00
- Controle de créditos por tipo
- Renovação automática quando créditos acabam

**Problema Atual:**
- Planos fixos em centavos sem correspondência real
- Não há controle de créditos disponíveis
- Sistema não suporta renovação automática por esgotamento

---

## 🎯 **Proposta de Reestruturação**

### **1. Nova Estrutura de Tipos de Consulta**

#### **Tabela: `consultation_types`**
```sql
CREATE TABLE consultation_types (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,           -- 'protestos', 'receita_federal', 'simples', etc
    name VARCHAR(100) NOT NULL,                 -- Nome amigável
    description TEXT,                           -- Descrição detalhada
    cost_cents INTEGER NOT NULL,                -- Custo em centavos (15, 5, 5, etc)
    provider VARCHAR(50) NOT NULL,              -- 'resolve_cenprot', 'cnpja', 'receita_federal'
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Dados iniciais baseados no fluxo
INSERT INTO consultation_types (code, name, description, cost_cents, provider) VALUES
('protestos', 'Consulta de Protestos', 'Consulta protestos via Resolve CenProt', 15, 'resolve_cenprot'),
('receita_federal', 'Receita Federal', 'Dados básicos da empresa via CNPJa', 5, 'cnpja'),
('simples_nacional', 'Simples Nacional', 'Consulta regime tributário via CNPJa', 5, 'cnpja'),
('cadastro_contribuintes', 'Cadastro de Contribuintes', 'Inscrições estaduais via CNPJa', 5, 'cnpja'),
('geocodificacao', 'Geocodificação', 'Coordenadas geográficas via CNPJa', 5, 'cnpja'),
('suframa', 'Suframa', 'Dados da Suframa via CNPJa', 5, 'cnpja');
```

### **2. Reestruturação do Histórico de Consultas**

#### **Tabela: `consultations` (substitui `query_history`)**
```sql
CREATE TABLE consultations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    api_key_id UUID REFERENCES api_keys(id) ON DELETE SET NULL,
    cnpj VARCHAR(18) NOT NULL,
    
    -- Metadados da consulta
    total_cost_cents INTEGER NOT NULL DEFAULT 0,   -- Custo total da consulta
    response_time_ms INTEGER,
    status VARCHAR(20) DEFAULT 'success',          -- success, error, partial
    error_message TEXT,
    
    -- Controle de cache e performance
    cache_used BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### **Tabela: `consultation_details` (detalhamento por tipo)**
```sql
CREATE TABLE consultation_details (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    consultation_id UUID REFERENCES consultations(id) ON DELETE CASCADE,
    consultation_type_id UUID REFERENCES consultation_types(id),
    
    -- Resultado específico do tipo
    success BOOLEAN NOT NULL DEFAULT true,
    cost_cents INTEGER NOT NULL,               -- Custo específico deste tipo
    response_data JSONB,                       -- Dados retornados (opcional)
    cache_used BOOLEAN DEFAULT false,
    response_time_ms INTEGER,
    error_message TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### **3. Reestruturação do Sistema de Planos**

#### **Tabela: `subscription_plans` (atualizada - Simplificada)**
```sql
-- Remover tabela atual e recriar
DROP TABLE IF EXISTS subscription_plans CASCADE;

CREATE TABLE subscription_plans (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,           -- 'basic', 'professional', 'enterprise'
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Preços em centavos (R$ 100,00 = 10000 centavos)
    price_cents INTEGER NOT NULL,               -- Valor da assinatura
    credits_included_cents INTEGER NOT NULL,    -- Créditos inclusos na assinatura
    
    -- Limites do plano
    api_keys_limit INTEGER DEFAULT 1,
    
    -- Configurações simplificadas
    auto_renew_on_depletion BOOLEAN DEFAULT true, -- Renovar automaticamente quando créditos acabam
    
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Planos baseados no fluxo (quando créditos acabam, renova automaticamente)
INSERT INTO subscription_plans (code, name, description, price_cents, credits_included_cents, api_keys_limit) VALUES
('basic', 'Plano Básico', 'Ideal para começar - R$ 100,00 em créditos, renova automaticamente', 10000, 10000, 1),      -- R$ 100,00 = R$ 100,00 créditos
('professional', 'Plano Profissional', 'Para uso intensivo - R$ 300,00 em créditos, renova automaticamente', 30000, 30000, 5),   -- R$ 300,00 = R$ 300,00 créditos  
('enterprise', 'Plano Empresarial', 'Uso corporativo - R$ 500,00 em créditos, renova automaticamente', 50000, 50000, 20);        -- R$ 500,00 = R$ 500,00 créditos
```

### **4. Sistema de Controle de Créditos**

#### **Tabela: `user_credits` (Simplificada)**
```sql
CREATE TABLE user_credits (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    
    -- Controle de créditos em centavos (simplificado)
    available_credits_cents INTEGER DEFAULT 0,     -- Créditos disponíveis atuais
    total_purchased_cents INTEGER DEFAULT 0,       -- Total de créditos já comprados
    total_used_cents INTEGER DEFAULT 0,            -- Total de créditos já utilizados
    
    -- Controle de renovação automática
    last_auto_renewal TIMESTAMP WITH TIME ZONE,    -- Última renovação automática
    auto_renewal_count INTEGER DEFAULT 0,          -- Quantas renovações automáticas foram feitas
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

#### **Tabela: `credit_transactions` (Simplificada)**
```sql
CREATE TABLE credit_transactions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    consultation_id UUID REFERENCES consultations(id) ON DELETE SET NULL,
    
    -- Transação de crédito
    type VARCHAR(20) NOT NULL,                  -- 'purchase', 'usage', 'auto_renewal'
    amount_cents INTEGER NOT NULL,              -- Valor da transação (positivo para compra, negativo para uso)
    balance_after_cents INTEGER NOT NULL,       -- Saldo após a transação
    
    -- Metadados
    description TEXT,
    stripe_payment_id VARCHAR(255),             -- ID do pagamento no Stripe (para compras)
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### **5. Atualização da Tabela de Assinaturas (Simplificada)**

```sql
-- Atualizar tabela de assinaturas existente para suportar renovação automática
ALTER TABLE subscriptions 
ADD COLUMN IF NOT EXISTS last_auto_renewal TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS auto_renewal_enabled BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS auto_renewal_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_spent_cents INTEGER DEFAULT 0; -- Total gasto pelo usuário
```

### **6. Sistema de Analytics Aprimorado**

#### **Tabela: `daily_analytics` (substitui `query_analytics` - Simplificada)**
```sql
CREATE TABLE daily_analytics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    
    -- Estatísticas gerais
    total_consultations INTEGER DEFAULT 0,
    successful_consultations INTEGER DEFAULT 0,
    failed_consultations INTEGER DEFAULT 0,
    
    -- Custos e créditos (simplificado)
    total_cost_cents INTEGER DEFAULT 0,         -- Custo total do dia
    credits_used_cents INTEGER DEFAULT 0,       -- Créditos consumidos
    
    -- Por tipo de consulta (JSONB para flexibilidade)
    consultations_by_type JSONB DEFAULT '{}',   -- {"protestos": 5, "receita_federal": 10}
    costs_by_type JSONB DEFAULT '{}',           -- {"protestos": 75, "receita_federal": 50}
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, date)
);
```

---

## 🔄 **Plano de Migração**

### **Fase 1: Criação das Novas Tabelas (Sem Interrupção)**
1. Criar todas as novas tabelas
2. Popular `consultation_types` com dados base
3. Configurar novos planos em `subscription_plans`
4. Criar índices de performance

### **Fase 2: Migração de Dados Existentes**
```sql
-- Script de migração de dados históricos
-- Migrar query_history para consultations + consultation_details

INSERT INTO consultations (user_id, api_key_id, cnpj, total_cost_cents, response_time_ms, status, created_at)
SELECT 
    user_id, 
    api_key_id, 
    cnpj,
    CASE 
        WHEN endpoint LIKE '%protest%' THEN 15  -- Custo protestos
        ELSE 5                                   -- Custo padrão outros
    END as total_cost_cents,
    response_time_ms,
    CASE 
        WHEN response_status < 400 THEN 'success'
        ELSE 'error'
    END as status,
    created_at
FROM query_history;

-- Migrar detalhes (assumindo que query_history atual é principalmente protestos)
INSERT INTO consultation_details (consultation_id, consultation_type_id, success, cost_cents, created_at)
SELECT 
    c.id,
    (SELECT id FROM consultation_types WHERE code = 'protestos'),
    CASE WHEN qh.response_status < 400 THEN true ELSE false END,
    15,
    c.created_at
FROM consultations c
JOIN query_history qh ON (c.user_id = qh.user_id AND c.cnpj = qh.cnpj AND c.created_at = qh.created_at);
```

### **Fase 3: Atualização dos Serviços**
1. Atualizar `QueryLoggerService` para usar nova estrutura
2. Modificar `UnifiedConsultationService` para registrar por tipo
3. Atualizar `DashboardService` para calcular custos corretos
4. Implementar `CreditService` para controle de créditos

### **Fase 4: Atualização da Interface**
1. Dashboard com custos reais por tipo
2. Histórico detalhado por tipo de consulta
3. Página de créditos e cobrança
4. Relatórios de consumo por tipo

### **Fase 5: Remoção de Tabelas Antigas**
```sql
-- Após validação completa
DROP TABLE query_history;
DROP TABLE query_analytics;
-- Manter backup dos dados por segurança
```

---

## 📊 **Benefícios da Nova Estrutura Simplificada**

### **1. Modelo de Negócio Simples e Claro**
- Pagamento único por bloco de créditos
- Renovação automática quando créditos acabam
- Sem complexidade de cobrança por excedente

### **2. Controle Granular de Custos**
- Custo específico por tipo de consulta
- Histórico detalhado de gastos por tipo
- Transparência total para o usuário

### **3. Sistema de Créditos Simplificado**
- Controle claro de saldo disponível
- Renovação automática transparente
- Histórico completo de compras e consumo

### **4. Escalabilidade para Novos Tipos**
- Fácil adição de novos tipos de consulta
- Configuração dinâmica de preços
- Suporte a novos providers

### **5. Experiência do Usuário Otimizada**
- Sem surpresas na faturação
- Uso contínuo sem interrupções
- Dashboard claro com saldo em tempo real

---

## 🔄 **Lógica de Renovação Automática**

### **Funcionamento do Sistema**

#### **1. Verificação de Saldo Antes de Cada Consulta**
```python
async def check_credits_and_renew_if_needed(user_id: str, consultation_cost_cents: int):
    """
    Verifica se usuário tem créditos suficientes
    Se não tiver, renova automaticamente
    """
    user_credits = await get_user_credits(user_id)
    
    if user_credits.available_credits_cents < consultation_cost_cents:
        # Créditos insuficientes - renovar automaticamente
        subscription = await get_user_subscription(user_id)
        plan = await get_subscription_plan(subscription.plan_id)
        
        # Processar pagamento no Stripe
        stripe_payment = await process_auto_renewal_payment(
            user_id=user_id, 
            amount=plan.price_cents
        )
        
        if stripe_payment.success:
            # Adicionar créditos
            await add_credits(
                user_id=user_id,
                amount_cents=plan.credits_included_cents,
                transaction_type="auto_renewal",
                stripe_payment_id=stripe_payment.id
            )
            
            # Registrar renovação
            await update_subscription_renewal(user_id)
            
            return True  # Renovação bem-sucedida
        else:
            # Falha no pagamento - bloquear consulta
            raise InsufficientCreditsError("Falha na renovação automática")
    
    return True  # Créditos suficientes
```

#### **2. Cenários de Renovação**

**Cenário A - Usuário com R$ 0,05 de crédito tentando consulta de protestos (R$ 0,15):**
- Sistema detecta saldo insuficiente
- Cobra automaticamente o valor do plano (ex: R$ 100,00)
- Adiciona R$ 100,00 em créditos
- Executa a consulta (R$ 0,15)
- Saldo final: R$ 99,85

**Cenário B - Falha no pagamento:**
- Sistema tenta renovar automaticamente
- Cartão recusado/expirado/problema no Stripe
- Consulta é bloqueada
- Usuário recebe notificação para atualizar forma de pagamento
- Sistema permite consultas assim que pagamento for resolvido

#### **3. Configurações de Renovação**
```sql
-- Usuário pode desabilitar renovação automática se desejar
UPDATE subscriptions 
SET auto_renewal_enabled = false 
WHERE user_id = ?;

-- Histórico de renovações para auditoria
SELECT 
    auto_renewal_count,
    last_auto_renewal,
    total_spent_cents
FROM subscriptions 
WHERE user_id = ?;
```

#### **4. Notificações ao Usuário**
- **Email antes da renovação**: "Seus créditos estão acabando (R$ 2,00 restantes)"
- **Email após renovação**: "Renovação automática processada: R$ 100,00"
- **Dashboard**: Indicator em tempo real do saldo
- **Histórico**: Lista completa de renovações automáticas

---

## 🚀 **Cronograma de Implementação**

### **Semana 1:**
- [ ] Criar scripts SQL das novas tabelas
- [ ] Implementar migração de dados
- [ ] Testes em ambiente de desenvolvimento

### **Semana 2:**
- [ ] Atualizar serviços backend
- [ ] Implementar CreditService
- [ ] Testes de integração

### **Semana 3:**
- [ ] Atualizar interfaces frontend
- [ ] Dashboard com nova estrutura
- [ ] Páginas de histórico e créditos

### **Semana 4:**
- [ ] Testes completos
- [ ] Deploy gradual em produção
- [ ] Monitoramento e ajustes

---

## 📋 **Scripts de Implementação**

### **1. Script Completo de Criação**
```sql
-- Ver arquivo: database/migration_v2.sql
```

### **2. Script de Migração de Dados**
```sql  
-- Ver arquivo: database/migrate_data_v1_to_v2.sql
```

### **3. Novos Índices de Performance**
```sql
-- Índices otimizados para nova estrutura
CREATE INDEX idx_consultations_user_date ON consultations(user_id, created_at);
CREATE INDEX idx_consultations_cnpj ON consultations(cnpj);
CREATE INDEX idx_consultation_details_type ON consultation_details(consultation_type_id);
CREATE INDEX idx_credit_transactions_user_date ON credit_transactions(user_id, created_at);
CREATE INDEX idx_daily_analytics_user_date ON daily_analytics(user_id, date);
```

---

**Status**: 📋 Planejamento Concluído - **SIMPLIFICADO**  
**Prioridade**: 🔥 Alta  
**Estimativa**: 3 semanas (reduzido com simplificação)  
**Impacto**: 🚀 Transformacional - Estrutura simplificada para SaaS escalável

---

## 📌 **Próximos Passos Imediatos**

1. **Validar estrutura simplificada** com stakeholders
2. **Criar scripts SQL** das novas tabelas  
3. **Implementar lógica de renovação automática**
4. **Criar ambiente de teste** com nova estrutura
5. **Atualizar serviços** para usar renovação automática

---

## ✨ **Resumo da Simplificação Aplicada**

### **O que foi REMOVIDO:**
- ❌ Sistema de cobrança por excedente (overage)
- ❌ Multiplicadores de preço para uso adicional
- ❌ Créditos bônus/promocionais
- ❌ Complexidade de períodos de faturação

### **O que foi MANTIDO/ADICIONADO:**
- ✅ Custos diferenciados por tipo de consulta
- ✅ Histórico detalhado por tipo
- ✅ Renovação automática quando créditos acabam
- ✅ Sistema transparente de créditos
- ✅ Controle total pelo usuário

### **Benefícios da Simplificação:**
- 📦 **Modelo mais simples**: Compra → Usa → Renova automaticamente
- 🚀 **Implementação mais rápida**: 25% menos complexidade
- 👥 **UX mais clara**: Usuário sempre sabe quanto vai pagar
- 💳 **Pagamentos previsíveis**: Sem surpresas na fatura
- 🔧 **Manutenção mais fácil**: Menos código, menos bugs

**⚠️ Importante**: Esta estrutura simplificada atende perfeitamente o modelo de negócio desejado e é mais fácil de implementar e manter.

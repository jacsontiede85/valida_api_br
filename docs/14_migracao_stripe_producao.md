# Plano de Migração Stripe: Teste → Produção

## 📋 Situação Atual

### Problema Identificado
- Os produtos cadastrados na tabela `valida_saas.subscription_plans` foram criados no **modo teste** do Stripe
- As chaves de API foram alteradas para **produção** no `.env`
- ✅ **Produtos de produção já foram criados no Stripe Dashboard**
- ❌ **Os produtos de produção não estão sincronizados na tabela local**
- Sistema está tentando usar IDs de produtos de teste (`prod_T6ANMZkdf6gzQE`, `prod_T6w1fA20Y5N0Mp`, `prod_T6w2idmnU4IBif`) em ambiente de produção

### Impacto
- ❌ Página de assinaturas não carrega produtos corretos
- ❌ Checkout sessions falham ao referenciar produtos inexistentes
- ❌ Usuários não conseguem assinar planos
- ❌ Sistema usa fallback para dados mockados

## 🎯 Objetivos da Migração

1. **🎯 SINCRONIZAR produtos de produção** com tabela `subscription_plans` - **AÇÃO PRINCIPAL**
2. **Corrigir backend** que está usando dados mock de teste
3. **Manter compatibilidade** com assinaturas existentes
4. **Garantir zero downtime** durante migração
5. **Validar funcionamento** completo do sistema

## 📊 Análise Técnica

### Arquitetura Atual
```
Frontend (assinatura.html) 
    ↓
API (/api/v1/stripe/products)
    ↓
Tabela Local (subscription_plans) ← PRINCIPAL
    ↓
Fallback: Stripe Online (IDs hardcoded) ← PROBLEMA
```

### Produtos Identificados no Código
```python
# IDs hardcoded em stripe_routes.py (linha 207-211)
product_ids = [
    "prod_T6ANMZkdf6gzQE",  # R$ 100,00 - TESTE
    "prod_T6w1fA20Y5N0Mp",  # R$ 200,00 - TESTE  
    "prod_T6w2idmnU4IBif"   # R$ 300,00 - TESTE
]
```

### Mapeamento de Preços
```python
# stripe_sync_service.py (linha 21-25)
PRICE_TO_PLAN_MAPPING = {
    10000: "starter",      # R$ 100,00
    20000: "professional", # R$ 200,00
    30000: "enterprise"    # R$ 300,00
}
```

## 🚀 Plano de Ação Detalhado

### FASE 1: Preparação e Análise (15 min)

#### 1.1 Verificar Configuração Atual
```bash
# Verificar variáveis de ambiente
echo $STRIPE_API_KEY_SECRETA
echo $STRIPE_API_KEY_PUBLICAVEL
echo $STRIPE_WEBHOOK_SECRET
```

#### 1.2 Identificar Produtos de Produção
- Acessar Stripe Dashboard (modo produção)
- Listar produtos ativos
- Anotar IDs dos produtos de produção
- Verificar preços e configurações

#### 1.3 Backup da Tabela Atual
```sql
-- Backup da tabela subscription_plans
CREATE TABLE subscription_plans_backup AS 
SELECT * FROM subscription_plans;

-- Verificar dados atuais
SELECT id, code, name, price_cents, stripe_product_id, stripe_price_id 
FROM subscription_plans 
WHERE is_active = 1;
```

### FASE 2: Identificação dos Produtos de Produção (15 min)

#### 2.1 ✅ PRODUTOS JÁ CRIADOS NO STRIPE
**Os produtos de produção já foram criados no Stripe Dashboard.**
Agora precisamos apenas identificar e anotar os IDs corretos:

**Produto 1: Starter (R$ 100,00)**
- ID do Produto: `prod_XXXXX_STARTER`
- ID do Preço: `price_XXXXX_STARTER`

**Produto 2: Professional (R$ 200,00)**
- ID do Produto: `prod_XXXXX_PROFESSIONAL`
- ID do Preço: `price_XXXXX_PROFESSIONAL`

**Produto 3: Enterprise (R$ 300,00)**
- ID do Produto: `prod_XXXXX_ENTERPRISE`
- ID do Preço: `price_XXXXX_ENTERPRISE`

#### 2.2 Verificar Webhooks de Produção
- ✅ Webhooks já configurados em produção
- Verificar se endpoint está funcionando
- Confirmar eventos: `checkout.session.completed`, `invoice.payment_succeeded`

### FASE 3: Correção do Backend - Remover Dados Mock (20 min)

#### 3.1 ✅ FOCO PRINCIPAL: Sincronização Automática
**O sistema já tem sincronização automática implementada.**
O problema é que está usando dados mock/hardcoded de teste.

#### 3.2 Atualizar IDs Hardcoded (Se Necessário)
**Arquivo: `api/routers/stripe_routes.py`**
```python
# Linha 207-211: Substituir IDs de teste pelos de produção
# ⚠️ IMPORTANTE: Estes IDs só são usados no fallback
# O sistema principal usa dados da tabela subscription_plans
product_ids = [
    "prod_XXXXX_STARTER",    # R$ 100,00 - PRODUÇÃO
    "prod_XXXXX_PROFESSIONAL", # R$ 200,00 - PRODUÇÃO
    "prod_XXXXX_ENTERPRISE"   # R$ 300,00 - PRODUÇÃO
]
```

#### 3.3 ✅ PRIORIDADE: Sincronização com Tabela Local
**O sistema principal carrega produtos da tabela `subscription_plans`.**
**A correção principal é sincronizar esta tabela com os produtos de produção.**

### FASE 4: ✅ SINCRONIZAÇÃO AUTOMÁTICA - AÇÃO PRINCIPAL (15 min)

#### 4.1 🎯 EXECUTAR SINCRONIZAÇÃO (MÉTODO PRINCIPAL)
**Este é o passo mais importante da migração!**

```bash
# Via API endpoint - Força sincronização completa
curl -X POST "https://seu-dominio.com/api/v1/stripe/sync-products" \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json"
```

**Ou via interface web:**
- Acessar página de assinaturas
- O sistema deve detectar automaticamente os produtos de produção
- Executar sincronização via endpoint `/api/v1/stripe/sync-products`

#### 4.2 ✅ VERIFICAR SINCRONIZAÇÃO
```sql
-- Verificar produtos sincronizados com IDs de produção
SELECT 
    code, 
    name, 
    price_cents, 
    stripe_product_id, 
    stripe_price_id,
    is_active,
    created_at,
    updated_at
FROM subscription_plans 
WHERE stripe_product_id IS NOT NULL
ORDER BY price_cents;
```

#### 4.3 🔍 VALIDAR SINCRONIZAÇÃO
- ✅ Produtos devem ter `stripe_product_id` preenchido
- ✅ IDs devem começar com `prod_` (não `prod_T6...` de teste)
- ✅ `stripe_price_id` deve estar preenchido
- ✅ `is_active = 1` para todos os produtos

### FASE 5: ✅ CORREÇÃO MANUAL (Se Necessário) (10 min)

#### 5.1 ⚠️ APENAS SE SINCRONIZAÇÃO AUTOMÁTICA FALHAR
**A sincronização automática deve resolver o problema.**
**Use esta fase apenas se houver problemas específicos.**

#### 5.2 Correção Manual de IDs (Último Recurso)
```sql
-- ⚠️ SUBSTITUIR pelos IDs reais de produção
-- Obter IDs corretos do Stripe Dashboard primeiro

-- Atualizar produtos existentes com IDs de produção
UPDATE subscription_plans 
SET 
    stripe_product_id = 'prod_XXXXX_STARTER',
    stripe_price_id = 'price_XXXXX_STARTER',
    updated_at = NOW()
WHERE code = 'starter';

UPDATE subscription_plans 
SET 
    stripe_product_id = 'prod_XXXXX_PROFESSIONAL', 
    stripe_price_id = 'price_XXXXX_PROFESSIONAL',
    updated_at = NOW()
WHERE code = 'professional';

UPDATE subscription_plans 
SET 
    stripe_product_id = 'prod_XXXXX_ENTERPRISE',
    stripe_price_id = 'price_XXXXX_ENTERPRISE', 
    updated_at = NOW()
WHERE code = 'enterprise';
```

#### 5.3 ✅ VERIFICAÇÃO PÓS-CORREÇÃO
```sql
-- Verificar se correção foi aplicada
SELECT code, stripe_product_id, stripe_price_id 
FROM subscription_plans 
WHERE is_active = 1;
```

### FASE 6: Validação e Testes (30 min)

#### 6.1 Testes de API
```bash
# Testar endpoint de produtos
curl -H "Authorization: Bearer TOKEN" \
  "https://seu-dominio.com/api/v1/stripe/products"

# Testar endpoint de sincronização
curl -X POST -H "Authorization: Bearer TOKEN" \
  "https://seu-dominio.com/api/v1/stripe/sync-status"
```

#### 6.2 Testes de Frontend
- Acessar página `/assinatura`
- Verificar se produtos carregam corretamente
- Testar botão "Selecionar Plano"
- Verificar redirecionamento para checkout

#### 6.3 Testes de Checkout
- Criar sessão de checkout de teste
- Verificar se redireciona para Stripe correto
- Testar com cartão de teste do Stripe

### FASE 7: Monitoramento Pós-Migração (Contínuo)

#### 7.1 Logs a Monitorar
```bash
# Verificar logs de sincronização
tail -f logs/service-output.log | grep "stripe"

# Verificar logs de webhook
tail -f logs/service-output.log | grep "webhook"
```

#### 7.2 Métricas de Sucesso
- ✅ Produtos carregam na página de assinaturas
- ✅ Checkout sessions são criadas com sucesso
- ✅ Webhooks processam pagamentos
- ✅ Créditos são adicionados automaticamente
- ✅ Zero erros relacionados a produtos não encontrados

## 🔧 Scripts de Apoio

### Script de Verificação
```python
# verify_stripe_migration.py
import stripe
import os
from api.database.connection import execute_sql

async def verify_migration():
    """Verifica se migração foi bem-sucedida"""
    
    # 1. Verificar configuração Stripe
    stripe.api_key = os.getenv("STRIPE_API_KEY_SECRETA")
    if not stripe.api_key:
        print("❌ Stripe não configurado")
        return False
    
    # 2. Listar produtos do Stripe
    products = stripe.Product.list(active=True)
    print(f"✅ {len(products.data)} produtos ativos no Stripe")
    
    # 3. Verificar produtos no banco
    sql = "SELECT COUNT(*) as total FROM subscription_plans WHERE stripe_product_id IS NOT NULL AND is_active = 1"
    result = await execute_sql(sql, (), "one")
    print(f"✅ {result['data']['total']} produtos sincronizados no banco")
    
    # 4. Verificar mapeamento
    for product in products.data:
        prices = stripe.Price.list(product=product.id, active=True)
        if prices.data:
            price = prices.data[0]
            print(f"✅ {product.name}: {price.unit_amount/100:.2f} BRL")
    
    return True
```

### Script de Rollback
```sql
-- rollback_migration.sql
-- Restaurar backup se necessário
DROP TABLE subscription_plans;
RENAME TABLE subscription_plans_backup TO subscription_plans;

-- Ou reverter IDs para teste
UPDATE subscription_plans 
SET 
    stripe_product_id = 'prod_T6ANMZkdf6gzQE',
    stripe_price_id = 'price_fallback_100'
WHERE code = 'starter';
```

## ⚠️ Riscos e Mitigações

### Riscos Identificados
1. **Produtos não encontrados**: IDs de teste em produção
2. **Assinaturas quebradas**: Referências a produtos inexistentes  
3. **Downtime**: Sistema indisponível durante migração
4. **Perda de dados**: Backup inadequado

### Mitigações
1. **Backup completo** antes da migração
2. **Testes em ambiente de staging** primeiro
3. **Rollback plan** detalhado
4. **Monitoramento ativo** durante migração
5. **Comunicação com usuários** sobre manutenção

## 📅 Cronograma Estimado (ATUALIZADO)

| Fase | Duração | Responsável | Status | Observação |
|------|---------|-------------|--------|------------|
| Preparação | 15 min | Dev | ⏳ Pendente | Backup e análise |
| Identificação Produtos | 15 min | Dev | ⏳ Pendente | ✅ Produtos já criados |
| Correção Backend | 20 min | Dev | ⏳ Pendente | Remover dados mock |
| **Sincronização** | **15 min** | **Dev** | **⏳ Pendente** | **🎯 AÇÃO PRINCIPAL** |
| Correção Manual | 10 min | Dev | ⏳ Pendente | Apenas se necessário |
| Validação | 30 min | Dev | ⏳ Pendente | Testes completos |
| **TOTAL** | **1h 45min** | | | **Reduzido de 2h 10min** |

## ✅ Checklist Final (ATUALIZADO)

- [ ] Backup da tabela `subscription_plans` criado
- [x] ✅ Produtos criados no Stripe Dashboard (produção) - **JÁ FEITO**
- [x] ✅ Webhooks configurados em produção - **JÁ FEITO**
- [ ] IDs de produção identificados e anotados
- [ ] **🎯 SINCRONIZAÇÃO executada com sucesso** - **AÇÃO PRINCIPAL**
- [ ] Produtos aparecem na página de assinaturas
- [ ] Checkout funciona corretamente
- [ ] Logs limpos sem erros
- [ ] Testes de pagamento realizados
- [ ] Documentação atualizada

## 🎯 Próximos Passos (ATUALIZADO)

1. **Executar FASE 1**: Preparação e análise (backup)
2. **Identificar IDs** dos produtos já criados no Stripe
3. **🎯 EXECUTAR SINCRONIZAÇÃO** - Ação principal via API
4. **Validar sincronização** na tabela `subscription_plans`
5. **Testar funcionamento** completo da página de assinaturas
6. **Monitorar** por 24h após migração

### ⚡ AÇÃO IMEDIATA
**O passo mais importante é executar a sincronização automática:**
```bash
curl -X POST "https://seu-dominio.com/api/v1/stripe/sync-products" \
  -H "Authorization: Bearer SEU_TOKEN"
```

---

**⚠️ IMPORTANTE**: Este plano deve ser executado em horário de baixo tráfego e com backup completo do banco de dados.

# Plano de Ação - Correção Assinatura Plano Customizado

## 📋 **Problema Identificado**

**Situação Atual:**
- ✅ Usuário `jacsontiede@valida.api.br` tem assinatura ativa no Stripe por **R$ 10,00**
- ❌ Frontend exibe assinatura de **R$ 500,00** (valor incorreto)
- ❌ Plano customizado de R$ 10,00 **NÃO foi criado** na tabela `subscription_plans`

**Dados Encontrados:**
```
Usuário: jacsontiede@valida.api.br (ID: dc573a39-48df-4d81-a2da-9049f64b6477)
Assinatura Ativa:
  - Status: active
  - Plano: Crédito 500 reais (INCORRETO)
  - Código: custom
  - Preço: R$ 500.00 (INCORRETO)
  - Stripe Subscription ID: sub_1SBaH0AS0N7jA0Z3FnN7uZ3M
  - Stripe Price ID: price_1SBaFRAS0N7jA0Z3230tkoY8
  - Stripe Product ID: prod_T7pcheo3Fj5oAp (produto de R$ 500,00)
```

## 🔍 **Análise da Causa Raiz**

### **Problema Principal:**
O sistema está mapeando incorretamente a assinatura de R$ 10,00 para o plano de R$ 500,00 devido a:

1. **Falta de Plano Customizado**: Não existe plano de R$ 10,00 na tabela `subscription_plans`
2. **Mapeamento Incorreto**: Sistema está associando a assinatura ao plano `enterprise` (R$ 500,00)
3. **Processamento Manual Falhou**: O webhook ou processamento manual não criou o plano customizado

### **Fluxo Problemático:**
```
Stripe (R$ 10,00) → Processamento → Plano Enterprise (R$ 500,00) → Frontend (R$ 500,00)
```

### **Fluxo Correto Esperado:**
```
Stripe (R$ 10,00) → Criar Plano Custom → Plano Custom (R$ 10,00) → Frontend (R$ 10,00)
```

## 🎯 **Objetivos da Correção**

1. **Criar plano customizado** de R$ 10,00 na tabela `subscription_plans`
2. **Corrigir associação** da assinatura para o plano correto
3. **Atualizar dados** para refletir valor real (R$ 10,00)
4. **Garantir sincronização** entre Stripe e banco local
5. **Validar frontend** exibe dados corretos

## 📋 **Plano de Ação Detalhado**

### **FASE 1: Investigação Detalhada**
- [ ] **1.1** Verificar dados reais no Stripe da assinatura `sub_1SBaH0AS0N7jA0Z3FnN7uZ3M`
- [ ] **1.2** Confirmar valor real pago (R$ 10,00)
- [ ] **1.3** Identificar Product ID e Price ID corretos no Stripe
- [ ] **1.4** Verificar logs de processamento da assinatura

### **FASE 2: Criação do Plano Customizado**
- [ ] **2.1** Criar plano customizado na tabela `subscription_plans`:
  ```sql
  INSERT INTO subscription_plans (
    id, code, name, description, price_cents, credits_included_cents,
    stripe_product_id, stripe_price_id, user_id, is_active
  ) VALUES (
    'uuid', 'custom_10', 'Crédito 10 reais', 'R$ 10,00 em créditos mensais',
    1000, 1000, 'prod_id_real', 'price_id_real', 'user_id', 1
  )
  ```

### **FASE 3: Correção da Associação**
- [ ] **3.1** Atualizar tabela `subscriptions` para apontar para o plano correto:
  ```sql
  UPDATE subscriptions 
  SET plan_id = 'novo_plano_id', stripe_price_id = 'price_id_real'
  WHERE stripe_subscription_id = 'sub_1SBaH0AS0N7jA0Z3FnN7uZ3M'
  ```

### **FASE 4: Validação e Testes**
- [ ] **4.1** Verificar dados no banco após correção
- [ ] **4.2** Testar API `/api/v1/stripe/subscription/current`
- [ ] **4.3** Validar frontend exibe R$ 10,00
- [ ] **4.4** Verificar créditos do usuário

### **FASE 5: Prevenção de Problemas Futuros**
- [ ] **5.1** Melhorar lógica de criação de planos customizados
- [ ] **5.2** Adicionar logs detalhados no processamento
- [ ] **5.3** Implementar validação de valores entre Stripe e banco
- [ ] **5.4** Criar endpoint de diagnóstico para assinaturas

## 🛠️ **Implementação Técnica**

### **Script de Correção:**
```python
async def fix_custom_subscription():
    # 1. Buscar dados reais no Stripe
    subscription = stripe.Subscription.retrieve('sub_1SBaH0AS0N7jA0Z3FnN7uZ3M')
    items = stripe.SubscriptionItem.list(subscription=subscription.id)
    price = items.data[0].price
    product = stripe.Product.retrieve(price.product)
    
    # 2. Criar plano customizado
    plan_id = generate_uuid()
    await execute_sql("""
        INSERT INTO subscription_plans 
        (id, code, name, description, price_cents, credits_included_cents,
         stripe_product_id, stripe_price_id, user_id, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
    """, (plan_id, 'custom_10', product.name, product.description,
          price.unit_amount, price.unit_amount, product.id, price.id,
          'dc573a39-48df-4d81-a2da-9049f64b6477'))
    
    # 3. Atualizar assinatura
    await execute_sql("""
        UPDATE subscriptions 
        SET plan_id = %s, stripe_price_id = %s
        WHERE stripe_subscription_id = %s
    """, (plan_id, price.id, subscription.id))
```

### **Validação:**
```python
async def validate_fix():
    # Verificar assinatura corrigida
    result = await execute_sql("""
        SELECT s.*, sp.name, sp.price_cents
        FROM subscriptions s
        JOIN subscription_plans sp ON s.plan_id = sp.id
        WHERE s.stripe_subscription_id = 'sub_1SBaH0AS0N7jA0Z3FnN7uZ3M'
    """, (), "one")
    
    assert result['data']['price_cents'] == 1000  # R$ 10,00
    print("✅ Correção validada com sucesso!")
```

## ⚠️ **Riscos e Mitigações**

### **Riscos:**
- **Perda de dados**: Alteração incorreta pode afetar histórico
- **Inconsistência**: Dados podem ficar dessincronizados
- **Downtime**: Sistema pode ficar indisponível durante correção

### **Mitigações:**
- **Backup completo** antes de qualquer alteração
- **Transações atômicas** para garantir consistência
- **Validação rigorosa** após cada etapa
- **Rollback plan** em caso de problemas

## 📊 **Critérios de Sucesso**

### **Validação Final:**
- [ ] ✅ Frontend exibe "Crédito 10 reais" (R$ 10,00)
- [ ] ✅ API retorna valor correto (1000 centavos)
- [ ] ✅ Banco local sincronizado com Stripe
- [ ] ✅ Créditos do usuário calculados corretamente
- [ ] ✅ Logs mostram processamento correto

### **Métricas:**
- **Tempo de correção**: < 30 minutos
- **Downtime**: 0 segundos
- **Precisão**: 100% dos dados corretos
- **Cobertura**: Todos os endpoints funcionando

## 🚀 **Próximos Passos**

1. **Executar investigação** detalhada no Stripe
2. **Implementar script** de correção
3. **Validar resultados** em ambiente de teste
4. **Aplicar correção** em produção
5. **Monitorar sistema** por 24h

---

## 🔧 **CORREÇÃO ADICIONAL NECESSÁRIA: Novas Assinaturas**

### **❌ Problema Identificado:**
Após análise mais profunda, foi descoberto que **o problema ainda existe para novas assinaturas customizadas** devido ao mapeamento hardcoded no código.

### **🎯 Causa Raiz:**
```python
# Código problemático em stripe_routes.py (linha 897-903)
plan_mapping = {
    10000: "starter",      # R$ 100,00
    20000: "professional", # R$ 200,00  
    30000: "enterprise"    # R$ 300,00
}

plan_code = plan_mapping.get(price_amount_cents, "custom")  # ❌ PROBLEMA AQUI!
```

**Fluxo problemático para novas assinaturas:**
1. Usuário cria assinatura de R$ 15,00
2. Sistema mapeia para `"custom"` (não está no mapeamento)
3. Busca plano com `code = "custom"`
4. **Encontra plano "custom" existente (R$ 500,00)**
5. **Usa plano errado!**

### **🛠️ Solução Necessária:**

#### **FASE 6: Correção do Mapeamento Dinâmico**
- [ ] **6.1** Atualizar função `process_subscription_manually()` em `stripe_routes.py`
- [ ] **6.2** Substituir mapeamento hardcoded por lógica dinâmica:
  ```python
  # ✅ CÓDIGO CORRETO (dinâmico)
  if price_amount_cents in [10000, 20000, 30000]:
      plan_mapping = {
          10000: "starter",
          20000: "professional",  
          30000: "enterprise"
      }
      plan_code = plan_mapping[price_amount_cents]
  else:
      # Para valores customizados, criar código único
      plan_code = f"custom_{price_amount_cents}"
  ```
- [ ] **6.3** Atualizar função `create_dynamic_product()` com mesma lógica
- [ ] **6.4** Testar com diferentes valores customizados (R$ 15, R$ 50, R$ 75, etc.)
- [ ] **6.5** Validar que não quebra planos existentes

#### **FASE 7: Validação Completa**
- [ ] **7.1** Testar criação de assinatura R$ 15,00
- [ ] **7.2** Verificar que cria plano `custom_1500` específico
- [ ] **7.3** Confirmar que não conflita com outros planos
- [ ] **7.4** Validar frontend exibe valor correto
- [ ] **7.5** Testar múltiplos valores customizados simultaneamente

### **🎯 Benefícios da Correção:**
- ✅ **Cada valor customizado** terá seu próprio plano
- ✅ **Evita conflitos** entre planos customizados
- ✅ **Sistema mais robusto** e escalável
- ✅ **Previne problemas futuros** automaticamente
- ✅ **Suporte a qualquer valor** entre R$ 10,00 e R$ 10.000,00

### **📋 Implementação Técnica:**

#### **Arquivos a Modificar:**
1. `api/routers/stripe_routes.py` - Função `process_subscription_manually()`
2. `api/routers/stripe_routes.py` - Função `create_dynamic_product()`

#### **Script de Teste:**
```python
async def test_custom_subscriptions():
    """Testa criação de múltiplos planos customizados"""
    test_values = [1500, 2500, 5000, 7500]  # R$ 15, R$ 25, R$ 50, R$ 75
    
    for amount_cents in test_values:
        # Simular processamento
        plan_code = f"custom_{amount_cents}"
        
        # Verificar se plano é criado corretamente
        result = await execute_sql(
            "SELECT * FROM subscription_plans WHERE code = %s",
            (plan_code,), "one"
        )
        
        assert result['data']['price_cents'] == amount_cents
        print(f"✅ Plano {plan_code} criado corretamente")
```

### **⚠️ Riscos Adicionais:**
- **Conflito com planos existentes**: Mitigado com códigos únicos
- **Performance**: Muitos planos customizados podem impactar queries
- **Manutenção**: Mais planos para gerenciar

### **📊 Critérios de Sucesso Adicionais:**
- [ ] ✅ Novas assinaturas R$ 15,00 criam plano `custom_1500`
- [ ] ✅ Novas assinaturas R$ 50,00 criam plano `custom_5000`
- [ ] ✅ Não há conflitos entre planos customizados
- [ ] ✅ Sistema suporta até 1000 planos customizados diferentes
- [ ] ✅ Performance mantida (< 100ms para busca de planos)

---

**Status**: 🔍 **Análise Concluída** - Pronto para implementação
**Prioridade**: 🔴 **Alta** - Afeta experiência do usuário
**Estimativa**: ⏱️ **45 minutos** - Correção rápida e segura (incluindo prevenção)

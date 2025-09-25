# Plano de Integração Stripe - Sistema de Créditos Recorrentes

## Análise da Implementação Atual

### ✅ **Já Implementado**
1. **Interface HTML completa** (`assinatura.html`):
   - Template dinâmico para planos
   - Seção de assinatura atual com créditos
   - Toggle de renovação automática
   - Histórico de transações recentes
   - Integração com Stripe SDK

2. **JavaScript funcional** (`assinatura.js`):
   - Classe `AssinaturaManager` completa
   - Carregamento de planos e custos
   - Criação de checkout sessions
   - Gerenciamento de auto-renewal
   - Notificações toast

3. **Backend básico** (`stripe_routes.py`):
   - Endpoints de API estruturados
   - Integração com Supabase
   - Retorno de dados mockados (funcional para testes)

4. **Schema de banco completo** (`bd.sql`):
   - Tabela `users` com campo `credits`
   - Tabela `credit_transactions` para histórico
   - Triggers para atualização automática de saldo
   - Views para relatórios

## 🎯 **Objetivo do Sistema**

**Sistema baseado em créditos com assinaturas recorrentes:**
- Cada consulta consome créditos (R$)
- Usuários assinam valores fixos mensais de créditos
- 3 planos padrão + 1 opção personalizada
- Renovação automática via Stripe

## 📋 **Plano de Implementação**

### **FASE 1: Configuração Stripe Real**

#### 1.1. Criar Produtos no Stripe Dashboard
```javascript
// Produtos a serem criados no Stripe Dashboard
const stripeProducts = [
  {
    name: "Créditos R$ 29,90",
    description: "Plano básico - R$ 29,90 em créditos mensais",
    price: 2990, // centavos
    recurring: "month"
  },
  {
    name: "Créditos R$ 99,90", 
    description: "Plano profissional - R$ 99,90 em créditos mensais",
    price: 9990,
    recurring: "month"
  },
  {
    name: "Créditos R$ 299,90",
    description: "Plano empresarial - R$ 299,90 em créditos mensais", 
    price: 29990,
    recurring: "month"
  }
]
```

#### 1.2. Atualizar Backend para Stripe Real
**Arquivo:** `api/routers/stripe_routes.py`

- ✅ Variáveis já configuradas: `STRIPE_API_KEY_SECRETA`, `STRIPE_API_KEY_PUBLICAVEL`
- ⚠️ **AÇÃO:** Substituir dados mockados por chamadas reais ao Stripe
- ⚠️ **AÇÃO:** Implementar webhook handler para eventos de assinatura

### **FASE 2: Sistema de Planos + Opção Personalizada**

#### 2.1. Modificar Interface (assinatura.html)
**Template já existe, apenas adicionar:**
```html
<!-- Após os 3 planos padrão -->
<div class="custom-plan-card bg-gradient-to-r from-purple-600 to-blue-600 rounded-lg p-6">
  <h3 class="text-xl font-bold mb-4">Plano Personalizado</h3>
  <div class="mb-4">
    <label class="block text-sm font-medium mb-2">Valor mensal em créditos:</label>
    <div class="flex items-center">
      <span class="text-lg">R$</span>
      <input 
        type="number" 
        id="custom-amount" 
        min="10" 
        step="0.01" 
        class="ml-2 bg-gray-700 border border-gray-600 rounded px-3 py-2 w-32"
        placeholder="0,00"
      >
    </div>
  </div>
  <button id="custom-plan-btn" class="w-full bg-purple-600 hover:bg-purple-700 py-3 rounded-lg font-medium">
    Assinar Valor Personalizado
  </button>
</div>
```

#### 2.2. Atualizar JavaScript (assinatura.js)
**Já implementado - apenas adicionar:**
```javascript
// No setupEventListeners(), adicionar:
document.getElementById('custom-plan-btn').addEventListener('click', () => {
  const amount = document.getElementById('custom-amount').value;
  if (amount >= 10) {
    this.handleCustomPlanSelection(parseFloat(amount));
  }
});

async handleCustomPlanSelection(amount) {
  // Criar produto/preço dinâmico no Stripe
  // Redirecionar para checkout
}
```

### **FASE 3: Integração Stripe Completa**

#### 3.1. Implementar Rotas Backend Reais

**Endpoint para produtos reais:**
```python
@router.get("/products")
async def get_stripe_products():
    """Buscar produtos reais do Stripe"""
    try:
        products = stripe.Product.list(active=True)
        prices = stripe.Price.list(active=True)
        
        return {
            "products": products.data,
            "prices": {price.id: price for price in prices.data}
        }
    except Exception as e:
        logger.error(f"Erro Stripe: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Endpoint para checkout real:**
```python
@router.post("/create-checkout-session")
async def create_checkout_session(request: CheckoutSessionRequest, user: AuthUser = Depends(require_auth)):
    try:
        # Buscar cliente Stripe ou criar novo
        customer_id = await get_or_create_stripe_customer(user)
        
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{
                'price': request.price_id,
                'quantity': 1,
            }],
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={
                'user_id': user.user_id
            }
        )
        
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        logger.error(f"Erro ao criar checkout: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

#### 3.2. Implementar Webhooks Stripe
**Novo arquivo:** `api/routers/stripe_webhooks.py`
```python
@router.post("/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        
        if event['type'] == 'invoice.payment_succeeded':
            await handle_payment_succeeded(event['data']['object'])
        elif event['type'] == 'customer.subscription.created':
            await handle_subscription_created(event['data']['object'])
        # ... outros eventos
        
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

async def handle_payment_succeeded(invoice):
    """Adicionar créditos quando pagamento for bem-sucedido"""
    customer_id = invoice['customer']
    amount_paid = invoice['amount_paid'] / 100  # converter de centavos
    
    # Buscar usuário por stripe_customer_id
    user = await get_user_by_stripe_customer(customer_id)
    
    # Adicionar créditos
    await add_user_credits(user.user_id, amount_paid, "Pagamento de assinatura processado")
```

### **FASE 4: Sistema de Créditos Automatizado**

#### 4.1. Trigger de Atualização já Implementado
**Arquivo:** `bd.sql` (linhas 272-299)
- ✅ Trigger automático para atualizar `users.credits` 
- ✅ Cálculo de saldo em `credit_transactions`

#### 4.2. Serviços de Crédito
**Novo arquivo:** `api/services/credit_service.py`
```python
async def add_user_credits(user_id: str, amount: float, description: str):
    """Adicionar créditos via transação"""
    supabase = get_supabase_client()
    
    # Inserir transação - trigger atualizará o saldo automaticamente
    await supabase.table("credit_transactions").insert({
        "user_id": user_id,
        "type": "purchase",
        "amount_cents": int(amount * 100),
        "description": description
    }).execute()

async def consume_credits(user_id: str, amount: float, description: str, consultation_id: str = None):
    """Consumir créditos em uma consulta"""
    # Verificar saldo disponível
    user_credits = await get_user_credits(user_id)
    if user_credits < amount:
        raise HTTPException(status_code=402, detail="Créditos insuficientes")
    
    # Registrar consumo
    await supabase.table("credit_transactions").insert({
        "user_id": user_id,
        "consultation_id": consultation_id,
        "type": "spend",
        "amount_cents": int(-amount * 100),  # Negativo para debitar
        "description": description
    }).execute()
```

### **FASE 5: Opção Personalizada Dinâmica**

#### 5.1. Criar Preços Dinâmicos no Stripe
```python
@router.post("/create-custom-subscription")
async def create_custom_subscription(amount: float, user: AuthUser = Depends(require_auth)):
    """Criar assinatura personalizada"""
    try:
        # Criar preço dinâmico no Stripe
        price = stripe.Price.create(
            unit_amount=int(amount * 100),
            currency='brl',
            recurring={'interval': 'month'},
            product_data={
                'name': f'Créditos Personalizados R$ {amount:.2f}',
                'description': f'Plano personalizado de R$ {amount:.2f} em créditos mensais'
            },
            metadata={
                'custom_plan': 'true',
                'user_id': user.user_id
            }
        )
        
        # Criar checkout session com o novo preço
        return await create_checkout_session(
            CheckoutSessionRequest(price_id=price.id), user
        )
    except Exception as e:
        logger.error(f"Erro ao criar plano personalizado: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### **FASE 6: Testes e Deployment**

#### 6.1. Checklist de Testes
- [ ] **Stripe Test Mode:** Configurar chaves de teste primeiro
- [ ] **Webhooks:** Testar com ngrok ou webhook test
- [ ] **Fluxo completo:** Assinatura → Pagamento → Créditos adicionados
- [ ] **Cancelamento:** Testar cancelamento via Customer Portal
- [ ] **Renovação:** Verificar renovação automática

#### 6.2. Configuração de Produção
```env
# Desenvolvimento
STRIPE_API_KEY_PUBLICAVEL=pk_test_...
STRIPE_API_KEY_SECRETA=sk_test_...

# Produção  
STRIPE_API_KEY_PUBLICAVEL=pk_live_...
STRIPE_API_KEY_SECRETA=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

## 🚀 **Resumo da Implementação**

### **O que já funciona:**
1. ✅ Interface completa e responsiva
2. ✅ JavaScript com todas as funcionalidades
3. ✅ Backend com APIs estruturadas
4. ✅ Banco de dados com triggers automáticos
5. ✅ Sistema de créditos implementado

### **O que precisa ser feito:**
1. ⚠️ **Substituir dados mockados por Stripe real** (1-2 dias)
2. ⚠️ **Implementar webhooks** (1 dia)  
3. ⚠️ **Adicionar opção de plano personalizado** (0.5 dia)
4. ⚠️ **Testes completos** (1 dia)

### **Estimativa total:** 3-4 dias para implementação completa

### **Próximas ações imediatas:**
1. Criar produtos no Stripe Dashboard
2. Obter IDs dos preços criados
3. Atualizar `stripe_routes.py` com chamadas reais
4. Configurar webhook endpoint
5. Testar fluxo completo em modo teste



PRODUTO_ID: prod_T6w2idmnU4IBif (300,00)
PRODUTO_ID: prod_T6w1fA20Y5N0Mp (200,00)
PRODUTO_ID: prod_T6ANMZkdf6gzQE (100,00)
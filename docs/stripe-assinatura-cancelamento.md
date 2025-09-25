# Documentação Completa: Assinatura e Cancelamento de Planos Recorrentes no Stripe

## Visão Geral

Este guia aborda todos os aspectos práticos de como assinar planos recorrentes e cancelar assinaturas no Stripe, incluindo implementações via API, Dashboard e diferentes cenários de uso.

## 1. Criação de Assinaturas

### 1.1 Assinatura Básica via API

**Método Direto**:

```javascript
const subscription = await stripe.subscriptions.create({
  customer: 'cus_customer_id', // ID do cliente existente
  items: [{
    price: 'price_1234567890', // ID do preço/plano
    quantity: 1
  }],
  collection_method: 'charge_automatically'
});
```

**Com Checkout Session**:

```javascript
const session = await stripe.checkout.sessions.create({
  success_url: 'https://seusite.com/sucesso?session_id={CHECKOUT_SESSION_ID}',
  cancel_url: 'https://seusite.com/cancelado',
  mode: 'subscription',
  line_items: [{
    price: 'price_1234567890',
    quantity: 1,
  }]
});
```

### 1.2 Assinatura com Período de Teste Gratuito

**Via API - Dias de Teste**:

```javascript
const subscription = await stripe.subscriptions.create({
  customer: 'cus_customer_id',
  items: [{
    price: 'price_1234567890'
  }],
  trial_period_days: 30 // 30 dias de teste gratuito
});
```

**Via API - Data Específica de Fim**:

```javascript
const trialEnd = Math.floor(Date.now() / 1000) + (30 * 24 * 60 * 60); // 30 dias
const subscription = await stripe.subscriptions.create({
  customer: 'cus_customer_id',
  items: [{
    price: 'price_1234567890'
  }],
  trial_end: trialEnd
});
```

**Via Checkout com Teste**:

```javascript
const session = await stripe.checkout.sessions.create({
  success_url: 'https://seusite.com/sucesso',
  cancel_url: 'https://seusite.com/cancelado',
  mode: 'subscription',
  line_items: [{
    price: 'price_1234567890',
    quantity: 1,
  }],
  subscription_data: {
    trial_period_days: 14 // 14 dias de teste
  }
});
```

### 1.3 Assinatura via Dashboard

1. **Acesse** Stripe Dashboard > **Clientes**
2. **Selecione** o cliente desejado
3. **Clique** em "**Criar assinatura**"
4. **Escolha** o produto e preço
5. **Configure** período de teste (opcional):
   - Marque "**Adicionar período de teste**"
   - Defina número de dias
6. **Clique** em "**Criar assinatura**"

## 2. Estados da Assinatura

### 2.1 Estados Principais

| Status | Descrição | Ação Necessária |
|--------|-----------|-----------------|
| `incomplete` | Aguardando primeiro pagamento | Confirmar método de pagamento |
| `trialing` | Em período de teste | Monitorar término do teste |
| `active` | Ativa e cobrando | Manter serviço disponível |
| `past_due` | Pagamento em atraso | Solicitar atualização ou suspender |
| `canceled` | Cancelada permanentemente | Revogar acesso |
| `unpaid` | Não paga após tentativas | Bloquear acesso |

### 2.2 Eventos de Webhook Importantes

```javascript
// Processar eventos de assinatura
const handleWebhook = (event) => {
  switch (event.type) {
    case 'customer.subscription.created':
      // Nova assinatura criada
      provisionarAcesso(event.data.object.customer);
      break;
      
    case 'customer.subscription.trial_will_end':
      // Teste terminará em 3 dias
      enviarLembreteTesteTerminando(event.data.object.customer);
      break;
      
    case 'invoice.payment_succeeded':
      // Pagamento bem-sucedido
      manterAcessoAtivo(event.data.object.customer);
      break;
      
    case 'invoice.payment_failed':
      // Falha no pagamento
      notificarFalhaPagamento(event.data.object.customer);
      break;
      
    case 'customer.subscription.deleted':
      // Assinatura cancelada
      revogarAcesso(event.data.object.customer);
      break;
  }
};
```

## 3. Pausar Assinaturas

### 3.1 Pausar Cobrança (Manter Assinatura Ativa)

**Via API**:

```javascript
const subscription = await stripe.subscriptions.update('sub_1234567890', {
  pause_collection: {
    behavior: 'void', // 'void', 'keep_as_draft', 'mark_uncollectible'
    resumes_at: Math.floor(Date.now() / 1000) + (30 * 24 * 60 * 60) // Retomar em 30 dias
  }
});
```

**Opções de Comportamento**:
- `void`: Anula faturas criadas durante pausa (serviço gratuito)
- `keep_as_draft`: Mantém faturas como rascunho para cobrança posterior
- `mark_uncollectible`: Marca faturas como incobráveis

**Via Dashboard**:
1. **Acesse** a assinatura
2. **Clique** nos três pontos (⋯) no canto superior direito
3. **Selecione** "**Pausar cobrança de pagamentos**"
4. **Configure** data de retomada (opcional)

### 3.2 Retomar Cobrança

```javascript
const subscription = await stripe.subscriptions.update('sub_1234567890', {
  pause_collection: null
});
```

## 4. Cancelamento de Assinaturas

### 4.1 Cancelamento Imediato

**Via API**:

```javascript
const subscription = await stripe.subscriptions.cancel('sub_1234567890', {
  prorate: true, // true para prorratear, false para não prorratear
  invoice_now: true // true para faturar imediatamente as prorratações
});
```

**Via Dashboard**:
1. **Acesse** Assinaturas > **Selecione** a assinatura
2. **Clique** no menu (⋯) > "**Cancelar assinatura**"
3. **Escolha** "**Imediatamente**"
4. **Configure** reembolso (se aplicável)

### 4.2 Cancelamento no Final do Período

**Via API**:

```javascript
const subscription = await stripe.subscriptions.update('sub_1234567890', {
  cancel_at_period_end: true
});
```

**Reativar Cancelamento Programado**:

```javascript
const subscription = await stripe.subscriptions.update('sub_1234567890', {
  cancel_at_period_end: false
});
```

**Via Dashboard**:
1. **Selecione** "**No final do período**" ao cancelar
2. Para reativar: **Ações** > "**Não cancelar**"

### 4.3 Cancelamento em Data Específica

```javascript
const cancelDate = Math.floor(Date.now() / 1000) + (7 * 24 * 60 * 60); // 7 dias
const subscription = await stripe.subscriptions.update('sub_1234567890', {
  cancel_at: cancelDate
});
```

### 4.4 Cancelamento com Reembolso

```javascript
// 1. Cancelar assinatura
const subscription = await stripe.subscriptions.cancel('sub_1234567890', {
  prorate: true,
  invoice_now: true
});

// 2. Criar reembolso se necessário
if (subscription.status === 'canceled') {
  const refund = await stripe.refunds.create({
    charge: 'ch_charge_id', // ID da cobrança a ser reembolsada
    amount: 2500 // Valor em centavos (R$ 25,00)
  });
}
```

## 5. Atualização de Assinaturas

### 5.1 Mudança de Plano

**Upgrade Imediato**:

```javascript
const subscription = await stripe.subscriptions.update('sub_1234567890', {
  items: [{
    id: 'si_item_id', // ID do item atual da assinatura
    price: 'price_novo_plano' // Novo preço/plano
  }],
  proration_behavior: 'always_invoice' // Faturar prorratação imediatamente
});
```

**Mudança para Próximo Período**:

```javascript
const subscription = await stripe.subscriptions.update('sub_1234567890', {
  items: [{
    id: 'si_item_id',
    price: 'price_novo_plano'
  }],
  proration_behavior: 'none', // Sem prorratação
  billing_cycle_anchor: 'unchanged' // Manter ciclo atual
});
```

### 5.2 Alterar Quantidade

```javascript
const subscription = await stripe.subscriptions.update('sub_1234567890', {
  items: [{
    id: 'si_item_id',
    quantity: 5 // Nova quantidade
  }]
});
```

## 6. Gerenciamento via Customer Portal

### 6.1 Configurar Portal do Cliente

```javascript
const portalSession = await stripe.billingPortal.sessions.create({
  customer: 'cus_customer_id',
  return_url: 'https://seusite.com/conta'
});

// Redirecionar cliente para: portalSession.url
```

### 6.2 Configurações do Portal

**No Dashboard**:
1. **Acesse** Configurações > **Faturamento** > **Portal do cliente**
2. **Configure** permissões:
   - ✅ Cancelar assinaturas
   - ✅ Pausar assinaturas
   - ✅ Alterar planos
   - ✅ Atualizar métodos de pagamento
   - ✅ Ver faturas e histórico

## 7. Cenários Especiais

### 7.1 Assinatura com Teste Pago

```javascript
// Criar produto especial para teste pago
const trialPrice = await stripe.prices.create({
  unit_amount: 100, // R$ 1,00 para teste
  currency: 'brl',
  product: 'prod_produto_id'
});

// Criar assinatura com teste pago + período gratuito
const subscription = await stripe.subscriptions.create({
  customer: 'cus_customer_id',
  items: [{ price: trialPrice.id }],
  trial_period_days: 14,
  add_invoice_items: [{
    price: trialPrice.id,
    quantity: 1
  }]
});
```

### 7.2 Downgrade com Crédito

```javascript
const subscription = await stripe.subscriptions.update('sub_1234567890', {
  items: [{
    id: 'si_item_id',
    price: 'price_plano_menor'
  }],
  proration_behavior: 'create_prorations' // Criar crédito para próxima fatura
});
```

### 7.3 Cancelamento por Disputa

**Configurar no Dashboard**:
1. **Configurações** > **Faturamento** > **Assinaturas**
2. **Em "Gerenciar pagamentos contestados"**:
   - "Cancelar imediatamente sem prorratação"
   - "Cancelar no final do período"

## 8. Tratamento de Erros

### 8.1 Erros Comuns

```javascript
try {
  const subscription = await stripe.subscriptions.create({
    customer: 'cus_customer_id',
    items: [{ price: 'price_id' }]
  });
} catch (error) {
  switch (error.code) {
    case 'resource_missing':
      // Cliente ou preço não existe
      console.log('Cliente ou preço não encontrado');
      break;
      
    case 'subscription_creation_failed':
      // Falha na criação (ex: método de pagamento inválido)
      console.log('Falha ao criar assinatura:', error.message);
      break;
      
    case 'invoice_payment_failed':
      // Falha no pagamento inicial
      console.log('Pagamento inicial rejeitado');
      break;
      
    default:
      console.log('Erro inesperado:', error.message);
  }
}
```

### 8.2 Validações Antes de Criar Assinatura

```javascript
const validateSubscriptionCreation = async (customerId, priceId) => {
  try {
    // Verificar se cliente existe
    const customer = await stripe.customers.retrieve(customerId);
    
    // Verificar se preço está ativo
    const price = await stripe.prices.retrieve(priceId);
    if (!price.active) {
      throw new Error('Preço não está ativo');
    }
    
    // Verificar se cliente já tem assinatura ativa (se aplicável)
    const subscriptions = await stripe.subscriptions.list({
      customer: customerId,
      status: 'active'
    });
    
    if (subscriptions.data.length > 0) {
      throw new Error('Cliente já possui assinatura ativa');
    }
    
    return true;
  } catch (error) {
    throw new Error(`Validação falhou: ${error.message}`);
  }
};
```

## 9. Monitoramento e Métricas

### 9.1 Webhooks Essenciais para SaaS

```javascript
const webhookEvents = [
  'customer.subscription.created',
  'customer.subscription.updated', 
  'customer.subscription.deleted',
  'customer.subscription.trial_will_end',
  'invoice.payment_succeeded',
  'invoice.payment_failed',
  'invoice.finalized'
];
```

### 9.2 Métricas Importantes

- **MRR (Monthly Recurring Revenue)**: Receita mensal recorrente
- **Churn Rate**: Taxa de cancelamento
- **Trial Conversion Rate**: Taxa de conversão de teste para pago
- **ARPU (Average Revenue Per User)**: Receita média por usuário

## 10. Boas Práticas

### 10.1 Segurança

- **Sempre** validar webhooks com assinatura
- **Nunca** expor chaves secretas no frontend
- **Implementar** idempotência nos webhooks
- **Usar HTTPS** em todos os endpoints

### 10.2 UX/UI

- **Comunicar claramente** termos do teste gratuito
- **Enviar lembretes** antes do término do teste
- **Facilitar** cancelamento e pausas
- **Oferecer** opções de downgrade antes do cancelamento

### 10.3 Compliance no Brasil

- **Configurar** impostos adequadamente
- **Implementar** métodos de pagamento locais (PIX, boleto)
- **Cumprir** regulamentações de cancelamento
- **Manter** histórico de faturas acessível

## Conclusão

Esta documentação fornece uma base sólida para implementar e gerenciar assinaturas recorrentes com o Stripe. Lembre-se de sempre testar em ambiente de desenvolvimento antes de implementar em produção, e considere usar o Customer Portal para reduzir o suporte manual.
# 📋 Plano de Ação - Página de Perfil com Dados Reais

## 🎯 Objetivo
Implementar uma página de perfil funcional que exiba dados reais do banco de dados MariaDB, substituindo os dados mock atuais.

## 📊 Análise da Situação Atual

### ✅ O que já existe:
- **Frontend**: Página `perfil.html` com interface completa
- **JavaScript**: `perfil.js` com lógica de interação
- **API**: Endpoint `/api/v1/auth/me` funcional
- **Banco**: Tabela `users` com campos necessários
- **Serviços**: `user_service.py` e `dashboard_service.py` implementados

### ❌ Problemas identificados:
- **Dados Mock**: Frontend exibe dados estáticos (João Silva, etc.)
- **Campos Faltando**: Alguns campos do perfil não estão sendo buscados
- **Estatísticas**: Dados de créditos e consultas não são carregados
- **Configurações**: Notificações e preferências não são persistidas

## 🏗️ Estrutura do Banco de Dados

### Tabela `users` (MariaDB):
```sql
CREATE TABLE users (
    id char(36) PRIMARY KEY,
    email varchar(255) UNIQUE NOT NULL,
    name varchar(255) NOT NULL,
    password_hash varchar(255),
    last_login datetime,
    is_active tinyint(1) DEFAULT 1,
    stripe_customer_id varchar(255),
    credits decimal(10,2) DEFAULT 0.00,
    created_at datetime DEFAULT current_timestamp(),
    updated_at datetime DEFAULT current_timestamp()
);
```

### Tabelas Relacionadas:
- `credit_transactions`: Histórico de créditos
- `consultations`: Histórico de consultas
- `api_keys`: Chaves de API do usuário
- `subscriptions`: Assinaturas ativas

## 📋 Plano de Implementação

### **FASE 1: Backend - Endpoints de Perfil** ⏱️ 2-3 horas

#### 1.1 Criar endpoint `/api/v1/auth/profile` (PUT)
```python
# api/routers/saas_routes.py
@router.put("/auth/profile")
async def update_profile(
    profile_data: ProfileUpdateRequest,
    user: AuthUser = Depends(require_auth)
):
    """Atualiza dados do perfil do usuário"""
```

#### 1.2 Expandir endpoint `/api/v1/auth/me` (GET)
```python
# Retornar dados completos incluindo:
- Informações básicas (name, email, created_at)
- Estatísticas de créditos (disponível, usado, total)
- Estatísticas de consultas (este mês, total)
- Configurações de notificação
- Status da assinatura
- Informações de segurança (2FA, último login)
```

#### 1.3 Criar endpoint `/api/v1/auth/notifications` (PUT)
```python
@router.put("/auth/notifications")
async def update_notification_settings(
    settings: NotificationSettingsRequest,
    user: AuthUser = Depends(require_auth)
):
    """Atualiza configurações de notificação"""
```

#### 1.4 Criar endpoint `/api/v1/auth/change-password` (POST)
```python
@router.post("/auth/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    user: AuthUser = Depends(require_auth)
):
    """Altera senha do usuário"""
```

### **FASE 2: Serviços - Lógica de Negócio** ⏱️ 2-3 horas

#### 2.1 Expandir `UserService.get_user()` 
```python
# api/services/user_service.py
async def get_user_complete_profile(self, user_id: str) -> UserProfileResponse:
    """
    Obtém perfil completo do usuário com:
    - Dados básicos
    - Estatísticas de créditos
    - Estatísticas de consultas
    - Configurações de notificação
    - Status da assinatura
    """
```

#### 2.2 Criar `UserService.update_profile()`
```python
async def update_profile(self, user_id: str, profile_data: dict) -> bool:
    """Atualiza dados do perfil"""
```

#### 2.3 Criar `UserService.update_notification_settings()`
```python
async def update_notification_settings(self, user_id: str, settings: dict) -> bool:
    """Atualiza configurações de notificação"""
```

#### 2.4 Criar `UserService.change_password()`
```python
async def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
    """Altera senha do usuário"""
```

### **FASE 3: Modelos - Estruturas de Dados** ⏱️ 1 hora

#### 3.1 Criar modelos Pydantic
```python
# api/models/saas_models.py

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None

class NotificationSettingsRequest(BaseModel):
    email_notifications: Optional[bool] = None
    api_alerts: Optional[bool] = None
    billing_alerts: Optional[bool] = None
    credits_alerts: Optional[bool] = None
    renewal_alerts: Optional[bool] = None
    security_alerts: Optional[bool] = None
    marketing_emails: Optional[bool] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class UserProfileResponse(BaseModel):
    # Dados básicos
    id: str
    name: str
    email: str
    created_at: datetime
    last_login: Optional[datetime]
    
    # Estatísticas de créditos
    credits_available: float
    credits_used_total: float
    credits_purchased_total: float
    
    # Estatísticas de consultas
    monthly_queries: int
    total_queries: int
    last_query_date: Optional[datetime]
    
    # Configurações
    notification_settings: Dict[str, bool]
    
    # Status da assinatura
    subscription_status: str
    subscription_plan: str
    subscription_days: int
```

### **FASE 4: Frontend - Integração com API** ⏱️ 2-3 horas

#### 4.1 Atualizar `perfil.js` - Carregamento de Dados
```javascript
// static/js/perfil.js
async loadUserData() {
    try {
        const data = await AuthUtils.authenticatedFetchJSON('/api/v1/auth/me');
        this.userData = data.user;
        
        // Renderizar dados reais
        this.renderProfile();
    } catch (error) {
        console.error('Erro ao carregar dados:', error);
        this.showErrorState('Erro ao carregar perfil');
    }
}
```

#### 4.2 Implementar `renderAccountStats()` com Dados Reais
```javascript
renderAccountStats() {
    const stats = this.userData.account_stats;
    
    // Atualizar elementos com dados reais
    document.querySelector('[data-profile-credits-available]').textContent = 
        `R$ ${stats.credits_available.toFixed(2)}`;
    
    document.querySelector('[data-profile-credits-used]').textContent = 
        `R$ ${stats.credits_used_total.toFixed(2)}`;
    
    document.querySelector('[data-profile-monthly-queries]').textContent = 
        stats.monthly_queries.toLocaleString();
}
```

#### 4.3 Implementar `renderBasicInfo()` com Dados Reais
```javascript
renderBasicInfo() {
    // Nome e email reais
    document.querySelector('[data-profile-name]').value = this.userData.name;
    document.querySelector('[data-profile-email]').value = this.userData.email;
    
    // Data de criação real
    document.querySelector('[data-member-since]').textContent = 
        this.formatDate(this.userData.created_at);
}
```

#### 4.4 Implementar `renderSecuritySettings()` com Dados Reais
```javascript
renderSecuritySettings() {
    // Status do 2FA real
    const twoFactorStatus = document.querySelector('[data-2fa-status]');
    twoFactorStatus.textContent = this.userData.two_factor_enabled ? 'Ativado' : 'Desativado';
    
    // Último login real
    document.querySelector('[data-last-login]').textContent = 
        this.formatDateTime(this.userData.last_login);
}
```

### **FASE 5: Funcionalidades Avançadas** ⏱️ 3-4 horas

#### 5.1 Sistema de Notificações
- Implementar persistência das configurações
- Criar tabela `user_notification_settings` se necessário
- Implementar toggle de configurações em tempo real

#### 5.2 Sistema de 2FA
- Implementar geração de QR code
- Criar endpoints para ativar/desativar 2FA
- Integrar com biblioteca de autenticação 2FA

#### 5.3 Upload de Avatar
- Implementar endpoint para upload de arquivos
- Configurar storage de imagens
- Implementar redimensionamento automático

#### 5.4 Histórico de Uso Detalhado
- Integrar com `history_service.py`
- Mostrar breakdown por tipo de consulta
- Implementar gráficos de uso

### **FASE 6: Testes e Validação** ⏱️ 1-2 horas

#### 6.1 Testes de Integração
- Testar carregamento de dados reais
- Testar atualização de perfil
- Testar alteração de senha
- Testar configurações de notificação

#### 6.2 Validação de Segurança
- Verificar autenticação em todos os endpoints
- Validar sanitização de dados
- Testar proteção contra CSRF

#### 6.3 Testes de Performance
- Verificar tempo de carregamento
- Otimizar queries do banco
- Implementar cache se necessário

## 🔧 Implementação Técnica

### **Queries SQL Necessárias:**

#### Buscar dados completos do usuário:
```sql
SELECT 
    u.id, u.name, u.email, u.created_at, u.last_login, u.credits,
    s.status as subscription_status,
    sp.name as subscription_plan,
    COUNT(DISTINCT ak.id) as api_keys_count,
    COUNT(DISTINCT c.id) as total_queries,
    COUNT(DISTINCT CASE WHEN c.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) THEN c.id END) as monthly_queries,
    MAX(c.created_at) as last_query_date
FROM users u
LEFT JOIN subscriptions s ON u.id = s.user_id AND s.status = 'active'
LEFT JOIN subscription_plans sp ON s.plan_id = sp.id
LEFT JOIN api_keys ak ON u.id = ak.user_id AND ak.is_active = 1
LEFT JOIN consultations c ON u.id = c.user_id
WHERE u.id = %s
GROUP BY u.id;
```

#### Buscar estatísticas de créditos:
```sql
SELECT 
    SUM(CASE WHEN type IN ('add', 'purchase') THEN amount_cents ELSE 0 END) / 100.0 as total_purchased,
    SUM(CASE WHEN type IN ('subtract', 'spend', 'usage') THEN amount_cents ELSE 0 END) / 100.0 as total_spent
FROM credit_transactions 
WHERE user_id = %s;
```

### **Estrutura de Resposta da API:**
```json
{
  "user": {
    "id": "uuid",
    "name": "Nome Real",
    "email": "email@real.com",
    "created_at": "2024-01-15T10:30:00Z",
    "last_login": "2024-09-25T08:45:00Z",
    "credits_available": 150.75,
    "credits_used_total": 45.25,
    "credits_purchased_total": 200.00,
    "monthly_queries": 25,
    "total_queries": 150,
    "last_query_date": "2024-09-24T16:30:00Z",
    "api_keys_count": 2,
    "subscription_status": "active",
    "subscription_plan": "Professional",
    "subscription_days": 15,
    "two_factor_enabled": false,
    "notification_settings": {
      "email_notifications": true,
      "api_alerts": true,
      "billing_alerts": true,
      "credits_alerts": true,
      "renewal_alerts": true,
      "security_alerts": true,
      "marketing_emails": false
    }
  }
}
```

## 📊 Cronograma de Execução

| Fase | Duração | Prioridade | Dependências |
|------|---------|------------|--------------|
| **FASE 1** | 2-3h | 🔴 Alta | Nenhuma |
| **FASE 2** | 2-3h | 🔴 Alta | FASE 1 |
| **FASE 3** | 1h | 🟡 Média | FASE 1 |
| **FASE 4** | 2-3h | 🔴 Alta | FASE 2, 3 |
| **FASE 5** | 3-4h | 🟡 Média | FASE 4 |
| **FASE 6** | 1-2h | 🟢 Baixa | Todas |

**⏱️ Tempo Total Estimado: 11-16 horas**

## 🎯 Critérios de Sucesso

### ✅ Funcionalidades Básicas:
- [ ] Carregar dados reais do usuário
- [ ] Exibir estatísticas de créditos corretas
- [ ] Mostrar histórico de consultas real
- [ ] Permitir edição de nome e email
- [ ] Salvar alterações no banco

### ✅ Funcionalidades Avançadas:
- [ ] Configurações de notificação funcionais
- [ ] Alteração de senha segura
- [ ] Sistema de 2FA básico
- [ ] Upload de avatar
- [ ] Histórico detalhado de uso

### ✅ Qualidade:
- [ ] Performance < 500ms para carregamento
- [ ] Tratamento de erros robusto
- [ ] Validação de dados completa
- [ ] Interface responsiva
- [ ] Testes de integração passando

## 🚀 Próximos Passos

1. **Iniciar FASE 1**: Implementar endpoints de perfil
2. **Testar integração**: Verificar comunicação frontend-backend
3. **Iterar**: Ajustar conforme feedback
4. **Documentar**: Atualizar documentação da API
5. **Deploy**: Testar em ambiente de produção

---

**📝 Notas:**
- Manter compatibilidade com sistema de autenticação existente
- Preservar funcionalidades já implementadas
- Focar em dados reais sem quebrar interface atual
- Implementar gradualmente para facilitar testes

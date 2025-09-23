# 🏗️ Plano de Migração de Banco de Dados - Supabase PostgreSQL → MariaDB Local

## 🎯 Visão Geral da Migração

**Situação Atual**: Supabase PostgreSQL (Cloud)  
**Situação Desejada**: MariaDB Local (Self-hosted)  
**Complexidade**: **ALTA** - Sistema SaaS completo com 12+ tabelas e funcionalidades avançadas  
**Tempo Estimado**: 2-3 dias de desenvolvimento + 1 dia de testes  

---

## 📊 Análise Detalhada do Sistema Atual

### 🗂️ **Estrutura do Banco de Dados Atual (Supabase PostgreSQL)**

| Tabela | Registros | Propósito | Complexidade Migração |
|--------|-----------|-----------|----------------------|
| `users` | 7 | Gestão de usuários do sistema | 🟡 **MÉDIA** - Adicionar campos Stripe |
| `subscription_plans` | 3 | Planos de assinatura disponíveis | 🟢 **BAIXA** - Estrutura simples |
| `subscriptions` | 2 | Assinaturas ativas dos usuários | 🟡 **MÉDIA** - Integração Stripe |
| `api_keys` | 10 | Chaves de API dos usuários | 🟢 **BAIXA** - Hash SHA256 simples |
| `user_credits` | 2 | Sistema de créditos por usuário | 🟡 **MÉDIA** - Lógica de negócio |
| `consultation_types` | 6 | Tipos de consulta com custos | 🟢 **BAIXA** - Dados de configuração |
| `consultations` | 1 | Histórico de consultas realizadas | 🟡 **MÉDIA** - Volume de dados |
| `consultation_details` | 1 | Detalhes por tipo de cada consulta | 🟡 **MÉDIA** - Relacionamentos |
| `credit_transactions` | 2 | Transações de crédito | 🔴 **ALTA** - Triggers complexos |
| `daily_analytics` | 1 | Analytics diário consolidado | 🟡 **MÉDIA** - Agregações |
| `service_costs` | ❓ | Custos dos serviços | 🟢 **BAIXA** - Tabela nova |
| `stripe_webhook_logs` | ❓ | Logs de webhooks Stripe | 🟢 **BAIXA** - Logs simples |

### 🧩 **Funcionalidades Específicas do PostgreSQL/Supabase**

#### ⚠️ **Recursos Críticos que Precisam de Adaptação:**

1. **UUID com gen_random_uuid()** → Substituir por CHAR(36) + UUID() do MariaDB
2. **TIMESTAMP WITH TIME ZONE** → Substituir por DATETIME + controle de timezone na aplicação  
3. **JSONB** → Substituir por JSON do MariaDB
4. **Row Level Security (RLS)** → Implementar controle de acesso na aplicação
5. **PL/pgSQL Functions/Triggers** → Reescrever em MySQL/MariaDB syntax
6. **Cliente Supabase Python** → Migrar para PyMySQL ou mysql-connector-python

#### 🔧 **Views e Objetos Complexos:**

```sql
-- Views atuais que precisam ser adaptadas:
- user_credits_summary
- active_subscriptions  
- Agregações de analytics
```

#### ⚡ **Triggers/Functions Críticas:**

```sql
-- Função principal que precisa ser reescrita:
update_user_credits() - Calcula saldo após transações
trigger_update_user_credits - Trigger BEFORE INSERT
```

---

## 🎯 Estratégia de Migração

### **Fase 1: Análise e Preparação** ⏱️ **4-6 horas**

#### 1.1 **Mapeamento Completo das Dependências**
- ✅ **Concluído** - Análise detalhada realizada
- ✅ **Concluído** - Identificadas todas as tabelas e relacionamentos  
- ✅ **Concluído** - Mapeados serviços que interagem com BD

#### 1.2 **Identificação de Incompatibilidades**
- **UUIDs**: PostgreSQL gen_random_uuid() → MariaDB UUID()
- **Timezones**: TIMESTAMP WITH TIME ZONE → DATETIME + pytz na aplicação
- **JSON**: JSONB → JSON (sintaxe ligeiramente diferente)
- **Triggers**: PL/pgSQL → MySQL syntax
- **RLS**: Remover e implementar na aplicação

---

### **Fase 2: Criação do Schema MariaDB** ⏱️ **8-10 horas**

#### 2.1 **Criação do Arquivo bd.sql**
- Adaptar todas as 12+ tabelas para MariaDB syntax
- Converter UUIDs para CHAR(36) com triggers de geração
- Adaptar tipos de dados (TIMESTAMP, JSON, etc.)
- Reescrever constraints e foreign keys
- Criar índices otimizados

#### 2.2 **Triggers e Stored Procedures**
```sql
-- Exemplo de trigger a ser criado:
DELIMITER $$
CREATE TRIGGER trigger_update_user_credits
BEFORE INSERT ON credit_transactions
FOR EACH ROW
BEGIN
    -- Lógica do cálculo de saldo em MySQL syntax
END$$
DELIMITER ;
```

#### 2.3 **Views e Agregações**
- Recriar user_credits_summary adaptada para MariaDB
- Adaptar views de analytics
- Otimizar consultas para MySQL engine

---

### **Fase 3: Adaptação do Código Python** ⏱️ **6-8 horas**

#### 3.1 **Substituição do Cliente Supabase**
```python
# ANTES (Supabase):
from supabase import create_client
supabase = create_client(url, key)
result = supabase.table("users").select("*").execute()

# DEPOIS (MariaDB):
import pymysql
connection = pymysql.connect(host, user, password, database)
cursor = connection.cursor(pymysql.cursors.DictCursor)
cursor.execute("SELECT * FROM users")
result = cursor.fetchall()
```

#### 3.2 **Arquivos a serem Modificados**:
- `api/database/connection.py` - **CRÍTICO** - Cliente de conexão
- `api/database/models.py` - Adaptar tipos de dados (UUID → str)
- `api/services/*.py` - Todos os 10+ serviços que fazem queries
- `api/middleware/auth_middleware.py` - Autenticação e queries de usuário

#### 3.3 **Padrões de Migração por Serviço**:

**CreditService** (Mais Crítico):
```python
# ANTES:
response = self.supabase.table("credit_transactions").insert(data).execute()

# DEPOIS:  
cursor.execute("""
    INSERT INTO credit_transactions (id, user_id, type, amount_cents, description) 
    VALUES (UUID(), %s, %s, %s, %s)
""", (user_id, type, amount_cents, description))
```

**DashboardService**, **HistoryService**, etc.:
- Adaptar todas as queries SELECT complexas
- Manter mesma lógica de negócio
- Ajustar sintaxe de agregações e JOINs

---

### **Fase 4: Configuração do Ambiente** ⏱️ **2-3 horas**

#### 4.1 **Instalação MariaDB Local**
```bash
# Ubuntu/Debian:
sudo apt update
sudo apt install mariadb-server mariadb-client

# Windows (via Docker):
docker run -d --name mariadb \
  -e MYSQL_ROOT_PASSWORD=senha_segura \
  -e MYSQL_DATABASE=valida_saas \
  -e MYSQL_USER=valida_user \  
  -e MYSQL_PASSWORD=senha_user \
  -p 3306:3306 \
  mariadb:latest
```

#### 4.2 **Configuração de Segurança**
```sql
-- Criar usuário específico para a aplicação
CREATE USER 'valida_saas'@'localhost' IDENTIFIED BY 'senha_super_segura';
GRANT ALL PRIVILEGES ON valida_saas.* TO 'valida_saas'@'localhost';
FLUSH PRIVILEGES;
```

#### 4.3 **Variáveis de Ambiente (.env)**
```env
# ANTES (Supabase):
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx

# DEPOIS (MariaDB):
DB_HOST=localhost
DB_PORT=3306
DB_NAME=valida_saas  
DB_USER=valida_saas
DB_PASSWORD=senha_super_segura
DB_CHARSET=utf8mb4
```

---

### **Fase 5: Migração de Dados** ⏱️ **4-6 horas**

#### 5.1 **Exportação dos Dados do Supabase**
```python
# Script de exportação a ser criado:
export_supabase_data.py
- Conectar no Supabase
- Exportar todas as tabelas para JSON/CSV
- Manter relacionamentos e referências
```

#### 5.2 **Importação para MariaDB**
```python
# Script de importação a ser criado:  
import_to_mariadb.py
- Converter UUIDs para formato MariaDB
- Ajustar timestamps para UTC
- Manter integridade referencial
```

#### 5.3 **Dados Críticos a Migrar**:
| Tabela | Volume | Criticalidade | Observações |
|--------|--------|---------------|-------------|
| users | 7 registros | 🔴 **CRÍTICA** | Senhas, emails, dados pessoais |
| api_keys | 10 registros | 🔴 **CRÍTICA** | Chaves ativas, hashs SHA256 |
| subscriptions | 2 registros | 🟡 **ALTA** | Planos ativos, Stripe IDs |
| credit_transactions | 2 registros | 🟡 **ALTA** | Histórico financeiro |
| consultations | 1+ registros | 🟡 **MÉDIA** | Histórico de uso |

---

### **Fase 6: Testes e Validação** ⏱️ **8-10 horas**

#### 6.1 **Testes Unitários**
- Testar cada serviço individualmente
- Validar queries e resultados
- Verificar performance vs Supabase

#### 6.2 **Testes de Integração**
- Fluxo completo de autenticação  
- Consultas CNPJ end-to-end
- Sistema de créditos e cobrança
- Dashboard e analytics

#### 6.3 **Testes de Carga**
- Stress test com múltiplas consultas simultâneas
- Validar triggers de crédito sob pressão
- Monitorar locks e deadlocks

#### 6.4 **Validação de Dados**
```python
# Script de validação a ser criado:
validate_migration.py
- Comparar contagens de registros
- Verificar integridade de relacionamentos  
- Validar cálculos de créditos
- Testar todas as funcionalidades críticas
```

---

## 📁 Arquivos a Serem Criados/Modificados

### **🆕 Arquivos Novos** 
1. `bd.sql` - Schema completo MariaDB ⭐ **PRINCIPAL ENTREGÁVEL**
2. `scripts/export_supabase_data.py` - Exportação de dados
3. `scripts/import_to_mariadb.py` - Importação de dados  
4. `scripts/validate_migration.py` - Validação pós-migração
5. `docker-compose.mariadb.yml` - Setup local via Docker

### **🔧 Arquivos a Modificar**
1. `requirements.txt` - Adicionar PyMySQL/mysql-connector-python
2. `api/database/connection.py` - **CRÍTICO** - Nova lógica de conexão
3. `api/database/models.py` - Adaptar tipos UUID → str
4. `api/services/*.py` - **10+ arquivos** - Adaptar queries
5. `api/middleware/auth_middleware.py` - Adaptar autenticação  
6. `.env.example` - Novas variáveis de BD

---

## ⚡ Riscos e Mitigações

### 🔴 **Riscos ALTOS**

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| **Perda de dados durante migração** | Média | Crítico | Backup completo + validação rigorosa |
| **Triggers complexos com bugs** | Alta | Alto | Testes extensivos + rollback plan |
| **Performance degradada** | Média | Alto | Índices otimizados + monitoramento |
| **Incompatibilidade de queries** | Alta | Médio | Testes unitários completos |

### 🟡 **Riscos MÉDIOS**

- **Timezone issues** → Usar UTC + conversões na aplicação
- **JSON syntax differences** → Testes específicos para campos JSON  
- **Connection pooling** → Implementar pool adequado para MariaDB

---

## 📋 Cronograma Detalhado

### **Semana 1 - Preparação e Schema**
- **Dia 1-2**: Criação bd.sql + adaptação de triggers
- **Dia 3**: Modificação connection.py + models.py
- **Dia 4**: Adaptação dos services principais (credit, user, auth)
- **Dia 5**: Adaptação serviços restantes + dashboard

### **Semana 2 - Migração e Testes**  
- **Dia 1**: Scripts de export/import + migração de dados
- **Dia 2-3**: Testes unitários + integração + correção de bugs
- **Dia 4**: Testes de carga + otimização performance
- **Dia 5**: Deploy e monitoramento + documentação

---

## ✅ Critérios de Sucesso

### **Funcionais:**
- ✅ Todos os endpoints da API funcionando  
- ✅ Sistema de autenticação (JWT + API keys) operacional
- ✅ Sistema de créditos calculando corretamente
- ✅ Dashboard com dados reais
- ✅ Integração Stripe mantida

### **Não-Funcionais:**
- ✅ Performance igual ou superior ao Supabase
- ✅ Zero perda de dados
- ✅ Uptime > 99.9% pós-migração  
- ✅ Backups automáticos funcionando

### **Operacionais:**
- ✅ Documentação atualizada
- ✅ Scripts de backup/restore testados
- ✅ Monitoramento e alertas configurados
- ✅ Rollback plan validado

---

## 🎯 Próximos Passos Imediatos

### **1. Criar bd.sql (Prioridade MÁXIMA)**
- Arquivo principal com toda estrutura MariaDB
- Includes: tabelas, índices, triggers, views, dados iniciais

### **2. Configurar Ambiente Local**
- MariaDB via Docker ou instalação nativa
- Teste inicial do schema criado

### **3. Adaptar connection.py**
- Primeira integração Python ↔ MariaDB
- Teste básico de conectividade

---

## 📞 Suporte e Recursos

### **Documentação de Referência:**
- [MariaDB Documentation](https://mariadb.com/kb/en/)
- [PyMySQL Documentation](https://pymysql.readthedocs.io/)
- [MySQL Connector/Python](https://dev.mysql.com/doc/connector-python/en/)

### **Ferramentas Úteis:**
- **DBeaver**: Interface gráfica para ambos os BDs
- **MySQL Workbench**: Design e migração
- **Adminer**: Interface web leve

---

## 🏁 Conclusão

Esta migração é **tecnicamente viável** mas **complexa** devido ao volume de funcionalidades específicas do PostgreSQL/Supabase que precisam ser adaptadas para MariaDB.

O maior desafio será manter a **paridade funcional** especialmente no sistema de créditos (triggers complexos) e nas consultas analíticas do dashboard.

Com planejamento adequado e testes rigorosos, a migração pode ser realizada com **sucesso** e até mesmo resultar em **melhor performance** devido ao controle total sobre a infraestrutura de banco de dados.

---
**Documento criado em**: 22/09/2025  
**Versão**: 1.0  
**Status**: Plano Inicial - Pronto para Implementação  
**Próxima etapa**: Criação do arquivo `bd.sql` 🚀

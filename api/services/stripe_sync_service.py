"""
Serviço de Sincronização dos Produtos Stripe com MariaDB
Otimiza carregamento da página de assinaturas mantendo dados locais atualizados
"""
import stripe
import os
from datetime import datetime
from typing import List, Dict
import structlog

from api.database.connection import execute_sql, generate_uuid

logger = structlog.get_logger(__name__)

# Configurar Stripe
stripe_secret_key = os.getenv("STRIPE_API_KEY_SECRETA")
if stripe_secret_key:
    stripe.api_key = stripe_secret_key

# ✅ MAPEAMENTO DINÂMICO: Busca produtos por preço em vez de ID fixo
PRICE_TO_PLAN_MAPPING = {
    10000: "starter",      # R$ 100,00 = 10000 centavos
    20000: "professional", # R$ 200,00 = 20000 centavos
    30000: "enterprise"    # R$ 300,00 = 30000 centavos
}

# ✅ PRODUTOS CONHECIDOS - será preenchido dinamicamente
KNOWN_STRIPE_PRODUCTS = []


async def get_products_from_database() -> List[Dict]:
    """
    Busca produtos/planos da tabela subscription_plans local (RÁPIDO)
    """
    try:
        sql = """
        SELECT 
            id, code, name, description, price_cents, credits_included_cents,
            stripe_product_id, stripe_price_id, is_active, features
        FROM subscription_plans 
        WHERE is_active = 1 
        ORDER BY price_cents ASC
        """
        
        result = await execute_sql(sql, (), "all")
        
        if result["error"]:
            logger.error(f"❌ Erro ao buscar planos do MariaDB: {result['error']}")
            return []
        
        products = []
        if result["data"]:
            for plan in result["data"]:
                # Converter para formato compatível com frontend
                product_data = {
                    "id": plan["stripe_product_id"] or plan["id"],  # Usar Stripe ID se disponível
                    "name": plan["name"],
                    "description": plan["description"],
                    "code": plan["code"],
                    "default_price": plan["stripe_price_id"] or f"price_{plan['code']}",
                    "price_cents": plan["price_cents"],
                    "credits_included_cents": plan["credits_included_cents"],
                    "is_active": plan["is_active"],
                    "features": plan.get("features", {}),
                    "metadata": {
                        "plan_code": plan["code"],
                        "local_plan_id": plan["id"]
                    }
                }
                products.append(product_data)
        
        logger.info(f"✅ {len(products)} produtos carregados do MariaDB (local)")
        return products
        
    except Exception as e:
        logger.error(f"❌ Erro ao buscar produtos do MariaDB: {e}")
        return []


async def discover_stripe_products() -> List[Dict]:
    """
    ✅ NOVA FUNÇÃO: Descobre produtos ativos no Stripe dinamicamente
    """
    try:
        logger.info("🔍 Descobrindo produtos ativos no Stripe...")
        
        # Buscar todos os produtos ativos
        products = stripe.Product.list(active=True, limit=100)
        discovered_products = []
        
        for product in products.data:
            try:
                # Buscar preços ativos para este produto
                prices = stripe.Price.list(product=product.id, active=True)
                
                if not prices.data:
                    continue
                
                price = prices.data[0]  # Usar primeiro preço ativo
                
                # Determinar código do plano baseado no preço
                plan_code = PRICE_TO_PLAN_MAPPING.get(price.unit_amount, "custom")
                
                discovered_products.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "price_id": price.id,
                    "price_amount": price.unit_amount,
                    "plan_code": plan_code,
                    "description": product.description
                })
                
                logger.info(f"✅ Produto descoberto: {product.name} (R$ {price.unit_amount/100:.2f}) → {plan_code}")
                
            except Exception as e:
                logger.warning(f"⚠️ Erro ao processar produto {product.id}: {e}")
                continue
        
        logger.info(f"🎯 {len(discovered_products)} produtos descobertos no Stripe")
        return discovered_products
        
    except Exception as e:
        logger.error(f"❌ Erro ao descobrir produtos Stripe: {e}")
        return []


async def sync_stripe_products_to_database() -> Dict:
    """
    ✅ VERSÃO MELHORADA: Sincroniza produtos descobertos dinamicamente
    """
    try:
        if not stripe.api_key or stripe.api_key == "sk_test_dummy":
            logger.warning("⚠️ Stripe não configurado - pulando sincronização")
            return {"success": False, "message": "Stripe não configurado"}
        
        sync_results = {
            "success": True,
            "updated": 0,
            "created": 0,
            "errors": []
        }
        
        logger.info("🔄 Iniciando sincronização Stripe → MariaDB (busca dinâmica)")
        
        # ✅ DESCOBRIR produtos automaticamente
        discovered_products = await discover_stripe_products()
        
        if not discovered_products:
            logger.warning("⚠️ Nenhum produto encontrado no Stripe")
            return {
                "success": False,
                "message": "Nenhum produto encontrado no Stripe",
                "updated": 0,
                "created": 0,
                "errors": ["Nenhum produto encontrado"]
            }
        
        # ✅ PROCESSAR cada produto descoberto
        for product_data in discovered_products:
            try:
                product_id = product_data["product_id"]
                plan_code = product_data["plan_code"]
                
                # Verificar se plano já existe
                check_sql = "SELECT id FROM subscription_plans WHERE code = %s"
                check_result = await execute_sql(check_sql, (plan_code,), "one")
                
                if check_result.get('data'):
                    # ✅ ATUALIZAR plano existente
                    plan_id = check_result['data']['id']
                    update_sql = """
                    UPDATE subscription_plans 
                    SET name = %s, description = %s, price_cents = %s, credits_included_cents = %s,
                        stripe_product_id = %s, stripe_price_id = %s, updated_at = %s
                    WHERE id = %s
                    """
                    
                    update_data = (
                        product_data["product_name"],
                        product_data["description"] or f"Plano de R$ {product_data['price_amount']/100:.2f} em créditos mensais",
                        product_data["price_amount"],
                        product_data["price_amount"],  # 1:1 - cada R$ pago vira R$ em créditos
                        product_id,
                        product_data["price_id"],
                        datetime.now(),
                        plan_id
                    )
                    
                    result = await execute_sql(update_sql, update_data, "none")
                    
                    if result["error"]:
                        error_msg = f"Erro ao atualizar plano {plan_code}: {result['error']}"
                        sync_results["errors"].append(error_msg)
                    else:
                        sync_results["updated"] += 1
                        logger.info(f"🔄 Plano '{plan_code}' atualizado com novo produto {product_id}")
                
                else:
                    # ✅ CRIAR novo plano
                    plan_id = generate_uuid()
                    insert_sql = """
                    INSERT INTO subscription_plans 
                    (id, code, name, description, price_cents, credits_included_cents, 
                     stripe_product_id, stripe_price_id, is_active, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
                    """
                    
                    insert_data = (
                        plan_id,
                        plan_code,
                        product_data["product_name"],
                        product_data["description"] or f"Plano de R$ {product_data['price_amount']/100:.2f} em créditos mensais",
                        product_data["price_amount"],
                        product_data["price_amount"],
                        product_id,
                        product_data["price_id"],
                        datetime.now()
                    )
                    
                    result = await execute_sql(insert_sql, insert_data, "none")
                    
                    if result["error"]:
                        error_msg = f"Erro ao criar plano {plan_code}: {result['error']}"
                        sync_results["errors"].append(error_msg)
                    else:
                        sync_results["created"] += 1
                        logger.info(f"➕ Plano '{plan_code}' criado com produto {product_id}")
                
            except Exception as e:
                error_msg = f"Erro ao processar produto {product_data['product_id']}: {str(e)}"
                sync_results["errors"].append(error_msg)
                logger.error(error_msg)
                continue
        
        # ✅ LOG FINAL
        logger.info(f"✅ Sincronização concluída: {sync_results['updated']} atualizados, {sync_results['created']} criados")
        
        if sync_results["errors"]:
            logger.warning(f"⚠️ {len(sync_results['errors'])} erros encontrados")
            for error in sync_results["errors"]:
                logger.warning(f"   {error}")
        
        return sync_results
        
    except Exception as e:
        logger.error(f"❌ Erro geral na sincronização: {e}")
        return {
            "success": False,
            "message": f"Erro na sincronização: {str(e)}",
            "updated": 0,
            "created": 0,
            "errors": [str(e)]
        }


async def get_last_sync_info() -> Dict:
    """
    Retorna informações sobre a última sincronização
    """
    try:
        sql = """
        SELECT MAX(updated_at) as last_updated
        FROM subscription_plans 
        WHERE stripe_product_id IS NOT NULL
        """
        
        result = await execute_sql(sql, (), "one")
        
        if result["data"] and result["data"]["last_updated"]:
            last_updated = result["data"]["last_updated"]
            return {
                "last_sync": last_updated.isoformat() if last_updated else None,
                "has_stripe_data": True
            }
        else:
            return {
                "last_sync": None,
                "has_stripe_data": False
            }
            
    except Exception as e:
        logger.error(f"❌ Erro ao verificar última sincronização: {e}")
        return {
            "last_sync": None,
            "has_stripe_data": False,
            "error": str(e)
        }


class StripeProductSyncService:
    """
    Serviço para sincronização automática de produtos Stripe
    """
    
    def __init__(self):
        self.last_sync = None
        self.cache_duration_minutes = 60  # Cache por 1 hora
    
    async def get_products(self, force_sync: bool = False) -> List[Dict]:
        """
        Retorna produtos da tabela local, sincroniza se necessário
        """
        try:
            # Verificar se precisa sincronizar
            sync_info = await get_last_sync_info()
            
            if force_sync or not sync_info["has_stripe_data"]:
                logger.info("🔄 Sincronizando produtos do Stripe...")
                await sync_stripe_products_to_database()
            
            # Retornar produtos da tabela local
            return await get_products_from_database()
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter produtos: {e}")
            return []
    
    async def force_sync(self) -> Dict:
        """
        Força sincronização completa com Stripe
        """
        return await sync_stripe_products_to_database()


# Instância singleton
stripe_sync_service = StripeProductSyncService()

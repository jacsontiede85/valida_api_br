"""
Serviço para registrar consultas no histórico
"""
import structlog
from typing import Optional, Dict, Any
from datetime import datetime
from api.middleware.auth_middleware import get_supabase_client

logger = structlog.get_logger("query_logger_service")

class QueryLoggerService:
    def __init__(self):
        self.supabase = get_supabase_client()
    
    async def log_query(
        self,
        user_id: str,
        api_key_id: Optional[str],
        cnpj: str,
        endpoint: str,
        response_status: int,
        credits_used: int = 1,
        response_time_ms: Optional[int] = None,
        success: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Registra uma consulta no histórico
        """
        try:
            if not self.supabase:
                logger.warning("Supabase não configurado - consulta não será registrada")
                return None
            
            # Determinar status baseado no response_status
            status = "success" if success and response_status < 400 else "error"
            
            query_data = {
                "user_id": user_id,
                "api_key_id": api_key_id,  # Pode ser None se não for UUID válido
                "cnpj": cnpj,
                "endpoint": endpoint,
                "response_status": response_status,
                "credits_used": credits_used,
                "response_time_ms": response_time_ms,
                "status": status,
                "created_at": datetime.now().isoformat()
            }
            
            # Se api_key_id não é um UUID válido, remover do insert
            if api_key_id and not api_key_id.startswith("00000000-0000-0000-0000-000000000"):
                # Verificar se é um UUID válido
                try:
                    import uuid
                    uuid.UUID(api_key_id)
                except ValueError:
                    # Não é um UUID válido, remover do insert
                    query_data.pop("api_key_id", None)
            
            # Inserir no banco
            response = self.supabase.table("query_history").insert(query_data).execute()
            
            if response.data:
                logger.info(
                    "consulta_registrada",
                    user_id=user_id,
                    cnpj=cnpj,
                    status=status,
                    query_id=response.data[0]["id"]
                )
                return response.data[0]
            else:
                logger.error("Falha ao registrar consulta no histórico")
                return None
                
        except Exception as e:
            logger.error("erro_registrar_consulta", user_id=user_id, cnpj=cnpj, error=str(e))
            return None
    
    async def update_query_analytics(
        self,
        user_id: str,
        date: str,
        total_queries: int = 1,
        successful_queries: int = 1,
        failed_queries: int = 0,
        total_credits_used: int = 1
    ) -> bool:
        """
        Atualiza ou cria analytics diários para o usuário
        """
        try:
            if not self.supabase:
                return False
            
            # Verificar se já existe analytics para esta data
            existing = self.supabase.table("query_analytics").select("*").eq("user_id", user_id).eq("date", date).execute()
            
            if existing.data:
                # Atualizar existente
                update_data = {
                    "total_queries": existing.data[0]["total_queries"] + total_queries,
                    "successful_queries": existing.data[0]["successful_queries"] + successful_queries,
                    "failed_queries": existing.data[0]["failed_queries"] + failed_queries,
                    "total_credits_used": existing.data[0]["total_credits_used"] + total_credits_used
                }
                
                response = self.supabase.table("query_analytics").update(update_data).eq("id", existing.data[0]["id"]).execute()
            else:
                # Criar novo
                analytics_data = {
                    "user_id": user_id,
                    "date": date,
                    "total_queries": total_queries,
                    "successful_queries": successful_queries,
                    "failed_queries": failed_queries,
                    "total_credits_used": total_credits_used
                }
                
                response = self.supabase.table("query_analytics").insert(analytics_data).execute()
            
            return bool(response.data)
            
        except Exception as e:
            logger.error("erro_atualizar_analytics", user_id=user_id, date=date, error=str(e))
            return False

# Instância global do serviço
query_logger_service = QueryLoggerService()

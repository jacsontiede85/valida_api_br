"""
Serviço de gerenciamento de histórico de consultas
"""
import structlog
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from api.middleware.auth_middleware import get_supabase_client

logger = structlog.get_logger("history_service")

class HistoryService:
    def __init__(self):
        self.supabase = get_supabase_client()
    
    async def get_user_query_history(
        self, 
        user_id: str, 
        page: int = 1, 
        limit: int = 20,
        status: str = "all",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtém o histórico de consultas do usuário com filtros e paginação
        """
        try:
            if not self.supabase:
                # Sem Supabase configurado
                return {
                    "queries": [],
                    "pagination": {
                        "page": page,
                        "limit": limit,
                        "total": 0,
                        "pages": 0
                    },
                    "message": "Sistema de histórico não configurado"
                }
            
            # Construir query com filtros
            query = self.supabase.table("query_history").select("*").eq("user_id", user_id)
            
            # Aplicar filtros
            if status != "all":
                query = query.eq("status", status)
            
            if date_from:
                query = query.gte("created_at", date_from)
            
            if date_to:
                query = query.lte("created_at", date_to)
            
            if search:
                query = query.ilike("cnpj", f"%{search}%")
            
            # Aplicar paginação
            offset = (page - 1) * limit
            query = query.range(offset, offset + limit - 1).order("created_at", desc=True)
            
            response = query.execute()
            
            # Buscar total de registros para paginação
            count_query = self.supabase.table("query_history").select("id", count="exact").eq("user_id", user_id)
            if status != "all":
                count_query = count_query.eq("status", status)
            if date_from:
                count_query = count_query.gte("created_at", date_from)
            if date_to:
                count_query = count_query.lte("created_at", date_to)
            if search:
                count_query = count_query.ilike("cnpj", f"%{search}%")
            
            count_response = count_query.execute()
            total = count_response.count if count_response.count else 0
            
            return {
                "data": response.data,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit
                }
            }
            
        except Exception as e:
            logger.error("erro_buscar_historico", user_id=user_id, error=str(e))
            raise e
    
    async def get_user_analytics(
        self, 
        user_id: str, 
        period: str = "30d",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtém analytics de uso do usuário
        """
        try:
            if not self.supabase:
                # Retornar analytics mock
                return self._generate_mock_analytics(period)
            
            # Calcular datas baseado no período
            end_date = datetime.now()
            if period == "7d":
                start_date = end_date - timedelta(days=7)
            elif period == "30d":
                start_date = end_date - timedelta(days=30)
            elif period == "90d":
                start_date = end_date - timedelta(days=90)
            else:
                start_date = end_date - timedelta(days=30)
            
            if date_from:
                start_date = datetime.fromisoformat(date_from)
            if date_to:
                end_date = datetime.fromisoformat(date_to)
            
            # Buscar dados de uso
            response = self.supabase.table("query_history").select("*").eq("user_id", user_id).gte("created_at", start_date.isoformat()).lte("created_at", end_date.isoformat()).execute()
            
            # Calcular estatísticas
            total_queries = len(response.data)
            successful_queries = len([q for q in response.data if q.get("status") == "success"])
            failed_queries = total_queries - successful_queries
            
            # Agrupar por dia
            daily_stats = {}
            for query in response.data:
                date = query["created_at"][:10]  # YYYY-MM-DD
                if date not in daily_stats:
                    daily_stats[date] = {"total": 0, "success": 0, "failed": 0}
                daily_stats[date]["total"] += 1
                if query.get("status") == "success":
                    daily_stats[date]["success"] += 1
                else:
                    daily_stats[date]["failed"] += 1
            
            return {
                "period": period,
                "total_queries": total_queries,
                "successful_queries": successful_queries,
                "failed_queries": failed_queries,
                "success_rate": (successful_queries / total_queries * 100) if total_queries > 0 else 0,
                "daily_stats": daily_stats,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
            
        except Exception as e:
            logger.error("erro_buscar_analytics", user_id=user_id, error=str(e))
            raise e
    
    async def export_user_history(
        self, 
        user_id: str, 
        format: str = "csv",
        status: str = "all",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exporta o histórico de consultas do usuário
        """
        try:
            if not self.supabase:
                # Retornar dados mock para exportação
                mock_data = self._generate_mock_history(1, 1000)  # Buscar todos os dados
                return {
                    "format": format,
                    "data": mock_data["data"],
                    "filename": f"historico_consultas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}",
                    "total_records": len(mock_data["data"])
                }
            
            # Buscar todos os dados (sem paginação)
            query = self.supabase.table("query_history").select("*").eq("user_id", user_id)
            
            if status != "all":
                query = query.eq("status", status)
            if date_from:
                query = query.gte("created_at", date_from)
            if date_to:
                query = query.lte("created_at", date_to)
            if search:
                query = query.ilike("cnpj", f"%{search}%")
            
            response = query.order("created_at", desc=True).execute()
            
            return {
                "format": format,
                "data": response.data,
                "filename": f"historico_consultas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}",
                "total_records": len(response.data)
            }
            
        except Exception as e:
            logger.error("erro_exportar_historico", user_id=user_id, error=str(e))
            raise e
    

# Instância global do serviço
history_service = HistoryService()

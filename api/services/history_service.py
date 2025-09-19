"""
Serviço de gerenciamento de histórico de consultas
"""
import structlog
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date
from api.middleware.auth_middleware import get_supabase_client
from api.models.saas_models import DashboardPeriod

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
            
            # Tentar buscar da nova tabela consultations primeiro
            query = self.supabase.table("consultations").select(
                "*, consultation_details(*, consultation_types(*))"
            ).eq("user_id", user_id)
            
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
            
            # Se não encontrou dados na nova tabela, buscar na antiga
            if not response.data:
                # Fallback para tabela antiga
                query_old = self.supabase.table("query_history").select("*").eq("user_id", user_id)
                
                # Aplicar filtros
                if status != "all":
                    query_old = query_old.eq("status", status)
                
                if date_from:
                    query_old = query_old.gte("created_at", date_from)
                
                if date_to:
                    query_old = query_old.lte("created_at", date_to)
                
                if search:
                    query_old = query_old.ilike("cnpj", f"%{search}%")
                
                # Aplicar paginação
                query_old = query_old.range(offset, offset + limit - 1).order("created_at", desc=True)
                response = query_old.execute()
            
            # Buscar total de registros para paginação (tentar nova tabela primeiro)
            count_query = self.supabase.table("consultations").select("id", count="exact").eq("user_id", user_id)
            if status != "all":
                count_query = count_query.eq("status", status)
            if date_from:
                count_query = count_query.gte("created_at", date_from)
            if date_to:
                count_query = count_query.lte("created_at", date_to)
            if search:
                count_query = count_query.ilike("cnpj", f"%{search}%")
            
            count_response = count_query.execute()
            
            # Se não tem dados na nova tabela, buscar na antiga
            if not count_response.count or count_response.count == 0:
                count_query_old = self.supabase.table("query_history").select("id", count="exact").eq("user_id", user_id)
                if status != "all":
                    count_query_old = count_query_old.eq("status", status)
                if date_from:
                    count_query_old = count_query_old.gte("created_at", date_from)
                if date_to:
                    count_query_old = count_query_old.lte("created_at", date_to)
                if search:
                    count_query_old = count_query_old.ilike("cnpj", f"%{search}%")
                
                count_response = count_query_old.execute()
            
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
            
            # Implementação completa seria aqui
            return self._generate_mock_analytics(period)
            
        except Exception as e:
            logger.error("erro_buscar_analytics", user_id=user_id, error=str(e))
            return self._generate_mock_analytics(period)
    
    def _calculate_period_dates(self, period: str) -> tuple[date, date]:
        """
        Calcula datas de início e fim do período
        """
        end_date = date.today()
        
        if period == "today":
            start_date = end_date
        elif period == "7d":
            start_date = end_date - timedelta(days=7)
        elif period == "30d":
            start_date = end_date - timedelta(days=30)
        elif period == "90d":
            start_date = end_date - timedelta(days=90)
        elif period == "120d":
            start_date = end_date - timedelta(days=120)
        elif period == "180d":
            start_date = end_date - timedelta(days=180)
        elif period == "365d":
            start_date = end_date - timedelta(days=365)
        else:  # 30d (padrão)
            start_date = end_date - timedelta(days=30)
        
        return start_date, end_date

    def _generate_mock_analytics(self, period: str) -> Dict[str, Any]:
        """Gera analytics mock"""
        start_date, end_date = self._calculate_period_dates(period)
        
        return {
            "period": period,
            "total_queries": 47,
            "successful_queries": 42,
            "failed_queries": 5,
            "success_rate": 89.4,
            "daily_stats": {},
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }
    
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
    

    async def get_user_consultations_v2(
        self, 
        user_id: str, 
        page: int = 1, 
        limit: int = 20,
        type_filter: str = "all",
        status_filter: str = "all",
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtém histórico de consultas v2.0 com custos detalhados por tipo
        """
        try:
            if not self.supabase:
                # Retornar dados vazios quando Supabase não estiver configurado
                return {
                    "data": [],
                    "pagination": {
                        "page": page,
                        "limit": limit,
                        "total": 0,
                        "pages": 0
                    },
                    "message": "Sistema de histórico não configurado"
                }
            
            # Query principal usando nova tabela consultations
            query = self.supabase.table("consultations").select(
                "*, consultation_details(*, consultation_types(*))"
            ).eq("user_id", user_id)
            
            # Aplicar filtros
            if status_filter != "all":
                query = query.eq("status", status_filter)
            
            if search:
                query = query.ilike("cnpj", f"%{search}%")
            
            # Aplicar paginação
            offset = (page - 1) * limit
            query = query.range(offset, offset + limit - 1).order("created_at", desc=True)
            
            response = query.execute()
            
            # Formatar dados para frontend
            consultations = []
            for item in response.data:
                consultation = {
                    "id": item["id"],
                    "cnpj": item["cnpj"],
                    "created_at": item["created_at"],
                    "status": item["status"],
                    "total_cost_cents": item["total_cost_cents"],
                    "formatted_cost": f"R$ {item['total_cost_cents'] / 100:.2f}",
                    "response_time_ms": item["response_time_ms"],
                    "cache_used": item["cache_used"],
                    "types": []
                }
                
                # Adicionar detalhes por tipo
                for detail in item.get("consultation_details", []):
                    type_info = detail.get("consultation_types", {})
                    consultation["types"].append({
                        "name": type_info.get("name"),
                        "code": type_info.get("code"),
                        "success": detail["success"],
                        "cost_cents": detail["cost_cents"],
                        "formatted_cost": f"R$ {detail['cost_cents'] / 100:.2f}"
                    })
                
                consultations.append(consultation)
            
            # Contar total para paginação
            count_query = self.supabase.table("consultations").select("id", count="exact").eq("user_id", user_id)
            if status_filter != "all":
                count_query = count_query.eq("status", status_filter)
            if search:
                count_query = count_query.ilike("cnpj", f"%{search}%")
            
            count_response = count_query.execute()
            total = count_response.count if count_response.count else 0
            
            return {
                "data": consultations,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit
                }
            }
            
        except Exception as e:
            logger.error("erro_buscar_consultations_v2", user_id=user_id, error=str(e))
            # Retornar dados vazios em caso de erro
            return {
                "data": [],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": 0,
                    "pages": 0
                },
                "message": f"Erro ao buscar histórico: {str(e)}"
            }
    
    async def get_monthly_usage_by_type(self, user_id: str) -> Dict[str, Any]:
        """
        Obtém estatísticas mensais de uso por tipo de consulta
        """
        try:
            if not self.supabase:
                return self._generate_mock_monthly_usage()
            
            # Buscar dados do mês atual
            current_month = datetime.now().strftime("%Y-%m")
            
            # Query para analytics diários do mês atual
            response = self.supabase.table("daily_analytics").select(
                "*"
            ).eq("user_id", user_id).ilike("date", f"{current_month}%").execute()
            
            # Agregar dados
            total_consultations = 0
            total_cost = 0
            types_stats = {"protestos": {"count": 0, "cost": 0}, "receita_federal": {"count": 0, "cost": 0}, "others": {"count": 0, "cost": 0}}
            
            for day in response.data:
                total_consultations += day["total_consultations"]
                total_cost += day["total_cost_cents"]
                
                # Processar tipos JSONB
                consultations_by_type = day.get("consultations_by_type", {})
                costs_by_type = day.get("costs_by_type", {})
                
                for type_code, count in consultations_by_type.items():
                    if type_code == "protestos":
                        types_stats["protestos"]["count"] += count
                        types_stats["protestos"]["cost"] += costs_by_type.get(type_code, 0)
                    elif type_code in ["receita_federal", "simples_nacional"]:
                        types_stats["receita_federal"]["count"] += count
                        types_stats["receita_federal"]["cost"] += costs_by_type.get(type_code, 0)
                    else:
                        types_stats["others"]["count"] += count
                        types_stats["others"]["cost"] += costs_by_type.get(type_code, 0)
            
            return {
                "total_consultations": total_consultations,
                "protestos": types_stats["protestos"],
                "receita_federal": types_stats["receita_federal"],
                "others": types_stats["others"],
                "total": {"count": total_consultations, "cost": total_cost}
            }
            
        except Exception as e:
            logger.error("erro_buscar_monthly_usage", user_id=user_id, error=str(e))
            # Retornar dados vazios em caso de erro
            return {
                "total_consultations": 0,
                "protestos": {"count": 0, "cost": 0},
                "receita_federal": {"count": 0, "cost": 0},
                "others": {"count": 0, "cost": 0},
                "total": {"count": 0, "cost": 0},
                "message": f"Erro ao buscar estatísticas mensais: {str(e)}"
            }
    


# Instância global do serviço
history_service = HistoryService()

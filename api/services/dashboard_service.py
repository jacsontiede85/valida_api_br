"""
Serviço para dados do dashboard (Visão Geral)
"""
import structlog
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from api.middleware.auth_middleware import get_supabase_client

logger = structlog.get_logger("dashboard_service")

class DashboardService:
    def __init__(self):
        self.supabase = get_supabase_client()
    
    async def get_dashboard_stats(self, user_id: str, period: str = "30d") -> Dict[str, Any]:
        """
        Obtém estatísticas do dashboard para o usuário
        """
        try:
            if not self.supabase:
                # Retornar dados vazios quando Supabase não estiver configurado
                return self._get_empty_dashboard_stats()
            
            # Calcular período
            end_date = datetime.now()
            if period == "7d":
                start_date = end_date - timedelta(days=7)
            elif period == "30d":
                start_date = end_date - timedelta(days=30)
            elif period == "90d":
                start_date = end_date - timedelta(days=90)
            else:
                start_date = end_date - timedelta(days=30)
            
            # Buscar dados de consultas do período
            query_history = self.supabase.table("query_history").select("*").eq("user_id", user_id).gte("created_at", start_date.isoformat()).lte("created_at", end_date.isoformat()).execute()
            
            # Debug logs removidos
            
            # Buscar dados de analytics do período
            analytics = self.supabase.table("query_analytics").select("*").eq("user_id", user_id).gte("date", start_date.strftime("%Y-%m-%d")).lte("date", end_date.strftime("%Y-%m-%d")).execute()
            
            # Calcular estatísticas - usar analytics se query_history estiver vazio
            if query_history.data:
                total_queries = len(query_history.data)
                successful_queries = len([q for q in query_history.data if q.get("status") == "success"])
                failed_queries = total_queries - successful_queries
                total_credits_used = sum(q.get("credits_used", 0) for q in query_history.data)
            else:
                # Usar dados de analytics se query_history estiver vazio
                total_queries = sum(a.get("total_queries", 0) for a in analytics.data)
                successful_queries = sum(a.get("successful_queries", 0) for a in analytics.data)
                failed_queries = sum(a.get("failed_queries", 0) for a in analytics.data)
                total_credits_used = sum(a.get("total_credits_used", 0) for a in analytics.data)
            
            # Buscar assinatura do usuário
            subscription = self.supabase.table("subscriptions").select("*, subscription_plans(*)").eq("user_id", user_id).eq("status", "active").execute()
            
            # Calcular créditos disponíveis
            credits_available = 0
            credits_renewal_date = None
            if subscription.data:
                plan = subscription.data[0].get("subscription_plans", {})
                plan_limit = plan.get("queries_limit")
                if plan_limit:
                    credits_used_this_period = sum(a.get("total_credits_used", 0) for a in analytics.data)
                    credits_available = max(0, plan_limit - credits_used_this_period)
                    credits_renewal_date = subscription.data[0].get("current_period_end")
            
            # Calcular custo médio por consulta
            avg_cost_per_query = 0.0
            if total_queries > 0:
                # Assumir custo de R$ 0,10 por consulta (pode ser configurável)
                avg_cost_per_query = 0.10
            
            # Gerar dados de gráfico de consumo por período
            if query_history.data:
                consumption_chart = self._generate_consumption_chart(query_history.data, start_date, end_date)
                volume_by_api = self._generate_volume_by_api(query_history.data)
            else:
                # Usar dados de analytics para gráficos
                consumption_chart = self._generate_consumption_chart_from_analytics(analytics.data, start_date, end_date)
                volume_by_api = self._generate_volume_by_api_from_analytics(analytics.data)
            
            return {
                "credits_available": credits_available,
                "credits_renewal_date": credits_renewal_date,
                "period_consumption": total_queries,
                "period_consumption_message": f"{total_queries} consulta(s) realizadas" if total_queries > 0 else "Nenhum consumo registrado",
                "total_queries": total_queries,
                "total_queries_message": f"{total_queries} consulta(s) realizada(s)" if total_queries > 0 else "Nenhuma consulta realizada",
                "total_cost": total_credits_used * avg_cost_per_query,
                "avg_cost_per_query": avg_cost_per_query,
                "avg_cost_message": f"Custo médio por consulta: R$ {avg_cost_per_query:.2f}",
                "consumption_chart": consumption_chart,
                "volume_by_api": volume_by_api,
                "period": period,
                "success_rate": (successful_queries / total_queries * 100) if total_queries > 0 else 0
            }
            
        except Exception as e:
            logger.error("erro_buscar_dashboard_stats", user_id=user_id, error=str(e))
            # Retornar dados vazios em caso de erro
            return self._get_empty_dashboard_stats()
    
    def _generate_consumption_chart(self, query_data: list, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Gera dados para o gráfico de consumo por período
        """
        # Agrupar por mês
        monthly_data = {}
        current_date = start_date
        
        while current_date <= end_date:
            month_key = current_date.strftime("%Y-%m")
            monthly_data[month_key] = 0
            current_date += timedelta(days=32)  # Aproximadamente próximo mês
            current_date = current_date.replace(day=1)  # Primeiro dia do mês
        
        # Contar consultas por mês
        for query in query_data:
            query_date = datetime.fromisoformat(query["created_at"].replace("Z", "+00:00"))
            month_key = query_date.strftime("%Y-%m")
            if month_key in monthly_data:
                monthly_data[month_key] += 1
        
        # Converter para formato do gráfico
        months = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        chart_data = []
        labels = []
        
        for month_key, count in monthly_data.items():
            year, month = month_key.split("-")
            month_index = int(month) - 1
            labels.append(months[month_index])
            chart_data.append(count)
        
        return {
            "labels": labels,
            "data": chart_data,
            "datasets": [{
                "label": "Consultas por Mês",
                "data": chart_data,
                "borderColor": "rgb(59, 130, 246)",
                "backgroundColor": "rgba(59, 130, 246, 0.1)",
                "tension": 0.1
            }]
        }
    
    def _generate_volume_by_api(self, query_data: list) -> Dict[str, Any]:
        """
        Gera dados para o gráfico de volume por API
        """
        api_counts = {}
        
        for query in query_data:
            endpoint = query.get("endpoint", "unknown")
            if endpoint not in api_counts:
                api_counts[endpoint] = 0
            api_counts[endpoint] += 1
        
        # Mapear endpoints para nomes amigáveis
        api_mapping = {
            "/api/v1/cnpj/consult": "CNPJ Consult",
            "/api/v1/protestos": "Protestos",
            "/api/v1/historico": "Histórico"
        }
        
        labels = []
        data = []
        colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444"]  # blue, green, yellow, red
        
        for i, (endpoint, count) in enumerate(api_counts.items()):
            api_name = api_mapping.get(endpoint, "Outros")
            labels.append(api_name)
            data.append(count)
        
        return {
            "labels": labels,
            "data": data,
            "colors": colors[:len(labels)]
        }
    
    def _generate_consumption_chart_from_analytics(self, analytics_data: list, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Gera dados para o gráfico de consumo por período usando dados de analytics
        """
        # Agrupar por mês
        monthly_data = {}
        current_date = start_date
        
        while current_date <= end_date:
            month_key = current_date.strftime("%Y-%m")
            monthly_data[month_key] = 0
            current_date += timedelta(days=32)  # Aproximadamente próximo mês
            current_date = current_date.replace(day=1)  # Primeiro dia do mês
        
        # Contar consultas por mês dos analytics
        for analytic in analytics_data:
            analytic_date = datetime.fromisoformat(analytic["date"])
            month_key = analytic_date.strftime("%Y-%m")
            if month_key in monthly_data:
                monthly_data[month_key] += analytic.get("total_queries", 0)
        
        # Converter para formato do gráfico
        months = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        chart_data = []
        labels = []
        
        for month_key, count in monthly_data.items():
            year, month = month_key.split("-")
            month_index = int(month) - 1
            labels.append(months[month_index])
            chart_data.append(count)
        
        return {
            "labels": labels,
            "data": chart_data,
            "datasets": [{
                "label": "Consultas por Mês",
                "data": chart_data,
                "borderColor": "rgb(59, 130, 246)",
                "backgroundColor": "rgba(59, 130, 246, 0.1)",
                "tension": 0.1
            }]
        }
    
    def _generate_volume_by_api_from_analytics(self, analytics_data: list) -> Dict[str, Any]:
        """
        Gera dados para o gráfico de volume por API usando dados de analytics
        """
        # Para analytics, assumir que todas as consultas são do endpoint CNPJ
        total_queries = sum(analytic.get("total_queries", 0) for analytic in analytics_data)
        
        labels = ["CNPJ Consult"]
        data = [total_queries]
        colors = ["#3B82F6"]
        
        return {
            "labels": labels,
            "data": data,
            "colors": colors
        }
    
    def _get_empty_dashboard_stats(self) -> Dict[str, Any]:
        """
        Retorna dados vazios para o dashboard quando não há dados reais
        """
        return {
            "credits_available": 0,
            "credits_renewal_date": None,
            "period_consumption": 0,
            "period_consumption_message": "Nenhum consumo registrado",
            "total_queries": 0,
            "total_queries_message": "Nenhuma consulta realizada",
            "total_cost": 0.0,
            "avg_cost_per_query": 0.0,
            "avg_cost_message": "Custo médio por consulta: R$ 0,00",
            "consumption_chart": {
                "labels": [],
                "data": [],
                "datasets": [{
                    "label": "Consultas por Mês",
                    "data": [],
                    "borderColor": "rgb(59, 130, 246)",
                    "backgroundColor": "rgba(59, 130, 246, 0.1)",
                    "tension": 0.1
                }]
            },
            "volume_by_api": {
                "labels": [],
                "data": [],
                "colors": []
            },
            "period": "30d",
            "success_rate": 0
        }

# Instância global do serviço
dashboard_service = DashboardService()

"""
Serviço para dados do dashboard (Visão Geral)
"""
import structlog
from typing import Dict, Any, Optional, List
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
            
            # Buscar dados das novas tabelas de consultas do período
            consultations = self.supabase.table("consultations").select(
                "*, consultation_details(*, consultation_types(*))"
            ).eq("user_id", user_id).gte("created_at", start_date.isoformat()).lte("created_at", end_date.isoformat()).execute()
            
            # Fallback para tabelas antigas se as novas não existirem
            if not consultations.data:
                # Buscar dados de consultas do período (tabela antiga)
                query_history = self.supabase.table("query_history").select("*").eq("user_id", user_id).gte("created_at", start_date.isoformat()).lte("created_at", end_date.isoformat()).execute()
                
                # Buscar dados de analytics do período
                analytics = self.supabase.table("query_analytics").select("*").eq("user_id", user_id).gte("date", start_date.strftime("%Y-%m-%d")).lte("date", end_date.strftime("%Y-%m-%d")).execute()
                
                # Usar dados antigos se consultas novas não existirem
                if query_history.data:
                    total_queries = len(query_history.data)
                    successful_queries = len([q for q in query_history.data if q.get("status") == "success"])
                    failed_queries = total_queries - successful_queries
                    total_credits_used = sum(q.get("credits_used", 0) for q in query_history.data)
                else:
                    total_queries = sum(a.get("total_queries", 0) for a in analytics.data)
                    successful_queries = sum(a.get("successful_queries", 0) for a in analytics.data)
                    failed_queries = sum(a.get("failed_queries", 0) for a in analytics.data)
                    total_credits_used = sum(a.get("total_credits_used", 0) for a in analytics.data)
            else:
                # Calcular estatísticas das novas tabelas
                total_queries = len(consultations.data)
                successful_queries = len([c for c in consultations.data if c.get("status") == "success"])
                failed_queries = total_queries - successful_queries
                
                # Calcular custo total em créditos (converter de centavos)
                total_cost_cents = sum(c.get("total_cost_cents", 0) for c in consultations.data)
                total_credits_used = total_cost_cents / 100  # Converter centavos para reais
            
            # Buscar assinatura do usuário (com fallback se não existir)
            credits_available = 10.0  # Créditos padrão de R$ 10,00
            credits_renewal_date = None
            
            try:
                subscription = self.supabase.table("subscriptions").select("*, subscription_plans(*)").eq("user_id", user_id).eq("status", "active").execute()
                
                if subscription.data:
                    plan = subscription.data[0].get("subscription_plans", {})
                    plan_limit = plan.get("queries_limit")
                    if plan_limit:
                        credits_used_this_period = total_credits_used
                        credits_available = max(0, (plan_limit / 100) - credits_used_this_period)  # Converter de centavos
                        credits_renewal_date = subscription.data[0].get("current_period_end")
            except Exception as sub_error:
                logger.warning("erro_buscar_assinatura", user_id=user_id, error=str(sub_error))
                # Usar valores padrão se não conseguir buscar assinatura
            
            # Calcular custo médio por consulta
            avg_cost_per_query = 0.0
            if total_queries > 0:
                # Assumir custo de R$ 0,10 por consulta (pode ser configurável)
                avg_cost_per_query = 0.10
            
            # Gerar dados de gráfico de consumo por período
            if consultations.data:
                # Usar dados das novas consultas para gráficos
                consumption_chart = self._generate_consumption_chart_v2(consultations.data, start_date, end_date)
                volume_by_api = self._generate_volume_by_api_v2(consultations.data)
            elif 'query_history' in locals() and query_history.data:
                # Usar dados antigos se disponíveis
                consumption_chart = self._generate_consumption_chart(query_history.data, start_date, end_date)
                volume_by_api = self._generate_volume_by_api(query_history.data)
            else:
                # Usar dados vazios se não tiver nenhuma fonte
                consumption_chart = []
                volume_by_api = {"protestos": 0, "receita_federal": 0, "outros": 0}
            
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
    
    def _generate_consumption_chart_v2(self, consultations_data: List[dict], start_date: datetime, end_date: datetime) -> List[dict]:
        """Gerar dados de gráfico de consumo das novas tabelas"""
        try:
            daily_data = {}
            current_date = start_date.date()
            
            # Inicializar todos os dias com zero
            while current_date <= end_date.date():
                daily_data[current_date.isoformat()] = {"protestos": 0, "receita_federal": 0, "outros": 0}
                current_date += timedelta(days=1)
            
            # Processar consultas
            for consultation in consultations_data:
                consultation_date = datetime.fromisoformat(consultation['created_at']).date().isoformat()
                if consultation_date in daily_data:
                    # Somar custos dos detalhes por tipo
                    details = consultation.get('consultation_details', [])
                    for detail in details:
                        cost_reais = detail.get('cost_cents', 0) / 100
                        type_info = detail.get('consultation_types', {})
                        type_code = type_info.get('code', 'outros')
                        
                        if type_code == 'protestos':
                            daily_data[consultation_date]["protestos"] += cost_reais
                        elif type_code == 'receita_federal':
                            daily_data[consultation_date]["receita_federal"] += cost_reais
                        else:
                            daily_data[consultation_date]["outros"] += cost_reais
            
            # Converter para formato do gráfico
            chart_data = []
            for date, costs in sorted(daily_data.items()):
                chart_data.append({
                    "date": date,
                    "protestos": round(costs["protestos"], 2),
                    "receita_federal": round(costs["receita_federal"], 2),
                    "outros": round(costs["outros"], 2)
                })
            
            return chart_data
            
        except Exception as e:
            logger.warning("erro_gerar_chart_v2", error=str(e))
            return []
    
    def _generate_volume_by_api_v2(self, consultations_data: List[dict]) -> dict:
        """Gerar dados de volume por API das novas tabelas"""
        try:
            volume_data = {"protestos": 0, "receita_federal": 0, "outros": 0}
            
            for consultation in consultations_data:
                details = consultation.get('consultation_details', [])
                for detail in details:
                    type_info = detail.get('consultation_types', {})
                    type_code = type_info.get('code', 'outros')
                    
                    if type_code == 'protestos':
                        volume_data["protestos"] += 1
                    elif type_code == 'receita_federal':
                        volume_data["receita_federal"] += 1
                    else:
                        volume_data["outros"] += 1
            
            return volume_data
            
        except Exception as e:
            logger.warning("erro_gerar_volume_v2", error=str(e))
            return {"protestos": 0, "receita_federal": 0, "outros": 0}

# Instância global do serviço
dashboard_service = DashboardService()

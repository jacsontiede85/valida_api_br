"""
Serviço de Dashboard - Dados Reais do Banco de Dados
Integração completa com todos os serviços existentes (sem dados mock)
"""

import structlog
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, date
from api.middleware.auth_middleware import get_supabase_client
from api.services.consultation_types_service import consultation_types_service
from api.services.credit_service import credit_service
from api.services.history_service import history_service

logger = structlog.get_logger("dashboard_service")


class DashboardService:
    """
    Serviço de dashboard com dados 100% reais do banco de dados
    Integra com todos os serviços existentes do sistema
    """
    
    def __init__(self):
        """Inicializa o serviço com integrações"""
        self.supabase = get_supabase_client()
        self.consultation_types = consultation_types_service
        self.credit_service = credit_service
        self.history_service = history_service
    
    async def get_dashboard_data(self, user_id: str, period: str = "30d") -> Dict[str, Any]:
        """
        Obtém todos os dados do dashboard para o usuário
        
        Args:
            user_id: ID do usuário
            period: Período para análise (today, 7d, 30d, 90d, 120d, 180d, 365d)
            
        Returns:
            Dict com todos os dados do dashboard
        """
        try:
            logger.info("buscando_dados_dashboard", user_id=user_id, period=period)
            
            # Buscar dados em paralelo para melhor performance
            credits_data = await self._get_credits(user_id)
            consultations_data = await self._get_consultations(user_id, period)
            costs_data = await self._get_consultation_costs()
            usage_stats = await self._calculate_usage_stats(consultations_data)
            charts_data = await self._generate_charts(consultations_data, period)
            
            # Calcular estatísticas agregadas
            total_cost_reais = sum(c.get("total_cost_cents", 0) for c in consultations_data) / 100
            total_consultations = len(consultations_data)
            
            result = {
                "credits": credits_data,
                "usage": {
                    "total_consultations": total_consultations,
                    "total_cost": f"R$ {total_cost_reais:.2f}",
                    "total_cost_raw": total_cost_reais,
                    **usage_stats
                },
                "costs": costs_data,
                "charts": charts_data,
                "period": period,
                "last_updated": datetime.now().isoformat(),
                "success_rate": self._calculate_success_rate(consultations_data)
            }
            
            logger.info("dados_dashboard_obtidos", 
                       user_id=user_id, 
                       consultas=total_consultations,
                       custo_total=total_cost_reais)
            
            return result
            
        except Exception as e:
            logger.error("erro_buscar_dados_dashboard", 
                        user_id=user_id, 
                        period=period, 
                        error=str(e))
            # Retornar dados vazios em caso de erro, mas nunca mock
            return await self._get_empty_state(period)
    
    async def _get_credits(self, user_id: str) -> Dict[str, Any]:
        """
        Busca créditos do usuário calculando saldo real baseado no histórico
        """
        try:
            # Buscar histórico de compras e uso
            credits_history = await self._get_credits_history(user_id)
            
            # Calcular saldo real: comprado - usado
            total_purchased = credits_history.get("total_purchased", 0)
            total_used = credits_history.get("total_used", 0)
            real_balance = total_purchased - total_used
            
            # Buscar dados de renovação automática da tabela user_credits
            user_credits = await credit_service.get_user_credits(user_id)
            if isinstance(user_credits, dict):
                auto_renewal = user_credits.get("auto_renewal_count", 0) > 0
                renewal_date = user_credits.get("last_auto_renewal")
            else:
                auto_renewal = getattr(user_credits, "auto_renewal_count", 0) > 0
                renewal_date = getattr(user_credits, "last_auto_renewal", None)
            
            # Atualizar saldo na tabela user_credits se estiver desatualizado
            if abs(real_balance - (user_credits.get("available_credits_cents", 0) / 100)) > 0.01:
                try:
                    await self._sync_credit_balance(user_id, real_balance)
                    logger.info("saldo_creditos_sincronizado", 
                               user_id=user_id, 
                               saldo_anterior=user_credits.get("available_credits_cents", 0) / 100,
                               saldo_real=real_balance)
                except Exception as sync_error:
                    logger.error("erro_sincronizar_saldo", 
                                user_id=user_id, 
                                error=str(sync_error))
            
            return {
                "available": f"R$ {real_balance:.2f}",
                "available_raw": real_balance,
                "purchased": f"R$ {total_purchased:.2f}",
                "purchased_raw": total_purchased,
                "used": f"R$ {total_used:.2f}",
                "used_raw": total_used,
                "auto_renewal": auto_renewal,
                "last_purchase": credits_history.get("last_purchase_date"),
                "renewal_date": renewal_date
            }
            
        except Exception as e:
            logger.error("erro_buscar_creditos", user_id=user_id, error=str(e))
            # Retornar dados vazios, não mock
            return {
                "available": "R$ 0,00",
                "available_raw": 0,
                "purchased": "R$ 0,00", 
                "purchased_raw": 0,
                "used": "R$ 0,00",
                "used_raw": 0,
                "auto_renewal": False,
                "last_purchase": None,
                "renewal_date": None
            }
    
    async def _sync_credit_balance(self, user_id: str, real_balance: float) -> None:
        """
        Sincroniza o saldo na tabela user_credits com o valor real calculado
        """
        try:
            if not self.supabase:
                return
            
            # Atualizar saldo na tabela user_credits
            balance_cents = int(real_balance * 100)
            
            self.supabase.table("user_credits").update({
                "available_credits_cents": balance_cents,
                "updated_at": datetime.now().isoformat()
            }).eq("user_id", user_id).execute()
            
            logger.info("saldo_sincronizado_com_sucesso", 
                       user_id=user_id, 
                       novo_saldo=real_balance)
            
        except Exception as e:
            logger.error("erro_sincronizar_saldo_creditos", 
                        user_id=user_id, 
                        error=str(e))
            raise
    
    async def _get_consultations(self, user_id: str, period: str) -> List[Dict[str, Any]]:
        """
        Busca consultas das tabelas corretas (consultations + consultation_details)
        """
        try:
            if not self.supabase:
                return []
            
            # Calcular período
            start_date, end_date = self._calculate_period_dates(period)
            
            # Buscar consultas e detalhes separadamente (JOIN está com problema)
            # 🔧 CORRIGIDO: Usar formato completo de timestamp com hora
            start_timestamp = f"{start_date.isoformat()}T00:00:00"
            end_timestamp = f"{end_date.isoformat()}T23:59:59"
            
            # 1. Buscar consultas primeiro
            consultations_response = self.supabase.table("consultations").select(
                "id, user_id, cnpj, total_cost_cents, status, created_at"
            ).eq("user_id", user_id).gte("created_at", start_timestamp).lte("created_at", end_timestamp).order("created_at", desc=True).execute()
            
            consultations = consultations_response.data or []
            
            # 2. Buscar detalhes para cada consulta separadamente
            for consultation in consultations:
                cons_id = consultation["id"]
                
                # Buscar consultation_details primeiro
                details_response = self.supabase.table("consultation_details").select(
                    "id, consultation_id, consultation_type_id, cost_cents, success, response_data, cache_used, response_time_ms, error_message"
                ).eq("consultation_id", cons_id).execute()
                
                details = details_response.data or []
                
                # Para cada detail, buscar o consultation_type separadamente
                for detail in details:
                    type_id = detail.get("consultation_type_id")
                    if type_id:
                        type_response = self.supabase.table("consultation_types").select(
                            "id, code, name, cost_cents, is_active"
                        ).eq("id", type_id).execute()
                        
                        if type_response.data:
                            detail["consultation_types"] = type_response.data[0]
                        else:
                            detail["consultation_types"] = {"code": "outros", "name": "Outros"}
                    else:
                        detail["consultation_types"] = {"code": "outros", "name": "Outros"}
                
                # Adicionar detalhes à consulta
                consultation["consultation_details"] = details
            
            logger.info("consultas_encontradas", 
                       user_id=user_id, 
                       count=len(consultations), 
                       period=period)
            
            return consultations
            
        except Exception as e:
            logger.error("erro_buscar_consultas", 
                        user_id=user_id, 
                        period=period, 
                        error=str(e))
            return []
    
    async def _get_consultation_costs(self) -> Dict[str, Any]:
        """
        Busca custos dos tipos de consulta usando consultation_types_service
        """
        try:
            # Buscar todos os tipos de consulta com custos reais
            all_types = await self.consultation_types.get_all_types()
            
            costs_data = {}
            for type_code, type_data in all_types.items():
                costs_data[type_code] = {
                    "cost_cents": type_data["cost_cents"],
                    "cost_formatted": f"R$ {type_data['cost_cents']/100:.2f}",
                    "name": type_data["name"],
                    "description": type_data.get("description", "")
                }
            
            logger.info("custos_obtidos", types_count=len(costs_data))
            return costs_data
            
        except Exception as e:
            logger.error("erro_buscar_custos", error=str(e))
            return {}
    
    async def _calculate_usage_stats(self, consultations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calcula estatísticas de uso baseadas nas consultas
        """
        try:
            # Inicializar contadores por tipo
            usage_by_type = {}
            cost_by_type = {}
            success_by_type = {}
            
            # Processar cada consulta e seus detalhes
            for consultation in consultations:
                details = consultation.get("consultation_details", [])
                
                for detail in details:
                    type_info = detail.get("consultation_types", {})
                    type_code = type_info.get("code", "unknown")
                    type_name = type_info.get("name", type_code.title())
                    
                    # Contar consultas por tipo
                    if type_code not in usage_by_type:
                        usage_by_type[type_code] = {"count": 0, "name": type_name}
                        cost_by_type[type_code] = {"cost_cents": 0, "name": type_name}
                        success_by_type[type_code] = {"success": 0, "total": 0}
                    
                    usage_by_type[type_code]["count"] += 1
                    cost_by_type[type_code]["cost_cents"] += detail.get("cost_cents", 0)
                    success_by_type[type_code]["total"] += 1
                    
                    if detail.get("success", False):
                        success_by_type[type_code]["success"] += 1
            
            # Formatar dados para o frontend
            formatted_usage = {}
            formatted_costs = {}
            
            for type_code, data in usage_by_type.items():
                formatted_usage[f"{type_code}_count"] = data["count"]
                
            for type_code, data in cost_by_type.items():
                formatted_costs[f"{type_code}_cost"] = f"R$ {data['cost_cents']/100:.2f}"
                formatted_costs[f"{type_code}_cost_raw"] = data["cost_cents"] / 100
            
            return {
                **formatted_usage,
                **formatted_costs,
                "usage_by_type": usage_by_type,
                "success_by_type": success_by_type
            }
            
        except Exception as e:
            logger.error("erro_calcular_estatisticas_uso", error=str(e))
            return {}
    
    async def _generate_charts(self, consultations: List[Dict[str, Any]], period: str) -> Dict[str, Any]:
        """
        Gera dados para os gráficos baseados nas consultas
        """
        try:
            consumption_chart = await self._generate_consumption_chart_data(consultations, period)
            volume_chart = await self._generate_volume_chart_data(consultations)
            cost_breakdown = await self._generate_cost_breakdown_data(consultations)
            
            return {
                "consumption": consumption_chart,
                "volume": volume_chart,
                "cost_breakdown": cost_breakdown,
                "trend": await self._generate_trend_data(consultations, period)
            }
            
        except Exception as e:
            logger.error("erro_gerar_graficos", error=str(e))
            return self._get_empty_charts_data()
    
    async def _generate_consumption_chart_data(self, consultations: List[Dict[str, Any]], period: str) -> Dict[str, Any]:
        """
        Gera dados do gráfico de consumo por período
        """
        try:
            start_date, end_date = self._calculate_period_dates(period)
            
            # Agrupar por data
            daily_data = {}
            current_date = start_date
        
            # Inicializar todos os dias com zero para TODOS os tipos
            tipos_disponiveis = ["protestos", "receita_federal", "simples_nacional", "cadastro_contribuintes", "geocodificacao", "suframa"]
            
            while current_date <= end_date:
                day_data = {"total": 0}
                # Adicionar cada tipo individualmente
                for tipo in tipos_disponiveis:
                    day_data[tipo] = 0
                
                daily_data[current_date.strftime("%Y-%m-%d")] = day_data
                current_date += timedelta(days=1)
            
            # Processar consultas reais
            for consultation in consultations:
                consultation_date = datetime.fromisoformat(consultation["created_at"]).date()
                date_key = consultation_date.strftime("%Y-%m-%d")
                
                if date_key in daily_data:
                    daily_data[date_key]["total"] += consultation.get("total_cost_cents", 0) / 100
                    
                    # Processar detalhes por tipo
                    details = consultation.get("consultation_details", [])
                    for detail in details:
                        type_info = detail.get("consultation_types", {})
                        type_code = type_info.get("code", "outros")
                        cost_reais = detail.get("cost_cents", 0) / 100
                        
                        # Adicionar ao tipo específico se existir
                        if type_code in tipos_disponiveis:
                            daily_data[date_key][type_code] += cost_reais
                        # Se não existir, não processar (evitar categoria genérica "outros")
            
            # Converter para formato Chart.js com TODOS os tipos
            labels = []
            datasets = {"total": []}
            
            # Inicializar datasets para todos os tipos
            for tipo in tipos_disponiveis:
                datasets[tipo] = []
            
            # Cores para cada tipo
            type_colors = {
                "protestos": {"border": "#EF4444", "bg": "rgba(239, 68, 68, 0.1)"},
                "receita_federal": {"border": "#10B981", "bg": "rgba(16, 185, 129, 0.1)"},
                "simples_nacional": {"border": "#F59E0B", "bg": "rgba(245, 158, 11, 0.1)"},
                "cadastro_contribuintes": {"border": "#8B5CF6", "bg": "rgba(139, 92, 246, 0.1)"},
                "geocodificacao": {"border": "#06B6D4", "bg": "rgba(6, 182, 212, 0.1)"},
                "suframa": {"border": "#EC4899", "bg": "rgba(236, 72, 153, 0.1)"}
            }
            
            # Nomes amigáveis para os tipos
            type_labels = {
                "protestos": "Protestos",
                "receita_federal": "Receita Federal", 
                "simples_nacional": "Simples Nacional",
                "cadastro_contribuintes": "Cadastro Contribuintes",
                "geocodificacao": "Geocodificação",
                "suframa": "Suframa"
            }
            
            # Processar dados por data
            for date_key in sorted(daily_data.keys()):
                date_obj = datetime.strptime(date_key, "%Y-%m-%d")
                labels.append(date_obj.strftime("%d/%m"))
                
                # Adicionar dados de cada tipo
                datasets["total"].append(round(daily_data[date_key]["total"], 2))
                for tipo in tipos_disponiveis:
                    datasets[tipo].append(round(daily_data[date_key][tipo], 2))
        
            # Gerar datasets finais
            chart_datasets = [
                {
                    "label": "Total",
                    "data": datasets["total"],
                    "borderColor": "#3B82F6",
                    "backgroundColor": "rgba(59, 130, 246, 0.1)",
                    "borderWidth": 3
                }
            ]
            
            # Adicionar dataset para cada tipo que tem dados
            for tipo in tipos_disponiveis:
                if any(val > 0 for val in datasets[tipo]):
                    color_info = type_colors.get(tipo, {"border": "#6B7280", "bg": "rgba(107, 114, 128, 0.1)"})
                    chart_datasets.append({
                        "label": type_labels.get(tipo, tipo.title()),
                        "data": datasets[tipo],
                        "borderColor": color_info["border"],
                        "backgroundColor": color_info["bg"],
                        "borderWidth": 2
                    })
        
            return {
                "labels": labels,
                "datasets": chart_datasets
            }
            
        except Exception as e:
            logger.error("erro_gerar_grafico_consumo", error=str(e))
            return {"labels": [], "datasets": []}
    
    async def _generate_volume_chart_data(self, consultations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Gera dados do gráfico de volume por tipo de consulta
        CORRIGIDO: Conta consultas únicas por tipo, não consultation_details
        """
        try:
            type_counts = {}
            type_colors = {
                "protestos": "#EF4444",
                "receita_federal": "#10B981", 
                "simples_nacional": "#F59E0B",
                "cadastro_contribuintes": "#8B5CF6",
                "geocodificacao": "#06B6D4",
                "suframa": "#EC4899"
            }
            
            # 🔧 CORRIGIDO: Contar consultas únicas por tipo
            for consultation in consultations:
                details = consultation.get("consultation_details", [])
                
                # Obter tipos únicos desta consulta (evita contar duplicatas)
                types_in_consultation = set()
                
                for detail in details:
                    type_info = detail.get("consultation_types", {})
                    type_code = type_info.get("code", "outros")
                    type_name = type_info.get("name", type_code.title())
                    
                    types_in_consultation.add((type_code, type_name))
                
                # Contar esta consulta uma vez para cada tipo que ela contém
                for type_code, type_name in types_in_consultation:
                    if type_code not in type_counts:
                        type_counts[type_code] = {"count": 0, "name": type_name}
                    type_counts[type_code]["count"] += 1  # ✅ +1 por consulta única
            
            # Converter para formato Chart.js com informações aprimoradas
            labels = []
            data = []
            colors = []
            
            # Calcular total de usos para percentuais
            total_usos = sum(info["count"] for info in type_counts.values())
            
            for type_code, info in type_counts.items():
                count = info["count"]
                name = info["name"]
                
                # Adicionar percentual ao label para melhor contexto
                if total_usos > 0:
                    percentage = (count / total_usos) * 100
                    enhanced_label = f"{name} ({percentage:.1f}%)"
                else:
                    enhanced_label = name
                
                labels.append(enhanced_label)
                data.append(count)
                colors.append(type_colors.get(type_code, "#6B7280"))
        
            return {
                "labels": labels,
                "data": data,
                "backgroundColor": colors,
                "borderWidth": 0,
                "total_usos": total_usos,
                "breakdown_percentual": {
                    type_code: {
                        "count": info["count"],
                        "percentage": (info["count"] / total_usos * 100) if total_usos > 0 else 0
                    } for type_code, info in type_counts.items()
                }
            }
            
        except Exception as e:
            logger.error("erro_gerar_grafico_volume", error=str(e))
            return {"labels": [], "data": [], "backgroundColor": []}
    
    async def _generate_cost_breakdown_data(self, consultations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Gera dados de breakdown de custos por tipo
        """
        try:
            cost_by_type = {}
            
            # Calcular custos por tipo
            for consultation in consultations:
                details = consultation.get("consultation_details", [])
                for detail in details:
                    type_info = detail.get("consultation_types", {})
                    type_code = type_info.get("code", "outros")
                    type_name = type_info.get("name", type_code.title())
                    cost_reais = detail.get("cost_cents", 0) / 100
                    
                    if type_code not in cost_by_type:
                        cost_by_type[type_code] = {"cost": 0, "name": type_name}
                    cost_by_type[type_code]["cost"] += cost_reais
            
            # Converter para formato Chart.js
            labels = []
            data = []
            colors = ["#EF4444", "#10B981", "#F59E0B", "#8B5CF6", "#06B6D4", "#EC4899"]
            
            for i, (type_code, info) in enumerate(cost_by_type.items()):
                labels.append(f"{info['name']} (R$ {info['cost']:.2f})")
                data.append(round(info["cost"], 2))
        
            return {
                "labels": labels,
                "data": data,
                "backgroundColor": colors[:len(labels)]
            }
            
        except Exception as e:
            logger.error("erro_gerar_breakdown_custos", error=str(e))
            return {"labels": [], "data": [], "backgroundColor": []}
    
    async def _generate_trend_data(self, consultations: List[Dict[str, Any]], period: str) -> List[Dict[str, Any]]:
        """
        Gera dados de tendência para últimos dias
        """
        try:
            start_date, end_date = self._calculate_period_dates(period)
            trend_data = []
            
            # Gerar dados dos últimos 7 dias para tendência
            current_date = end_date - timedelta(days=6)
            while current_date <= end_date:
                day_consultations = [
                    c for c in consultations 
                    if datetime.fromisoformat(c["created_at"]).date() == current_date
                ]
                
                trend_data.append({
                    "date": current_date.strftime("%Y-%m-%d"),
                    "label": current_date.strftime("%d/%m"),
                    "count": len(day_consultations),
                    "cost": sum(c.get("total_cost_cents", 0) for c in day_consultations) / 100
                })
                
                current_date += timedelta(days=1)
            
            return trend_data
            
        except Exception as e:
            logger.error("erro_gerar_dados_tendencia", error=str(e))
            return []
    
    async def _get_credits_history(self, user_id: str) -> Dict[str, Any]:
        """
        Busca histórico de créditos (compras e uso) de forma mais precisa
        """
        try:
            if not self.supabase:
                return {"total_purchased": 0, "total_used": 0, "last_purchase_date": None}
            
            # Buscar todas as transações de créditos
            try:
                all_transactions = self.supabase.table("credit_transactions").select("*").eq("user_id", user_id).execute()
            except:
                all_transactions = {"data": []}
            
            # Calcular compras e uso baseado nas transações
            total_purchased = 0
            total_used = 0
            last_purchase = None
            
            if all_transactions.data:
                for transaction in all_transactions.data:
                    amount_cents = transaction.get("amount_cents", 0)
                    transaction_type = transaction.get("type", "")
                    
                    if transaction_type == "purchase":
                        total_purchased += amount_cents
                        if last_purchase is None or transaction.get("created_at", "") > last_purchase:
                            last_purchase = transaction.get("created_at")
                    elif transaction_type == "usage":
                        # Transações de uso são negativas, então somamos o valor absoluto
                        total_used += abs(amount_cents)
            
            # Converter para reais
            total_purchased = total_purchased / 100
            total_used = total_used / 100
            
            # Fallback: se não há transações, calcular baseado nas consultas
            if total_used == 0:
                try:
                    consultations = self.supabase.table("consultations").select("total_cost_cents").eq("user_id", user_id).execute()
                    total_used = sum(c.get("total_cost_cents", 0) for c in (consultations.data or [])) / 100
                except:
                    total_used = 0
            
            return {
                "total_purchased": total_purchased,
                "total_used": total_used,
                "last_purchase_date": last_purchase
            }
            
        except Exception as e:
            logger.error("erro_buscar_historico_creditos", user_id=user_id, error=str(e))
            return {"total_purchased": 0, "total_used": 0, "last_purchase_date": None}
    
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
    
    def _calculate_success_rate(self, consultations: List[Dict[str, Any]]) -> float:
        """
        Calcula taxa de sucesso das consultas
        """
        if not consultations:
            return 0.0
        
        successful = sum(1 for c in consultations if c.get("status") == "success")
        return round((successful / len(consultations)) * 100, 1)
    
    def _get_empty_charts_data(self) -> Dict[str, Any]:
        """
        Retorna estrutura vazia para gráficos
        """
        return {
            "consumption": {"labels": [], "datasets": []},
            "volume": {"labels": [], "data": [], "backgroundColor": []},
            "cost_breakdown": {"labels": [], "data": [], "backgroundColor": []},
            "trend": []
        }
    
    async def _get_empty_state(self, period: str) -> Dict[str, Any]:
        """
        Retorna estado vazio quando há erro
        """
        return {
            "credits": {
                "available": "R$ 0,00",
                "available_raw": 0,
                "purchased": "R$ 0,00",
                "purchased_raw": 0,
                "used": "R$ 0,00", 
                "used_raw": 0,
                "auto_renewal": False
            },
            "usage": {
                "total_consultations": 0,
                "total_cost": "R$ 0,00",
                "total_cost_raw": 0,
                "protestos_count": 0,
                "receita_federal_count": 0
            },
            "costs": {},
            "charts": self._get_empty_charts_data(),
            "period": period,
            "last_updated": datetime.now().isoformat(),
            "success_rate": 0.0
        }


# Instância global do serviço
dashboard_service = DashboardService()
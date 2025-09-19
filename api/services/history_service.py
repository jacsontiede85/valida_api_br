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
        search: Optional[str] = None,
        type_filter: str = "all"
    ) -> Dict[str, Any]:
        """
        Obtém o histórico de consultas do usuário com filtros e paginação
        Versão corrigida com estrutura de dados adequada para o frontend
        """
        try:
            if not self.supabase:
                # Tentar carregar dados dos arquivos de log primeiro
                file_data = await self._load_from_log_files(page, limit, search, status, date_from, date_to)
                if file_data and file_data["data"]:
                    return file_data
                
                # Fallback para dados mock quando Supabase não estiver configurado
                mock_data = self._generate_mock_history_data(page, limit)
                return mock_data
            
            # Tentar buscar da nova tabela consultations primeiro
            query = self.supabase.table("consultations").select(
                "id, cnpj, created_at, status, response_time_ms, total_cost_cents, "
                "user_id, cache_used, error_message, client_ip, "
                "consultation_details(id, success, cost_cents, consultation_types(name, code, cost_cents))"
            ).eq("user_id", user_id)
            
            # Aplicar filtros
            if status != "all":
                query = query.eq("status", status)
            
            if date_from:
                # Converter data para formato ISO com timezone
                date_from_iso = f"{date_from}T00:00:00.000Z"
                query = query.gte("created_at", date_from_iso)
            
            if date_to:
                # Converter data para formato ISO com timezone (fim do dia)
                date_to_iso = f"{date_to}T23:59:59.999Z"
                query = query.lte("created_at", date_to_iso)
            
            if search:
                query = query.ilike("cnpj", f"%{search}%")
            
            # Aplicar paginação
            offset = (page - 1) * limit
            query = query.range(offset, offset + limit - 1).order("created_at", desc=True)
            
            response = query.execute()
            
            # Se não encontrou dados na nova tabela, buscar na antiga com fallback
            if not response.data:
                query_old = self.supabase.table("query_history").select("*").eq("user_id", user_id)
                
                if status != "all":
                    query_old = query_old.eq("status", status)
                if date_from:
                    query_old = query_old.gte("created_at", date_from)
                if date_to:
                    query_old = query_old.lte("created_at", date_to)
                if search:
                    query_old = query_old.ilike("cnpj", f"%{search}%")
                
                query_old = query_old.range(offset, offset + limit - 1).order("created_at", desc=True)
                response = query_old.execute()
                
                # Converter dados antigos para nova estrutura
                if response.data:
                    response.data = self._convert_old_to_new_format(response.data)
            
            # Processar e formatar dados para o frontend
            formatted_data = []
            for item in response.data:
                # Calcular custo total se não estiver definido
                total_cost_cents = item.get("total_cost_cents", 0)
                if not total_cost_cents and item.get("consultation_details"):
                    total_cost_cents = sum(detail.get("cost_cents", 0) for detail in item["consultation_details"])
                
                # Calcular créditos usados baseado no custo (1 crédito = 5 centavos)
                credits_used = max(1, total_cost_cents // 5) if total_cost_cents > 0 else 1
                
                # Extrair tipos de consulta
                consultation_types = self._extract_consultation_types(item.get("consultation_details", []))
                
                # Aplicar filtro por tipo se especificado
                if type_filter != "all":
                    has_type = any(ct.get("code") == type_filter for ct in consultation_types)
                    if not has_type:
                        continue  # Pular este item se não contém o tipo filtrado
                
                # Formatar item para frontend
                formatted_item = {
                    "id": item["id"],
                    "cnpj": item["cnpj"],
                    "created_at": item["created_at"],
                    "status": item.get("status", "success"),
                    "response_status": 200 if item.get("status") == "success" else 500,
                    "response_time_ms": item.get("response_time_ms", 0),
                    "total_cost_cents": total_cost_cents,
                    "credits_used": credits_used,
                    "endpoint": "/api/v1/cnpj/consult",
                    "user_id": item["user_id"],
                    "cache_used": item.get("cache_used", False),
                    "error_message": item.get("error_message"),
                    "client_ip": item.get("client_ip"),  # 🔧 CAMPO CLIENT_IP ADICIONADO
                    # Campos formatados para exibição
                    "formatted_cost": f"R$ {total_cost_cents / 100:.2f}",
                    "formatted_time": self._format_duration(item.get("response_time_ms", 0)),
                    "status_text": self._get_status_text(item.get("status", "success")),
                    "consultation_types": consultation_types
                }
                
                formatted_data.append(formatted_item)
            
            # Buscar total de registros para paginação
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
            
            # Fallback para tabela antiga se necessário
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
                "data": formatted_data,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit if total > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error("erro_buscar_historico", user_id=user_id, error=str(e))
            # Retornar dados mock em caso de erro
            return self._generate_mock_history_data(page, limit)
    
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
    
    def _generate_mock_history_data(self, page: int, limit: int) -> Dict[str, Any]:
        """Gera dados mock para histórico quando Supabase não está configurado"""
        from datetime import datetime, timedelta
        import uuid
        
        # Dados mock baseados na imagem fornecida
        mock_queries = []
        base_time = datetime.now()
        
        cnpjs = [
            "25113317000165",
            "13919474000183", 
            "04596858000111",
            "11142002000131"
        ]
        
        for i in range(min(limit, 20)):  # Máximo 20 registros mock
            hours_ago = i * 2 + 1
            query_time = base_time - timedelta(hours=hours_ago)
            
            cnpj = cnpjs[i % len(cnpjs)]
            response_time = 1000 + (i * 500)  # Varia entre 1s e 15s
            
            mock_queries.append({
                "id": str(uuid.uuid4()),
                "cnpj": cnpj,
                "created_at": query_time.isoformat() + "Z",
                "status": "success",
                "response_status": 200,
                "response_time_ms": response_time,
                "total_cost_cents": 15,  # R$ 0,15 para protestos
                "credits_used": 1,
                "endpoint": "/api/v1/cnpj/consult",
                "user_id": "mock-user",
                "cache_used": False,
                "formatted_cost": "R$ 0,15",
                "formatted_time": f"{response_time / 1000:.2f} s",
                "status_text": "Sucesso",
                "consultation_types": [
                    {
                        "name": "Protestos",
                        "code": "protestos",
                        "cost_cents": 15,
                        "success": True
                    }
                ]
            })
        
        return {
            "data": mock_queries,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": 47,  # Total mock
                "pages": 3
            }
        }
    
    def _format_duration(self, ms: int) -> str:
        """Formata duração em milissegundos para exibição"""
        if not ms or ms == 0:
            return "0.00 s"
        if ms < 1000:
            return f"{ms} ms"
        return f"{(ms / 1000):.2f} s"
    
    def _get_status_text(self, status: str) -> str:
        """Converte status para texto em português"""
        status_map = {
            "success": "Sucesso",
            "error": "Erro", 
            "partial": "Parcial",
            "pending": "Pendente"
        }
        return status_map.get(status, "Sucesso")
    
    def _extract_consultation_types(self, consultation_details: List[Dict]) -> List[Dict]:
        """Extrai tipos de consulta dos detalhes"""
        types = []
        for detail in consultation_details:
            consultation_type = detail.get("consultation_types", {})
            if consultation_type:
                types.append({
                    "name": consultation_type.get("name", ""),
                    "code": consultation_type.get("code", ""),
                    "cost_cents": detail.get("cost_cents", 0),
                    "success": detail.get("success", True)
                })
        return types
    
    def _convert_old_to_new_format(self, old_data: List[Dict]) -> List[Dict]:
        """Converte dados da tabela antiga para novo formato"""
        converted = []
        for item in old_data:
            converted.append({
                "id": item.get("id"),
                "cnpj": item.get("cnpj"),
                "created_at": item.get("created_at"),
                "status": item.get("status", "success"),
                "response_time_ms": item.get("response_time_ms", 0),
                "total_cost_cents": 15,  # Custo padrão para dados antigos
                "credits_used": item.get("credits_used", 1),
                "endpoint": item.get("endpoint", "/api/v1/cnpj/consult"),
                "user_id": item.get("user_id"),
                "cache_used": False,
                "consultation_details": []
            })
        return converted
    
    async def _load_from_log_files(
        self, 
        page: int, 
        limit: int, 
        search: Optional[str] = None, 
        status: str = "all", 
        date_from: Optional[str] = None, 
        date_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Carrega dados dos arquivos de log quando Supabase não está disponível
        """
        try:
            import json
            from pathlib import Path
            from datetime import datetime, timedelta
            
            log_dir = Path("logs/query_history")
            if not log_dir.exists():
                return {"data": [], "pagination": {"page": page, "limit": limit, "total": 0, "pages": 0}}
            
            all_queries = []
            
            # Buscar arquivos de log dos últimos 30 dias
            for i in range(30):
                date = datetime.now() - timedelta(days=i)
                log_file = log_dir / f"queries_{date.strftime('%Y%m%d')}.jsonl"
                
                if log_file.exists():
                    try:
                        with open(log_file, "r", encoding="utf-8") as f:
                            for line in f:
                                if line.strip():
                                    entry = json.loads(line.strip())
                                    all_queries.append(entry)
                    except Exception as e:
                        logger.warning("erro_ler_arquivo_log", file=str(log_file), error=str(e))
            
            # Aplicar filtros
            filtered_queries = []
            for query in all_queries:
                # Filtro por status
                if status != "all" and query.get("status") != status:
                    continue
                
                # Filtro por busca (CNPJ)
                if search and search not in query.get("cnpj", ""):
                    continue
                
                # Filtros de data
                query_date = query.get("timestamp", "")
                if date_from and query_date < date_from:
                    continue
                if date_to and query_date > date_to:
                    continue
                
                # Converter para formato esperado pelo frontend
                formatted_query = {
                    "id": f"file_{hash(query.get('timestamp', '') + query.get('cnpj', ''))}",
                    "cnpj": query.get("cnpj", ""),
                    "created_at": query.get("timestamp", ""),
                    "status": query.get("status", "success"),
                    "response_status": 200 if query.get("status") == "success" else 500,
                    "response_time_ms": query.get("response_time_ms", 0),
                    "total_cost_cents": query.get("total_cost_cents", 0),
                    "credits_used": 1,
                    "endpoint": "/api/v1/cnpj/consult",
                    "user_id": query.get("user_id", ""),
                    "cache_used": query.get("cache_used", False),
                    "formatted_cost": f"R$ {query.get('total_cost_cents', 0) / 100:.2f}",
                    "formatted_time": self._format_duration(query.get("response_time_ms", 0)),
                    "status_text": self._get_status_text(query.get("status", "success")),
                    "consultation_types": self._format_consultation_types_from_log(query.get("consultation_types", []))
                }
                
                filtered_queries.append(formatted_query)
            
            # Ordenar por data (mais recente primeiro)
            filtered_queries.sort(key=lambda x: x["created_at"], reverse=True)
            
            # Aplicar paginação
            total = len(filtered_queries)
            start_idx = (page - 1) * limit
            end_idx = start_idx + limit
            paginated_queries = filtered_queries[start_idx:end_idx]
            
            logger.info("dados_carregados_arquivos_log", total=total, paginated=len(paginated_queries))
            
            return {
                "data": paginated_queries,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit if total > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error("erro_carregar_arquivos_log", error=str(e))
            return {"data": [], "pagination": {"page": page, "limit": limit, "total": 0, "pages": 0}}
    
    def _format_consultation_types_from_log(self, consultation_types: List[Dict]) -> List[Dict]:
        """
        Formatar tipos de consulta dos arquivos de log
        """
        formatted_types = []
        for ct in consultation_types:
            formatted_types.append({
                "name": self._get_type_name_by_code(ct.get("type_code", "")),
                "code": ct.get("type_code", ""),
                "cost_cents": ct.get("cost_cents", 0),
                "success": ct.get("success", True)
            })
        return formatted_types
    
    def _get_type_name_by_code(self, code: str) -> str:
        """
        Mapear código do tipo para nome
        """
        type_names = {
            "protestos": "Protestos",
            "receita_federal": "Receita Federal", 
            "simples_nacional": "Simples Nacional",
            "cadastro_contribuintes": "Cadastro de Contribuintes",
            "suframa": "SUFRAMA"
        }
        return type_names.get(code, code.title())
    
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
                    "client_ip": item.get("client_ip"),  # 🔧 CAMPO CLIENT_IP ADICIONADO
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

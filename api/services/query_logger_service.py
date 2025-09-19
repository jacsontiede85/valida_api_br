"""
Serviço para registrar consultas no histórico - Nova Estrutura v2.0
"""
import structlog
from typing import Optional, Dict, Any, List
from datetime import datetime
import pytz
from api.middleware.auth_middleware import get_supabase_client

logger = structlog.get_logger("query_logger_service")

class QueryLoggerService:
    def __init__(self):
        self.supabase = get_supabase_client()
        # Timezone do Brasil
        self.brazil_tz = pytz.timezone('America/Sao_Paulo')
    
    def _get_brazil_datetime(self) -> datetime:
        """
        Retorna datetime atual no timezone do Brasil
        """
        return datetime.now(self.brazil_tz)
    
    def _get_brazil_datetime_iso(self) -> str:
        """
        Retorna datetime atual no timezone do Brasil em formato ISO
        """
        return self._get_brazil_datetime().isoformat()
    
    async def log_consultation(
        self,
        user_id: str,
        api_key_id: Optional[str],
        cnpj: str,
        consultation_types: List[Dict[str, Any]],  # Lista de tipos consultados com custos
        response_time_ms: Optional[int] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        cache_used: bool = False,
        client_ip: Optional[str] = None  # IP do cliente
    ) -> Optional[Dict[str, Any]]:
        """
        Registra uma consulta completa no novo formato
        
        Args:
            user_id: ID do usuário
            api_key_id: ID da API key usada
            cnpj: CNPJ consultado
            consultation_types: Lista de tipos consultados:
                [
                    {
                        "type_code": "protestos",
                        "cost_cents": 15,
                        "success": True,
                        "response_data": {...},
                        "cache_used": False,
                        "response_time_ms": 1500,
                        "error_message": None
                    },
                    ...
                ]
            response_time_ms: Tempo total da consulta
            status: Status geral da consulta
            error_message: Mensagem de erro se houver
            cache_used: Se usou cache geral
            
        Returns:
            Dict com dados da consulta registrada
        """
        try:
            logger.info(
                "tentando_registrar_consulta",
                user_id=user_id,
                cnpj=cnpj[:8] + "****",
                supabase_configurado=bool(self.supabase),
                consultation_types_count=len(consultation_types),
                status=status
            )
            
            if not self.supabase:
                logger.warning("Supabase não configurado - consulta não será registrada")
                # Salvar em log local como fallback
                await self._log_to_file(user_id, cnpj, consultation_types, response_time_ms, status, cache_used)
                return None
            
            # Calcular custo total
            total_cost_cents = sum(ct.get("cost_cents", 0) for ct in consultation_types)
            
            # 1. Inserir consulta principal
            consultation_data = {
                "user_id": user_id,
                "api_key_id": self._validate_api_key_id(api_key_id),
                "cnpj": cnpj,
                "total_cost_cents": total_cost_cents,
                "response_time_ms": response_time_ms,
                "status": status,
                "error_message": error_message,
                "cache_used": cache_used,
                "client_ip": client_ip,  # IP do cliente
                "created_at": self._get_brazil_datetime_iso()
            }
            
            logger.info("inserindo_consulta_principal", data=consultation_data)
            
            consultation_response = self.supabase.table("consultations").insert(consultation_data).execute()
            
            if not consultation_response.data:
                logger.error("falha_inserir_consulta_principal", user_id=user_id, cnpj=cnpj)
                # Fallback para log local
                await self._log_to_file(user_id, cnpj, consultation_types, response_time_ms, status, cache_used)
                return None
                
            consultation_id = consultation_response.data[0]["id"]
            
            logger.info("consulta_principal_inserida", consultation_id=consultation_id)
            
            # 2. Inserir detalhes por tipo de consulta
            details_success = await self._log_consultation_details(consultation_id, consultation_types)
            
            # 3. Atualizar analytics diários
            analytics_success = await self.update_daily_analytics(user_id, consultation_types, total_cost_cents)
            
            logger.info(
                "consulta_completa_registrada",
                user_id=user_id,
                cnpj=cnpj[:8] + "****",
                consultation_id=consultation_id,
                total_cost=total_cost_cents,
                types_count=len(consultation_types),
                details_success=details_success,
                analytics_success=analytics_success
            )
            
            return consultation_response.data[0]
                
        except Exception as e:
            logger.error("erro_registrar_consulta_completa", user_id=user_id, cnpj=cnpj[:8] + "****", error=str(e))
            # Fallback para log local em caso de erro
            await self._log_to_file(user_id, cnpj, consultation_types, response_time_ms, status, cache_used)
            return None
    
    async def _log_to_file(self, user_id: str, cnpj: str, consultation_types: List[Dict], response_time_ms: int, status: str, cache_used: bool):
        """
        Fallback para salvar consulta em arquivo quando Supabase não está disponível
        """
        try:
            import json
            from pathlib import Path
            
            log_dir = Path("logs/query_history")
            log_dir.mkdir(parents=True, exist_ok=True)
            
            log_entry = {
                "timestamp": self._get_brazil_datetime_iso(),
                "user_id": user_id,
                "cnpj": cnpj,
                "consultation_types": consultation_types,
                "response_time_ms": response_time_ms,
                "status": status,
                "cache_used": cache_used,
                "total_cost_cents": sum(ct.get("cost_cents", 0) for ct in consultation_types)
            }
            
            log_file = log_dir / f"queries_{self._get_brazil_datetime().strftime('%Y%m%d')}.jsonl"
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
            
            logger.info("consulta_salva_em_arquivo", file=str(log_file), user_id=user_id)
            
        except Exception as e:
            logger.error("erro_salvar_consulta_arquivo", error=str(e))
    
    async def _log_consultation_details(self, consultation_id: str, consultation_types: List[Dict[str, Any]]) -> bool:
        """
        Registra detalhes de cada tipo de consulta
        """
        try:
            details_to_insert = []
            
            for ct in consultation_types:
                # Obter ID do tipo de consulta
                type_id = await self._get_consultation_type_id(ct["type_code"])
                if not type_id:
                    logger.warning("tipo_consulta_nao_encontrado", type_code=ct["type_code"])
                    continue
                
                detail = {
                    "consultation_id": consultation_id,
                    "consultation_type_id": type_id,
                    "success": ct.get("success", True),
                    "cost_cents": ct.get("cost_cents", 0),
                    "response_data": ct.get("response_data"),
                    "cache_used": ct.get("cache_used", False),
                    "response_time_ms": ct.get("response_time_ms"),
                    "error_message": ct.get("error_message"),
                    "created_at": self._get_brazil_datetime_iso()
                }
                
                details_to_insert.append(detail)
            
            if details_to_insert:
                response = self.supabase.table("consultation_details").insert(details_to_insert).execute()
                return bool(response.data)
            
            return True
            
        except Exception as e:
            logger.error("erro_registrar_detalhes", consultation_id=consultation_id, error=str(e))
            return False
    
    async def _get_consultation_type_id(self, type_code: str) -> Optional[str]:
        """
        Obtém ID do tipo de consulta pelo código
        """
        try:
            response = self.supabase.table("consultation_types").select("id").eq("code", type_code).execute()
            return response.data[0]["id"] if response.data else None
        except Exception as e:
            logger.error("erro_obter_tipo_id", type_code=type_code, error=str(e))
            return None
    
    def _validate_api_key_id(self, api_key_id: Optional[str]) -> Optional[str]:
        """
        Valida se api_key_id é um UUID válido
        """
        if not api_key_id:
            return None
            
        try:
            import uuid
            uuid.UUID(api_key_id)
            return api_key_id
        except ValueError:
            logger.warning("api_key_id_invalido", api_key_id=api_key_id)
            return None
    
    async def update_daily_analytics(
        self,
        user_id: str,
        consultation_types: List[Dict[str, Any]],
        total_cost_cents: int
    ) -> bool:
        """
        Atualiza analytics diários com nova estrutura
        """
        try:
            if not self.supabase:
                return False
            
            today = self._get_brazil_datetime().date().isoformat()
            
            # Contar consultas por tipo
            consultations_by_type = {}
            costs_by_type = {}
            successful_count = 0
            failed_count = 0
            
            for ct in consultation_types:
                type_code = ct["type_code"]
                cost = ct.get("cost_cents", 0)
                success = ct.get("success", True)
                
                consultations_by_type[type_code] = consultations_by_type.get(type_code, 0) + 1
                costs_by_type[type_code] = costs_by_type.get(type_code, 0) + cost
                
                if success:
                    successful_count += 1
                else:
                    failed_count += 1
            
            # Verificar se já existe analytics para hoje
            existing = self.supabase.table("daily_analytics").select("*").eq("user_id", user_id).eq("date", today).execute()
            
            if existing.data:
                # Atualizar existente
                current = existing.data[0]
                
                # Mesclar consultations_by_type
                current_by_type = current.get("consultations_by_type", {})
                for type_code, count in consultations_by_type.items():
                    current_by_type[type_code] = current_by_type.get(type_code, 0) + count
                
                # Mesclar costs_by_type
                current_costs = current.get("costs_by_type", {})
                for type_code, cost in costs_by_type.items():
                    current_costs[type_code] = current_costs.get(type_code, 0) + cost
                
                update_data = {
                    "total_consultations": current["total_consultations"] + len(consultation_types),
                    "successful_consultations": current["successful_consultations"] + successful_count,
                    "failed_consultations": current["failed_consultations"] + failed_count,
                    "total_cost_cents": current["total_cost_cents"] + total_cost_cents,
                    "credits_used_cents": current["credits_used_cents"] + total_cost_cents,
                    "consultations_by_type": current_by_type,
                    "costs_by_type": current_costs,
                    "updated_at": self._get_brazil_datetime_iso()
                }
                
                response = self.supabase.table("daily_analytics").update(update_data).eq("id", current["id"]).execute()
            else:
                # Criar novo
                analytics_data = {
                    "user_id": user_id,
                    "date": today,
                    "total_consultations": len(consultation_types),
                    "successful_consultations": successful_count,
                    "failed_consultations": failed_count,
                    "total_cost_cents": total_cost_cents,
                    "credits_used_cents": total_cost_cents,
                    "consultations_by_type": consultations_by_type,
                    "costs_by_type": costs_by_type,
                    "created_at": self._get_brazil_datetime_iso()
                }
                
                response = self.supabase.table("daily_analytics").insert(analytics_data).execute()
            
            return bool(response.data)
            
        except Exception as e:
            logger.error("erro_atualizar_analytics_diarios", user_id=user_id, error=str(e))
            return False
    
    # Método de compatibilidade com código antigo
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
        Método de compatibilidade - mapeia para nova estrutura
        """
        # Mapear endpoint antigo para tipos de consulta
        consultation_types = []
        
        if "protest" in endpoint.lower() or "cnpj" in endpoint.lower():
            consultation_types.append({
                "type_code": "protestos",
                "cost_cents": 15,
                "success": success,
                "response_time_ms": response_time_ms,
                "cache_used": False
            })
        
        if not consultation_types:
            # Default para protestos se não conseguir mapear
            consultation_types.append({
                "type_code": "protestos", 
                "cost_cents": credits_used * 5,  # Converter créditos antigos
                "success": success,
                "response_time_ms": response_time_ms,
                "cache_used": False
            })
        
        status = "success" if success and response_status < 400 else "error"
        error_message = f"HTTP {response_status}" if response_status >= 400 else None
        
        return await self.log_consultation(
            user_id=user_id,
            api_key_id=api_key_id,
            cnpj=cnpj,
            consultation_types=consultation_types,
            response_time_ms=response_time_ms,
            status=status,
            error_message=error_message
        )

# Instância global do serviço
query_logger_service = QueryLoggerService()

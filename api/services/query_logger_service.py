"""
Serviço para registrar consultas no histórico - Nova Estrutura v2.0
MIGRADO: Supabase → MariaDB
"""
import structlog
from typing import Optional, Dict, Any, List
from datetime import datetime
import pytz
from api.database.connection import execute_sql, generate_uuid

logger = structlog.get_logger("query_logger_service")

class QueryLoggerService:
    def __init__(self):
        # Migrado de Supabase para MariaDB - não precisa de cliente específico
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
        client_ip: Optional[str] = None,  # IP do cliente
        response_data: Optional[Dict[str, Any]] = None  # JSON completo da resposta da API
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
            client_ip: IP do cliente
            response_data: JSON completo retornado pela rota /api/v1/cnpj/consult
            
        Returns:
            Dict com dados da consulta registrada
        """
        try:
            logger.info(
                "tentando_registrar_consulta_mariadb",
                user_id=user_id,
                cnpj=cnpj[:8] + "****",
                consultation_types_count=len(consultation_types),
                status=status
            )
            
            # Calcular custo total
            total_cost_cents = sum(ct.get("cost_cents", 0) for ct in consultation_types)
            
            # 1. Inserir consulta principal no MariaDB
            consultation_id = generate_uuid()
            
            # Converter response_data para JSON string se fornecido
            import json
            response_data_json = None
            if response_data:
                try:
                    response_data_json = json.dumps(response_data, ensure_ascii=False, default=str)
                except Exception as json_error:
                    logger.warning("erro_serializar_response_data", 
                                 user_id=user_id, 
                                 error=str(json_error))
                    response_data_json = None
            
            consultation_insert_sql = """
                INSERT INTO consultations 
                (id, user_id, api_key_id, cnpj, total_cost_cents, response_time_ms, 
                 status, error_message, cache_used, client_ip, response_data, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """
            
            consultation_params = (
                consultation_id,
                user_id,
                self._validate_api_key_id(api_key_id),
                cnpj,
                total_cost_cents,
                response_time_ms,
                status,
                error_message,
                cache_used,
                client_ip,
                response_data_json  # Novo campo response_data
            )
            
            logger.info("inserindo_consulta_principal_mariadb", consultation_id=consultation_id)
            
            result = await execute_sql(consultation_insert_sql, consultation_params, "none")
            
            if result["error"]:
                logger.error("falha_inserir_consulta_principal_mariadb", 
                           user_id=user_id, cnpj=cnpj, error=result["error"])
                # Fallback para log local
                await self._log_to_file(user_id, cnpj, consultation_types, response_time_ms, status, cache_used)
                return None
            
            logger.info("consulta_principal_inserida", consultation_id=consultation_id)
            
            # 2. Inserir detalhes por tipo de consulta
            details_success = await self._log_consultation_details(consultation_id, consultation_types)
            
            # ✅ REMOVIDO: update_daily_analytics - tabela daily_analytics descontinuada por ser redundante
            
            logger.info(
                "consulta_completa_registrada",
                user_id=user_id,
                cnpj=cnpj[:8] + "****",
                consultation_id=consultation_id,
                total_cost=total_cost_cents,
                types_count=len(consultation_types),
                details_success=details_success
                # ✅ REMOVIDO: analytics_success - daily_analytics descontinuada
            )
            
            # Retornar dados da consulta criada
            return {
                "id": consultation_id,
                "user_id": user_id,
                "cnpj": cnpj,
                "total_cost_cents": total_cost_cents,
                "response_time_ms": response_time_ms,
                "status": status,
                "cache_used": cache_used,
                "details_success": details_success,
                # ✅ REMOVIDO: analytics_success - daily_analytics descontinuada
                "created_at": self._get_brazil_datetime_iso()
            }
                
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
        MIGRADO: MariaDB
        """
        try:
            details_inserted = 0
            
            for ct in consultation_types:
                # Obter ID do tipo de consulta
                type_id = await self._get_consultation_type_id(ct["type_code"])
                if not type_id:
                    logger.warning("tipo_consulta_nao_encontrado", type_code=ct["type_code"])
                    continue
                
                # Inserir detalhe individual
                detail_id = generate_uuid()
                detail_insert_sql = """
                    INSERT INTO consultation_details 
                    (id, consultation_id, consultation_type_id, cost_cents, status,
                     response_data, error_message, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """
                
                # Serializar JSON para string
                import json
                response_data = ct.get("response_data")
                response_data_json = json.dumps(response_data) if response_data else None
                
                detail_params = (
                    detail_id,
                    consultation_id,
                    type_id,
                    ct.get("cost_cents", 0),
                    "success" if ct.get("success", True) else "error",
                    response_data_json,  # JSON serializado como string
                    ct.get("error_message")
                )
                
                result = await execute_sql(detail_insert_sql, detail_params, "none")
                
                if result["error"]:
                    logger.error("erro_inserir_detalhe_mariadb", 
                               consultation_id=consultation_id, 
                               type_code=ct["type_code"],
                               error=result["error"])
                else:
                    details_inserted += 1
            
            logger.info("detalhes_inseridos_mariadb", 
                       consultation_id=consultation_id,
                       total_tipos=len(consultation_types),
                       inseridos=details_inserted)
            
            return details_inserted > 0
            
        except Exception as e:
            logger.error("erro_registrar_detalhes_mariadb", consultation_id=consultation_id, error=str(e))
            return False
    
    async def _get_consultation_type_id(self, type_code: str) -> Optional[str]:
        """
        Obtém ID do tipo de consulta pelo código
        MIGRADO: MariaDB
        """
        try:
            result = await execute_sql(
                "SELECT id FROM consultation_types WHERE code = %s AND is_active = TRUE LIMIT 1",
                (type_code,),
                "one"
            )
            return result["data"]["id"] if result["data"] else None
        except Exception as e:
            logger.error("erro_obter_tipo_id_mariadb", type_code=type_code, error=str(e))
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
    
    # ✅ REMOVIDO: update_daily_analytics - tabela daily_analytics descontinuada por ser redundante
    # Analytics podem ser calculados on-demand via consultations quando necessário
    
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

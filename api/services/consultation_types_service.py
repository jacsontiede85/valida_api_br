"""
Serviço de Tipos de Consulta
Gerencia custos dinâmicos da tabela consultation_types com cache inteligente
"""

import structlog
import asyncio
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from api.middleware.auth_middleware import get_supabase_client

logger = structlog.get_logger(__name__)


class ConsultationTypesService:
    """
    Serviço para gerenciar tipos de consulta com custos dinâmicos
    """
    
    def __init__(self):
        """Inicializa o serviço com cache vazio"""
        self._cache: Dict[str, Any] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_minutes = 5  # TTL do cache: 5 minutos
        self._supabase = None
        
        # Mapeamento de códigos do sistema para códigos do banco
        self._code_mapping = {
            'protestos': 'protestos',
            'receita_federal': 'receita_federal', 
            'simples_nacional': 'simples_nacional',
            'registrations': 'cadastro_contribuintes',  # Mapeamento específico
            'geocoding': 'geocodificacao',              # Mapeamento específico
            'suframa': 'suframa'
        }
        
        # Custos padrão como fallback de segurança
        self._fallback_costs = {
            'protestos': 15,           # R$ 0,15
            'receita_federal': 5,      # R$ 0,05
            'simples_nacional': 5,     # R$ 0,05
            'cadastro_contribuintes': 5, # R$ 0,05
            'geocodificacao': 5,       # R$ 0,05
            'suframa': 5              # R$ 0,05
        }
    
    def _get_supabase(self):
        """Lazy initialization do Supabase client"""
        if self._supabase is None:
            self._supabase = get_supabase_client()
        return self._supabase
    
    def _map_system_code_to_db_code(self, system_code: str) -> str:
        """
        Mapeia código do sistema para código do banco de dados
        
        Args:
            system_code: Código usado no sistema (ex: 'registrations')
            
        Returns:
            str: Código correspondente no BD (ex: 'cadastro_contribuintes')
        """
        return self._code_mapping.get(system_code, system_code)
    
    def _is_cache_valid(self) -> bool:
        """
        Verifica se o cache está válido baseado no TTL
        
        Returns:
            bool: True se cache válido, False caso contrário
        """
        if not self._cache or not self._cache_timestamp:
            return False
        
        cache_age = datetime.now() - self._cache_timestamp
        return cache_age < timedelta(minutes=self._cache_ttl_minutes)
    
    async def _load_types_from_database(self) -> Dict[str, Dict]:
        """
        Carrega tipos de consulta diretamente do banco de dados
        
        Returns:
            Dict[str, Dict]: Dicionário com tipos indexados por código
        """
        try:
            supabase = self._get_supabase()
            if not supabase:
                logger.error("supabase_nao_configurado")
                return {}
            
            # Buscar apenas tipos ativos
            response = supabase.table("consultation_types").select("*").eq("is_active", True).execute()
            
            if not response.data:
                logger.warning("nenhum_tipo_consulta_encontrado")
                return {}
            
            # Indexar por código para acesso rápido
            types_dict = {}
            for tipo in response.data:
                code = tipo.get("code")
                if code:
                    types_dict[code] = {
                        "id": tipo.get("id"),
                        "code": code,
                        "name": tipo.get("name", ""),
                        "description": tipo.get("description", ""),
                        "cost_cents": int(tipo.get("cost_cents", 0)),
                        "provider": tipo.get("provider", ""),
                        "is_active": tipo.get("is_active", True)
                    }
            
            logger.info("tipos_carregados_bd", count=len(types_dict), codes=list(types_dict.keys()))
            return types_dict
            
        except Exception as e:
            logger.error("erro_carregar_tipos_bd", error=str(e), error_type=type(e).__name__)
            return {}
    
    async def get_all_types(self, force_refresh: bool = False) -> Dict[str, Dict]:
        """
        Obtém todos os tipos de consulta (com cache)
        
        Args:
            force_refresh: Se True, força refresh do cache
            
        Returns:
            Dict[str, Dict]: Tipos indexados por código
        """
        # Verificar se precisa atualizar cache
        if force_refresh or not self._is_cache_valid():
            logger.info("atualizando_cache_tipos", force_refresh=force_refresh)
            
            new_data = await self._load_types_from_database()
            
            if new_data:
                # Atualizar cache com dados válidos
                self._cache = new_data
                self._cache_timestamp = datetime.now()
                logger.info("cache_tipos_atualizado", count=len(new_data))
            else:
                # Manter cache existente se falha na busca
                logger.warning("mantendo_cache_existente_por_falha")
        
        return self._cache.copy()  # Retorna cópia para evitar modificações externas
    
    async def get_cost_by_code(self, system_code: str) -> Optional[int]:
        """
        Obtém custo de um tipo específico pelo código do sistema
        
        Args:
            system_code: Código usado no sistema (ex: 'protestos', 'registrations')
            
        Returns:
            Optional[int]: Custo em centavos ou None se não encontrado
        """
        try:
            # Mapear código do sistema para código do BD
            db_code = self._map_system_code_to_db_code(system_code)
            
            # Buscar tipos atualizados
            types = await self.get_all_types()
            
            if db_code in types:
                cost = types[db_code]["cost_cents"]
                logger.debug("custo_encontrado", system_code=system_code, db_code=db_code, cost=cost)
                return cost
            
            # Fallback para custo padrão
            fallback_cost = self._fallback_costs.get(db_code, self._fallback_costs.get(system_code))
            if fallback_cost:
                logger.warning("usando_custo_fallback", 
                              system_code=system_code, 
                              db_code=db_code, 
                              fallback_cost=fallback_cost)
                return fallback_cost
            
            logger.error("custo_nao_encontrado", system_code=system_code, db_code=db_code)
            return None
            
        except Exception as e:
            logger.error("erro_obter_custo", 
                        system_code=system_code, 
                        error=str(e), 
                        error_type=type(e).__name__)
            
            # Fallback em caso de erro
            fallback_cost = self._fallback_costs.get(system_code, 5)
            logger.warning("usando_fallback_por_erro", 
                          system_code=system_code, 
                          fallback_cost=fallback_cost)
            return fallback_cost
    
    async def get_type_by_code(self, system_code: str) -> Optional[Dict]:
        """
        Obtém informações completas de um tipo específico
        
        Args:
            system_code: Código usado no sistema
            
        Returns:
            Optional[Dict]: Dados completos do tipo ou None
        """
        try:
            db_code = self._map_system_code_to_db_code(system_code)
            types = await self.get_all_types()
            
            return types.get(db_code)
            
        except Exception as e:
            logger.error("erro_obter_tipo", 
                        system_code=system_code, 
                        error=str(e))
            return None
    
    async def refresh_cache(self) -> bool:
        """
        Força refresh do cache
        
        Returns:
            bool: True se refresh bem-sucedido
        """
        try:
            logger.info("forcando_refresh_cache")
            types = await self.get_all_types(force_refresh=True)
            return len(types) > 0
        except Exception as e:
            logger.error("erro_refresh_cache", error=str(e))
            return False
    
    def get_code_mapping(self) -> Dict[str, str]:
        """
        Retorna mapeamento completo de códigos
        
        Returns:
            Dict[str, str]: Mapeamento sistema -> banco
        """
        return self._code_mapping.copy()
    
    def get_fallback_costs(self) -> Dict[str, int]:
        """
        Retorna custos de fallback
        
        Returns:
            Dict[str, int]: Custos padrão em centavos
        """
        return self._fallback_costs.copy()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Verifica saúde do serviço
        
        Returns:
            Dict[str, Any]: Status de saúde
        """
        try:
            start_time = datetime.now()
            types = await self.get_all_types()
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                "status": "healthy" if types else "degraded",
                "types_count": len(types),
                "cache_valid": self._is_cache_valid(),
                "cache_timestamp": self._cache_timestamp.isoformat() if self._cache_timestamp else None,
                "response_time_ms": response_time,
                "supabase_connected": bool(self._get_supabase())
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "types_count": 0,
                "cache_valid": False
            }


# Instância global do serviço
consultation_types_service = ConsultationTypesService()

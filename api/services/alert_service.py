"""
Serviço de alertas críticos para monitoramento do sistema
"""
import structlog
from datetime import datetime, timedelta
from typing import Dict, Any
import os

logger = structlog.get_logger("alert_service")

class AlertService:
    def __init__(self):
        self.critical_alerts = {}
        
    async def send_critical_alert(self, alert_type: str, message: str, context: Dict[str, Any] = None):
        """
        Envia alerta crítico sobre problemas no sistema
        """
        alert_id = f"{alert_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        alert_data = {
            "id": alert_id,
            "type": alert_type,
            "message": message,
            "context": context or {},
            "timestamp": datetime.now().isoformat(),
            "severity": "CRITICAL",
            "resolved": False
        }
        
        # Log crítico estruturado
        logger.critical("sistema_alerta_critico",
                       alert_id=alert_id,
                       alert_type=alert_type,
                       message=message,
                       context=context)
        
        # Armazenar localmente para monitoramento
        self.critical_alerts[alert_id] = alert_data
        
        # Em produção, aqui você integraria com:
        # - Slack/Discord webhooks
        # - Email alerts
        # - SMS notifications
        # - Monitoring tools (Datadog, New Relic, etc.)
        
        # Por enquanto, criar arquivo de alerta crítico
        await self._write_alert_file(alert_data)
        
        return alert_id
    
    async def _write_alert_file(self, alert_data: Dict[str, Any]):
        """
        Escreve arquivo de alerta para monitoramento externo
        """
        try:
            alerts_dir = "logs/critical_alerts"
            os.makedirs(alerts_dir, exist_ok=True)
            
            alert_file = os.path.join(alerts_dir, f"alert_{alert_data['id']}.json")
            
            import json
            with open(alert_file, 'w', encoding='utf-8') as f:
                json.dump(alert_data, f, indent=2, ensure_ascii=False)
                
            logger.info("arquivo_alerta_criado", 
                       alert_id=alert_data['id'],
                       arquivo=alert_file)
                       
        except Exception as e:
            logger.error("erro_criar_arquivo_alerta", 
                        alert_id=alert_data['id'],
                        error=str(e))

# Instância global
alert_service = AlertService()

# Função utilitária para alertas da API oficial
async def alert_api_oficial_error(cnpj: str, error_message: str, context: Dict[str, Any] = None):
    """
    Alerta específico para erros da API oficial
    """
    await alert_service.send_critical_alert(
        alert_type="API_OFICIAL_ERROR",
        message=f"Erro crítico na API oficial para CNPJ {cnpj[:8]}****",
        context={
            "cnpj_mascarado": cnpj[:8] + "****",
            "error_message": error_message,
            "timestamp": datetime.now().isoformat(),
            **(context or {})
        }
    )

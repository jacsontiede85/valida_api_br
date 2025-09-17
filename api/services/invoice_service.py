"""
Serviço de gerenciamento de faturas
"""
import structlog
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from api.middleware.auth_middleware import get_supabase_client

logger = structlog.get_logger("invoice_service")

class InvoiceService:
    def __init__(self):
        self.supabase = get_supabase_client()
    
    async def get_user_invoices(
        self, 
        user_id: str, 
        page: int = 1, 
        limit: int = 10,
        status: str = "all",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Lista as faturas do usuário com filtros e paginação
        """
        try:
            if not self.supabase:
                # Sem Supabase configurado
                return {
                    "invoices": [],
                    "pagination": {
                        "page": page,
                        "limit": limit,
                        "total": 0,
                        "pages": 0
                    },
                    "message": "Sistema de faturas não configurado"
                }
            
            # Construir query com filtros
            query = self.supabase.table("invoices").select("*").eq("user_id", user_id)
            
            # Aplicar filtros
            if status != "all":
                query = query.eq("status", status)
            
            if date_from:
                query = query.gte("created_at", date_from)
            
            if date_to:
                query = query.lte("created_at", date_to)
            
            if search:
                query = query.ilike("invoice_number", f"%{search}%")
            
            # Aplicar paginação
            offset = (page - 1) * limit
            query = query.range(offset, offset + limit - 1).order("created_at", desc=True)
            
            response = query.execute()
            
            # Buscar total de registros para paginação
            count_query = self.supabase.table("invoices").select("id", count="exact").eq("user_id", user_id)
            if status != "all":
                count_query = count_query.eq("status", status)
            if date_from:
                count_query = count_query.gte("created_at", date_from)
            if date_to:
                count_query = count_query.lte("created_at", date_to)
            if search:
                count_query = count_query.ilike("invoice_number", f"%{search}%")
            
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
            logger.error("erro_buscar_faturas", user_id=user_id, error=str(e))
            raise e
    
    async def get_invoice(self, user_id: str, invoice_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém detalhes de uma fatura específica
        """
        try:
            if not self.supabase:
                # Retornar fatura mock
                return self._generate_mock_invoice(invoice_id)
            
            # Buscar fatura no Supabase
            response = self.supabase.table("invoices").select("*").eq("id", invoice_id).eq("user_id", user_id).execute()
            
            if response.data:
                return response.data[0]
            return None
            
        except Exception as e:
            logger.error("erro_buscar_fatura", user_id=user_id, invoice_id=invoice_id, error=str(e))
            raise e
    
    async def download_invoice(self, user_id: str, invoice_id: str) -> Dict[str, Any]:
        """
        Faz download de uma fatura em PDF
        """
        try:
            if not self.supabase:
                # Retornar dados mock para download
                return {
                    "filename": f"fatura_{invoice_id}.pdf",
                    "content_type": "application/pdf",
                    "data": "base64_encoded_pdf_data_mock",
                    "size": 1024
                }
            
            # Buscar fatura
            invoice = await self.get_invoice(user_id, invoice_id)
            if not invoice:
                raise Exception("Fatura não encontrada")
            
            # Aqui você implementaria a geração real do PDF
            # Por enquanto, retornar mock
            return {
                "filename": f"fatura_{invoice_id}.pdf",
                "content_type": "application/pdf",
                "data": "base64_encoded_pdf_data",
                "size": 1024
            }
            
        except Exception as e:
            logger.error("erro_download_fatura", user_id=user_id, invoice_id=invoice_id, error=str(e))
            raise e
    
    async def pay_invoice(self, user_id: str, invoice_id: str) -> Dict[str, Any]:
        """
        Processa o pagamento de uma fatura
        """
        try:
            if not self.supabase:
                # Mock para pagamento
                return {
                    "success": True,
                    "message": "Pagamento processado com sucesso",
                    "payment_id": f"pay_{invoice_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    "paid_at": datetime.now().isoformat()
                }
            
            # Implementar lógica de pagamento real
            # Por enquanto, retornar mock
            return {
                "success": True,
                "message": "Pagamento processado com sucesso",
                "payment_id": f"pay_{invoice_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "paid_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error("erro_pagar_fatura", user_id=user_id, invoice_id=invoice_id, error=str(e))
            raise e
    

# Instância global do serviço
invoice_service = InvoiceService()

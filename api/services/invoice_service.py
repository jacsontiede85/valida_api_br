"""
Serviço de gerenciamento de faturas
MIGRADO: Supabase → MariaDB
"""
import structlog
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from api.database.connection import execute_sql

logger = structlog.get_logger("invoice_service")

class InvoiceService:
    def __init__(self):
        # Migrado de Supabase para MariaDB - não precisa de cliente específico
        pass
    
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
        MIGRADO: MariaDB
        """
        try:
            # Construir condições WHERE
            where_conditions = ["user_id = %s"]
            params = [user_id]
            
            if status != "all":
                where_conditions.append("status = %s")
                params.append(status)
            
            if date_from:
                where_conditions.append("created_at >= %s")
                params.append(date_from)
            
            if date_to:
                where_conditions.append("created_at <= %s")
                params.append(date_to)
            
            if search:
                where_conditions.append("invoice_number LIKE %s")
                params.append(f"%{search}%")
            
            where_clause = " AND ".join(where_conditions)
            
            # Buscar total de registros para paginação
            count_sql = f"SELECT COUNT(*) as total FROM invoices WHERE {where_clause}"
            count_result = await execute_sql(count_sql, tuple(params))
            total = count_result["data"][0]["total"] if count_result["data"] else 0
            
            # Buscar faturas com paginação
            offset = (page - 1) * limit
            invoices_sql = f"""
                SELECT id, user_id, invoice_number, amount_cents, currency, status,
                       due_date, paid_at, stripe_invoice_id, description,
                       created_at, updated_at
                FROM invoices 
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            
            invoices_params = params + [limit, offset]
            invoices_result = await execute_sql(invoices_sql, tuple(invoices_params))
            
            # Converter para formato esperado
            invoices = []
            for invoice in invoices_result["data"]:
                invoices.append({
                    "id": invoice["id"],
                    "user_id": invoice["user_id"],
                    "invoice_number": invoice["invoice_number"],
                    "amount": invoice["amount_cents"] / 100,  # Converter para reais
                    "amount_cents": invoice["amount_cents"],
                    "currency": invoice["currency"],
                    "status": invoice["status"],
                    "due_date": invoice["due_date"].isoformat() if invoice["due_date"] else None,
                    "paid_at": invoice["paid_at"].isoformat() if invoice["paid_at"] else None,
                    "stripe_invoice_id": invoice["stripe_invoice_id"],
                    "description": invoice["description"],
                    "created_at": invoice["created_at"].isoformat() if invoice["created_at"] else None,
                    "updated_at": invoice["updated_at"].isoformat() if invoice["updated_at"] else None
                })
            
            return {
                "data": invoices,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit if total > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error("erro_buscar_faturas_mariadb", user_id=user_id, error=str(e))
            raise e
    
    async def get_invoice(self, user_id: str, invoice_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém detalhes de uma fatura específica
        MIGRADO: MariaDB
        """
        try:
            # Buscar fatura no MariaDB
            sql = """
                SELECT id, user_id, invoice_number, amount_cents, currency, status,
                       due_date, paid_at, stripe_invoice_id, description,
                       created_at, updated_at
                FROM invoices 
                WHERE id = %s AND user_id = %s
                LIMIT 1
            """
            
            result = await execute_sql(sql, (invoice_id, user_id))
            
            if result["error"] or not result["data"]:
                logger.info("fatura_nao_encontrada", user_id=user_id, invoice_id=invoice_id)
                return None
            
            invoice = result["data"][0]
            return {
                "id": invoice["id"],
                "user_id": invoice["user_id"],
                "invoice_number": invoice["invoice_number"],
                "amount": invoice["amount_cents"] / 100,  # Converter para reais
                "amount_cents": invoice["amount_cents"],
                "currency": invoice["currency"],
                "status": invoice["status"],
                "due_date": invoice["due_date"].isoformat() if invoice["due_date"] else None,
                "paid_at": invoice["paid_at"].isoformat() if invoice["paid_at"] else None,
                "stripe_invoice_id": invoice["stripe_invoice_id"],
                "description": invoice["description"],
                "created_at": invoice["created_at"].isoformat() if invoice["created_at"] else None,
                "updated_at": invoice["updated_at"].isoformat() if invoice["updated_at"] else None
            }
            
        except Exception as e:
            logger.error("erro_buscar_fatura_mariadb", user_id=user_id, invoice_id=invoice_id, error=str(e))
            raise e
    
    async def download_invoice(self, user_id: str, invoice_id: str) -> Dict[str, Any]:
        """
        Faz download de uma fatura em PDF
        MIGRADO: MariaDB - PDF generation TODO
        """
        try:
            # Buscar fatura no MariaDB
            invoice = await self.get_invoice(user_id, invoice_id)
            if not invoice:
                raise Exception("Fatura não encontrada")
            
            # TODO: Implementar geração real do PDF usando biblioteca como ReportLab
            # Por enquanto, retornar resposta com indicação de que fatura existe
            return {
                "filename": f"fatura_{invoice['invoice_number']}.pdf",
                "content_type": "application/pdf",
                "invoice_data": invoice,
                "download_url": f"/api/v1/invoices/{invoice_id}/download",
                "message": "Fatura encontrada - PDF generation precisa ser implementado"
            }
            
        except Exception as e:
            logger.error("erro_download_fatura_mariadb", user_id=user_id, invoice_id=invoice_id, error=str(e))
            raise e
    
    async def pay_invoice(self, user_id: str, invoice_id: str, payment_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Processa o pagamento de uma fatura
        MIGRADO: MariaDB - Stripe integration TODO
        """
        try:
            # Verificar se fatura existe e não foi paga
            invoice = await self.get_invoice(user_id, invoice_id)
            if not invoice:
                return {
                    "success": False,
                    "error": "Fatura não encontrada"
                }
            
            if invoice["status"] == "paid":
                return {
                    "success": False,
                    "error": "Fatura já foi paga",
                    "paid_at": invoice["paid_at"]
                }
            
            # TODO: Integrar com Stripe para processar pagamento real
            # Por enquanto, simular pagamento bem-sucedido
            payment_id = f"pay_{invoice_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            paid_at = datetime.now()
            
            # Atualizar status da fatura no MariaDB
            update_sql = """
                UPDATE invoices 
                SET status = 'paid',
                    paid_at = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
            """
            
            await execute_sql(update_sql, (paid_at, invoice_id, user_id))
            
            logger.info("fatura_paga", user_id=user_id, invoice_id=invoice_id, payment_id=payment_id)
            
            return {
                "success": True,
                "message": "Pagamento processado com sucesso",
                "payment_id": payment_id,
                "paid_at": paid_at.isoformat(),
                "invoice_id": invoice_id,
                "amount_paid": invoice["amount"]
            }
            
        except Exception as e:
            logger.error("erro_pagar_fatura_mariadb", user_id=user_id, invoice_id=invoice_id, error=str(e))
            raise e
    

# Instância global do serviço
invoice_service = InvoiceService()

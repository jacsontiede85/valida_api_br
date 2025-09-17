"""
Módulo para gerenciamento de dados de protesto no banco de dados Oracle.
Responsável pela inserção de dados de protestos nas tabelas ALA_CLIENTE_PROTESTOSC e ALA_CLIENTE_PROTESTOSI.
"""

import logging
from datetime import datetime
import pandas as pd
from typing import Dict, List, Union, Optional, Any, Tuple
import json
import os

from bd.oracle_casaaladim import OracleDatabase

# Configuração do logger
logger = logging.getLogger(__name__)
handler = logging.FileHandler('log/bd/protesto_manager.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class OracleProtestoManager:
    """
    Classe responsável por gerenciar a inserção de dados de protestos no banco de dados Oracle.
    Utiliza a classe OracleDatabase para realizar as operações de banco de dados.
    """
    
    def __init__(self):
        """Inicializa o gerenciador de protestos com uma instância do OracleDatabase."""
        self.db = OracleDatabase()
        self.codcli_cache = {}  # Cache para armazenar CODCLI por CNPJ
        self.cartorio_ids = {}  # Cache para armazenar IDs de cartórios
        
    def _sanitize_string(self, value: str) -> str:
        """
        Sanitiza uma string para uso em consultas SQL.
        Remove aspas simples e outros caracteres problemáticos.
        Também trunca strings que excedem o tamanho máximo permitido para evitar erros ORA-12899.
        
        Args:
            value: String a ser sanitizada
            
        Returns:
            String sanitizada
        """
        if value is None:
            return ""
        return str(value).replace("'", "''")
    
    def _truncate_string(self, value: str, max_length: int) -> str:
        """
        Trunca uma string se ela exceder o tamanho máximo especificado.
        Registra um aviso caso a string precise ser truncada.
        
        Args:
            value: String a ser truncada
            max_length: Tamanho máximo permitido
            
        Returns:
            String truncada para o tamanho máximo especificado
        """
        if value is None:
            return ""
            
        value_str = str(value)
        if len(value_str) > max_length:
            truncated = value_str[:max_length]
            logger.warning(f"Valor truncado de {len(value_str)} para {max_length} caracteres: '{value_str[:10]}...'")
            return truncated
        
        return value_str
    
    def obter_codcli(self, cnpj: str) -> Optional[int]:
        """
        Obtém o código do cliente (CODCLI) a partir do CNPJ.
        Utiliza cache para evitar consultas repetidas.
        
        Args:
            cnpj: CNPJ do cliente (apenas números)
            
        Returns:
            Código do cliente ou None se não encontrado
        """
        # Verifica se já está no cache
        if cnpj in self.codcli_cache:
            logger.debug(f"CODCLI para CNPJ {cnpj} obtido do cache: {self.codcli_cache[cnpj]}")
            return self.codcli_cache[cnpj]
        
        try:
            # Consulta no banco de dados
            sql = f"""
                select
                    nvl(
                        (SELECT codcli FROM pcclient WHERE cnpj_formatted(pcclient.cgcent) = '{cnpj}'),
                        (SELECT codcli FROM pcclientfv WHERE cnpj_formatted(pcclientfv.cgcent) = '{cnpj}')
                    ) as codcli
                from dual
            """
            logger.debug(f"Executando consulta: {sql}")
            result = self.db.select(sql)
            
            if not result.empty:
                codcli = int(result.iloc[0]['codcli'])
                # Armazena no cache
                self.codcli_cache[cnpj] = codcli
                logger.info(f"CODCLI para CNPJ {cnpj} encontrado: {codcli}")
                return codcli
            
            logger.warning(f"CODCLI para CNPJ {cnpj} não encontrado na tabela PCCLIENT")
            return None
        except Exception as e:
            logger.error(f"Erro ao obter CODCLI para CNPJ {cnpj}: {str(e)}")
            return None
    
    def gerar_idcart(self, cartorio: str, uf: str, cidade: str) -> int:
        """
        Gera um identificador único para um cartório.
        Se já existir um ID para o cartório, retorna o existente.
        Caso contrário, consulta o próximo ID disponível no banco.
        
        Args:
            cartorio: Nome do cartório
            uf: UF do cartório
            cidade: Cidade do cartório
            
        Returns:
            ID único do cartório
        """
        # Cria uma chave composta para identificar o cartório
        chave = f"{cartorio}|{uf}|{cidade}".upper()
        
        # Verifica se já temos um ID para este cartório no cache
        if chave in self.cartorio_ids:
            return self.cartorio_ids[chave]
        
        try:
            # Verifica se já existe no banco
            cartorio_safe = self._sanitize_string(cartorio)
            uf_safe = self._sanitize_string(uf)
            cidade_safe = self._sanitize_string(cidade)
            
            sql = f"""
                SELECT MAX(IDCART) as max_id 
                FROM ALA_CLIENTE_PROTESTOSC 
                WHERE UPPER(CARTORIO) = UPPER('{cartorio_safe}')
                AND UPPER(UF) = UPPER('{uf_safe}')
                AND UPPER(CIDADE) = UPPER('{cidade_safe}')
            """
            result = self.db.select(sql)
            
            if not result.empty and result.iloc[0]['max_id'] is not None:
                idcart = int(result.iloc[0]['max_id'])
                self.cartorio_ids[chave] = idcart
                return idcart
            
            # Se não existe, obtém o próximo ID
            sql = "SELECT NVL(MAX(IDCART), 0) + 1 as next_id FROM ALA_CLIENTE_PROTESTOSC"
            result = self.db.select(sql)
            
            if not result.empty:
                idcart = int(result.iloc[0]['next_id'])
                self.cartorio_ids[chave] = idcart
                logger.info(f"Novo IDCART gerado para {cartorio}|{uf}|{cidade}: {idcart}")
                return idcart
            
            # Fallback caso ocorra algum erro
            logger.warning(f"Não foi possível obter próximo IDCART. Utilizando valor padrão 1.")
            return 1
        except Exception as e:
            logger.error(f"Erro ao gerar IDCART para {cartorio}|{uf}|{cidade}: {str(e)}")
            # Fallback caso ocorra algum erro
            return 1
    
    def excluir_registros_anteriores(self, cnpj: str) -> None:
        """
        Exclui registros anteriores para um determinado CNPJ.
        Isso garante que apenas a consulta mais recente seja mantida.
        
        Args:
            cnpj: CNPJ do cliente
        """
        try:
            # Exclui registros da tabela de itens diretamente pelo CNPJ
            sql_delete_items = f"""
                DELETE FROM ALA_CLIENTE_PROTESTOSI WHERE CNPJ = '{cnpj}'
            """
            rowcount = self.db.update(sql_delete_items)
            logger.info(f"Excluídos {rowcount} registros de itens para CNPJ {cnpj}")
            
            # Exclui os registros da tabela de cabeçalho
            sql_delete_header = f"""
                DELETE FROM ALA_CLIENTE_PROTESTOSC WHERE CNPJ = '{cnpj}'
            """
            rowcount = self.db.update(sql_delete_header)
            logger.info(f"Excluídos {rowcount} registros de cabeçalho para CNPJ {cnpj}")
            
        except Exception as e:
            logger.error(f"Erro ao excluir registros anteriores para CNPJ {cnpj}: {str(e)}")
    
    def inserir_protesto_cabecalho(self, dados: Dict[str, Any], idcart: int) -> bool:
        """
        Insere ou atualiza dados na tabela ALA_CLIENTE_PROTESTOSC.
        
        Args:
            dados: Dicionário com os dados do cabeçalho
            idcart: ID único do cartório
            
        Returns:
            True se a operação foi bem-sucedida, False caso contrário
        """
        try:
            codcli = self.obter_codcli(dados['cnpj'])
            if not codcli:
                logger.warning(f"Não foi possível obter CODCLI para CNPJ {dados['cnpj']}. Utilizando NULL.")
                codcli_value = "NULL"
            else:
                codcli_value = str(codcli)
            
            # Aplica truncamento nos campos de texto para evitar erros ORA-12899
            cartorio = self._sanitize_string(self._truncate_string(dados.get('cartorio', ''), 255))
            obterdetalhes = self._sanitize_string(self._truncate_string(dados.get('obterDetalhes', ''), 255))
            cidade = self._sanitize_string(self._truncate_string(dados.get('cidade', ''), 255))
            uf = self._sanitize_string(self._truncate_string(dados.get('uf', ''), 2))
            qtd_titulos = dados.get('quantidadeTitulos', 0)
            endereco = self._sanitize_string(self._truncate_string(dados.get('endereco', ''), 255))
            telefone = self._sanitize_string(self._truncate_string(dados.get('telefone', ''), 20))
            
            # Data de consulta (data atual)
            data_consulta = datetime.now().strftime("%Y-%m-%d")
            
            # Insere novo registro (sem verificar existência, pois já foi feito delete)
            sql = f"""
                INSERT INTO ALA_CLIENTE_PROTESTOSC 
                (CODCLI, CNPJ, CARTORIO, OBTERDETALHES, CIDADE, UF, 
                QUANTIDADETITULOS, ENDERECO, TELEFONE, DATACONSULTA, IDCART)
                VALUES
                ({codcli_value}, '{dados['cnpj']}', '{cartorio}', '{obterdetalhes}', 
                '{cidade}', '{uf}', {qtd_titulos}, '{endereco}', '{telefone}', 
                TO_DATE('{data_consulta}', 'YYYY-MM-DD'), {idcart})
            """
            logger.debug(f"Inserindo cabeçalho para CNPJ {dados['cnpj']} e IDCART {idcart}")
            
            rowcount = self.db.update(sql)
            logger.info(f"Cabeçalho para CNPJ {dados['cnpj']} e IDCART {idcart} inserido. Linhas afetadas: {rowcount}")
            return rowcount > 0
        except Exception as e:
            logger.error(f"Erro ao inserir cabeçalho para CNPJ {dados['cnpj']}: {str(e)}")
            return False
    
    def inserir_protesto_item(self, dados: Dict[str, Any], idcart: int) -> bool:
        """
        Insere dados de um item de protesto na tabela ALA_CLIENTE_PROTESTOSI.
        Aplica SUBSTR para evitar erros ORA-12899.
        
        Args:
            dados: Dicionário com os dados do item
            idcart: ID único do cartório
            
        Returns:
            True se a operação foi bem-sucedida, False caso contrário
        """
        try:
            codcli = self.obter_codcli(dados['cpfCnpj'])
            if not codcli:
                logger.warning(f"Não foi possível obter CODCLI para CNPJ {dados['cpfCnpj']}. Utilizando NULL.")
                codcli_value = "NULL"
            else:
                codcli_value = str(codcli)
            
            # Tratamento das datas - campo DATA sempre usa data atual da inserção
            data = "TRUNC(SYSDATE)"
            
            data_protesto = "NULL"
            if dados.get('dataProtesto'):
                data_protesto = f"TO_DATE('{dados['dataProtesto']}', 'YYYY-MM-DD')"
            
            data_vencimento = "NULL"
            if dados.get('dataVencimento'):
                data_vencimento = f"TO_DATE('{dados['dataVencimento']}', 'YYYY-MM-DD')"
            
            # Tratamento do valor - melhorado para garantir conversão correta
            valor = 0
            valor_str = dados.get('valor', '0')
            if valor_str:
                # Tratamento aprimorado para valores monetários
                try:
                    if isinstance(valor_str, str):
                        # Remove todos os caracteres não numéricos exceto vírgula e ponto
                        valor_limpo = ''.join(c for c in valor_str if c.isdigit() or c in ['.', ','])
                        
                        # Tratamento para formato brasileiro (ex: "1.234,56" ou "1234,56")
                        if ',' in valor_limpo:
                            # Verifica se há ponto antes da vírgula (separador de milhar)
                            if '.' in valor_limpo and valor_limpo.rindex('.') < valor_limpo.index(','):
                                # Formato com separador de milhar: 1.234,56
                                valor_limpo = valor_limpo.replace('.', '')
                            
                            # Converte vírgula para ponto para processamento
                            valor_limpo = valor_limpo.replace(',', '.')
                        
                        valor = float(valor_limpo)
                        logger.info(f"Valor convertido com sucesso: {valor_str} -> {valor}")
                    else:
                        # Se já for um número
                        valor = float(valor_str)
                except (ValueError, TypeError) as e:
                    logger.error(f"Erro ao converter valor '{valor_str}' para float: {str(e)}. Usando valor original para debug.")
                    # Tenta extrair apenas os dígitos e a vírgula/ponto decimal
                    try:
                        import re
                        # Extrai padrão de número com vírgula ou ponto decimal
                        match = re.search(r'(\d+[.,]\d+|\d+)', str(valor_str))
                        if match:
                            valor_extraido = match.group(0).replace(',', '.')
                            valor = float(valor_extraido)
                            logger.info(f"Valor extraído com regex: {valor_str} -> {valor}")
                        else:
                            valor = 0
                            logger.warning(f"Não foi possível extrair valor numérico de '{valor_str}'. Utilizando 0.")
                    except Exception as ex:
                        valor = 0
                        logger.warning(f"Falha na extração com regex para '{valor_str}': {str(ex)}. Utilizando 0.")
            
            # Flags de autorização e custas de cancelamento
            aut_cancel = 'N'
            if dados.get('autorizacaoCancelamento', False):
                aut_cancel = 'S'
            
            # Tratamento melhorado para custas de cancelamento (similar ao valor)
            custas_cancel = 0
            custas_cancel_str = dados.get('custasCancelamento', '0')
            if custas_cancel_str:
                try:
                    if isinstance(custas_cancel_str, str):
                        # Remove caracteres não numéricos (exceto ponto e vírgula)
                        custas_limpo = ''.join(c for c in custas_cancel_str if c.isdigit() or c in ['.', ','])
                        
                        # Tratamento para formato brasileiro
                        if ',' in custas_limpo:
                            if '.' in custas_limpo and custas_limpo.rindex('.') < custas_limpo.index(','):
                                custas_limpo = custas_limpo.replace('.', '')
                            
                            custas_limpo = custas_limpo.replace(',', '.')
                        
                        custas_cancel = float(custas_limpo)
                    else:
                        custas_cancel = float(custas_cancel_str)
                except (ValueError, TypeError):
                    custas_cancel = 0
                    logger.warning(f"Não foi possível converter custas '{custas_cancel_str}' para float. Utilizando 0.")
            
            # Aplicando truncamento do CNPJ para evitar erro ORA-12899
            cnpj = self._truncate_string(dados['cpfCnpj'], 14)
            
            # SQL para inserção com proteção SUBSTR
            sql = f"""
                INSERT INTO ALA_CLIENTE_PROTESTOSI
                (CODCLI, CNPJ, DATA, DATAPROTESTO, DATAVENCIMENTO, VALOR, IDCART, AUT_CANCEL, CUSTAS_CANCEL)
                VALUES
                ({codcli_value}, '{cnpj}', {data}, {data_protesto}, {data_vencimento}, 
                {valor}, {idcart}, '{aut_cancel}', {custas_cancel})
            """
            
            rowcount = self.db.update(sql)
            logger.info(f"Item para CNPJ {dados['cpfCnpj']} e IDCART {idcart} inserido. Valor: {valor}. Linhas afetadas: {rowcount}")
            return rowcount > 0
        except Exception as e:
            logger.error(f"Erro ao inserir item para CNPJ {dados.get('cpfCnpj', 'N/A')}: {str(e)}")
            return False
    
    def registrar_consulta_sem_protestos(self, cnpj: str) -> bool:
        """
        Registra uma consulta sem protestos na tabela ALA_CLIENTE_PROTESTOSC.
        Aplica SUBSTR para evitar erros ORA-12899.
        
        Args:
            cnpj: CNPJ consultado
            
        Returns:
            True se a operação foi bem-sucedida, False caso contrário
        """
        try:
            # Exclui registros anteriores para este CNPJ
            self.excluir_registros_anteriores(cnpj)
            
            codcli = self.obter_codcli(cnpj)
            if not codcli:
                logger.warning(f"Não foi possível obter CODCLI para CNPJ {cnpj}. Utilizando NULL.")
                codcli_value = "NULL"
            else:
                codcli_value = str(codcli)
            
            # Data de consulta (data atual)
            data_consulta = datetime.now().strftime("%Y-%m-%d")
            
            # Insere novo registro com SUBSTR nos campos de texto
            sql = f"""
                INSERT INTO ALA_CLIENTE_PROTESTOSC 
                (CODCLI, CNPJ, CARTORIO, OBTERDETALHES, CIDADE, UF, 
                QUANTIDADETITULOS, ENDERECO, TELEFONE, DATACONSULTA, IDCART)
                VALUES
                ({codcli_value}, '{cnpj}', SUBSTR('Nenhum protesto encontrado', 1, 255), NULL, 
                NULL, NULL, 0, NULL, NULL, 
                TO_DATE('{data_consulta}', 'YYYY-MM-DD'), 0)
            """
            
            rowcount = self.db.update(sql)
            logger.info(f"Consulta sem protestos para CNPJ {cnpj} registrada. Linhas afetadas: {rowcount}")
            return rowcount > 0
        except Exception as e:
            logger.error(f"Erro ao registrar consulta sem protestos para CNPJ {cnpj}: {str(e)}")
            return False
    
    def inserir_protesto_completo(self, dados: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Insere dados de protesto completo (cabeçalho e itens) em uma única transação,
        utilizando um bloco PL/SQL anônimo para garantir atomicidade.
        
        Args:
            dados: Dicionário com os dados do protesto obtidos da API CENPROT
            
        Returns:
            Tupla com: (sucesso, mensagem) onde sucesso é um booleano e mensagem é uma string
        """
        try:
            cnpj = dados.get('cnpj')
            if not cnpj:
                logger.error("CNPJ não encontrado no resultado da consulta")
                return False, "CNPJ não encontrado nos dados fornecidos"
            
            # Obter o CODCLI para o CNPJ (e armazenar em cache)
            codcli = self.obter_codcli(cnpj)
            if not codcli:
                logger.warning(f"Não foi possível obter CODCLI para CNPJ {cnpj}. Utilizando NULL.")
                codcli = None
            
            cenprotProtestos = dados.get('cenprotProtestos', {})
            
            # Verifica se é uma resposta sem protestos
            if 'code' in cenprotProtestos and 'message' in cenprotProtestos:
                code = cenprotProtestos.get('code')
                message = cenprotProtestos.get('message')
                
                if code == 606 and "Não encontrado protestos" in message:
                    # Para casos sem protestos, usamos um bloco PL/SQL simples
                    return self._inserir_sem_protestos_pl_sql(cnpj, codcli)
                else:
                    logger.warning(f"Código de resposta não reconhecido: {code} - {message}")
                    return self._inserir_sem_protestos_pl_sql(cnpj, codcli)
            
            # Lista para armazenar todos os itens de protestos de todos os cartórios
            todos_protestos = []
            cartorio_data_list = []
            
            # Processa os protestos por UF
            for uf, protestos_uf in cenprotProtestos.items():
                for protesto_info in protestos_uf:
                    # Extrai dados do cartório
                    cartorio = protesto_info.get('cartorio', '')
                    cidade = protesto_info.get('cidade', '')
                    
                    # Gera ID do cartório
                    idcart = self.gerar_idcart(
                        cartorio, 
                        uf, 
                        cidade
                    )
                    
                    # Dados do cartório para inserção
                    cartorio_data = {
                        'cnpj': cnpj,
                        'codcli': codcli,
                        'cartorio': self._sanitize_string(cartorio),
                        'obterDetalhes': self._sanitize_string(protesto_info.get('obterDetalhes', '')),
                        'cidade': self._sanitize_string(cidade),
                        'uf': self._sanitize_string(uf),
                        'quantidadeTitulos': protesto_info.get('quantidadeTitulos', 0),
                        'endereco': self._sanitize_string(protesto_info.get('endereco', '')),
                        'telefone': self._sanitize_string(protesto_info.get('telefone', '')),
                        'idcart': idcart
                    }
                    cartorio_data_list.append(cartorio_data)
                    
                    # Processa itens de protesto para este cartório
                    protestos_list = protesto_info.get('protestos', [])
                    for protesto in protestos_list:
                        # Tratamento das datas
                        data = protesto.get('data')
                        data_protesto = protesto.get('dataProtesto')
                        data_vencimento = protesto.get('dataVencimento')
                        
                        # Tratamento do valor
                        valor_str = protesto.get('valor', '0')
                        valor = self._converter_valor_monetario(valor_str)
                        
                        # Flags de autorização e custas de cancelamento
                        aut_cancel = 'S' if protesto.get('autorizacaoCancelamento', False) else 'N'
                        custas_cancel_str = protesto.get('custasCancelamento', '0')
                        custas_cancel = self._converter_valor_monetario(custas_cancel_str)
                        
                        # Dados do item para inserção
                        item_data = {
                            'cnpj': cnpj,
                            'codcli': codcli,
                            'dataProtesto': data_protesto,
                            'dataVencimento': data_vencimento,
                            'valor': valor,
                            'idcart': idcart,
                            'aut_cancel': aut_cancel,
                            'custas_cancel': custas_cancel
                        }
                        todos_protestos.append(item_data)
            
            # Verifica se há dados para processar
            if not cartorio_data_list or not todos_protestos:
                logger.info(f"Não foram encontrados protestos para CNPJ {cnpj}. Registrando consulta sem protestos.")
                return self._inserir_sem_protestos_pl_sql(cnpj, codcli)
            
            # Agora vamos construir o bloco PL/SQL para inserir tudo de uma vez
            return self._executar_bloco_pl_sql_protesto(cnpj, cartorio_data_list, todos_protestos)
        
        except Exception as e:
            logger.error(f"Erro ao processar resultado da consulta: {str(e)}")
            return False, f"Erro ao processar protestos: {str(e)}"
    
    def _converter_valor_monetario(self, valor_str: Union[str, float, int]) -> float:
        """
        Método auxiliar para converter valores monetários em vários formatos para float.
        
        Args:
            valor_str: Valor em formato string ou numérico
            
        Returns:
            Valor convertido para float
        """
        valor = 0.0
        
        if not valor_str:
            return valor
            
        try:
            if isinstance(valor_str, (int, float)):
                return float(valor_str)
                
            if isinstance(valor_str, str):
                # Remove todos os caracteres não numéricos exceto vírgula e ponto
                valor_limpo = ''.join(c for c in valor_str if c.isdigit() or c in ['.', ','])
                
                # Tratamento para formato brasileiro (ex: "1.234,56" ou "1234,56")
                if ',' in valor_limpo:
                    # Verifica se há ponto antes da vírgula (separador de milhar)
                    if '.' in valor_limpo and valor_limpo.rindex('.') < valor_limpo.index(','):
                        # Formato com separador de milhar: 1.234,56
                        valor_limpo = valor_limpo.replace('.', '')
                    
                    # Converte vírgula para ponto para processamento
                    valor_limpo = valor_limpo.replace(',', '.')
                
                valor = float(valor_limpo)
                return valor
        except Exception as e:
            logger.warning(f"Erro ao converter valor '{valor_str}': {str(e)}")
            
            # Tenta extrair apenas os dígitos e a vírgula/ponto decimal
            try:
                import re
                # Extrai padrão de número com vírgula ou ponto decimal
                match = re.search(r'(\d+[.,]\d+|\d+)', str(valor_str))
                if match:
                    valor_extraido = match.group(0).replace(',', '.')
                    return float(valor_extraido)
            except Exception:
                pass
                
        return valor
    
    def _inserir_sem_protestos_pl_sql(self, cnpj: str, codcli: Optional[int]) -> Tuple[bool, str]:
        """
        Insere registro de consulta sem protestos utilizando bloco PL/SQL anônimo.
        Aplica proteção SUBSTR para evitar erros de ORA-12899.
        
        Args:
            cnpj: CNPJ consultado
            codcli: Código do cliente (pode ser None para inserir NULL)
            
        Returns:
            Tupla com: (sucesso, mensagem) onde sucesso é um booleano e mensagem é uma string
        """
        # Data de consulta (data atual)
        data_consulta = datetime.now().strftime("%Y-%m-%d")
        
        # Bloco PL/SQL para consulta sem protestos
        bloco_pl_sql = """
        BEGIN
            -- Exclui registros anteriores
            DELETE FROM ALA_CLIENTE_PROTESTOSI WHERE CNPJ = :cnpj;
            DELETE FROM ALA_CLIENTE_PROTESTOSC WHERE CNPJ = :cnpj;
            
            -- Insere cabeçalho indicando que não há protestos
            INSERT INTO ALA_CLIENTE_PROTESTOSC 
            (CODCLI, CNPJ, CARTORIO, OBTERDETALHES, CIDADE, UF, 
            QUANTIDADETITULOS, ENDERECO, TELEFONE, DATACONSULTA, IDCART)
            VALUES
            (:codcli, :cnpj, SUBSTR('Nenhum protesto encontrado', 1, 255), NULL, 
            NULL, NULL, 0, NULL, NULL, 
            TO_DATE(:data_consulta, 'YYYY-MM-DD'), 0);
            
            COMMIT;
        EXCEPTION
            WHEN OTHERS THEN
                ROLLBACK;
                RAISE;
        END;
        """
        
        # Parâmetros para o bloco PL/SQL - None será automaticamente convertido para NULL
        parametros = {
            'cnpj': cnpj,
            'codcli': codcli,  # None será tratado como NULL pelo Oracle
            'data_consulta': data_consulta
        }
        
        # Executar o bloco PL/SQL
        try:
            logger.info(f"Executando bloco PL/SQL para registrar consulta sem protestos para CNPJ {cnpj}")
            result = self.db.executar_bloco_pl_sql(bloco_pl_sql, parametros)
            
            if result['success']:
                logger.info(f"Consulta sem protestos para CNPJ {cnpj} registrada com sucesso.")
                return True, "Consulta sem protestos registrada com sucesso"
            else:
                logger.error(f"Erro ao registrar consulta sem protestos: {result['message']}")
                return False, f"Erro ao registrar consulta sem protestos: {result['message']}"
        except Exception as e:
            logger.error(f"Exceção ao executar bloco PL/SQL para CNPJ {cnpj}: {str(e)}")
            return False, f"Erro ao registrar consulta: {str(e)}"
    
    def _executar_bloco_pl_sql_protesto(self, cnpj: str, cartorios: List[Dict[str, Any]], 
                                        itens: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Executa um bloco PL/SQL para inserir todos os dados de protesto de uma só vez.
        Aplica truncamento em todos os campos de texto para evitar erros ORA-12899.
        
        Args:
            cnpj: CNPJ do cliente
            cartorios: Lista de dicionários com dados dos cartórios
            itens: Lista de dicionários com dados dos itens de protesto
            
        Returns:
            Tupla com: (sucesso, mensagem) onde sucesso é um booleano e mensagem é uma string
        """
        try:
            if not cartorios or not itens:
                logger.warning(f"Sem dados para processar para CNPJ {cnpj}")
                return False, "Sem dados para processar"
            
            # Data de consulta (data atual)
            data_consulta = datetime.now().strftime("%Y-%m-%d")
            
            # Criamos listas para armazenar os dados que serão usados no PL/SQL
            cartorio_lista = []
            item_lista = []
            
            # Preparamos os dados dos cartórios com truncamento para evitar ORA-12899
            for cartorio in cartorios:
                cartorio_lista.append({
                    'codcli': cartorio['codcli'],  # Pode ser None e será tratado como NULL
                    'cartorio': self._truncate_string(cartorio['cartorio'], 255),
                    'obterdetalhes': self._truncate_string(cartorio['obterDetalhes'], 255),
                    'cidade': self._truncate_string(cartorio['cidade'], 255),
                    'uf': self._truncate_string(cartorio['uf'], 2),
                    'qtd_titulos': cartorio['quantidadeTitulos'],
                    'endereco': self._truncate_string(cartorio['endereco'], 255),
                    'telefone': self._truncate_string(cartorio['telefone'], 20),
                    'idcart': cartorio['idcart']
                })
            
            # Preparamos os dados dos itens
            for item in itens:
                item_lista.append({
                    'codcli': item['codcli'],  # Pode ser None e será tratado como NULL
                    'dataprotesto': item['dataProtesto'] or None,
                    'datavencimento': item['dataVencimento'] or None,
                    'valor': item['valor'],
                    'idcart': item['idcart'],
                    'aut_cancel': item['aut_cancel'],
                    'custas_cancel': item['custas_cancel']
                })
            
            # Construímos o bloco PL/SQL
            bloco_pl_sql = self._construir_bloco_pl_sql_protesto(len(cartorio_lista), len(item_lista))
            
            # Preparamos os parâmetros para o bloco PL/SQL
            parametros = {
                'cnpj': cnpj,
                'data_consulta': data_consulta
            }
            
            # Adicionamos os parâmetros dos cartórios
            for i, cartorio in enumerate(cartorio_lista):
                for key, value in cartorio.items():
                    parametros[f'c_{key}_{i}'] = value
            
            # Adicionamos os parâmetros dos itens
            for i, item in enumerate(item_lista):
                for key, value in item.items():
                    parametros[f'i_{key}_{i}'] = value
            
            # Executamos o bloco PL/SQL
            logger.info(f"Executando bloco PL/SQL para CNPJ {cnpj} com {len(cartorio_lista)} cartórios e {len(item_lista)} itens")
            result = self.db.executar_bloco_pl_sql(bloco_pl_sql, parametros)
            
            if result['success']:
                logger.info(f"Dados de protesto para CNPJ {cnpj} inseridos com sucesso")
                return True, "Dados de protesto inseridos com sucesso"
            else:
                logger.error(f"Erro ao inserir dados de protesto: {result['message']}")
                return False, f"Erro ao inserir dados de protesto: {result['message']}"
                
        except Exception as e:
            logger.error(f"Exceção ao executar bloco PL/SQL para CNPJ {cnpj}: {str(e)}")
            return False, f"Erro ao inserir dados de protesto: {str(e)}"
    
    def _construir_bloco_pl_sql_protesto(self, num_cartorios: int, num_itens: int) -> str:
        """
        Constrói dinamicamente o bloco PL/SQL para inserção de dados de protesto.
        Inclui proteções SUBSTR para evitar erros ORA-12899 em todas as inserções.
        
        Args:
            num_cartorios: Número de cartórios a serem inseridos
            num_itens: Número de itens a serem inseridos
            
        Returns:
            String contendo o bloco PL/SQL
        """
        bloco = """
        BEGIN
            -- Exclui registros anteriores
            DELETE FROM ALA_CLIENTE_PROTESTOSI WHERE CNPJ = :cnpj;
            DELETE FROM ALA_CLIENTE_PROTESTOSC WHERE CNPJ = :cnpj;
            
            -- Insere cabeçalhos dos cartórios
        """
        
        # Adiciona inserções de cabeçalho para cada cartório com proteção SUBSTR
        for i in range(num_cartorios):
            bloco += f"""
            INSERT INTO ALA_CLIENTE_PROTESTOSC 
            (CODCLI, CNPJ, CARTORIO, OBTERDETALHES, CIDADE, UF, 
            QUANTIDADETITULOS, ENDERECO, TELEFONE, DATACONSULTA, IDCART)
            VALUES
            (:c_codcli_{i}, :cnpj, SUBSTR(:c_cartorio_{i}, 1, 255), SUBSTR(:c_obterdetalhes_{i}, 1, 255), 
            SUBSTR(:c_cidade_{i}, 1, 255), SUBSTR(:c_uf_{i}, 1, 2), :c_qtd_titulos_{i}, SUBSTR(:c_endereco_{i}, 1, 255), SUBSTR(:c_telefone_{i}, 1, 20), 
            TO_DATE(:data_consulta, 'YYYY-MM-DD'), :c_idcart_{i});
            """
        
        # Adiciona inserções de itens
        for i in range(num_itens):
            data_protesto_clause = f"TO_DATE(:i_dataprotesto_{i}, 'YYYY-MM-DD')" if f":i_dataprotesto_{i}" != "None" else "NULL"
            data_vencimento_clause = f"TO_DATE(:i_datavencimento_{i}, 'YYYY-MM-DD')" if f":i_datavencimento_{i}" != "None" else "NULL"
            
            bloco += f"""
            INSERT INTO ALA_CLIENTE_PROTESTOSI
            (CODCLI, CNPJ, DATA, DATAPROTESTO, DATAVENCIMENTO, VALOR, IDCART, AUT_CANCEL, CUSTAS_CANCEL)
            VALUES
            (:i_codcli_{i}, :cnpj, 
            TRUNC(SYSDATE),
            CASE 
                WHEN :i_dataprotesto_{i} IS NOT NULL THEN TO_DATE(:i_dataprotesto_{i}, 'YYYY-MM-DD')
                ELSE NULL
            END,
            CASE 
                WHEN :i_datavencimento_{i} IS NOT NULL THEN TO_DATE(:i_datavencimento_{i}, 'YYYY-MM-DD')
                ELSE NULL
            END,
            :i_valor_{i}, :i_idcart_{i}, :i_aut_cancel_{i}, :i_custas_cancel_{i});
            """
        
        # Finaliza o bloco
        bloco += """
            COMMIT;
        EXCEPTION
            WHEN OTHERS THEN
                ROLLBACK;
                RAISE;
        END;
        """
        
        return bloco
    
    def processar_resultado_consulta(self, resultado_json: Dict[str, Any]) -> bool:
        """
        Processa o resultado de uma consulta ao CENPROT e insere os dados no banco.
        
        Args:
            resultado_json: Resultado da consulta em formato JSON
            
        Returns:
            True se o processamento foi bem-sucedido, False caso contrário
        """
        try:
            # Implementação usando o novo método de inserção atômica
            success, message = self.inserir_protesto_completo(resultado_json)
            if not success:
                logger.error(f"Falha na inserção atômica de protestos: {message}")
                
                # Fallback para método antigo em caso de falha
                logger.warning("Tentando inserção pelo método tradicional como fallback")
                
                # Código original de inserção aqui (mantido para compatibilidade)
                cnpj = resultado_json.get('cnpj')
                if not cnpj:
                    logger.error("CNPJ não encontrado no resultado da consulta")
                    return False
                
                # Exclui registros anteriores para este CNPJ
                self.excluir_registros_anteriores(cnpj)
                
                cenprotProtestos = resultado_json.get('cenprotProtestos', {})
                
                # Verifica se é uma resposta sem protestos
                if 'code' in cenprotProtestos and 'message' in cenprotProtestos:
                    code = cenprotProtestos.get('code')
                    message = cenprotProtestos.get('message')
                    
                    if code == 606 and "Não encontrado protestos" in message:
                        return self.registrar_consulta_sem_protestos(cnpj)
                    else:
                        logger.warning(f"Código de resposta não reconhecido: {code} - {message}")
                        return self.registrar_consulta_sem_protestos(cnpj)
                
                # Processa os protestos por UF
                success = True
                for uf, protestos_uf in cenprotProtestos.items():
                    for protesto_info in protestos_uf:
                        # Extrai dados do cartório
                        cartorio_data = {
                            'cnpj': cnpj,
                            'cartorio': protesto_info.get('cartorio', ''),
                            'obterDetalhes': protesto_info.get('obterDetalhes', ''),
                            'cidade': protesto_info.get('cidade', ''),
                            'uf': uf,  # UF vem da chave do dicionário
                            'quantidadeTitulos': protesto_info.get('quantidadeTitulos', 0),
                            'endereco': protesto_info.get('endereco', ''),
                            'telefone': protesto_info.get('telefone', '')
                        }
                        
                        # Gera ID do cartório
                        idcart = self.gerar_idcart(
                            cartorio_data['cartorio'], 
                            cartorio_data['uf'], 
                            cartorio_data['cidade']
                        )
                        
                        # Insere cabeçalho
                        if not self.inserir_protesto_cabecalho(cartorio_data, idcart):
                            logger.error(f"Falha ao inserir cabeçalho para CNPJ {cnpj} e cartório {cartorio_data['cartorio']}")
                            success = False
                        
                        # Insere itens (protestos)
                        protestos_list = protesto_info.get('protestos', [])
                        for protesto in protestos_list:
                            if not self.inserir_protesto_item(protesto, idcart):
                                logger.error(f"Falha ao inserir item de protesto para CNPJ {cnpj} e cartório {cartorio_data['cartorio']}")
                                success = False
                
                return success
            
            return success
        except Exception as e:
            logger.error(f"Erro ao processar resultado da consulta: {str(e)}")
            return False
    
    def processar_resultado_api_resolve_cenprot(self, api_result: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Processa resultado completo da API resolve.cenprot.org.br.
        Método otimizado que recebe o resultado completo da API e extrai os dados internamente.
        
        Args:
            api_result: Dicionário completo com resultado da API (inclui 'success', 'data', etc.)
            
        Returns:
            Tupla com: (sucesso, mensagem) onde sucesso é um booleano e mensagem é uma string
        """
        try:
            # Valida estrutura básica do resultado da API
            if not isinstance(api_result, dict):
                logger.error("Resultado da API deve ser um dicionário")
                return False, "Formato de dados inválido"
            
            # Verifica se a API retornou sucesso
            if not api_result.get('success', False):
                error_msg = api_result.get('message', 'Erro desconhecido da API')
                logger.error(f"API retornou erro: {error_msg}")
                return False, f"Erro da API: {error_msg}"
            
            # Extrai os dados do resultado da API
            data = api_result.get('data')
            if not data:
                logger.error("Campo 'data' não encontrado no resultado da API")
                return False, "Dados não encontrados no resultado da API"
            
            # Valida estrutura dos dados extraídos
            if not isinstance(data, dict):
                logger.error("Campo 'data' deve ser um dicionário")
                return False, "Formato dos dados inválido"
            
            # Verifica se contém as chaves essenciais
            required_keys = ['cnpj', 'cenprotProtestos']
            missing_keys = [key for key in required_keys if key not in data]
            if missing_keys:
                logger.error(f"Chaves obrigatórias ausentes nos dados da API: {missing_keys}")
                return False, f"Chaves obrigatórias ausentes: {missing_keys}"
            
            cnpj = data.get('cnpj')
            if not cnpj:
                logger.error("CNPJ não encontrado nos dados da API")
                return False, "CNPJ não encontrado nos dados"
            
            # Remove formatação do CNPJ se necessário
            cnpj_limpo = cnpj.replace(".", "").replace("/", "").replace("-", "")
            resultado_corrigido = data.copy()
            resultado_corrigido['cnpj'] = cnpj_limpo
            
            # Corrige CNPJs nos protestos também
            cenprotProtestos = resultado_corrigido.get('cenprotProtestos', {})
            if cenprotProtestos and isinstance(cenprotProtestos, dict):
                for uf, protestos_uf in cenprotProtestos.items():
                    if isinstance(protestos_uf, list):
                        for protesto_info in protestos_uf:
                            protestos_list = protesto_info.get('protestos', [])
                            for protesto in protestos_list:
                                if 'cpfCnpj' in protesto:
                                    cnpj_original = protesto['cpfCnpj']
                                    cnpj_sem_formatacao = cnpj_original.replace(".", "").replace("/", "").replace("-", "")
                                    protesto['cpfCnpj'] = cnpj_sem_formatacao
            
            # Processa usando método existente
            logger.info(f"Processando resultado da API resolve.cenprot.org.br para CNPJ {cnpj_limpo}")
            success, message = self.inserir_protesto_completo(resultado_corrigido)
            
            if success:
                logger.info(f"Resultado da API para CNPJ {cnpj_limpo} processado e salvo com sucesso")
            else:
                logger.error(f"Falha ao processar resultado da API para CNPJ {cnpj_limpo}: {message}")
            
            return success, message
            
        except Exception as e:
            logger.error(f"Erro ao processar resultado da API resolve.cenprot.org.br: {str(e)}")
            return False, f"Erro no processamento: {str(e)}"
    
    def processar_arquivo_json(self, arquivo_json: str) -> bool:
        """
        Processa um arquivo JSON com resultado de consulta ao CENPROT.
        
        Args:
            arquivo_json: Caminho para o arquivo JSON
            
        Returns:
            True se o processamento foi bem-sucedido, False caso contrário
        """
        try:
            if not os.path.exists(arquivo_json):
                logger.error(f"Arquivo não encontrado: {arquivo_json}")
                return False
            
            with open(arquivo_json, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                
            return self.processar_resultado_consulta(dados)
        except Exception as e:
            logger.error(f"Erro ao processar arquivo JSON {arquivo_json}: {str(e)}")
            return False 
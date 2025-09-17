# CONEXÃO COM BANCO DE DADOS ORACLE

#!/usr/bin/python3.11.9
# ! pip install python-dotenv

import pandas as pd #type: ignore
import cx_Oracle #type: ignore
from dotenv import load_dotenv #type: ignore
import os
import sys
import base64
from pathlib import Path
import logging
from typing import Dict, List, Any, Optional, Union

# Garantir que o diretório de logs existe antes de configurar o logger
ROOT_DIR = Path(__file__).resolve().parent.parent
log_path = Path(ROOT_DIR) / 'log' / 'bd'
log_path.mkdir(parents=True, exist_ok=True)

# Configuração do logger
logger = logging.getLogger(__name__)
handler = logging.FileHandler(log_path / 'oracle_database.log')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class OracleDatabase:
    _client_initialized = False  # Atributo de classe para rastrear a inicialização

    def __init__(self):
        self.initialize_client()  # Inicializa o cliente Oracle se ainda não foi feito

        # Carregar credenciais do banco de dados a partir das variáveis de ambiente
        # Compatível com múltiplas configurações de projeto
        import os
        from dotenv import load_dotenv
        
        # Carregar .env se disponível
        load_dotenv()
        
        # Obter credenciais do ambiente
        db_user = os.environ.get('DB_USER', '')
        db_password = os.environ.get('DB_PASSWORD', '')
        
        if not db_user or not db_password:
            raise ValueError("Credenciais DB_USER e DB_PASSWORD devem estar definidas nas variáveis de ambiente")
        
        self.username = db_user
        # Decodificar senha se estiver em base64
        try:
            decoded_bytes = base64.b64decode(db_password)
            self.password = decoded_bytes.decode('utf-8')
        except Exception:
            # Se não conseguir decodificar como base64, usa a string diretamente
            self.password = db_password

        # Dados de conexão com Oracle
        self.dsn_tns = cx_Oracle.makedsn('192.33.0.3', '1521', service_name='WINT')
        
        # Define o diretório de logs relativo à raiz do projeto
        ROOT_DIR = Path(__file__).resolve().parent.parent
        self.log_path = Path(ROOT_DIR) / 'log' / 'bd'
        self.log_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def initialize_client(cls):
        if not cls._client_initialized:  # Verifica se o cliente já foi inicializado
            try:
                # Detectar se está rodando como executável PyInstaller
                if getattr(sys, 'frozen', False):
                    # Executável PyInstaller
                    base_path = Path(sys._MEIPASS)
                    instantclient_path = base_path / 'instantclient_19_18'
                else:
                    # Desenvolvimento local
                    if os.name == 'nt':  # Windows
                        instantclient_path = Path(r'C:\src\instantclient_19_18')
                    else:  # Linux (Docker)
                        instantclient_path = Path(r'/opt/oracle/instantclient_19_18')
                
                # Verificar se o diretório existe
                if not instantclient_path.exists():
                    raise FileNotFoundError(f"Instant Client não encontrado em: {instantclient_path}")
                
                # Inicializar o cliente Oracle
                cx_Oracle.init_oracle_client(lib_dir=str(instantclient_path))
                cls._client_initialized = True  # Marca como inicializado
                logger.info(f"Cliente Oracle inicializado com sucesso em: {instantclient_path}")
            except cx_Oracle.Error as error:
                logger.error(f"Falha na inicialização do cliente Oracle: {error}")
                raise
            except FileNotFoundError as error:
                logger.error(f"Instant Client não encontrado: {error}")
                raise

    def get_connection(self):
        """Retorna uma nova conexão com o banco de dados Oracle"""
        try:
            connection = cx_Oracle.connect(
                user=self.username,
                password=self.password,
                dsn=self.dsn_tns,
                encoding="UTF-8"
            )
            # Configurar conexão para commit automático
            connection.autocommit = False
            return connection
        except cx_Oracle.Error as error:
            self.log_error("Falha ao conectar ao banco de dados", error)
            raise

    # FUNÇÃO PARA EXECUTAR CONSULTAS SQL
    def select(self, sql: str) -> pd.DataFrame:
        connection = None
        cursor = None
        try:
            connection = self.get_connection()
            # Usar cursor de dicionário para facilitar o processamento
            cursor = connection.cursor()
            cursor.execute(sql)
            
            # Obter nomes das colunas e convertê-los para minúsculo
            columns = [col[0].lower() for col in cursor.description]
            
            # Mapear tipos de dados Oracle para Python
            oracle_types = [col[1] for col in cursor.description]
            
            # Processar resultados para garantir que sejam compatíveis com pandas
            processed_rows = []
            for row in cursor.fetchall():
                processed_row = []
                for i, item in enumerate(row):
                    # Converter LOBs e outros tipos complexos em strings
                    if isinstance(item, cx_Oracle.LOB):
                        processed_row.append(item.read())
                    # Converter valores numéricos
                    elif oracle_types[i] in [cx_Oracle.DB_TYPE_NUMBER, cx_Oracle.NUMBER]:
                        if item is not None:
                            # Tentar converter para int ou float conforme necessário
                            try:
                                # Se for um número inteiro, converter para int
                                if float(item).is_integer():
                                    processed_row.append(int(item))
                                else:
                                    processed_row.append(float(item))
                            except:
                                processed_row.append(item)
                        else:
                            processed_row.append(item)
                    elif hasattr(item, '__str__'):
                        processed_row.append(str(item))
                    else:
                        processed_row.append(item)
                processed_rows.append(processed_row)
            
            # Criar DataFrame com os dados processados
            # Usando lowercase para todas as colunas
            df = pd.DataFrame(processed_rows, columns=columns)
            
            # O método itertuples() do pandas já permite acesso por atributo
            # Não é necessário fazer mais nada, o pandas lidará com isso corretamente
            
            return df
        except Exception as error:
            self.log_error(sql, error)
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    # FUNÇÃO PARA EXECUTAR UPDATE E INSERT
    def update(self, sql: str) -> int:
        connection = None
        cursor = None
        rowcount = 0
        try:
            connection = self.get_connection()
            cursor = connection.cursor()
            cursor.execute(sql)
            rowcount = cursor.rowcount
            connection.commit()
            return rowcount
        except Exception as error:
            if connection:
                connection.rollback()
            self.log_error(sql, error)
            return 0
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
                
    # FUNÇÃO PARA EXECUTAR BLOCOS PL/SQL ANÔNIMOS
    def executar_bloco_pl_sql(self, bloco_pl_sql: str, parametros: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executa um bloco PL/SQL anônimo com parâmetros opcionais.
        
        Args:
            bloco_pl_sql: String contendo o bloco PL/SQL anônimo a ser executado
            parametros: Dicionário com os parâmetros de bind para o bloco PL/SQL
            
        Returns:
            Dicionário com o resultado da execução contendo:
            - 'success': True se a execução foi bem-sucedida, False caso contrário
            - 'rowcount': Número de linhas afetadas (quando aplicável)
            - 'message': Mensagem de retorno (sucesso ou erro)
            - 'output_params': Dicionário com valores de parâmetros de saída (quando existirem)
        """
        connection = None
        cursor = None
        start_time = pd.Timestamp.now()
        result = {
            'success': False,
            'rowcount': 0,
            'message': '',
            'output_params': {}
        }
        
        try:
            # Log de início da execução
            logger.info(f"Iniciando execução de bloco PL/SQL")
            if parametros:
                param_log = {k: v for k, v in parametros.items() if not isinstance(v, (list, dict))}
                logger.info(f"Parâmetros: {param_log}")
            
            connection = self.get_connection()
            cursor = connection.cursor()
            
            # Preparar parâmetros de bind
            bind_vars = {}
            output_params = {}
            
            # Configurar parâmetros de entrada e saída
            if parametros:
                for key, value in parametros.items():
                    # Verifica se é um parâmetro de saída (formato: 'out:tipo')
                    if isinstance(value, str) and value.startswith('out:'):
                        tipo = value.split(':')[1].strip().upper()
                        if tipo == 'NUMBER':
                            bind_vars[key] = cursor.var(cx_Oracle.NUMBER)
                        elif tipo == 'STRING' or tipo == 'VARCHAR2':
                            bind_vars[key] = cursor.var(cx_Oracle.STRING)
                        elif tipo == 'DATE':
                            bind_vars[key] = cursor.var(cx_Oracle.DATETIME)
                        elif tipo == 'CURSOR':
                            bind_vars[key] = cursor.var(cx_Oracle.CURSOR)
                        else:
                            bind_vars[key] = cursor.var(cx_Oracle.STRING)
                        
                        # Registra para recuperar após a execução
                        output_params[key] = bind_vars[key]
                    else:
                        # Parâmetro normal de entrada
                        bind_vars[key] = value
            
            # Executar o bloco PL/SQL
            cursor.execute(bloco_pl_sql, bind_vars)
            
            # Processar parâmetros de saída
            for key, var in output_params.items():
                if var.type == cx_Oracle.CURSOR:
                    # Processar cursor de saída para DataFrame
                    result_cursor = var.getvalue()
                    if result_cursor:
                        # Obter nomes das colunas
                        columns = [col[0].lower() for col in result_cursor.description]
                        rows = result_cursor.fetchall()
                        result['output_params'][key] = pd.DataFrame(rows, columns=columns)
                        result_cursor.close()
                else:
                    # Outros tipos de saída
                    result['output_params'][key] = var.getvalue()
            
            # Commit da transação
            connection.commit()
            
            # Registrar sucesso
            result['success'] = True
            result['rowcount'] = cursor.rowcount
            result['message'] = "Bloco PL/SQL executado com sucesso"
            
            # Log de conclusão
            elapsed_time = (pd.Timestamp.now() - start_time).total_seconds()
            logger.info(f"Bloco PL/SQL executado com sucesso em {elapsed_time:.2f} segundos.")
            return result
            
        except Exception as error:
            # Rollback em caso de erro
            if connection:
                connection.rollback()
            
            # Registrar erro
            self.log_error(bloco_pl_sql, error)
            
            # Construir resultado de erro
            result['success'] = False
            result['message'] = str(error)
            
            # Log de erro
            elapsed_time = (pd.Timestamp.now() - start_time).total_seconds()
            logger.error(f"Erro ao executar bloco PL/SQL após {elapsed_time:.2f} segundos: {error}")
            return result
            
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def log_error(self, sql: str, error: Exception) -> None:
        with open(str(self.log_path / 'oracle-error.log'), 'a', encoding='utf-8') as file:
            file.write(f'\n\nSQL:\n\n{sql}\n\nERRO [ORACLE]:\n\n{error}')


# # Exemplo de uso
# if __name__ == "__main__":
#     try:
#         db = OracleDatabase()
        
#         codcli = 78270
#         print("Executando update...")
#         rowcount = db.update(f"""update pcclient
#                             set cliente = 'teste agora' 
#                             where codcli = {codcli}""")
#         print(f"Linhas afetadas: {rowcount}")
        
#         print("\nExecutando select...")
#         sql = f"""
#             select codcli, cliente from pcclient where codcli = {codcli}
#         """
        
#         df = db.select(sql)
        
#         # Verificar se o DataFrame não está vazio antes de imprimir
#         if not df.empty:
#             print(f"Total de linhas retornadas: {len(df)}")
#             print(f"Colunas: {df.columns.tolist()}")
#             print("\nPrimeiras 5 linhas:")
#             # Usar método head() para limitar a saída
#             print(df.head(5).to_string(index=False))
#         else:
#             print("Nenhum resultado encontrado.")
#     except Exception as e:
#         print(f"Erro ao executar o script: {e}") 
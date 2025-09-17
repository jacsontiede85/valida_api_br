# Exemplo de Uso do `oracle_casaaladim.py`

Este documento fornece um exemplo de como utilizar a classe `OracleDatabase` definida no arquivo `oracle_casaaladim.py` para interagir com um banco de dados Oracle.

## Pré-requisitos

Antes de executar o exemplo, certifique-se de que:

- O arquivo `oracle_casaaladim.py` está corretamente configurado e acessível.
- As variáveis de ambiente necessárias estão definidas em um arquivo `.env` na raiz do projeto:
  - `DB_USER`: Nome de usuário do banco de dados.
  - `DB_PASSWORD`: Senha do banco de dados (codificada em base64).
- O Oracle Instant Client está instalado:
  - No Windows: `C:\src\instantclient_19_18`
  - No Linux (Docker): `/opt/oracle/instantclient_19_18`
- Pacotes Python necessários:
  - `cx_Oracle`
  - `pandas`
  - `python-dotenv`

## Estrutura da Classe OracleDatabase

A classe `OracleDatabase` oferece os seguintes métodos principais:

1. `select(sql)`: Executa consultas SQL e retorna um DataFrame pandas com os resultados.
2. `update(sql)`: Executa comandos de UPDATE ou INSERT e retorna o número de linhas afetadas.

## Exemplos de Uso

### Exemplo básico de consulta e atualização

```python
from bd.oracle_casaaladim import OracleDatabase

# Criando uma instância da conexão
db = OracleDatabase()

# Executando uma consulta SELECT
result = db.select("SELECT * FROM pcclient WHERE codcli = 78270")
print(f"Dados antes da atualização:")
print(result)

# Executando um UPDATE
linhas_afetadas = db.update("UPDATE pcclient SET cliente = 'TESTE SETOR DE TI' WHERE codcli = 78270")
print(f"Linhas afetadas: {linhas_afetadas}")

# Verificando o resultado após atualização
result = db.select("SELECT * FROM pcclient WHERE codcli = 78270")
print(f"Dados após a atualização:")
print(result)
```

### Exemplo mais elaborado

```python
from bd.oracle_casaaladim import OracleDatabase

try:
    db = OracleDatabase()
    
    # Consultando dados
    codcli = 78270
    sql = f"""
        SELECT codcli, cliente 
        FROM pcclient 
        WHERE codcli = {codcli}
    """
    
    df = db.select(sql)
    
    # Verificando se o DataFrame não está vazio antes de imprimir
    if not df.empty:
        print(f"Total de linhas retornadas: {len(df)}")
        print(f"Colunas: {df.columns.tolist()}")
        print("\nRegistros encontrados:")
        print(df.to_string(index=False))
        
        # Exemplo de acesso aos dados usando itertuples()
        for row in df.itertuples():
            print(f"Código: {row.codcli}, Cliente: {row.cliente}")
    else:
        print("Nenhum resultado encontrado.")
    
    # Executando uma atualização
    novo_nome = "Cliente Atualizado"
    rowcount = db.update(f"""
        UPDATE pcclient
        SET cliente = '{novo_nome}' 
        WHERE codcli = {codcli}
    """)
    
    print(f"Linhas afetadas pelo UPDATE: {rowcount}")
    
except Exception as e:
    print(f"Erro ao executar as operações: {e}")
```

## Notas Importantes

1. A classe gerencia automaticamente a conexão e a fecha após cada operação.
2. Os erros são registrados em um arquivo de log em `logs/services/oracle-error.log`.
3. Transações (commit/rollback) são gerenciadas automaticamente.
4. Os nomes das colunas são convertidos para minúsculas no DataFrame retornado.
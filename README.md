# Resolve CenProt API - Serviço Windows

API REST para consulta de protestos no site resolve.cenprot.org.br, compilada como executável e instalada como serviço Windows.

## 🚀 Instalação Rápida

### Pré-requisitos
- Windows 10/11 ou Windows Server 2016+
- Executável compilado: `dist\resolve-cenprot.exe`

### Instalar o Serviço

1. **Abra PowerShell como Administrador**
2. **Navegue até a pasta do projeto**:
   ```powershell
   cd C:\src\resolve_cenprot
   ```
3. **Execute o instalador**:
   ```batch
   install-service-direct.bat
   ```

### Gerenciar o Serviço

Use `manage-service.bat` para:
- Verificar status
- Iniciar/Parar/Reiniciar
- Ver logs
- Desinstalar

## 📋 Estrutura do Projeto

```
resolve_cenprot/
├── dist/
│   └── resolve-cenprot.exe    # Executável compilado (83MB)
├── logs/
│   ├── service.log            # Log principal do serviço
│   └── service_error.log      # Log de erros
├── api/                       # Módulos da API
├── src/                       # Código fonte
├── bd/                        # Módulos de banco de dados
├── data/                      # Dados e sessões
├── files_api_local/           # Arquivos JSON de exemplo
├── nssm.exe                   # Gerenciador de serviços
├── install-service-direct.bat # Instalador do serviço
├── manage-service.bat         # Gerenciador do serviço
├── uninstall-service.bat      # Desinstalador
├── run.py                     # Script principal
├── resolve-cenprot.spec       # Configuração PyInstaller
└── .env                       # Configurações
```

## 🌐 Endpoints da API

Após a instalação, acesse:

- **Documentação Interativa**: http://localhost:8099/docs
- **Status da API**: http://localhost:8099/status
- **Redoc**: http://localhost:8099/redoc

### Principais Endpoints

- `POST /api/v1/cnpj/consult` - Consultar CNPJ
- `GET /api/v1/session/status` - Status da sessão
- `POST /api/v1/session/login` - Login (se necessário)

## ⚙️ Configuração

### Alterar Porta

Edite o arquivo `.env`:
```env
SERVER_PORT=8099
```

### Configurações do Serviço

- **Nome**: ResolveCenprotAPI
- **Inicialização**: Automática
- **Reinicialização**: Automática em caso de falha
- **Logs**: Rotação automática (10MB)

## 🛠️ Comandos Úteis

```batch
# Verificar status do serviço
sc query ResolveCenprotAPI

# Iniciar serviço
sc start ResolveCenprotAPI

# Parar serviço
sc stop ResolveCenprotAPI

# Ver logs
type logs\service.log
```

## 📊 Monitoramento

### Logs
- `logs/service.log` - Log principal da aplicação
- `logs/service_error.log` - Erros e exceções

### Event Viewer
1. Abra o Event Viewer (eventvwr.msc)
2. Navegue para: Windows Logs → Application
3. Filtre por Source: ResolveCenprotAPI

## 🔧 Solução de Problemas

### Serviço não inicia
1. Verifique os logs em `logs/service_error.log`
2. Execute: `sc query ResolveCenprotAPI`
3. Tente reiniciar: `sc stop ResolveCenprotAPI && sc start ResolveCenprotAPI`

### API não responde
1. Verifique se a porta 8099 está livre: `netstat -ano | findstr :8099`
2. Verifique o status: http://localhost:8099/status

### Reinstalar o serviço
```batch
uninstall-service.bat
install-service-direct.bat
```

## 📝 Desenvolvimento

### Recompilar o Executável
```batch
pyinstaller --clean --noconfirm resolve-cenprot.spec
```

### Executar em Modo Desenvolvimento
```batch
python run.py
```

## 📄 Licença

Copyright (c) 2025 CenProt Solutions. Todos os direitos reservados.

## 🆘 Suporte

Para problemas ou dúvidas:
1. Verifique os logs em `logs/`
2. Consulte a documentação em `/docs`
3. Verifique o status em `/status`
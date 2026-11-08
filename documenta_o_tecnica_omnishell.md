# 📚 Documentação Técnica — OmniShell

> **Versão:** 1.0.0  
> **Autor / Criador:** [Marcelo Ramiro Rissi / Celorissi]  
> **Arquitetura:** Event-Driven Web SSH Jumper & Infrastructure Manager  
> **Stack Principal:** Python (Flask / Socket.IO / Paramiko / Eventlet) + Xterm.js + Docker  

---

## 1. Visão Geral e Arquitetura

O **OmniShell** nasceu da minha necessidade de criar um painel web moderno, leve, seguro e altamente eficiente para a gestão de conexões SSH e automações de infraestrutura. Projetado a pensar em engenheiros de redes e administradores de sistemas, o OmniShell centraliza o acesso simultâneo a múltiplos dispositivos (routers, switches, firewalls e servidores) diretamente pelo browser, oferecendo a estabilidade e fluidez de clientes nativos como o *MobaXterm*.

### 1.1 Diagrama de Fluxo e Arquitetura de Dados

```text
[ Browser / Client ] 
    │ (HTTPS / WSS - HTML, Bootstrap 5, Xterm.js, Dark Theme)
    ▼
[ WSGI Server (Eventlet) + Flask App (ssh.py) ]
    ├── Authentication & Session Manager (users.json)
    ├── Inventory Parser (devices_<user>.xlsx via Pandas)
    └── SSH Engine (Paramiko Bridge Manager)
            │
            │ (Encapsulamento SSHv2 - PTY Xterm / Port 22)
            ▼
[ Dispositivos de Rede / Servidores ] (Cisco, Fortinet, Juniper, Linux, etc.)
```

---

## 2. Requisitos de Ambiente & Dependências

### 2.1 Requisitos Mínimos de Hardware
- **CPU:** 1-2 vCPU (Otimizado para x86_64 e dispositivos ARM64 como Raspberry Pi 4/5).
- **RAM:** 512 MB (Mínimo) / 2 GB (Recomendado para dezenas de conexões concorrentes).
- **Rede:** Rota IP acessível na porta 22 (SSH) para os alvos geridos.

### 2.2 Requisitos de Software & Bibliotecas Python
- **Python:** `3.11+`
- **Dependências Principais (`requirements.txt`):**
  - `flask`: Roteamento HTTP e controlo de sessões.
  - `flask-socketio`: Camada de comunicação assíncrona em tempo real (WebSockets).
  - `eventlet`: Servidor de concorrência não bloqueante (*high-performance non-blocking I/O*).
  - `paramiko`: Implementação nativa do protocolo SSHv2 em Python.
  - `pandas` & `openpyxl`: Leitura e parse dos inventários em Excel.
  - `werkzeug`: Encriptação e validação segura de hashes de password.

---

## 3. Funcionalidades Principais Desenvolvidas

- **Autenticação Segura & Isolada:** Contas protegidas por hash de palavra-passe (`Werkzeug`). Cada utilizador possui o seu próprio espaço de trabalho e inventário em ficheiro `.xlsx` individual, garantindo total isolamento de dados.
- **Painel de Administração Global (`admin`):**
  - Controlo total do ciclo de vida dos utilizadores (criação, redefinição de credenciais, remoção).
  - Monitorização em tempo real de sessões ativas (IP de origem, dispositivo conectado, tempo de sessão).
  - Botão de desconnexão forçada (*Kill Session*).
- **Terminais Simultâneos (Xterm.js):** Grelha flexível e dinâmica (1 painel único, 2 painéis lado a lado ou matriz de 4 painéis) para execução simultânea de comandos.
- **Buffer Alargado (50.000 Linhas):** Histórico retroativo massivo em memória por painel para auditoria completa e consultas de logs ou *show running-config*.
- **Múltiplos Temas Visuais (Dark Theme Integrado):**
  - *Classic Green* (Estilo terminal retro).
  - *MobaXterm Dark* (Fundo preto absoluto `#000000` com alto contraste).
  - *Dracula*, *Matrix*, *Nord*, entre outros.
- **Temporizador de Inatividade Rigoroso (`Idle Timeout`):** Thread de controlo que encerra sessões automaticamente após o período de inatividade configurado pelo utilizador (de 1 a 120 minutos).
- **Cronómetro em Tempo Real:** Contador ativo no cabeçalho de cada terminal a contabilizar a duração exata da sessão (`HH:MM:SS`).
- **Exportação de Logs Local:** Botão dedicado que converte o buffer ativo do Xterm.js em texto limpo e descarrega um ficheiro `.txt` com timestamp.
- **Colagem Segura (*Safe Paste*):** Modal ativado via clique direito para inspeção e validação de scripts antes do envio para a consola.

---

## 4. Estrutura do Inventário Excel (`devices_<utilizador>.xlsx`)

Para que o OmniShell construa automaticamente a árvore de navegação na barra lateral, o ficheiro Excel do utilizador deve estruturar-se com as seguintes colunas:

| Coluna | Tipo | Obrigatório | Descrição / Exemplo |
| :--- | :--- | :--- | :--- |
| `folder` | String | Sim | Pasta na árvore (ex: `Datacenter / Core-Switches` ou `Firewalls`). |
| `hostname` | String | Sim | Nome de identificação (ex: `SW-SP-01`). |
| `ip` | String | Sim | Endereço IP ou FQDN do equipamento (ex: `192.168.10.1`). |
| `port` | Integer | Não | Porta SSH (Padrão: `22`). |
| `username` | String | Não | Utilizador SSH predefinido (se omitido, o sistema solicita no pop-up de conexão). |

---

## 5. Arquitetura Interna do Código Backend (`ssh.py`)

O motor do OmniShell foi construído com uma arquitetura orientada a eventos para garantir máxima fluidez:

### 5.1 O Motor de Concorrência
```python
import eventlet
eventlet.monkey_patch()
```
*Garante a substituição do I/O padrão do Python por greensocks, permitindo que o Paramiko e o Socket.IO processem múltiplos fluxos SSH concorrentes sem bloquear a aplicação web.*

### 5.2 O Fluxo da Classe `SSHBridge`
1. **`connect(host, port, username, password)`**: Autentica no alvo via Paramiko e aloca um Pseudo-Terminal (PTY) com dimensões iniciais padrão.
2. **`_read_from_ssh()`**: Ciclo contínuo que lê os bytes recebidos do equipamento (`recv(1024)`) e emite via WebSocket (`ssh_output`) para o browser.
3. **`_check_idle_timeout()`**: Thread de vigilância que avalia a inatividade e encerra a sessão de forma limpa caso o limite seja atingido.
4. **`resize(rows, cols)`**: Ajusta em tempo real o PTY remoto sempre que o utilizador altera o tamanho da janela no browser.

---

## 6. Arquitetura do Frontend (`templates/index.html`)

O frontend funciona como uma Single Page Application (SPA) assíncrona:
- **Xterm.js Core:** Instanciação dinâmica com suporte a buffer de 50.000 linhas e addons de redimensionamento (`FitAddon`).
- **Gestão de Eventos de Janela:** Um `ResizeObserver` monitoriza os contentores e redimensiona os terminais de forma fluida quando a barra lateral é recolhida ou a grelha é alterada.

---

## 7. Guia de Deploy com Docker

O OmniShell foi concebido para ser executado de forma simples e portátil via Docker.

### 7.1 Ficheiro `Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8513

CMD ["python", "ssh.py"]
```

### 7.2 Ficheiro `docker-compose.yml`
```yaml
version: '3.8'

services:
  omnishell:
    build: .
    container_name: omnishell-app
    restart: always
    ports:
      - "8513:8513"
    volumes:
      - ./data/users.json:/app/users.json
      - ./data/devices:/app/devices
    environment:
      - PYTHONUNBUFFERED=1
```

---

## 8. Resolução de Problemas (Troubleshooting)

- **Caracteres corrompidos no terminal:** O OmniShell força nativamente `term='xterm'`. Valide se o equipamento remoto suporta codificação UTF-8.
- **Desconexão por Inatividade:** Verifique e ajuste o parâmetro `Idle Timeout` nas configurações de perfil do utilizador.
- **Inventário em Excel não carrega:** Certifique-se de que a primeira linha do ficheiro possui exatamente os nomes de colunas exigidos (`folder`, `hostname`, `ip`, `port`, `username`).

---
*OmniShell v1.0.0 — Desenvolvido com foco em alta performance e simplicidade operacional.*
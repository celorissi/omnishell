# 📚 Documentação Técnica — Portal Web SSH (NRE)

## 1. Visão Geral e Arquitetura
O **Portal SSH Jumper** é uma aplicação corporativa robusta desenvolvida em **Python (Flask, Flask-SocketIO e Eventlet)** no backend e **Bootstrap 5 com Xterm.js** no frontend. O seu principal objetivo é permitir a administradores e engenheiros de redes o acesso centralizado, seguro e simultâneo a múltiplos dispositivos via SSH diretamente pelo browser, simulando a experiência e estabilidade de ferramentas profissionais como o *MobaXterm*.

---

## 2. Funcionalidades Principais

* **Autenticação Segura & Isolada:** Contas de utilizador protegidas por hash de palavra-passe (`Werkzeug`), com inventários de dispositivos individuais salvos em ficheiros `.xlsx`.
* **Painel de Administração Global (`admin`):** Permite listar utilizadores, redefinir credenciais, eliminar contas, monitorizar sessões ativas e forçar desconexões remotas.
* **Terminais Simultâneos (Xterm.js):** Suporte a grelhas flexíveis (1 painel, 2 lado a lado ou grelha de 4 painéis).
* **Buffer Alargado (50.000 Linhas):** Histórico retroativo massivo em qualquer tema visual para auditoria de comandos.
* **Múltiplos Temas Visuais:** Inclui o verde clássico (`classic`), o autêntico *MobaXterm* (fundo preto absoluto `#000000`), *Matrix*, *Dracula*, *Nord*, entre outros.
* **Temporizador de Ociosidade Rigoroso (`Idle Timeout`):** Encerramento automático configurável por utilizador (ex: 1 minuto para testes ou 30 minutos corporativos) em caso de inatividade.
* **Cronómetro em Tempo Real:** Contador ativo no cabeçalho de cada terminal a contabilizar a duração exata da sessão (`HH:MM:SS`).
* **Exportação de Logs:** Botão dedicado para descarregar todo o histórico do terminal atual num ficheiro de texto (`.txt`) com timestamp.
* **Colagem Segura:** Caixa flutuante acionada por clique direito para validação de blocos de texto e scripts antes do envio.
* **Atalhos Úteis:** Atalho `Ctrl + R` para reconexão rápida e cópia automática para a área de transferência ao selecionar texto com o rato.

---

## 3. Estrutura e Explicação do Código Backend (`ssh.py`)

O ficheiro `ssh.py` é o coração da aplicação. Ele gere o servidor HTTP/WebSocket, as rotas de segurança, a leitura de inventários e as pontes SSH.

* **Inicialização e Concorrência (`Eventlet`):**
  * Utiliza `eventlet.monkey_patch()` para garantir operações assíncronas e evitar bloqueios na execução simultânea dos WebSockets.
* **Gestão de Utilizadores e Ficheiros (`json` e `pandas`):**
  * `carregar_utilizadores()` / `guardar_utilizadores()`: Lêem e gravam as credenciais e as preferências de timeout no ficheiro `users.json`.
  * `carregar_arvore_devices()`: Lê o ficheiro Excel (`devices_<utilizador>.xlsx`) correspondente ao utilizador logado e transforma as colunas numa árvore de pastas hierárquica para a barra lateral.
* **Rotas HTTP Protegidas:**
  * `/login` e `/register`: Autenticam e criam novas contas, gerando automaticamente a pasta e o Excel de inventário inicial do utilizador.
  * `/api/user/settings`: Gere e atualiza o tempo limite de ociosidade (`idle_timeout`) personalizado de cada utilizador.
  * `/api/admin/...`: Rotas restritas exclusivamente à conta `admin` para auditoria de sessões ativas, força de logout e eliminação de utilizadores.
* **A Classe `SSHBridge` (O Motor SSH):**
  * `connect()`: Estabelece a conexão Paramiko com o alvo e invoca uma shell interativa (`term='xterm'`).
  * `_read_from_ssh()`: Lê continuamente os dados vindos do equipamento de rede e envia-os via Socket.IO para o browser.
  * `_check_idle_timeout()`: Uma thread dedicada que verifica a cada 5 segundos se o tempo de inatividade (`time.time() - self.last_activity`) ultrapassou o limite configurado pelo utilizador, disparando o encerramento automático caso excedido.
  * `write()` / `resize()` / `close()`: Processam os inputs do utilizador, redimensionam o PTY da shell e encerram os sockets de forma limpa.

---

## 4. Estrutura e Explicação do Código Frontend (`templates/index.html`)

O ficheiro `index.html` agrupa a interface visual corporativa, a árvore de navegação, a grelha de terminais e todos os modais de gestão.

* **Layout e Sidebar:**
  * Estrutura Flexbox dividida entre a barra lateral colapsável (com a árvore de dispositivos e botões de atalho) e a área principal de terminais.
* **Gestão de Múltiplos Terminais (`Xterm.js`):**
  * `criarNovoTerminalSimultaneo()`: Instancia dinamicamente um novo objeto `Terminal` com o buffer configurado para **50.000 linhas** (`scrollback: 50000`) e o tema padrão **Verde Clássico** (`classic`).
  * Associa addons de redimensionamento (`FitAddon`) e escuta os eventos de Socket.IO (`ssh_output`, `ssh_connected`, `ssh_closed`).
* **Temporizadores e Timers:**
  * Um `setInterval` global de 1 segundo percorre todas as sessões ativas e atualiza o cronómetro visual (`00:00`) no cabeçalho de cada painel.
* **Exportação de Logs:**
  * A função `exportarLogTerminal()` percorre o buffer ativo do Xterm.js, traduz as linhas para texto puro e descarrega um ficheiro `.txt` nomeado com o hostname e a data/hora exata.
* **Segurança e Colagem:**
  * O evento de clique direito (`contextmenu`) intercepta o comportamento padrão do browser e abre a caixa flutuante de colagem segura, evitando que blocos grandes de comandos corrompam a consola antes de serem confirmados.

---

## 5. Fluxo de Autenticação (`login.html` / `login` route)

* **Credenciais:** O sistema valida o nome de utilizador e compara o hash da palavra-passe guardado no `users.json` através de `check_password_hash`.
* **Sessão Flask:** Se bem-sucedido, o nome do utilizador é gravado em `session['username']`, concedendo acesso à rota raiz (`/`).
* **Isolamento de Dados:** Todas as consultas de dispositivos e definições subsequentes utilizam o nome de utilizador presente na sessão ativa, garantindo total isolamento entre operadores.
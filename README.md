# ⚡ OmniShell

> Painel web moderno, leve e seguro para gestão de conexões SSH e automações de infraestrutura, com tema escuro integrado, suporte a Docker e autenticação de utilizadores.

![OmniShell Preview](https://img.shields.io/badge/Status-Active-success) ![Python](https://img.shields.io/badge/Python-3.11%2B-blue) ![Docker](https://img.shields.io/badge/Docker-Ready-informational)

---

## 🚀 Funcionalidades

* **Terminais SSH Rápidos e Persistentes:** Interface web interativa para acesso direto a servidores e dispositivos de rede.
* **Tema Escuro Nativo:** Identidade visual moderna e cuidada, com alto contraste e legibilidade garantida em modais, formulários e alertas.
* **Gestão de Utilizadores:** Sistema seguro de autenticação com alteração obrigatória de senha no primeiro acesso.
* **Pronto para Docker:** Execução isolada e portátil, otimizada para ambientes locais, servidores ou dispositivos como o Raspberry Pi.

---

## 🛠️ Tecnologias Utilizadas

* **Backend:** Python (Flask, Flask-SocketIO, Paramiko, Eventlet)
* **Frontend:** Bootstrap, FontAwesome, CSS Personalizado (Dark Theme)
* **Infraestrutura:** Docker & Docker Compose

---

## 📦 Instalação e Execução (Docker)

A forma mais rápida de colocar o OmniShell a funcionar é utilizando o Docker Compose.

1. **Clonar o repositório:**
   ```bash
   git clone https://github.com/celorissi/omnishell.git
   cd omnishell

### 1.1 - Subir o contentor com o Docker Compose:

```Bash
docker compose up -d --build
```

Aceder à aplicação:
Abra o seu browser conforme abaixo:
```
http://<IP-DO-SERVIDOR>:8513
```
### 1.2 - Credenciais Padrão (Primeiro Acesso):

Utilizador: admin

Palavra-passe: admin123(O sistema solicitará a definição de uma nova senha definitiva logo no primeiro login).

📁 Estrutura do Projeto

<pre>
omnishell/
├── static/           # Imagens, logótipos, favicons e estilos CSS personalizados
├── templates/        # Ficheiros HTML (login, index, modais)
├── Dockerfile        # Configuração do ambiente Python optimizado
├── docker-compose.yml# Orquestração do contentor
├── requirements.txt  # Dependências fixadas do projeto
└── ssh.py            # Aplicação principal (Flask / SocketIO / Paramiko)
</pre>

📄 Licença
Este projeto é de uso livre para fins educacionais, de laboratório e gestão de infraestruturas. Sinta-se à vontade para contribuir com melhorias!


---

Basta criar o ficheiro `README.md` na raiz da pasta do projeto com este conteúdo, ajustar o URL do seu repositório no comando de `git clone` e fazer o commit e push para o GitHub!



import os
import json
import time
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_socketio import SocketIO, emit
import paramiko
import pandas as pd
import threading
import shutil
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nre-ssh-secure-secret-key-2026'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

USERS_DB = 'users.json'
USERS_FILE = 'users.json'  # Correção: Declarado explicitamente para a função init_users_file
USERS_DIR = 'users'
ADMIN_USER = 'admin'  # Administrador principal protegido

if not os.path.exists(USERS_DIR):
    os.makedirs(USERS_DIR)

def init_users_file():
    if not os.path.exists(USERS_FILE):
        initial_password_hash = generate_password_hash("admin123")
        users_data = {
            "admin": {
                "password": initial_password_hash,
                "approved": True,
                "active": True,
                "must_change_password": True,  # Força a alteração no 1º acesso
                "idle_timeout": 5
            }
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users_data, f, indent=4)
        print("> Ficheiro users.json criado com o utilizador 'admin' inicial (palavra-passe: admin123).")

def carregar_utilizadores():
    if not os.path.exists(USERS_DB):
        return {}
    try:
        with open(USERS_DB, 'r', encoding='utf-8') as f:
            data = json.load(f)
            updated = {}
            for k, v in data.items():
                if isinstance(v, str):
                    updated[k] = {'password': v, 'idle_timeout': 1, 'must_change_password': False, 'approved': (k == ADMIN_USER), 'active': True}
                else:
                    if 'must_change_password' not in v:
                        v['must_change_password'] = False
                    if 'approved' not in v:
                        v['approved'] = (k == ADMIN_USER)
                    if 'active' not in v:
                        v['active'] = True
                    updated[k] = v
            return updated
    except:
        return {}

def guardar_utilizadores(users):
    with open(USERS_DB, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4)

def obter_caminho_excel(username):
    user_folder = os.path.join(USERS_DIR, username)
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    return os.path.join(user_folder, f'devices_{username}.xlsx')

def carregar_arvore_devices(username):
    excel_path = obter_caminho_excel(username)
    if not os.path.exists(excel_path):
        df_init = pd.DataFrame([{
            'categoria': 'Geral',
            'nome': 'Exemplo Servidor',
            'ip': '127.0.0.1',
            'porta': 22,
            'usuario': 'root'
        }])
        df_init.to_excel(excel_path, index=False)
    
    df = pd.read_excel(excel_path).fillna('')
    tree = {}

    for _, row in df.iterrows():
        cat_path = str(row.get('categoria', 'Geral')).strip()
        if not cat_path: cat_path = 'Geral'
            
        partes_pasta = [p.strip() for p in cat_path.replace('/', '>').split('>') if p.strip()]
        
        current_level = tree
        for parte in partes_pasta:
            if parte not in current_level:
                current_level[parte] = {"__devices__": []}
            current_level = current_level[parte]
            
        if "__devices__" not in current_level:
            current_level["__devices__"] = []

        current_level["__devices__"].append({
            "nome": str(row.get('nome', '')),
            "ip": str(row.get('ip', '')),
            "porta": int(row.get('porta', 22)) if str(row.get('porta', 22)).isdigit() else 22,
            "usuario": str(row.get('usuario', ''))
        })
        
    return tree

# --- ROTAS DE AUTENTICAÇÃO E GESTÃO ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        users = carregar_utilizadores()
        if username in users:
            user_info = users[username]
            
            if not user_info.get('active', True):
                return render_template('login.html', error='Esta conta encontra-se inativada pelo administrador.')
            
            if not user_info.get('approved', False) and username != ADMIN_USER:
                return render_template('login.html', error='A sua conta aguarda aprovação do administrador.')
                
            stored_pass = user_info.get('password', '')
            if check_password_hash(stored_pass, password):
                session['username'] = username
                
                if user_info.get('must_change_password', False):
                    if request.is_json:
                        return jsonify({'status': 'success', 'redirect': '/force_change_password'})
                    return redirect(url_for('force_change_password_page'))

                if request.is_json:
                    return jsonify({'status': 'success', 'redirect': '/'})
                return redirect(url_for('index'))
        
        if request.is_json:
            return jsonify({'status': 'error', 'message': 'Utilizador ou palavra-passe incorretos.'}), 401
        return render_template('login.html', error='Utilizador ou palavra-passe incorretos.')
        
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() if request.is_json else request.form
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return render_template('login.html', error='Preencha todos os campos.')
        
    users = carregar_utilizadores()
    if username in users:
        return render_template('login.html', error='Este utilizador já existe.')
        
    is_approved = (username == ADMIN_USER)
    
    users[username] = {
        'password': generate_password_hash(password),
        'idle_timeout': 1,
        'must_change_password': False,
        'approved': is_approved,
        'active': True
    }
    guardar_utilizadores(users)
    obter_caminho_excel(username)
    
    if is_approved:
        session['username'] = username
        return redirect(url_for('index'))
        
    return render_template('login.html', error='Registo efetuado com sucesso! Aguarde a aprovação do administrador.')

@app.route('/force_change_password', methods=['GET', 'POST'])
def force_change_password_page():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        nova_senha = data.get('new_password', '').strip()
        
        if not nova_senha:
            return jsonify({'status': 'error', 'message': 'A nova palavra-passe não pode estar vazia.'}), 400
            
        username = session['username']
        users = carregar_utilizadores()
        
        if username in users:
            users[username]['password'] = generate_password_hash(nova_senha)
            users[username]['must_change_password'] = False
            guardar_utilizadores(users)
            
            if request.is_json:
                return jsonify({'status': 'success', 'redirect': '/'})
            return redirect(url_for('index'))
            
    return render_template('force_change_pass.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Não autorizado'}), 401
    
    username = session['username']
    if username == ADMIN_USER:
        return jsonify({'status': 'error', 'message': 'A conta de administrador principal não pode ser eliminada.'}), 403

    data = request.get_json() if request.is_json else {}
    confirmacao_texto = data.get('confirm_text', '').strip()

    if confirmacao_texto != username:
        return jsonify({'status': 'error', 'message': 'O texto de confirmação não corresponde ao seu nome de utilizador.'}), 400

    try:
        users = carregar_utilizadores()
        if username in users:
            del users[username]
            guardar_utilizadores(users)
        
        user_folder = os.path.join(USERS_DIR, username)
        if os.path.exists(user_folder):
            shutil.rmtree(user_folder)
            
        session.pop('username', None)
        return jsonify({'status': 'success', 'redirect': '/login'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Não autorizado'}), 401
    
    data = request.get_json()
    senha_atual = data.get('current_password', '').strip()
    nova_senha = data.get('new_password', '').strip()
    
    if not senha_atual or not nova_senha:
        return jsonify({'status': 'error', 'message': 'Preencha todos os campos.'}), 400
        
    username = session['username']
    users = carregar_utilizadores()
    
    if username in users and check_password_hash(users[username]['password'], senha_atual):
        users[username]['password'] = generate_password_hash(nova_senha)
        guardar_utilizadores(users)
        return jsonify({'status': 'success', 'message': 'Palavra-passe alterada com sucesso!'})
    
    return jsonify({'status': 'error', 'message': 'Palavra-passe atual incorreta.'}), 400

@app.route('/api/admin/create_user', methods=['POST'])
def api_admin_create_user():
    if session.get('username') != ADMIN_USER:
        return jsonify({'status': 'error', 'message': 'Acesso restrito ao administrador.'}), 403
        
    data = request.get_json()
    new_username = data.get('username', '').strip()
    temp_password = data.get('password', '').strip()
    
    if not new_username or not temp_password:
        return jsonify({'status': 'error', 'message': 'Preencha o nome de utilizador e a palavra-passe temporária.'}), 400
        
    users = carregar_utilizadores()
    if new_username in users:
        return jsonify({'status': 'error', 'message': 'Este utilizador já existe.'}), 400
        
    users[new_username] = {
        'password': generate_password_hash(temp_password),
        'idle_timeout': 1,
        'must_change_password': True,
        'approved': True,
        'active': True
    }
    guardar_utilizadores(users)
    obter_caminho_excel(new_username)
    
    return jsonify({'status': 'success', 'message': f'Utilizador "{new_username}" criado com sucesso!'})

@app.route('/api/admin/approve_user', methods=['POST'])
def api_admin_approve_user():
    if session.get('username') != ADMIN_USER:
        return jsonify({'status': 'error', 'message': 'Acesso restrito.'}), 403
        
    data = request.get_json()
    target_user = data.get('username', '').strip()
    
    users = carregar_utilizadores()
    if target_user in users:
        users[target_user]['approved'] = True
        guardar_utilizadores(users)
        return jsonify({'status': 'success', 'message': f'Utilizador "{target_user}" aprovado com sucesso!'})
    return jsonify({'status': 'error', 'message': 'Utilizador não encontrado.'}), 404

@app.route('/api/admin/reject_user', methods=['POST'])
def api_admin_reject_user():
    if session.get('username') != ADMIN_USER:
        return jsonify({'status': 'error', 'message': 'Acesso restrito.'}), 403
        
    data = request.get_json()
    target_user = data.get('username', '').strip()
    
    if target_user == ADMIN_USER:
        return jsonify({'status': 'error', 'message': 'Não pode rejeitar o administrador principal.'}), 400
        
    users = carregar_utilizadores()
    if target_user in users:
        del users[target_user]
        guardar_utilizadores(users)
        
        user_folder = os.path.join(USERS_DIR, target_user)
        if os.path.exists(user_folder):
            shutil.rmtree(user_folder)
            
        return jsonify({'status': 'success', 'message': f'Registo de "{target_user}" rejeitado e removido com sucesso!'})
    return jsonify({'status': 'error', 'message': 'Utilizador não encontrado.'}), 404

@app.route('/api/admin/toggle_active', methods=['POST'])
def api_admin_toggle_active():
    if session.get('username') != ADMIN_USER:
        return jsonify({'status': 'error', 'message': 'Acesso restrito.'}), 403
        
    data = request.get_json()
    target_user = data.get('username', '').strip()
    
    if target_user == ADMIN_USER:
        return jsonify({'status': 'error', 'message': 'Não pode inativar a conta de administrador principal.'}), 400
        
    users = carregar_utilizadores()
    if target_user in users:
        current_state = users[target_user].get('active', True)
        new_state = not current_state
        users[target_user]['active'] = new_state
        guardar_utilizadores(users)
        
        if not new_state:
            to_delete = [k for k, bridge in user_sessions.items() if bridge.session_username == target_user]
            for k in to_delete:
                user_sessions[k].close()
                del user_sessions[k]

        estado_str = "ativado" if new_state else "inativado"
        return jsonify({'status': 'success', 'message': f'Utilizador "{target_user}" {estado_str} com sucesso!'})
    return jsonify({'status': 'error', 'message': 'Utilizador não encontrado.'}), 404

@app.route('/api/admin/reset_user_password', methods=['POST'])
def api_admin_reset_user_password():
    if session.get('username') != ADMIN_USER:
        return jsonify({'status': 'error', 'message': 'Acesso restrito ao administrador.'}), 403
        
    data = request.get_json()
    target_user = data.get('username', '').strip()
    nova_senha = data.get('new_password', '').strip()
    
    if not target_user or not nova_senha:
        return jsonify({'status': 'error', 'message': 'Preencha todos os campos.'}), 400
        
    users = carregar_utilizadores()
    if target_user not in users:
        return jsonify({'status': 'error', 'message': 'Utilizador não encontrado.'}), 404
        
    users[target_user]['password'] = generate_password_hash(nova_senha)
    users[target_user]['must_change_password'] = True
    guardar_utilizadores(users)
    return jsonify({'status': 'success', 'message': f'Palavra-passe de "{target_user}" redefinida!'})

@app.route('/api/user/settings', methods=['GET', 'POST'])
def api_user_settings():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Não autorizado'}), 401
        
    username = session['username']
    users = carregar_utilizadores()
    
    if request.method == 'POST':
        data = request.get_json()
        timeout_min = int(data.get('idle_timeout', 1))
        if timeout_min < 1: timeout_min = 1
        
        if username in users:
            users[username]['idle_timeout'] = timeout_min
            guardar_utilizadores(users)
            return jsonify({'status': 'success', 'message': 'Tempo de ociosidade atualizado!'})
        return jsonify({'status': 'error', 'message': 'Utilizador não encontrado.'}), 404
        
    user_data = users.get(username, {'idle_timeout': 1})
    return jsonify({'status': 'success', 'idle_timeout': user_data.get('idle_timeout', 1)})

@app.route('/api/admin/users', methods=['GET'])
def api_admin_list_users():
    if session.get('username') != ADMIN_USER:
        return jsonify({'status': 'error', 'message': 'Acesso restrito ao administrador.'}), 403
        
    users = carregar_utilizadores()
    user_list = []
    
    for uname, udata in users.items():
        user_folder = os.path.join(USERS_DIR, uname)
        devices_count = 0
        last_modified = 'N/A'
        
        if os.path.exists(user_folder):
            excel_path = obter_caminho_excel(uname)
            if os.path.exists(excel_path):
                try:
                    df = pd.read_excel(excel_path)
                    devices_count = len(df)
                    timestamp = os.path.getmtime(excel_path)
                    import datetime
                    last_modified = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
                except:
                    pass

        user_list.append({
            'username': uname,
            'devices_count': devices_count,
            'last_modified': last_modified,
            'approved': udata.get('approved', True),
            'active': udata.get('active', True)
        })
        
    return jsonify({'status': 'success', 'users': user_list})

@app.route('/api/admin/delete_user', methods=['POST'])
def api_admin_delete_user():
    if session.get('username') != ADMIN_USER:
        return jsonify({'status': 'error', 'message': 'Acesso restrito ao administrador.'}), 403
        
    data = request.get_json()
    target_user = data.get('username', '').strip()
    
    if not target_user:
        return jsonify({'status': 'error', 'message': 'Utilizador não especificado.'}), 400
        
    if target_user == ADMIN_USER:
        return jsonify({'status': 'error', 'message': 'Não é permitido eliminar a conta de administrador.'}), 400
        
    users = carregar_utilizadores()
    if target_user not in users:
        return jsonify({'status': 'error', 'message': 'Utilizador não encontrado.'}), 404
        
    try:
        del users[target_user]
        guardar_utilizadores(users)
        
        user_folder = os.path.join(USERS_DIR, target_user)
        if os.path.exists(user_folder):
            shutil.rmtree(user_folder)
            
        return jsonify({'status': 'success', 'message': f'Conta de "{target_user}" eliminada com sucesso!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/active_sessions', methods=['GET'])
def api_admin_active_sessions():
    if session.get('username') != ADMIN_USER:
        return jsonify({'status': 'error', 'message': 'Acesso restrito ao administrador.'}), 403
        
    sessions_list = []
    current_time = time.time()
    
    for session_key, bridge in user_sessions.items():
        uname = bridge.session_username
        if uname and not any(s['username'] == uname for s in sessions_list):
            inactive_secs = int(current_time - bridge.last_activity)
            mins = inactive_secs // 60
            secs = inactive_secs % 60
            uptime_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
            
            sessions_list.append({
                'username': uname,
                'client_ip': bridge.host,
                'uptime': uptime_str
            })
            
    return jsonify({'status': 'success', 'sessions': sessions_list})

@app.route('/api/admin/force_logout', methods=['POST'])
def api_admin_force_logout():
    if session.get('username') != ADMIN_USER:
        return jsonify({'status': 'error', 'message': 'Acesso restrito ao administrador.'}), 403
        
    data = request.get_json()
    target_user = data.get('username', '').strip()
    
    if target_user == ADMIN_USER:
        return jsonify({'status': 'error', 'message': 'Não pode desconectar a sua própria conta de administrador.'}), 400
        
    to_delete = [k for k, bridge in user_sessions.items() if bridge.session_username == target_user]
    for k in to_delete:
        user_sessions[k].close()
        del user_sessions[k]
        
    return jsonify({'status': 'success', 'message': f'Utilizador "{target_user}" foi desconectado com sucesso!'})

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    devices_tree = carregar_arvore_devices(username)
    is_admin = (username == ADMIN_USER)
    return render_template('index.html', tree=devices_tree, username=username, is_admin=is_admin)

@app.route('/api/devices', methods=['GET'])
def api_get_devices():
    if 'username' not in session:
        return jsonify({'devices': []}), 401
        
    excel_path = obter_caminho_excel(session['username'])
    if not os.path.exists(excel_path):
        return jsonify({'devices': []})
    try:
        df = pd.read_excel(excel_path).fillna('')
        devices = []
        for _, row in df.iterrows():
            devices.append({
                'categoria': str(row.get('categoria', 'Geral')).strip(),
                'nome': str(row.get('nome', '')).strip(),
                'ip': str(row.get('ip', '')).strip(),
                'porta': int(row.get('porta', 22)) if str(row.get('porta', 22)).isdigit() else 22,
                'usuario': str(row.get('usuario', '')).strip()
            })
        return jsonify({'devices': devices})
    except Exception as e:
        return jsonify({'devices': [], 'error': str(e)}), 500

@app.route('/api/devices/save', methods=['POST'])
def api_save_devices():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Não autorizado'}), 401
        
    try:
        data = request.get_json()
        devices = data.get('devices', [])
        excel_path = obter_caminho_excel(session['username'])
        
        rows = []
        for d in devices:
            rows.append({
                'categoria': d.get('categoria', 'Geral'),
                'nome': d.get('nome', ''),
                'ip': d.get('ip', ''),
                'porta': d.get('porta', 22),
                'usuario': d.get('usuario', '')
            })
        
        df = pd.DataFrame(rows)
        df.to_excel(excel_path, index=False)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/devices/export', methods=['GET'])
def api_export_devices():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Não autorizado'}), 401
        
    username = session['username']
    excel_path = obter_caminho_excel(username)
    if not os.path.exists(excel_path):
        return jsonify({'status': 'error', 'message': 'Nenhum dispositivo encontrado.'}), 404
        
    return send_file(excel_path, as_attachment=True, download_name=f'devices_{username}.xlsx')

@app.route('/api/devices/import', methods=['POST'])
def api_import_devices():
    if 'username' not in session:
        return jsonify({'status': 'error', 'message': 'Não autorizado'}), 401
        
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Nenhum ficheiro enviado.'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'Ficheiro inválido.'}), 400
        
    if file and file.filename.endswith('.xlsx'):
        try:
            excel_path = obter_caminho_excel(session['username'])
            file.save(excel_path)
            return jsonify({'status': 'success', 'message': 'Dispositivos importados com sucesso!'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
            
    return jsonify({'status': 'error', 'message': 'Apenas ficheiros .xlsx são permitidos.'}), 400

class SSHBridge:
    def __init__(self, sid, tab_id, host, user, password, port=22, session_username=None):
        self.sid = sid
        self.tab_id = tab_id
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.session_username = session_username
        self.client = None
        self.chan = None
        self.running = False
        self.last_activity = time.time()

    def get_idle_timeout(self):
        if self.session_username:
            users = carregar_utilizadores()
            u_data = users.get(self.session_username)
            if isinstance(u_data, dict) and 'idle_timeout' in u_data:
                return int(u_data['idle_timeout']) * 60
        return 60

    def connect(self):
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                timeout=10,
                look_for_keys=False,
                allow_agent=False
            )
            self.chan = self.client.invoke_shell(term='xterm', width=120, height=30)
            self.running = True
            self.password = None
            self.last_activity = time.time()
            
            threading.Thread(target=self._read_from_ssh, daemon=True).start()
            threading.Thread(target=self._check_idle_timeout, daemon=True).start()
            return True
        except Exception as e:
            self.password = None
            return str(e)

    def _read_from_ssh(self):
        while self.running and self.chan and not self.chan.closed:
            try:
                if self.chan.recv_ready():
                    data = self.chan.recv(4096)
                    if not data:
                        break
                    socketio.emit('ssh_output', {
                        'tab_id': self.tab_id,
                        'data': data.decode('utf-8', errors='ignore')
                    }, room=self.sid)
                else:
                    eventlet.sleep(0.02)
            except Exception:
                break
        self.close()

    def _check_idle_timeout(self):
        while self.running:
            eventlet.sleep(5)
            if not self.running:
                break
            
            timeout_limit = self.get_idle_timeout()
            idle_duration = time.time() - self.last_activity
            
            if idle_duration > timeout_limit:
                socketio.emit('ssh_output', {
                    'tab_id': self.tab_id,
                    'data': f'\r\n\x1b[31m> [AVISO DO PORTAL]: Sessão encerrada automaticamente por ociosidade (Sem atividade há {int(idle_duration // 60)} min).\x1b[0m\r\n'
                }, room=self.sid)
                self.close()
                break

    def record_activity(self):
        self.last_activity = time.time()

    def write(self, data):
        if self.chan and not self.chan.closed:
            self.record_activity()
            self.chan.send(data)

    def resize(self, cols, rows):
        if self.chan and not self.chan.closed:
            self.record_activity()
            self.chan.resize_pty(width=cols, height=rows)

    def close(self):
        self.running = False
        if self.chan:
            try: self.chan.close()
            except: pass
        if self.client:
            try: self.client.close()
            except: pass
        socketio.emit('ssh_closed', {
            'tab_id': self.tab_id,
            'message': 'Conexão encerrada por ociosidade ou comando manual.'
        }, room=self.sid)

user_sessions = {}

@socketio.on('start_ssh')
def handle_start_ssh(data):
    if 'username' not in session:
        return
    sid = request.sid
    tab_id = data.get('tab_id')
    host = data.get('host')
    user = data.get('username')
    password = data.get('password')
    port = int(data.get('port', 22))
    current_username = session.get('username')

    session_key = f"{sid}_{tab_id}"
    bridge = SSHBridge(sid, tab_id, host, user, password, port, session_username=current_username)
    res = bridge.connect()

    if res is True:
        user_sessions[session_key] = bridge
        emit('ssh_connected', {'status': 'success', 'tab_id': tab_id, 'host': host})
    else:
        emit('ssh_connected', {'status': 'error', 'tab_id': tab_id, 'message': str(res)})

@socketio.on('ssh_input')
def handle_ssh_input(data):
    sid = request.sid
    tab_id = data.get('tab_id')
    session_key = f"{sid}_{tab_id}"
    if session_key in user_sessions:
        user_sessions[session_key].write(data.get('data', ''))

@socketio.on('resize')
def handle_resize(data):
    sid = request.sid
    tab_id = data.get('tab_id')
    session_key = f"{sid}_{tab_id}"
    if session_key in user_sessions:
        user_sessions[session_key].resize(data.get('cols', 80), data.get('rows', 24))

@socketio.on('close_tab_ssh')
def handle_close_tab_ssh(data):
    sid = request.sid
    tab_id = data.get('tab_id')
    session_key = f"{sid}_{tab_id}"
    if session_key in user_sessions:
        user_sessions[session_key].close()
        del user_sessions[session_key]

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    to_delete = [k for k in user_sessions.keys() if k.startswith(f"{sid}_")]
    for k in to_delete:
        user_sessions[k].close()
        del user_sessions[k]

if __name__ == '__main__':
    init_users_file()  # Garante a criação do ficheiro users.json com o admin no arranque
    socketio.run(app, host='0.0.0.0', port=8513, debug=True)
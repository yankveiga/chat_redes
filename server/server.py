import socket
import threading
import json
import os 

# módulos que a gente criou
from .database import Database
from .user import UserManager
from .group import GroupManager

class ChatServer:
    def __init__(self, host='0.0.0.0', port=12345):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # dicionários pra controlar quem tá online e conversando
        self.clients = {}         # socket -> nome do user
        self.users_online = {}    # nome do user -> socket
        self.chat_context = {}    # nome do user -> {tipo: user/grupo, alvo: nome}
        
        # Conexão com o Banco de Dados (PostgreSQL/Render)
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise ValueError("[ERRO] Variável de ambiente DATABASE_URL não definida!")
            
        self.db = Database(db_url) 

        self.user_manager = UserManager(self.db)
        self.group_manager = GroupManager(self.db)
        print("[Servidor] Banco de dados e gerenciadores prontos.")

    def start(self):
        # liga o server e fica esperando conexão
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"[Servidor] Escutando em {self.host}:{self.port}")

        while True:
            # cada conexão nova vira uma thread
            client_socket, addr = self.server_socket.accept()
            print(f"[Nova Conexão] Conexão de {addr} estabelecida.")
            
            thread = threading.Thread(target=self.handle_client, args=(client_socket, addr))
            thread.daemon = True
            thread.start()

    def send_json(self, sock, data):
        # função helper pra mandar mensagem em JSON
        try:
            sock.send(json.dumps(data).encode('utf-8'))
        except (ConnectionResetError, BrokenPipeError):
            pass 

    def handle_client(self, client_socket, addr):
        username = None 
        try:
            # loop de login/registro
            while True:
                auth_data_raw = client_socket.recv(1024).decode('utf-8')
                if not auth_data_raw:
                    print(f"[{addr}] Cliente desconectou antes de autenticar.")
                    return
                
                auth_data = json.loads(auth_data_raw)
                user = auth_data.get('username')
                pwd = auth_data.get('password')
                command = auth_data.get('command')

                if command == 'register':
                    if user and pwd and self.user_manager.register(user, pwd):
                        self.send_json(client_socket, {"status": "success", "message": "Cadastro realizado com sucesso! Faça o login."})
                    else:
                        self.send_json(client_socket, {"status": "error", "message": "Nome de usuário já existe ou dados inválidos."})
                
                elif command == 'login':
                    if user and pwd and self.user_manager.authenticate(user, pwd):
                        if user in self.users_online:
                            self.send_json(client_socket, {"status": "error", "message": "Este usuário já está logado."})
                            continue 
                        
                        username = user
                        self.clients[client_socket] = username
                        self.users_online[username] = client_socket
                        
                        self.send_json(client_socket, {"status": "success", "message": f"Login realizado com sucesso! Bem-vindo, {username}."})
                        print(f"[Autenticação] Usuário '{username}' logado de {addr}.")
                        
                        break  # sai do loop de autenticação
                    else:
                        self.send_json(client_socket, {"status": "error", "message": "Nome de usuário ou senha inválidos."})
                else:
                    self.send_json(client_socket, {"status": "error", "message": "Comando de autenticação inválido."})

            # pós-login: entrega mensagens pendentes e entra no loop de comandos
            # 1. pega mensagens offline e entrega ao user
            offline_msgs = self.db.get_and_delete_messages_for(username)
            if offline_msgs:
                self.send_json(client_socket, {"status": "info", "message": "Você tem novas mensagens!"})
                for sender, msg_text in offline_msgs:
                    self.send_json(client_socket, {"type": "chat_message", "sender": sender, "message": msg_text})
            
            # 2. Loop principal de comandos (substitui o loop vazio)
            while True:
                message_raw = client_socket.recv(4096).decode('utf-8')
                if not message_raw:
                    break # Cliente desconectou

                data = json.loads(message_raw)
                command = data.get('command')

                if command == 'list_all':
                    users = self.db.get_all_users()
                    # pega só os grupos que este usuário participa
                    groups = self.db.get_groups_for_user(username)
                    
                    user_list_str = "\n".join(f"- {u} {'(online)' if u in self.users_online else '(offline)'}" for u in users)
                    group_list_str = "\n".join(f"- {g}" for g in groups) if groups else "Você não está em nenhum grupo."
                    
                    full_message = f"--- USUÁRIOS ---\n{user_list_str}\n\n--- MEUS GRUPOS ---\n{group_list_str}"
                    self.send_json(client_socket, {"status": "info", "message": full_message})

                elif command == 'send_message':
                    context = self.chat_context.get(username)
                    if not context:
                        self.send_json(client_socket, {"status": "error", "message": "Você não está em uma conversa. Use o menu para selecionar um chat."})
                        continue
                    
                    target_type = context['type']
                    target_name = context['target']
                    message_text = data['message']
                    
                    if target_type == 'user':
                        # Envia DM
                        if target_name in self.users_online:
                            # Se estiver online, envia direto
                            target_socket = self.users_online[target_name]
                            self.send_json(target_socket, {"type": "chat_message", "sender": username, "message": message_text})
                        else:
                            # Se estiver offline, salva no banco
                            self.db.save_message(username, target_name, message_text)
                            self.send_json(client_socket, {"status": "info", "message": f"'{target_name}' está offline. A mensagem será entregue quando ele(a) se conectar."})
                    
                    elif target_type == 'group':
                        # Envia para Grupo
                        members = self.group_manager.get_members(target_name)
                        for member in members:
                            if member != username and member in self.users_online:
                                # Envia para todos os membros online (menos ele mesmo)
                                target_socket = self.users_online[member]
                                self.send_json(target_socket, {"type": "group_message", "group": target_name, "sender": username, "message": message_text})
                
                elif command == 'select_chat':
                    target_user = data.get('target_user')
                    target_group = data.get('target_group')

                    if target_user:
                        if self.db.user_exists(target_user):
                            # Define o "contexto" do chat para DM
                            self.chat_context[username] = {'type': 'user', 'target': target_user}
                            self.send_json(client_socket, {"status": "success", "message": f"Conversa privada com '{target_user}' iniciada. Use /menu para sair."})
                        else:
                            self.send_json(client_socket, {"status": "error", "message": f"Usuário '{target_user}' não encontrado."})
                    
                    elif target_group:
                        if self.db.group_exists(target_group):
                            # só permite entrar se o user for membro do grupo
                            if username in self.group_manager.get_members(target_group):
                                self.chat_context[username] = {'type': 'group', 'target': target_group}
                                self.send_json(client_socket, {"status": "success", "message": f"Conversa no grupo '{target_group}' iniciada. Use /menu para sair."})
                            else:
                                self.send_json(client_socket, {"status": "error", "message": f"Você não é membro do grupo '{target_group}'."})
                        else:
                            self.send_json(client_socket, {"status": "error", "message": f"Grupo '{target_group}' não encontrado."})
                
                elif command == 'create_group':
                    group_name = data.get('group_name')
                    if group_name:
                        # cria o grupo e adiciona o criador como membro
                        if self.group_manager.create_group(group_name, username):
                            self.send_json(client_socket, {"status": "success", "message": f"Grupo '{group_name}' criado! Você foi adicionado."})
                        else:
                            self.send_json(client_socket, {"status": "error", "message": f"Grupo '{group_name}' já existe."})
                    else:
                        self.send_json(client_socket, {"status": "error", "message": "Nome do grupo não fornecido."})

                elif command == 'add_member_to_group':
                    group_name = data.get('group_name')
                    user_to_add = data.get('user_to_add')

                    if not group_name or not user_to_add:
                        self.send_json(client_socket, {"status": "error", "message": "Nome do grupo e do usuário são obrigatórios."})
                    elif not self.db.group_exists(group_name):
                        self.send_json(client_socket, {"status": "error", "message": f"O grupo '{group_name}' não existe."})
                    elif not self.db.user_exists(user_to_add):
                        self.send_json(client_socket, {"status": "error", "message": f"O usuário '{user_to_add}' não existe."})
                    elif username not in self.group_manager.get_members(group_name):
                        # verifica se quem envia o pedido é membro do grupo
                        self.send_json(client_socket, {"status": "error", "message": "Você não é membro deste grupo e não pode adicionar novos usuários."})
                    else:
                        self.group_manager.add_member(group_name, user_to_add)
                        self.send_json(client_socket, {"status": "success", "message": f"Usuário '{user_to_add}' adicionado ao grupo '{group_name}'."})
                
                elif command == 'leave_chat':
                    # limpa o contexto de chat (volta ao menu)
                    if username in self.chat_context:
                        del self.chat_context[username]
                    # o cliente já mostra "Voltando ao menu...", então não é preciso responder

            # fim do loop principal de comandos

        except (ConnectionResetError, json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"[Aviso] Conexão com '{username or addr}' foi perdida. Causa: {e}")
        except Exception as e:
            print(f"[ERRO] Ocorreu um erro com o cliente '{username or addr}': {e}")
        
        finally:
            # limpa tudo quando o user sai
            if username:
                print(f"[Desconexão] Usuário '{username}' desconectado.")
                if username in self.users_online: del self.users_online[username]
                if username in self.chat_context: del self.chat_context[username]
            
            if client_socket in self.clients: del self.clients[client_socket]
            
            client_socket.close()
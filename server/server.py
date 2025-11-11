import socket
import threading
import json

# módulos que a gente criou
from database import Database
from user import UserManager
from group import GroupManager

class ChatServer:
    # prepara o servidor com o IP e a porta local
    def __init__(self, host='0.0.0.0', port=12345):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # dicionários pra controlar quem tá online e conversando
        self.clients = {}         # socket -> nome do user
        self.users_online = {}    # nome do user -> socket
        self.chat_context = {}    # nome do user -> {tipo: user/grupo, alvo: nome}
        
        # inicializa o banco de dados (o arquivo chat.db)
        self.db = Database() 

        # passa o banco pros "ajudantes" de user e grupo
        self.user_manager = UserManager(self.db)
        self.group_manager = GroupManager(self.db)
        print("[Servidor] Banco de dados (SQLite) e gerenciadores prontos.")

    def start(self):
        # amarra o server no IP/porta e fica de ouvido
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"[Servidor] Escutando em {self.host}:{self.port}")

        # loop infinito pra aceitar conexões
        while True:
            # trava aqui até alguém conectar
            client_socket, addr = self.server_socket.accept()
            print(f"[Nova Conexão] Conexão de {addr} estabelecida.")
            
            # cria uma thread nova só pra cuidar desse cliente
            # e volta pro loop pra aceitar mais gente
            thread = threading.Thread(target=self.handle_client, args=(client_socket, addr))
            thread.daemon = True # morre se o server principal fechar
            thread.start()

    def send_json(self, sock, data):
        # função rápida pra transformar dict em JSON e mandar
        try:
            sock.send(json.dumps(data).encode('utf-8'))
        except (ConnectionResetError, BrokenPipeError):
            # se o cliente já caiu, só ignora
            pass 

    def handle_client(self, client_socket, addr):
        # essa função roda na thread de cada cliente
        username = None # começa deslogado
        try:
            # --- LOOP DE LOGIN/REGISTRO ---
            # o cliente fica preso aqui até logar
            while True:
                # espera receber o JSON de auth (1kb tá de boa)
                auth_data_raw = client_socket.recv(1024).decode('utf-8')
                # se não vier nada, o cara fechou a janela
                if not auth_data_raw:
                    print(f"[{addr}] Cliente desconectou antes de autenticar.")
                    return # mata a thread
                
                auth_data = json.loads(auth_data_raw)
                user = auth_data.get('username')
                pwd = auth_data.get('password')
                command = auth_data.get('command')

                # se o comando for 'register'
                if command == 'register':
                    # tenta registrar o usuário no banco
                    if user and pwd and self.user_manager.register(user, pwd):
                        self.send_json(client_socket, {"status": "success", "message": "Cadastro realizado com sucesso! Faça o login."})
                    else:
                        # ou o user já existe, ou veio dado zoado
                        self.send_json(client_socket, {"status": "error", "message": "Nome de usuário já existe ou dados inválidos."})
                
                # se o comando for 'login'
                elif command == 'login':
                    # bate a senha com o hash salvo no banco
                    if user and pwd and self.user_manager.authenticate(user, pwd):
                        
                        # checa se ele já não tá logado em outro terminal
                        if user in self.users_online:
                            self.send_json(client_socket, {"status": "error", "message": "Este usuário já está logado."})
                            continue # volta pro começo do loop
                        
                        # --- LOGIN OK ---
                        username = user # agora sim, ele tem nome
                        self.clients[client_socket] = username # guarda no dict 1
                        self.users_online[username] = client_socket # guarda no dict 2
                        
                        self.send_json(client_socket, {"status": "success", "message": f"Login realizado com sucesso! Bem-vindo, {username}."})
                        print(f"[Autenticação] Usuário '{username}' logado de {addr}.")
                        
                        break  # QUEBRA o loop de auth e vai pro menu
                    else:
                        self.send_json(client_socket, {"status": "error", "message": "Nome de usuário ou senha inválidos."})
                else:
                    self.send_json(client_socket, {"status": "error", "message": "Comando de autenticação inválido."})

            # --- FIM DO LOOP DE AUTH ---
            # (se chegou aqui, tá logado)

            # 1. busca no banco se tem msg offline pra ele
            offline_msgs = self.db.get_and_delete_messages_for(username)
            if offline_msgs:
                # avisa que tem coisa nova
                self.send_json(client_socket, {"status": "info", "message": "Você tem novas mensagens!"})
                # manda as mensagens uma por uma
                for sender, msg_text in offline_msgs:
                    self.send_json(client_socket, {"type": "chat_message", "sender": sender, "message": msg_text})
            
            # --- LOOP DE COMANDOS (MENU) ---
            # agora fica aqui ouvindo os comandos do menu
            while True:
                message_raw = client_socket.recv(4096).decode('utf-8')
                # se não vier nada, o cliente fechou o app
                if not message_raw:
                    break # vai pro 'finally' limpar tudo

                data = json.loads(message_raw)
                command = data.get('command')

                # comando: 'list_all' (ver users e grupos)
                if command == 'list_all':
                    users = self.db.get_all_users()
                    # puxa só os grupos que o *esse* user tá
                    groups = self.db.get_groups_for_user(username)
                    
                    # monta a string de users (vendo quem tá online)
                    user_list_str = "\n".join(f"- {u} {'(online)' if u in self.users_online else '(offline)'}" for u in users)
                    # monta a string de grupos
                    group_list_str = "\n".join(f"- {g}" for g in groups) if groups else "Você não está em nenhum grupo."
                    
                    # manda o textão pro cliente
                    full_message = f"--- USUÁRIOS ---\n{user_list_str}\n\n--- MEUS GRUPOS ---\n{group_list_str}"
                    self.send_json(client_socket, {"status": "info", "message": full_message})

                # comando: 'send_message' (mandar DM ou msg em grupo)
                elif command == 'send_message':
                    # vê com quem o user tá falando (o "contexto")
                    context = self.chat_context.get(username)
                    
                    # se ele não selecionou ninguém, tá no menu
                    if not context:
                        self.send_json(client_socket, {"status": "error", "message": "Você não está em uma conversa. Use o menu para selecionar um chat."})
                        continue
                    
                    target_type = context['type'] # 'user' ou 'group'
                    target_name = context['target'] # nome do alvo
                    message_text = data['message']
                    
                    # se o alvo for 'user' (DM)
                    if target_type == 'user':
                        # o cara tá online?
                        if target_name in self.users_online:
                            # tá. acha o socket dele
                            target_socket = self.users_online[target_name]
                            # e manda a msg direto
                            self.send_json(target_socket, {"type": "chat_message", "sender": username, "message": message_text})
                        else:
                            # tá offline. salva no banco
                            self.db.save_message(username, target_name, message_text)
                            self.send_json(client_socket, {"status": "info", "message": f"'{target_name}' está offline. A mensagem será entregue quando ele(a) se conectar."})
                    
                    # se o alvo for 'group'
                    elif target_type == 'group':
                        members = self.group_manager.get_members(target_name)
                        # manda pra todo mundo do grupo
                        for member in members:
                            # que esteja online E não seja o próprio remetente
                            if member != username and member in self.users_online:
                                target_socket = self.users_online[member]
                                self.send_json(target_socket, {"type": "group_message", "group": target_name, "sender": username, "message": message_text})
                
                # comando: 'select_chat' (entrar numa DM ou grupo)
                elif command == 'select_chat':
                    target_user = data.get('target_user')
                    target_group = data.get('target_group')

                    # se for DM
                    if target_user:
                        if self.db.user_exists(target_user):
                            # define o "contexto" dele pra DM
                            self.chat_context[username] = {'type': 'user', 'target': target_user}
                            self.send_json(client_socket, {"status": "success", "message": f"Conversa privada com '{target_user}' iniciada. Use /menu para sair."})
                        else:
                            self.send_json(client_socket, {"status": "error", "message": f"Usuário '{target_user}' não encontrado."})
                    
                    # se for grupo
                    elif target_group:
                        if self.db.group_exists(target_group):
                            # checa se o user é membro do grupo
                            if username in self.group_manager.get_members(target_group):
                                # define o "contexto" dele pro grupo
                                self.chat_context[username] = {'type': 'group', 'target': target_group}
                                self.send_json(client_socket, {"status": "success", "message": f"Conversa no grupo '{target_group}' iniciada. Use /menu para sair."})
                            else:
                                # se não for membro, barra
                                self.send_json(client_socket, {"status": "error", "message": f"Você não é membro do grupo '{target_group}'."})
                        else:
                            self.send_json(client_socket, {"status": "error", "message": f"Grupo '{target_group}' não encontrado."})
                
                # comando: 'create_group'
                elif command == 'create_group':
                    group_name = data.get('group_name')
                    if group_name:
                        # group_manager já bota o criador no grupo
                        if self.group_manager.create_group(group_name, username):
                             self.send_json(client_socket, {"status": "success", "message": f"Grupo '{group_name}' criado! Você foi adicionado."})
                        else:
                             self.send_json(client_socket, {"status": "error", "message": f"Grupo '{group_name}' já existe."})
                    else:
                        self.send_json(client_socket, {"status": "error", "message": "Nome do grupo não fornecido."})

                # comando: 'add_member_to_group'
                elif command == 'add_member_to_group':
                    group_name = data.get('group_name')
                    user_to_add = data.get('user_to_add')

                    # checagens de segurança
                    if not group_name or not user_to_add:
                        self.send_json(client_socket, {"status": "error", "message": "Nome do grupo e do usuário são obrigatórios."})
                    elif not self.db.group_exists(group_name):
                        self.send_json(client_socket, {"status": "error", "message": f"O grupo '{group_name}' não existe."})
                    elif not self.db.user_exists(user_to_add):
                        self.send_json(client_socket, {"status": "error", "message": f"O usuário '{user_to_add}' não existe."})
                    # só pode adicionar se for membro
                    elif username not in self.group_manager.get_members(group_name):
                        self.send_json(client_socket, {"status": "error", "message": "Você não é membro deste grupo e não pode adicionar novos usuários."})
                    else:
                        # se passou, adiciona
                        self.group_manager.add_member(group_name, user_to_add)
                        self.send_json(client_socket, {"status": "success", "message": f"Usuário '{user_to_add}' adicionado ao grupo '{group_name}'."})
                
                # comando: 'leave_chat' (o /menu do cliente)
                elif command == 'leave_chat':
                    # limpa o contexto do usuário
                    if username in self.chat_context:
                        del self.chat_context[username]

        # se der pau em qualquer lugar (JSON mal feito, cliente caiu, etc.)
        except (ConnectionResetError, json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"[Aviso] Conexão com '{username or addr}' foi perdida. Causa: {e}")
        except Exception as e:
            print(f"[ERRO] Ocorreu um erro com o cliente '{username or addr}': {e}")
        
        # 'finally' roda sempre, dando erro ou não
        finally:
            # faz a "faxina" do usuário que saiu
            if username:
                print(f"[Desconexão] Usuário '{username}' desconectado.")
                # tira ele dos dicts de "online"
                if username in self.users_online: del self.users_online[username]
                if username in self.chat_context: del self.chat_context[username]
            
            if client_socket in self.clients: del self.clients[client_socket]
            
            client_socket.close()
            # a thread morre aqui

import socket
import threading
import json
import os 

# Flag para controlar as threads
running = True 

#Boca do cliente
def send_json(sock, data):
    # empacota e manda um dict em JSON pro servidor
    global running
    try:
        sock.send(json.dumps(data).encode('utf-8'))
    except (ConnectionResetError, BrokenPipeError):
        if running:
            print("\n[ERRO] Não foi possível enviar dados. A conexão foi perdida.")
        running = False

# orelha do cliente — thread que recebe mensagens do servidor
def receive_messages(sock):
    # roda numa thread só pra ficar ouvindo o servidor
    global running
    while running:
        try:
            data_raw = sock.recv(4096)
            if not data_raw:
                if running:
                    print("\n[INFO] Conexão perdida com o servidor.")
                break
            
            # parseia o JSON e formata a mensagem conforme o tipo
            response = json.loads(data_raw.decode('utf-8'))
            
            # mostra a mensagem de acordo com o tipo (privada/grupo/status)
            if response.get('type') == 'chat_message':
                print(f"\n[DM de {response['sender']}]: {response['message']}")
            elif response.get('type') == 'group_message':
                print(f"\n[{response['group']} | {response['sender']}]: {response['message']}")
            # Mensagens de status (erro, sucesso, info)
            else:
                status = response.get('status', 'info')
                message = response.get('message', '')
                
                if status == 'error':
                    print(f"\n[ERRO] {message}")
                elif status == 'success':
                    print(f"\n[SUCESSO] {message}")
                else:
                    print(f"\n[INFO] {message}")
            # fim do parser de mensagens

        except (ConnectionResetError, json.JSONDecodeError):
            if running:
                print("\n[ERRO] Erro de comunicação com o servidor.")
            break
        except Exception as e:
            if running and e:
                print(f"\n[ERRO] Ocorreu um erro inesperado: {e}")
            break

    print("\nSessão de recebimento encerrada.")
    running = False

# funções do menu e modo chat

def start_chat_mode(sock):
    """Entra no modo de conversa (DM ou Grupo)."""
    print("\nVocê está no modo de conversa.")
    print("Digite '/menu' para voltar ao menu principal.")
    while running:
        msg = input()
        if not running:
             break
        
        # Comando para sair do chat e voltar ao menu
        if msg == '/menu':
            send_json(sock, {"command": "leave_chat"})
            print("Voltando ao menu...")
            break
        
        # Envia a mensagem para o contexto (DM/Grupo) atual
        if msg:
            send_json(sock, {"command": "send_message", "message": msg})

def main_menu(sock):
    """Mostra o menu principal e processa os comandos."""
    global running
    while running:
        print("\n------- MENU PRINCIPAL -------")
        print("1. Listar usuários e meus grupos")
        print("2. Iniciar uma conversa DM")
        print("3. Iniciar uma conversa em grupo")
        print("4. Criar um novo grupo")
        print("5. Adicionar membro a um grupo")
        print("6. Sair")

        choice = input("O que gostaria de fazer?\nR: ")

        if not running:
            break

        if choice == '1':
            send_json(sock, {"command": "list_all"})
        
        elif choice == '2':
            target_user = input("\nCom quem deseja conversar?\nR: ")
            if target_user:
                # Avisa o servidor que queremos falar com 'target_user'
                send_json(sock, {"command": "select_chat", "target_user": target_user})
                start_chat_mode(sock) # Entra no loop de chat

        elif choice == '3':
            target_group = input("\nQual o grupo que você deseja mandar mensagem?\nR: ")
            if target_group:
                # Avisa o servidor que queremos falar no 'target_group'
                send_json(sock, {"command": "select_chat", "target_group": target_group})
                start_chat_mode(sock) # Entra no loop de chat

        elif choice == '4':
            group_name = input("\nQual o nome do novo grupo?\nR: ")
            if group_name:
                send_json(sock, {"command": "create_group", "group_name": group_name})
        
        elif choice == '5':
            group_name = input("\nQual o grupo?\nR: ")
            user_to_add = input(f"\nQual usuário você quer adicionar ao grupo '{group_name}'?\nR: ")
            if group_name and user_to_add:
                send_json(sock, {
                    "command": "add_member_to_group",
                    "group_name": group_name,
                    "user_to_add": user_to_add
                })

        elif choice == '6':
            running = False
            sock.close()
            print("Desconectando...")
            break
        else:
            print("[ERRO] Opção inválida.")

# fim das funções de menu/chat


#Função principal que liga o client ao Host
def main():
    global running
    # no Render a URL pública deve ser usada; pra testes locais, localhost tá de boa
    host = '0.tcp.sa.ngrok.io'
    port = 19918

    # cria o socket do cliente
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # tenta conectar no servidor
    try:
        client_socket.connect((host, port))
        print(f"Conectado ao servidor em {host}:{port}")
    except ConnectionRefusedError:
        print(f"[ERRO] Não foi possível conectar ao servidor em {host}:{port}.")
        print("Verifique se o servidor está rodando e se o endereço/porta estão corretos.")
        return

    # loop de autenticação: registra ou faz login
    # (autenticação feita acima neste bloco)
    while True: 
        print("\n--- TELA INICIAL ---")
        print("1. Login")
        print("2. Cadastro")
        action = input("O que gostaria de fazer? (1 ou 2): ")

        username = input("Nome de usuário: ")
        password = input("Senha: ")

        if action == '1':
            auth_command = 'login'
        elif action == '2':
            auth_command = 'register'
        else:
            print("[ERRO] Ação inválida. Tente '1' ou 2'.")
            continue

        send_json(client_socket, {
            "command": auth_command,
            "username": username,
            "password": password
        })

        try:
            response_raw = client_socket.recv(1024)
            if not response_raw:
                print("[ERRO] Servidor encerrou a conexão inesperadamente.")
                return

            response = json.loads(response_raw.decode('utf-8'))
            print(f"\n[{response['status'].upper()}] {response['message']}")

            if response['status'] == 'success' and auth_command == 'login':
                break

        except (json.JSONDecodeError, ConnectionResetError):
             print("[ERRO] Falha na comunicação durante a autenticação.")
             return

    # pós-auth: inicia thread de recepção e mostra menu
    # inicializa a "orelha" que fica recebendo mensagens
    receiver_thread = threading.Thread(target=receive_messages, args=(client_socket,))
    receiver_thread.daemon = True # Se o programa principal terminar ele encerra a thread
    receiver_thread.start() # Inicia a "Orelha"
    
    #Enquanto a orelha escuta, o programa principal (Boca) mostra o menu 
    try:
        main_menu(client_socket)
    except KeyboardInterrupt:
        print("\nSaindo (Ctrl+C)...")

    # Finalização
    running = False
    client_socket.close()
    receiver_thread.join(timeout=1) # Espera a thread do "Ouvido" fechar
    print("Programa cliente encerrado.")
    os._exit(0) # Força o encerramento de todas as threads

if __name__ == "__main__":
    main()
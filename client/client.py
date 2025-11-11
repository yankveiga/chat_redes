import socket
import threading
import json
import os

# Variável global para controlar se o app está rodando
running = True

# Envia um dicionário como JSON para o servidor
# Se der erro, avisa e encerra o programa
def send_json(sock, data):
    global running
    try:
        sock.send(json.dumps(data).encode('utf-8'))
    except (ConnectionResetError, BrokenPipeError):
        if running:
            print("\n[CHATINHO | XABLAU] Opa, deu ruim! Não rolou enviar, conexão sumiu no rolê.")
        running = False

# Fica ouvindo mensagens do servidor e mostra na tela
# Roda em uma thread separada
def receive_messages(sock):
    global running
    while running:
        try:
            data_raw = sock.recv(4096)
            if not data_raw:
                if running:
                    print("\n[CHATINHO | INFO] Ih, o servidor foi tomar um café e te deixou falando sozinho.")
                break

            response = json.loads(data_raw.decode('utf-8'))

            # Se for mensagem privada
            if response.get('type') == 'chat_message':
                print(f"\n[CHATINHO | Papinho a Dois de {response['sender']}]: {response['message']}")
            # Se for mensagem de grupo
            elif response.get('type') == 'group_message':
                print(f"\n[CHATINHO | {response['group']} | {response['sender']}]: {response['message']}")
            # Se for outra resposta (erro, sucesso, info)
            else:
                status = response.get('status', 'info')
                message = response.get('message', '')

                if status == 'error':
                    print(f"\n[CHATINHO | XABLAU] {message} - OPS!")
                elif status == 'success':
                    print(f"\n[CHATINHO | SUCESSO] {message} - UHUL!)")
                else:
                    print(f"\n[CHATINHO | INFO] {message}")

        except (ConnectionResetError, json.JSONDecodeError):
            if running:
                print("\n[CHATINHO | XABLAU] O servidor bugou, chama o suporte!")
            break
        except Exception as e:
            if running and e:
                print(f"\n[CHATINHO | XABLAU] Erro inesperado: {e} (bug sinistro!)")
            break

    print("\n[CHATINHO] Ouvinte cansou, sessão encerrada!")
    running = False

# Modo de conversa (papinho a dois ou grupo)
# Envia mensagens até o usuário digitar /menu
# Sai do chat e volta pro menu
def start_chat_mode(sock, chat_type=None, chat_name=None):
    if chat_type == 'group':
        print(f"\n[CHATINHO] Você entrou no grupão '{chat_name}'. Solta o papo aí!")
        print("[CHATINHO] Digite '/menu' se cansar do papo e quiser voltar pro menu.")
    else:
        print("\n[CHATINHO] Você entrou no modo Papinho a Dois. Manda ver!")
        print("[CHATINHO] Digite '/menu' se cansar do papo e quiser voltar pro menu.")
    while running:
        msg = input()
        if not running:
             break

        if msg == '/menu':
            send_json(sock, {"command": "leave_chat"})
            print("[CHATINHO] Voltando pro menu, sem ressentimentos...")
            break

        if msg:
            send_json(sock, {"command": "send_message", "message": msg})

# Mostra o menu principal e trata as opções do usuário
# Aceita letras maiúsculas ou minúsculas
# Chama as funções de acordo com a escolha
def main_menu(sock):
    global running
    while running:
        print("\n     CHATINHO - MENU PRINCIPAL ")
        print("A. Espiar galera e grupos")
        print("B. Puxar um Papinho a Dois")
        print("C. Mandar papo no grupo")
        print("D. Criar um grupão")
        print("E. Chamar mais gente pro grupão")
        print("F. Meter o pé")

        choice = input("[CHATINHO] E aí, qual vai ser?\nR: ").strip().upper()

        if not running:
            break

        if choice == 'A':
            send_json(sock, {"command": "list_all"})

        elif choice == 'B':
            target_user = input("\n[CHATINHO] Com quem vai ser o Papinho a Dois?\nR: ")
            if target_user:
                send_json(sock, {"command": "select_chat", "target_user": target_user})
                start_chat_mode(sock, chat_type='user', chat_name=target_user)

        elif choice == 'C':
            target_group = input("\n[CHATINHO] Qual grupão vai receber o papo?\nR: ")
            if target_group:
                send_json(sock, {"command": "select_chat", "target_group": target_group})
                start_chat_mode(sock, chat_type='group', chat_name=target_group)

        elif choice == 'D':
            group_name = input("\n[CHATINHO] Nome do novo grupão?\nR: ")
            if group_name:
                send_json(sock, {"command": "create_group", "group_name": group_name})

        elif choice == 'E':
            group_name = input("\n[CHATINHO] Qual grupão?\nR: ")
            user_to_add = input(f"\n[CHATINHO] Quem vai entrar no grupão '{group_name}'?\nR: ")
            if group_name and user_to_add:
                send_json(sock, {
                    "command": "add_member_to_group",
                    "group_name": group_name,
                    "user_to_add": user_to_add
                })

        elif choice == 'F':
            running = False
            sock.close()
            print("[CHATINHO] Falou, até a próxima!")
            break
        else:
            print("[CHATINHO | XABLAU] Opção inválida, tenta de novo!")

# Função principal do cliente
# Conecta no servidor, faz login/cadastro e inicia o menu
# Cria a thread para receber mensagens
# Encerra tudo ao sair

def main():
    global running
    host = '0.tcp.sa.ngrok.io'
    port = 19918

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client_socket.connect((host, port))
        print(f"[CHATINHO] Conectado! O rolê tá em {host}:{port}")
    except ConnectionRefusedError:
        print(f"[CHATINHO | XABLAU] Não deu pra conectar em {host}:{port}.")
        print("[CHATINHO] Vê se o servidor tá de pé ou se o endereço tá certo.")
        return

    # Loop de autenticação (login ou cadastro)
    while True:
        print("\n   CHATINHO | TELA INICIAL ")
        print("1. Login ")
        print("2. Cadastro")
        action = input("[CHATINHO] Qual vai ser? (1 ou 2): ")

        username = input("[CHATINHO] Codinome: ")
        password = input("[CHATINHO] Senha secreta: ")

        if action == '1':
            auth_command = 'login'
        elif action == '2':
            auth_command = 'register'
        else:
            print("[CHATINHO | XABLAU] Ação inválida, só vale 1 ou 2!")
            continue

        send_json(client_socket, {
            "command": auth_command,
            "username": username,
            "password": password
        })

        try:
            response_raw = client_socket.recv(1024)
            if not response_raw:
                print("[CHATINHO | XABLAU] O servidor sumiu do mapa.")
                return

            response = json.loads(response_raw.decode('utf-8'))
            print(f"\n[CHATINHO | {response['status'].upper()}] {response['message']}")

            if response['status'] == 'success' and auth_command == 'login':
                break

        except (json.JSONDecodeError, ConnectionResetError):
             print("[CHATINHO | XABLAU] Bugou na autenticação, tenta de novo!")
             return

    # Cria a thread para receber mensagens do servidor
    receiver_thread = threading.Thread(target=receive_messages, args=(client_socket,))
    receiver_thread.daemon = True
    receiver_thread.start()

    try:
        main_menu(client_socket)
    except KeyboardInterrupt:
        print("\n[CHATINHO] Saiu no sapatinho (Ctrl+C)...")

    running = False
    client_socket.close()
    receiver_thread.join(timeout=1)
    print("[CHATINHO] Fim de papo, até mais!")
    os._exit(0)

# Só roda o main se for executado direto
if __name__ == "__main__":
    main()

# libs pra criptografia(nativo, como pedido)
import hashlib  # faz o hash da senha
import os

class UserManager:
    def __init__(self, db):
        self.db = db  # pega a conexão com o banco
    
    def register(self, username, password):
        # primeiro vê se já tem alguém com esse nome
        if self.db.user_exists(username):
            return False

        # gera 16 bytes aleatórios pro sal
        salt = os.urandom(16)
        
        # cria o hash da senha com PBKDF2 (mais seguro que MD5/SHA)
        password_bytes = password.encode('utf-8')
        hashed_password = hashlib.pbkdf2_hmac(
            'sha256',        # tipo de hash
            password_bytes,  # senha do user
            salt,           # sal aleatório
            100000         # quanto maior, mais difícil de quebrar
        )
        
        # transforma em texto pra salvar no banco (sal:hash)
        salt_hex = salt.hex()
        hashed_password_hex = hashed_password.hex()
        
        # junta o sal e o hash com : no meio
        full_hash_string = f"{salt_hex}:{hashed_password_hex}"
        
        self.db.create_user(username, full_hash_string)
        return True
    
    def authenticate(self, username, password):
        # pega o hash salvo do user
        full_hash_string = self.db.get_user_password_hash(username)
        if not full_hash_string:
            return False  # user não existe
        
        try:
            # separa o sal do hash (tavam juntos com : no meio)
            salt_hex, stored_hash_hex = full_hash_string.split(':')
            
            # converte de texto pra bytes de novo
            salt = bytes.fromhex(salt_hex)
            stored_hash = bytes.fromhex(stored_hash_hex)

            # faz o hash da senha que o user digitou
            # usando o mesmo sal que tava guardado
            password_bytes = password.encode('utf-8')
            new_hashed_password = hashlib.pbkdf2_hmac(
                'sha256', 
                password_bytes, 
                salt, 
                100000
            )
            
            # compara os hashes do jeito seguro
            # (tem que ser timing_safe_compare pra não dar brecha)
            return hashlib.timing_safe_compare(stored_hash, new_hashed_password)
        
        except Exception as e:
            # se der erro no formato do hash
            print(f"Erro ao autenticar {username}: {e}")
            return False
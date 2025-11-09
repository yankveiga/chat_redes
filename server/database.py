# usa postgres via psycopg2
import psycopg2

class Database:
    def __init__(self, db_url):
        # tenta conectar no postgres usando a URL do Render
        # (sslmode=require é obrigatório no Render)
        try:
            self.conn = psycopg2.connect(db_url, sslmode='require')
            print("[Database] Beleza! Conectou no postgres.")
        except psycopg2.OperationalError as e:
            print(f"[Database] Deu ruim: Não rolou conectar no postgres: {e}")
            raise
            
        # postgres já lida com threads sozinho, não precisa de config especial
        
        self.create_user_table()
        self.create_message_table()
        self.create_group_tables()
    
    # --- Funções dos Usuários ---

    def create_user_table(self):
        # tabela de users: nome único e hash da senha
        # postgres e sqlite aceitam IF NOT EXISTS
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL 
            )
        """)
        self.conn.commit()
    
    def user_exists(self, username):
        # ve se tem algum user com esse nome
        # no postgres usa %s em vez de ? pra placeholder
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE username=%s", (username,))
        return cursor.fetchone() is not None
    
    def create_user(self, username, password_hash):
        cursor = self.conn.cursor()
        # placeholder do psycopg2 usa %s
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, password_hash))
        self.conn.commit()
    
    def get_user_password_hash(self, username):
        cursor = self.conn.cursor()
        # placeholder do psycopg2 usa %s
        cursor.execute("SELECT password_hash FROM users WHERE username=%s", (username,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def get_all_users(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT username FROM users")
        return [row[0] for row in cursor.fetchall()]

    # --- Mensagens Offline ---
    
    def create_message_table(self):
        # tabela pra mensagens offline:
        # - SERIAL é tipo o AUTOINCREMENT do sqlite
        # - TIMESTAMPTZ guarda data/hora com timezone
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS offline_messages (
                id SERIAL PRIMARY KEY, 
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()
    
    def save_message(self, sender, receiver, message):
        # guarda msg quando alguém tá offline
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO offline_messages (sender, receiver, message) VALUES (%s, %s, %s)",
            (sender, receiver, message)
        )
        self.conn.commit()
    
    def get_and_delete_messages_for(self, receiver):
        cursor = self.conn.cursor()
        # busca mensagens pendentes para o destinatário
        cursor.execute("SELECT sender, message FROM offline_messages WHERE receiver=%s", (receiver,))
        messages = cursor.fetchall()
        if messages:
            # apaga as mensagens já entregues
            cursor.execute("DELETE FROM offline_messages WHERE receiver=%s", (receiver,))
            self.conn.commit()
        return messages

    # --- Grupos ---

    def create_group_tables(self):
        # cria duas tabelas:
        # 1. groups: só guarda o nome do grupo
        # 2. group_members: liga users com grupos
        #    (ON DELETE CASCADE: se apagar o grupo/user, limpa automático)
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                name TEXT PRIMARY KEY
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_members (
                group_name TEXT,
                username TEXT,
                FOREIGN KEY (group_name) REFERENCES groups(name) ON DELETE CASCADE,
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE,
                PRIMARY KEY (group_name, username)
            )
        """)
        self.conn.commit()
    
    def group_exists(self, group_name):
        # ve se tem grupo com esse nome
        cursor = self.conn.cursor()
        # placeholder do psycopg2 usa %s
        cursor.execute("SELECT 1 FROM groups WHERE name=%s", (group_name,))
        return cursor.fetchone() is not None
    
    def create_group(self, group_name):
        cursor = self.conn.cursor()
        # cria o grupo (usa %s como placeholder)
        cursor.execute("INSERT INTO groups (name) VALUES (%s)", (group_name,))
        self.conn.commit()
    
    def add_group_member(self, group_name, username):
        cursor = self.conn.cursor()
        # no postgres é ON CONFLICT DO NOTHING
        # (mesma coisa que INSERT OR IGNORE do sqlite)
        cursor.execute(
            "INSERT INTO group_members (group_name, username) VALUES (%s, %s) ON CONFLICT DO NOTHING", 
            (group_name, username)
        )
        self.conn.commit()
    
    def get_group_members(self, group_name):
        # lista todos os users de um grupo
        cursor = self.conn.cursor()
        cursor.execute("SELECT username FROM group_members WHERE group_name=%s", (group_name,))
        return [row[0] for row in cursor.fetchall()]
    
    def get_groups_for_user(self, username):
        # lista todos os grupos que o user tá
        cursor = self.conn.cursor()
        cursor.execute("SELECT group_name FROM group_members WHERE username=%s", (username,))
        return [row[0] for row in cursor.fetchall()]
class GroupManager:
    def __init__(self, db):
        # conexão com o banco
        self.db = db
    
    def create_group(self, group_name, creator_username):
        # tenta criar o grupo e bota o criador nele
        if self.db.group_exists(group_name):
            return False  # já tem grupo com esse nome
        
        # Cria o grupo no banco
        self.db.create_group(group_name)
        # Adiciona o criador como primeiro membro
        self.db.add_group_member(group_name, creator_username)
        return True
    
    def add_member(self, group_name, username):
        # ve se tanto o grupo quanto o user existem
        if not self.db.group_exists(group_name) or not self.db.user_exists(username):
            return False  # um dos dois não existe
        
        self.db.add_group_member(group_name, username)
        return True
    
    def get_members(self, group_name):
        # retorna a lista de users do grupo
        return self.db.get_group_members(group_name)
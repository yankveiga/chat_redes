# pega a classe ChatServer do server.py
from .server import ChatServer

if __name__ == "__main__":
    # cria o servidor (usa host/port padrão se não passar nada)
    server = ChatServer()
    
    # liga o servidor — o método start() entra no loop principal
    server.start()
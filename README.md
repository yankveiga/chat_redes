# chat_redes
Trabalho 1 de Redes de Computadores do grupo 3, formado por Humberto, Karoline e Yan.

## Descrição
Este projeto implementa um sistema de chat em Python, permitindo comunicação entre múltiplos usuários via rede. O sistema possui funcionalidades de cadastro, login, criação de grupos e troca de mensagens.

## Requisitos
- Python 3.10 ou superior
- Bibliotecas padrão do Python

## Como acessar
O servidor do chat já está rodando e acessível via uma porta pública do ngrok. Não é necessário executar o servidor localmente.

### Cliente
1. Acesse o diretório `client`:
   ```zsh
   cd client
   ```
2. Execute o cliente:
   ```zsh
   python3 client.py
   ```
3. Informe o endereço público do ngrok quando solicitado pelo cliente para se conectar ao servidor.

## Estrutura do Projeto
```
chat_redes/
├── client/
│   └── client.py
├── server/
│   ├── database.py
│   ├── group.py
│   ├── main.py
│   ├── server.py
│   └── user.py
└── README.md
```

## Autores
- Humberto
- Karoline
- Yan

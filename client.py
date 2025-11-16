import sys
import grpc
import kvstore_pb2
import kvstore_pb2_grpc

def main():
    # Verifica se o usuário forneceu o endereço do servidor (host:porta)
    if len(sys.argv) < 2:
        sys.exit(1)

    address = sys.argv[1]

    # Cria um canal gRPC inseguro para o servidor no endereço informado
    channel = grpc.insecure_channel(address)

    # Cria o stub (proxy) que permite chamar métodos remotos definidos no serviço KeyValueStore
    stub = kvstore_pb2_grpc.KeyValueStoreStub(channel)

    try:
        # Loop que lê comandos linha a linha da entrada padrão
        # Isso permite que o cliente funcione em modo interativo ou recebendo um arquivo via pipe
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue  # Ignora linhas vazias

            cmd = line[0]  # Primeiro caractere indica o comando

            # Comando I <key> <value>  → insere um par (chave, valor)
            if cmd == 'I':
                # Divide a linha em no máximo 3 partes:
                # I, chave, e o restante como valor (que pode conter espaços)
                parts = line.split(' ', 2)
                key = int(parts[1])
                value = parts[2] if len(parts) > 2 else ""

                # Envia requisição gRPC ao servidor
                reply = stub.Insert(kvstore_pb2.InsertRequest(key=key, value=value))

                # O servidor responde com um status
                print(reply.status)

            # Comando C <key>  → consulta valor associado à chave
            elif cmd == 'C':
                parts = line.split()
                key = int(parts[1])

                # Envia requisição de consulta
                reply = stub.Query(kvstore_pb2.QueryRequest(key=key))

                # Imprime o valor retornado (pode ser string vazia se a chave não existir)
                print(reply.value)

            # Comando A  → ativa o servidor (equivalente a "ligar" o serviço)
            elif cmd == 'A':
                reply = stub.Activate(kvstore_pb2.ActivateRequest())
                print(reply.status)

            # Comando T  → encerra o servidor e retorna quantas chaves estavam armazenadas
            elif cmd == 'T':
                reply = stub.Terminate(kvstore_pb2.TerminateRequest())

                # O servidor retorna o número de chaves salvas antes de desligar
                print(reply.num_keys)

                break  # Finaliza o cliente após enviar o comando T

    except EOFError:
        # Permite que o cliente termine silenciosamente quando a entrada é encerrada
        pass


if __name__ == "__main__":
    main()
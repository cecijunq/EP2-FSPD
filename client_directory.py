import sys
import grpc
import kvstore_pb2
import kvstore_pb2_grpc


def main():
    # Verifica se o usuário forneceu o endereço do servidor localizador (Directory Service)
    if len(sys.argv) < 2:
        #print("Uso: python client_directory.py <host:porta>")
        sys.exit(1)

    # Endereço do servidor localizador
    locator = sys.argv[1]

    # Cria um canal gRPC para se comunicar com o Directory Service
    channel = grpc.insecure_channel(locator)

    # Stub para chamar métodos remotos do DirectoryService definidos no .proto
    stub = kvstore_pb2_grpc.DirectoryServiceStub(channel)

    try:
        # Loop principal: lê comandos da entrada padrão (stdin)
        for line in sys.stdin:
            line = line.strip()

            if not line:
                continue  # Ignora linhas vazias

            cmd = line[0]  # Primeiro caractere define o comando

            # ----------------------------------------------------------------------
            # Comando T — Terminate
            # Solicita ao Directory Service que encerre e retorne o total de chaves
            # armazenadas em todos os pares registrados.
            # ----------------------------------------------------------------------
            if cmd == 'T':
                reply = stub.Terminate(kvstore_pb2.TerminateRequest())

                # O servidor retorna quantas chaves existem no sistema inteiro
                print(reply.total_keys)

                break  # Encerra o cliente local após enviar T

            # ----------------------------------------------------------------------
            # Comando P <locator>
            # Realiza o pairing de um novo peer no sistema distribuído.
            # O Directory Service registra um novo servidor de pares (key-value).
            # ----------------------------------------------------------------------
            elif cmd == 'P':
                parts = line.split(' ', 1)

                if len(parts) < 2:
                    continue  # Linha inválida, sem argumento

                loc = parts[1]  # Endereço host:porta do peer a registrar

                reply = stub.Pairing(kvstore_pb2.PairingRequest(locator=loc))

                # Imprime status retornado: normalmente "OK" ou "ERROR"
                print(reply.status)

            # ----------------------------------------------------------------------
            # Comando B <key>
            # Busca qual peer é responsável pela chave <key>,
            # consulta esse peer e imprime o valor da chave.
            # ----------------------------------------------------------------------
            elif cmd == 'B':
                parts = line.split()
            
                if len(parts) < 2:
                    continue
            
                key = int(parts[1])
            
                reply = stub.Lookup(kvstore_pb2.LookupRequest(key=key))
            
                print("=== DEBUG DIRECTORY ===")
                print("reply.locator =", repr(reply.locator))
            
                if reply.locator == "":
                    print("0")
                    continue
            
                # limpar
                peer_addr = reply.locator.strip()
                peer_addr = peer_addr.replace("\t", "")
                peer_addr = peer_addr.replace("\r", "")
                peer_addr = peer_addr.replace(" ", "")
            
                print("peer_addr limpado =", repr(peer_addr))
            
                peer_channel = grpc.insecure_channel(peer_addr)
                print("=== Testando conexão... ===")
                try:
                    grpc.channel_ready_future(peer_channel).result(timeout=2)
                    print("CONEXÃO OK!")
                except Exception as e:
                    print("FALHOU:", e)
                    continue
            
                peer_stub = kvstore_pb2_grpc.KeyValueStoreStub(peer_channel)
            
                q = peer_stub.Query(kvstore_pb2.QueryRequest(key=key))


    except EOFError:
        # Permite encerrar silenciosamente quando o stdin fechar
        pass


if __name__ == "__main__":
    main()

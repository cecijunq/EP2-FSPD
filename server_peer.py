import grpc
from concurrent import futures
import kvstore_pb2
import kvstore_pb2_grpc
import threading
import sys
import time


class KeyValueStoreServicer(kvstore_pb2_grpc.KeyValueStoreServicer):
    def __init__(self, server, directory_locator=None, self_locator=None):
        # Armazena pares chave-valor locais
        self.store = {}

        # Referência ao servidor gRPC, usada para desligamento
        self.server = server

        # Endereço do Directory Service (se existir)
        self.directory_locator = directory_locator

        # Endereço deste próprio servidor (host:porta)
        self.self_locator = self_locator


    # ----------------------------------------------------------------------
    # Insere ou atualiza uma chave localmente
    # ----------------------------------------------------------------------
    def Insert(self, request, context):
        key, value = request.key, request.value

        # Verifica se a chave já existia
        exists = key in self.store

        # Insere/atualiza o valor
        self.store[key] = value

        # Retorna 1 se a chave já existia, 0 caso contrário
        return kvstore_pb2.InsertReply(status=1 if exists else 0)


    # ----------------------------------------------------------------------
    # Consulta valor associado a uma chave
    # ----------------------------------------------------------------------
    def Query(self, request, context):
        key = request.key

        # Retorna string vazia se chave não existir
        value = self.store.get(key, "")

        return kvstore_pb2.QueryReply(value=value)
    

    # ----------------------------------------------------------------------
    # Ativa o servidor no Directory Service
    # Envia sua lista de chaves e seu endereço próprio.
    # ----------------------------------------------------------------------
    def Activate(self, request, context):
        # Se não há Directory Service configurado, falha
        if not self.directory_locator:
            return kvstore_pb2.ActivateReply(status=0)

        # Lista de chaves armazenadas localmente
        keys = list(self.store.keys())

        try:
            # Canal para o Directory Service
            channel = grpc.insecure_channel(self.directory_locator)
            stub = kvstore_pb2_grpc.DirectoryServiceStub(channel)

            # Cria mensagem de registro
            req = kvstore_pb2.RegisterRequest(locator=self.self_locator, keys=keys)

            # Envia para o Directory Service
            reply = stub.Register(req)

            # Retorna quantidade de chaves registradas no Directory Service
            return kvstore_pb2.ActivateReply(status=reply.count)

        except Exception:
            # Falha de comunicação
            return kvstore_pb2.ActivateReply(status=0)


    # ----------------------------------------------------------------------
    # Termina o servidor
    # Retorna o número de chaves armazenadas localmente.
    # Finaliza o processo após retorno ao cliente.
    # ----------------------------------------------------------------------
    def Terminate(self, request, context):
        num_keys = len(self.store)

        # Para permitir que a resposta seja enviada antes do shutdown,
        # a finalização do servidor ocorre em outra thread.
        threading.Thread(target=self._shutdown_server, daemon=True).start()

        return kvstore_pb2.TerminateReply(num_keys=num_keys)


    # ----------------------------------------------------------------------
    # Função auxiliar para desligar o servidor com pequeno atraso
    # ----------------------------------------------------------------------
    def _shutdown_server(self):
        time.sleep(0.5)  # Espera para garantir envio da resposta ao cliente
        try:
            self.server.stop(0)
        except Exception:
            pass

        # Encerra o processo por completo
        sys.exit(0)


# Função que inicializa o servidor gRPC KeyValueStore
def serve(port, directory_locator, self_host):
    # Cria servidor gRPC com pool de threads
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # Endereço host:porta deste servidor
    self_locator = f"{self_host}:{port}"

    # Cria instância do servicer
    servicer = KeyValueStoreServicer(
        server,
        directory_locator=directory_locator,
        self_locator=self_locator
    )

    # Registra o serviço no servidor gRPC
    kvstore_pb2_grpc.add_KeyValueStoreServicer_to_server(servicer, server)

    # Aceita conexões em todas as interfaces de rede
    server.add_insecure_port(f"[::]:{port}")

    # Inicia servidor
    server.start()

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        # Permite encerrar via CTRL+C
        return


# Executa servidor via linha de comando
if __name__ == "__main__":
    # Espera 3 argumentos: porta, endereço do Directory Service e host local
    if len(sys.argv) < 4:
        sys.exit(1)

    # Inicializa servidor com parâmetros da linha de comando
    serve(sys.argv[1], sys.argv[2], sys.argv[3])

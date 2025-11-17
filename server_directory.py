import grpc
from concurrent import futures
import kvstore_pb2
import kvstore_pb2_grpc
import threading
import sys
import time
from urllib.parse import urlparse

class DirectoryServicer(kvstore_pb2_grpc.DirectoryServiceServicer):
    def __init__(self, server, is_super=False):
        self.server = server
        self.directory = {}  # key (int) -> locator (string)
        self.is_super = is_super
        # lista de locators (host:port) de outros super-pares conhecidos
        self.super_peers = []

    def Register(self, request, context):
        count = 0
        for ch in request.keys:
            # grava/atualiza entrada localmente
            self.directory[ch] = request.locator
            count += 1
        return kvstore_pb2.RegisterReply(count=count)

    def Lookup(self, request, context):
        key = request.key
    
        # 1: primeiro verifica o dicionário local
        locator = self.directory.get(key, "")
        if locator:
            return kvstore_pb2.LookupReply(locator=locator)
    
        # 2: tenta perguntar a todos os peers registrados
        for peer in list(self.super_peers):
            try:
                ch = grpc.insecure_channel(peer)
                stub = kvstore_pb2_grpc.KeyValueStoreStub(ch)
                rep = stub.Query(kvstore_pb2.QueryRequest(key=key), timeout=1.0)
                if rep.value != "":
                    # encontrou chave nesse peer
                    return kvstore_pb2.LookupReply(locator=peer)
            except:
                continue
    
        # 3: não encontrado
        return kvstore_pb2.LookupReply(locator="")
    def Pairing(self, request, context):
        loc = request.locator
    
        # Registra o peer normalmente
        if loc not in self.super_peers:
            self.super_peers.append(loc)
    
        return kvstore_pb2.PairingReply(status=1)

    def Terminate(self, request, context):
        total = len(self.directory)
        threading.Thread(target=self._shutdown_server, daemon=True).start()
        return kvstore_pb2.DirectoryTerminateReply(total_keys=total)

    def _shutdown_server(self):
        time.sleep(0.5)
        try:
            self.server.stop(0)
        except Exception:
            pass
        sys.exit(0)


def serve(port, is_super=False):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = DirectoryServicer(server, is_super=is_super)

    kvstore_pb2_grpc.add_DirectoryServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f"[::]:{port}")

    server.start()
    role = "super-nó" if is_super else "concentrador"
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    # uso:
    # python server_directory.py <porta> [qualquer-coisa-para-ativar-super]
    if len(sys.argv) < 2:
        sys.exit(1)

    port = sys.argv[1]
    is_super = len(sys.argv) >= 3  # se houver segundo parâmetro, age como super-nó
    serve(port, is_super=is_super)

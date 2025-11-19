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
        """
        Se a chave estiver no dicionário local, retorna locator.
        Caso contrário, se for super-nó, faz alagamento recusivo
        usando self.super_peers (excluindo o par que fez a chamada).
        """
        key = request.key
        locator = self.directory.get(key, "")
        if locator:
            return kvstore_pb2.LookupReply(locator=locator)

        # não encontrou localmente -> se não for super, devolve vazio
        if not self.is_super:
            return kvstore_pb2.LookupReply(locator="")

        # obter IP do peer que chamou (forma: "ipv4:127.0.0.1:xxxxx" ou "ipv6:...").
        try:
            peer = context.peer()
            # peer pode ser '' em alguns cenários; trate com segurança
            caller_ip = None
            if peer:
                # exemplo: 'ipv4:127.0.0.1:54321'
                parts = peer.split(':')
                if len(parts) >= 2:
                    # pega a segunda parte (o endereço IP)
                    caller_ip = parts[1]
        except Exception:
            caller_ip = None

        # Procura recursivamente entre os super-pares conhecidos.
        # Exclui aquele cujo host corresponde ao caller_ip (se possível).
        for sp in list(self.super_peers):
            try:
                sp_host = sp.split(':')[0] if ':' in sp else sp
                # se conseguimos identificar caller_ip e for igual ao host deste super, pule
                if caller_ip and sp_host == caller_ip:
                    continue

                # tenta consultar o super-par
                channel = grpc.insecure_channel(sp)
                stub = kvstore_pb2_grpc.DirectoryServiceStub(channel)
                # pequeno timeout para evitar travar indefinidamente
                reply = stub.Lookup(kvstore_pb2.LookupRequest(key=key), timeout=2.0)
                if reply and reply.locator:
                    return kvstore_pb2.LookupReply(locator=reply.locator)
            except Exception:
                # ignora super-pares indisponíveis e continua
                continue

        # não encontrou em nenhum super-par
        return kvstore_pb2.LookupReply(locator="")

    def Pairing(self, request, context):
        """
        Em modo super, inclui o locator recebido na lista de super-pares conhecidos.
        Caso contrário, mantém comportamento simples (status = 0).
        """
        loc = request.locator
        if self.is_super:
            # evita duplicatas
            if loc not in self.super_peers:
                self.super_peers.append(loc)
            return kvstore_pb2.PairingReply(status=1)
        else:
            # comportamento compatível com etapas anteriores
            return kvstore_pb2.PairingReply(status=0)
    
    def Terminate(self, request, context):
        total = 0
    
        # Encerra todos os peers conhecidos no dicionário
        locators = set(self.directory.values())
    
        for loc in locators:
            try:
                channel = grpc.insecure_channel(loc)
                stub = kvstore_pb2_grpc.KeyValueStoreStub(channel)
    
                reply = stub.Terminate(kvstore_pb2.TerminateRequest())
                total += reply.num_keys
            except Exception:
                # Peer pode estar offline
                continue
    
        # Encerra o próprio DirectoryService
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

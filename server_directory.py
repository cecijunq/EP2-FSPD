import grpc
from concurrent import futures
import kvstore_pb2
import kvstore_pb2_grpc
import threading
import sys
import time


class DirectoryServicer(kvstore_pb2_grpc.DirectoryServiceServicer):
    """
    Implementação do DirectoryService.

    - Quando não é super-nó: realiza apenas registro local e lookup local.
    - Quando é super-nó: além do local, realiza busca recursiva entre outros super-nós.
    """

    def __init__(self, server, is_super=False):
        self.server = server
        self.directory = {}         # key (int) -> locator (string)
        self.is_super = is_super
        self.super_peers = []       # lista de locators (host:port) de outros super-nós conhecidos

    # ----------------------------------------------------------------------
    # Registro simples de chaves
    # ----------------------------------------------------------------------
    def Register(self, request, context):
        """
        Registra várias chaves associadas ao locator informado pelo cliente.
        """
        count = 0
        for ch in request.keys:
            self.directory[ch] = request.locator
            count += 1

        return kvstore_pb2.RegisterReply(count=count)

    # ----------------------------------------------------------------------
    # Lookup com possível busca recursiva (apenas entre super-nós)
    # ----------------------------------------------------------------------
    def Lookup(self, request, context):
        key = request.key

        # 1) Tenta buscar localmente.
        local = self.directory.get(key, "")
        if local:
            return kvstore_pb2.LookupReply(locator=local)

        # Se não é super-nó, não propaga busca.
        if not self.is_super:
            return kvstore_pb2.LookupReply(locator="")

        # 2) Identifica o IP do peer que fez a chamada, para evitar loop de flood.
        caller_ip = self._extract_peer_ip(context)

        # 3) Flood recursivo entre super-peers.
        for sp in list(self.super_peers):
            sp_host = sp.split(":")[0] if ":" in sp else sp

            # evita reenviar a consulta para quem nos chamou
            if caller_ip and caller_ip == sp_host:
                continue

            try:
                channel = grpc.insecure_channel(sp)
                stub = kvstore_pb2_grpc.DirectoryServiceStub(channel)

                reply = stub.Lookup(kvstore_pb2.LookupRequest(key=key), timeout=2.0)

                if reply and reply.locator:
                    return kvstore_pb2.LookupReply(locator=reply.locator)

            except Exception:
                # Super-nó indisponível — ignoramos e seguimos.
                continue

        # 4) Não achou em nenhum lugar
        return kvstore_pb2.LookupReply(locator="")

    # ----------------------------------------------------------------------
    # Pairing entre super-nós
    # ----------------------------------------------------------------------
    def Pairing(self, request, context):
        """
        Em modo super-nó:
            adiciona o locator recebido à lista de super-peers (sem duplicatas).
        Caso contrário:
            comportamento simples de compatibilidade.
        """
        loc = request.locator

        if self.is_super:
            if loc not in self.super_peers:
                self.super_peers.append(loc)
            return kvstore_pb2.PairingReply(status=1)

        return kvstore_pb2.PairingReply(status=0)

    # ----------------------------------------------------------------------
    # Finalização segura do servidor
    # ----------------------------------------------------------------------
    def Terminate(self, request, context):
        total = len(self.directory)

        # Usamos thread para permitir que o gRPC responda antes de encerrar.
        threading.Thread(target=self._shutdown_server, daemon=True).start()

        return kvstore_pb2.DirectoryTerminateReply(total_keys=total)

    def _shutdown_server(self):
        time.sleep(0.5)
        try:
            self.server.stop(0)
        except Exception:
            pass
        sys.exit(0)

    # ----------------------------------------------------------------------
    # Utilitário: extrai IP do cliente que chamou o método
    # ----------------------------------------------------------------------
    def _extract_peer_ip(self, context):
        """
        Retorna apenas o IP (ex.: '127.0.0.1') do peer que fez a chamada RPC.
        Formatos comuns:
            'ipv4:127.0.0.1:54321'
            'ipv6:[::1]:12345'
        """
        try:
            peer = context.peer()
            if not peer:
                return None

            parts = peer.split(":")
            if len(parts) >= 2:
                return parts[1]
        except Exception:
            pass
        return None


# --------------------------------------------------------------------------------------
# Execução do servidor
# --------------------------------------------------------------------------------------
def serve(port, is_super=False):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = DirectoryServicer(server, is_super=is_super)

    kvstore_pb2_grpc.add_DirectoryServiceServicer_to_server(servicer, server)

    server.add_insecure_port(f"[::]:{port}")
    server.start()

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        return


# --------------------------------------------------------------------------------------
# Execução via linha de comando
# --------------------------------------------------------------------------------------
if __name__ == "__main__":
    # Uso:
    #   python server_directory.py <porta>
    #   python server_directory.py <porta> super
    #
    if len(sys.argv) < 2:
        print("Uso: python server_directory.py <porta> [super]")
        sys.exit(1)

    port = sys.argv[1]
    is_super = len(sys.argv) >= 3
    serve(port, is_super=is_super)

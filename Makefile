PYTHON=python3
PROTO=kvstore.proto
STUB_PY=kvstore_pb2.py
STUB_GRPC_PY=kvstore_pb2_grpc.py

# Host da máquina local automaticamente detectado
HOSTNAME=$(shell hostname -f)

.PHONY: all clean stubs run_cli_pares run_serv_pares_1 run_serv_pares_2 run_serv_central run_cli_central run_super_par

all: stubs

clean:
	-rm -f $(STUB_PY) $(STUB_GRPC_PY)
	-rm -f *.pyc
	-rm -rf __pycache__

stubs:
	$(PYTHON) -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. $(PROTO)

# -------------------------------------------------------------------
# CLIENTE do peer
# make run_cli_pares arg=host:porta
# -------------------------------------------------------------------
run_cli_pares: stubs
	$(PYTHON) client.py $(arg)

# -------------------------------------------------------------------
# SERVIDOR PEER – PARTE 1 (sem Directory)
# make run_serv_pares_1 arg=5555
# -------------------------------------------------------------------
run_serv_pares_1: stubs
	$(PYTHON) server_peer.py $(arg) "" $(HOSTNAME)

# -------------------------------------------------------------------
# SERVIDOR PEER – PARTE 2/3 (com Directory)
# make run_serv_pares_2 arg1=5555 arg2=host_do_directory:6666
# -------------------------------------------------------------------
run_serv_pares_2: stubs
	$(PYTHON) server_peer.py $(arg1) $(arg2) $(HOSTNAME)

# -------------------------------------------------------------------
# SERVIDOR CENTRAL (Directory normal)
# make run_serv_central arg=6666
# -------------------------------------------------------------------
run_serv_central: stubs
	$(PYTHON) server_directory.py $(arg)

# -------------------------------------------------------------------
# CLIENTE DO DIRECTORY
# make run_cli_central arg=host:porta
# -------------------------------------------------------------------
run_cli_central: stubs
	$(PYTHON) client_directory.py $(arg)

# -------------------------------------------------------------------
# SUPER-PAR
# make run_super_par arg=6666
# -------------------------------------------------------------------
run_super_par: stubs
	$(PYTHON) server_directory.py $(arg) super

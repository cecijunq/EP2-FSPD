PYTHON=python3
PROTO=kvstore.proto
STUB_PY=kvstore_pb2.py
STUB_GRPC_PY=kvstore_pb2_grpc.py

.PHONY: all clean stubs run_cli_pares run_serv_pares_1 run_serv_pares_2 run_serv_central run_cli_central run_super_par

all: stubs

clean:
	-rm -f $(STUB_PY) $(STUB_GRPC_PY)
	-rm -f *.pyc
	-rm -f __pycache__ -r

stubs:
	# gera stubs Python (gRPC) a partir do .proto
#	@echo "Gerando stubs gRPC a partir de $(PROTO)..."
	$(PYTHON) -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. $(PROTO)

# run rules: assumem que os scripts python estão no diretório atual.
# usar: make run_cli_pares arg=nome_do_host_do_serv_pares:5555
run_cli_pares: stubs
	$(PYTHON) client.py $(arg)

# Para executar o peer no modo parte 1 (ativação não faz nada), passamos um directory_locator vazio ("")
# make run_serv_pares_1 arg=5555
run_serv_pares_1: stubs
#	@echo "Iniciando servidor peer (parte 1) na porta $(arg)..."
	$(PYTHON) server_peer.py $(arg) "" localhost

# Para executar o peer no modo parte 2/3 (ativação com concentrador)
# make run_serv_pares_2 arg1=5555 arg2=nome_do_host_do_serv_central:6666
run_serv_pares_2: stubs
#	@echo "Iniciando servidor peer (parte 2/3) na porta $(arg1) com concentrador $(arg2)..."
	$(PYTHON) server_peer.py $(arg1) $(arg2) localhost

# servidor central (concentrador) normal
# make run_serv_central arg=6666
run_serv_central: stubs
#	@echo "Iniciando servidor concentrador na porta $(arg)..."
	$(PYTHON) server_directory.py $(arg)

# cliente do concentrador (cliente central)
# make run_cli_central arg=nome_do_host_do_serv_central:6666
run_cli_central: stubs
	$(PYTHON) client_directory.py $(arg)

# iniciar um super-par (concentrador em modo super)
# make run_super_par arg=6666
run_super_par: stubs
#	@echo "Iniciando servidor concentrador (super-par) na porta $(arg)..."
	$(PYTHON) server_directory.py $(arg) super

"""imports"""

import logging
import os
from dotenv import load_dotenv

from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException

from txs_analyzer.txs_analyzer import BlockchainAnalyzer

from chain_analisys.parser.cl_parser import build_argument_parser
from chain_analisys.utils import logging_
from chain_analisys.openvpn_connection import opvpn_conn


script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)

# Parse command line arguments
cl_args = build_argument_parser().parse_args()

# Setup logging
logging_level = getattr(logging, cl_args.log_level.upper())
log_formatter = logging_.get_common_formatter()
log_handlers = []
# Stdout handler
log_stdout_handler = logging_.get_stdout_handler(
    formatter=log_formatter, log_level=logging_level
)
log_handlers.append(log_stdout_handler)
logging_.setup_project_logger(handlers=log_handlers, logger_level=logging_level)

logger = logging.getLogger(f"{os.path.basename(os.getcwd())}.{__name__}")

# Percorso al file di configurazione OpenVPN (.ovpn)
vpn_config_path = "/etc/openvpn/client/mlorenzato.ovpn"

# Avvia la connessione VPN
vpn_process = opvpn_conn.connect_to_vpn(vpn_config_path)

"""Configura la connessione RPC al nodo Bitcoin"""
load_dotenv()

rpc_user = os.getenv("RPC_USER")
rpc_password = os.getenv("RPC_PASSWORD")
rpc_host = os.getenv("RPC_HOST")
rpc_port = os.getenv("RPC_PORT")
db_username = os.getenv("DB_USERNAME")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")

# Crea un'istanza di connessione al nodo
rpc_connection = AuthServiceProxy(
    f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}"
)

# Testa la connessione ottenendo informazioni base sul nodo
try:
    blockchain_info = rpc_connection.getblockchaininfo()
    logger.info("Blockchain Info: %s", blockchain_info)
except JSONRPCException as e:
    logger.info("Errore nella connessione RPC: %s", e)

db_params = {
    "dbname": "blockchain_analisys",
    "user": db_username,
    "password": db_password,
    "host": db_host,
}

# Crea un'istanza della classe BlockchainAnalyzer
reset_db = True
analyzer = BlockchainAnalyzer(
    rpc_user, rpc_password, rpc_host, rpc_port, db_params, reset_db
)

# Itera su tutte le transazioni partendo dal blocco 0
analyzer.iterate_all_transactions()

# Chiudi la connessione
analyzer.close()

# Termina la connessione VPN
opvpn_conn.disconnect_vpn(vpn_process)

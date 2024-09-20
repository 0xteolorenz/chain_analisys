import logging
import os
from dotenv import load_dotenv

from chain_analisys.parser.cl_parser import build_argument_parser
from chain_analisys.utils import logging_

from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException


script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)

"""Setup logger"""
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

"""Configura la connessione RPC al nodo Bitcoin"""
load_dotenv()

rpc_user = os.getenv("RPC_USER")
rpc_password = os.getenv("RPC_PASSWORD")
rpc_host = os.getenv("RPC_HOST")
rpc_port = os.getenv("RPC_PORT")

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
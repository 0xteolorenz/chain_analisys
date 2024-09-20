"""imports"""

import subprocess
import time
import logging


_logger = logging.getLogger(__name__)


def connect_to_vpn(vpn_config_path):
    """Connect to a VPN using OpenVPN and the provided configuration file."""
    try:
        # Avvia OpenVPN usando subprocess
        vpn_process = subprocess.Popen(
            ["sudo", "openvpn", "--config", vpn_config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Aspetta qualche secondo per dare tempo alla connessione VPN
        time.sleep(10)

        # Controlla se il processo è ancora attivo
        if vpn_process.poll() is None:
            _logger.info("Connessione VPN stabilita con successo.")
        else:
            _, stderr = vpn_process.communicate()
            _logger.info("Errore durante la connessione VPN.")
            _logger.info(stderr.decode())

        return vpn_process

    except Exception as e:
        _logger.info("Si è verificato un errore: %s", e)
        return None


def disconnect_vpn(vpn_process):
    """Disconnect from the VPN by terminating the OpenVPN process."""
    # Termina la connessione VPN
    if vpn_process:
        vpn_process.terminate()
        vpn_process.wait()
        _logger.info("Connessione VPN terminata.")

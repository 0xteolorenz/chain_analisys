"""Module with the custom logging handlers."""

import logging.handlers


class UTF8DatagramHandler(logging.handlers.DatagramHandler):
    """Datagram handler to send messages UTF-8 encoded."""

    def emit(self, record):
        try:
            msg = self.format(record)
            # Ensure the message is encoded as UTF-8
            self.send(msg.encode("utf-8"))
        except Exception:  # pylint: disable=broad-exception-caught
            self.handleError(record)

    def send(self, s):
        if self.sock is None:
            self.createSocket()
        self.sock.sendto(s, (self.host, self.port))  # type: ignore

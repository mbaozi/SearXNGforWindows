import ssl
import typing

from httpcore._backends.sync import SyncStream as CoreSyncStream
from httpcore._utils import is_socket_readable
from python_socks.sync.v2._ssl_transport import SSLTransport


class SyncStream(CoreSyncStream):
    def get_extra_info(self, info: str) -> typing.Any:
        if info == "ssl_object":
            if isinstance(self._sock, ssl.SSLSocket):
                # noinspection PyProtectedMember
                return self._sock._sslobj  # type: ignore
            if isinstance(self._sock, SSLTransport):
                return self._sock.sslobj  # type: ignore
            return None

        if info == "client_addr":  # pragma: nocover
            if isinstance(self._sock, SSLTransport):
                return self._sock.socket.getsockname()
            else:
                return self._sock.getsockname()

        if info == "server_addr":  # pragma: nocover
            if isinstance(self._sock, SSLTransport):
                return self._sock.socket.getpeername()
            else:
                return self._sock.getpeername()

        if info == "socket":  # pragma: nocover
            return self._sock  # ???

        if info == "is_readable":
            if isinstance(self._sock, SSLTransport):
                return is_socket_readable(self._sock.socket)
            else:
                return is_socket_readable(self._sock)

        return None  # pragma: nocover

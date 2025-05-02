import ssl

from httpcore import (
    ConnectionPool,
    Origin,
    ConnectionInterface,
    Request,
    Response,
    default_ssl_context,
    HTTP11Connection,
    ConnectionNotAvailable,
)
# from httpcore.backends.sync import SyncStream
from ._sync_stream import SyncStream
from httpcore._synchronization import Lock

from python_socks import ProxyType, parse_proxy_url
from python_socks.sync.v2 import Proxy


class SyncProxy(ConnectionPool):
    def __init__(
        self,
        *,
        proxy_type: ProxyType,
        proxy_host: str,
        proxy_port: int,
        username=None,
        password=None,
        rdns=None,
        proxy_ssl: ssl.SSLContext = None,
        **kwargs,
    ):
        self._proxy_type = proxy_type
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port
        self._username = username
        self._password = password
        self._rdns = rdns
        self._proxy_ssl = proxy_ssl

        super().__init__(**kwargs)

    def create_connection(self, origin: Origin) -> ConnectionInterface:
        return SyncProxyConnection(
            proxy_type=self._proxy_type,
            proxy_host=self._proxy_host,
            proxy_port=self._proxy_port,
            username=self._username,
            password=self._password,
            rdns=self._rdns,
            proxy_ssl=self._proxy_ssl,
            remote_origin=origin,
            ssl_context=self._ssl_context,
            keepalive_expiry=self._keepalive_expiry,
            http1=self._http1,
            http2=self._http2,
        )

    @classmethod
    def from_url(cls, url, **kwargs):
        proxy_type, host, port, username, password = parse_proxy_url(url)
        return cls(
            proxy_type=proxy_type,
            proxy_host=host,
            proxy_port=port,
            username=username,
            password=password,
            **kwargs,
        )


class SyncProxyConnection(ConnectionInterface):
    def __init__(
        self,
        *,
        proxy_type: ProxyType,
        proxy_host: str,
        proxy_port: int,
        username=None,
        password=None,
        rdns=None,
        proxy_ssl: ssl.SSLContext = None,
        remote_origin: Origin,
        ssl_context: ssl.SSLContext,
        keepalive_expiry: float = None,
        http1: bool = True,
        http2: bool = False,
    ) -> None:

        if ssl_context is None:  # pragma: no cover
            ssl_context = default_ssl_context()

        self._proxy_type = proxy_type
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port
        self._username = username
        self._password = password
        self._rdns = rdns
        self._proxy_ssl = proxy_ssl

        self._remote_origin = remote_origin
        self._ssl_context = ssl_context
        self._keepalive_expiry = keepalive_expiry
        self._http1 = http1
        self._http2 = http2

        self._connect_lock = Lock()
        self._connection = None

    def handle_request(self, request: Request) -> Response:
        timeouts = request.extensions.get('timeout', {})
        timeout = timeouts.get('connect', None)

        with self._connect_lock:
            if self._connection is None:
                stream = self._connect_via_proxy(
                    origin=self._remote_origin,
                    connect_timeout=timeout,
                )

                ssl_object = stream.get_extra_info('ssl_object')
                http2_negotiated = (
                    ssl_object is not None and ssl_object.selected_alpn_protocol() == "h2"
                )
                if http2_negotiated or (self._http2 and not self._http1):
                    from httpcore import HTTP2Connection

                    self._connection = HTTP2Connection(
                        origin=self._remote_origin,
                        stream=stream,
                        keepalive_expiry=self._keepalive_expiry,
                    )
                else:
                    self._connection = HTTP11Connection(
                        origin=self._remote_origin,
                        stream=stream,
                        keepalive_expiry=self._keepalive_expiry,
                    )
            elif not self._connection.is_available():  # pragma: no cover
                raise ConnectionNotAvailable()

        return self._connection.handle_request(request)

    def _connect_via_proxy(self, origin: Origin, connect_timeout: int):
        scheme, hostname, port = origin.scheme, origin.host, origin.port

        ssl_context = self._ssl_context if scheme == b'https' else None
        host = hostname.decode('ascii')

        proxy = Proxy.create(
            proxy_type=self._proxy_type,
            host=self._proxy_host,
            port=self._proxy_port,
            username=self._username,
            password=self._password,
            rdns=self._rdns,
            proxy_ssl=self._proxy_ssl,
        )

        proxy_stream = proxy.connect(
            host,
            port,
            dest_ssl=ssl_context,
            timeout=connect_timeout,
        )

        return SyncStream(sock=proxy_stream.socket)

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()

    def can_handle_request(self, origin: Origin) -> bool:
        return origin == self._remote_origin

    def is_available(self) -> bool:
        if self._connection is None:  # pragma: no cover
            # return self._http2 and (self._remote_origin.scheme == b"https" or not self._http1)
            return False
        return self._connection.is_available()

    def has_expired(self) -> bool:
        if self._connection is None:
            return False
        return self._connection.has_expired()

    def is_idle(self) -> bool:
        if self._connection is None:
            return False
        return self._connection.is_idle()

    def is_closed(self) -> bool:
        if self._connection is None:
            return False
        return self._connection.is_closed()

    def info(self) -> str:  # pragma: no cover
        if self._connection is None:
            return "CONNECTING"
        return self._connection.info()

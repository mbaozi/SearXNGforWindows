import ssl

import sniffio
from httpcore import (
    AsyncConnectionPool,
    Origin,
    AsyncConnectionInterface,
    Request,
    Response,
    default_ssl_context,
    AsyncHTTP11Connection,
    ConnectionNotAvailable,
)
from httpcore import AsyncNetworkStream
from httpcore._synchronization import AsyncLock
from python_socks import ProxyType, parse_proxy_url


class AsyncProxy(AsyncConnectionPool):
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
        loop=None,
        **kwargs,
    ):
        self._proxy_type = proxy_type
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port
        self._username = username
        self._password = password
        self._rdns = rdns
        self._proxy_ssl = proxy_ssl
        self._loop = loop

        super().__init__(**kwargs)

    def create_connection(self, origin: Origin) -> AsyncConnectionInterface:
        return AsyncProxyConnection(
            proxy_type=self._proxy_type,
            proxy_host=self._proxy_host,
            proxy_port=self._proxy_port,
            username=self._username,
            password=self._password,
            rdns=self._rdns,
            proxy_ssl=self._proxy_ssl,
            loop=self._loop,
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


class AsyncProxyConnection(AsyncConnectionInterface):
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
        loop=None,
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
        self._loop = loop

        self._remote_origin = remote_origin
        self._ssl_context = ssl_context
        self._keepalive_expiry = keepalive_expiry
        self._http1 = http1
        self._http2 = http2

        self._connect_lock = AsyncLock()
        self._connection = None

    async def handle_async_request(self, request: Request) -> Response:
        timeouts = request.extensions.get('timeout', {})
        timeout = timeouts.get('connect', None)

        async with self._connect_lock:
            if self._connection is None:
                stream = await self._connect_via_proxy(
                    origin=self._remote_origin,
                    connect_timeout=timeout,
                )

                ssl_object = stream.get_extra_info("ssl_object")
                http2_negotiated = (
                    ssl_object is not None and ssl_object.selected_alpn_protocol() == "h2"
                )
                if http2_negotiated or (self._http2 and not self._http1):
                    from httpcore import AsyncHTTP2Connection

                    self._connection = AsyncHTTP2Connection(
                        origin=self._remote_origin,
                        stream=stream,
                        keepalive_expiry=self._keepalive_expiry,
                    )
                else:
                    self._connection = AsyncHTTP11Connection(
                        origin=self._remote_origin,
                        stream=stream,
                        keepalive_expiry=self._keepalive_expiry,
                    )
            elif not self._connection.is_available():  # pragma: no cover
                raise ConnectionNotAvailable()

            return await self._connection.handle_async_request(request)

    async def _connect_via_proxy(self, origin, connect_timeout) -> AsyncNetworkStream:
        scheme, hostname, port = origin.scheme, origin.host, origin.port

        ssl_context = self._ssl_context if scheme == b'https' else None
        host = hostname.decode('ascii')  # ?

        return await self._open_stream(
            host=host,
            port=port,
            connect_timeout=connect_timeout,
            ssl_context=ssl_context,
        )

    async def _open_stream(self, host, port, connect_timeout, ssl_context):
        backend = sniffio.current_async_library()

        if backend == 'asyncio':
            return await self._open_aio_stream(host, port, connect_timeout, ssl_context)

        if backend == 'trio':
            return await self._open_trio_stream(host, port, connect_timeout, ssl_context)

        # Curio support has been dropped in httpcore 0.14.0
        # if backend == 'curio':
        #     return await self._open_curio_stream(host, port, connect_timeout, ssl_context)

        raise RuntimeError(f'Unsupported concurrency backend {backend!r}')  # pragma: no cover

    async def _open_aio_stream(self, host, port, connect_timeout, ssl_context):
        from httpcore._backends.anyio import AnyIOStream
        from python_socks.async_.anyio import Proxy

        proxy = Proxy.create(
            proxy_type=self._proxy_type,
            host=self._proxy_host,
            port=self._proxy_port,
            username=self._username,
            password=self._password,
            rdns=self._rdns,
            proxy_ssl=self._proxy_ssl,
        )

        proxy_stream = await proxy.connect(
            host,
            port,
            dest_ssl=ssl_context,
            timeout=connect_timeout,
        )

        return AnyIOStream(proxy_stream.anyio_stream)

    async def _open_trio_stream(self, host, port, connect_timeout, ssl_context):
        from httpcore._backends.trio import TrioStream
        from python_socks.async_.trio.v2 import Proxy

        proxy = Proxy.create(
            proxy_type=self._proxy_type,
            host=self._proxy_host,
            port=self._proxy_port,
            username=self._username,
            password=self._password,
            rdns=self._rdns,
            proxy_ssl=self._proxy_ssl,
        )

        proxy_stream = await proxy.connect(
            host,
            port,
            dest_ssl=ssl_context,
            timeout=connect_timeout,
        )

        return TrioStream(proxy_stream.trio_stream)

    async def aclose(self) -> None:
        if self._connection is not None:
            await self._connection.aclose()

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

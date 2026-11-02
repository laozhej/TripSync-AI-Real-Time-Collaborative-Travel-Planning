"""Bound HTTP input before parsers allocate it; never log rejected bodies."""
from starlette.responses import JSONResponse


class TransportGuard:
    def __init__(self, app, max_bytes=2*1024*1024):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        # Buffer a bounded body before dispatch, so an oversized stream cannot
        # partially execute a mutation or produce a second response.
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            if len(body) + len(chunk) > self.max_bytes:
                return await JSONResponse({'detail': 'Request exceeds 2 MiB'}, 413)(scope, receive, send)
            body.extend(chunk)
            if not message.get('more_body', False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {'type': 'http.request', 'body': bytes(body), 'more_body': False}

        async def safe_send(message):
            if message['type'] == 'http.response.start':
                message['headers'] = list(message.get('headers', [])) + [
                    (b'x-content-type-options', b'nosniff'),
                    (b'referrer-policy', b'no-referrer'),
                    (b'cache-control', b'no-store'),
                ]
            await send(message)

        await self.app(scope, bounded_receive, safe_send)

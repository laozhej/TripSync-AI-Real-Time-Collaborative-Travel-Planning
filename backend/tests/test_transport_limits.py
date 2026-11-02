"""Transport limits run before JSON parsing, including chunked bodies."""
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.transport import TransportGuard


def test_body_limit_counts_chunks_and_does_not_trust_content_length():
    app = FastAPI()
    app.add_middleware(TransportGuard, max_bytes=32)

    @app.post('/')
    async def echo(request: Request):
        return {'size': len(await request.body())}

    with TestClient(app) as client:
        assert client.post('/', content=b'a'*32).json() == {'size': 32}
        for headers in ({}, {'content-length': '1'}):
            result = client.post('/', content=iter([b'a'*20, b'b'*20]), headers=headers)
            assert result.status_code == 413
            assert 'aaaa' not in result.text
        response = client.get('/')
        assert response.headers['x-content-type-options'] == 'nosniff'
        assert response.headers['referrer-policy'] == 'no-referrer'

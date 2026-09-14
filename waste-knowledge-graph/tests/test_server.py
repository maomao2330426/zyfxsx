import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen,Request
from urllib.error import HTTPError
import pytest
from wastekg.server import App,handler


@pytest.fixture()
def base():
    server=ThreadingHTTPServer(('127.0.0.1',0),handler(App()))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    yield f'http://127.0.0.1:{server.server_port}'
    server.shutdown();server.server_close();thread.join()


def test_http_stats_and_static_route(base):
    with urlopen(base+'/api/stats') as r:assert json.load(r)['items']>=100
    with urlopen(base+'/') as r:assert b'WASTE KNOWLEDGE' in r.read()
    with pytest.raises(HTTPError) as e:urlopen(base+'/../../requirements.txt')
    assert e.value.code==404


@pytest.mark.parametrize('payload',[{'text':''},{'text':'a'*129},{'text':'a','mode':'unknown'},[]])
def test_invalid_extraction_returns_400(base,payload):
    req=Request(base+'/api/extract',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with pytest.raises(HTTPError) as e:urlopen(req)
    assert e.value.code==400


def test_cross_origin_request_is_denied(base):
    req=Request(base+'/api/extract',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://example.org'})
    with pytest.raises(HTTPError) as e:urlopen(req)
    assert e.value.code==403

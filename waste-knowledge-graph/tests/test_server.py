import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import urlopen,Request
from urllib.error import HTTPError
from urllib.parse import urlencode
import pytest
from wastekg.server import App,handler
from wastekg.common import model_signature,write_json


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


@pytest.mark.parametrize('query',['limit=0','limit=-1','offset=-2','offset=x','scope=unreviewed'])
def test_invalid_pagination_returns_400(base,query):
    with pytest.raises(HTTPError) as error:urlopen(base+'/api/search?'+query)
    assert error.value.code==400


def test_external_catalog_qa_and_audit_routes(base):
    with urlopen(base+'/api/search?scope=external&limit=24&offset=150') as response:
        page=json.load(response)
    assert page['offset']==150 and len(page['items'])==24
    assert all(row['review_status']=='source_labeled' for row in page['items'])
    with urlopen(base+'/api/qa?'+urlencode({'q':'阿司匹林是什么垃圾'})) as response:
        assert json.load(response)['status']=='reference'
    with urlopen(base+'/api/dataset') as response:
        audit=json.load(response)
    assert audit['summary']['formats_match'] is True
    assert audit['conflicts'][0]['name']=='竹签'


def test_graph_limit_and_empty_qa_rejected(base):
    with urlopen(base+'/api/graph?limit=1&scope=external') as response:
        graph=json.load(response)
    assert sum(node['kind']=='ITEM' for node in graph['nodes'])==1
    for route in ('/api/graph?limit=0','/api/qa?q='):
        with pytest.raises(HTTPError) as error:urlopen(base+route)
        assert error.value.code==400


def test_evaluation_is_bound_to_current_weights(tmp_path):
    for name in ('ner.weights.h5','relation.weights.h5','vocab.json'):
        (tmp_path/name).write_bytes(b'first model')
    report={'model_signature':model_signature(tmp_path),'score':.5}
    write_json(tmp_path/'web_metrics.json',report)
    app=App(tmp_path)
    assert app.evaluation('web_metrics.json')==report
    (tmp_path/'ner.weights.h5').write_bytes(b'new model')
    assert app.evaluation('web_metrics.json') is None
    write_json(tmp_path/'web_metrics.json',{'score':.8})
    assert app.evaluation('web_metrics.json') is None

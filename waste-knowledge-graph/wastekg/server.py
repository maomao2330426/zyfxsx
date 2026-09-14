"""仅绑定本机的教学 Web 服务；界面不依赖 CDN。"""
import argparse
import mimetypes
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from .common import *
from .graph import KnowledgeBase


class App:
    def __init__(self):
        self.kb=KnowledgeBase();self.model=None;self.model_lock=threading.Lock()

    def stats(self):
        from collections import Counter
        return {'items':len(self.kb.rows),'nodes':len(self.kb.graph['nodes']),'edges':len(self.kb.graph['edges']),
                'categories':dict(Counter(r['category'] for r in self.kb.rows)),
                'model_ready':(ROOT/'models'/'ner.weights.h5').exists() and (ROOT/'models'/'relation.weights.h5').exists(),
                'backend':'local_json','region':'上海','sources':read_json(DATA/'sources.json')}


def handler(app):
    class Handler(BaseHTTPRequestHandler):
        def reply(self,status,payload,ctype='application/json; charset=utf-8'):
            data=json.dumps(payload,ensure_ascii=False).encode() if ctype.startswith('application/json') else payload
            self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)))
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(data)

        def do_GET(self):
            url=urlparse(self.path);query=parse_qs(url.query)
            arg=lambda k,d='':query.get(k,[d])[0]
            try:
                if url.path=='/api/stats':return self.reply(200,app.stats())
                if url.path=='/api/search':return self.reply(200,app.kb.search(arg('q'),arg('category'),int(arg('limit','30'))))
                if url.path=='/api/graph':return self.reply(200,app.kb.subgraph(arg('q'),arg('category'),min(80,int(arg('limit','24')))))
                if url.path=='/api/metrics':
                    path=ROOT/'models'/'metrics.json'
                    return self.reply(200,{'available':path.exists(),'metrics':read_json(path) if path.exists() else None,
                                           'history':read_json(ROOT/'models'/'history.json') if path.exists() else [],
                                           'challenge':read_json(ROOT/'reports'/'challenge_metrics.json') if (ROOT/'reports'/'challenge_metrics.json').exists() else None,
                                           'web':read_json(ROOT/'reports'/'web_metrics.json') if (ROOT/'reports'/'web_metrics.json').exists() else None})
                allowed={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
                if url.path not in allowed:return self.reply(404,{'error':'未找到页面'})
                path=ROOT/'web'/allowed[url.path]
                return self.reply(200,path.read_bytes(),(mimetypes.guess_type(str(path))[0] or 'application/octet-stream')+'; charset=utf-8')
            except (ValueError,TypeError):return self.reply(400,{'error':'查询参数不合法'})

        def do_POST(self):
            if self.path!='/api/extract':return self.reply(404,{'error':'未知接口'})
            # 防止外部网页以跨域请求调用本机的昂贵模型推理。
            origin=self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
                return self.reply(403,{'error':'不允许跨域请求'})
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=8192:return self.reply(413,{'error':'请求体过大或为空'})
                payload=json.loads(self.rfile.read(n))
                if not isinstance(payload,dict):raise ValueError()
                text=payload.get('text','')
                if not isinstance(text,str) or not 1<=len(text.strip())<=MAX_LEN:raise ValueError()
                mode=payload.get('mode','neural')
                if mode=='baseline':
                    from .inference import baseline
                    return self.reply(200,baseline(text))
                if mode!='neural':raise ValueError()
                with app.model_lock:
                    if app.model is None:
                        from .inference import Extractor
                        app.model=Extractor()
                    return self.reply(200,app.model.extract(text))
            except (ValueError,TypeError,json.JSONDecodeError):return self.reply(400,{'error':'请输入 1 至 128 字，并选择有效抽取模式'})
            except (ImportError,FileNotFoundError):return self.reply(503,{'error':'缺少 TensorFlow 或模型文件。请安装依赖并训练，或选择词典基线。'})
            except Exception as error:
                print('Extraction error:',repr(error),flush=True)
                return self.reply(500,{'error':'模型推理失败，请查看服务日志'})

    return Handler


def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);args=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(App()))
    print(f'打开 http://127.0.0.1:{args.port} ；Ctrl+C 停止',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()

"""仅绑定本机的教学 Web 服务；界面不依赖 CDN。"""
import argparse
import mimetypes
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from .common import *
from .graph import KnowledgeBase
from .qa import answer


class App:
    def __init__(self,model_dir=None):
        self.model_dir=Path(model_dir or ROOT/'models')
        self.kb=KnowledgeBase();self.model=None;self.model_lock=threading.Lock()

    def evaluation(self,name):
        path=self.model_dir/name
        if not path.exists():
            if self.model_dir.resolve()!=(ROOT/'models').resolve():return None
            path=ROOT/'reports'/name
        if not path.exists():return None
        report=read_json(path)
        signature=report.get('model_signature')
        if signature:
            return report if signature==model_signature(self.model_dir) else None
        metrics_path=self.model_dir/'metrics.json'
        legacy=metrics_path.exists() and not read_json(metrics_path).get('model_signature')
        return report if legacy and self.model_dir.resolve()==(ROOT/'models').resolve() else None

    def stats(self):
        from collections import Counter
        return {'items':len(self.kb.rows),'nodes':len(self.kb.graph['nodes']),'edges':len(self.kb.graph['edges']),
                'categories':dict(Counter(r['category'] for r in self.kb.rows)),
                'model_ready':all((self.model_dir/name).exists() for name in ('ner.weights.h5','relation.weights.h5','vocab.json')),
                'model_name':self.model_dir.name,
                'external_items':sum(row.get('provenance')=='external_dataset' for row in self.kb.rows),
                'backend':'local_json','region':'上海四分类名称映射',
                'region_note':'外部数据来源地区未核验','sources':read_json(DATA/'sources.json')}


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
                if url.path=='/api/search':return self.reply(200,app.kb.search(arg('q'),arg('category'),int(arg('limit','30')),int(arg('offset','0')),arg('scope','all')))
                if url.path=='/api/graph':return self.reply(200,app.kb.subgraph(arg('q'),arg('category'),int(arg('limit','24')),arg('scope','all'),int(arg('offset')) if 'offset' in query else None))
                if url.path=='/api/qa':return self.reply(200,answer(app.kb,arg('q')))
                if url.path=='/api/dataset':
                    audit_path=DATA/'old'/'imported'/'audit.json'
                    audit=read_json(audit_path) if audit_path.exists() else {}
                    return self.reply(200,{'available':bool(audit),'summary':audit.get('summary'),
                                          'conflicts':audit.get('conflicts',[])[:20]})
                if url.path=='/api/metrics':
                    metrics=app.evaluation('metrics.json')
                    return self.reply(200,{'available':metrics is not None,'metrics':metrics,
                                           'model_name':app.model_dir.name,
                                           'history':read_json(app.model_dir/'history.json') if metrics is not None and (app.model_dir/'history.json').exists() else [],
                                           'challenge':app.evaluation('challenge_metrics.json'),
                                           'web':app.evaluation('web_metrics.json')})
                allowed={'/':'index.html','/app.js':'app.js','/graph-layout.js':'graph-layout.js','/style.css':'style.css'}
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
                mode=payload.get('mode','hybrid')
                if mode=='baseline':
                    from .inference import baseline
                    return self.reply(200,baseline(text))
                if mode not in ('neural','hybrid'):raise ValueError()
                with app.model_lock:
                    if app.model is None:
                        from .inference import Extractor
                        app.model=Extractor(app.model_dir)
                    if mode=='hybrid':
                        from .inference import assisted_extract
                        return self.reply(200,assisted_extract(app.model,text))
                    return self.reply(200,app.model.extract(text))
            except (ValueError,TypeError,json.JSONDecodeError):return self.reply(400,{'error':'请输入 1 至 128 字，并选择有效抽取模式'})
            except (ImportError,FileNotFoundError):return self.reply(503,{'error':'缺少 TensorFlow 或模型文件。请安装依赖并训练，或选择词典基线。'})
            except Exception as error:
                print('Extraction error:',repr(error),flush=True)
                return self.reply(500,{'error':'模型推理失败，请查看服务日志'})

    return Handler


def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765)
    p.add_argument('--model-dir',type=Path,default=ROOT/'models');args=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(App(args.model_dir)))
    print(f'打开 http://127.0.0.1:{args.port} ；Ctrl+C 停止',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()

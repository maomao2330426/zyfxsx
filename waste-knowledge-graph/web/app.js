'use strict';
const $ = s => document.querySelector(s);
const colors = {'可回收物':'#568bb2','干垃圾':'#8c8a81','湿垃圾':'#689577','有害垃圾':'#bf7466'};
let category='', search='', latest=[], currentGraph, resultLimit=24;
function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
async function api(url,options){const r=await fetch(url,options);const d=await r.json();if(!r.ok)throw Error(d.error||'请求失败');return d;}
function error(e){$('#global-error').textContent=e.message;$('#global-error').hidden=false;}
function safeLink(url,label){const a=el('a','source-link',label);if(/^https?:\/\//i.test(url)){a.href=url;a.target='_blank';a.rel='noopener noreferrer';}return a;}
function detail(row){$('#detail-title').textContent=row.name;const box=$('#detail-content');box.replaceChildren();box.append(el('span','tag',row.category),el('strong','', '投放要求'),el('p','',row.method),el('strong','', '适用条件'),el('p','',row.note),el('strong','', '来源与状态'),el('p','',row.provenance==='curated_example'?'人工编制 · 教学示例':'人工审核的网页候选'),safeLink(row.source_url,'查看分类依据 ↗'));}
async function refresh(){
  $('#global-error').hidden=true;
  const params=new URLSearchParams({q:search,category,limit:'24'});
  const listParams=new URLSearchParams({q:search,category,limit:String(resultLimit)});
  const [result,graph]=await Promise.all([api('/api/search?'+listParams),api('/api/graph?'+params)]);
  latest=result.items;currentGraph=graph;drawGraph(graph);
  $('#result-count').textContent=`共 ${result.total} 条，当前展示 ${result.items.length} 条`;
  $('#results').replaceChildren();
  result.items.forEach(row=>{const b=el('button','result-item');b.append(el('strong','',row.name),el('small','',row.category+' · '+row.method));b.addEventListener('click',()=>detail(row));$('#results').append(b);});
  if(!result.items.length){$('#results').append(el('div','no-results','暂未找到相关条目。试试具体物品名称，或清除分类筛选。'));$('#detail-title').textContent='暂未收录';$('#detail-content').replaceChildren(el('p','',result.notice));}
  else if(search)detail(result.items[0]);
  $('#show-more').hidden=result.items.length>=result.total;
}
function svgEl(tag,attrs,text){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs||{}))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=text;return n;}
function drawGraph(graph){
  const svg=$('#graph');svg.replaceChildren();$('#graph-count').textContent=`${graph.nodes.length} 个节点 · ${graph.edges.length} 条关联`;
  if(!graph.nodes.length)return;
  const nodes=graph.nodes.map(n=>({...n}));const lookup=new Map(nodes.map(n=>[n.id,n]));
  const cats=nodes.filter(n=>n.kind==='CATEGORY');
  const centers=[[240,170],[620,170],[240,370],[620,370]];
  cats.forEach((c,i)=>{const center=cats.length===1?[380,260]:centers[i];c.x=center[0];c.y=center[1];c.color=colors[c.name];
    const items=graph.edges.filter(e=>e.target===c.id&&e.relation==='BELONGS_TO').map(e=>lookup.get(e.source));
    items.forEach((n,j)=>{const angle=(j/items.length)*Math.PI*2-.6;n.x=c.x+120*Math.cos(angle);n.y=c.y+77*Math.sin(angle);n.color=c.color;});
  });
  const methods=nodes.filter(n=>n.kind==='METHOD');methods.forEach((n,i)=>{n.x=80+i*700/Math.max(1,methods.length-1);n.y=i%2===0?38:505;n.color='#a8b5a0';});
  const links=svgEl('g',{'stroke-width':1});svg.append(links);
  const edgeElements=graph.edges.map(e=>{const line=svgEl('line',{stroke:e.relation==='BELONGS_TO'?'#c3d4bc':'#e0e6dc','stroke-dasharray':e.relation==='DISPOSE_WITH'?'4 4':''});links.append(line);return {line,e};});
  function updateLines(){edgeElements.forEach(({line,e})=>{const a=lookup.get(e.source),b=lookup.get(e.target);Object.entries({x1:a.x,y1:a.y,x2:b.x,y2:b.y}).forEach(([k,v])=>line.setAttribute(k,v));});}
  updateLines();
  nodes.forEach(n=>{const g=svgEl('g',{class:'node',transform:`translate(${n.x},${n.y})`,tabindex:0,role:'button','aria-label':n.name});
    const isCat=n.kind==='CATEGORY',isMethod=n.kind==='METHOD';
    g.append(svgEl('circle',{r:isCat?34:isMethod?6:11,fill:isCat?n.color:isMethod?'#eff3eb':'#fff',stroke:n.color,'stroke-width':isCat?0:2}));
    g.append(svgEl('text',{'text-anchor':'middle',y:isCat?4:isMethod?-12:29,'font-size':isCat?16:isMethod?12:14,fill:isCat?'#fff':'#537054'},n.name));
    const title=svgEl('title',{},`${n.name} · ${n.kind==='ITEM'?'物品':isCat?'类别':'投放要求'}`);g.append(title);
    const choose=async()=>{if(isCat){category=n.name;setChips();await refresh();}else if(n.kind==='ITEM'){let row=latest.find(r=>r.name===n.name);if(!row){const result=await api('/api/search?q='+encodeURIComponent(n.name));row=result.items[0];}if(row)detail(row);}};
    let moved=false,startPoint;
    g.addEventListener('pointerdown',ev=>{moved=false;startPoint=[ev.clientX,ev.clientY];g.setPointerCapture(ev.pointerId);});
    g.addEventListener('pointermove',ev=>{if(!g.hasPointerCapture(ev.pointerId))return;if(Math.hypot(ev.clientX-startPoint[0],ev.clientY-startPoint[1])<4)return;moved=true;const p=svg.createSVGPoint();p.x=ev.clientX;p.y=ev.clientY;const local=p.matrixTransform(svg.getScreenCTM().inverse());n.x=Math.max(30,Math.min(830,local.x));n.y=Math.max(35,Math.min(500,local.y));g.setAttribute('transform',`translate(${n.x},${n.y})`);updateLines();});
    g.addEventListener('pointerup',ev=>{g.releasePointerCapture(ev.pointerId);if(!moved)choose().catch(error);});
    g.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();choose().catch(error);}});svg.append(g);
  });
}
function setChips(){document.querySelectorAll('.chip').forEach(b=>b.classList.toggle('active',b.dataset.category===category));}
$('#search-form').addEventListener('submit',ev=>{ev.preventDefault();search=$('#query').value.trim();refresh().catch(error);});
document.querySelectorAll('.chip').forEach(b=>b.addEventListener('click',()=>{category=b.dataset.category;setChips();refresh().catch(error);}));
document.querySelectorAll('[data-example]').forEach(b=>b.addEventListener('click',()=>{search=b.dataset.example;category='';$('#query').value=search;setChips();refresh().catch(error);}));
$('#reset-graph').addEventListener('click',()=>drawGraph(currentGraph));
document.querySelectorAll('.nav').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.panel').forEach(x=>x.hidden=x.id!==b.dataset.panel);$('#breadcrumb').textContent=b.textContent.trim().slice(1).trim();if(b.dataset.panel==='experiment')experiments().catch(error);}));
$('#extract-button').addEventListener('click',async()=>{const button=$('#extract-button'),box=$('#extract-result');button.disabled=true;button.textContent='正在分析…';box.replaceChildren(el('p','muted','正在加载并运行模型，请稍候…'));try{const d=await api('/api/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:$('#sentence').value,mode:$('input[name="mode"]:checked').value})});box.replaceChildren(el('p','muted',d.mode==='neural'?'BiLSTM-CRF + BiGRU-Attention':'词典规则基线'));const ents=el('div');d.entities.forEach(e=>ents.append(el('span','entity-tag',e.text+' / '+e.type)));box.append(ents);d.triples.forEach(t=>{const card=el('div','triple',`${t.head} → ${t.relation==='BELONGS_TO'?'属于':'投放要求'} → ${t.tail}`);card.append(el('small','',`待人工审核${t.confidence!==null?' · 关系分数 '+(100*t.confidence).toFixed(1)+'%':''}`));box.append(card);});if(!d.triples.length)box.append(el('p','muted','未提取到符合阈值的肯定关系，可调整句子后重试。'));box.append(el('p','muted',d.note));}catch(e){box.replaceChildren(el('p','error',e.message));}finally{button.disabled=false;button.textContent='分析文本';}});
function table(headers,rows){const wrap=el('div','table-wrap'),t=el('table'),head=el('thead'),hr=el('tr');headers.forEach(x=>{const th=el('th','',x);th.scope='col';hr.append(th);});head.append(hr);t.append(head);const body=el('tbody');rows.forEach(row=>{const tr=el('tr');row.forEach(x=>tr.append(el('td','',String(x))));body.append(tr);});t.append(body);wrap.append(t);return wrap;}
async function experiments(){const d=await api('/api/metrics'),box=$('#experiment-content');box.replaceChildren();if(!d.available){box.append(el('p','', '训练结果尚未生成，请运行项目训练命令。'));return;}const m=d.metrics;box.append(el('p','footnote',m.limitation));const row=el('div','metric-row');[['实体严格 F1',m.ner.f1],['关系宏平均 F1',m.relation.macro_f1],['关系准确率',m.relation.accuracy]].forEach(([name,value])=>{const c=el('div','white-card');c.append(el('p','',name),el('strong','',(value*100).toFixed(1)+'%'));row.append(c);});box.append(row);const extra=el('section','white-card');extra.append(el('h2','','模板外表现与使用范围'),el('p','','下面的分数包含实体识别、关系抽取与阈值过滤，不能与上方使用金标准实体的关系指标混用。'));
  const extraRows=[];
  if(d.challenge)extraRows.push(['改写开发集（20句）',(100*d.challenge.ner.f1).toFixed(1)+'%',(100*d.challenge.end_to_end.neural.f1).toFixed(1)+'%','曾用于指导数据增强，非盲测']);
  if(d.web)extraRows.push(['网页原句（'+d.web.unique_sentences+'句）',(100*d.web.ner.f1).toFixed(1)+'%',(100*d.web.end_to_end.f1).toFixed(1)+'%','小样本单人标注，不能代表生产效果']);
  if(extraRows.length)extra.append(table(['评测集合','实体严格 F1','端到端三元组 F1','适用限制'],extraRows));
  box.append(extra);
  const config=el('section','white-card');config.append(el('h2','', '实验设置'),el('p','',`训练 / 验证 / 测试：${m.dataset.train} / ${m.dataset.val} / ${m.dataset.test} 句。随机种子 ${m.seed}，最佳轮次 ${m.best_epoch}，用时 ${m.seconds.toFixed(1)} 秒。`),el('p','', 'NER 按实体边界与类型严格匹配；关系分类使用金标准实体位置，分数不等于端到端三元组准确率。'));box.append(config);const chartCard=el('section','white-card');chartCard.append(el('h2','', '验证集 F1 随训练轮次变化'));const s=svgEl('svg',{viewBox:'0 0 900 230',class:'chart',role:'img','aria-label':'绿色为实体F1，蓝色为关系宏平均F1'});[0,.5,1].forEach(v=>{const y=190-v*155;s.append(svgEl('line',{x1:42,y1:y,x2:860,y2:y,stroke:'#e2e8de'}),svgEl('text',{x:10,y:y+5,'font-size':11,fill:'#809077'},String(v)));});[['val_ner_f1','#568b5e'],['val_relation_macro_f1','#538aaa']].forEach(([k,color])=>{s.append(svgEl('polyline',{points:d.history.map((r,i)=>`${45+i*810/Math.max(1,d.history.length-1)},${190-r[k]*155}`).join(' '),fill:'none',stroke:color,'stroke-width':2.5}));});chartCard.append(s,el('p','muted','绿色：实体严格 F1；蓝色：关系宏平均 F1。模型选择只使用验证集。'));box.append(chartCard);const matrix=el('section','white-card');matrix.append(el('h2','','关系混淆矩阵'),el('p','muted','行是真实标签，列是预测标签。'),table(['真实 / 预测',...m.relation.label_order],m.relation.confusion_matrix.map((r,i)=>[m.relation.label_order[i],...r])));box.append(matrix);const errors=el('section','white-card');errors.append(el('h2','','错误案例'),table(['原句','真实关系','预测关系'],m.errors.slice(0,10).map(e=>[e.text,e.gold_relation,e.predicted_relation])));box.append(errors);}
async function init(){const d=await api('/api/stats');$('#stat-items').textContent=d.items;$('#stat-nodes').textContent=d.nodes;$('#stat-edges').textContent=d.edges;const s=$('#sources-content');d.sources.forEach(r=>{const c=el('section','white-card');c.append(el('h2','',r.purpose),el('p','',r.kind==='encyclopedia'?'百科网页 · 采集实验':'政府公开资料 · 分类依据'),safeLink(r.url,r.url));if(r.license)c.append(el('p','muted',r.license));s.append(c);});await refresh();}
$('#show-more').addEventListener('click',()=>{resultLimit=150;refresh().catch(error);});
init().catch(error);

'use strict';
const $ = s => document.querySelector(s);
const colors = {'可回收物':'#568bb2','干垃圾':'#8c8a81','湿垃圾':'#689577','有害垃圾':'#bf7466'};
let category='', search='', latest=[], currentGraph, scope='all', pageOffset=0, nextOffset=null, refreshVersion=0, pageSize=12;
function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
async function api(url,options){const r=await fetch(url,options);const d=await r.json();if(!r.ok)throw Error(d.error||'请求失败');return d;}
function error(e){$('#global-error').textContent=e.message;$('#global-error').hidden=false;}
function safeLink(url,label){const a=el('a','source-link',label);if(/^https?:\/\//i.test(url)){a.href=url;a.target='_blank';a.rel='noopener noreferrer';}return a;}
function provenance(row){return row.provenance==='external_dataset'?'外部来源标签 · 未逐条审核':row.provenance==='curated_example'?'人工编制 · 教学示例':'人工审核的网页候选';}
function detail(row){
  $('#graph-selection').replaceChildren(el('strong','',row.name+' · '+row.category),el('span','',provenance(row)),safeLink(row.source_url,'查看分类证据 ↗'));
  $('#detail-title').textContent=row.name;
  const box=$('#detail-content');box.replaceChildren();
  box.append(el('span','tag',row.category),el('strong','','投放要求'),el('p','',row.method||'来源未提供，不自动补造'),el('strong','','适用条件'),el('p','',row.note),el('strong','','来源与状态'),el('p','',provenance(row)),el('p','muted','地区：'+row.region),el('strong','','分类证据'),el('p','',row.evidence),safeLink(row.source_url,'查看分类来源 ↗'));
  if(row.method){const evidence=row.method_provenance||row;box.append(el('strong','','投放依据'),el('p','',evidence.method_evidence||'教学目录中的投放示例，需结合物品状态核对。'),safeLink(evidence.source_url,'查看投放依据 ↗'));}
}
async function refresh(offset=0){
  const requestId=++refreshVersion;
  $('#global-error').hidden=true;
  const params=new URLSearchParams({q:search,category,limit:String(pageSize),offset:String(offset),scope});
  const listParams=new URLSearchParams(params);
  try{
    const [result,graph]=await Promise.all([api('/api/search?'+listParams),api('/api/graph?'+params)]);
    if(requestId!==refreshVersion)return;
    pageOffset=result.offset;nextOffset=result.next_offset;
    latest=result.items;currentGraph=graph;drawGraph(graph);
    $('#result-count').textContent='共 '+result.total+' 条，当前展示 '+result.items.length+' 条';
    $('#results').replaceChildren();
    result.items.forEach(row=>{const button=el('button','result-item');button.append(el('strong','',row.name),el('small','',row.category+' · '+(row.method||'未提供投放方法')),el('small','provenance-label',provenance(row)));button.addEventListener('click',()=>detail(row));$('#results').append(button);});
    if(!result.items.length){$('#results').append(el('div','no-results','暂未找到相关条目。试试具体名称，或清除筛选。'));$('#detail-title').textContent='暂未收录';$('#detail-content').replaceChildren(el('p','',result.notice));$('#graph-selection').replaceChildren();}
    else detail(result.items[0]);
    $('#previous-page').disabled=pageOffset===0;
    $('#show-more').disabled=nextOffset===null;
    $('#page-number').textContent=result.total?'第 '+(Math.floor(pageOffset/pageSize)+1)+' / '+Math.ceil(result.total/pageSize)+' 页':'无匹配结果';
    $('#graph-page').textContent=$('#page-number').textContent;
    $('#graph-previous').disabled=pageOffset===0;$('#graph-next').disabled=nextOffset===null;
  }catch(failure){if(requestId===refreshVersion)throw failure;}
}
function svgEl(tag,attrs,text){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v]of Object.entries(attrs||{}))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=text;return n;}
let graphView=null;
function paintView(){
  if(!graphView)return;
  const view=graphView.view;
  $('#graph').setAttribute('viewBox',[view.x,view.y,view.width,view.height].join(' '));
  $('#graph-zoom').textContent=Math.round(graphView.zoom*100)+'%';
}
function fitGraph(){
  if(!graphView)return;
  $('#graph').style.removeProperty('height');$('#graph-viewport').scrollTop=0;
  graphView.view={...WasteGraphLayout.bounds(graphView.nodes)};graphView.zoom=1;paintView();
}
function zoomGraph(factor,anchor){
  if(!graphView)return;
  const zoom=Math.min(5,Math.max(.3,graphView.zoom*factor));
  factor=zoom/graphView.zoom;
  const view=graphView.view;
  const center=anchor||{x:view.x+view.width/2,y:view.y+view.height/2};
  graphView.view={x:center.x-(center.x-view.x)/factor,y:center.y-(center.y-view.y)/factor,width:view.width/factor,height:view.height/factor};
  graphView.zoom=zoom;paintView();
}
function graphPoint(event){
  const rect=$('#graph').getBoundingClientRect(),view=graphView.view;
  const width=rect.width||860,height=rect.height||540;
  const scale=Math.min(width/view.width,height/view.height);
  return {x:view.x+(event.clientX-rect.left-(width-view.width*scale)/2)/scale,y:view.y+(event.clientY-rect.top-(height-view.height*scale)/2)/scale};
}
function drawGraph(graph){
  const svg=$('#graph');svg.replaceChildren();
  const count=graph.nodes.filter(node=>node.kind==='ITEM').length;
  $('#graph-count').textContent='本页 '+count+' / 共 '+graph.total_items+' 个物品 · '+graph.nodes.length+' 节点 · '+graph.edges.length+' 关联';
  const width=svg.parentElement.clientWidth||1100;
  const layout=WasteGraphLayout.layout(graph,width);
  svg.style.height=Math.ceil(Math.max(520,layout.bounds.height*Math.min(1,width/layout.bounds.width)))+'px';
  $('#graph-viewport').scrollTop=0;
  graphView={nodes:layout.nodes,view:{...layout.bounds},zoom:1,layoutWidth:width};paintView();
  if(!graph.nodes.length){svg.append(svgEl('text',{x:430,y:260,'text-anchor':'middle',class:'graph-empty'},'当前筛选暂无物品，请调整查询。'));return;}
  const lookup=new Map(layout.nodes.map(node=>[node.id,node]));
  const definitions=svgEl('defs'),marker=svgEl('marker',{id:'relation-arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:5,markerHeight:5,orient:'auto-start-reverse'});
  marker.append(svgEl('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#819781'}));definitions.append(marker);svg.append(definitions);
  const links=svgEl('g',{'aria-hidden':'true'});svg.append(links);
  const edges=graph.edges.map(edge=>{
    const path=svgEl('path',{class:'graph-edge '+(edge.relation==='DISPOSE_WITH'?'method-edge':''),'marker-end':'url(#relation-arrow)'});
    path.append(svgEl('title',{},edge.label+' · '+edge.review_status+' · '+edge.evidence));links.append(path);return {path,edge};
  });
  function updatePaths(){
    const leftLane=Math.min(...layout.nodes.map(node=>node.x-node.width/2))-20;
    const rightLane=Math.max(...layout.nodes.map(node=>node.x+node.width/2))+20;
    edges.forEach(({path,edge})=>{
      const source=lookup.get(edge.source),target=lookup.get(edge.target),direction=target.x>=source.x?1:-1;
      if(graphView.layoutWidth<760){
        if(edge.relation==='BELONGS_TO'){
          const from=source.y-source.height/2;
          path.setAttribute('d','M '+source.x+' '+from+' V '+(from-18)+' H '+leftLane+' V '+target.y+' H '+(target.x-target.width/2));
        }else{
          const from=source.y+source.height/2,to=target.y-target.height/2;
          path.setAttribute('d','M '+source.x+' '+from+' V '+(from+18)+' H '+rightLane+' V '+(to-18)+' H '+target.x+' V '+to);
        }
        return;
      }
      const from=source.x+direction*source.width/2,to=target.x-direction*target.width/2,middle=(from+to)/2;
      path.setAttribute('d','M '+from+' '+source.y+' C '+middle+' '+source.y+', '+middle+' '+target.y+', '+to+' '+target.y);
    });
  }
  updatePaths();
  const groups=new Map();
  function highlight(id){
    const connected=new Set([id]);
    edges.forEach(({edge})=>{if(edge.source===id||edge.target===id){connected.add(edge.source);connected.add(edge.target);}});
    groups.forEach((group,key)=>group.classList.toggle('graph-muted',Boolean(id)&&!connected.has(key)));
    edges.forEach(({path,edge})=>{path.classList.toggle('graph-muted',Boolean(id)&&edge.source!==id&&edge.target!==id);path.classList.toggle('graph-edge-active',edge.source===id||edge.target===id);});
  }
  layout.nodes.forEach(node=>{
    const color=colors[node.category||node.name]||'#7c9471';
    const group=svgEl('g',{class:'node graph-node '+node.kind.toLowerCase(),transform:'translate('+node.x+','+node.y+')',tabindex:0,role:'button','data-node-id':node.id,'aria-label':node.name});
    group.append(svgEl('rect',{x:-node.width/2,y:-node.height/2,width:node.width,height:node.height,rx:12,fill:node.kind==='CATEGORY'?color:'#fff',stroke:color,'stroke-width':1.5}));
    const text=svgEl('text',{'text-anchor':'middle',fill:node.kind==='CATEGORY'?'#fff':'#314d39',class:'graph-label'});
    node.lines.forEach((line,index)=>text.append(svgEl('tspan',{x:0,y:(index-(node.lines.length-1)/2)*22+5},line)));
    group.append(text,svgEl('title',{},node.name+' · '+(node.kind==='ITEM'?'点击查看物品证据':node.kind==='CATEGORY'?'点击筛选类别':'点击查看投放来源')));
    const choose=async()=>{
      if(node.kind==='CATEGORY'){category=node.name;setChips();await refresh();}
      else if(node.kind==='ITEM'){const row=latest.find(item=>item.name===node.name);if(row)detail(row);}
      else {
        const evidence=graph.edges.filter(edge=>edge.target===node.id);
        $('#detail-title').textContent=node.name;const box=$('#detail-content');box.replaceChildren(el('p','','投放要求 · 以下关系均保留原始来源'));
        evidence.forEach(edge=>box.append(el('p','',lookup.get(edge.source).name+'：'+edge.evidence),safeLink(edge.source_url,'查看来源 ↗')));
        $('#graph-selection').replaceChildren(el('strong','',node.name),el('span','','关联 '+evidence.length+' 个物品；详细来源见右侧详情。'));
      }
    };
    let drag=null;
    group.addEventListener('pointerdown',event=>{if(event.button!==0)return;event.stopPropagation();const point=graphPoint(event);drag={point,x:node.x,y:node.y,moved:false};group.setPointerCapture?.(event.pointerId);});
    group.addEventListener('pointermove',event=>{if(!drag)return;event.stopPropagation();const point=graphPoint(event);if(Math.hypot(point.x-drag.point.x,point.y-drag.point.y)>3)drag.moved=true;if(!drag.moved)return;node.x=drag.x+point.x-drag.point.x;node.y=drag.y+point.y-drag.point.y;group.setAttribute('transform','translate('+node.x+','+node.y+')');updatePaths();});
    group.addEventListener('pointerup',event=>{if(!drag)return;event.stopPropagation();const moved=drag.moved;drag=null;group.releasePointerCapture?.(event.pointerId);if(!moved)choose().catch(error);});
    group.addEventListener('pointercancel',()=>{drag=null;});
    group.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();choose().catch(error);}});
    group.addEventListener('mouseenter',()=>highlight(node.id));group.addEventListener('mouseleave',()=>highlight(null));
    group.addEventListener('focus',()=>highlight(node.id));group.addEventListener('blur',()=>highlight(null));
    groups.set(node.id,group);svg.append(group);
  });
}
let pan=null;
$('#graph').addEventListener('pointerdown',event=>{if(!graphView||event.button!==0)return;pan={point:graphPoint(event),view:{...graphView.view}};$('#graph').setPointerCapture?.(event.pointerId);});
$('#graph').addEventListener('pointermove',event=>{if(!pan)return;const point=graphPoint(event);graphView.view.x+=pan.point.x-point.x;graphView.view.y+=pan.point.y-point.y;paintView();});
$('#graph').addEventListener('pointerup',event=>{pan=null;$('#graph').releasePointerCapture?.(event.pointerId);});
$('#graph').addEventListener('pointercancel',()=>{pan=null;});
$('#graph').addEventListener('wheel',event=>{if(!event.ctrlKey||!graphView)return;event.preventDefault();zoomGraph(event.deltaY<0?1.2:1/1.2,graphPoint(event));},{passive:false});
$('#zoom-in').addEventListener('click',()=>zoomGraph(1.25));
$('#zoom-out').addEventListener('click',()=>zoomGraph(.8));
$('#fit-graph').addEventListener('click',fitGraph);
function expandGraph(expanded){$('#graph-card').classList.toggle('expanded',expanded);document.body.classList.toggle('graph-expanded',expanded);$('#expand-graph').textContent=expanded?'退出大图':'展开大图';$('#expand-graph').setAttribute('aria-pressed',String(expanded));if(currentGraph)drawGraph(currentGraph);}
$('#expand-graph').addEventListener('click',()=>expandGraph(!$('#graph-card').classList.contains('expanded')));
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&$('#graph-card').classList.contains('expanded'))expandGraph(false);});
function reflowGraph(){
  const width=$('#graph-viewport').clientWidth;
  if(currentGraph&&graphView&&width>0&&Math.abs(width-graphView.layoutWidth)>1)drawGraph(currentGraph);
}
if(typeof ResizeObserver!=='undefined'){
  const observer=new ResizeObserver(reflowGraph);observer.observe($('#graph-viewport'));
}else window.addEventListener('resize',reflowGraph);
function setChips(){document.querySelectorAll('.chip').forEach(b=>b.classList.toggle('active',b.dataset.category===category));}
$('#search-form').addEventListener('submit',ev=>{ev.preventDefault();search=$('#query').value.trim();refresh().catch(error);});
document.querySelectorAll('.chip').forEach(b=>b.addEventListener('click',()=>{category=b.dataset.category;setChips();refresh().catch(error);}));
document.querySelectorAll('[data-example]').forEach(b=>b.addEventListener('click',()=>{search=b.dataset.example;category='';$('#query').value=search;setChips();refresh().catch(error);}));
$('#reset-graph').addEventListener('click',()=>{if(currentGraph)drawGraph(currentGraph);});
document.querySelectorAll('.nav').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.panel').forEach(x=>x.hidden=x.id!==b.dataset.panel);$('#breadcrumb').textContent=b.textContent.trim().slice(1).trim();if(b.dataset.panel==='experiment')experiments().catch(error);}));
$('#extract-button').addEventListener('click',async()=>{const button=$('#extract-button'),box=$('#extract-result');button.disabled=true;button.textContent='正在分析…';box.replaceChildren(el('p','muted','正在加载并运行模型，请稍候…'));try{const d=await api('/api/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:$('#sentence').value,mode:$('input[name="mode"]:checked').value})});box.replaceChildren(el('p','muted',d.mode==='neural'?'BiLSTM-CRF + BiGRU-Attention':'词典规则基线'));const ents=el('div');d.entities.forEach(e=>ents.append(el('span','entity-tag',e.text+' / '+e.type)));box.append(ents);d.triples.forEach(t=>{const card=el('div','triple',`${t.head} → ${t.relation==='BELONGS_TO'?'属于':'投放要求'} → ${t.tail}`);card.append(el('small','',`待人工审核${t.confidence!==null?' · 关系分数 '+(100*t.confidence).toFixed(1)+'%':''}`));box.append(card);});if(!d.triples.length)box.append(el('p','muted','未提取到符合阈值的肯定关系，可调整句子后重试。'));box.append(el('p','muted',d.note));}catch(e){box.replaceChildren(el('p','error',e.message));}finally{button.disabled=false;button.textContent='分析文本';}});
function table(headers,rows){const wrap=el('div','table-wrap'),t=el('table'),head=el('thead'),hr=el('tr');headers.forEach(x=>{const th=el('th','',x);th.scope='col';hr.append(th);});head.append(hr);t.append(head);const body=el('tbody');rows.forEach(row=>{const tr=el('tr');row.forEach(x=>tr.append(el('td','',String(x))));body.append(tr);});t.append(body);wrap.append(t);return wrap;}
async function experiments(){const d=await api('/api/metrics'),box=$('#experiment-content');box.replaceChildren();if(!d.available){box.append(el('p','', '训练结果尚未生成，请运行项目训练命令。'));return;}const m=d.metrics;box.append(el('p','footnote','当前模型：'+d.model_name+'。'+m.limitation));if(d.model_name!=='models')box.append(el('p','error','独立实验模型：请先查看网页及改写集表现，不能仅凭模板高分替换默认模型。'));const row=el('div','metric-row');[['实体严格 F1',m.ner.f1],['关系宏平均 F1',m.relation.macro_f1],['关系准确率',m.relation.accuracy]].forEach(([name,value])=>{const c=el('div','white-card');c.append(el('p','',name),el('strong','',(value*100).toFixed(1)+'%'));row.append(c);});box.append(row);const extra=el('section','white-card');extra.append(el('h2','','模板外表现与使用范围'),el('p','','下面的分数包含实体识别、关系抽取与阈值过滤，不能与上方使用金标准实体的关系指标混用。'));
  const extraRows=[];
  if(d.challenge)extraRows.push(['改写开发集（20句）',(100*d.challenge.ner.f1).toFixed(1)+'%',(100*d.challenge.end_to_end.neural.f1).toFixed(1)+'%','曾用于指导数据增强，非盲测']);
  if(d.web)extraRows.push(['网页原句（'+d.web.unique_sentences+'句）',(100*d.web.ner.f1).toFixed(1)+'%',(100*d.web.end_to_end.f1).toFixed(1)+'%','小样本单人标注，不能代表生产效果']);
  if(extraRows.length)extra.append(table(['评测集合','实体严格 F1','端到端三元组 F1','适用限制'],extraRows));
  box.append(extra);
  const config=el('section','white-card');config.append(el('h2','', '实验设置'),el('p','',`训练 / 验证 / 测试：${m.dataset.train} / ${m.dataset.val} / ${m.dataset.test} 句。随机种子 ${m.seed}，最佳轮次 ${m.best_epoch}，用时 ${m.seconds.toFixed(1)} 秒。`),el('p','', 'NER 按实体边界与类型严格匹配；关系分类使用金标准实体位置，分数不等于端到端三元组准确率。'));box.append(config);const chartCard=el('section','white-card');chartCard.append(el('h2','', '验证集 F1 随训练轮次变化'));const s=svgEl('svg',{viewBox:'0 0 900 230',class:'chart',role:'img','aria-label':'绿色为实体F1，蓝色为关系宏平均F1'});[0,.5,1].forEach(v=>{const y=190-v*155;s.append(svgEl('line',{x1:42,y1:y,x2:860,y2:y,stroke:'#e2e8de'}),svgEl('text',{x:10,y:y+5,'font-size':11,fill:'#809077'},String(v)));});[['val_ner_f1','#568b5e'],['val_relation_macro_f1','#538aaa']].forEach(([k,color])=>{s.append(svgEl('polyline',{points:d.history.map((r,i)=>`${45+i*810/Math.max(1,d.history.length-1)},${190-r[k]*155}`).join(' '),fill:'none',stroke:color,'stroke-width':2.5}));});chartCard.append(s,el('p','muted','绿色：实体严格 F1；蓝色：关系宏平均 F1。模型选择只使用验证集。'));box.append(chartCard);const matrix=el('section','white-card');matrix.append(el('h2','','关系混淆矩阵'),el('p','muted','行是真实标签，列是预测标签。'),table(['真实 / 预测',...m.relation.label_order],m.relation.confusion_matrix.map((r,i)=>[m.relation.label_order[i],...r])));box.append(matrix);const errors=el('section','white-card');errors.append(el('h2','','错误案例'),table(['原句','真实关系','预测关系'],m.errors.slice(0,10).map(e=>[e.text,e.gold_relation,e.predicted_relation])));box.append(errors);}
async function datasetSummary(){
  const data=await api('/api/dataset');
  if(!data.available)return;
  const report=data.summary,card=el('section','white-card dataset-audit');
  card.append(el('h2','','新增数据集审计'),el('p','','原始 '+report.raw_records+' 条；新增 '+report.accepted_items+' 个物品；同名一致 '+report.existing_matches+' 组；冲突隔离 '+report.conflict_items+' 组；重复规范化 '+report.duplicate_records+' 条。'),el('p','','CSV / JSONL 一致性：'+(report.formats_match===true?'已核对一致':'未提供双格式校验')));
  card.append(table(['映射后分类','新增物品'],Object.entries(report.categories)),el('p','muted','描述字段非空 '+report.description_records+' 条。训练语句由标签弱监督生成，不是自然网页的实体标注；原模型不会因导入而自动更新。'));
  data.conflicts.forEach(conflict=>card.append(el('p','error','待审核：'+conflict.name+'，原目录 '+conflict.existing_category+'，外部 '+[...new Set(conflict.incoming.map(row=>row.category))].join(' / ')+'。冲突记录未进入新训练集。')));
  report.sources.forEach(url=>card.append(safeLink(url,'外部数据来源 ↗')));
  card.append(el('p','muted','输入 SHA-256：'+report.input_sha256));
  $('#sources-content').prepend(card);
}
async function init(){
  const data=await api('/api/stats');
  $('#stat-items').textContent=data.items;$('#stat-nodes').textContent=data.nodes;$('#stat-edges').textContent=data.edges;
  $('#backend-status').textContent='本地目录已连接';
  $('#dataset-note').textContent='外部标签 '+data.external_items+' 条 · 当前模型 '+data.model_name;
  if(!data.model_ready){$('input[name="mode"][value="baseline"]').checked=true;}
  const sources=$('#sources-content');
  data.sources.forEach(row=>{const card=el('section','white-card');card.append(el('h2','',row.purpose),el('p','',row.kind==='encyclopedia'?'百科网页 · 采集实验':'政府公开资料 · 分类依据'),safeLink(row.url,row.url));if(row.license)card.append(el('p','muted',row.license));sources.append(card);});
  await Promise.all([refresh(),datasetSummary()]);
}
$('#data-scope').addEventListener('change',()=>{scope=$('#data-scope').value;refresh().catch(error);});
$('#previous-page').addEventListener('click',()=>refresh(Math.max(0,pageOffset-pageSize)).catch(error));
$('#graph-previous').addEventListener('click',()=>refresh(Math.max(0,pageOffset-pageSize)).catch(error));
$('#graph-next').addEventListener('click',()=>{if(nextOffset!==null)refresh(nextOffset).catch(error);});
$('#page-size').addEventListener('change',()=>{pageSize=Number($('#page-size').value);refresh().catch(error);});
$('#qa-form').addEventListener('submit',async event=>{
  event.preventDefault();const button=event.currentTarget.querySelector('button'),box=$('#qa-result');
  button.disabled=true;box.replaceChildren(el('p','muted','正在检索目录证据…'));
  try{
    const data=await api('/api/qa?'+new URLSearchParams({q:$('#question').value}));
    box.replaceChildren(el('p','',data.answer));
    if(data.notice)box.append(el('p','muted',data.notice));
    data.items.forEach(row=>{const item=el('button','text-button',row.name+' · '+row.category+' · '+provenance(row));item.addEventListener('click',()=>detail(row));box.append(item);});
    data.triples.forEach(triple=>{const evidence=el('p','',triple.evidence);evidence.append(safeLink(triple.source_url,' 查看证据 ↗'));box.append(evidence);});
  }catch(failure){box.replaceChildren(el('p','error',failure.message));}finally{button.disabled=false;}
});
$('#show-more').addEventListener('click',()=>{if(nextOffset!==null)refresh(nextOffset).catch(error);});
init().catch(error);

const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const project=path.resolve(__dirname,'..');
const base=process.env.WASTEKG_TEST_URL||'http://127.0.0.1:18765';
const delay=milliseconds=>new Promise(resolve=>setTimeout(resolve,milliseconds));

async function waitFor(predicate){
  for(let attempt=0;attempt<100;attempt++){
    if(predicate())return;
    await delay(25);
  }
  throw new Error('Timed out waiting for DOM update');
}

async function app(width){
  const dom=new JSDOM(fs.readFileSync(path.join(project,'web/index.html'),'utf8'),{url:base,runScripts:'outside-only'});
  if(width)Object.defineProperty(dom.window.document.querySelector('#graph-viewport'),'clientWidth',{value:width,writable:true,configurable:true});
  dom.window.fetch=(url,options)=>fetch(new URL(url,base),options);
  dom.window.eval(fs.readFileSync(path.join(project,'web/graph-layout.js'),'utf8'));
  dom.window.eval(fs.readFileSync(path.join(project,'web/app.js'),'utf8'));
  await waitFor(()=>dom.window.document.querySelectorAll('.result-item').length===12&&dom.window.document.querySelector('.dataset-audit'));
  return dom;
}

test('pagination goes beyond 150 entries and scope resets the page',async()=>{
  const dom=await app();
  try{
    const document=dom.window.document;
    const pageSize=document.querySelector('#page-size');pageSize.value='24';
    pageSize.dispatchEvent(new dom.window.Event('change'));
    await waitFor(()=>document.querySelectorAll('.result-item').length===24);
    const first=document.querySelector('.result-item strong').textContent;
    for(let page=2;page<=8;page++){
      document.querySelector('#show-more').click();
      await waitFor(()=>document.querySelector('#page-number').textContent.startsWith('第 '+page+' /'));
    }
    assert.notEqual(document.querySelector('.result-item strong').textContent,first);
    const select=document.querySelector('#data-scope');select.value='external';
    select.dispatchEvent(new dom.window.Event('change'));
    await waitFor(()=>document.querySelector('#page-number').textContent.startsWith('第 1 /'));
    assert.match(document.querySelector('.provenance-label').textContent,/未逐条审核/);
    assert.match(document.querySelector('#detail-content').textContent,/未提供/);
    assert.equal(document.querySelector('#previous-page').disabled,true);
    assert.equal(document.querySelector('#global-error').hidden,true);
  }finally{dom.window.close();}
});

test('graph changes page with the list and supports zoom, fit and expanded view',async()=>{
  const dom=await app();
  try{
    const document=dom.window.document;
    const initial=[...document.querySelectorAll('.graph-node.item')].map(node=>node.getAttribute('aria-label'));
    document.querySelector('#graph-next').click();
    await waitFor(()=>document.querySelector('#graph-page').textContent.startsWith('第 2 /'));
    const current=[...document.querySelectorAll('.graph-node.item')].map(node=>node.getAttribute('aria-label'));
    const list=[...document.querySelectorAll('.result-item strong')].map(node=>node.textContent);
    assert.deepEqual(new Set(current),new Set(list));assert.notDeepEqual(current,initial);
    const svg=document.querySelector('#graph'),original=svg.getAttribute('viewBox');
    document.querySelector('#zoom-in').click();assert.notEqual(svg.getAttribute('viewBox'),original);
    document.querySelector('#fit-graph').click();assert.equal(svg.getAttribute('viewBox'),original);
    document.querySelector('#expand-graph').click();assert.equal(document.querySelector('#graph-card').classList.contains('expanded'),true);
    document.dispatchEvent(new dom.window.KeyboardEvent('keydown',{key:'Escape'}));
    assert.equal(document.querySelector('#graph-card').classList.contains('expanded'),false);
    assert.equal(document.querySelector('#global-error').hidden,true);
  }finally{dom.window.close();}
});

test('narrow graphs stay readable and resize without losing the current page',async()=>{
  const dom=await app(390);
  try{
    const document=dom.window.document,svg=document.querySelector('#graph'),viewport=document.querySelector('#graph-viewport');
    const initial=svg.getAttribute('viewBox').split(' ').map(Number);
    assert.ok(initial[2]<=390);
    assert.ok(parseFloat(svg.style.height)>=initial[3]);
    const names=[...document.querySelectorAll('.graph-node.item')].map(node=>node.getAttribute('aria-label'));
    document.querySelector('#fit-graph').click();assert.equal(svg.style.height,'');
    document.querySelector('#reset-graph').click();assert.ok(parseFloat(svg.style.height)>520);
    viewport.clientWidth=1400;dom.window.dispatchEvent(new dom.window.Event('resize'));
    assert.notEqual(svg.getAttribute('viewBox'),initial.join(' '));
    assert.deepEqual([...document.querySelectorAll('.graph-node.item')].map(node=>node.getAttribute('aria-label')),names);
    assert.equal(document.querySelector('#global-error').hidden,true);
  }finally{dom.window.close();}
});

test('wrapped labels retain long names and leave horizontal card padding',()=>{
  const {layout}=require('../web/graph-layout.js');
  for(const name of ['这是一个非常长的垃圾名称用来检查卡片文字边界','ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789','混合NameWithLongWords垃圾名称']){
    const result=layout({nodes:[{id:'item',name,kind:'ITEM'}],edges:[]},390),node=result.nodes[0];
    assert.equal(node.lines.join(''),name);
    for(const line of node.lines){
      const units=Array.from(line).reduce((total,character)=>total+(character.codePointAt(0)>255?1:.6),0);
      assert.ok(units*16<=node.width-28);
    }
  }
});

test('all label cards are disjoint and inside fit bounds at different sizes',async()=>{
  const {layout}=require('../web/graph-layout.js');
  const graph=await (await fetch(base+'/api/graph?'+new URLSearchParams({category:'有害垃圾',limit:'48',offset:'0'}))).json();
  for(const width of [320,390,650,759,760,860,1400]){
    const result=layout(graph,width),bounds=result.bounds;
    for(const node of result.nodes){
      assert.ok(node.x-node.width/2>=bounds.x&&node.x+node.width/2<=bounds.x+bounds.width);
      assert.ok(node.y-node.height/2>=bounds.y&&node.y+node.height/2<=bounds.y+bounds.height);
      assert.equal(node.lines.join(''),node.name);
    }
    for(let first=0;first<result.nodes.length;first++)for(let second=first+1;second<result.nodes.length;second++){
      const left=result.nodes[first],right=result.nodes[second];
      const overlap=Math.abs(left.x-right.x)<(left.width+right.width)/2&&Math.abs(left.y-right.y)<(left.height+right.height)/2;
      assert.equal(overlap,false,left.name+' overlaps '+right.name);
    }
  }
});

test('late search responses cannot overwrite the newest result',async()=>{
  const dom=await app();
  try{
    const document=dom.window.document;
    dom.window.fetch=async(url,options)=>{
      const target=new URL(url,base);
      const response=await fetch(target,options);
      if(target.searchParams.get('q')==='纸箱')await delay(250);
      return response;
    };
    const submit=value=>{document.querySelector('#query').value=value;document.querySelector('#search-form').dispatchEvent(new dom.window.Event('submit',{cancelable:true}));};
    submit('纸箱');submit('阿司匹林');
    await waitFor(()=>document.querySelector('#detail-title').textContent==='阿司匹林');
    await delay(350);
    assert.equal(document.querySelector('#detail-title').textContent,'阿司匹林');
  }finally{dom.window.close();}
});

test('QA and data audit expose provenance and conflicts',async()=>{
  const dom=await app();
  try{
    const document=dom.window.document;
    document.querySelector('#question').value='阿司匹林是什么垃圾？';
    document.querySelector('#qa-form').dispatchEvent(new dom.window.Event('submit',{cancelable:true}));
    await waitFor(()=>document.querySelector('#qa-result').textContent.includes('外部数据集标注'));
    assert.match(document.querySelector('#qa-result').textContent,/外部数据集标注/);
    assert.match(document.querySelector('#qa-result').textContent,/未逐条人工核验/);
    const source=await (await fetch(base+'/api/search?'+new URLSearchParams({q:'阿司匹林'}))).json();
    assert.ok(document.querySelector('#qa-result').textContent.includes(source.items[0].method));
    assert.match(document.querySelector('#qa-result a').href,/^https:/);
    await waitFor(()=>document.querySelector('.dataset-audit'));
    assert.match(document.querySelector('.dataset-audit').textContent,/竹签/);
    document.querySelector('[data-panel="experiment"]').click();
    await waitFor(()=>document.querySelectorAll('#experiment-content table').length>0);
    assert.equal(document.querySelector('#global-error').hidden,true);
  }finally{dom.window.close();}
});

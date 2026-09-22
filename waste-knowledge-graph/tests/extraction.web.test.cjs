const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const project=path.resolve(__dirname,'..');
const base=process.env.WASTEKG_TEST_URL||'http://127.0.0.1:18765';
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function waitFor(predicate){
  for(let i=0;i<300;i++){if(predicate())return;await delay(100);}
  throw new Error('Timed out waiting for extraction UI');
}
test('recommended extraction uses the actual API and labels rule backfills honestly',async()=>{
  const dom=new JSDOM(fs.readFileSync(path.join(project,'web/index.html'),'utf8'),{url:base,runScripts:'outside-only'});
  dom.window.fetch=(url,options)=>fetch(new URL(url,base),options);
  dom.window.eval(fs.readFileSync(path.join(project,'web/graph-layout.js'),'utf8'));
  dom.window.eval(fs.readFileSync(path.join(project,'web/app.js'),'utf8'));
  const d=dom.window.document;
  try{
    await waitFor(()=>d.querySelectorAll('.result-item').length===12&&d.querySelector('.dataset-audit'));
    assert.equal(d.querySelector('input[name="mode"]:checked').value,'hybrid');
    assert.equal(d.querySelectorAll('input[name="mode"]').length,3);
    for(const sentence of ['香蕉皮是湿垃圾',
        '一个表面已经发黑、还残留少量果肉和酸奶，并且刚刚从塑料保鲜袋里取出来的香蕉皮属于厨余垃圾。']){
      d.querySelector('#sentence').value=sentence;d.querySelector('#extract-button').click();
      await waitFor(()=>!d.querySelector('#extract-button').disabled);
      const cards=d.querySelectorAll('#extract-result .triple');
      assert.equal(cards.length,1,d.querySelector('#extract-result').textContent);
      assert.match(cards[0].textContent,/香蕉皮 → 属于 → (?:湿垃圾|厨余垃圾)/);
      assert.match(cards[0].textContent,/句式规则/);
      // Retraining can turn a former rule backfill into genuine model agreement.
      if(cards[0].textContent.includes('待人工审核 · 句式规则'))assert.doesNotMatch(cards[0].textContent,/%/);
      else assert.match(cards[0].textContent,/模型与句式规则一致.*模型关系分数/);
      assert.match(d.querySelector('#extract-result').textContent,/增强抽取/);
    }
    for(const mode of ['hybrid','baseline']){
      d.querySelector('input[value="'+mode+'"]').checked=true;
      d.querySelector('#sentence').value='香蕉皮属于湿垃圾,应该扔进垃圾桶里';
      d.querySelector('#extract-button').click();
      await waitFor(()=>!d.querySelector('#extract-button').disabled);
      const result=d.querySelector('#extract-result');
      assert.equal(result.querySelectorAll('.triple').length,2,result.textContent);
      assert.match(result.textContent,/香蕉皮 → 属于 → 湿垃圾/);
      assert.match(result.textContent,/香蕉皮 → 投放要求 → 扔进垃圾桶里/);
      assert.match(result.textContent,/扔进垃圾桶里 \/ METHOD/);
      assert.doesNotMatch(result.textContent,/垃圾桶 \/ ITEM/);
      const method=[...result.querySelectorAll('.triple')].find(c=>c.textContent.includes('投放要求'));
      if(method.textContent.includes('待人工审核 · 句式规则'))assert.doesNotMatch(method.textContent,/%/);
    }
    d.querySelector('input[value="baseline"]').checked=true;
    d.querySelector('#sentence').value='香蕉皮不是干垃圾，而是湿垃圾。';
    d.querySelector('#extract-button').click();
    await waitFor(()=>!d.querySelector('#extract-button').disabled);
    assert.equal(d.querySelectorAll('#extract-result .triple').length,1);
    assert.match(d.querySelector('#extract-result .triple').textContent,/香蕉皮 → 属于 → 湿垃圾/);
    d.querySelector('#sentence').value='香蕉皮是湿垃圾吗？';d.querySelector('#extract-button').click();
    await waitFor(()=>!d.querySelector('#extract-button').disabled);
    assert.equal(d.querySelectorAll('#extract-result .triple').length,0);
    assert.match(d.querySelector('#extract-result').textContent,/未找到可明确对应/);
    assert.equal(d.querySelector('#global-error').hidden,true,d.querySelector('#global-error').textContent);
  }finally{dom.window.close();}
});

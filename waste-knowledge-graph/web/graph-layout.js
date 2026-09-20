(function(root,factory){
  const layout=factory();
  if(typeof module==='object'&&module.exports)module.exports=layout;
  else root.WasteGraphLayout=layout;
})(globalThis,function(){
  function wrapLabel(text,capacity=10){
    const lines=[];let line='',units=0;
    for(const character of Array.from(text)){
      const width=character.codePointAt(0)>255?1:.6;
      if(units+width>capacity&&line){lines.push(line);line='';units=0;}
      line+=character;units+=width;
    }
    if(line)lines.push(line);
    return lines;
  }

  function bounds(nodes,padding=40){
    if(!nodes.length)return {x:0,y:0,width:860,height:540};
    const left=Math.min(...nodes.map(node=>node.x-node.width/2))-padding;
    const top=Math.min(...nodes.map(node=>node.y-node.height/2))-padding;
    const right=Math.max(...nodes.map(node=>node.x+node.width/2))+padding;
    const bottom=Math.max(...nodes.map(node=>node.y+node.height/2))+padding;
    return {x:left,y:top,width:right-left,height:bottom-top};
  }

  function layout(graph,viewportWidth=1100){
    const nodes=graph.nodes.map(node=>({...node,lines:wrapLabel(node.name),width:190,height:0}));
    nodes.forEach(node=>{node.height=Math.max(64,node.lines.length*22+28);});
    const lookup=new Map(nodes.map(node=>[node.id,node]));
    const categories=nodes.filter(node=>node.kind==='CATEGORY');
    const methods=nodes.filter(node=>node.kind==='METHOD');
    const items=nodes.filter(node=>node.kind==='ITEM');
    if(viewportWidth<760){
      const columns=Math.max(1,Math.min(3,Math.floor((viewportWidth-40)/230)));
      const center=120+(columns-1)*115;
      const placed=new Set();let cursor=60;
      function placeGrid(group){
        for(let start=0;start<group.length;start+=columns){
          const row=group.slice(start,start+columns),height=Math.max(...row.map(node=>node.height));
          row.forEach((node,index)=>{node.x=120+index*230;node.y=cursor+height/2;placed.add(node.id);});
          cursor+=height+44;
        }
      }
      categories.forEach(category=>{
        category.x=center;category.y=cursor+category.height/2;cursor+=category.height+64;
        const group=graph.edges.filter(edge=>edge.relation==='BELONGS_TO'&&edge.target===category.id).map(edge=>lookup.get(edge.source)).filter(Boolean);
        group.forEach(item=>{item.category=category.name;});placeGrid(group);cursor+=40;
      });
      placeGrid(items.filter(item=>!placed.has(item.id)));
      if(methods.length){cursor+=40;placeGrid(methods);}
      return {nodes,edges:graph.edges,bounds:bounds(nodes)};
    }
    const columns=viewportWidth<600?1:viewportWidth<1000?2:3;
    const rowHeight=Math.max(108,...items.map(node=>node.height+30));
    const maxColumns=Math.min(columns,Math.max(1,items.length));
    let cursor=60;
    categories.forEach(category=>{
      const group=graph.edges.filter(edge=>edge.relation==='BELONGS_TO'&&edge.target===category.id).map(edge=>lookup.get(edge.source)).filter(Boolean);
      const height=Math.max(category.height+40,Math.ceil(group.length/maxColumns)*rowHeight);
      category.x=120;category.y=cursor+height/2;
      group.forEach((item,index)=>{item.x=380+(index%maxColumns)*230;item.y=cursor+rowHeight/2+Math.floor(index/maxColumns)*rowHeight;item.category=category.name;});
      cursor+=height+70;
    });
    const unplaced=items.filter(item=>!Number.isFinite(item.x));
    unplaced.forEach((item,index)=>{item.x=380+(index%maxColumns)*230;item.y=cursor+rowHeight/2+Math.floor(index/maxColumns)*rowHeight;});
    cursor+=Math.ceil(unplaced.length/maxColumns)*rowHeight;
    const methodHeight=Math.max(120,...methods.map(node=>node.height+40));
    const totalHeight=Math.max(cursor-60,methods.length*methodHeight);
    methods.forEach((method,index)=>{method.x=380+maxColumns*230+40;method.y=60+(index+.5)*totalHeight/Math.max(1,methods.length);});
    return {nodes,edges:graph.edges,bounds:bounds(nodes)};
  }
  return {layout,bounds,wrapLabel};
});

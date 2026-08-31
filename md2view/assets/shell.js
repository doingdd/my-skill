/* md2view v4 shell — 交互
 * 双栏锚定同步、点击锁定映射、模式切换、分栏拖动、diagram 连线路由。
 * 右栏契约:[data-sources="b005 b006"] 标注来源;[data-node="id"] 图节点;
 * <i class="mv-edge" data-from data-to data-label data-kind> 声明连线(隐藏元数据,运行时绘制)。
 */
(function(){
  'use strict';
  var wrap=document.getElementById('split'),L=document.getElementById('paneL'),R=document.getElementById('paneR');
  var separator=document.querySelector('[data-md2view-separator]');
  var status=document.querySelector('[data-md2view-status]');
  var hint=document.querySelector('.hint');
  var compact=window.matchMedia('(max-width:767px)');
  var reduced=window.matchMedia('(prefers-reduced-motion:reduce)').matches;
  var driver=null,lock=false,pinned=null,pendingReveal=null,previewed=[],syncEls=[],drawQueued=false;
  var rIndex={},lIndex={};
  function idsOf(el){return (el.getAttribute('data-sources')||'').trim().split(/\s+/).filter(Boolean);}
  R.querySelectorAll('[data-sources]').forEach(function(el){
    idsOf(el).forEach(function(bid){(rIndex[bid]||(rIndex[bid]=[])).push(el);});
    if(!el.matches('button,a,input,select,textarea,[tabindex]'))el.tabIndex=0;
    if(!el.hasAttribute('role')&&!el.matches('button,a,input,select,textarea'))el.setAttribute('role','button');
    if(!el.hasAttribute('aria-label'))el.setAttribute('aria-label','定位原文:'+(el.getAttribute('data-label')||el.textContent.trim().slice(0,24)));
  });
  Object.keys(rIndex).forEach(function(bid){
    rIndex[bid].sort(function(a,b){var af=a.classList.contains('mv-fact')?0:1,bf=b.classList.contains('mv-fact')?0:1;return af-bf||idsOf(a).length-idsOf(b).length;});
  });
  L.querySelectorAll('[data-block]').forEach(function(el){
    var bid=el.getAttribute('data-block');lIndex[bid]=el;el.tabIndex=0;el.setAttribute('role','button');el.setAttribute('aria-label','定位信息重组:'+bid);
  });
  function setStatus(text){if(status)status.textContent=text;}
  function flashHint(text){if(!hint)return;hint.textContent=text;hint.classList.add('show');clearTimeout(flashHint.timer);flashHint.timer=setTimeout(function(){hint.classList.remove('show');},2200);}
  function storageGet(key){try{return localStorage.getItem(key);}catch(e){return null;}}
  function storageSet(key,value){try{localStorage.setItem(key,value);}catch(e){}}
  function anchorOf(pane,attr){
    var mid=pane.getBoundingClientRect().top+pane.clientHeight*.30,best=null,bd=1e9;
    pane.querySelectorAll('['+attr+']').forEach(function(el){var rect=el.getBoundingClientRect(),d=Math.abs(rect.top-mid);if(rect.height>0&&d<bd){bd=d;best=el;}});
    return best;
  }
  function clearClass(list,name){while(list.length)list.pop().classList.remove(name);}
  function mark(list,el,name){if(el&&!el.classList.contains(name)){el.classList.add(name);list.push(el);}}
  function align(dst,target,anchor,src,behavior){
    var aOff=anchor.getBoundingClientRect().top-src.getBoundingClientRect().top;
    var tOff=target.getBoundingClientRect().top-dst.getBoundingClientRect().top+dst.scrollTop;
    dst.scrollTo({top:Math.max(0,tOff-aOff),behavior:behavior||'auto'});
  }
  function revealTarget(pane,target,behavior){
    if(!pane||!target||getComputedStyle(pane).display==='none')return false;
    var paneRect=pane.getBoundingClientRect(),targetRect=target.getBoundingClientRect();
    if(paneRect.width<8||!paneRect.height||!targetRect.height)return false;
    var top=targetRect.top-paneRect.top+pane.scrollTop-pane.clientHeight*.36;
    pane.scrollTo({top:Math.max(0,top),behavior:behavior||(reduced?'auto':'smooth')});return true;
  }
  function revealPending(){if(pendingReveal&&revealTarget(pendingReveal.pane,pendingReveal.target,pendingReveal.behavior))pendingReveal=null;}
  function queueReveal(pane,target,behavior){pendingReveal={pane:pane,target:target,behavior:behavior};requestAnimationFrame(function(){requestAnimationFrame(revealPending);});}
  function firstSourceFor(el){
    if(!el)return null;
    if(L.contains(el)&&el.hasAttribute('data-block'))return el;
    var ids=idsOf(el);
    for(var i=0;i<ids.length;i++){if(lIndex[ids[i]])return lIndex[ids[i]];}
    return null;
  }
  function inClosedDetails(el){for(var p=el;p&&p!==R;p=p.parentElement){if(p.tagName==='DETAILS'&&!p.open)return true;}return false;}
  function openAncestors(el){for(var p=el;p&&p!==R;p=p.parentElement){if(p.tagName==='DETAILS')p.open=true;}}
  function firstTargetFor(el){
    if(!el)return null;
    if(R.contains(el)&&el.matches('[data-sources]'))return el;
    var bid=el.getAttribute&&el.getAttribute('data-block'),targets=bid&&(rIndex[bid]||[]);
    return targets&&targets[0]||null;
  }
  function revealPinnedInMode(actual){
    if(!pinned)return false;
    if(actual==='l'){var source=firstSourceFor(pinned);if(source){queueReveal(L,source,'auto');return true;}}
    if(actual==='r'){var target=firstTargetFor(pinned);if(target){queueReveal(R,target,'auto');return true;}}
    if(actual==='both'){
      if(R.contains(pinned)){var s=firstSourceFor(pinned);if(s){queueReveal(L,s,'auto');return true;}}
      if(L.contains(pinned)){var t=firstTargetFor(pinned);if(t){queueReveal(R,t,'auto');return true;}}
    }
    return false;
  }
  function sync(from){
    if(lock||pinned||compact.matches)return;lock=true;clearClass(syncEls,'sync-hi');
    if(from==='L'){
      var a=anchorOf(L,'data-block'),targets=a&&rIndex[a.getAttribute('data-block')];
      if(a&&targets&&targets[0]){align(R,targets[0],a,L);mark(syncEls,a,'sync-hi');mark(syncEls,targets[0],'sync-hi');}
    }else{
      var a2=anchorOf(R,'data-sources'),bid=a2&&idsOf(a2)[0],target=bid&&lIndex[bid];
      if(a2&&target){align(L,target,a2,R);mark(syncEls,target,'sync-hi');mark(syncEls,a2,'sync-hi');}
    }
    setTimeout(function(){lock=false;},80);
  }
  function setEdgeFocus(node){
    var nodeId=node&&node.getAttribute('data-node'),diagram=node&&node.closest('[data-diagram]');    document.querySelectorAll('.mv-edge-path').forEach(function(path){
      var sameDiagram=diagram&&path.closest('[data-diagram]')===diagram;
      var active=nodeId&&sameDiagram&&(path.dataset.from===nodeId||path.dataset.to===nodeId);
      path.classList.toggle('is-active',!!active);path.classList.toggle('is-muted',!!nodeId&&!!sameDiagram&&!active);
      if(path._label)path._label.classList.toggle('is-active',!!active);
    });
  }
  function clearPreview(){clearClass(previewed,'is-preview');if(!pinned)setEdgeFocus(null);}
  function preview(el){
    clearPreview();if(pinned)return;mark(previewed,el,'is-preview');idsOf(el).forEach(function(id){mark(previewed,lIndex[id],'is-preview');});setEdgeFocus(el.closest('[data-node]'));
  }
  function clearPinned(announce){
    document.querySelectorAll('.is-pinned').forEach(function(el){el.classList.remove('is-pinned');});pinned=null;pendingReveal=null;setEdgeFocus(null);
    if(announce){setStatus('双栏联动 · 未锁定');flashHint('已取消定位');}
  }
  function pinRight(el,move){
    clearPinned(false);clearPreview();pinned=el;el.classList.add('is-pinned');
    var ids=idsOf(el),sources=ids.map(function(id){return lIndex[id];}).filter(Boolean);sources.forEach(function(src){src.classList.add('is-pinned');});
    if(move&&sources[0])queueReveal(L,sources[0]);
    setEdgeFocus(el.closest('[data-node]'));var label=el.getAttribute('data-label')||el.textContent.trim().slice(0,20);
    setStatus('已定位 · '+label+' · '+sources.length+' 处原文');flashHint(wrap.classList.contains('only-r')?'已锁定 · 切换到原文查看':'已锁定原文映射 · Esc 取消');
  }
  function pinLeft(el,move){
    var bid=el.getAttribute('data-block'),targets=rIndex[bid]||[];clearPinned(false);clearPreview();pinned=el;el.classList.add('is-pinned');targets.forEach(function(target){target.classList.add('is-pinned');});
    var target=firstTargetFor(el);
    if(target)openAncestors(target);
    if(move&&target)queueReveal(R,target);
    setEdgeFocus(targets[0]&&targets[0].closest('[data-node]'));setStatus('已定位 · '+bid+' · '+targets.length+' 个视图元素');flashHint(wrap.classList.contains('only-l')?'已锁定 · 切换到信息重组查看':'已锁定重组映射 · Esc 取消');
  }
  R.addEventListener('pointerover',function(event){if(event.target.closest('summary'))return;var el=event.target.closest('[data-sources]');if(el&&R.contains(el))preview(el);});
  R.addEventListener('pointerout',function(event){var el=event.target.closest('[data-sources]');if(el&&!el.contains(event.relatedTarget))clearPreview();});
  R.addEventListener('click',function(event){var el=event.target.closest('[data-sources]');if(!el)return;if(event.target.closest('a,summary'))return;event.preventDefault();if(pinned===el)clearPinned(true);else pinRight(el,true);});
  L.addEventListener('click',function(event){var el=event.target.closest('[data-block]');if(!el)return;if(event.target.closest('a'))return;if(pinned===el)clearPinned(true);else pinLeft(el,true);});
  document.addEventListener('keydown',function(event){
    if(event.target.closest&&event.target.closest('summary'))return;
    var el=event.target.closest&&event.target.closest('[data-sources],[data-block]');
    if(el&&(event.key==='Enter'||event.key===' ')){event.preventDefault();el.click();}
    if(event.key==='Escape'&&pinned)clearPinned(true);
  });
  L.addEventListener('pointerenter',function(){driver='L';});R.addEventListener('pointerenter',function(){driver='R';});
  L.addEventListener('scroll',function(){if(driver==='L'&&!wrap.classList.contains('only-r'))sync('L');},{passive:true});
  R.addEventListener('scroll',function(){if(driver==='R'&&!wrap.classList.contains('only-l'))sync('R');},{passive:true});

  var modeButtons=[].slice.call(document.querySelectorAll('[data-md2view-mode]'));
  var preferredMode='both';
  function setMode(mode,announce,persist){
    if(['l','both','r'].indexOf(mode)<0)mode='both';if(persist!==false)preferredMode=mode;var actual=compact.matches&&mode==='both'?'r':mode;wrap.classList.remove('only-l','only-r');
    if(actual==='l')wrap.classList.add('only-l');else if(actual==='r')wrap.classList.add('only-r');
    wrap.dataset.layout=actual;modeButtons.forEach(function(button){var on=button.dataset.md2viewMode===actual;button.classList.toggle('on',on);button.setAttribute('aria-pressed',on?'true':'false');});
    if(persist!==false)storageSet('md2view:mode',mode);scheduleDraw();if(!revealPinnedInMode(actual))queueMicrotask(function(){requestAnimationFrame(revealPending);});if(announce){var names={l:'原文',both:'双栏',r:'信息重组'};setStatus(names[actual]+'模式');flashHint('已切换到'+names[actual]);}
  }
  window.setMode=function(mode){setMode(mode,true);};modeButtons.forEach(function(button){button.addEventListener('click',function(){setMode(button.dataset.md2viewMode,true);});});

  function splitBounds(){var width=wrap.getBoundingClientRect().width;if(compact.matches||width<740)return{min:28,max:68};return{min:Math.max(28,300/width*100),max:Math.min(68,(width-400)/width*100)};}
  function defaultRatio(){var bounds=splitBounds();return 42>=bounds.min&&42<=bounds.max?42:(bounds.min+bounds.max)/2;}
  function setRatio(value,persist){var bounds=splitBounds(),ratio=Math.max(bounds.min,Math.min(bounds.max,value));wrap.style.setProperty('--source-ratio',ratio.toFixed(2)+'%');separator.setAttribute('aria-valuemin',Math.ceil(bounds.min));separator.setAttribute('aria-valuemax',Math.floor(bounds.max));separator.setAttribute('aria-valuenow',Math.round(ratio));if(persist)storageSet('md2view:splitRatio',ratio.toFixed(2));scheduleDraw();return ratio;}
  function resetRatio(announce){var ratio=setRatio(defaultRatio(),true);if(announce){setStatus('原文宽度 · '+Math.round(ratio)+'%');flashHint('已恢复默认栏宽');}}
  var dragging=false;
  separator.addEventListener('pointerdown',function(event){if(compact.matches)return;dragging=true;separator.classList.add('is-dragging');separator.setPointerCapture(event.pointerId);event.preventDefault();});
  separator.addEventListener('pointermove',function(event){if(!dragging)return;var rect=wrap.getBoundingClientRect(),ratio=setRatio((event.clientX-rect.left)/rect.width*100,false);setStatus('原文宽度 · '+Math.round(ratio)+'%');});
  separator.addEventListener('pointerup',function(event){if(!dragging)return;dragging=false;separator.classList.remove('is-dragging');var ratio=parseFloat(separator.getAttribute('aria-valuenow'));setRatio(ratio,true);flashHint('栏宽已记住 · 双击可重置');separator.releasePointerCapture(event.pointerId);});
  separator.addEventListener('pointercancel',function(){dragging=false;separator.classList.remove('is-dragging');});
  separator.addEventListener('dblclick',function(){resetRatio(true);});
  separator.addEventListener('keydown',function(event){var now=parseFloat(separator.getAttribute('aria-valuenow'))||defaultRatio(),next=now;if(event.key==='ArrowLeft')next-=2;else if(event.key==='ArrowRight')next+=2;else if(event.key==='Home')next=splitBounds().min;else if(event.key==='End')next=splitBounds().max;else if(event.key==='Enter')next=defaultRatio();else return;event.preventDefault();next=setRatio(next,true);setStatus('原文宽度 · '+Math.round(next)+'%');});

  /* ---------- diagram 连线路由 ---------- */
  var NS='http://www.w3.org/2000/svg';
  function svgEl(name,attrs){var el=document.createElementNS(NS,name);Object.keys(attrs||{}).forEach(function(key){el.setAttribute(key,attrs[key]);});return el;}
  function point(rect,side,root){var x=rect.left-root.left,y=rect.top-root.top,w=rect.width,h=rect.height;if(side==='top')return{x:x+w/2,y:y};if(side==='bottom')return{x:x+w/2,y:y+h};if(side==='left')return{x:x,y:y+h/2};return{x:x+w,y:y+h/2};}
  function roundedPath(points){
    var cleaned=points.filter(function(p,i){return !i||Math.abs(p.x-points[i-1].x)>.2||Math.abs(p.y-points[i-1].y)>.2;});if(cleaned.length===2)return'M '+cleaned[0].x+' '+cleaned[0].y+' L '+cleaned[1].x+' '+cleaned[1].y;
    var d='M '+cleaned[0].x+' '+cleaned[0].y;for(var i=1;i<cleaned.length-1;i++){var prev=cleaned[i-1],cur=cleaned[i],next=cleaned[i+1],a=Math.min(10,Math.hypot(cur.x-prev.x,cur.y-prev.y)/2,Math.hypot(next.x-cur.x,next.y-cur.y)/2);var before={x:cur.x+(prev.x-cur.x)*(a/Math.max(1,Math.hypot(prev.x-cur.x,prev.y-cur.y))),y:cur.y+(prev.y-cur.y)*(a/Math.max(1,Math.hypot(prev.x-cur.x,prev.y-cur.y)))};var after={x:cur.x+(next.x-cur.x)*(a/Math.max(1,Math.hypot(next.x-cur.x,next.y-cur.y))),y:cur.y+(next.y-cur.y)*(a/Math.max(1,Math.hypot(next.x-cur.x,next.y-cur.y)))};d+=' L '+before.x+' '+before.y+' Q '+cur.x+' '+cur.y+' '+after.x+' '+after.y;}return d+' L '+cleaned[cleaned.length-1].x+' '+cleaned[cleaned.length-1].y;
  }
  function segmentHitsRect(a,b,rect){var pad=5,left=rect.left-pad,right=rect.right+pad,top=rect.top-pad,bottom=rect.bottom+pad;if(Math.abs(a.x-b.x)<.5)return a.x>left&&a.x<right&&Math.max(a.y,b.y)>top&&Math.min(a.y,b.y)<bottom;if(Math.abs(a.y-b.y)<.5)return a.y>top&&a.y<bottom&&Math.max(a.x,b.x)>left&&Math.min(a.x,b.x)<right;return false;}
  function routePoints(start,end,axis,obstacles,bounds){
    var candidates=[],distance=Math.abs(axis==='v'?end.y-start.y:end.x-start.x),step=Math.min(24,Math.max(10,distance/4)),escape=6;
    if(axis==='v'){
      var sign=end.y>=start.y?1:-1,ys=[(start.y+end.y)/2,start.y+sign*step,end.y-sign*step];obstacles.forEach(function(rect){ys.push(rect.top-10,rect.bottom+10);});
      ys.filter(function(y){return y>Math.min(start.y,end.y)+4&&y<Math.max(start.y,end.y)-4;}).forEach(function(y){candidates.push([start,{x:start.x,y:y},{x:end.x,y:y},end]);});
      var detourXs=[bounds.left,bounds.right];obstacles.forEach(function(rect){detourXs.push(rect.left-10,rect.right+10);});
      detourXs.filter(function(x){return x>=bounds.left&&x<=bounds.right;}).forEach(function(x){var exit=start.y+sign*escape,entry=end.y-sign*escape;candidates.push([start,{x:start.x,y:exit},{x:x,y:exit},{x:x,y:entry},{x:end.x,y:entry},end]);candidates.push([start,{x:x,y:start.y},{x:x,y:end.y},end]);});
    }else{
      var signX=end.x>=start.x?1:-1,xs=[(start.x+end.x)/2,start.x+signX*step,end.x-signX*step];obstacles.forEach(function(rect){xs.push(rect.left-10,rect.right+10);});
      xs.filter(function(x){return x>Math.min(start.x,end.x)+4&&x<Math.max(start.x,end.x)-4;}).forEach(function(x){candidates.push([start,{x:x,y:start.y},{x:x,y:end.y},end]);});
      var detourYs=[bounds.top,bounds.bottom];obstacles.forEach(function(rect){detourYs.push(rect.top-10,rect.bottom+10);});
      detourYs.filter(function(y){return y>=bounds.top&&y<=bounds.bottom;}).forEach(function(y){var exitX=start.x+signX*escape,entryX=end.x-signX*escape;candidates.push([start,{x:exitX,y:start.y},{x:exitX,y:y},{x:entryX,y:y},{x:entryX,y:end.y},end]);candidates.push([start,{x:start.x,y:y},{x:end.x,y:y},end]);});
    }
    if(!candidates.length)candidates.push([start,end]);
    function score(points){var hits=0,length=0;for(var i=1;i<points.length;i++){var a=points[i-1],b=points[i];length+=Math.hypot(b.x-a.x,b.y-a.y);obstacles.forEach(function(rect){if(segmentHitsRect(a,b,rect))hits++;});}var hugsOuterEdge=points.some(function(p){return p.x-bounds.left<16||bounds.right-p.x<16||p.y-bounds.top<16||bounds.bottom-p.y<16;});return hits*100000+length+points.length*2+(hugsOuterEdge?64:0);}
    candidates.sort(function(a,b){return score(a)-score(b);});return candidates[0];
  }
  function routePath(start,end,axis,obstacles,bounds){return roundedPath(routePoints(start,end,axis,obstacles,bounds));}
  function labelColumns(text){return Array.from(text||'').reduce(function(total,char){return total+(/[⺀-鿿豈-﫿]/.test(char)?2:1);},0);}
  function boxesOverlap(a,b){return Math.min(a.right,b.right)-Math.max(a.left,b.left)>0&&Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>0;}
  function paddedLabelBox(label,padding){var box=label.getBBox();return{left:box.x-padding,right:box.x+box.width+padding,top:box.y-padding,bottom:box.y+box.height+padding};}
  function placeEdgeLabel(edge,nodeBoxes,placed,width,height){
    var text=edge.meta.dataset.label||'';edge.label.textContent=text;if(!text)return;
    var length;try{length=edge.path.getTotalLength();}catch(e){edge.label.dataset.placementScore='invalid-path';return;}if(!Number.isFinite(length)||length<=0){edge.label.dataset.placementScore='invalid-path';return;}
    var fractions=[.5],offsets=[0,10,-10,18,-18,28,-28,36,-36],best=null;for(var step=1;step<40;step++)fractions.push(step/40);
    fractions.some(function(fraction){
      var distance=length*fraction,pt=edge.path.getPointAtLength(distance),before=edge.path.getPointAtLength(Math.max(0,distance-2)),after=edge.path.getPointAtLength(Math.min(length,distance+2)),dx=after.x-before.x,dy=after.y-before.y,norm=Math.hypot(dx,dy)||1,nx=-dy/norm,ny=dx/norm;
      return offsets.some(function(offset){
        var x=pt.x+nx*offset,y=pt.y+ny*offset;edge.label.setAttribute('x',x);edge.label.setAttribute('y',y);
        var box;try{box=paddedLabelBox(edge.label,3);}catch(e){return false;}
        var overflow=Math.max(0,6-box.left)+Math.max(0,box.right-(width-6))+Math.max(0,6-box.top)+Math.max(0,box.bottom-(height-6));
        var nodeHits=nodeBoxes.filter(function(nodeBox){return boxesOverlap(box,nodeBox);}).length,labelHits=placed.filter(function(labelBox){return boxesOverlap(box,labelBox);}).length,score=overflow*1000+nodeHits*100000+labelHits*120000;
        if(!best||score<best.score)best={x:x,y:y,box:box,score:score};return score===0;
      });
    });
    if(best){if(best.score>0){edge.label.textContent='';edge.label.dataset.placementScore='suppressed:'+best.score;}else{edge.label.setAttribute('x',best.x);edge.label.setAttribute('y',best.y);edge.label.dataset.placementScore=String(best.score);placed.push(best.box);}}
  }
  function setupDiagram(diagram,index){
    var svg=svgEl('svg',{'class':'mv-edge-layer','aria-hidden':'true'}),defs=svgEl('defs'),markerId='mv-arrow-'+index,marker=svgEl('marker',{id:markerId,viewBox:'0 0 10 10',refX:'8.5',refY:'5',markerWidth:'6',markerHeight:'6',orient:'auto-start-reverse'}),arrow=svgEl('path',{d:'M 1 1 L 9 5 L 1 9 z',fill:'context-stroke'});marker.appendChild(arrow);defs.appendChild(marker);svg.appendChild(defs);diagram.insertBefore(svg,diagram.firstChild);
    diagram._edges=[];diagram.querySelectorAll('.mv-edge[data-from][data-to]').forEach(function(meta){var path=svgEl('path',{'class':'mv-edge-path','data-kind':meta.dataset.kind||'dependsOn','marker-end':'url(#'+markerId+')','pathLength':'1'}),label=svgEl('text',{'class':'mv-edge-label'});label.textContent=meta.dataset.label||'';path.dataset.from=meta.dataset.from;path.dataset.to=meta.dataset.to;path._label=label;svg.appendChild(path);svg.appendChild(label);diagram._edges.push({meta:meta,path:path,label:label});});diagram._svg=svg;
    if('ResizeObserver'in window){var observer=new ResizeObserver(scheduleDraw);observer.observe(diagram);diagram.querySelectorAll('.mv-node,.mv-fact').forEach(function(content){observer.observe(content);});diagram._observer=observer;}
  }
  function drawDiagram(diagram){
    if(!diagram.offsetParent||!diagram._svg)return;var root=diagram.getBoundingClientRect(),width=diagram.clientWidth,height=diagram.clientHeight;diagram._svg.setAttribute('viewBox','0 0 '+width+' '+height);diagram._svg.setAttribute('width',width);diagram._svg.setAttribute('height',height);
    diagram._edges.forEach(function(edge){var from=diagram.querySelector('[data-node="'+CSS.escape(edge.meta.dataset.from)+'"]'),to=diagram.querySelector('[data-node="'+CSS.escape(edge.meta.dataset.to)+'"]');if(!from||!to){edge.path.setAttribute('d','');edge.label.dataset.placementScore='missing-node';return;}var a=from.getBoundingClientRect(),b=to.getBoundingClientRect(),dx=b.left+b.width/2-(a.left+a.width/2),dy=b.top+b.height/2-(a.top+a.height/2),axis=edge.meta.dataset.route||((Math.abs(dy)>=Math.abs(dx)*.72)?'v':'h');var fromSide=edge.meta.dataset.fromSide||(axis==='v'?(dy>=0?'bottom':'top'):(dx>=0?'right':'left')),toSide=edge.meta.dataset.toSide||(axis==='v'?(dy>=0?'top':'bottom'):(dx>=0?'left':'right')),start=point(a,fromSide,root),end=point(b,toSide,root),obstacles=[].slice.call(diagram.querySelectorAll('.mv-node,.mv-fact')).filter(function(content){return content!==from&&content!==to;}).map(function(content){var rect=content.getBoundingClientRect();return{left:rect.left-root.left,right:rect.right-root.left,top:rect.top-root.top,bottom:rect.bottom-root.top};}),bounds={left:10,right:width-10,top:10,bottom:height-10},d=routePath(start,end,axis,obstacles,bounds);edge.path.setAttribute('d',d);});
    var contentBoxes=[].slice.call(diagram.querySelectorAll('.mv-node,.mv-fact')).map(function(content){var rect=content.getBoundingClientRect();return{left:rect.left-root.left-3,right:rect.right-root.left+3,top:rect.top-root.top-3,bottom:rect.bottom-root.top+3};}),placed=[];diagram._edges.forEach(function(edge){placeEdgeLabel(edge,contentBoxes,placed,width,height);});
  }
  function drawAll(){drawQueued=false;document.querySelectorAll('[data-diagram]').forEach(drawDiagram);}
  function scheduleDraw(){if(drawQueued)return;drawQueued=true;requestAnimationFrame(function(){requestAnimationFrame(drawAll);});}
  document.querySelectorAll('[data-diagram]').forEach(setupDiagram);
  window.addEventListener('resize',scheduleDraw,{passive:true});
  function compactChanged(){setMode(preferredMode,false,false);scheduleDraw();}
  if(compact.addEventListener)compact.addEventListener('change',compactChanged);else compact.addListener(compactChanged);
  if(document.fonts&&document.fonts.ready)document.fonts.ready.then(scheduleDraw);
  var savedRatio=parseFloat(storageGet('md2view:splitRatio'));setRatio(Number.isFinite(savedRatio)?savedRatio:defaultRatio(),false);
  preferredMode=storageGet('md2view:mode')||'both';setMode(preferredMode,false,false);compactChanged();scheduleDraw();
  setTimeout(scheduleDraw,240);
  setStatus(compact.matches?'信息重组模式':'双栏联动 · 拖动中线调宽');setTimeout(function(){flashHint(compact.matches?'点击内容可定位原文':'拖动中线调宽 · 点击内容锁定映射');},420);
})();

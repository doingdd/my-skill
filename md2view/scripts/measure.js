// md2view 构图尺 —— 自审时在生产浏览器里对打开中的 reader.html 执行。
// 用法(任一):playwright/chrome-devtools MCP 的 evaluate;或 console 粘贴。
// 返回每个视图的:高度、屏数(按 900px 视口)、主视觉占比(图+链,抽屉外)、
// 抽屉外表格数、卡片数;以及全页汇总。构图合同见 SKILL.md 第 6 步。
(function(){
  var R=document.getElementById('paneR');
  if(!R)return '未找到 #paneR——请在打开的 reader.html 上运行';
  var vh=window.innerHeight||900;
  function visible(el){for(var p=el;p&&p!==R;p=p.parentElement){if(p.tagName==='DETAILS'&&!p.open)return false;}return true;}
  var rows=[].slice.call(R.querySelectorAll('section.mv-view')).map(function(v){
    var h=v.getBoundingClientRect().height;
    var figH=[].slice.call(v.querySelectorAll('[data-diagram],.mv-chain'))
      .filter(function(e){return visible(e);})
      .reduce(function(s,e){return s+e.getBoundingClientRect().height;},0);
    var tablesOut=[].slice.call(v.querySelectorAll('table.mv-table')).filter(visible).length;
    return {
      view:v.id,
      heightPx:Math.round(h),
      screens:+(h/vh).toFixed(1),
      figureShare:Math.round(figH/h*100)+'%',
      tablesOutsideDrawer:tablesOut,
      cards:[].slice.call(v.querySelectorAll('.mv-card')).filter(visible).length
    };
  });
  var doc=R.querySelector('.doc');
  var summary={totalHeightPx:Math.round(doc.scrollHeight),totalScreens:+(doc.scrollHeight/vh).toFixed(1),views:rows.length};
  if(typeof console!=='undefined'&&console.table){console.log(summary);console.table(rows);}
  return {summary:summary,views:rows};
})();

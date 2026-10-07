/* Design prototype only. All tasks, accounts, processing and receipts are simulated. */
"use strict";

const iconPaths = {
  home:'<rect x="3" y="3" width="7" height="7" rx="1.4"/><rect x="14" y="3" width="7" height="7" rx="1.4"/><rect x="3" y="14" width="7" height="7" rx="1.4"/><rect x="14" y="14" width="7" height="7" rx="1.4"/>',
  folder:'<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/><path d="M3 10h18"/>',
  tasks:'<rect x="4" y="3" width="16" height="18" rx="2"/><path d="m8 8 1 1 2-2m2 1h3m-8 5 1 1 2-2m2 1h3M8 18h8"/>',
  scissors:'<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="m8 8 13 13M8 16l13-13"/>',
  send:'<path d="m21 3-7 18-4-8-8-3 19-7ZM10 13l11-10"/>',
  settings:'<path d="m9 3-.8 2.5L6 7l-2.5.3-1 3L4 12l-1.5 1.7 1 3L6 17l2.2 1.5L9 21h6l.8-2.5L18 17l2.5-.3 1-3L20 12l1.5-1.7-1-3L18 7l-2.2-1.5L15 3H9Z"/><circle cx="12" cy="12" r="3"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
  chevron:'<path d="m9 5 7 7-7 7"/>',
  down:'<path d="m6 9 6 6 6-6"/>',
  upload:'<path d="M4 15v5h16v-5M12 16V3m-5 5 5-5 5 5"/>',
  film:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4m-4 8h4M17 8h4m-4 8h4"/>',
  image:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.4"/><path d="m3 17 5-5 4 4 4-7 5 8"/>',
  play:'<path d="m8 5 11 7-11 7V5Z"/>',
  pause:'<path d="M9 5v14M15 5v14"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  check:'<path d="m5 12 4 4L20 5"/>',
  circleCheck:'<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  refresh:'<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  list:'<path d="M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1"/>',
  bell:'<path d="M6 8a6 6 0 0 1 12 0c0 7 3 7 3 9H3c0-2 3-2 3-9ZM10 21h4"/>',
  help:'<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-1 .5-1 1.2-1 2.2M12 17h.01"/>',
  close:'<path d="m6 6 12 12M18 6 6 18"/>',
  menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
  more:'<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  sound:'<path d="M9 18V5l11-2v13M9 8l11-2"/><ellipse cx="6" cy="18" rx="3" ry="2"/><ellipse cx="17" cy="16" rx="3" ry="2"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  link:'<path d="m10 7 3-3a5 5 0 0 1 7 7l-3 3M14 17l-3 3a5 5 0 0 1-7-7l3-3M8 16l8-8"/>',
  file:'<path d="M14 2H5v20h14V7l-5-5ZM14 2v6h5M8 13h8M8 17h6"/>',
  spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z"/>',
  download:'<path d="M12 3v13m-5-5 5 5 5-5M4 16v5h16v-5"/>'
};
const icon = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${iconPaths[name] || iconPaths.file}</svg>`;
const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
// The required image service returned "Authentication failed". The prototype
// therefore uses semantic file-information views, with no placeholder images.
const initialMaterials = [
  {id:"m1",name:"法式美甲 · 完整教学",type:"video",image:0,duration:"08:42",size:"328 MB",date:"今天 14:32",state:"已分析",scenes:24},
  {id:"m2",name:"课堂实录 · 基础手法练习",type:"video",image:1,duration:"12:18",size:"512 MB",date:"今天 13:48",state:"待处理",scenes:0},
  {id:"m3",name:"秋日酒红 · 学员作品",type:"image",image:2,duration:"照片",size:"4.8 MB",date:"今天 11:06",state:"可用",scenes:0},
  {id:"m4",name:"工具准备 · 美甲师的一天",type:"video",image:3,duration:"03:26",size:"146 MB",date:"今天 10:25",state:"已分析",scenes:12},
  {id:"m5",name:"进阶课 · 法式线条特写",type:"shot",image:0,duration:"00:18",size:"12.6 MB",date:"昨天 17:20",state:"可用",scenes:1},
  {id:"m6",name:"课堂花絮 · 导师示范",type:"shot",image:1,duration:"00:24",size:"18.2 MB",date:"昨天 16:08",state:"可用",scenes:1},
  {id:"m7",name:"毕业作品 · 光泽与细节",type:"image",image:2,duration:"照片",size:"6.2 MB",date:"昨天 15:40",state:"可用",scenes:0},
  {id:"m8",name:"基础课 · 甲油涂刷技巧",type:"video",image:3,duration:"06:15",size:"268 MB",date:"昨天 14:12",state:"待处理",scenes:0}
];
const tasks = [
  {id:"JF-1026",name:"法式美甲 · 完整教学",type:"分析任务",state:"running",progress:68,stage:"语义分镜",time:"今天 14:35",material:"m1",options:["原始切镜","音频转录","语义分镜"]},
  {id:"JF-1025",name:"课堂实录 · 基础手法练习",type:"分析任务",state:"queued",progress:0,stage:"等待本地引擎",time:"今天 14:32",material:"m2",options:["原始切镜","音频转录"]},
  {id:"JF-1024",name:"秋日美甲 · 教学混剪 03",type:"混剪任务",state:"complete",progress:100,stage:"已生成预览与剪映草稿",time:"今天 13:58",material:"m3",options:["预览 MP4","剪映草稿"]},
  {id:"JF-1023",name:"工具准备 · 美甲师的一天",type:"分析任务",state:"complete",progress:100,stage:"12 个原始镜头 · 转录完成",time:"今天 11:20",material:"m4",options:["原始切镜","音频转录"]},
  {id:"JF-1022",name:"基础课 · 甲油涂刷技巧",type:"分析任务",state:"failed",progress:32,stage:"音频转录失败",time:"今天 10:42",material:"m8",options:["原始切镜","音频转录"],error:"转录模型尚未准备完成。真实版本会在这里提供模型检查与日志。"}
];
const outputs = [
  {id:"o1",name:"秋日美甲 · 教学混剪 03",image:2,duration:"00:42",size:"38.6 MB",type:"final",label:"已确认成片",title:"这个秋天，把喜欢的颜色留在指尖",caption:"从基础线条到完整作品，每一次练习都有新的进步。\n#美甲教学 #秋日美甲 #美甲日常"},
  {id:"o2",name:"美甲师的一天 · 预览 02",image:3,duration:"00:35",size:"31.2 MB",type:"preview",label:"预览 MP4",title:"美甲师的一天，从准备工具开始",caption:"#美甲教学 #美甲师日常"},
  {id:"o3",name:"法式线条 · 剪映草稿",image:0,duration:"00:48",size:"草稿目录",type:"draft",label:"剪映草稿",title:"法式线条练习",caption:""}
];
const statusLabels = {running:"进行中",queued:"排队中",complete:"已完成",failed:"失败",paused:"已暂停",waiting:"待人工确认",submitted:"已提交（模拟）"};
const orderedOptions = (options) => ["视频清洗","原始切镜","音频转录","语义分镜"].filter(option=>options.has(option));
const navItems = [["home","home","工作台"],["library","folder","素材库"],["tasks","tasks","任务中心"],["studio","scissors","混剪工作室"],["publish","send","成片与发布"],["settings","settings","设置"]];
const state = {
  page:"home",materials:[...initialMaterials],selected:new Set(),libraryFilter:"all",libraryQuery:"",view:"grid",taskFilter:"all",taskQuery:"",
  wizard:null,drawer:null,dialog:null,mix:{seed:"20261006",template:"teaching",pool:"all",outputs:["preview","draft"],plan:null,clip:0},
  publish:{id:"o1",mode:"prefill",confirmed:false,receipts:[],forms:{}},
  settings:{source:"~/Movies/青序素材",output:"./output",draft:"~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft",model:"small",reuse:true,longShots:true}
};
const $ = (selector) => document.querySelector(selector);
const badge = (status,label) => `<span class="tag ${status}"><span class="tag-dot"></span>${label || statusLabels[status] || status}</span>`;
const notice = (text,warm=false) => `<div class="notice ${warm?"warm":""}">${icon("info")}<span>${text}</span></div>`;
const imageTag = (index,title) => {
  const labels=["教学示范","课堂实录","作品展示","工具与手法"];
  return `<div class="asset-data asset-tone-${index}"><div class="asset-data-top"><span>${icon(index===2?"image":"film")}</span><span>ASSET / ${String(index+1).padStart(2,"0")}</span></div><div class="asset-data-title">${labels[index]}</div><div class="asset-data-bottom"><span>青序内容工作室</span><span>${index===2?"COLLECTION":"FOOTAGE"}</span></div><span class="screen-reader">${escapeHtml(title)}，素材信息视图</span></div>`;
};
const materialVisual = (m) => m.image === null ? `<div class="imported-symbol">${icon("film")}</div>` : imageTag(m.image,m.name);
const button = (text,action,ico="",kind="",attrs="") => `<button class="button ${kind}" data-action="${action}" ${attrs}>${ico?icon(ico):""}${text}</button>`;
function pageHeader(title,subtitle,actions=""){
  return `<div class="page-header"><div><h1>${title}</h1><p>${subtitle}</p></div><div class="page-actions">${actions}</div></div>`;
}
function sectionHead(title,action="",label="查看全部",sub=""){
  return `<div class="section-head"><h2>${title}${sub?`<small>${sub}</small>`:""}</h2>${action?`<button class="text-button" data-action="${action}">${label}${icon("arrow")}</button>`:""}</div>`;
}
function route(page){
  if(location.hash === `#${page}`) renderPage(); else location.hash = page;
}
function renderNav(){
  $("#navigation").innerHTML=navItems.map(([id,ico,name],i)=>`${i===5?'<div class="nav-divider"></div>':""}<a href="#${id}" class="nav-link ${state.page===id?"active":""}" ${state.page===id?'aria-current="page"':""} title="${name}">${icon(ico)}<span>${name}</span>${id==="tasks"?`<span class="nav-count">${tasks.filter(t=>["running","queued"].includes(t.state)).length}</span>`:""}</a>`).join("");
}
function renderPage(){
  const hash=location.hash.slice(1);
  state.page=navItems.some(n=>n[0]===hash)?hash:"home";
  renderNav();
  $("#breadcrumb-title").textContent=navItems.find(n=>n[0]===state.page)[2];
  document.title=`${$("#breadcrumb-title").textContent} · 镜流工坊原型`;
  const renderers={home:renderHome,library:renderLibrary,tasks:renderTasks,studio:renderStudio,publish:renderPublish,settings:renderSettings};
  $("#main").innerHTML=`<div class="page">${renderers[state.page]()}</div>`;
  $("#sidebar").classList.remove("mobile-open");
}
function mediaCard(m,selectable=false){
  return `<article class="media-card ${selectable?"has-select":""} ${state.selected.has(m.id)?"selected":""}" data-material="${m.id}">
    <div class="media-image">${materialVisual(m)}<button class="media-open" data-action="material" data-id="${m.id}" aria-label="查看${escapeHtml(m.name)}"></button>
    ${selectable?`<input class="select-check" type="checkbox" data-select="${m.id}" aria-label="选择${escapeHtml(m.name)}" ${state.selected.has(m.id)?"checked":""}>`:""}
    <span class="media-kind">${{video:"原始视频",image:"作品照片",shot:"镜头片段"}[m.type]}</span><span class="duration">${m.duration}</span></div>
    <div class="media-title">${escapeHtml(m.name)}</div><div class="media-meta"><span>${m.date} · ${m.size}</span><span>${m.state==="已分析"?`${icon("check")} 已分析`:m.state}</span></div>
  </article>`;
}
function renderHome(){
  const active=tasks.find(t=>t.id==="JF-1026");
  const failed=tasks.filter(t=>t.state==="failed").length;
  return `${pageHeader("工作台","10 月 6 日，星期二 · 查看当前任务与最近素材。",button("导入素材","import","upload","secondary-action")+button("新建任务","new-task","plus","primary"))}
    <div class="metric-strip">
      <div class="metric"><div class="metric-label">${icon("folder")}素材总览</div><div class="metric-value">${state.materials.length}<small>份素材已入库</small></div></div>
      <div class="metric"><div class="metric-label">${icon("tasks")}进行中的任务</div><div class="metric-value">${tasks.filter(t=>t.state==="running").length}<small><span class="orange">${tasks.filter(t=>t.state==="queued").length}</span> 个排队中</small></div></div>
      <div class="metric"><div class="metric-label">${icon("scissors")}可用镜头</div><div class="metric-value">38<small>来自已分析素材</small></div></div>
      <div class="metric"><div class="metric-label">${icon("send")}待发布成片</div><div class="metric-value">${outputs.filter(o=>o.type==="final").length}<small>等待你的确认</small></div></div>
    </div>
    <div class="dashboard-main"><section>
      ${sectionHead("继续创作","go-tasks","任务中心","IN PROGRESS")}
      <div class="feature analysis-feature"><div class="analysis-heading"><span class="overline">PROJECT / 026</span><span class="analysis-status">镜头分析 · 示例</span></div>
        <div class="analysis-main"><div><h3>法式美甲<br>完整教学</h3><p>08:42 原片 &nbsp;·&nbsp; 1080P</p></div><div class="shot-count"><strong>24</strong><span>原始镜头</span></div></div>
        <div class="shot-map" aria-label="24 个镜头分布示意">${Array.from({length:24},(_,i)=>`<span style="flex:${[3,1,2,4,2,1][i%6]}" class="${i<Math.floor(24*active.progress/100)?"analyzed":""}"></span>`).join("")}</div>
        <div class="shot-map-label"><span>00:00</span><span>保留原始镜头结构</span><span>08:42</span></div>
      </div>
      <div class="feature-foot"><div class="feature-progress"><div class="progress-label"><span>${badge(active.state)}<span>${active.stage}</span></span><span class="mono">${active.progress}%</span></div><div class="progress"><span style="width:${active.progress}%"></span></div></div>${button("查看任务","task","","small",`data-id="${active.id}"`)}</div>
      <div class="task-mini"><div class="task-mini-icon">${icon("film")}</div><div class="task-mini-title">课堂实录 · 基础手法练习<small>原始切镜 + 音频转录 · 今天 14:32</small></div>${badge(tasks.find(t=>t.id==="JF-1025").state)}<button class="icon-button" data-action="task" data-id="JF-1025" aria-label="查看课堂实录任务">${icon("chevron")}</button></div>
      <div class="task-mini"><div class="task-mini-icon">${icon("scissors")}</div><div class="task-mini-title">秋日美甲 · 教学混剪 03<small>预览 MP4 + 剪映草稿 · 今天 13:58</small></div>${badge("complete")}<button class="icon-button" data-action="go-publish" aria-label="查看混剪产物">${icon("chevron")}</button></div>
    </section><aside class="right-rail">
      <div class="rail-group"><div class="rail-title">需要关注</div>
        <div class="attention-item"><span class="attention-number">01</span><div class="attention-content"><h3>${failed?`${failed} 个任务需要重试`:"任务异常已处理"}</h3><p>基础课 · 甲油涂刷技巧</p><button class="text-button" data-action="task" data-id="JF-1022">${failed?"查看原因":"查看任务"} ${icon("arrow")}</button></div></div>
        <div class="attention-item"><span class="attention-number">02</span><div class="attention-content"><h3>继续整理镜头池</h3><p>把教学片段变成下一支成片。</p><button class="text-button" data-action="go-studio">打开混剪工作室 ${icon("arrow")}</button></div></div>
      </div><div class="rail-group"><div class="rail-divider"></div><div class="rail-title">准备好发布</div><div class="ready-media">${imageTag(2,"秋日酒红色美甲作品")}<span class="duration">00:42</span></div><h3 class="ready-title">秋日美甲 · 教学混剪 03</h3><p class="ready-meta">竖屏 9:16 · MP4 · 已确认成片</p>${button("前往发布","go-publish","send","small full")}</div>
    </aside></div>
    <section class="recent-section">${sectionHead("最近素材","go-library","查看素材库","RECENT ASSETS")}<div class="media-grid">${state.materials.slice(0,4).map(m=>mediaCard(m)).join("")}</div></section>`;
}
function filteredMaterials(){
  return state.materials.filter(m=>(state.libraryFilter==="all"||m.type===state.libraryFilter)&&m.name.toLowerCase().includes(state.libraryQuery.toLowerCase()));
}
function renderLibrary(){
  return `${pageHeader("素材库","把原片、镜头和作品放在一起，随时开始下一次创作。",button("导入素材","import","upload","primary"))}
    <div class="filter-bar"><div class="tabs">${[["all","全部素材"],["video","原始视频"],["shot","镜头片段"],["image","作品照片"]].map(([key,label])=>`<button class="tab ${state.libraryFilter===key?"active":""}" data-action="library-filter" data-value="${key}">${label}<small>${state.materials.filter(m=>key==="all"||m.type===key).length}</small></button>`).join("")}</div>
      <div class="toolbar"><label class="search-field">${icon("search")}<input type="search" id="library-search" placeholder="搜索素材名称" aria-label="搜索素材" value="${escapeHtml(state.libraryQuery)}"></label><div class="view-switch"><button data-action="view-grid" class="${state.view==="grid"?"active":""}" aria-label="网格视图" aria-pressed="${state.view==="grid"}">${icon("grid")}</button><button data-action="view-list" class="${state.view==="list"?"active":""}" aria-label="列表视图" aria-pressed="${state.view==="list"}">${icon("list")}</button></div></div>
    </div><div id="library-results">${renderLibraryResults()}</div>`;
}
function renderLibraryResults(){
  const filtered=filteredMaterials(),allSelected=filtered.length>0&&filtered.every(m=>state.selected.has(m.id));
  let content=state.view==="grid"?`<div class="media-grid library-grid">${filtered.map(m=>mediaCard(m,true)).join("")}</div>`:
    `<div class="table-wrap"><table><thead><tr><th></th><th>素材名称</th><th>类型</th><th>时长 / 大小</th><th>状态</th><th>操作</th></tr></thead><tbody>${filtered.map(m=>`<tr><td><input class="select-check" type="checkbox" data-select="${m.id}" aria-label="选择${escapeHtml(m.name)}" ${state.selected.has(m.id)?"checked":""}></td><td><div class="table-name">${m.image!==null?imageTag(m.image,m.name):icon("film")}<button data-action="material" data-id="${m.id}">${escapeHtml(m.name)}<small>${m.date}</small></button></div></td><td>${{video:"原始视频",image:"作品照片",shot:"镜头片段"}[m.type]}</td><td class="muted">${m.duration} / ${m.size}</td><td>${badge(m.state==="待处理"?"queued":"complete",m.state)}</td><td>${button("详情","material","","small",`data-id="${m.id}"`)}</td></tr>`).join("")}</tbody></table></div>`;
  if(!filtered.length)content=`<div class="empty-state">${icon("search")}<h3>没有找到匹配的素材</h3><p>换个关键词，或切换素材分类。</p>${button("清除筛选","clear-library")}</div>`;
  return `<div class="sub-toolbar"><label class="check-label"><input class="select-check" type="checkbox" id="select-all" ${allSelected?"checked":""} ${!filtered.length?"disabled":""}>全选当前结果 <span>· ${filtered.length} 份素材</span></label><span>按导入时间排序 · 最新优先</span></div>${content}${state.selected.size?`<div class="selection-bar">${icon("check")}已选择 ${state.selected.size} 份素材${button("取消选择","clear-selection","","ghost small")}${button("创建处理任务","selected-task","plus","primary small")}</div>`:""}`;
}
function refreshLibrary(){ $("#library-results").innerHTML=renderLibraryResults(); }
function renderTasks(){
  return `${pageHeader("任务中心","查看每一步的进度，处理需要关注的任务。",button("新建任务","new-task","plus","primary"))}
    <div class="filter-bar"><div class="tabs">${[["all","全部"],["running","进行中"],["queued","排队中"],["complete","已完成"],["failed","失败"],["paused","已暂停"]].map(([key,label])=>`<button class="tab ${state.taskFilter===key?"active":""}" data-action="task-filter" data-value="${key}">${label}<small>${tasks.filter(t=>key==="all"||t.state===key).length}</small></button>`).join("")}</div><label class="search-field">${icon("search")}<input id="task-search" type="search" placeholder="搜索任务名称或编号" aria-label="搜索任务" value="${escapeHtml(state.taskQuery)}"></label></div>
    <div id="task-results">${renderTaskResults()}</div>${notice("当前为交互演示。你可以暂停、继续、重试任务，或在详情中推进演示阶段。")}`;
}
function renderTaskResults(){
  const list=tasks.filter(t=>(state.taskFilter==="all"||t.state===state.taskFilter)&&(t.name+t.id).toLowerCase().includes(state.taskQuery.toLowerCase()));
  if(!list.length)return `<div class="empty-state">${icon("tasks")}<h3>这里还没有任务</h3><p>切换筛选，或从素材创建一个新任务。</p>${button("查看全部","reset-tasks")}</div>`;
  return `<div class="table-wrap"><table><thead><tr><th>任务名称</th><th>类型</th><th>状态 / 当前阶段</th><th>创建时间</th><th>操作</th></tr></thead><tbody>${list.map(t=>`<tr><td><div class="table-name"><span class="task-mini-icon">${icon(t.type==="混剪任务"?"scissors":"film")}</span><button data-action="task" data-id="${t.id}">${escapeHtml(t.name)}<small>${t.id}</small></button></div></td><td class="muted">${t.type}</td><td>${badge(t.state)}<div class="task-step">${t.stage}</div></td><td class="muted mono">${t.time}</td><td><div class="table-actions">${taskActionButton(t)}<button class="icon-button" data-action="task" data-id="${t.id}" aria-label="查看${escapeHtml(t.name)}任务详情">${icon("chevron")}</button></div></td></tr>`).join("")}</tbody></table></div>`;
}
function taskActionButton(t){
  const action=t.state==="running"?"pause-task":t.state==="failed"?"retry-task":["paused","queued"].includes(t.state)?"resume-task":"task";
  const label=t.state==="running"?"暂停":t.state==="failed"?"重试":t.state==="paused"?"继续":t.state==="queued"?"开始演示":"查看结果";
  return button(label,action,t.state==="running"?"pause":t.state==="failed"?"refresh":"","small",`data-id="${t.id}"`);
}
function buildMixPlan(){
  const mix=state.mix;
  let seed=2166136261;
  for(const c of `${mix.seed}|${mix.pool}|${mix.template}`)seed=Math.imul(seed^c.charCodeAt(0),16777619)>>>0;
  const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
  const pool=state.materials.filter(m=>m.image!==null&&(mix.pool!=="shots"||m.type==="shot"));
  const durations=mix.template==="teaching"?[5,9,10,10,8]:[4,5,6,6,5];
  const names=mix.template==="teaching"?["开场","手法示范","细节特写","课堂过程","作品展示"]:["开场","作品一","作品二","细节","收尾"];
  mix.plan={seed:mix.seed,pool:mix.pool,template:mix.template,id:`PLAN-${seed.toString(16).slice(0,6).toUpperCase()}`,clips:durations.map((duration,i)=>{const m=pool[Math.floor(random()*pool.length)];return {material:m.id,image:m.image,name:names[i],source:m.name,duration};})};
  mix.clip=0;
}
function renderStudio(){
  if(!state.mix.plan)buildMixPlan();
  const mix=state.mix,plan=mix.plan,clip=plan.clips[mix.clip],duration=plan.clips.reduce((s,c)=>s+c.duration,0);
  const stale=mix.seed!==plan.seed||mix.template!==plan.template||mix.pool!==plan.pool;
  return `${pageHeader("混剪工作室","选好素材和节奏，先看选片方案，再创建混剪任务。",button("查看混剪任务","mix-tasks","tasks"))}
    <div class="studio-layout"><section class="panel studio-config"><h2 class="panel-title"><span class="step-marker">01</span>混剪配置</h2>
      <div class="form-field"><label for="mix-template">混剪模板</label><select id="mix-template"><option value="teaching" ${mix.template==="teaching"?"selected":""}>教学展示 · 42 秒</option><option value="showcase" ${mix.template==="showcase"?"selected":""}>作品速览 · 26 秒</option></select><span class="field-help">开场 → 示范 → 细节 → 过程 → 作品</span></div>
      <div class="form-field"><label for="mix-pool">素材池</label><select id="mix-pool"><option value="all" ${mix.pool==="all"?"selected":""}>美甲教学 · 全部示例素材</option><option value="shots" ${mix.pool==="shots"?"selected":""}>已切分镜头 · 2 个片段</option></select></div>
      <div class="form-field"><label for="mix-seed">随机种子</label><div class="field-inline"><input id="mix-seed" class="field-input mono" value="${escapeHtml(mix.seed)}" maxlength="24"><button class="icon-button" data-action="shuffle-mix" aria-label="更换种子并重新选片">${icon("refresh")}</button></div><span class="field-help">相同种子与配置会得到相同选片。</span></div>
      <div class="form-field"><span class="field-label">输出内容</span><div class="output-checks"><label class="check-label"><input type="checkbox" data-mix-output="preview" ${mix.outputs.includes("preview")?"checked":""}>预览 MP4</label><label class="check-label"><input type="checkbox" data-mix-output="draft" ${mix.outputs.includes("draft")?"checked":""}>剪映草稿</label></div></div>
      ${button("生成选片方案","build-mix","spark","full")}
      ${notice("预览 MP4 用于检查选片；剪映中的标题和关键帧仍需导出为最终成片。")}
    </section><section class="studio-canvas"><div class="section-head"><h2>选片预览 <small>STORYBOARD</small></h2><span class="tag">已固定方案</span></div>
      <div class="studio-preview">${imageTag(clip.image,clip.source)}<span class="preview-tag">选片结构示意 · ${mix.clip+1} / ${plan.clips.length}</span><div class="preview-overlay"><h3>${clip.name}</h3><p>${escapeHtml(clip.source)}</p></div></div>
      <div class="preview-controls"><button class="icon-button" data-action="next-clip" aria-label="切换下一镜头">${icon("chevron")}</button><span class="mono">00:${String(plan.clips.slice(0,mix.clip).reduce((s,c)=>s+c.duration,0)).padStart(2,"0")}</span><div class="progress green"><span style="width:${(mix.clip+1)/plan.clips.length*100}%"></span></div><span class="mono">${duration} 秒</span><span>选片示意</span></div>
      <div class="timeline"><div class="timeline-ruler"><span>00:00</span><span>00:10</span><span>00:20</span><span>00:${duration}</span></div><div class="timeline-track">${plan.clips.map((c,i)=>`<button class="timeline-clip ${mix.clip===i?"active":""}" style="flex:${c.duration}" data-action="mix-clip" data-index="${i}" aria-label="预览第${i+1}镜头：${c.name}">${imageTag(c.image,c.name)}<span>${c.name} · ${c.duration}s</span></button>`).join("")}</div><div class="audio-track">${icon("sound")}原片音轨 · 保留素材声音</div><div class="plan-summary"><span class="mono">${plan.id} · SEED ${escapeHtml(plan.seed)}</span><span>5 个镜头 · ${duration} 秒</span></div></div>
      <div class="studio-bottom"><p>${stale?"配置已修改，请重新生成选片方案。":"方案已固定，创建任务将使用当前选片。"}</p>${button("创建混剪任务","create-mix","plus","primary",stale||!mix.outputs.length?"disabled":"")}</div>
    </section></div>`;
}
function publishFormFor(output){
  if(!state.publish.forms[output.id])state.publish.forms[output.id]={title:output.title,caption:output.caption};
  return state.publish.forms[output.id];
}
function renderPublish(){
  const pub=state.publish,o=outputs.find(x=>x.id===pub.id),form=publishFormFor(o),receipt=pub.receipts.find(r=>r.output===o.id);
  return `${pageHeader("成片与发布","挑选确认好的成片，完成最后一次检查。",button("发布记录","publish-history","clock"))}
    <div class="publish-layout"><aside class="publish-list">${sectionHead("选择产物","","",`${outputs.length} 个`)}${outputs.map(item=>`<button class="publish-item ${o.id===item.id?"active":""}" data-action="select-output" data-id="${item.id}">${imageTag(item.image,item.name)}<h3>${item.name}</h3><small>${item.duration} · ${item.size}</small><div style="margin-top:7px">${badge(item.type==="final"?"ready":"queued",item.label)}</div></button>`).join("")}</aside>
    <section class="publish-form">${o.type==="draft"?`<div class="panel"><h2>这是剪映草稿</h2><p class="setting-note" style="margin-top:15px">草稿需要在剪映中精修并导出 MP4，之后才可作为发布文件。这个原型不打开实际剪映工程。</p>${notice("请选择左侧的已确认成片体验发布流程。")}${button("查看草稿信息","draft-info","folder","full")}</div>`:`<div class="panel">
      <h2 class="panel-title"><span class="step-marker">01</span>发布信息</h2><div class="form-field"><label for="publish-title">标题</label><input id="publish-title" maxlength="55" value="${escapeHtml(form.title)}"></div><div class="form-field"><label for="publish-caption">文案与话题</label><textarea id="publish-caption" maxlength="1000">${escapeHtml(form.caption)}</textarea></div>
      <div class="form-two-col"><div class="form-field"><span class="field-label">发布封面</span><button class="radio-option" data-action="cover"><span>${icon("image")}</span><span>使用成片首帧<small>查看封面设置说明</small></span></button></div><div class="form-field"><span class="field-label">文件规格</span><div class="radio-option"><span>${icon("film")}</span><span>1080 × 1920 · MP4<small>${o.duration} · ${o.size} · 示例元数据</small></span></div></div></div>
      <h2 class="panel-title" style="margin-top:8px"><span class="step-marker">02</span>平台与账号</h2><div class="publish-target"><span class="douyin-logo">♪</span><div><h3>抖音 · 青序美甲课堂</h3><small>演示账号 @qingxu_demo · Chrome 插件</small></div>${badge("ready","演示连接")}</div><p class="field-help" style="margin-bottom:24px">首版优先接入抖音，小红书与视频号后续接入。</p>
      <h2 class="panel-title"><span class="step-marker">03</span>执行方式</h2><div class="radio-stack">
        <label class="radio-option"><input type="radio" name="publish-mode" value="prefill" ${pub.mode==="prefill"?"checked":""}><span>预填后，我来确认 <span class="tag">推荐</span><small>在电脑发布页上传并填写信息，停在最终发布前。</small></span></label>
        <label class="radio-option"><input type="radio" name="publish-mode" value="direct" ${pub.mode==="direct"?"checked":""}><span>直接发布<small>确认本条成片、账号和文案后，再提交发布。</small></span></label>
      </div>
      ${o.type==="preview"?notice("这份文件是预览 MP4，可能不包含剪映后加的标题与特效。请先确认它就是要发布的版本。",true):""}
      <label class="confirm-row"><input id="publish-confirm" type="checkbox" ${pub.confirmed?"checked":""}><span>我已核对成片、封面、文案和目标账号${o.type==="preview"?"，确认使用这份预览文件":""}。</span></label>
      ${button(pub.mode==="prefill"?"模拟预填发布页":"模拟直接发布","start-publish","send","primary full",pub.confirmed&&form.title.trim()?"":"disabled")}
      <p class="field-help" style="text-align:center;margin-top:10px">仅演示交互，不上传文件，也不操作真实账号。</p>
      ${receipt?renderReceipt(receipt):""}
    </div>`}</section></div>`;
}
function renderReceipt(receipt){
  return `<div class="receipt"><h3>${icon("circleCheck")} ${receipt.mode==="prefill"?"预填完成 · 等待人工确认":"已模拟提交发布"}</h3><p>成片：${escapeHtml(receipt.name)}</p><p>账号：抖音 · 青序美甲课堂（演示）</p><div class="receipt-row"><span class="mono">${receipt.id}</span>${badge(receipt.mode==="prefill"?"waiting":"complete",receipt.mode==="prefill"?"待人工确认":"已提交（模拟）")}</div>${receipt.mode==="prefill"?`<p>真实版本会停留在电脑创作者发布页，等待你点击发布。</p>`:""}</div>`;
}
function renderSettings(){
  const s=state.settings;
  return `${pageHeader("设置","管理本地目录、处理偏好与浏览器连接。",button("保存设置","save-settings","check","primary"))}
    <div class="settings-layout"><div class="panel"><div class="settings-group"><h2>本地目录</h2>
      ${[["source","素材目录"],["output","处理结果目录"],["draft","剪映草稿目录"]].map(([key,label])=>`<div class="form-field"><label for="setting-${key}">${label}</label><input id="setting-${key}" value="${escapeHtml(s[key])}" spellcheck="false"></div>`).join("")}<p class="field-help" style="margin-bottom:20px">这里展示目录配置的交互，不会读取或修改你的实际目录。</p></div>
      <div class="settings-group"><h2>处理偏好</h2><div class="form-field"><label for="setting-model">转录模型</label><select id="setting-model">${["tiny","base","small","medium"].map(m=>`<option ${s.model===m?"selected":""}>${m}</option>`).join("")}</select></div><label class="switch-label"><span>复用已有分析结果<small>已有结果时不重复运行相同处理。</small></span><input class="toggle" type="checkbox" id="setting-reuse" ${s.reuse?"checked":""}></label><label class="switch-label"><span>优先保留原始长镜头<small>在原始切镜基础上进行后续处理。</small></span><input class="toggle" type="checkbox" id="setting-longShots" ${s.longShots?"checked":""}></label></div></div>
      <aside><div class="panel"><h2 class="panel-title">连接与依赖 <span class="tag">示例</span></h2>${[["本地处理引擎","演示在线"],["FFmpeg","可用 · 演示"],["Whisper",`${s.model} · 演示`],["Chrome 发布插件","已配对 · 演示"]].map(([name,status])=>`<div class="dependency-row"><span>${name}</span>${badge("ready",status)}</div>`).join("")}<div style="margin-top:20px">${button("演示连接检查","check-connection","refresh","full")}</div></div>${notice("原型设置只在当前页面会话保留；刷新后恢复示例值，不保存真实凭据。")}</aside>
    </div>`;
}

// Overlays preserve focus and keep the background inert.
let returnFocus=null,toastTimer;
function showOverlay(html,drawer=false,preserveFocus=false){
  if(!preserveFocus)returnFocus=document.activeElement;
  $("#overlay-root").innerHTML=`<div class="overlay ${drawer?"drawer-overlay":""}">${html}</div>`;
  $(".main-shell").inert=true;$("#sidebar").inert=true;document.body.style.overflow="hidden";
  requestAnimationFrame(()=>$("#overlay-root button, #overlay-root input")?.focus());
}
function closeOverlay(){
  $("#overlay-root").innerHTML="";$(".main-shell").inert=false;$("#sidebar").inert=false;document.body.style.overflow="";
  state.wizard=null;state.drawer=null;state.dialog=null;
  if(returnFocus?.isConnected)returnFocus.focus();else $("#main").focus({preventScroll:true});
}
function toast(text){
  clearTimeout(toastTimer);$("#toast").textContent=text;$("#toast").classList.add("show");
  toastTimer=setTimeout(()=>$("#toast").classList.remove("show"),3200);
}
function modal(title,subtitle,body,footer="",wide=false){
  return `<section class="modal" role="dialog" aria-modal="true" aria-labelledby="dialog-title" ${wide?'style="width:720px"':""}><header class="modal-head"><div><h2 id="dialog-title">${title}</h2><p>${subtitle}</p></div><button class="icon-button" data-action="close-overlay" aria-label="关闭弹窗">${icon("close")}</button></header><div class="modal-body">${body}</div>${footer?`<footer class="modal-footer">${footer}</footer>`:""}</section>`;
}
function openWizard(ids=[]){
  state.wizard={step:1,selected:new Set(ids),options:new Set(["原始切镜","音频转录"]),threshold:27,name:"",inputType:"library"};
  renderWizard();
}
function renderWizard(preserve=false){
  const w=state.wizard,selected=state.materials.filter(m=>w.selected.has(m.id));
  const steps=`<div class="steps">${["选择素材","处理选项","确认创建"].map((name,i)=>`<div class="wizard-step ${w.step===i+1?"active":w.step>i+1?"done":""}"><span>${w.step>i+1?"✓":i+1}</span>${name}</div>`).join("")}</div>`;
  let body="";
  if(w.step===1)body=`<div class="import-zone">${icon("upload")}<h3>从电脑选择视频</h3><p>仅演示导入，不会上传或处理文件。</p>${button("选择本地视频","choose-file","plus","small")}<input type="file" id="local-files" accept="video/*,.mp4,.mov,.mkv,.webm" multiple hidden></div><div class="section-head"><h3>或选择已有素材</h3><span class="muted" id="wizard-selected-count" style="font-size:10px">已选 ${selected.length} 份</span></div><div class="wizard-materials">${state.materials.filter(m=>m.type!=="image").map(m=>`<label class="wizard-material"><input type="checkbox" data-wizard-material="${m.id}" ${w.selected.has(m.id)?"checked":""}>${m.image!==null?imageTag(m.image,m.name):icon("film")}<span>${escapeHtml(m.name)}<small>${m.duration} · ${m.size}</small></span></label>`).join("")}</div>`;
  if(w.step===2)body=`<div class="form-field"><label for="wizard-name">任务名称</label><input id="wizard-name" maxlength="80" placeholder="${selected.length===1?escapeHtml(selected[0].name):`批量处理 · ${selected.length} 份素材`}" value="${escapeHtml(w.name)}"></div><div class="form-field"><span class="field-label">处理步骤</span><div class="option-grid">${[["视频清洗","使用现有清洗流程"],["原始切镜","按原始镜头拆分，保留长镜头"],["音频转录","提取语音，生成带时间戳文本"],["语义分镜","基于镜头与转录进行语义分组"]].map(([name,desc])=>`<label class="option-tile"><input type="checkbox" data-wizard-option="${name}" ${w.options.has(name)?"checked":""}><span>${name}<small>${desc}</small></span></label>`).join("")}</div></div><div class="form-field"><label for="wizard-threshold">切镜阈值 <span class="muted">（越低越敏感）</span></label><input type="number" id="wizard-threshold" min="1" max="100" value="${w.threshold}"></div>${notice("语义分镜会同时选中原始切镜和音频转录，保证前置结果完整。")}`;
  if(w.step===3)body=`<dl class="summary-list"><dt>任务名称</dt><dd>${escapeHtml(w.name|| (selected.length===1?selected[0].name:`批量处理 · ${selected.length} 份素材`))}</dd><dt>选择素材</dt><dd>${selected.map(m=>escapeHtml(m.name)).join("<br>")}</dd><dt>处理流程</dt><dd>${orderedOptions(w.options).join(" → ")}</dd><dt>切镜阈值</dt><dd>${w.threshold}</dd><dt>输出位置</dt><dd class="mono">./output/&lt;视频名_时间&gt;/</dd></dl>${notice("创建后进入演示队列，可在任务中心查看状态；不运行实际视频处理。")}`;
  const nextDisabled=w.step===1?!selected.length:w.step===2?!w.options.size:false;
  showOverlay(modal("新建处理任务","选择素材，安排好下一步。",steps+body,`<span>步骤 ${w.step} / 3 · 示例工作流</span><div>${button(w.step===1?"取消":"上一步",w.step===1?"close-overlay":"wizard-back")}${button(w.step===3?"创建演示任务":"下一步",w.step===3?"wizard-create":"wizard-next",w.step===3?"plus":"arrow","primary",`id="wizard-next" ${nextDisabled?"disabled":""}`)}</div>`),false,preserve);
}
function openMaterial(id,tab="overview"){
  const m=state.materials.find(x=>x.id===id);if(!m)return;
  const preserve=state.drawer?.type==="material";
  state.drawer={type:"material",id,tab};
  const details=tab==="overview"?`<dl class="summary-list"><dt>素材类型</dt><dd>${{video:"原始视频",image:"作品照片",shot:"镜头片段"}[m.type]}</dd><dt>时长 / 大小</dt><dd>${m.duration} · ${m.size}</dd><dt>处理状态</dt><dd>${m.state}</dd><dt>画面规格</dt><dd>${m.image===null?"本地选择 · 待实际分析":"1920 × 1080 · 示例元数据"}</dd><dt>导入时间</dt><dd>${m.date}</dd></dl>`:
    tab==="scenes"?(m.scenes?`<p class="field-help" style="margin-bottom:12px">共 ${m.scenes} 个原始镜头 · 下方为分镜排版示意</p><div class="scene-list">${Array.from({length:Math.min(m.scenes,6)},(_,i)=>`<div class="scene-thumb">${imageTag((m.image+i)%4,`镜头${i+1}示意`)}<span>${String(i+1).padStart(2,"0")} / 00:${String(i*8).padStart(2,"0")}</span></div>`).join("")}</div>`:`<div class="empty-state" style="padding:30px 0">${icon("scissors")}<h3>还没有镜头分析</h3><p>先创建处理任务，再查看镜头结果。</p></div>`):
    (m.state==="已分析"?`<div class="activity-row"><time class="mono muted">00:00</time><div>今天我们来练习法式美甲的基础线条。<small>转录示例</small></div></div><div class="activity-row"><time class="mono muted">00:12</time><div>先找到中线，再从两侧慢慢向中间连接。<small>转录示例</small></div></div><div class="activity-row"><time class="mono muted">00:28</time><div>注意笔尖的力度，保持线条流畅。<small>转录示例</small></div></div>`:`<p class="setting-note">当前素材还没有转录结果。</p>`);
  showOverlay(`<section class="drawer" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><header class="modal-head"><div><h2 id="dialog-title">素材详情</h2><p>ASSET / ${m.id.toUpperCase()}</p></div><button class="icon-button" data-action="close-overlay" aria-label="关闭详情">${icon("close")}</button></header><div class="drawer-body"><div class="drawer-preview">${materialVisual(m)}<span>${m.image===null?"本地文件 · 未处理":"素材信息视图"}</span></div><h2 style="font-size:16px">${escapeHtml(m.name)}</h2><div class="detail-tabs">${[["overview","基本信息"],["scenes","镜头"],["transcript","转录"]].map(([key,label])=>`<button class="detail-tab ${tab===key?"active":""}" data-action="material-tab" data-value="${key}">${label}</button>`).join("")}</div>${details}</div><footer class="drawer-footer">${button("关闭","close-overlay")}${m.type!=="image"?button("创建处理任务","material-task","plus","primary",`data-id="${m.id}"`):button("去混剪工作室","material-studio","scissors","primary")}</footer></section>`,true,preserve);
}
function openTask(id){
  const t=tasks.find(x=>x.id===id);if(!t)return;
  const preserve=state.drawer?.type==="task";
  state.drawer={type:"task",id};
  showOverlay(`<section class="drawer" role="dialog" aria-modal="true" aria-labelledby="dialog-title"><header class="modal-head"><div><h2 id="dialog-title">任务详情</h2><p>${t.id} · ${t.type}</p></div><button class="icon-button" data-action="close-overlay" aria-label="关闭详情">${icon("close")}</button></header><div class="drawer-body"><div style="display:flex;justify-content:space-between;gap:15px;align-items:flex-start"><h2 style="font-size:16px">${escapeHtml(t.name)}</h2>${badge(t.state)}</div><div style="margin-top:24px"><div class="progress-label"><span>${t.stage}</span><span>${t.progress}%</span></div><div class="progress"><span style="width:${t.progress}%"></span></div></div>
    <ul class="log-list"><li>任务已创建<time>${t.time} · 示例事件</time></li><li>素材检查${t.state==="queued"?"等待中":"通过"}<time>${t.material || "混剪方案"} · 本地素材</time></li><li class="current">${t.stage}<time>${t.state==="failed"?"等待修复后重试":t.state==="complete"?"产物已就绪":t.state==="paused"?"已暂停演示":"当前演示阶段"}</time></li></ul>
    ${t.error&&t.state==="failed"?notice(t.error,true):""}
    <h3 style="margin:24px 0 12px">处理选项</h3><p class="setting-note">${t.options.join(" · ")}</p>
    ${t.plan?`<h3 style="margin:22px 0 10px">固定选片方案</h3><p class="setting-note mono">${t.plan.id} · SEED ${escapeHtml(t.plan.seed)}</p><p class="setting-note">${t.plan.clips.map(c=>`${c.name} ${c.duration}s`).join(" → ")}</p>`:""}
    <h3 style="margin:24px 0 12px">日志示例</h3><div class="code-log">[demo] task_id=${t.id}\n[demo] state=${t.state}\n[demo] ${t.state==="failed"?"transcription model unavailable":t.stage}\n[demo] no real processing performed</div>
    ${t.state==="running"?`<div style="margin-top:22px">${button("推进一个演示阶段","advance-task","arrow","full",`data-id="${t.id}"`)}</div>`:""}</div><footer class="drawer-footer">${button("关闭","close-overlay")}${t.state==="complete"?button("查看产物示意","task-result","folder","primary",`data-id="${t.id}"`):taskActionButton(t)}</footer></section>`,true,preserve);
}
function showGuide(){
  state.dialog="guide";
  showOverlay(modal("从素材开始，走完整个流程","交互原型 · v0.1",`<div class="radio-stack">${[["01","素材库","浏览、搜索、选择素材；右侧抽屉查看镜头和转录。"],["02","处理任务","点击“新建任务”，完成选择素材、处理选项和确认。"],["03","混剪工作室","切换模板与随机种子，生成固定选片方案。"],["04","成片与发布","核对成片与账号，体验预填和直接发布的确认流程。"]].map(([n,title,text])=>`<div class="radio-option"><span class="step-marker">${n}</span><span>${title}<small>${text}</small></span></div>`).join("")}</div>${notice("所有处理进度、连接、账号和发布回执均为示例。刷新页面可恢复初始数据。")}`,`<span>可按 Esc 关闭弹窗</span>${button("开始体验","close-overlay","arrow","primary")}`));
}
function updateTask(id,next){
  const t=tasks.find(x=>x.id===id);if(!t)return;
  t.state=next;
  if(next==="running")t.stage=t.progress>0?"继续处理（演示）":"准备处理（演示）";
  if(next==="paused")t.stage="演示已暂停";
  if(next==="queued"){t.progress=0;t.stage="已重新排队";}
  renderPage();if(state.drawer?.type==="task")openTask(id);
  toast({running:"已开始 / 继续演示任务",paused:"任务演示已暂停",queued:"已重新加入演示队列"}[next]);
}
function simulatePublish(){
  const pub=state.publish,o=outputs.find(x=>x.id===pub.id),form=publishFormFor(o);
  if(!pub.confirmed||!form.title.trim()||o.type==="draft")return;
  if(pub.mode==="direct"){
    state.dialog="direct-publish";
    showOverlay(modal("确认模拟直接发布","请核对本条内容与目标账号。",`<dl class="summary-list"><dt>成片</dt><dd>${o.name}</dd><dt>标题</dt><dd>${escapeHtml(form.title)}</dd><dt>目标账号</dt><dd>抖音 · 青序美甲课堂（演示）</dd><dt>执行方式</dt><dd>直接发布</dd></dl>${notice("当前仅生成模拟回执，不会连接平台或发布真实内容。",true)}`,`<span>本次仅演示 1 条成片</span><div>${button("返回检查","close-overlay")}${button("确认模拟提交","confirm-publish","send","primary")}</div>`));
  }else completePublish();
}
function completePublish(){
  const pub=state.publish,o=outputs.find(x=>x.id===pub.id);
  const receipt={id:`PUB-DEMO-${String(pub.receipts.length+1).padStart(3,"0")}`,output:o.id,name:o.name,mode:pub.mode};
  pub.receipts.unshift(receipt);
  closeOverlay();renderPage();
  requestAnimationFrame(()=>$(".receipt")?.scrollIntoView({behavior:"smooth",block:"nearest"}));
  toast(pub.mode==="prefill"?"模拟预填完成，等待人工确认":"已生成模拟提交回执");
}

document.addEventListener("click",(event)=>{
  const el=event.target.closest("[data-action]");
  if(!el){
    if(event.target.classList.contains("overlay"))closeOverlay();
    return;
  }
  const action=el.dataset.action,id=el.dataset.id,value=el.dataset.value;
  if(action.startsWith("go-")){route(action.slice(3));return;}
  const actions={
    "menu":()=>$("#sidebar").classList.toggle("mobile-open"),
    "guide":showGuide,
    "new-task":()=>openWizard(),
    "import":()=>openWizard(),
    "selected-task":()=>{
      const ids=[...state.selected].filter(id=>state.materials.find(m=>m.id===id)?.type!=="image");
      if(!ids.length){toast("照片可用于混剪，请选择视频创建处理任务");return;}
      openWizard(ids);
    },
    "material":()=>openMaterial(id),
    "material-tab":()=>openMaterial(state.drawer.id,value),
    "material-task":()=>{closeOverlay();openWizard([id]);},
    "material-studio":()=>{closeOverlay();route("studio");},
    "task":()=>openTask(id),
    "task-result":()=>{const t=tasks.find(x=>x.id===id);closeOverlay();if(t.type==="混剪任务")route("publish");else openMaterial(t.material);},
    "pause-task":()=>updateTask(id,"paused"),
    "resume-task":()=>updateTask(id,"running"),
    "retry-task":()=>updateTask(id,"queued"),
    "advance-task":()=>{
      const t=tasks.find(x=>x.id===id);
      t.progress=Math.min(100,t.progress+25);
      t.stage=t.progress===100?"演示处理完成":"写入分析结果（演示）";
      if(t.progress===100)t.state="complete";
      renderPage();openTask(id);toast(t.progress===100?"演示任务已完成":"已推进演示进度");
    },
    "library-filter":()=>{state.libraryFilter=value;renderPage();},
    "task-filter":()=>{state.taskFilter=value;renderPage();},
    "view-grid":()=>{state.view="grid";renderPage();},
    "view-list":()=>{state.view="list";renderPage();},
    "clear-library":()=>{state.libraryQuery="";state.libraryFilter="all";renderPage();},
    "clear-selection":()=>{state.selected.clear();refreshLibrary();},
    "reset-tasks":()=>{state.taskFilter="all";state.taskQuery="";renderPage();},
    "close-overlay":closeOverlay,
    "choose-file":()=>$("#local-files").click(),
    "wizard-back":()=>{state.wizard.step--;renderWizard(true);},
    "wizard-next":()=>{
      const w=state.wizard;
      if(w.step===1&&!w.selected.size)return;
      if(w.step===2){
        if(!w.options.size){toast("至少选择一个处理步骤");return;}
        if(!Number.isFinite(w.threshold)||w.threshold<1||w.threshold>100){toast("切镜阈值请输入 1–100");return;}
      }
      w.step++;renderWizard(true);
    },
    "wizard-create":()=>{
      const w=state.wizard,selected=state.materials.filter(m=>w.selected.has(m.id));
      selected.forEach((m,i)=>tasks.unshift({id:`JF-${1027+tasks.filter(t=>Number(t.id.slice(3))>=1027).length}`,name:w.name?`${w.name}${selected.length>1?` · ${i+1}`:""}`:m.name,type:"分析任务",state:"queued",progress:0,stage:"等待本地引擎",time:"刚刚",material:m.id,options:orderedOptions(w.options),threshold:w.threshold}));
      state.taskFilter="all";state.taskQuery="";state.selected.clear();closeOverlay();route("tasks");toast(`已创建 ${selected.length} 个演示任务`);
    },
    "build-mix":()=>{if(!state.mix.seed.trim()){toast("请填写随机种子");return;}buildMixPlan();renderPage();toast("选片方案已固定，可以创建混剪任务");},
    "shuffle-mix":()=>{state.mix.seed=String(Math.floor(Math.random()*90000000)+10000000);buildMixPlan();renderPage();toast("已更换种子并重新选片");},
    "mix-clip":()=>{state.mix.clip=Number(el.dataset.index);renderPage();},
    "next-clip":()=>{state.mix.clip=(state.mix.clip+1)%state.mix.plan.clips.length;renderPage();},
    "mix-tasks":()=>{state.taskQuery="混剪";state.taskFilter="all";route("tasks");},
    "create-mix":()=>{
      const mix=state.mix,plan=mix.plan;
      if(mix.seed!==plan.seed||mix.template!==plan.template||mix.pool!==plan.pool||!mix.outputs.length)return;
      const task={id:`JF-${Math.max(...tasks.map(t=>Number(t.id.slice(3))))+1}`,name:`美甲教学 · 混剪方案 ${plan.id.slice(-6)}`,type:"混剪任务",state:"queued",progress:0,stage:"已固定选片，等待合成",time:"刚刚",material:plan.clips[0].material,options:mix.outputs.map(x=>x==="preview"?"预览 MP4":"剪映草稿"),plan:structuredClone(plan)};
      tasks.unshift(task);state.taskFilter="all";state.taskQuery="";route("tasks");toast("混剪演示任务已创建，选片方案保持不变");
    },
    "select-output":()=>{state.publish.id=id;state.publish.confirmed=false;renderPage();},
    "cover":()=>{
      const o=outputs.find(x=>x.id===state.publish.id);
      state.dialog="cover";showOverlay(modal("封面设置","使用所选成片的首帧",`<dl class="summary-list"><dt>所选成片</dt><dd>${o.name}</dd><dt>封面来源</dt><dd>成片首帧</dd><dt>画面比例</dt><dd>9:16</dd></dl>${notice("当前未接入视频文件。实际版本会在这里展示提取到的首帧，供你检查后确认。")}`,`<span>封面策略示意</span>${button("保留此设置","close-overlay","check","primary")}`));
    },
    "draft-info":()=>{state.dialog="draft";showOverlay(modal("剪映草稿信息","产物类型：草稿目录",`<dl class="summary-list"><dt>草稿名称</dt><dd>法式线条 · 剪映草稿</dd><dt>包含内容</dt><dd>素材引用、时间线、标题与关键帧示意</dd><dt>下一步</dt><dd>在剪映中检查画面与字幕，再导出最终 MP4。</dd></dl>`,`${button("关闭","close-overlay")}`));},
    "start-publish":simulatePublish,
    "confirm-publish":completePublish,
    "publish-history":()=>{
      state.dialog="history";showOverlay(modal("发布记录","本次会话的模拟回执",state.publish.receipts.length?state.publish.receipts.map(renderReceipt).join(""):`<div class="empty-state" style="padding:25px">${icon("send")}<h3>还没有发布记录</h3><p>完成一次模拟预填后，这里会显示回执。</p></div>`,`${button("关闭","close-overlay")}`));
    },
    "save-settings":()=>{
      for(const key of ["source","output","draft"])state.settings[key]=$(`#setting-${key}`).value;
      state.settings.model=$("#setting-model").value;state.settings.reuse=$("#setting-reuse").checked;state.settings.longShots=$("#setting-longShots").checked;
      renderPage();toast("设置已保留在本次原型会话中");
    },
    "check-connection":()=>toast("演示检查完成：引擎、FFmpeg、Whisper、插件均显示可用"),
    "activity":()=>{
      state.dialog="activity";
      showOverlay(modal("工作空间动态","仅展示示例活动",`<div class="activity-row">${icon("scissors")}<div>秋日美甲 · 教学混剪 03 已完成<small>今天 13:58 · 预览 MP4 与剪映草稿</small></div></div><div class="activity-row">${icon("folder")}<div>新增 4 份教学素材<small>今天 11:06 · 原始视频与学员作品</small></div></div><div class="activity-row">${icon("info")}<div>基础课任务需要重试<small>今天 10:42 · 转录模型未准备完成</small></div></div>`,`${button("关闭","close-overlay")}`));
    }
  };
  actions[action]?.();
});
document.addEventListener("input",(event)=>{
  const el=event.target;
  if(el.id==="library-search"){state.libraryQuery=el.value;refreshLibrary();}
  if(el.id==="task-search"){state.taskQuery=el.value;$("#task-results").innerHTML=renderTaskResults();}
  if(el.id==="wizard-name")state.wizard.name=el.value;
  if(el.id==="wizard-threshold")state.wizard.threshold=el.value===""?NaN:Number(el.value);
  if(el.id==="mix-seed"){
    state.mix.seed=el.value;
    $(".studio-bottom p").textContent="种子已修改，请重新生成选片方案。";
    $('[data-action="create-mix"]').disabled=true;
  }
  if(["publish-title","publish-caption"].includes(el.id)){
    const form=publishFormFor(outputs.find(x=>x.id===state.publish.id));
    form[el.id==="publish-title"?"title":"caption"]=el.value;
    state.publish.confirmed=false;$("#publish-confirm").checked=false;$('[data-action="start-publish"]').disabled=true;
  }
});
document.addEventListener("change",(event)=>{
  const el=event.target;
  if(el.dataset.select){el.checked?state.selected.add(el.dataset.select):state.selected.delete(el.dataset.select);refreshLibrary();}
  if(el.id==="select-all"){filteredMaterials().forEach(m=>el.checked?state.selected.add(m.id):state.selected.delete(m.id));refreshLibrary();}
  if(el.dataset.wizardMaterial){
    const w=state.wizard;el.checked?w.selected.add(el.dataset.wizardMaterial):w.selected.delete(el.dataset.wizardMaterial);
    $("#wizard-selected-count").textContent=`已选 ${w.selected.size} 份`;$("#wizard-next").disabled=!w.selected.size;
  }
  if(el.dataset.wizardOption){
    const w=state.wizard,name=el.dataset.wizardOption;
    el.checked?w.options.add(name):w.options.delete(name);
    if(name==="语义分镜"&&el.checked){w.options.add("原始切镜");w.options.add("音频转录");}
    if(["原始切镜","音频转录"].includes(name)&&!el.checked)w.options.delete("语义分镜");
    renderWizard(true);
  }
  if(el.id==="local-files"){
    const files=[...el.files].filter(f=>f.type.startsWith("video/")||/\.(mp4|mov|mkv|webm)$/i.test(f.name));
    files.forEach((file,i)=>{
      const m={id:`local-${Date.now()}-${i}`,name:file.name,type:"video",image:null,duration:"待分析",size:`${(file.size/1024/1024).toFixed(1)} MB`,date:"刚刚",state:"待处理",scenes:0};
      state.materials.unshift(m);state.wizard.selected.add(m.id);
    });
    renderPage();renderWizard(true);toast(files.length?`已选择 ${files.length} 个本地视频，仅登记文件名与大小`:"请选择视频文件");
  }
  if(el.id==="mix-template"){state.mix.template=el.value;renderPage();}
  if(el.id==="mix-pool"){state.mix.pool=el.value;renderPage();}
  if(el.dataset.mixOutput){const key=el.dataset.mixOutput;state.mix.outputs=el.checked?[...state.mix.outputs,key]:state.mix.outputs.filter(x=>x!==key);renderPage();}
  if(el.name==="publish-mode"){state.publish.mode=el.value;state.publish.confirmed=false;renderPage();}
  if(el.id==="publish-confirm"){state.publish.confirmed=el.checked;$('[data-action="start-publish"]').disabled=!el.checked||!$("#publish-title").value.trim();}
});
document.addEventListener("keydown",(event)=>{
  if(event.key==="Escape"){
    if($("#overlay-root").children.length)closeOverlay();else $("#sidebar").classList.remove("mobile-open");
  }
  if(event.key==="Tab"&&$("#overlay-root").children.length){
    const items=[...$("#overlay-root").querySelectorAll('button:not(:disabled),input:not([hidden]):not(:disabled),select,textarea,[tabindex="0"]')].filter(x=>x.offsetParent!==null);
    const first=items[0],last=items.at(-1);
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
  }
});
window.addEventListener("hashchange",()=>{if($("#overlay-root").children.length)closeOverlay();renderPage();window.scrollTo(0,0);});
document.querySelectorAll("[data-icon]").forEach(el=>el.innerHTML=icon(el.dataset.icon));
renderPage();

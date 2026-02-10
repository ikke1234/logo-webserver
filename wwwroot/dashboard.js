let token=null, role=null;
let ui=null; // {tabs, widgets}
let currentTabId=null;

async function apiGet(url){
  const r = await fetch(url);
  return {ok:r.ok, data: await r.json().catch(()=>null)};
}
async function apiPost(url, body){
  const r = await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  return {ok:r.ok, data: await r.json().catch(()=>null)};
}

async function login(){
  const u=document.getElementById("login-username").value;
  const p=document.getElementById("login-password").value;

  const res = await apiPost("/api/login",{username:u,password:p});
  if(!res.ok){ document.getElementById("login-error").textContent="Login fout"; return; }

  token=res.data.token; role=res.data.role;
  document.getElementById("login-panel").style.display="none";
  document.getElementById("app").style.display="block";

  await loadUI();
  renderTabs();
  openTab(ui.tabs[0]?.id);
}

async function loadUI(){
  const res = await apiGet(`/api/ui?token=${encodeURIComponent(token)}`);
  ui = res.data;
}

function renderTabs(){
  const bar=document.getElementById("tabbar");
  bar.innerHTML="";

  ui.tabs.forEach(t=>{
    const b=document.createElement("button");
    b.textContent=t.name;
    b.onclick=()=>openTab(t.id);
    bar.appendChild(b);
  });

  // admin paneel knop alleen voor admin
  if(role==="admin"){
    const b=document.createElement("button");
    b.textContent="Beheer";
    b.onclick=()=>openAdmin();
    bar.appendChild(b);
  }
}

function widgetDiv(w){
  const d=document.createElement("div");
  d.className="widget";
  d.style.gridColumn = `${w.x} / span ${w.w}`;
  d.style.gridRow = `${w.y} / span ${w.h}`;
  d.innerHTML = `<h3>${w.title}</h3><div id="w_${w.id}"></div>`;
  return d;
}

async function openTab(tabId){
  currentTabId=tabId;
  const area=document.getElementById("grid");
  area.innerHTML="";

  const widgets = ui.widgets.filter(w=>w.tab_id===tabId);
  widgets.forEach(w=>area.appendChild(widgetDiv(w)));

  await refreshValues();
  setInterval(refreshValues, 1000);
}

async function refreshValues(){
  if(!currentTabId) return;
  const res = await apiGet(`/api/values?token=${encodeURIComponent(token)}&tab_id=${currentTabId}`);
  if(!res.ok) return;

  const values = res.data.values;
  const widgets = ui.widgets.filter(w=>w.tab_id===currentTabId);

  widgets.forEach(w=>{
    const el=document.getElementById(`w_${w.id}`);
    const v = values[w.id];

    if(w.type==="gauge"){
      el.textContent = `${v} ${w.unit||""}`;
    } else if(w.type==="text"){
      el.textContent = `${v}`;
    } else if(w.type==="toggle"){
      el.innerHTML = `<button ${w.writable? "":"disabled"} onclick="toggleWidget(${w.id}, ${v?0:1})">${v?"AAN":"UIT"}</button>`;
    } else if(w.type==="setpoint"){
      el.innerHTML = `
        <div>Huidig: <b>${v}</b> ${w.unit||""}</div>
        <input id="sp_${w.id}" type="number" step="0.1">
        <button ${w.writable? "":"disabled"} onclick="writeSetpoint(${w.id})">Opslaan</button>
      `;
    }
  });
}

async function toggleWidget(widgetId, value){
  await apiPost("/api/write",{token, tab_id: currentTabId, widget_id: widgetId, value: !!value});
  await refreshValues();
}

async function writeSetpoint(widgetId){
  const v = parseFloat(document.getElementById(`sp_${widgetId}`).value);
  if(Number.isNaN(v)) return;
  await apiPost("/api/write",{token, tab_id: currentTabId, widget_id: widgetId, value: v});
  await refreshValues();
}

async function openAdmin(){
  document.getElementById("admin").style.display="block";
  document.getElementById("grid").style.display="none";
}

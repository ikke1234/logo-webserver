let token=null, role=null, username=null;
let ui=null;
let currentTabId=null;
let grid=null;
let editMode=false;
let pollTimer=null;

function qs(id){ return document.getElementById(id); }

async function apiGet(url){
  const r = await fetch(url);
  let data=null; try{ data=await r.json(); }catch{}
  return {ok:r.ok, data};
}
async function apiPost(url, body){
  const r = await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  let data=null; try{ data=await r.json(); }catch{}
  return {ok:r.ok, data};
}

async function login(){
  const u=qs("login-username").value;
  const p=qs("login-password").value;
  qs("login-error").textContent="";

  const res = await apiPost("/api/login",{username:u,password:p});
  if(!res.ok){ qs("login-error").textContent=res.data?.detail || "Login fout"; return; }

  token=res.data.token; role=res.data.role; username=res.data.username;

  qs("login-panel").style.display="none";

  if(res.data.force_pw_change){
    qs("pw-panel").style.display="block";
    return;
  }

  qs("app").style.display="block";
  await initApp();
}

async function forgotPassword(){
  const u=qs("login-username").value;
  if(!u){ qs("login-error").textContent="Vul gebruikersnaam in"; return; }
  await apiPost("/api/forgot_password",{username:u});
  qs("login-error").textContent="Request verstuurd. Admin kan je resetten.";
}

async function changePassword(){
  qs("pw-error").textContent="";
  const oldp=qs("pw-old").value;
  const newp=qs("pw-new").value;
  const res = await apiPost("/api/change_password",{token, old_password:oldp, new_password:newp});
  if(!res.ok){ qs("pw-error").textContent=res.data?.detail || "Fout"; return; }

  qs("pw-panel").style.display="none";
  qs("app").style.display="block";
  await initApp();
}

async function initApp(){
  // admin knoppen
  if(role==="admin"){
    qs("btnEdit").style.display="inline-block";
    qs("btnSave").style.display="inline-block";
    qs("btnAddWidget").style.display="inline-block";
    qs("btnAdmin").style.display="inline-block";
  }

  await loadUI();
  renderTabs();

  if(!grid){
    grid = GridStack.init({cellHeight: 140, margin: 8, disableOneColumnMode: true}, "#grid");
    grid.enableMove(false); grid.enableResize(false);
    grid.on("change", () => {}); // placeholder
  }

  if(ui.tabs.length>0) openTab(ui.tabs[0].id);
}

async function loadUI(){
  const res = await apiGet(`/api/ui?token=${encodeURIComponent(token)}`);
  ui = res.data;
}

function renderTabs(){
  const bar=qs("tabbar");
  bar.innerHTML="";
  ui.tabs.forEach(t=>{
    const b=document.createElement("button");
    b.textContent = `${t.name}`;
    b.onclick=()=>openTab(t.id);
    bar.appendChild(b);
  });
}

function setPLCStatus(plc){
  const el=qs("plcstatus");
  if(!plc || plc.ok){
    el.textContent="PLC: OK";
    el.style.background="#d4edda";
  } else {
    el.textContent="PLC: OFFLINE";
    el.style.background="#f8d7da";
  }
}

function makeWidgetEl(w){
  const wrap = document.createElement("div");
  wrap.className="grid-stack-item";
  wrap.setAttribute("gs-x", w.x);
  wrap.setAttribute("gs-y", w.y);
  wrap.setAttribute("gs-w", w.w);
  wrap.setAttribute("gs-h", w.h);
  wrap.dataset.id = w.id;

  const content = document.createElement("div");
  content.className="grid-stack-item-content";

  const card = document.createElement("div");
  card.className="widgetCard";
  card.innerHTML = `
    <button class="delBtn" onclick="deleteWidget(${w.id})">X</button>
    <div class="widgetTitle">${w.title}</div>
    <div id="w_${w.id}">...</div>
  `;
  content.appendChild(card);
  wrap.appendChild(content);
  return wrap;
}

async function openTab(tabId){
  currentTabId = tabId;
  editMode=false;
  setEditUI();

  // admin panel dicht
  qs("adminPanel").style.display="none";
  qs("grid").style.display="block";

  // grid leeg en widgets erin
  grid.removeAll(true);

  const widgets = ui.widgets.filter(w=>w.tab_id===tabId);
  widgets.forEach(w=>{
    grid.addWidget(makeWidgetEl(w));
  });

  if(pollTimer) clearInterval(pollTimer);
  await refreshValues();
  pollTimer = setInterval(refreshValues, 1000);
}

async function refreshValues(){
  if(!currentTabId) return;
  const res = await apiGet(`/api/values?token=${encodeURIComponent(token)}&tab_id=${currentTabId}`);
  if(!res.ok) return;

  setPLCStatus(res.data.plc);

  const values = res.data.values;
  const widgets = ui.widgets.filter(w=>w.tab_id===currentTabId);

  widgets.forEach(w=>{
    const el = document.getElementById(`w_${w.id}`);
    const v = values[w.id];

    if(!el) return;

    if(w.type==="lamp"){
      const on = !!v;
      el.innerHTML = `<span class="lamp ${on?"on":"off"}"></span>${on?"AAN":"UIT"}`;
    }
    else if(w.type==="toggle"){
      const txt = v ? "AAN" : "UIT";
      const dis = w.writable ? "" : "disabled";
      el.innerHTML = `<div class="widgetBtns"><button ${dis} onclick="writePoint(${w.id}, ${!v})">${txt}</button></div>`;
    }
    else if(w.type==="setpoint"){
      const dis = w.writable ? "" : "disabled";
      el.innerHTML = `
        <div>Huidig: <b>${v ?? ""}</b> ${w.unit||""}</div>
        <input id="sp_${w.id}" type="number" step="0.1">
        <button ${dis} onclick="writeSetpoint(${w.id})">Opslaan</button>
      `;
    }
    else {
      // gauge/analog/text voorlopig als groot getal (later kun je echte gauges tekenen)
      el.innerHTML = `<div class="widgetValue">${(v ?? "")}</div><div class="widgetUnit">${w.unit||""}</div>`;
    }
  });
}

async function writePoint(widgetId, value){
  await apiPost("/api/write",{token, tab_id: currentTabId, widget_id: widgetId, value});
  await refreshValues();
}

async function writeSetpoint(widgetId){
  const v=parseFloat(document.getElementById(`sp_${widgetId}`).value);
  if(Number.isNaN(v)) return;
  await writePoint(widgetId, v);
}

function setEditUI(){
  // grid lock/unlock
  grid.enableMove(editMode);
  grid.enableResize(editMode);

  // delete knoppen tonen in edit mode
  document.querySelectorAll(".delBtn").forEach(b=>{
    b.style.display = (editMode ? "block" : "none");
  });

  qs("btnEdit").textContent = editMode ? "Stop edit" : "Edit layout";
}

function toggleEdit(){
  if(role!=="admin") return;
  editMode = !editMode;
  setEditUI();
}

async function saveLayout(){
  if(role!=="admin") return;
  const items = [];
  grid.engine.nodes.forEach(n=>{
    const wid = parseInt(n.el.dataset.id, 10);
    items.push({id: wid, x: n.x, y: n.y, w: n.w, h: n.h});
  });

  const res = await apiPost("/api/admin/widgets/layout",{token, items});
  if(res.ok){
    await loadUI();
    // UI herladen zodat posities consistent blijven
    openTab(currentTabId);
  }
}

async function deleteWidget(widgetId){
  if(role!=="admin") return;
  if(!editMode) return;

  await apiPost(`/api/admin/widget/delete?token=${encodeURIComponent(token)}&widget_id=${widgetId}`, {});
  await loadUI();
  openTab(currentTabId);
}

function showAddWidget(){
  toggleAdmin(true);
  // focus op widget sectie
  qs("w_msg").textContent = "Vul hieronder in en klik Toevoegen.";
}

function toggleAdmin(forceOpen=false){
  if(role!=="admin") return;

  const ap = qs("adminPanel");
  const open = forceOpen ? true : (ap.style.display==="none");
  ap.style.display = open ? "block" : "none";
  qs("grid").style.display = open ? "none" : "block";
}

async function adminAddWidget(){
  if(role!=="admin") return;

  const body = {
    token,
    tab_id: currentTabId,
    type: qs("w_type").value,
    title: qs("w_title").value,

    logo_resource: qs("w_logo_res").value || null,
    logo_index: qs("w_logo_idx").value || null,

    modbus_kind: qs("w_kind").value,
    address: qs("w_addr").value ? parseInt(qs("w_addr").value, 10) : null,

    scale: parseFloat(qs("w_scale").value || "1"),
    unit: qs("w_unit").value || null,
    min_value: qs("w_min").value ? parseFloat(qs("w_min").value) : null,
    max_value: qs("w_max").value ? parseFloat(qs("w_max").value) : null,
    default_value: null,
    x: 1, y: 1, w: 2, h: 1,
    writable: qs("w_writable").checked
  };

  // als logo mapping gekozen is, raw velden mogen leeg zijn
  if(body.logo_resource && body.logo_index){
    body.modbus_kind = null;
    body.address = null;
  }

  const res = await apiPost("/api/admin/widget", body);
  qs("w_msg").textContent = res.ok ? `Toegevoegd (addr ${res.data.address})` : (res.data?.detail || "Fout");

  if(res.ok){
    await loadUI();
    openTab(currentTabId);
    toggleAdmin(false);
  }
}

async function adminCreateUser(){
  const u=qs("au_user").value;
  const p=qs("au_pass").value;
  const r=qs("au_role").value;

  const res = await apiPost("/api/admin/user",{token, username:u, password:p, role:r});
  qs("au_msg").textContent = res.ok ? `OK user_id=${res.data.user_id} (moet wachtwoord wijzigen)` : (res.data?.detail || "Fout");
  if(res.ok) loadUsers();
}

async function loadUsers(){
  const res = await apiGet(`/api/admin/users?token=${encodeURIComponent(token)}`);
  if(!res.ok) return;

  const rows = res.data.users.map(u=>{
    return `
      <div style="border-top:1px solid #ddd; padding:6px 0;">
        <b>${u.username}</b> (id ${u.id}) - ${u.role}
        <br>logins: ${u.login_count} / last: ${u.last_login || "-"}
        <br>force_pw_change: ${u.force_pw_change} / disabled: ${u.is_disabled}
        <br>
        <button onclick="resetUserPw(${u.id})">Reset PW</button>
        <button onclick="toggleDisable(${u.id}, ${!u.is_disabled})">${u.is_disabled?"Enable":"Disable"}</button>
        <button onclick="forcePwChange(${u.id}, true)">Force PW change</button>
      </div>
    `;
  }).join("");

  qs("usersTable").innerHTML = rows || "(geen users)";
}

async function resetUserPw(userId){
  const temp = prompt("Nieuw tijdelijk wachtwoord:");
  if(!temp) return;
  await apiPost("/api/admin/user/reset_password",{token, user_id:userId, temp_password:temp, force_change:true});
  loadUsers();
}

async function toggleDisable(userId, disabled){
  await apiPost("/api/admin/user/disable",{token, user_id:userId, disabled});
  loadUsers();
}

async function forcePwChange(userId, force_change){
  await apiPost("/api/admin/user/force_pw_change",{token, user_id:userId, force_change});
  loadUsers();
}

async function adminAddTab(){
  const name=qs("at_name").value;
  const sort=parseInt(qs("at_sort").value||"10",10);
  const res = await apiPost("/api/admin/tab",{token, name, sort_order:sort});
  qs("at_msg").textContent = res.ok ? "Tab toegevoegd" : (res.data?.detail || "Fout");
  if(res.ok){
    await loadUI();
    renderTabs();
  }
}

async function adminSetAcl(){
  const tab_id=parseInt(qs("acl_tab").value,10);
  const user_id=parseInt(qs("acl_user").value,10);
  const can_view=qs("acl_view").checked;
  const can_edit=qs("acl_edit").checked;

  const res = await apiPost("/api/admin/tab_acl",{token, tab_id, user_id, can_view, can_edit});
  qs("acl_msg").textContent = res.ok ? "ACL opgeslagen" : (res.data?.detail || "Fout");
}

const $=id=>document.getElementById(id);
let me=null;

async function api(url,options={}){const r=await fetch(url,options);const d=await r.json();if(!r.ok)throw Error(d.detail||"Something went wrong");return d}
function formData(form){return new FormData(form)}

async function loadMe(){
 try{const d=await api("/api/me");me=d.user}catch(e){}
 if(me){$("auth").classList.add("hidden");$("add").classList.remove("hidden");$("dashboard").classList.remove("hidden");$("logout").classList.remove("hidden");}
 else{$("auth").classList.remove("hidden");$("add").classList.add("hidden");$("dashboard").classList.add("hidden");$("logout").classList.add("hidden")}
 loadItems();
 if(me)loadDashboard();
}

$("register").onsubmit=async e=>{e.preventDefault();try{const d=await api("/api/register",{method:"POST",body:formData(e.target)});me=d.user;alert("Welcome to Borrow Box!");loadMe()}catch(x){alert(x.message)}};
$("login").onsubmit=async e=>{e.preventDefault();try{const d=await api("/api/login",{method:"POST",body:formData(e.target)});me=d.user;alert("Logged in successfully!");loadMe()}catch(x){alert(x.message)}};
$("logout").onclick=async()=>{await api("/api/logout",{method:"POST"});me=null;loadMe();location.hash="browse"};

$("addItem").onsubmit=async e=>{e.preventDefault();try{await api("/api/items",{method:"POST",body:formData(e.target)});e.target.reset();alert("Item listed successfully!");loadItems();loadDashboard()}catch(x){alert(x.message)}};

async function loadItems(){
 const search=$("search").value,cat=$("category").value;
 try{const d=await api(`/api/items?search=${encodeURIComponent(search)}&category=${encodeURIComponent(cat)}`);
 $("items").innerHTML=d.items.length?d.items.map(x=>`
 <article class="item"><span class="category">${x.category}</span><h3>${esc(x.title)}</h3>
 <p>${esc(x.description||"No description provided.")}</p>
 <div class="owner">Lent by <b>${esc(x.owner)}</b></div><br>
 <span class="status ${x.status==="borrowed"?"borrowed":""}">${x.status}</span>
 ${x.status==="available"&&me&&x.owner!==me.username?`<button class="btn" onclick="requestItem(${x.id})">Request to Borrow</button>`:""}
 ${!me?`<p class="muted">Login to request this item.</p>`:""}
 </article>`).join(""):"<p class='muted'>No items found. Be the first to lend something!</p>"
 }catch(e){$("items").innerHTML="<p>Could not load items.</p>"}
}
$("search").oninput=loadItems;$("category").onchange=loadItems;

async function requestItem(id){try{await api(`/api/items/${id}/request`,{method:"POST"});alert("Borrow request sent!");loadItems();loadDashboard()}catch(e){alert(e.message)}}

async function loadDashboard(){
 try{
 const a=await api("/api/my-items"),b=await api("/api/requests"),c=await api("/api/my-borrows");
 $("myItems").innerHTML=a.items.length?a.items.map(x=>`<div class="dashitem"><b>${esc(x.title)}</b><div class="muted">${x.status} • ${x.requests} pending request(s)</div></div>`).join(""):"<p class='muted'>You haven't listed items yet.</p>";
 $("requests").innerHTML=b.requests.length?b.requests.map(x=>`<div class="dashitem"><b>${esc(x.title)}</b><div>${esc(x.borrower)} • <b>${x.status}</b></div>${x.status==="pending"?`<button class="smallbtn approve" onclick="decision(${x.id},'approve')">Approve</button> <button class="smallbtn reject" onclick="decision(${x.id},'reject')">Reject</button>`:""}</div>`).join(""):"<p class='muted'>No requests yet.</p>";
 $("myBorrows").innerHTML=c.borrows.length?c.borrows.map(x=>`<div class="dashitem"><b>${esc(x.title)}</b><div class="muted">Owner: ${esc(x.owner)} • ${x.status}</div></div>`).join(""):"<p class='muted'>No borrow requests yet.</p>";
 }catch(e){}
}
async function decision(id,type){try{await api(`/api/requests/${id}/${type}`,{method:"POST"});loadDashboard();loadItems()}catch(e){alert(e.message)}}
function esc(s){const d=document.createElement("div");d.textContent=s;return d.innerHTML}
loadMe();

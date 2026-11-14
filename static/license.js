/* Licence page and reminders for the Windows app. Loaded after team.js. */
pages.licence='Licence';
iconPaths.licence='M12 2l8 3v6c0 5-3.4 9.3-8 11-4.6-1.7-8-6-8-11V5z M8.5 12l2.5 2.5 4.5-5';
let licenceDraft='';
const licencePageAllowed=pageAllowed;
pageAllowed=function(name){return name==='licence'||licencePageAllowed(name)};
const licenceTone=l=>!l.writable?'red':l.warn?'warn':'';
const licenceLabel=l=>({licensed:'Licensed',trial:'Trial',grace:'Grace period',expired:'Expired',unlicensed:'Trial ended'})[l.status]||l.status;
function licenceDays(l){
  if(l.status==='trial')return l.trial_days_left;
  if(l.status==='licensed')return l.days_left===null?'∞':l.days_left;
  if(l.status==='grace')return l.grace_days+l.days_left+1;
  return 0;
}
function licencePage(){
  const l=S.licence,owner=S.web_user.role==='owner',has=!!l.licence_id;
  const daysFoot=l.status==='trial'?`of ${l.trial_days} trial days`:l.status==='grace'?'days of grace left':l.status==='licensed'&&l.days_left===null?'Perpetual licence':'days remaining';
  return heading('LICENCE','One licence, this PC.',esc(l.message),`<span class="pill ${licenceTone(l)} licence-pill">${licenceLabel(l)}</span>`)
  +`<div class="stats">${stat('Status',licenceLabel(l),'◈',l.writable?'All functions available':'Read-only until licensed')}${stat('Days remaining',licenceDays(l),'◷',daysFoot)}${stat('Licensed to',esc(l.customer||'—'),'❏',has?esc(l.edition)+' edition':'No licence installed')}${stat('Expires',esc(l.expires||(has?'Never':'—')),'▣',has?'Licence '+esc(l.licence_id):'Trial ends automatically')}</div>`
  +(l.problem?`<div class="licence-bar red" role="alert"><span>${esc(l.problem)}</span></div>`:'')
  +`<div class="settings-layout"><div class="card"><div class="card-head"><h2>Installation ID</h2><button class="btn secondary small" onclick="copyInstallationId()">Copy</button></div><div class="card-content"><div class="licence-id" id="installation-id">${esc(l.installation_id)}</div><div class="help">Send this ID to your supplier. The licence file you receive works on this PC only and needs no internet.</div></div></div>`
  +`<div class="card"><div class="card-head"><h2>${has?'Replace or renew licence':'Install a licence'}</h2></div><div class="card-content">`
  +(owner?`<div class="field"><label for="licence-file">Licence file (.lic)</label><input id="licence-file" type="file" accept=".lic,.txt,text/plain" onchange="readLicenceFile(this)"></div><div class="field"><label for="licence-text">Or paste the licence text</label><textarea id="licence-text" rows="6" spellcheck="false" class="licence-text" oninput="licenceDraft=this.value" placeholder="-----BEGIN AL HADIYA LICENCE-----">${esc(licenceDraft)}</textarea></div><div class="licence-actions"><button class="btn gold" onclick="installLicence()">Install licence</button>${has?'<button class="btn danger" onclick="removeLicence()">Remove licence</button>':''}</div>`
    :'<div class="notice">Only the owner can install or remove a licence.</div>')
  +`</div></div></div><div class="help">Your records are never locked away. Without a valid licence the app becomes read-only: you can still view, print, export and back up everything.</div>`;
}
async function readLicenceFile(input){
  const file=input.files[0];if(!file)return;
  if(file.size>20000)return toast('That file is too large to be a licence.',true);
  licenceDraft=await file.text();$('#licence-text').value=licenceDraft;
}
async function installLicence(){
  const text=($('#licence-text')?.value||'').trim();
  if(!text)return toast('Choose the licence file or paste its text first.',true);
  try{const l=await api('licence_install',{text});licenceDraft='';await load();toast(l.message)}catch(e){toast(e.message,true)}
}
async function removeLicence(){
  if(!confirm('Remove the licence from this PC? The app returns to its trial or becomes read-only.'))return;
  try{await api('licence_remove');await load();toast('Licence removed.')}catch(e){toast(e.message,true)}
}
async function copyInstallationId(){
  const id=S.licence.installation_id;
  try{await navigator.clipboard.writeText(id);toast('Installation ID copied.')}
  catch{const r=document.createRange();r.selectNodeContents($('#installation-id'));const s=getSelection();s.removeAllRanges();s.addRange(r);toast('Press Ctrl+C to copy the selected ID.')}
}
const licenceRender=render;
render=function(){
  if(!S)return;
  const l=S.licence;
  if(!l){delete pages.licence;if(page==='licence')page='overview';return licenceRender()}
  if(page==='licence'){
    const keep=page;page='overview';licenceRender();page=keep;
    document.querySelectorAll('#nav button').forEach(b=>b.classList.toggle('active',(b.getAttribute('onclick')||'').includes("'licence'")));
    $('#page-label').textContent=pages.licence;$('#main').innerHTML=licencePage();
  }else{
    licenceRender();
    if(l.warn||!l.writable)$('#main').insertAdjacentHTML('afterbegin',`<div class="licence-bar ${licenceTone(l)}" role="status"><span><b>${licenceLabel(l)}.</b> ${esc(l.message)}</span><button class="btn secondary small" onclick="navTo('licence')">Manage licence</button></div>`);
  }
  let chip=$('#licence-chip');
  if(!chip){chip=document.createElement('button');chip.id='licence-chip';chip.onclick=()=>navTo('licence');$('.sidebar-bottom').insertBefore(chip,$('.sidebar-bottom .sync-button'))}
  chip.className='licence-chip '+licenceTone(l);
  chip.textContent=l.status==='licensed'?(l.days_left===null?'Licensed':`Licensed · ${l.days_left} days left`):l.status==='trial'?`Trial · ${l.trial_days_left} days left`:licenceLabel(l)+(l.writable?'':' · read-only');
};
if(S)render();

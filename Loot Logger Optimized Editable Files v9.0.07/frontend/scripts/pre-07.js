(()=>{
const VERSION='v8.3.70';
const normalizeText=value=>String(value??'').trim();
const normalizeName=value=>{
const raw=normalizeText(value);
try{return normalizeText(typeof Lb==='function'?Lb(raw):raw).toLowerCase()}catch{return raw.toLowerCase()}
};
const displayName=value=>{
const raw=normalizeText(value);
try{return normalizeText(typeof Lb==='function'?Lb(raw):raw)||raw}catch{return raw}
};
const normalizeItem=value=>normalizeText(value).toLowerCase().replace(/[’‘`]/g,"'").replace(/'/g,'').replace(/[^\p{L}\p{N}]+/gu,' ').trim();
const itemKey=row=>normalizeItem(row?.item)+'\x1f'+Math.max(0,Number(row?.enchantment||0));
const responsibilityKey=(player,row)=>normalizeName(player)+'\x1e'+itemKey(row);
const parseTime=value=>{const time=Date.parse(normalizeText(value));return Number.isFinite(time)?time:0};
const escapeHTML=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const formatNumber=value=>Math.max(0,Number(value||0)).toLocaleString();
const hashText=text=>{let hash=2166136261;for(const char of String(text||''))hash=Math.imul(hash^char.charCodeAt(0),16777619);return(hash>>>0).toString(16)+'-'+String(text||'').length};
const imageURL=row=>{
const direct=normalizeText(row?.image_url);
if(direct)return direct;
const id=normalizeText(row?.item_id);
if(!id||/^(?:CSV_|SIM_|TEST_|UNKNOWN_)/i.test(id))return'';
return'https://render.albiononline.com/v1/item/'+encodeURIComponent(id).replace(/%40/gi,'@')+'.png';
};
function addResponsibility(map,player,row,quantity,kind,fileName){
quantity=Math.max(0,Number(quantity||0));
if(!quantity)return;
const canonical=displayName(player),key=responsibilityKey(canonical,row);
let entry=map.get(key);
if(!entry){
entry={
player:canonical,
item:normalizeText(row?.item)||'Unknown item',
item_id:normalizeText(row?.item_id),
image_url:normalizeText(row?.image_url),
enchantment:Math.max(0,Number(row?.enchantment||0)),
expected:0,
withdrawn:0,
remaining:0,
temporary_files:new Set(),
};
map.set(key,entry);
}
if(!entry.item_id&&row?.item_id)entry.item_id=normalizeText(row.item_id);
if(!entry.image_url&&row?.image_url)entry.image_url=normalizeText(row.image_url);
entry.expected+=quantity;
if(kind==='withdrawn')entry.withdrawn+=quantity;
if(kind==='remaining')entry.remaining+=quantity;
if(fileName)entry.temporary_files.add(fileName);
}
function computeTemporaryResponsibilities(temporaryFiles){
const expected=new Map();
for(const file of temporaryFiles||[]){
const groups=new Map();
(file.rows||[]).forEach((row,index)=>{
const key=itemKey(row),list=groups.get(key)||[];
list.push({...row,__order:index});
groups.set(key,list);
});
for(const rows of groups.values()){
rows.sort((a,b)=>{
const left=parseTime(a.date),right=parseTime(b.date);
if(left&&right&&left!==right)return left-right;
if(left&&!right)return-1;
if(!left&&right)return 1;
return a.__order-b.__order;
});
const lots=[];
for(const row of rows){
const amount=Number(row.amount||0);
if(amount>0){
lots.push({player:displayName(row.player),quantity:amount,row});
continue;
}
if(amount>=0)continue;
let needed=Math.abs(amount);
while(needed>0&&lots.length){
const lot=lots[0],taken=Math.min(needed,lot.quantity);
lot.quantity-=taken;
needed-=taken;
if(lot.quantity<=0)lots.shift();
}
// The withdrawing player becomes responsible for the full quantity,
// including withdrawals from stock that predates the exported log.
addResponsibility(expected,row.player,row,Math.abs(amount),'withdrawn',file.name);
}
for(const lot of lots){
if(lot.quantity>0)addResponsibility(expected,lot.player,lot.row,lot.quantity,'remaining',file.name);
}
}
}
return expected;
}
function computeFinalAmounts(finalRows){
const actual=new Map();
for(const row of finalRows||[]){
const player=displayName(row.player),key=responsibilityKey(player,row);
let entry=actual.get(key);
if(!entry){
entry={
player,
item:normalizeText(row.item)||'Unknown item',
item_id:normalizeText(row.item_id),
image_url:normalizeText(row.image_url),
enchantment:Math.max(0,Number(row.enchantment||0)),
actual:0,
};
actual.set(key,entry);
}
if(!entry.item_id&&row.item_id)entry.item_id=normalizeText(row.item_id);
if(!entry.image_url&&row.image_url)entry.image_url=normalizeText(row.image_url);
entry.actual+=Number(row.amount||0);
}
for(const entry of actual.values())entry.actual=Math.max(0,entry.actual);
return actual;
}
function computeComparison(temporaryFiles,finalRows){
const expected=computeTemporaryResponsibilities(temporaryFiles),actual=computeFinalAmounts(finalRows),records=[];
for(const [key,left] of expected){
const right=actual.get(key),finalAmount=Math.max(0,Number(right?.actual||0)),expectedAmount=Math.max(0,Number(left.expected||0));
let status='missing';
if(finalAmount>expectedAmount)status='extra';
else if(finalAmount===expectedAmount&&expectedAmount>0)status='matched';
else if(finalAmount>0)status='partial';
records.push({...left,temporary_files:[...left.temporary_files],actual:finalAmount,missing:Math.max(0,expectedAmount-finalAmount),extra:Math.max(0,finalAmount-expectedAmount),status});
actual.delete(key);
}
for(const right of actual.values()){
if(right.actual<=0)continue;
records.push({...right,expected:0,withdrawn:0,remaining:0,temporary_files:[],missing:0,extra:right.actual,status:'different'});
}
records.sort((a,b)=>a.player.localeCompare(b.player)||a.status.localeCompare(b.status)||a.item.localeCompare(b.item));
return records;
}
window.AlbionBankLogsCompareCore={computeComparison,computeTemporaryResponsibilities,computeFinalAmounts};
const tabs=document.querySelector('.tabs');
const bankTab=document.querySelector('[data-tab="bank"]');
if(!tabs||!bankTab||document.querySelector('[data-tab="banklogs"]'))return;
bankTab.insertAdjacentHTML('afterend','<button class="tab-button" data-tab="banklogs"><span class="tab-icon">⇆</span><span class="tab-copy"><strong>Bank logs compare</strong><small>Temporary banks to final bank</small></span></button>');
const panel=document.createElement('section');
panel.id='bankLogsPanel';
panel.className='tab-panel';
panel.innerHTML=`
<div class="options-header blc-header"><div><h2>Bank logs compare <span class="version-pill">${VERSION}</span></h2><p>Track who withdrew loot from temporary chests, keep responsibility for items still left there, and verify everything against one final-bank log.</p></div></div>
<div class="blc-import-grid">
<section class="blc-import-card" id="blcTemporaryDrop">
<div><h3>Temporary banks</h3><p>Add every temporary chest log. Exact duplicate files are ignored.</p></div>
<div class="blc-actions">
<label class="file-picker">Choose temporary logs<input id="blcTemporaryFiles" type="file" multiple accept=".txt,.csv,.tsv,text/plain,text/csv,text/tab-separated-values"></label>
<button class="btn" id="blcPasteTemporary" type="button">Paste temporary log</button>
<button class="btn danger" id="blcClearTemporary" type="button">Clear temporary</button>
</div>
<div class="blc-file-list" id="blcTemporaryList">No temporary bank logs loaded.</div>
</section>
<section class="blc-import-card" id="blcFinalDrop">
<div><h3>Final bank</h3><p>Load the destination bank log used to verify each responsible player.</p></div>
<div class="blc-actions">
<label class="file-picker">Choose final log<input id="blcFinalFile" type="file" accept=".txt,.csv,.tsv,text/plain,text/csv,text/tab-separated-values"></label>
<button class="btn" id="blcPasteFinal" type="button">Paste final log</button>
<button class="btn danger" id="blcClearFinal" type="button">Clear final</button>
</div>
<div class="blc-file-list" id="blcFinalName">No final bank log loaded.</div>
</section>
</div>
<div class="stats blc-stats">
<div class="stat"><div class="label">Temporary files</div><div class="value" id="blcTempCount">0</div><div class="sub" id="blcTempRows">0 transactions</div></div>
<div class="stat"><div class="label">Final bank</div><div class="value" id="blcFinalStatus">None</div><div class="sub" id="blcFinalRows">0 transactions</div></div>
<div class="stat"><div class="label">Fully matched</div><div class="value" id="blcMatched">0</div><div class="sub">Expected quantity is in final</div></div>
<div class="stat"><div class="label">Missing or partial</div><div class="value" id="blcMissing">0</div><div class="sub">Needs review</div></div>
</div>
<div class="bank-toolbar blc-toolbar">
<input class="search" id="blcSearch" placeholder="Search responsible player, item or temporary file…">
<select id="blcStatus"><option value="all">All statuses</option><option value="missing">Missing</option><option value="partial">Partial</option><option value="matched">Matched</option><option value="extra">Extra</option><option value="different">Final-only</option></select>
<button class="btn" id="blcExpandCollapse" type="button" title="Collapse all players">Collapse all</button>
<button class="btn" id="blcCopyMissing" type="button">Copy missing</button>
<button class="btn danger" id="blcClearAll" type="button">Clear comparison</button>
</div>
<div class="bank-legend blc-legend"><span><i class="legend-dot matched"></i>Matched</span><span><i class="legend-dot partial"></i>Partial</span><span><i class="legend-dot missing"></i>Missing</span><span><i class="legend-dot extra"></i>Extra</span><span><i class="legend-dot different"></i>Final-only</span></div>
<main id="blcResults" class="players blc-results"><div class="empty"><div class="big">⇆</div><h3>Load temporary and final bank logs</h3><p>The comparison stays temporary and is cleared when the application closes.</p></div></main>`;
document.querySelector('.app').appendChild(panel);
const style=document.createElement('style');
style.id='bankLogsCompareV638Styles';
style.textContent=`
.blc-header p{max-width:920px;color:var(--muted);font-size:12px;line-height:1.5}.blc-import-grid{display:grid;grid-template-columns:1fr 1fr;gap:13px;margin-bottom:14px}.blc-import-card{min-width:0;padding:16px;border:1px solid var(--line);border-radius:15px;background:linear-gradient(145deg,#191e25,#12161b);box-shadow:var(--shadow)}.blc-import-card h3{margin:0 0 5px}.blc-import-card p{margin:0;color:var(--muted);font-size:11px;line-height:1.45}.blc-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:13px}.blc-file-list{margin-top:12px;min-height:39px;padding:9px 10px;border:1px dashed #38424e;border-radius:10px;background:#0e1217;color:#8e99a6;font-size:10px}.blc-file-row{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:5px 0;border-bottom:1px solid #252d36}.blc-file-row:last-child{border-bottom:0}.blc-file-row button{height:25px;padding:0 8px}.blc-toolbar{display:grid;grid-template-columns:minmax(260px,1fr) 170px auto auto auto;gap:8px}.blc-legend{margin:10px 0 13px}.blc-player{border:1px solid var(--line);border-radius:15px;background:linear-gradient(145deg,#181d24,#11151a);box-shadow:var(--shadow);overflow:hidden}.blc-player+ .blc-player{margin-top:11px}.blc-player summary{cursor:pointer;list-style:none;display:flex;align-items:center;justify-content:space-between;gap:14px;padding:14px 16px}.blc-player summary::-webkit-details-marker{display:none}.blc-player-name{font-size:16px;font-weight:780}.blc-player-meta{margin-top:3px;color:var(--muted);font-size:10px}.blc-items{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px;padding:0 13px 13px}.blc-item{position:relative;min-width:0;padding:12px;border:1px solid #303946;border-radius:12px;background:#10151b}.blc-item.matched{border-color:#3f7655}.blc-item.partial{border-color:#b69038}.blc-item.missing{border-color:#9c4149}.blc-item.extra,.blc-item.different{border-color:#536b94}.blc-item-head{display:flex;align-items:center;gap:10px}.blc-icon{width:43px;height:43px;flex:0 0 43px;display:grid;place-items:center;border-radius:10px;background:#0a0d11}.blc-icon img{width:40px;height:40px;object-fit:contain}.blc-item-name{font-size:12px;font-weight:750;line-height:1.25}.blc-item-id{margin-top:4px;color:#8793a1;font-size:9px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.blc-state{display:inline-flex;margin-top:9px;padding:4px 7px;border-radius:999px;background:#ffffff09;font-size:8px;font-weight:800;text-transform:uppercase}.blc-state.matched{color:var(--green)}.blc-state.partial{color:#f2ce72}.blc-state.missing{color:#ff8e96}.blc-state.extra,.blc-state.different{color:#8ab4ff}.blc-amounts{margin-top:8px;font-size:11px}.blc-breakdown{margin-top:5px;color:var(--muted);font-size:9px;line-height:1.45}.blc-files{margin-top:6px;color:#75818e;font-size:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}@media(max-width:1000px){.blc-import-grid{grid-template-columns:1fr}.blc-toolbar{grid-template-columns:1fr 1fr}.blc-stats{grid-template-columns:1fr 1fr}}html[data-theme="light"] .blc-import-card,html[data-theme="light"] .blc-player,html[data-theme="light"] .blc-item{background:#f8fafc;border-color:#d5dde8}html[data-theme="light"] .blc-file-list{background:#fff;border-color:#cbd5e1;color:#667085}`;
document.head.appendChild(style);
let temporaryFiles=[],finalFile=null,search='',statusFilter='all',playersExpanded=true;
const itemMetadataCache=new Map();
const $=selector=>panel.querySelector(selector);
const notify=(message,error=false)=>{try{if(typeof A==='function')A(message,error)}catch{}};
const metadataKey=row=>normalizeItem(row?.item)+'\x1f'+Math.max(0,Number(row?.enchantment||0));
function rememberMetadata(row,metadata){
const id=normalizeText(metadata?.id||metadata?.item_id),image=normalizeText(metadata?.image_url);
if(!id&&!image)return;
itemMetadataCache.set(metadataKey(row),{id,image_url:image});
}
function sessionItemMetadata(){
for(const player of j?.players||[])for(const item of player.items||[]){
const enchantment=typeof xa==='function'?xa(item):Math.max(0,Number(item.enchantment??item.bank_enchantment??0));
rememberMetadata({item:item.item_name,enchantment},{id:item.item_id,image_url:item.image_url});
}
}
async function resolveItemMetadata(rows){
sessionItemMetadata();
const unresolved=new Map();
for(const row of rows||[]){
if(row.item_id||row.image_url){rememberMetadata(row,{id:row.item_id,image_url:row.image_url});continue}
const cached=itemMetadataCache.get(metadataKey(row));
if(cached){row.item_id=cached.id||'';row.image_url=cached.image_url||'';continue}
unresolved.set(metadataKey(row),{name:row.item,enchantment:Math.max(0,Number(row.enchantment||0))});
}
if(unresolved.size){
try{
const response=await fetch('/api/catalog/resolve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items:[...unresolved.values()]})});
if(response.ok){
const payload=await response.json();
for(const resolved of payload.items||[])if(resolved?.found)rememberMetadata({item:resolved.name,enchantment:resolved.enchantment},resolved.item);
}
}catch{}
}
for(const row of rows||[]){
const cached=itemMetadataCache.get(metadataKey(row));
if(cached){row.item_id=row.item_id||cached.id||'';row.image_url=row.image_url||cached.image_url||''}
}
return rows;
}
async function parseFile(file){
const text=await file.text(),parsed=Pa(text,file.name),rows=parsed.sourceRows||[];
await resolveItemMetadata(rows);
return{name:file.name,hash:hashText(text),rows,text};
}
async function addTemporary(files){
let added=0;
for(const file of files||[]){
const parsed=await parseFile(file);
if(temporaryFiles.some(current=>current.hash===parsed.hash))continue;
temporaryFiles.push(parsed);added++;
}
if(!added&&files?.length)notify('These temporary bank logs are already loaded',true);
render();
}
async function setFinal(file){finalFile=await parseFile(file);render();}
async function clipboardFile(name){
const text=await navigator.clipboard.readText();
if(!normalizeText(text))throw Error('Clipboard is empty');
return new File([text],name,{type:'text/plain'});
}
function counts(records){
const result={matched:0,partial:0,missing:0,extra:0,different:0};
for(const record of records)result[record.status]=(result[record.status]||0)+1;
return result;
}
function grouped(records){
const players=new Map();
for(const record of records){const key=record.player.toLowerCase(),list=players.get(key)||{name:record.player,items:[]};list.items.push(record);players.set(key,list)}
return[...players.values()].sort((a,b)=>a.name.localeCompare(b.name));
}
function renderFiles(){
$('#blcTemporaryList').innerHTML=temporaryFiles.length?temporaryFiles.map(file=>`<div class="blc-file-row"><span><b>${escapeHTML(file.name)}</b> · ${formatNumber(file.rows.length)} transactions</span><button class="btn small danger" data-blc-remove="${escapeHTML(file.hash)}" type="button">Remove</button></div>`).join(''):'No temporary bank logs loaded.';
$('#blcFinalName').innerHTML=finalFile?`<b>${escapeHTML(finalFile.name)}</b> · ${formatNumber(finalFile.rows.length)} transactions`:'No final bank log loaded.';
panel.querySelectorAll('[data-blc-remove]').forEach(button=>button.onclick=()=>{temporaryFiles=temporaryFiles.filter(file=>file.hash!==button.dataset.blcRemove);render()});
}
function render(){
renderFiles();
const all=computeComparison(temporaryFiles,finalFile?.rows||[]),summary=counts(all),query=search.trim().toLowerCase();
let visible=all.filter(record=>statusFilter==='all'||record.status===statusFilter);
if(query)visible=visible.filter(record=>[record.player,record.item,record.item_id,...(record.temporary_files||[])].join(' ').toLowerCase().includes(query));
$('#blcTempCount').textContent=formatNumber(temporaryFiles.length);
$('#blcTempRows').textContent=`${formatNumber(temporaryFiles.reduce((sum,file)=>sum+file.rows.length,0))} transactions`;
$('#blcFinalStatus').textContent=finalFile?'Loaded':'None';
$('#blcFinalRows').textContent=`${formatNumber(finalFile?.rows?.length||0)} transactions`;
$('#blcMatched').textContent=formatNumber(summary.matched);
$('#blcMissing').textContent=formatNumber(summary.missing+summary.partial);
const expandButton=$('#blcExpandCollapse');
if(expandButton){expandButton.textContent=playersExpanded?'Collapse all':'Expand all';expandButton.title=playersExpanded?'Collapse all players':'Expand all players'}
const result=$('#blcResults');
if(!temporaryFiles.length&&!finalFile){result.innerHTML='<div class="empty"><div class="big">⇆</div><h3>Load temporary and final bank logs</h3><p>The comparison stays temporary and is cleared when the application closes.</p></div>';return}
if(!visible.length){result.innerHTML='<div class="empty"><div class="big">⌕</div><h3>No matching comparison entries</h3><p>Change the search or status filter.</p></div>';return}
result.innerHTML=grouped(visible).map(player=>{
const expected=player.items.reduce((sum,item)=>sum+item.expected,0),actual=player.items.reduce((sum,item)=>sum+item.actual,0),missing=player.items.reduce((sum,item)=>sum+item.missing,0);
return`<details class="blc-player"${playersExpanded?' open':''}><summary><div><div class="blc-player-name">${escapeHTML(player.name)}</div><div class="blc-player-meta">Temporary responsibility ${formatNumber(expected)} · Final ${formatNumber(actual)}${missing?` · Missing ${formatNumber(missing)}`:''}</div></div><span>⌄</span></summary><div class="blc-items">${player.items.map(item=>{
const img=imageURL(item),label=item.status==='different'?'Final-only deposit':item.status;
return`<article class="blc-item ${escapeHTML(item.status)}"><div class="blc-item-head"><div class="blc-icon">${img?`<img loading="lazy" src="${escapeHTML(img)}" alt="" onerror="this.replaceWith(document.createTextNode('◇'))">`:'◇'}</div><div style="min-width:0"><div class="blc-item-name">${escapeHTML(item.item)}${item.enchantment?` .${formatNumber(item.enchantment)}`:''}</div><div class="blc-item-id" title="${escapeHTML(item.item_id||'Item ID could not be resolved')}">ID: ${escapeHTML(item.item_id||'Unresolved')}</div></div></div><span class="blc-state ${escapeHTML(item.status)}">${escapeHTML(label)}</span><div class="blc-amounts">Temporary ${formatNumber(item.expected)} / Final ${formatNumber(item.actual)}${item.missing?` / Missing ${formatNumber(item.missing)}`:''}${item.extra?` / Extra ${formatNumber(item.extra)}`:''}</div><div class="blc-breakdown">Took out ${formatNumber(item.withdrawn)} · Still attributed in temporary ${formatNumber(item.remaining)}</div>${item.temporary_files?.length?`<div class="blc-files" title="${escapeHTML(item.temporary_files.join(' · '))}">${escapeHTML(item.temporary_files.join(' · '))}</div>`:''}</article>`
}).join('')}</div></details>`
}).join('');
}
async function withError(task){try{await task()}catch(error){notify(error?.message||String(error),true)}}
$('#blcTemporaryFiles').onchange=event=>withError(async()=>{await addTemporary([...event.target.files]);event.target.value=''});
$('#blcFinalFile').onchange=event=>withError(async()=>{const file=event.target.files?.[0];if(file)await setFinal(file);event.target.value=''});
$('#blcPasteTemporary').onclick=()=>withError(async()=>addTemporary([await clipboardFile('temporary-bank-clipboard.txt')]));
$('#blcPasteFinal').onclick=()=>withError(async()=>setFinal(await clipboardFile('final-bank-clipboard.txt')));
$('#blcClearTemporary').onclick=()=>{temporaryFiles=[];render();notify('Temporary bank logs cleared')};
$('#blcClearFinal').onclick=()=>{finalFile=null;render();notify('Final bank log cleared')};
$('#blcClearAll').onclick=()=>{temporaryFiles=[];finalFile=null;search='';statusFilter='all';$('#blcSearch').value='';$('#blcStatus').value='all';render();notify('Bank logs comparison cleared')};
$('#blcSearch').oninput=event=>{search=event.target.value;render()};
$('#blcStatus').onchange=event=>{statusFilter=event.target.value;render()};
$('#blcExpandCollapse').onclick=()=>{
playersExpanded=!playersExpanded;
panel.querySelectorAll('.blc-player').forEach(details=>details.open=playersExpanded);
const button=$('#blcExpandCollapse');
button.textContent=playersExpanded?'Collapse all':'Expand all';
button.title=playersExpanded?'Collapse all players':'Expand all players';
};
$('#blcCopyMissing').onclick=()=>withError(async()=>{
const records=computeComparison(temporaryFiles,finalFile?.rows||[]).filter(record=>record.status==='missing'||record.status==='partial');
if(!records.length){notify('There are no missing or partial entries');return}
const lines=['**Bank Logs Compare — Missing from final bank**'];
let current='';
for(const record of records){if(record.player!==current){current=record.player;lines.push(`\n**${record.player}**`)}lines.push(`• ${record.item}${record.enchantment?`.${record.enchantment}`:''}: temporary ${record.expected} · final ${record.actual} · missing ${record.missing}`)}
const text=lines.join('\n');
if(typeof Ob==='function')await Ob(text);else await navigator.clipboard.writeText(text);
notify('Missing bank-log entries copied');
});
for(const [selector,handler] of [['#blcTemporaryDrop',files=>addTemporary(files)],['#blcFinalDrop',files=>files?.[0]&&setFinal(files[0])]]){
const drop=$(selector);
drop.addEventListener('dragover',event=>{event.preventDefault();drop.classList.add('dragover')});
drop.addEventListener('dragleave',()=>drop.classList.remove('dragover'));
drop.addEventListener('drop',event=>{event.preventDefault();drop.classList.remove('dragover');withError(()=>handler([...event.dataTransfer.files]))});
}
const oldBa=ba;
ba=function(tab){
if(tab!=='banklogs'){panel.classList.remove('active');return oldBa(tab)}
document.querySelectorAll('[data-tab]').forEach(button=>button.classList.toggle('active',button.dataset.tab==='banklogs'));
document.querySelectorAll('.tab-panel').forEach(candidate=>candidate.classList.toggle('active',candidate===panel));
localStorage.setItem('albion-loot-tab','banklogs');
render();
};
document.querySelector('[data-tab="banklogs"]').onclick=()=>ba('banklogs');
document.addEventListener('keydown',event=>{
if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='f'&&panel.classList.contains('active')){event.preventDefault();$('#blcSearch').focus();$('#blcSearch').select()}
if(event.key==='/'&&panel.classList.contains('active')&&!['INPUT','SELECT','TEXTAREA'].includes(document.activeElement?.tagName)){event.preventDefault();$('#blcSearch').focus()}
});
render();
if(localStorage.getItem('albion-loot-tab')==='banklogs')setTimeout(()=>ba('banklogs'),0);
})();
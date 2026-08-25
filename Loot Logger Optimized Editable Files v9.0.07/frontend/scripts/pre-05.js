(()=>{
const toggle=document.getElementById('optDarkMode');
if(toggle){
toggle.checked=document.documentElement.dataset.theme!=='light';
toggle.addEventListener('change',()=>window.applyAlbionTheme?.(toggle.checked));
}
const titleMap={
saveSettings:'Save all option changes now',resetSettings:'Restore the default options',
refreshBankGuilds:'Verify tracked character names and load guild members',
liveToggle:'Pause or resume visual updates without stopping capture',
expandCollapse:'Expand or collapse all player cards',export:'Export the current loot overview',
refreshCatalog:'Refresh item names and categories',clear:'Clear the current session after confirmation',
bankUpload:'Import the selected bank export',copyMissing:'Copy unresolved Bank Compare entries'
};
for(const [id,title] of Object.entries(titleMap)){const el=document.getElementById(id);if(el&&!el.title)el.title=title;}
for(const button of document.querySelectorAll('button')){
if(!button.getAttribute('aria-label')){const text=button.textContent.trim().replace(/\s+/g,' ');if(text)button.setAttribute('aria-label',text);}
}
})();
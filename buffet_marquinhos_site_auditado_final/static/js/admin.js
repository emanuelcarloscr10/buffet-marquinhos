const adminMenuButton=document.querySelector('.admin-menu-toggle');
const adminNav=document.querySelector('.admin-nav');

function setAdminMenu(open){
  if(!adminMenuButton||!adminNav)return;
  const shouldOpen=Boolean(open)&&window.innerWidth<=820;
  adminNav.classList.toggle('open',shouldOpen);
  adminMenuButton.setAttribute('aria-expanded',String(shouldOpen));
  adminMenuButton.setAttribute('aria-label',shouldOpen?'Fechar menu':'Abrir menu');
}

adminMenuButton?.addEventListener('click',event=>{
  event.preventDefault();
  event.stopPropagation();
  setAdminMenu(!adminNav?.classList.contains('open'));
});

document.querySelectorAll('.admin-nav a').forEach(link=>{
  link.addEventListener('click',()=>setAdminMenu(false));
});

document.addEventListener('click',event=>{
  if(!adminNav?.classList.contains('open'))return;
  if(!adminNav.contains(event.target)&&!adminMenuButton?.contains(event.target))setAdminMenu(false);
});

document.addEventListener('keydown',event=>{
  if(event.key==='Escape')setAdminMenu(false);
});

window.addEventListener('resize',()=>{
  if(window.innerWidth>820)setAdminMenu(false);
},{passive:true});

// Evita envios duplicados por duplo clique/toque no painel. Isso é especialmente
// importante em cadastros de agenda, onde um segundo POST poderia criar um evento
// repetido antes da primeira navegação terminar.
document.querySelectorAll('form[method="post"], form[method="POST"]').forEach(form=>{
  form.addEventListener('submit',event=>{
    if(event.defaultPrevented)return;
    const submitter=event.submitter;
    if(!submitter)return;
    // O evento submit só dispara depois que a validação HTML passa. Desabilitar
    // imediatamente evita que um segundo toque envie outro POST antes da navegação.
    submitter.disabled=true;
    submitter.setAttribute('aria-busy','true');
    if(!submitter.dataset.originalLabel)submitter.dataset.originalLabel=submitter.textContent||'';
    if(!submitter.classList.contains('text-danger')&&!submitter.classList.contains('danger-button')){
      submitter.textContent='Salvando...';
    }
  });
});

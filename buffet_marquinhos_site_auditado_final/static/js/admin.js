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

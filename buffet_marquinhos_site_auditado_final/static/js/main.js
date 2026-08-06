const header=document.querySelector('.header');
const toggle=document.querySelector('.menu-toggle');
const links=document.querySelector('.nav-links');
const mobileBreakpoint=980;

function updateHeaderState(){
  header?.classList.toggle('scrolled',window.scrollY>40);
}
window.addEventListener('scroll',updateHeaderState,{passive:true});
updateHeaderState();

function isMobileMenu(){
  return window.innerWidth<=mobileBreakpoint;
}

function setMenu(open){
  if(!toggle||!links)return;
  const shouldOpen=Boolean(open)&&isMobileMenu();
  links.classList.toggle('open',shouldOpen);
  toggle.classList.toggle('active',shouldOpen);
  toggle.setAttribute('aria-expanded',String(shouldOpen));
  toggle.setAttribute('aria-label',shouldOpen?'Fechar menu':'Abrir menu');
  document.body.classList.toggle('mobile-menu-open',shouldOpen);
}

toggle?.addEventListener('click',event=>{
  event.preventDefault();
  event.stopPropagation();
  setMenu(!links?.classList.contains('open'));
});

function scrollToSection(target){
  if(!target)return;

  const alignTarget=behavior=>{
    const headerHeight=header?.getBoundingClientRect().height||0;
    const top=target.getBoundingClientRect().top+window.scrollY-headerHeight-10;
    window.scrollTo({top:Math.max(0,top),behavior});
  };

  alignTarget('smooth');

  // Uma segunda correção compensa mudanças de altura causadas por imagens,
  // fontes ou pelo fechamento do menu no Safari e em outros navegadores móveis.
  window.setTimeout(()=>{
    const headerHeight=header?.getBoundingClientRect().height||0;
    const correction=target.getBoundingClientRect().top-headerHeight-10;
    if(Math.abs(correction)>4){
      window.scrollBy({top:correction,behavior:'auto'});
    }
  },350);
}

document.querySelectorAll('a[href^="#"]').forEach(anchor=>{
  anchor.addEventListener('click',event=>{
    const hash=anchor.getAttribute('href');
    if(!hash||hash==='#')return;
    let target;
    try{target=document.querySelector(hash)}catch(_error){return;}
    if(!target)return;

    event.preventDefault();
    setMenu(false);

    // No Safari do iPhone, esperar o menu fixo fechar evita que o toque
    // seja perdido antes do deslocamento até a seção.
    window.setTimeout(()=>{
      scrollToSection(target);
      try{
        if(history.pushState)history.pushState(null,'',hash);
        else location.hash=hash;
      }catch(_error){
        location.hash=hash;
      }
    },isMobileMenu()?80:0);
  });
});

document.addEventListener('click',event=>{
  if(!isMobileMenu()||!links?.classList.contains('open'))return;
  if(!links.contains(event.target)&&!toggle?.contains(event.target))setMenu(false);
});

document.addEventListener('keydown',event=>{
  if(event.key==='Escape')setMenu(false);
});

window.addEventListener('resize',()=>{
  if(!isMobileMenu())setMenu(false);
},{passive:true});

window.addEventListener('pageshow',()=>{
  setMenu(false);
  if(budgetSubmit){
    budgetSubmit.disabled=false;
    budgetSubmit.textContent='Enviar pelo WhatsApp';
  }
});

document.querySelectorAll('.filter').forEach(btn=>btn.addEventListener('click',()=>{
  document.querySelectorAll('.filter').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active'); const f=btn.dataset.filter;
  document.querySelectorAll('.gallery-item').forEach(item=>item.classList.toggle('hidden',f!=='all'&&item.dataset.category!==f));
}));

const modal=document.querySelector('.modal'),modalImg=modal?.querySelector('img');
document.querySelectorAll('.gallery-item img, .team-member-photo img, .open-menu').forEach(el=>el.addEventListener('click',e=>{
  e.preventDefault(); modalImg.src=el.dataset.full||el.src; modal.classList.add('open'); document.body.style.overflow='hidden';
}));
function closeModal(){modal?.classList.remove('open');document.body.style.overflow=''}
document.querySelector('.modal-close')?.addEventListener('click',closeModal);
modal?.addEventListener('click',e=>{if(e.target===modal)closeModal()});
addEventListener('keydown',e=>{if(e.key==='Escape')closeModal()});

const today=new Date();
const todayIso=[today.getFullYear(),String(today.getMonth()+1).padStart(2,'0'),String(today.getDate()).padStart(2,'0')].join('-');
document.querySelectorAll('input[type="date"]').forEach(input=>{if(!input.closest('.admin-body')) input.min=todayIso});

async function getAvailability(dateValue){
  const response=await fetch(`/api/disponibilidade?data=${encodeURIComponent(dateValue)}`,{headers:{Accept:'application/json'}});
  if(!response.ok) throw new Error('Não foi possível consultar a agenda.');
  return response.json();
}

function paintAvailability(element,data){
  if(!element)return;
  element.className=`availability-result ${data.status}`;
  let detail='Consulte antes de solicitar seu orçamento.';
  if(data.status==='disponivel'){
    detail=`Ainda há ${data.remaining} vagas nesta data.`;
  }else if(data.status==='ultima_vaga'){
    detail='Entre em contato para reservar a última vaga disponível.';
  }else if(data.status==='lotada'){
    detail='A data está preenchida no momento, mas entre em contato conosco. Dependendo das características e do horário do evento, poderemos avaliar uma alternativa ou possibilidade excepcional de atendimento.';
  }else if(data.status==='indisponivel'){
    detail='Entre em contato conosco para verificarmos outras possibilidades de atendimento.';
  }
  element.innerHTML=`<strong>${data.message}</strong><span>${detail}</span>`;
}

const availabilityDate=document.querySelector('#availability-date');
const availabilityResult=document.querySelector('#availability-result');
async function checkPublicAvailability(){
  if(!availabilityDate?.value){paintAvailability(availabilityResult,{status:'idle',message:'Escolha uma data',remaining:0});return;}
  availabilityResult.className='availability-result loading';
  availabilityResult.innerHTML='<strong>Consultando...</strong><span>Aguarde um instante.</span>';
  try{paintAvailability(availabilityResult,await getAvailability(availabilityDate.value));}
  catch(error){paintAvailability(availabilityResult,{status:'error',message:error.message,remaining:0});}
}
document.querySelector('#check-availability')?.addEventListener('click',checkPublicAvailability);
availabilityDate?.addEventListener('change',checkPublicAvailability);

const budgetDate=document.querySelector('#budget-date');
const budgetStatus=document.querySelector('#budget-date-status');
const budgetSubmit=document.querySelector('#budget-submit');
let selectedAvailability=null;
async function checkBudgetDate(){
  selectedAvailability=null;
  budgetSubmit.disabled=false;
  if(!budgetDate?.value){budgetStatus.textContent='A disponibilidade será consultada automaticamente.';return;}
  budgetStatus.className='field-help checking';budgetStatus.textContent='Consultando agenda...';
  try{
    selectedAvailability=await getAvailability(budgetDate.value);
    budgetStatus.className=`field-help ${selectedAvailability.status}`;
    if(selectedAvailability.status==='lotada'){
      budgetStatus.textContent='Agenda preenchida nesta data. Você ainda pode enviar a solicitação para avaliarmos uma possível alternativa de atendimento.';
    }else if(selectedAvailability.status==='indisponivel'){
      budgetStatus.textContent='Esta data aparece como indisponível, mas você pode entrar em contato para consultar outras possibilidades.';
    }else{
      budgetStatus.textContent=selectedAvailability.message;
    }
    budgetSubmit.disabled=false;
  }catch(error){budgetStatus.className='field-help error';budgetStatus.textContent='Não foi possível consultar agora. Fale conosco pelo WhatsApp.';}
}
budgetDate?.addEventListener('change',checkBudgetDate);

function normalizeCity(value){return value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase().replace(/\s+/g,' ')}
const cityInput=document.querySelector('#event-city');
const travelWarning=document.querySelector('#travel-warning');
const travelAware=document.querySelector('#travel-aware');
const baseCity=normalizeCity(document.querySelector('#orcamento-form')?.dataset.baseCity||'Praia Grande');
function checkTravel(){
  const city=normalizeCity(cityInput?.value||'');
  const outside=Boolean(city)&&city!==baseCity&&city!==`${baseCity} sc`&&city!==`${baseCity}/sc`;
  travelWarning?.classList.toggle('hidden',!outside);
  if(travelAware) travelAware.required=outside;
  return outside;
}
cityInput?.addEventListener('input',checkTravel);

const menuCheckboxes=[...document.querySelectorAll('input[name="cardapio"]')];
const menuSelectionSummary=document.querySelector('#menu-selection-summary');
const customMenuInput=document.querySelector('#custom-menu');

function selectedMenuByCategory(){
  const groups=new Map();
  menuCheckboxes.filter(input=>input.checked).forEach(input=>{
    const category=input.dataset.category||'Outras opções';
    if(!groups.has(category))groups.set(category,[]);
    groups.get(category).push(input.value);
  });
  return groups;
}

function updateMenuSummary(){
  const count=menuCheckboxes.filter(input=>input.checked).length;
  if(!menuSelectionSummary)return;
  menuSelectionSummary.textContent=count
    ? `${count} opção(ões) selecionada(s).`
    : 'Nenhuma opção marcada. Você pode enviar assim mesmo e pedir orientação.';
  menuSelectionSummary.className=`field-help ${count?'success':''}`;
}

menuCheckboxes.forEach(input=>input.addEventListener('change',updateMenuSummary));
document.querySelector('#select-menu-all')?.addEventListener('click',()=>{
  menuCheckboxes.forEach(input=>{input.checked=true});
  updateMenuSummary();
});
document.querySelector('#clear-menu-all')?.addEventListener('click',()=>{
  menuCheckboxes.forEach(input=>{input.checked=false});
  updateMenuSummary();
});
updateMenuSummary();

const form=document.querySelector('#orcamento-form');
form?.addEventListener('submit',async e=>{
 e.preventDefault();
 if(budgetDate?.value && !selectedAvailability) await checkBudgetDate();
 // Mesmo quando a agenda aparece como lotada ou indisponível, a solicitação
 // pode ser enviada para que a equipe avalie alternativas de atendimento.
 const outside=checkTravel();
 if(outside && !travelAware.checked){travelAware.reportValidity();return;}
 const d=new FormData(form);
 const number=String(form.dataset.whatsapp||'').replace(/\D/g,'');
 if(number.length<12){
   budgetStatus.className='field-help error';
   budgetStatus.textContent='O número do WhatsApp não está configurado corretamente. Entre em contato pelo botão verde da página.';
   return;
 }
 const travelText=outside?'Sim — ciente de possível acréscimo de deslocamento.':`Evento em ${form.dataset.baseCity} ou cidade ainda não confirmada.`;
 const selectedMenu=selectedMenuByCategory();
 const menuLines=[];
 selectedMenu.forEach((items,category)=>{
   menuLines.push(`*${category}:* ${items.join(', ')}`);
 });
 const customMenu=(customMenuInput?.value||'').trim();
 if(customMenu)menuLines.push(`*Pedidos personalizados:* ${customMenu}`);
 const menuText=menuLines.length?menuLines.join('\n'):'Ainda não defini o cardápio e gostaria de orientação.';
 const availabilityText=selectedAvailability
   ? (selectedAvailability.status==='lotada'
      ? 'A data aparece como lotada; solicito, se possível, uma avaliação de alternativa ou atendimento excepcional.'
      : selectedAvailability.status==='indisponivel'
        ? 'A data aparece como indisponível; gostaria de consultar outras possibilidades.'
        : selectedAvailability.message)
   : 'Disponibilidade ainda não consultada.';
 const lines=[
   `Olá! Gostaria de solicitar um orçamento do ${form.dataset.brand}.`,
   '',
   `*Situação da agenda:* ${availabilityText}`,
   `*Nome:* ${d.get('nome')}`,
   `*Data do evento:* ${d.get('data')||'A definir'}`,
   `*Cidade:* ${d.get('cidade')}`,
   `*Convidados:* ${d.get('convidados')}`,
   `*Tipo de evento:* ${d.get('evento')}`,
   `*Pacote:* ${d.get('pacote')}`,
   '',
   '*Cardápio solicitado:*',
   menuText,
   '',
   `*Deslocamento:* ${travelText}`,
   `*Observações:* ${d.get('mensagem')||'Nenhuma'}`
 ];
 const whatsappUrl=new URL('https://api.whatsapp.com/send');
 whatsappUrl.searchParams.set('phone',number);
 whatsappUrl.searchParams.set('text',lines.join('\n'));

 const fallback=document.querySelector('#whatsapp-fallback');
 if(fallback){
   fallback.href=whatsappUrl.toString();
   fallback.classList.remove('hidden');
 }

 budgetSubmit.disabled=true;
 budgetSubmit.textContent='Abrindo WhatsApp...';
 budgetStatus.className='field-help success';
 budgetStatus.textContent='Abrindo o WhatsApp com a mensagem do orçamento...';
 window.location.assign(whatsappUrl.toString());
});

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

document.querySelectorAll('.filter').forEach(btn=>btn.addEventListener('click',()=>{
  document.querySelectorAll('.filter').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  const f=btn.dataset.filter;
  document.querySelectorAll('.gallery-item').forEach(item=>item.classList.toggle('hidden',f!=='all'&&item.dataset.category!==f));
}));

const modal=document.querySelector('.modal');
const modalImg=modal?.querySelector('img');
document.querySelectorAll('.gallery-item img, .team-member-photo img, .open-menu').forEach(el=>el.addEventListener('click',e=>{
  e.preventDefault();
  if(!modal||!modalImg)return;
  modalImg.src=el.dataset.full||el.src;
  modal.classList.add('open');
  document.body.style.overflow='hidden';
}));
function closeModal(){modal?.classList.remove('open');document.body.style.overflow='';}
document.querySelector('.modal-close')?.addEventListener('click',closeModal);
modal?.addEventListener('click',e=>{if(e.target===modal)closeModal();});
addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});

const today=new Date();
const todayIso=[today.getFullYear(),String(today.getMonth()+1).padStart(2,'0'),String(today.getDate()).padStart(2,'0')].join('-');
document.querySelectorAll('input[type="date"]').forEach(input=>{if(!input.closest('.admin-body'))input.min=todayIso;});

async function getAvailability(dateValue){
  const response=await fetch(`/api/disponibilidade?data=${encodeURIComponent(dateValue)}`,{
    headers:{Accept:'application/json'},
    cache:'no-store',
  });
  if(!response.ok)throw new Error('Não foi possível consultar a agenda.');
  return response.json();
}

function paintAvailability(element,data){
  if(!element)return;
  element.className=`availability-result ${data.status}`;
  let detail='Consulte antes de solicitar seu orçamento.';
  if(data.status==='disponivel'){
    detail=`Ainda há ${data.remaining} vaga(s) nesta data.`;
  }else if(data.status==='ultima_vaga'){
    detail='Entre em contato para reservar a última vaga disponível.';
  }else if(data.status==='lotada'){
    detail='A data está preenchida no momento, mas entre em contato. Dependendo do horário e das características do evento, a equipe poderá avaliar uma alternativa.';
  }else if(data.status==='indisponivel'){
    detail='Entre em contato para verificarmos outras possibilidades de atendimento.';
  }
  element.innerHTML=`<strong>${data.message}</strong><span>${detail}</span>`;
}

const availabilityDate=document.querySelector('#availability-date');
const availabilityResult=document.querySelector('#availability-result');
let publicAvailabilityRequestId=0;
async function checkPublicAvailability(){
    const requestId=++publicAvailabilityRequestId;
    const requestedDate=availabilityDate?.value||'';
  if(!requestedDate){
    paintAvailability(availabilityResult,{status:'idle',message:'Escolha uma data',remaining:0});
    return;
  }
  availabilityResult.className='availability-result loading';
  availabilityResult.innerHTML='<strong>Consultando...</strong><span>Aguarde um instante.</span>';
  try{
    const result=await getAvailability(requestedDate);
    if(requestId!==publicAvailabilityRequestId||availabilityDate?.value!==requestedDate)return;
    paintAvailability(availabilityResult,result);
  }catch(error){
    if(requestId!==publicAvailabilityRequestId||availabilityDate?.value!==requestedDate)return;
    paintAvailability(availabilityResult,{status:'error',message:error.message,remaining:0});
  }
}
document.querySelector('#check-availability')?.addEventListener('click',checkPublicAvailability);
availabilityDate?.addEventListener('change',checkPublicAvailability);

const form=document.querySelector('#orcamento-form');
const budgetDate=document.querySelector('#budget-date');
const budgetStatus=document.querySelector('#budget-date-status');
const budgetSubmit=document.querySelector('#budget-submit');
const cityInput=document.querySelector('#event-city');
const travelWarning=document.querySelector('#travel-warning');
const travelAware=document.querySelector('#travel-aware');
const packageChoice=document.querySelector('#package-choice');
const packageSummary=document.querySelector('#package-summary');
const guestsInput=form?.querySelector('input[name="convidados"]');
const menuOptions=[...document.querySelectorAll('[data-menu-option="1"]')];
const menuChoiceGroups=[...document.querySelectorAll('.menu-choice-group')];
const packageAwareMenuGroups=[...document.querySelectorAll('[data-requires-feature]')];
const menuSelectionSummary=document.querySelector('#menu-selection-summary');
const customMenuInput=document.querySelector('#custom-menu');
let selectedAvailability=null;
let budgetAvailabilityRequestId=0;

window.addEventListener('pageshow',()=>{
  setMenu(false);
  if(budgetSubmit){
    budgetSubmit.disabled=false;
    budgetSubmit.textContent='Enviar pelo WhatsApp';
  }
});

async function checkBudgetDate(){
  const requestId=++budgetAvailabilityRequestId;
  const requestedDate=budgetDate?.value||'';
  selectedAvailability=null;
  if(!requestedDate){
    if(budgetStatus){
      budgetStatus.className='field-help';
      budgetStatus.textContent='A disponibilidade será consultada automaticamente.';
    }
    return;
  }
  if(budgetStatus){
    budgetStatus.className='field-help checking';
    budgetStatus.textContent='Consultando agenda...';
  }
  try{
    const result=await getAvailability(requestedDate);
    if(requestId!==budgetAvailabilityRequestId||budgetDate?.value!==requestedDate)return;
    selectedAvailability=result;
    if(!budgetStatus)return;
    budgetStatus.className=`field-help ${selectedAvailability.status}`;
    if(selectedAvailability.status==='lotada'){
      budgetStatus.textContent='Agenda preenchida nesta data. Você ainda pode enviar a solicitação para avaliarmos uma alternativa.';
    }else if(selectedAvailability.status==='indisponivel'){
      budgetStatus.textContent='Esta data aparece como indisponível, mas você pode consultar outras possibilidades.';
    }else{
      budgetStatus.textContent=selectedAvailability.message;
    }
  }catch(_error){
    if(requestId!==budgetAvailabilityRequestId||budgetDate?.value!==requestedDate)return;
    if(budgetStatus){
      budgetStatus.className='field-help error';
      budgetStatus.textContent='Não foi possível consultar agora. O pedido ainda pode ser enviado pelo WhatsApp.';
    }
  }
}
budgetDate?.addEventListener('change',checkBudgetDate);

function normalizeCity(value){
  return (value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim().toLowerCase().replace(/\s+/g,' ');
}
const baseCity=normalizeCity(form?.dataset.baseCity||'Praia Grande');
function checkTravel(){
  const city=normalizeCity(cityInput?.value||'');
  const outside=Boolean(city)&&city!==baseCity&&city!==`${baseCity} sc`&&city!==`${baseCity}/sc`;
  travelWarning?.classList.toggle('hidden',!outside);
  if(travelAware)travelAware.required=outside;
  return outside;
}
cityInput?.addEventListener('input',checkTravel);

function currentPackageFeatures(){
  const option=packageChoice?.selectedOptions?.[0];
  return {
    entry:option?.dataset.entry||'unknown',
    dessert:option?.dataset.dessert||'unknown',
  };
}

function updatePackageState(){
  const features=currentPackageFeatures();
  if(packageSummary){
    if(features.entry==='unknown'||features.dessert==='unknown'){
      packageSummary.textContent='A equipe pode ajudar você a escolher o pacote ideal.';
    }else{
      const entry=features.entry==='1'?'com entrada':'sem entrada';
      const dessert=features.dessert==='1'?'com sobremesa':'sem sobremesa';
      packageSummary.textContent=`Este pacote é ${entry} e ${dessert}.`;
    }
  }

  packageAwareMenuGroups.forEach(group=>{
    const requiredFeature=group.dataset.requiresFeature||'always';
    let visible=true;
    if(requiredFeature==='entry'&&features.entry==='0')visible=false;
    if(requiredFeature==='dessert'&&features.dessert==='0')visible=false;
    group.classList.toggle('hidden',!visible);
    group.setAttribute('aria-hidden',String(!visible));
    if(!visible){
      group.querySelectorAll('[data-menu-option="1"]').forEach(input=>{
        input.checked=false;
        input.disabled=false;
      });
    }
  });
  updateMenuSummary();
}
packageChoice?.addEventListener('change',updatePackageState);

function groupInputs(group){
  return [...group.querySelectorAll('[data-menu-option="1"]')];
}

function groupRules(group){
  const min=Math.max(0,Number.parseInt(group.dataset.minChoices||'0',10)||0);
  const configuredMax=Math.max(0,Number.parseInt(group.dataset.maxChoices||'0',10)||0);
  const per100=Math.max(0,Number.parseInt(group.dataset.choicesPer100||'0',10)||0);
  const guests=Math.max(0,Number.parseInt(guestsInput?.value||'0',10)||0);
  let max=configuredMax;
  if(per100>0){
    // Sem número de convidados, mostramos o primeiro bloco de 100. Quando o cliente
    // informa a quantidade, cada bloco iniciado de 100 libera mais opções.
    const blocks=Math.max(1,Math.ceil((guests||1)/100));
    max=per100*blocks;
  }
  return {
    min,
    max,
    per100,
    guests,
    mode:group.dataset.selectionMode||'multiple',
    name:group.dataset.categoryName||group.querySelector('h3')?.textContent?.trim()||'Categoria',
  };
}

function updateGroupState(group,message=''){
  if(group.classList.contains('hidden'))return;
  const inputs=groupInputs(group);
  const checked=inputs.filter(input=>input.checked);
  const {min,max,per100,guests,mode}=groupRules(group);
  const status=group.querySelector('.menu-group-status');

  if(mode==='multiple'){
    const atLimit=max>0&&checked.length>=max;
    inputs.forEach(input=>{input.disabled=atLimit&&!input.checked;});
  }else{
    inputs.forEach(input=>{input.disabled=false;});
  }

  if(!status)return;
  if(message){
    status.textContent=message;
    status.className='menu-group-status field-help error';
    return;
  }

  if(per100>0){
    const guestDetail=guests>0?` para ${guests} convidado(s)`:'';
    status.textContent=`${checked.length} de até ${Math.min(max,inputs.length)} opção(ões) selecionada(s)${guestDetail}.`;
    status.className='menu-group-status field-help success';
  }else if(mode==='single'){
    status.textContent=checked.length?'1 opção selecionada.':'Escolha 1 opção.';
    status.className=`menu-group-status field-help ${checked.length?'success':''}`;
  }else if(min>0&&checked.length<min){
    status.textContent=`${checked.length} selecionada(s). Mínimo: ${min}.`;
    status.className='menu-group-status field-help';
  }else if(max>0){
    status.textContent=`${checked.length} de ${max} selecionada(s).`;
    status.className='menu-group-status field-help success';
  }else if(checked.length){
    status.textContent=`${checked.length} selecionada(s).`;
    status.className='menu-group-status field-help success';
  }else{
    status.textContent='';
    status.className='menu-group-status field-help';
  }
}

function selectedMenuByCategory(){
  const groups=new Map();
  menuOptions.filter(input=>input.checked).forEach(input=>{
    const category=input.dataset.category||'Outras opções';
    if(!groups.has(category))groups.set(category,[]);
    groups.get(category).push(input.value);
  });
  return groups;
}

function updateMenuSummary(){
  menuChoiceGroups.forEach(group=>updateGroupState(group));
  const count=menuOptions.filter(input=>input.checked).length;
  if(!menuSelectionSummary)return;
  menuSelectionSummary.textContent=count
    ? `${count} escolha(s) registrada(s). Os demais itens do buffet não precisam ser marcados.`
    : 'Faça apenas as escolhas indicadas. Churrasco, saladas e itens inclusos não precisam ser marcados.';
  menuSelectionSummary.className=`field-help ${count?'success':''}`;
}

function validateMenuSelection(){
  for(const group of menuChoiceGroups){
    if(group.classList.contains('hidden'))continue;
    const inputs=groupInputs(group);
    const count=inputs.filter(input=>input.checked).length;
    const {min,max,name}=groupRules(group);
    let message='';
    if(min>0&&count<min){
      message=`Em ${name}, escolha ${min===1?'1 opção':`pelo menos ${min} opções`}.`;
    }else if(max>0&&count>max){
      message=`Em ${name}, escolha no máximo ${max} opção(ões).`;
    }
    if(message){
      updateGroupState(group,message);
      group.scrollIntoView({behavior:'smooth',block:'center'});
      return false;
    }
  }
  return true;
}

menuOptions.forEach(input=>input.addEventListener('change',()=>{
  const group=input.closest('.menu-choice-group');
  if(group){
    const inputs=groupInputs(group);
    const {max,mode}=groupRules(group);
    const checked=inputs.filter(item=>item.checked);
    if(mode==='multiple'&&max>0&&checked.length>max){
      input.checked=false;
      updateGroupState(group,`Você pode escolher no máximo ${max} opção(ões) nesta categoria.`);
    }else{
      updateGroupState(group);
    }
  }
  updateMenuSummary();
}));

document.querySelector('#clear-menu-all')?.addEventListener('click',()=>{
  menuOptions.forEach(input=>{input.checked=false;input.disabled=false;});
  updateMenuSummary();
});

guestsInput?.addEventListener('input',()=>{
  menuChoiceGroups.forEach(group=>{
    const {max,mode}=groupRules(group);
    if(mode==='multiple'&&max>0){
      const checked=groupInputs(group).filter(input=>input.checked);
      checked.slice(max).forEach(input=>{input.checked=false;});
    }
    updateGroupState(group);
  });
  updateMenuSummary();
});

updatePackageState();
updateMenuSummary();
checkTravel();

form?.addEventListener('submit',event=>{
  event.preventDefault();

  if(!validateMenuSelection())return;
  const outside=checkTravel();
  if(outside&&travelAware&&!travelAware.checked){
    travelAware.reportValidity();
    return;
  }

  const data=new FormData(form);
  const number=String(form.dataset.whatsapp||'').replace(/\D/g,'');
  if(number.length<12){
    if(budgetStatus){
      budgetStatus.className='field-help error';
      budgetStatus.textContent='O número do WhatsApp não está configurado corretamente. Use o botão verde de contato.';
    }
    return;
  }

  const travelText=outside
    ? 'Sim — ciente de possível acréscimo de deslocamento.'
    : `Evento em ${form.dataset.baseCity} ou cidade ainda não confirmada.`;
  const selectedMenu=selectedMenuByCategory();
  const menuLines=[];
  selectedMenu.forEach((items,category)=>{
    menuLines.push(`*${category}:* ${items.join(', ')}`);
  });
  const customMenu=(customMenuInput?.value||'').trim();
  if(customMenu)menuLines.push(`*Pedido especial/restrição:* ${customMenu}`);
  if(!menuLines.length)menuLines.push('Sem escolhas adicionais informadas; seguir itens padrão do buffet conforme o pacote.');

  let availabilityText='Disponibilidade será confirmada pela equipe.';
  if(selectedAvailability){
    if(selectedAvailability.status==='lotada'){
      availabilityText='A data aparece como lotada; solicito avaliação de alternativa ou possibilidade excepcional.';
    }else if(selectedAvailability.status==='indisponivel'){
      availabilityText='A data aparece como indisponível; gostaria de consultar outras possibilidades.';
    }else{
      availabilityText=selectedAvailability.message;
    }
  }

  const lines=[
    `Olá! Gostaria de solicitar um orçamento do ${form.dataset.brand}.`,
    '',
    `*Situação da agenda:* ${availabilityText}`,
    `*Nome:* ${data.get('nome')}`,
    `*Data do evento:* ${data.get('data')||'A definir'}`,
    `*Cidade:* ${data.get('cidade')}`,
    `*Convidados:* ${data.get('convidados')}`,
    `*Tipo de evento:* ${data.get('evento')}`,
    `*Pacote:* ${data.get('pacote')}`,
    '',
    '*Escolhas do cardápio:*',
    menuLines.join('\n'),
    '',
    '*Itens padrão:* churrasco, saladas e itens inclusos seguem o cardápio do buffet e não precisam de seleção.',
    `*Deslocamento:* ${travelText}`,
    `*Observações:* ${data.get('mensagem')||'Nenhuma'}`,
  ];

  // IMPORTANTE PARA CELULAR: não existe await/fetch entre o clique no botão e
  // a navegação. Safari/iOS pode bloquear a abertura do WhatsApp quando o gesto
  // do usuário é perdido após uma operação assíncrona.
  const whatsappUrl=`https://wa.me/${number}?text=${encodeURIComponent(lines.join('\n'))}`;
  const fallback=document.querySelector('#whatsapp-fallback');
  if(fallback){
    fallback.href=whatsappUrl;
    fallback.classList.remove('hidden');
  }
  if(budgetSubmit){
    budgetSubmit.disabled=true;
    budgetSubmit.textContent='Abrindo WhatsApp...';
  }
  if(budgetStatus){
    budgetStatus.className='field-help success';
    budgetStatus.textContent='Abrindo o WhatsApp com a mensagem do orçamento...';
  }

  // Se o navegador bloquear a navegação por algum motivo, o usuário não fica
  // preso com o botão desabilitado: o link alternativo continua disponível.
  window.setTimeout(()=>{
    if(document.visibilityState==='visible'&&budgetSubmit){
      budgetSubmit.disabled=false;
      budgetSubmit.textContent='Enviar pelo WhatsApp';
    }
  },2500);
  window.location.href=whatsappUrl;
});

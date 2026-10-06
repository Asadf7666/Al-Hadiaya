/* Shared keyboard access for the desktop and hosted workspace. */
(() => {
  const $ = selector => document.querySelector(selector);
  const routes = [
    ['1', 'overview'], ['2', 'billing'], ['3', 'inventory'], ['4', 'purchases'],
    ['5', 'cafe'], ['6', 'people'], ['7', 'reports'], ['8', 'planning'],
    ['9', 'orders'], ['0', 'notifications'], ['s', 'settings'], ['t', 'staff']
  ];
  let navigating = false, opener = null, palette = [], selected = 0, scheduled = false, dialogVersion = 0;
  const available = el => !!el && !el.disabled && !el.closest('[inert]') && el.getClientRects().length > 0;
  function remember(el = document.activeElement) {
    if (!el || el === document.body) return null;
    const result = {el, id:el.id, key:el.dataset.kbKey, click:el.getAttribute('onclick'), text:el.textContent?.trim(), tag:el.tagName};
    if (el.matches('input:not([type=password]),textarea')) {
      result.value = el.value;
      try {result.start = el.selectionStart; result.end = el.selectionEnd;} catch {}
    }
    return result;
  }
  function restore(saved, preserveValue = false) {
    if (!saved) return false;
    let el = available(saved.el) ? saved.el : saved.id ? document.getElementById(saved.id) : null;
    if (!available(el) && saved.key) el = document.querySelector('[data-kb-key="'+CSS.escape(saved.key)+'"]');
    if (!available(el) && saved.click) el = [...document.querySelectorAll('[onclick]')].find(e => available(e) && e.getAttribute('onclick') === saved.click);
    if (!available(el) && saved.text) el = [...document.querySelectorAll('button,a[href]')].find(e => available(e) && e.tagName === saved.tag && e.textContent.trim() === saved.text);
    if (!available(el)) return false;
    if (preserveValue && saved.value !== undefined && el.matches('input:not([type=password]),textarea')) el.value = saved.value;
    el.focus({preventScroll:true});
    if (saved.start != null) try {el.setSelectionRange(saved.start, saved.end);} catch {}
    return true;
  }
  function sidebar() {
    const aside = $('.sidebar'), button = $('#mobile-menu');
    if (!aside) return;
    const open = innerWidth > 850 || aside.classList.contains('open');
    aside.inert = !open;
    aside.setAttribute('aria-hidden', String(!open));
    if (button) {button.setAttribute('aria-expanded', String(open)); button.setAttribute('aria-controls', 'sidebar-navigation');}
    if ($('#nav-backdrop')) $('#nav-backdrop').tabIndex = -1;
  }
  function enhance() {
    sidebar();
    const main = $('#main');
    if (main) main.tabIndex = -1;
    document.querySelectorAll('#nav button').forEach(button => {
      const route = button.getAttribute('onclick')?.match(/navTo\('([^']+)/)?.[1];
      if (!route) return;
      button.dataset.kbKey = 'nav-'+route;
      button.setAttribute('aria-label', pages[route] || button.textContent.trim());
      if (page === route) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
      const shortcut = routes.find(([,name]) => name === route);
      if (shortcut) {button.setAttribute('aria-keyshortcuts', 'Alt+'+shortcut[0]); button.title = (pages[route] || route)+' · Alt+'+shortcut[0].toUpperCase();}
    });
    document.querySelectorAll('.tabs').forEach((tabs, group) => {
      tabs.setAttribute('role', 'tablist'); tabs.setAttribute('aria-label', group === 0 ? 'View filters' : 'Additional filters');
      tabs.querySelectorAll('button').forEach((button, index) => {
        button.setAttribute('role','tab'); button.setAttribute('aria-selected',String(button.classList.contains('active')));
        button.tabIndex = button.classList.contains('active') ? 0 : -1;
        button.dataset.kbKey = 'filter-'+group+'-'+(button.dataset.category || button.textContent.trim());
      });
    });
    document.querySelectorAll('.product-card').forEach(button => {
      button.dataset.kbKey = 'product-'+(button.getAttribute('onclick')?.match(/addCart\((\d+)/)?.[1] || button.textContent.trim());
      button.setAttribute('aria-label',button.textContent.trim().replace(/\s+/g,' '));
    });
    document.querySelectorAll('.cart-line').forEach(line => {
      const name = line.querySelector('strong')?.textContent || 'item';
      line.querySelectorAll('button').forEach(button => {
        if (['+','＋'].includes(button.textContent.trim())) button.setAttribute('aria-label','Increase '+name+' quantity');
        if (['−','-'].includes(button.textContent.trim())) button.setAttribute('aria-label','Decrease '+name+' quantity');
      });
      line.querySelector('input[type=number]')?.setAttribute('aria-label', name+' quantity');
    });
    for (const [selector, names] of [['.purchase-line',['Product','Quantity','Cost per unit']],['.recipe-line',['Ingredient','Quantity per serving']]]) {
      document.querySelectorAll(selector).forEach((row, index) => row.querySelectorAll('select,input').forEach((el,n) => {
        el.setAttribute('aria-label',(names[n] || 'Value')+' '+(index+1));
      }));
    }
    for (const [id, label] of [['node-location','Transaction location'],['online-location','Transaction location'],['sale-party','Customer for current bill'],['discount','Bill discount in rupees']]) document.getElementById(id)?.setAttribute('aria-label',label);
    document.querySelector('.cart-head select:not([id])')?.setAttribute('aria-label','Selling price tier');
    document.querySelectorAll('input,select,textarea').forEach(el => {
      if (el.type === 'hidden' || el.hasAttribute('aria-label') || el.labels?.length) return;
      const label = el.closest('.field')?.querySelector('label')?.textContent || el.placeholder || el.name;
      if (label) el.setAttribute('aria-label',label);
    });
    document.querySelectorAll('.table-wrap').forEach(el => {
      el.tabIndex = 0; el.setAttribute('role','region');
      el.setAttribute('aria-label',(el.closest('.card')?.querySelector('h2')?.textContent || 'Records')+' table; use arrow keys to scroll');
    });
    if ($('#product-search')) {
      $('#product-search').setAttribute('aria-label','Search products or scan barcode');
      $('#product-search').setAttribute('aria-keyshortcuts','F3');
      $('#product-search').title = 'F3 to search; Down to choose a result; Enter to add or scan an exact barcode';
    }
    const dialog = $('#modal');
    if (dialog) {
      const title = dialog.querySelector('h2');
      if (title) {title.id = 'dialog-title'; title.tabIndex = -1; dialog.setAttribute('aria-labelledby',title.id);}
      dialog.setAttribute('aria-modal','true');
      dialog.querySelectorAll('.error').forEach(el => el.setAttribute('role','alert'));
    }
    if ($('.header-right') && !$('#keyboard-help')) {
      const button = document.createElement('button'); button.id = 'keyboard-help'; button.className = 'btn secondary small';
      button.textContent = '⌨'; button.setAttribute('aria-label','Keyboard shortcuts'); button.title = 'Keyboard shortcuts · Alt+K';
      button.onclick = help; $('.header-right').appendChild(button);
    }
  }
  function schedule() {
    if (scheduled) return;
    scheduled = true; requestAnimationFrame(() => {scheduled = false; enhance();});
  }
  function focusMain() {$('#main')?.focus({preventScroll:true});}
  function go(route) {if (pageAllowed(route)) navTo(route); else toast('Your role does not allow this page.',true);}
  function help() {
    if ($('#modal').open) return;
    const shortcuts = [['Ctrl+K / ⌘K','Find a page or action'],['Alt+1 … Alt+0','Open business pages'],['Alt+S / Alt+T','Settings / staff'],['F2','Open POS; keep current basket'],['F3','Search products or scan barcode'],['F4','Add or receive on this page'],['F8','Open checkout'],['F9','Invoice history'],['Ctrl+Enter / ⌘Enter','Submit the current form'],['Esc','Close a dialog or navigation'],['Tab / Shift+Tab','Next / previous control'],['Arrow keys','Choose product cards or view tabs'],['Alt+N / Alt+M','Focus navigation / workspace'],['Alt+L','Focus location selector'],['Alt+K','This shortcut guide']];
    openModal('Keyboard shortcuts','<p>Keyboard access works offline. Saving still uses the normal validation and confirmation screens.</p>'+table(['Shortcut','Action'],shortcuts.map(([key,value])=>'<tr><td><kbd>'+esc(key)+'</kbd></td><td>'+esc(value)+'</td></tr>')),'<button class="btn secondary" onclick="closeModal()">Close</button>');
  }
  function actions() {
    const result = Object.keys(pages).filter(pageAllowed).map(route => ({title:pages[route],group:'Page',run:()=>go(route)}));
    function add(title,group,permission,run) {if (canOperate(permission)) result.push({title,group,run});}
    add('Add product','Inventory','product',()=>{go('inventory');productForm();});
    add('Transfer stock','Inventory','transfer',()=>{go('inventory');transferForm();});
    add('Receive supplier purchase','Purchases','purchase',()=>{go('purchases');purchaseForm();});
    add('Add customer','Profiles','party',()=>{go('people');partyForm('customer');});
    if (['owner','manager'].includes(S.web_user?.role)) add('Add supplier','Profiles','party',()=>{go('people');partyForm('supplier');});
    add('Add café menu item','Café','product',()=>{go('cafe');productForm(null,true);});
    if (pageAllowed('cafe')) add('Open café POS','Café','sale',()=>openCafePOS());
    add('Record expense','Reports','expense',()=>expenseForm());
    add('Draft purchase order','Planning','purchase_order_create',()=>{go('planning');purchaseOrderForm();});
    if (pageAllowed('notifications')) result.push({title:'Draft WhatsApp campaign',group:'WhatsApp',run:()=>{go('notifications');campaignForm();}});
    if (S.web_user?.role === 'owner') result.push({title:'Add staff account',group:'Staff',run:()=>{go('staff');staffForm();}});
    add('Back up now','Recovery','backup',()=>runBackup());
    return result;
  }
  function drawPalette() {
    const query = $('#command-query').value.toLowerCase(); palette = actions().filter(a=>(a.title+' '+a.group).toLowerCase().includes(query));
    selected = 0;
    $('#command-results').innerHTML = palette.length ? palette.map((a,i)=>'<button type="button" data-command="'+i+'"><strong>'+esc(a.title)+'</strong><small>'+esc(a.group)+'</small></button>').join('') : '<p>No matching actions for your account.</p>';
    $('#command-results').querySelectorAll('button').forEach(button => button.onclick = () => choose(Number(button.dataset.command)));
    $('#command-count').textContent = palette.length+' matching action'+(palette.length===1?'':'s'); highlight();
  }
  function highlight() {
    $('#command-results')?.querySelectorAll('button').forEach((button,i)=> {button.classList.toggle('selected',i===selected);button.setAttribute('aria-current',i===selected?'true':'false');});
    $('#command-results button.selected')?.scrollIntoView({block:'nearest'});
  }
  function choose(index) {const action = palette[index]; if (action) {closeModal(); action.run();}}
  function commands() {
    if ($('#modal').open) return;
    openModal('Find a page or action','<label for="command-query">Search the business workspace</label><input id="command-query" placeholder="Try stock, customer, café or purchase…" autocomplete="off" aria-describedby="command-instructions"><p id="command-instructions">Type to filter. Use Up/Down and Enter to choose, or Tab to a result.</p><div id="command-results" class="command-results"></div><p id="command-count" role="status"></p>');
    $('#command-query').oninput = drawPalette; drawPalette();
  }
  function primaryAction() {
    const map = {inventory:()=>productForm(),purchases:()=>purchaseForm(),cafe:()=>productForm(null,true),people:()=>partyForm(peopleFilter),reports:()=>expenseForm(),planning:()=>purchaseOrderForm(),notifications:()=>campaignForm(),staff:()=>staffForm()};
    const permission = {inventory:'product',purchases:'purchase',cafe:'product',people:'party',reports:'expense',planning:'purchase_order_create',notifications:'whatsapp_settings',staff:'staff_user'}[page];
    if (['staff','notifications'].includes(page) && S.web_user?.role!=='owner') return;
    if (map[page] && canOperate(permission)) map[page]();
  }
  function grid(event, button) {
    const cards = [...button.closest('.product-grid').querySelectorAll('.product-card')].filter(available);
    if (!cards.length) return;
    const index = cards.indexOf(button), columns = cards.filter(el=>Math.abs(el.getBoundingClientRect().top-cards[0].getBoundingClientRect().top)<2).length;
    let next = index;
    if (event.key==='ArrowRight') next++; if (event.key==='ArrowLeft') next--;
    if (event.key==='ArrowDown') next+=columns; if (event.key==='ArrowUp') next-=columns;
    if (event.key==='Home') next=0; if (event.key==='End') next=cards.length-1;
    event.preventDefault();cards[Math.max(0,Math.min(cards.length-1,next))].focus();
  }
  document.addEventListener('keydown',event => {
    if (event.isComposing || event.ctrlKey && event.altKey || typeof S==='undefined' || !S) return;
    const key = event.key, lower = key.toLowerCase(), dialog = $('#modal'), target = event.target;
    if (event.repeat && ['Enter','F8'].includes(key)) {event.preventDefault();return;}
    if (dialog.open) {
      if (key==='Tab') {
        const fields=[...dialog.querySelectorAll('button,a[href],input:not([type=hidden]),select,textarea,[tabindex]')].filter(el=>available(el)&&el.tabIndex>=0);
        const index=fields.indexOf(document.activeElement);
        if(fields.length && (index<0 || event.shiftKey&&index===0 || !event.shiftKey&&index===fields.length-1)) {
          event.preventDefault();fields[event.shiftKey?fields.length-1:0].focus();
        }
        return;
      }
      const busy = $('#form-submit')?.disabled;
      if (busy && ['Escape','Enter'].includes(key)) {event.preventDefault();toast('Saving. Please wait for the result.');return;}
      if (key==='Escape') {event.preventDefault();closeModal();return;}
      if ((event.ctrlKey || event.metaKey) && key==='Enter') {
        const form = dialog.querySelector('form');if (form && !busy) {event.preventDefault();form.requestSubmit();}return;
      }
      if (target.id==='command-query' && ['ArrowDown','ArrowUp','Enter'].includes(key)) {
        event.preventDefault();
        if (key==='Enter') choose(selected);
        else if (palette.length) {selected=(selected+(key==='ArrowDown'?1:-1)+palette.length)%palette.length;highlight();}
      }
      return;
    }
    if ((event.ctrlKey || event.metaKey) && lower==='k') {event.preventDefault();commands();return;}
    if ((event.ctrlKey || event.metaKey) && key==='Enter' && page==='settings') {const form=$('#settings-form');if(form){event.preventDefault();form.requestSubmit();}return;}
    if (event.altKey && !event.shiftKey) {
      const route = routes.find(([shortcut])=>shortcut===lower);
      if (route) {event.preventDefault();go(route[1]);return;}
      if (lower==='k') {event.preventDefault();help();return;}
      if (lower==='m') {event.preventDefault();focusMain();return;}
      if (lower==='n') {event.preventDefault();$('.sidebar').classList.add('open');sidebar();$('#nav button')?.focus();return;}
      if (lower==='l') {event.preventDefault();($('#node-location') || $('#online-location'))?.focus();return;}
    }
    if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey && key.startsWith('F')) return;
    const shortcuts = {F1:help,F2:()=>go('billing'),F3:()=>{go('billing');$('#product-search')?.focus();},F4:primaryAction,F8:()=>{if(page==='billing'&&canOperate('sale'))checkout();},F9:()=>{if(pageAllowed('billing'))invoiceList();}};
    if (shortcuts[key]) {event.preventDefault();if(!event.repeat)shortcuts[key]();return;}
    if (key==='Escape' && $('.sidebar')?.classList.contains('open') && innerWidth<=850) {event.preventDefault();$('.sidebar').classList.remove('open');sidebar();$('#mobile-menu')?.focus();return;}
    if (target.id==='product-search' && key==='ArrowDown') {const first=$('#product-results .product-card');if(first){event.preventDefault();first.focus();}return;}
    if (target.id==='product-search' && key==='Enter') {
      const exact=S.products.some(p=>(p.sku===target.value.trim()||p.barcode===target.value.trim())&&p.kind!=='ingredient');
      if (!exact) {const cards=[...document.querySelectorAll('#product-results .product-card')];if(cards.length){event.preventDefault();event.stopImmediatePropagation();if(cards.length===1)cards[0].click();else cards[0].focus();}}return;
    }
    if (target.matches('.product-card') && ['ArrowRight','ArrowLeft','ArrowUp','ArrowDown','Home','End'].includes(key)) {grid(event,target);return;}
    if (target.matches('.tabs button') && ['ArrowRight','ArrowLeft','Home','End'].includes(key)) {
      const buttons=[...target.parentElement.querySelectorAll('button')],index=buttons.indexOf(target);
      const next=key==='Home'?0:key==='End'?buttons.length-1:(index+(key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;
      event.preventDefault();buttons[next].focus();buttons[next].click();enhance();
    }
  },true);
  function install() {
    const baseRender=render;render=function(...args){const saved=remember();const result=baseRender(...args);enhance();if(!navigating&&!$('#modal').open)restore(saved,true);return result;};
    const baseNav=navTo;navTo=function(name){if(!pageAllowed(name))return baseNav(name);dialogVersion++;navigating=true;try{baseNav(name);enhance();focusMain();}finally{navigating=false;}};
    const baseOpen=openModal;openModal=function(...args){if(!$('#modal').open)opener=remember();const version=++dialogVersion;baseOpen(...args);enhance();requestAnimationFrame(()=>{const dialog=$('#modal');if(!dialog.open||version!==dialogVersion)return;const field=dialog.querySelector('form input:not([type=hidden]):not([type=checkbox]),form select,form textarea,#command-query,input[type=search],#invoice-search');(available(field)?field:dialog.querySelector('h2'))?.focus({preventScroll:true});});};
    const baseClose=closeModal;closeModal=function(){const saved=opener;opener=null;const version=++dialogVersion;baseClose();queueMicrotask(()=>{if(version===dialogVersion&&!$('#modal').open&&!restore(saved))focusMain();});};
    $('#modal').addEventListener('cancel',event=>{event.preventDefault();closeModal();});
    document.addEventListener('click',event=>{if(event.target.closest('#mobile-menu,#nav-backdrop'))schedule();});
    new MutationObserver(schedule).observe(document.body,{subtree:true,childList:true});
    addEventListener('resize',sidebar);enhance();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();

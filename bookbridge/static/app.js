const members=[[],[]],cards=[...document.querySelectorAll('.card')],mode=document.querySelector('#mode'),statusEl=document.querySelector('#status'),output=document.querySelector('#output');
let revision=0; const searches=[0,0];
function renderChips(i){const box=cards[i].querySelector('.chips');box.replaceChildren();members[i].forEach((x,n)=>{const b=document.createElement('button');b.type='button';b.className='chip';b.textContent=`${x.name} ×`;b.ariaLabel=`Remove ${x.name}`;b.onclick=()=>{members[i].splice(n,1);revision++;output.hidden=true;renderChips(i)};box.append(b)})}
mode.onchange=()=>{revision++;members.forEach((xs,i)=>{xs.length=0;renderChips(i);cards[i].querySelector('.results').replaceChildren();const input=cards[i].querySelector('input');input.value='';input.placeholder=mode.value==='sample'?(i?'Try Harbor':'Try Lattice Lanterns'):'Search a cultural anchor'});output.hidden=true;statusEl.textContent='';document.querySelector('#mode-note').textContent=mode.value==='sample'?'Sample mode uses invented titles and tastes; no Qloo calls are made.':'Live mode uses Qloo. Confirm real entities; missing access never falls back to samples.'};
cards.forEach((card,i)=>card.querySelector('.search button').onclick=async()=>{
 const input=card.querySelector('input'),kind=card.querySelector('select').value,out=card.querySelector('.results'),expectedMode=mode.value,token=++searches[i],rev=revision;
 out.textContent='Searching…';
 try{const r=await fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:input.value,kind,mode:expectedMode})}),d=await r.json();
 if(rev!==revision||token!==searches[i])return;if(!r.ok)throw Error(d.detail||'Search failed');out.replaceChildren();
 d.results.forEach(x=>{const b=document.createElement('button');b.type='button';b.textContent=`${x.name} · ${x.kind}`;b.onclick=()=>{if(mode.value!==expectedMode)return;if(members[i].length>=3){out.textContent='Remove an anchor before adding another.';return}if(!members[i].some(a=>a.id===x.id)){members[i].push(x);revision++;output.hidden=true;renderChips(i)}out.replaceChildren()};out.append(b)});
 if(!d.results.length)out.textContent='No confirmed entities found.';
 }catch(e){if(rev===revision&&token===searches[i])out.textContent=e.message}
});
function bookCard(x){const d=document.createElement('article');d.className='book';const h=document.createElement('h3');h.textContent=x.name;const a=document.createElement('div');a.className='meta';a.textContent=[x.author,`reader ranks ${x.member_ranks[0]} / ${x.member_ranks[1]}`].filter(Boolean).join(' · ');d.append(h,a);return d}
document.querySelector('#form').onsubmit=async e=>{
 e.preventDefault();if(members.some(x=>x.length<1)){statusEl.textContent='Choose at least one anchor for each reader.';return}
 const rev=++revision;output.hidden=true;statusEl.textContent='Building and rescoring one candidate pool…';
 try{const r=await fetch('/api/shared',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({members,mode:mode.value,top_k:3})}),d=await r.json();if(rev!==revision)return;if(!r.ok)throw Error(d.detail||'Recommendation failed');
 const s=document.querySelector('#shared');s.replaceChildren(...d.shared.map(bookCard));if(!d.shared.length)s.textContent='No books had rank evidence for both readers in this pool.';
 const st=document.querySelector('#stretch');st.replaceChildren();if(d.stretch){st.append(bookCard(d.stretch));const p=document.createElement('p');p.textContent=`Rank gap: ${d.stretch.rank_gap}. A more uneven option, still ranked for both readers.`;st.append(p)}else st.textContent='No additional book had different ranks for both readers.';
 document.querySelector('#method').textContent=d.method;document.querySelector('#coverage').replaceChildren(...d.coverage.map((x,i)=>{const li=document.createElement('li');li.textContent=`Reader ${i+1}: ${x.returned}/${x.pool} candidates ranked; ${x.missing} unknown.`;return li}));document.querySelector('#trace').replaceChildren(...d.trace.map(x=>{const li=document.createElement('li');li.textContent=x;return li}));output.hidden=false;statusEl.textContent=`${d.mode==='sample'?'Invented sample':'Live Qloo'} result ready.`;
 }catch(err){if(rev===revision)statusEl.textContent=err.message}
};
fetch('/api/status').then(r=>r.json()).then(x=>{document.querySelector('#badge').textContent=x.live_available?'Live key configured · verify via search':'Live access pending · sample ready'}).catch(()=>{document.querySelector('#badge').textContent='Access status unavailable'});

(function () {
    const dataEl = document.getElementById('survey-charts-data');
    if (!dataEl) return;
    let charts = [];
    try { charts = JSON.parse(dataEl.textContent || '[]'); } catch(e){ charts=[]; }

    const palette = ['#2d6a4f','#40916c','#74c69d','#95d5b2','#d8f3dc','#22577a','#38a3a5','#57cc99','#80ed99','#c7f9cc'];

    charts.forEach((item, idx)=>{
        const canvas = document.getElementById('survey-chart-' + idx);
        if(!canvas) return;
        const colors = item.labels.map((_,i)=>palette[i%palette.length]);
        const total = (item.data||[]).reduce((a,b)=>a+Number(b||0),0);
        const isMobile = window.matchMedia('(max-width: 640px)').matches;
        new Chart(canvas,{
            type: item.type||'bar',
            data:{ labels:item.labels||[], datasets:[{ label:'Responses', data:item.data||[], backgroundColor:item.type==='bar'?'#74c69d':colors, borderColor:item.type==='bar'?'#2d6a4f':'#ffffff', borderWidth:1 }] },
            options:{
                responsive:true,
                maintainAspectRatio:false,
                plugins:{
                    datalabels:item.type==='pie'?{
                        color:'#ffffff',
                        font:{ weight:'bold', size:12 },
                        formatter:function(value){ if(!total) return ''; const pct=(Number(value)*100)/total; return pct>=3?pct.toFixed(1)+'%':''; }
                    }:{ display:false },
                    legend:{ display:true, position:isMobile?'bottom':'right' },
                    tooltip:{ callbacks:{ label:function(ctx){ const value=Number(ctx.raw||0); if(!total) return String(value); const pct=(value*100)/total; return ctx.label+': '+value+' ('+pct.toFixed(1)+'%)'; } } }
                },
                scales:item.type==='bar'?{ y:{ beginAtZero:true, ticks:{ precision:0 }}}:{}
            },
            plugins:[ChartDataLabels]
        });
    });

    setTimeout(()=>window.location.reload(),60000);
})();

(function(){
    const el=document.getElementById('survey-motivation-text');
    if(!el) return;
    const fullText=el.getAttribute('data-full-text')||'';
    let i=0;
    const speed=18;
    function typeStep(){ el.textContent = fullText.slice(0,i); if(i<fullText.length){ i+=1; setTimeout(typeStep,speed); } }
    typeStep();
})();

(function(){
    const buttons=document.querySelectorAll('.survey-emoji-btn');
    const status=document.getElementById('survey-emoji-status');
    if(!buttons.length||!status) return;
    buttons.forEach(function(btn){
        btn.addEventListener('click', function(){
            buttons.forEach(b=>{ b.classList.remove('ring-2','ring-primary','bg-primary/10'); });
            btn.classList.add('ring-2','ring-primary','bg-primary/10');
            status.textContent='Thanks for your feedback '+(btn.dataset.emoji||'');
            status.classList.remove('hidden');
        });
    });
})();

(function(){
    const refreshBtn=document.getElementById('refreshBtn');
    if(refreshBtn) refreshBtn.addEventListener('click',()=>{ refreshBtn.classList.add('animate-spin'); setTimeout(()=>refreshBtn.classList.remove('animate-spin'),2000); });
})();

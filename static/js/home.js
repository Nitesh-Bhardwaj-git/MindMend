(function(){
  // Location sharing banner logic
  const config = window.HOME_CONFIG || {};
  const banner = document.getElementById('locationShareBanner');
  
  if (banner && config.shareLocationUrl) {
    let autoHideTimer = null;

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function hideBanner() {
        banner.classList.add('hidden');
        if (autoHideTimer) {
            clearTimeout(autoHideTimer);
            autoHideTimer = null;
        }
    }

    function showBanner() {
        if (localStorage.getItem('mindmend_geo_permission_granted') === 'true') return;
        banner.classList.remove('hidden');
        autoHideTimer = setTimeout(hideBanner, 5000);
    }

    if (localStorage.getItem('mindmend_geo_permission_granted') === 'true') {
        // Do nothing
    } else if (navigator.permissions && navigator.permissions.query) {
        navigator.permissions.query({ name: 'geolocation' }).then(function(res) {
            if (res.state === 'granted') {
                localStorage.setItem('mindmend_geo_permission_granted', 'true');
            } else {
                showBanner();
            }
        }).catch(function() { showBanner(); });
    } else {
        showBanner();
    }

    document.getElementById('dismissLocationBanner')?.addEventListener('click', function(){
        hideBanner();
    });

    document.getElementById('shareLocationBtn')?.addEventListener('click', function(){
        if (!navigator.geolocation) { alert('Geolocation not supported.'); return; }
        const btn = this;
        hideBanner();
        btn.disabled = true;
        btn.textContent = 'Sharing...';
        navigator.geolocation.getCurrentPosition(
            function(pos){
                fetch(config.shareLocationUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({lat: pos.coords.latitude, lon: pos.coords.longitude})
                }).then(function(r){
                    if (!r.ok) throw new Error('Location save failed');
                    return r.json();
                }).then(function(){
                    localStorage.setItem('mindmend_geo_last_sent_at', String(Date.now()));
                    localStorage.setItem('mindmend_geo_permission_granted', 'true');
                }).catch(function(){
                    btn.disabled = false;
                    btn.textContent = 'Share';
                });
            },
            function(){
                btn.disabled = false;
                btn.textContent = 'Share';
            },
            {enableHighAccuracy: true, timeout: 10000}
        );
    });
  }

  // FAQ logic
  const initFAQ = function () {
    const tabs = document.querySelectorAll('.faq-tab');
    const panels = document.querySelectorAll('.faq-panel');

    tabs.forEach(tab => {
      tab.addEventListener('click', function () {
        const category = this.dataset.category;

        tabs.forEach(t => {
          t.classList.remove('bg-[#00d1b2]', 'text-black');
          t.classList.add('bg-white/5', 'text-gray-400');
        });

        this.classList.remove('bg-white/5', 'text-gray-400');
        this.classList.add('bg-[#00d1b2]', 'text-black');

        panels.forEach(panel => {
          panel.classList.add('hidden');
        });

        const activePanel = document.querySelector(`[data-panel="${category}"]`);
        if (activePanel) activePanel.classList.remove('hidden');
      });
    });

    document.querySelectorAll('.faq-toggle').forEach(button => {
      button.addEventListener('click', function () {
        const item = this.closest('.faq-item');
        const answer = item.querySelector('.faq-answer');
        const icon = item.querySelector('.faq-icon');
        if (!answer || !icon) return;
        const isOpen = !answer.classList.contains('hidden');

        document.querySelectorAll('.faq-answer').forEach(el => el.classList.add('hidden'));
        document.querySelectorAll('.faq-icon').forEach(el => {
          el.classList.remove('rotate-90', 'bg-[#00d1b2]', 'text-black', 'border-transparent');
        });

        if (!isOpen) {
          answer.classList.remove('hidden');
          icon.classList.add('rotate-90', 'bg-[#00d1b2]', 'text-black', 'border-transparent');
        }
      });
    });
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFAQ);
  } else {
    initFAQ();
  }
})();

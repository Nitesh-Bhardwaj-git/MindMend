(function() {
    const config = window.DOCTOR_DASHBOARD_CONFIG || {};

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return '';
    }

    var listEl = document.getElementById('doctorNotifications');
    var badgeEl = document.getElementById('doctorUnreadBadge');
    var markReadBtn = document.getElementById('markReadBtn');

    function updateUnread(delta) {
        if (!badgeEl) return;
        var current = parseInt(badgeEl.textContent || '0', 10) || 0;
        var next = Math.max(0, current + delta);
        badgeEl.textContent = String(next);
    }

    function prependNotification(n) {
        if (!listEl) return;
        var card = document.createElement('div');
        card.className = 'p-4 rounded-xl border border-[#00d1b2]/30 bg-[#00d1b2]/10';
        var safeBody = n.body ? n.body.replace(/</g, '&lt;').replace(/>/g, '&gt;') : '';
        var body = safeBody ? '<p class="text-gray-400 text-sm">' + safeBody + '</p>' : '';
        card.innerHTML = '<p class="text-white font-medium text-sm">' + (n.title || 'Notification') + '</p>' + body +
            '<p class="text-xs text-gray-500 mt-2">Just now</p>';
        listEl.prepend(card);
        updateUnread(1);
    }

    if (markReadBtn && config.markReadApiUrl) {
        markReadBtn.addEventListener('click', function(e) {
            e.preventDefault();
            fetch(config.markReadApiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({})
            }).then(function(r) {
                return r.json();
            }).then(function(data) {
                if (badgeEl) badgeEl.textContent = String(data.unread_count || 0);
                if (listEl) {
                    Array.prototype.forEach.call(listEl.children, function(el) {
                        el.classList.remove('border-[#00d1b2]/30', 'bg-[#00d1b2]/10');
                        el.classList.add('border-white/10', 'bg-white/5');
                    });
                }
            }).catch(function() {});
        });
    }

    var protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    var socket = new WebSocket(protocol + window.location.host + '/ws/doctor/notifications/');

    socket.onmessage = function(event) {
        try {
            var data = JSON.parse(event.data);
            if (data.type === 'doctor_notification' && data.notification) {
                var evType = data.notification.event_type || '';
                // Only show booking-level events in the notifications panel.
                // Chat message events (chat_started, message_received) are excluded
                // because their counts appear on the "Open Chat" button instead.
                if (evType === 'booking_created' || evType === 'booking_status') {
                    prependNotification(data.notification);
                }
            }
        } catch (err) {}
    };
})();

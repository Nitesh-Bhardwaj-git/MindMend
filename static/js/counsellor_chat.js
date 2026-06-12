(function() {
    var chatEl = document.getElementById('chatMessages');
    var chatInput = document.getElementById('chatInput');
    var chatForm = document.getElementById('chatForm');
    var csrfInput = chatForm ? chatForm.querySelector('input[name="csrfmiddlewaretoken"]') : null;
    var csrfToken = csrfInput ? csrfInput.value : '';
    var apiUrl = window.CHAT_CONFIG.apiUrl;
    var bookingId = window.CHAT_CONFIG.bookingId;
    var myUserId = window.CHAT_CONFIG.myUserId;
    var counsellorUserId = window.CHAT_CONFIG.counsellorUserId;
    var protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
    var socket = null;
    var latestMessageId = 0;
    var knownMessageIds = {};
    var pollingTimer = null;
    var pollInFlight = false;

    if (chatEl) {
        Array.prototype.forEach.call(chatEl.querySelectorAll('[data-message-id]'), function(node) {
            var id = Number(node.getAttribute('data-message-id') || 0);
            if (id > 0) {
                knownMessageIds[id] = true;
                if (id > latestMessageId) latestMessageId = id;
            }
        });
        chatEl.scrollTop = chatEl.scrollHeight;
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function removeEmptyState() {
        var empty = document.getElementById('emptyChatState');
        if (empty) empty.remove();
    }

    function appendMessage(m) {
        var msgId = Number(m.id || 0);
        if (msgId && knownMessageIds[msgId]) return;

        if (msgId) {
            knownMessageIds[msgId] = true;
            if (msgId > latestMessageId) latestMessageId = msgId;
        }

        var isMe = m.sender_id === myUserId;
        var role = m.sender_id === counsellorUserId ? ' (Counsellor)' : ' (Patient)';
        var div = document.createElement('div');
        div.className = 'flex ' + (isMe ? 'justify-end' : 'justify-start');
        if (msgId) div.setAttribute('data-message-id', String(msgId));

        div.innerHTML =
            '<div class="max-w-full sm:max-w-[85%] lg:max-w-[75%] rounded-3xl px-4 py-3 shadow-lg ' +
            (isMe ? 'bg-[#00d1b2] text-[#04111d]' : 'bg-white/5 text-white border border-white/10') +
            '">' +
            '<p class="text-xs opacity-75 mb-1">' + escapeHtml(m.sender) + role + '</p>' +
            '<p class="whitespace-pre-wrap break-words text-sm sm:text-base">' + escapeHtml(m.content) + '</p>' +
            '<p class="text-[11px] opacity-70 mt-2">' + new Date(m.created_at).toLocaleString() + '</p>' +
            '</div>';

        removeEmptyState();
        chatEl.appendChild(div);
        chatEl.scrollTop = chatEl.scrollHeight;
    }

    function startSocket() {
        socket = new WebSocket(protocol + window.location.host + '/ws/booking/' + bookingId + '/chat/');

        socket.onmessage = function(event) {
            try {
                var data = JSON.parse(event.data);
                if (data.type === 'chat_message' && data.message) {
                    appendMessage(data.message);
                } else if (data.type === 'chat_locked') {
                    alert(data.message || 'Session is completed. Chat disabled.');
                }
            } catch (err) {}
        };

        socket.onclose = function() {
            setTimeout(startSocket, 3000);
        };

        socket.onerror = function() {};
    }

    async function sendViaHttp(content) {
        var res = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ content: content })
        });

        if (!res.ok) return;
        var data = await res.json();
        if (data && data.message) appendMessage(data.message);
    }

    async function pollMessages() {
        if (pollInFlight) return;
        pollInFlight = true;

        try {
            var url = apiUrl + '?after_id=' + encodeURIComponent(String(latestMessageId || 0));
            var res = await fetch(url, { credentials: 'same-origin' });
            if (!res.ok) return;
            var data = await res.json();
            var list = (data && data.messages) ? data.messages : [];
            list.forEach(appendMessage);
        } catch (err) {
        } finally {
            pollInFlight = false;
        }
    }

    startSocket();
    pollMessages();
    pollingTimer = setInterval(pollMessages, 2000);

    if (chatForm) {
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            var content = (chatInput.value || '').trim();
            if (!content) return;

            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({ content: content }));
            } else {
                sendViaHttp(content);
            }

            chatInput.value = '';
        });
    }
})();

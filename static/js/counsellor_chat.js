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

    var lastDateLabel = null;

    if (chatEl) {
        Array.prototype.forEach.call(chatEl.querySelectorAll('[data-message-id]'), function(node) {
            var id = Number(node.getAttribute('data-message-id') || 0);
            if (id > 0) {
                knownMessageIds[id] = true;
                if (id > latestMessageId) latestMessageId = id;
            }
        });
        // Seed lastDateLabel from the last date separator already in DOM
        var separators = chatEl.querySelectorAll('[data-date-label]');
        if (separators.length > 0) {
            lastDateLabel = separators[separators.length - 1].getAttribute('data-date-label');
        }
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

    function formatTime(dateStr) {
        var d = new Date(dateStr);
        var h = d.getHours(), m = d.getMinutes();
        var ampm = h >= 12 ? 'PM' : 'AM';
        h = h % 12 || 12;
        return h + ':' + (m < 10 ? '0' : '') + m + ' ' + ampm;
    }

    function formatDateLabel(dateStr) {
        var d = new Date(dateStr);
        var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        return d.getDate() + ' ' + months[d.getMonth()] + ' ' + d.getFullYear();
    }

    function isToday(dateStr) {
        var d = new Date(dateStr), t = new Date();
        return d.getFullYear() === t.getFullYear() &&
               d.getMonth()    === t.getMonth()    &&
               d.getDate()     === t.getDate();
    }

    function makeDateSeparator(dateStr) {
        var label = formatDateLabel(dateStr);
        var sep = document.createElement('div');
        sep.setAttribute('data-date-label', label);
        sep.className = 'flex flex-col items-center gap-0.5 my-2';
        sep.innerHTML =
            '<div class="flex items-center gap-3 w-full">' +
            '<div class="flex-1 h-px bg-white/10"></div>' +
            '<span class="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-[11px] text-white/50 shrink-0">' + label + '</span>' +
            '<div class="flex-1 h-px bg-white/10"></div>' +
            '</div>' +
            (isToday(dateStr) ? '<span class="text-[10px] text-white/30">Today</span>' : '');
        return sep;
    }

    function appendMessage(m) {
        var msgId = Number(m.id || 0);
        if (msgId && knownMessageIds[msgId]) return;

        if (msgId) {
            knownMessageIds[msgId] = true;
            if (msgId > latestMessageId) latestMessageId = msgId;
        }

        var isMe = m.sender_id === myUserId;
        var timeStr = formatTime(m.created_at);

        // Insert date separator if day changed
        var dateLabel = formatDateLabel(m.created_at);
        if (dateLabel !== lastDateLabel) {
            lastDateLabel = dateLabel;
            removeEmptyState();
            chatEl.appendChild(makeDateSeparator(m.created_at));
        }

        var div = document.createElement('div');
        if (msgId) div.setAttribute('data-message-id', String(msgId));

        if (isMe) {
            // Own message — right-aligned, "You" label, teal bubble
            div.className = 'flex justify-end';
            div.innerHTML =
                '<div class="max-w-full sm:max-w-[85%] lg:max-w-[75%] rounded-2xl px-3 py-2 shadow-lg bg-[#00d1b2] text-[#04111d]">' +
                '<p class="whitespace-pre-wrap break-words text-sm sm:text-base">' + escapeHtml(m.content) + '</p>' +
                '<p class="text-[11px] opacity-60 mt-1 text-right">' + timeStr + '</p>' +
                '</div>';
        } else {
            // Other party — left-aligned, sender name label, dark bubble
            var senderLabel = escapeHtml(m.sender || 'Counsellor');
            div.className = 'flex justify-start items-end gap-2';
            div.innerHTML =
                '<div class="max-w-full sm:max-w-[85%] lg:max-w-[75%] rounded-2xl px-3 py-2 shadow-lg bg-white/5 text-white border border-white/10">' +
                '<p class="text-xs font-bold mb-0.5" style="color:rgba(0,209,178,0.8)">' + senderLabel + '</p>' +
                '<p class="whitespace-pre-wrap break-words text-sm sm:text-base">' + escapeHtml(m.content) + '</p>' +
                '<p class="text-[11px] opacity-50 mt-1 text-right">' + timeStr + '</p>' +
                '</div>';
        }

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

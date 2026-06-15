(function () {
  const form = document.getElementById('chatForm');
  const input = document.getElementById('messageInput');
  const messages = document.getElementById('chatMessages');
  const recs = document.getElementById('recommendations');
  const welcomeMsg = document.getElementById('welcomeMsg');
  const CHAT_STORE_KEY = 'mindmend_chats_v1';

  let sessionId = '';
  let currentChatId = '';

  function getTimeString() {
    const d = new Date();
    let h = d.getHours();
    const m = d.getMinutes();
    const am = h < 12;
    h = h % 12 || 12;
    return h + ':' + (m < 10 ? '0' : '') + m + (am ? ' am' : ' pm');
  }

  function loadChatStore() {
    try {
      return JSON.parse(localStorage.getItem(CHAT_STORE_KEY) || '[]');
    } catch (e) {
      return [];
    }
  }

  function saveChatStore(store) {
    try {
      localStorage.setItem(CHAT_STORE_KEY, JSON.stringify(store || []));
    } catch (e) {
      console.warn("localStorage is not available", e);
    }
  }

  function getBreathingOptIn() {
    try {
      return localStorage.getItem('mindmend_breathing_opt_in');
    } catch (e) {
      return null;
    }
  }

  function setBreathingOptIn(val) {
    try {
      localStorage.setItem('mindmend_breathing_opt_in', val);
    } catch (e) {
      console.warn("localStorage is not available for breathing opt in", e);
    }
  }

  function chatTitleFromText(text) {
    const t = (text || '').trim();
    if (!t) return 'New chat';
    if (t.length <= 28) return t;
    return t.slice(0, 28) + '...';
  }

  function renderHistory() {
    const list = document.getElementById('chatHistory');
    if (!list) return;

    list.innerHTML = '';
    const store = loadChatStore();

    if (!store.length) {
      list.innerHTML = '<div class="text-white/40 text-sm px-2">No chats yet.</div>';
      return;
    }

    const sorted = store.slice().sort(function (a, b) {
      const ap = a.pinned ? 1 : 0;
      const bp = b.pinned ? 1 : 0;
      if (ap !== bp) return bp - ap;

      const at = a.updated_at ? new Date(a.updated_at).getTime() : 0;
      const bt = b.updated_at ? new Date(b.updated_at).getTime() : 0;
      return bt - at;
    });

    sorted.forEach(function (chat) {
      const item = document.createElement('div');
      item.className = 'chat-history-item' + (chat.id === currentChatId ? ' active' : '');

      const openBtn = document.createElement('button');
      openBtn.type = 'button';
      openBtn.className = 'chat-history-open';

      const title = document.createElement('div');
      title.className = 'chat-history-title';
      title.textContent = chat.title || 'New chat';

      const meta = document.createElement('div');
      meta.className = 'chat-history-meta';

      if (chat.updated_at) {
        const d = new Date(chat.updated_at);
        meta.textContent = d.toLocaleDateString() + ' • ' + d.toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit'
        });
      }

      openBtn.appendChild(title);
      if (meta.textContent) openBtn.appendChild(meta);

      openBtn.addEventListener('click', function () {
        openChat(chat.id);
      });

      const menuBtn = document.createElement('button');
      menuBtn.type = 'button';
      menuBtn.className = 'chat-history-menu-btn';
      menuBtn.textContent = '⋯';

      const menu = document.createElement('div');
      menu.className = 'chat-history-menu';

      function closeMenus() {
        document.querySelectorAll('.chat-history-menu.open').forEach(function (el) {
          el.classList.remove('open');
        });
      }

      const shareBtn = document.createElement('button');
      shareBtn.type = 'button';
      shareBtn.textContent = 'Share';
      shareBtn.addEventListener('click', async function (e) {
        e.stopPropagation();
        closeMenus();

        const transcript = (chat.messages || []).map(function (m) {
          return (m.role === 'user' ? 'You: ' : 'MindMend: ') + m.text;
        }).join('\n');

        const text = (chat.title || 'Chat') + '\n\n' + transcript;

        if (navigator.share) {
          try {
            await navigator.share({ title: chat.title || 'Chat', text: text });
            return;
          } catch (err) {}
        }

        if (navigator.clipboard && navigator.clipboard.writeText) {
          try {
            await navigator.clipboard.writeText(text);
            alert('Chat copied to clipboard.');
          } catch (err) {
            prompt('Copy chat:', text);
          }
        } else {
          prompt('Copy chat:', text);
        }
      });

      const renameBtn = document.createElement('button');
      renameBtn.type = 'button';
      renameBtn.textContent = 'Rename';
      renameBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        closeMenus();

        const newTitle = prompt('Rename chat', chat.title || 'New chat');
        if (!newTitle) return;

        const storeNow = loadChatStore();
        const itemNow = storeNow.find(function (c) { return c.id === chat.id; });
        if (itemNow) {
          itemNow.title = newTitle.trim();
          saveChatStore(storeNow);
          renderHistory();
        }
      });

      const pinBtn = document.createElement('button');
      pinBtn.type = 'button';
      pinBtn.textContent = chat.pinned ? 'Unpin chat' : 'Pin chat';
      pinBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        closeMenus();

        const storeNow = loadChatStore();
        const itemNow = storeNow.find(function (c) { return c.id === chat.id; });
        if (itemNow) {
          itemNow.pinned = !itemNow.pinned;
          saveChatStore(storeNow);
          renderHistory();
        }
      });

      const deleteBtn = document.createElement('button');
      deleteBtn.type = 'button';
      deleteBtn.className = 'danger';
      deleteBtn.textContent = 'Delete';
      deleteBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        closeMenus();

        if (!confirm('Delete this chat?')) return;

        const storeNow = loadChatStore().filter(function (c) { return c.id !== chat.id; });
        saveChatStore(storeNow);

        if (currentChatId === chat.id) {
          startNewChat();
        } else {
          renderHistory();
        }
      });

      menu.appendChild(shareBtn);
      menu.appendChild(renameBtn);
      menu.appendChild(pinBtn);
      menu.appendChild(deleteBtn);

      menuBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (menu.classList.contains('open')) {
          menu.classList.remove('open');
        } else {
          closeMenus();
          menu.classList.add('open');
        }
      });

      item.appendChild(openBtn);
      item.appendChild(menuBtn);
      item.appendChild(menu);
      list.appendChild(item);
    });
  }

  document.addEventListener('click', function () {
    document.querySelectorAll('.chat-history-menu.open').forEach(function (el) {
      el.classList.remove('open');
    });
  });

  function updateEmptyStatePrompts() {
    const emptyState = document.getElementById('empty-state-prompts');
    if (emptyState) {
      const chatRowsCount = messages.querySelectorAll('.chat-row:not(#welcomeMsg)').length;
      if (chatRowsCount > 0) {
        emptyState.style.display = 'none';
      } else {
        emptyState.style.display = 'grid';
      }
    }
  }

  window.applyPromptTemplate = function(text) {
    const input = document.getElementById('messageInput');
    if (input) {
      input.value = text;
      const form = document.getElementById('chatForm');
      if (form) {
        form.requestSubmit();
      }
    }
  };

  function updateContextCount() {
    const el = document.getElementById('contextMsgCount');
    if (!el) return;
    const store = loadChatStore();
    const chat = store.find(function (c) { return c.id === currentChatId; });
    const count = chat && chat.messages ? chat.messages.length : 0;
    el.textContent = count + ' message' + (count !== 1 ? 's' : '');
  }

  function clearChatUI() {
    messages.querySelectorAll('.chat-row:not(#welcomeMsg)').forEach(function (el) {
      el.remove();
    });
    if (welcomeMsg) {
      welcomeMsg.style.display = '';
    }
    const emptyState = document.getElementById('empty-state-prompts');
    if (emptyState) {
      emptyState.style.display = 'grid';
    }
    recs.innerHTML = '';
    recs.classList.add('hidden');
    updateEmptyStatePrompts();
    updateContextCount();
  }

  function openChat(chatId) {
    const store = loadChatStore();
    const chat = store.find(function (c) { return c.id === chatId; });
    if (!chat) return;

    currentChatId = chat.id;
    sessionId = chat.session_id || '';
    
    messages.querySelectorAll('.chat-row:not(#welcomeMsg)').forEach(function (el) {
      el.remove();
    });

    if (welcomeMsg) welcomeMsg.style.display = 'none';

    (chat.messages || []).forEach(function (m) {
      addMsg(m.text, m.role === 'user');
    });

    renderHistory();
    updateEmptyStatePrompts();
    updateContextCount();
    messages.scrollTop = messages.scrollHeight;
  }

  function startNewChat() {
    currentChatId = 'c' + Math.random().toString(36).slice(2, 10);
    sessionId = '';
    clearChatUI();
    renderHistory();
    updateEmptyStatePrompts();
    updateContextCount();
  }

  function addMsg(text, isUser) {
    const row = document.createElement('div');
    row.className = 'chat-row ' + (isUser ? 'chat-row-user' : 'chat-row-bot');
    
    const emptyState = document.getElementById('empty-state-prompts');
    if (emptyState) emptyState.style.display = 'none';

    const sender = document.createElement('div');
    sender.className = 'chat-sender';
    sender.textContent = isUser ? 'You' : 'MindMend';

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    bubble.textContent = text;

    const time = document.createElement('span');
    time.className = 'chat-time';
    time.textContent = getTimeString();

    bubble.appendChild(time);

    const lastRow = messages.lastElementChild;
    const isConsecutive = lastRow && lastRow.classList.contains(isUser ? 'chat-row-user' : 'chat-row-bot') && lastRow.id !== 'welcomeMsg' && lastRow.id !== 'typingIndicator' && lastRow.id !== 'empty-state-prompts';
    if (isConsecutive) {
      row.style.marginTop = '4px';
      const lastBubble = lastRow.querySelector('.chat-bubble');
      if (lastBubble) {
        if (isUser) {
          lastBubble.style.borderBottomRightRadius = '20px';
          bubble.style.borderTopRightRadius = '6px';
        } else {
          lastBubble.style.borderBottomLeftRadius = '20px';
          bubble.style.borderTopLeftRadius = '6px';
        }
      }
    } else {
      row.appendChild(sender);
    }

    row.appendChild(bubble);
    messages.appendChild(row);
    messages.scrollTop = messages.scrollHeight;
    updateContextCount();
  }

  function addBotMsgWithTyping(text) {
    return new Promise(function (resolve) {
      const row = document.createElement('div');
      row.className = 'chat-row chat-row-bot';

      const sender = document.createElement('div');
      sender.className = 'chat-sender';
      sender.textContent = 'MindMend';

      const bubble = document.createElement('div');
      bubble.className = 'chat-bubble';

      const content = document.createElement('span');
      const time = document.createElement('span');
      time.className = 'chat-time';

      bubble.appendChild(content);
      bubble.appendChild(time);

      const lastRow = messages.lastElementChild;
      const isConsecutive = lastRow && lastRow.classList.contains('chat-row-bot') && lastRow.id !== 'welcomeMsg' && lastRow.id !== 'typingIndicator' && lastRow.id !== 'empty-state-prompts';
      if (isConsecutive) {
        row.style.marginTop = '4px';
        const lastBubble = lastRow.querySelector('.chat-bubble');
        if (lastBubble) {
          lastBubble.style.borderBottomLeftRadius = '20px';
          bubble.style.borderTopLeftRadius = '6px';
        }
      } else {
        row.appendChild(sender);
      }

      row.appendChild(bubble);
      messages.appendChild(row);
      messages.scrollTop = messages.scrollHeight;

      const fullText = text || '';
      let index = 0;
      const step = Math.max(1, Math.ceil(fullText.length / 70));

      const timer = setInterval(function () {
        index = Math.min(fullText.length, index + step);
        content.textContent = fullText.slice(0, index);
        messages.scrollTop = messages.scrollHeight;

        if (index >= fullText.length) {
          clearInterval(timer);
          time.textContent = getTimeString();
          updateContextCount();
          resolve();
        }
      }, 18);
    });
  }

  function addBreathingVideoBubble() {
    const row = document.createElement('div');
    row.className = 'chat-row chat-row-bot';

    const sender = document.createElement('div');
    sender.className = 'chat-sender';
    sender.textContent = 'MindMend';

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';

    const video = document.createElement('video');
    video.className = 'chat-video';
    video.autoplay = true;
    video.muted = true;
    video.loop = true;
    video.playsInline = true;
    video.controls = true;

    const source = document.createElement('source');
    source.src = '/static/videos/breathing.mp4';
    source.type = 'video/mp4';
    video.appendChild(source);

    bubble.appendChild(video);
    row.appendChild(sender);
    row.appendChild(bubble);
    messages.appendChild(row);
    messages.scrollTop = messages.scrollHeight;
  }

  function addBreathingConsentBubble() {
    const row = document.createElement('div');
    row.className = 'chat-row chat-row-bot';

    const sender = document.createElement('div');
    sender.className = 'chat-sender';
    sender.textContent = 'MindMend';

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    bubble.textContent = 'Want a short breathing exercise video?';

    const actions = document.createElement('div');
    actions.className = 'chat-actions';

    const yesBtn = document.createElement('button');
    yesBtn.type = 'button';
    yesBtn.className = 'chat-btn';
    yesBtn.textContent = 'Yes, show it';

    const noBtn = document.createElement('button');
    noBtn.type = 'button';
    noBtn.className = 'chat-btn';
    noBtn.textContent = 'No thanks';

    actions.appendChild(yesBtn);
    actions.appendChild(noBtn);
    bubble.appendChild(actions);
    row.appendChild(sender);
    row.appendChild(bubble);
    messages.appendChild(row);
    messages.scrollTop = messages.scrollHeight;

    yesBtn.addEventListener('click', function () {
      setBreathingOptIn('yes');
      row.remove();
      addBreathingVideoBubble();
    });

    noBtn.addEventListener('click', function () {
      setBreathingOptIn('no');
      row.remove();
    });
  }

  function showTyping() {
    const row = document.createElement('div');
    row.className = 'chat-row chat-typing';
    row.id = 'typingIndicator';
    row.innerHTML =
      '<div class="chat-sender">MindMend</div>' +
      '<div class="chat-bubble"><div class="chat-typing-dots"><span></span><span></span><span></span></div></div>';

    messages.appendChild(row);
    messages.scrollTop = messages.scrollHeight;
  }

  function hideTyping() {
    const el = document.getElementById('typingIndicator');
    if (el) el.remove();
  }

  (function setWelcomeTime() {
    const t = document.getElementById('welcomeTime');
    if (t) t.textContent = getTimeString();
  })();

  function showRecommendations(items) {
    recs.innerHTML = '';
    if (!items || items.length === 0) {
      recs.classList.add('hidden');
      return;
    }

    recs.classList.remove('hidden');

    items.forEach(function (r) {
      const card = document.createElement('div');
      card.className = 'recommendation-card' + (r.priority === 'urgent' ? ' urgent' : '');
      card.innerHTML = '<strong>' + r.title + '</strong><p class="mb-0 mt-1">' + r.content + '</p>';
      recs.appendChild(card);
    });
  }

  function getClientContext() {
    const now = new Date();
    let tz = '';

    try {
      tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    } catch (e) {
      tz = '';
    }

    return {
      client_time: now.toISOString(),
      client_tz_offset: now.getTimezoneOffset(),
      client_tz: tz
    };
  }

  // ---------- Guest Limit Modal ----------
  function showGuestLimitModal() {
    // Avoid showing duplicate modals
    if (document.getElementById('guestLimitModal')) return;

    const overlay = document.createElement('div');
    overlay.id = 'guestLimitModal';
    overlay.style.cssText = [
      'position:fixed', 'inset:0', 'z-index:9999',
      'display:flex', 'align-items:center', 'justify-content:center',
      'background:rgba(5,11,26,0.82)', 'backdrop-filter:blur(8px)',
      '-webkit-backdrop-filter:blur(8px)',
      'padding:1.5rem',
      'animation:fadeIn .25s ease'
    ].join(';');

    overlay.innerHTML = [
      '<style>',
      '@keyframes fadeIn{from{opacity:0;transform:scale(.96)}to{opacity:1;transform:scale(1)}}',
      '@keyframes slideUp{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:translateY(0)}}',
      '</style>',
      '<div style="',
        'max-width:420px;width:100%;',
        'background:linear-gradient(145deg,#0c1931,#081525);',
        'border:1px solid rgba(0,209,178,.22);',
        'border-radius:2rem;',
        'padding:2.5rem 2rem;',
        'text-align:center;',
        'box-shadow:0 32px 80px rgba(0,0,0,.55),0 0 0 1px rgba(0,209,178,.08);',
        'animation:slideUp .3s ease;',
        'position:relative',
      '">',
        '<div style="',
          'width:72px;height:72px;',
          'border-radius:50%;',
          'background:rgba(0,209,178,.08);',
          'border:2px solid rgba(0,209,178,.25);',
          'display:flex;align-items:center;justify-content:center;',
          'font-size:2rem;margin:0 auto 1.25rem;',
        '">🔒</div>',
        '<h2 style="color:#fff;font-size:1.4rem;font-weight:800;margin:0 0 .5rem;">Free Questions Used Up</h2>',
        '<p style="color:rgba(255,255,255,.55);font-size:.92rem;line-height:1.6;margin:0 0 .4rem;">',
          'You\'ve asked <strong style="color:#00d1b2;">3 free questions</strong>.',
        '</p>',
        '<p style="color:rgba(255,255,255,.45);font-size:.85rem;line-height:1.55;margin:0 0 2rem;">',
          'Create a free account to unlock <strong style="color:#fff;">unlimited chat</strong>, ',
          'personalised memory, saved history, mood tracking & more.',
        '</p>',
        '<div style="display:flex;flex-direction:column;gap:.75rem;">',
          '<a href="/register/" style="',
            'display:block;padding:.9rem 1.5rem;',
            'background:#00d1b2;color:#03120f;',
            'font-weight:800;font-size:.95rem;',
            'border-radius:1rem;text-decoration:none;',
            'transition:background .2s;',
          '" onmouseover="this.style.background=\'#00b39a\'" onmouseout="this.style.background=\'#00d1b2\'">',
            '✨ Create Free Account',
          '</a>',
          '<a href="/login/" style="',
            'display:block;padding:.9rem 1.5rem;',
            'background:rgba(255,255,255,.05);color:#fff;',
            'font-weight:600;font-size:.9rem;',
            'border:1px solid rgba(255,255,255,.12);',
            'border-radius:1rem;text-decoration:none;',
            'transition:background .2s;',
          '" onmouseover="this.style.background=\'rgba(255,255,255,.1)\'" onmouseout="this.style.background=\'rgba(255,255,255,.05)\'">',
            'Already have an account? Log In',
          '</a>',
        '</div>',
        '<p style="margin-top:1.25rem;font-size:.75rem;color:rgba(255,255,255,.25);">Free — no credit card required</p>',
      '</div>'
    ].join('');

    document.body.appendChild(overlay);

    // Lock the chat input to prevent further typing
    if (input) {
      input.disabled = true;
      input.placeholder = 'Sign up to keep chatting...';
    }
    const submitBtn = form ? form.querySelector('button[type="submit"]') : null;
    if (submitBtn) submitBtn.disabled = true;
    const micButton = document.getElementById('micBtn');
    if (micButton) micButton.disabled = true;
  }

  // Check on page load — if the session already reached the limit, lock the UI.
  // We pass `isAuthenticated` from the template via MINDMEND_CONFIG.
  (function checkInitialGuestLimit() {
    const cfg = window.MINDMEND_CONFIG || {};
    if (cfg.isAuthenticated) return; // logged-in users are never limited
    // We'll count from localStorage messages for this session
    // The real enforcement happens server-side; this is just a UI hint after reload.
  })();

  const newChatBtn = document.getElementById('newChatBtn');
  if (newChatBtn) {
    newChatBtn.addEventListener('click', function () {
      startNewChat();
    });
  }

  const micBtn = document.getElementById('micBtn');
  const micStatus = document.getElementById('micStatus');
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let isListening = false;

  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-IN';

    recognition.onresult = function (e) {
      const transcript = Array.from(e.results).map(function (r) {
        return r[0].transcript;
      }).join('').trim();

      if (transcript) input.value = transcript;
    };

    recognition.onend = function () {
      isListening = false;
      micBtn.classList.remove('bg-red-100', 'border-red-400');
      micStatus.classList.add('hidden');
    };

    recognition.onerror = function () {
      isListening = false;
      micBtn.classList.remove('bg-red-100', 'border-red-400');
      micStatus.classList.add('hidden');
    };

    micBtn.addEventListener('click', function () {
      if (isListening) {
        recognition.stop();
        return;
      }

      const langEl = document.getElementById('chatLangSelect');
      recognition.lang = (langEl && langEl.value === 'hi') ? 'hi-IN' : 'en-IN';

      input.focus();
      recognition.start();
      isListening = true;
      micBtn.classList.add('bg-red-100', 'border-red-400');
      micStatus.classList.remove('hidden');
      micStatus.textContent = 'Listening... speak now.';
    });
  } else {
    micBtn.style.display = 'none';
  }

  startNewChat();

  form.addEventListener('submit', async function (e) {
    e.preventDefault();

    const msg = input.value.trim();
    if (!msg) return;

    addMsg(msg, true);
    input.value = '';

    const btn = form.querySelector('button[type="submit"]');
    if (btn) btn.disabled = true;

    showTyping();

    try {
      let store = loadChatStore();
      let current = store.find(function (c) { return c.id === currentChatId; });

      if (!current) {
        current = {
          id: currentChatId,
          title: chatTitleFromText(msg),
          session_id: sessionId || '',
          messages: [],
          updated_at: new Date().toISOString()
        };
        store.unshift(current);
      }

      current.messages = current.messages || [];
      current.messages.push({ role: 'user', text: msg });

      if (!current.title || current.title === 'New chat') {
        current.title = chatTitleFromText(msg);
      }

      current.updated_at = new Date().toISOString();
      saveChatStore(store);
      renderHistory();

      const langEl = document.getElementById('chatLangSelect');
      const langVal = langEl ? langEl.value : 'en';

      const res = await fetch(window.MINDMEND_CONFIG.chatApiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(Object.assign({
          message: msg,
          session_id: sessionId,
          lang: langVal
        }, getClientContext()))
      });

      // Handle guest question limit
      if (res.status === 403) {
        const errData = await res.json().catch(function() { return {}; });
        hideTyping();
        if (btn) btn.disabled = false;
        if (errData.error === 'guest_limit_reached') {
          showGuestLimitModal();
          return;
        }
      }

      const data = await res.json();

      if (data.session_id) {
        sessionId = data.session_id;

        const storeAfter = loadChatStore();
        const currentAfter = storeAfter.find(function (c) { return c.id === currentChatId; });

        if (currentAfter) {
          currentAfter.session_id = sessionId;
          saveChatStore(storeAfter);
        }
      }

      hideTyping();
      await addBotMsgWithTyping(data.response || data.reply || 'Sorry, something went wrong.');

      if (data.recommendations && data.recommendations.length) {
        data.recommendations.forEach(function (r) {
          const row = document.createElement('div');
          row.className = 'chat-row chat-row-bot';

          const sender = document.createElement('div');
          sender.className = 'chat-sender';
          sender.textContent = 'MindMend';

          const bubble = document.createElement('div');
          bubble.className = 'chat-bubble';
          bubble.innerHTML = '<strong>' + r.title + '</strong><br>' + (r.content || '');

          const lastRow = messages.lastElementChild;
          const isConsecutive = lastRow && lastRow.classList.contains('chat-row-bot') && lastRow.id !== 'welcomeMsg' && lastRow.id !== 'typingIndicator' && lastRow.id !== 'empty-state-prompts';
          if (isConsecutive) {
            row.style.marginTop = '4px';
            const lastBubble = lastRow.querySelector('.chat-bubble');
            if (lastBubble) {
              lastBubble.style.borderBottomLeftRadius = '20px';
              bubble.style.borderTopLeftRadius = '6px';
            }
          } else {
            row.appendChild(sender);
          }

          row.appendChild(bubble);
          messages.appendChild(row);
        });

        messages.scrollTop = messages.scrollHeight;
        updateContextCount();
      }

      if (data.recommendations && data.recommendations.some(function (r) { return r.type === 'breathing'; })) {
        const pref = getBreathingOptIn();

        if (pref === 'yes') {
          addBreathingVideoBubble();
        } else if (pref !== 'no') {
          addBreathingConsentBubble();
        }
      }

      showRecommendations([]);

      const storeAfterMsg = loadChatStore();
      const currentMsg = storeAfterMsg.find(function (c) { return c.id === currentChatId; });

      if (currentMsg) {
        currentMsg.messages = currentMsg.messages || [];
        currentMsg.messages.push({ role: 'assistant', text: data.response || data.reply || 'Sorry, something went wrong.' });
        currentMsg.updated_at = new Date().toISOString();
        saveChatStore(storeAfterMsg);
      }
    } catch (err) {
      hideTyping();
      await addBotMsgWithTyping("Frontend Diagnostic Error: " + (err.message || err.toString()) + " | Please tell Antigravity what this says.");
    }

    if (btn) btn.disabled = false;
  });

  // Live Hindi keyboard transliteration
  input.addEventListener('keyup', async function(e) {
    if (e.key === ' ') {
      const langEl = document.getElementById('chatLangSelect');
      if (langEl && langEl.value === 'hi') {
        const cursor = input.selectionStart;
        const textUpToCursor = input.value.substring(0, cursor);
        const match = textUpToCursor.match(/([a-zA-Z]+)(\s+)$/);
        if (match) {
          const word = match[1];
          const spaces = match[2];
          try {
            const res = await fetch(window.MINDMEND_CONFIG.transliterateApiUrl, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({text: word, lang: 'hi'})
            });
            const data = await res.json();
            if (data.result) {
               const startSegment = textUpToCursor.substring(0, textUpToCursor.length - match[0].length);
               const newSegment = startSegment + data.result + spaces;
               const endSegment = input.value.substring(cursor);
               input.value = newSegment + endSegment;
               input.selectionStart = input.selectionEnd = newSegment.length;
            }
          } catch(err) {
            console.error("Transliteration failed", err);
          }
        }
      }
    }
  });
})();

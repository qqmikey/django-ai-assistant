(function () {
  function el(tag, attrs, html) {
    var e = document.createElement(tag);
    if (attrs) {
      for (var k in attrs) e.setAttribute(k, attrs[k]);
    }
    if (html != null) e.innerHTML = html;
    return e;
  }

  function getCookie(name) {
    var v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return v ? v.pop() : '';
  }

  function fetchJSON(url, opts) {
    var o = Object.assign(
      { credentials: 'same-origin', headers: { 'Content-Type': 'application/json', Accept: 'application/json' } },
      opts || {}
    );
    var method = (o.method || 'GET').toUpperCase();
    if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') o.headers['X-CSRFToken'] = getCookie('csrftoken');
    return fetch(url, o).then(function (r) {
      if (r.status === 204) return { ok: true, status: 204 };
      var ct = r.headers.get('content-type') || '';
      if (ct.indexOf('application/json') !== -1) return r.json();
      return r.text().then(function (t) {
        return { error: true, text: t, status: r.status };
      });
    });
  }

  function getApiBasePath() {
    var base = String(window.DJANGO_AI_ADMIN_BASE_PATH || '/ai-assistant');
    if (!base) base = '/ai-assistant';
    if (base.charAt(0) !== '/') base = '/' + base;
    base = base.replace(/\/+$/, '');
    return base || '/ai-assistant';
  }

  function apiUrl(path) {
    var p = String(path || '').replace(/^\/+/, '');
    return getApiBasePath() + '/' + p;
  }

  function normalizeEnvelope(res) {
    if (res && res.type) return res;
    if (res && res.summary != null) {
      return {
        type: 'answer',
        message: String(res.summary || ''),
        data: {
          summary: res.summary,
          result: res.result,
          truncated: !!res.truncated,
          explanation: res.explanation || '',
          code: res.code || '',
        },
        meta: {},
      };
    }
    if (res && res.error) {
      return {
        type: 'error',
        message: String(res.error || 'Error'),
        data: { error: String(res.error || 'Error'), code: res.code || '' },
        meta: {},
      };
    }
    if (res && res.text) {
      return { type: 'error', message: String(res.text), data: { error: res.text }, meta: {} };
    }
    return { type: 'error', message: 'Unexpected response', data: {}, meta: {} };
  }

  function isDark() {
    try {
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return true;
    } catch (e) {}
    try {
      var bg = getComputedStyle(document.body).backgroundColor || '';
      var m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
      if (m) {
        var r = +m[1], g = +m[2], b = +m[3];
        var l = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
        return l < 0.5;
      }
    } catch (e2) {}
    return false;
  }

  function theme() {
    var dark = isDark();
    return dark
      ? { bg: '#111', fg: '#eee', border: '#333', btnBg: '#222', btnFg: '#eee', inputBg: '#111', inputFg: '#eee' }
      : { bg: '#fff', fg: '#000', border: '#eee', btnBg: '#fff', btnFg: '#000', inputBg: '#fff', inputFg: '#000' };
  }

  function appendBubble(role, text, details) {
    var box = document.getElementById('dj-ai-admin-history');
    if (!box) return;
    var wrap = el('div', { class: 'dj-ai-row ' + (role === 'user' ? 'right' : 'left') });
    var bubble = el('div', { class: 'dj-ai-bubble ' + role });
    bubble.textContent = String(text || '');
    wrap.appendChild(bubble);
    box.appendChild(wrap);

    if (!details) return;
    var dwrap = el('div', { class: 'dj-ai-row ' + (role === 'user' ? 'right' : 'left') });
    var container = el('div');

    if (details.interpretation) {
      var btnI = el('button', { class: 'dj-ai-details-btn' }, 'Interpretation');
      var panelI = el('div', { class: 'dj-ai-details', 'data-open': '0' });
      panelI.style.display = 'none';
      var interp = el('div', { class: 'dj-ai-expl' });
      interp.textContent = String(details.interpretation);
      panelI.appendChild(interp);
      btnI.onclick = function () {
        var openI = panelI.getAttribute('data-open') === '1';
        panelI.style.display = openI ? 'none' : 'block';
        panelI.setAttribute('data-open', openI ? '0' : '1');
        btnI.textContent = openI ? 'Interpretation' : 'Hide interpretation';
      };
      container.appendChild(btnI);
      container.appendChild(panelI);
    }

    if (typeof details.result !== 'undefined') {
      var btnR = el('button', { class: 'dj-ai-details-btn' }, 'Result');
      var panelR = el('div', { class: 'dj-ai-details', 'data-open': '0' });
      panelR.style.display = 'none';
      var preR = el('pre', { class: 'dj-ai-result' });
      try {
        preR.textContent = JSON.stringify(details.result, null, 2);
      } catch (e) {
        preR.textContent = String(details.result);
      }
      panelR.appendChild(preR);
      btnR.onclick = function () {
        var open = panelR.getAttribute('data-open') === '1';
        panelR.style.display = open ? 'none' : 'block';
        panelR.setAttribute('data-open', open ? '0' : '1');
        btnR.textContent = open ? 'Result' : 'Hide result';
      };
      container.appendChild(btnR);
      container.appendChild(panelR);
    }

    if (details.explanation) {
      var btnE = el('button', { class: 'dj-ai-details-btn' }, 'Explanation');
      var panelE = el('div', { class: 'dj-ai-details', 'data-open': '0' });
      panelE.style.display = 'none';
      var expl = el('div', { class: 'dj-ai-expl' });
      expl.textContent = String(details.explanation);
      panelE.appendChild(expl);
      btnE.onclick = function () {
        var openE = panelE.getAttribute('data-open') === '1';
        panelE.style.display = openE ? 'none' : 'block';
        panelE.setAttribute('data-open', openE ? '0' : '1');
        btnE.textContent = openE ? 'Explanation' : 'Hide explanation';
      };
      container.appendChild(btnE);
      container.appendChild(panelE);
    }

    if (details.code) {
      var btnC = el('button', { class: 'dj-ai-details-btn' }, 'Code');
      var panelC = el('div', { class: 'dj-ai-details', 'data-open': '0' });
      panelC.style.display = 'none';
      var preC = el('pre', { class: 'dj-ai-code' });
      preC.textContent = String(details.code);
      panelC.appendChild(preC);
      btnC.onclick = function () {
        var openC = panelC.getAttribute('data-open') === '1';
        panelC.style.display = openC ? 'none' : 'block';
        panelC.setAttribute('data-open', openC ? '0' : '1');
        btnC.textContent = openC ? 'Code' : 'Hide code';
      };
      container.appendChild(btnC);
      container.appendChild(panelC);
    }

    dwrap.appendChild(container);
    box.appendChild(dwrap);
  }

  function appendErrorBubble(errorText, code) {
    appendBubble('assistant', String(errorText || 'Error'), null);
    if (!code) return;
    var box = document.getElementById('dj-ai-admin-history');
    if (!box) return;
    var dwrap = el('div', { class: 'dj-ai-row left' });
    var btn = el('button', { class: 'dj-ai-details-btn' }, 'Details');
    var panel = el('div', { class: 'dj-ai-details', 'data-open': '0' });
    panel.style.display = 'none';
    var pre = el('pre', { class: 'dj-ai-code' });
    pre.textContent = String(code);
    panel.appendChild(pre);
    btn.onclick = function () {
      var open = panel.getAttribute('data-open') === '1';
      panel.style.display = open ? 'none' : 'block';
      panel.setAttribute('data-open', open ? '0' : '1');
      btn.textContent = open ? 'Details' : 'Hide details';
    };
    dwrap.appendChild(btn);
    dwrap.appendChild(panel);
    box.appendChild(dwrap);
  }

  function appendOptions(options) {
    if (!Array.isArray(options) || !options.length) return;
    var box = document.getElementById('dj-ai-admin-history');
    if (!box) return;
    var wrap = el('div', { class: 'dj-ai-row left' });
    var holder = el('div');
    options.forEach(function (opt) {
      var label = String((opt && (opt.label || opt.model || opt.id)) || '');
      if (!label) return;
      var btn = el('button', { class: 'dj-ai-details-btn' }, label);
      btn.style.marginRight = '6px';
      btn.onclick = function () {
        var ta = document.getElementById('dj-ai-admin-input');
        if (!ta) return;
        ta.value = label;
        sendMessage();
      };
      holder.appendChild(btn);
    });
    wrap.appendChild(holder);
    box.appendChild(wrap);
  }

  function handleEnvelope(envelope) {
    var box = document.getElementById('dj-ai-admin-history');
    if (!box) return;
    var type = envelope.type;
    var data = envelope.data || {};
    var meta = envelope.meta || {};

    if (type === 'answer') {
      appendBubble('assistant', envelope.message || data.summary || '', {
        result: data.result,
        explanation: data.explanation,
        code: data.code,
        interpretation: data.interpretation || meta.interpretation,
      });
    } else if (type === 'clarification') {
      appendBubble('assistant', envelope.message || data.question || 'Please clarify your request.', null);
      appendOptions(data.options || []);
    } else if (type === 'out_of_scope') {
      appendBubble('assistant', envelope.message || 'This question is outside current project data scope.', null);
      if (data.how_to_rephrase) appendBubble('assistant', 'How to rephrase: ' + data.how_to_rephrase, null);
      if (Array.isArray(data.candidate_models) && data.candidate_models.length) {
        appendBubble('assistant', 'Possible entities: ' + data.candidate_models.join(', '), null);
      }
    } else if (type === 'error') {
      appendErrorBubble(data.error || envelope.message || 'Error', data.code || '');
    } else {
      appendBubble('assistant', envelope.message || 'Unexpected response', null);
    }
    box.scrollTop = box.scrollHeight;
  }

  function renderHistoryItem(msg) {
    if (!msg) return;
    if (msg.role === 'user') {
      appendBubble('user', msg.content, null);
      return;
    }
    var meta = msg.meta || {};
    var type = meta.response_type;
    if (!type && meta.error) type = 'error';
    if (!type && (typeof meta.result !== 'undefined' || meta.code || meta.explanation)) type = 'answer';
    if (type === 'error') {
      appendErrorBubble(meta.error || msg.content || 'Error', meta.code || '');
      return;
    }
    if (type === 'clarification') {
      appendBubble('assistant', msg.content, null);
      appendOptions(meta.options || []);
      return;
    }
    if (type === 'out_of_scope') {
      appendBubble('assistant', msg.content, null);
      return;
    }
    appendBubble('assistant', msg.content, {
      result: meta.result,
      explanation: meta.explanation,
      code: meta.code,
      interpretation: meta.interpretation,
    });
  }

  var currentChatId = null;
  var currentChatTitle = 'AI Assistant';
  var draftChatMode = false;
  var requestInFlight = false;
  var typingIndicatorNode = null;

  function isDrawerOpen() {
    var drawer = document.getElementById('dj-ai-admin-drawer');
    return !!drawer && drawer.style.transform !== 'translateX(100%)';
  }

  function updateHeaderToggleState() {
    var btn = document.getElementById('dj-ai-admin-toggle');
    if (!btn) return;
    var open = isDrawerOpen();
    btn.textContent = open ? 'Close AI' : 'Open AI';
    if (open) btn.setAttribute('data-open', '1');
    else btn.setAttribute('data-open', '0');
  }

  function setRequestState(isBusy) {
    requestInFlight = !!isBusy;
    var input = document.getElementById('dj-ai-admin-input');
    var sendBtn = document.getElementById('dj-ai-admin-send');
    if (input) input.disabled = requestInFlight;
    if (sendBtn) {
      sendBtn.disabled = requestInFlight;
      sendBtn.textContent = requestInFlight ? 'Thinking...' : 'Send';
      sendBtn.style.opacity = requestInFlight ? '0.72' : '1';
      sendBtn.style.cursor = requestInFlight ? 'wait' : 'pointer';
    }
  }

  function showTypingIndicator() {
    if (typingIndicatorNode) return;
    var box = document.getElementById('dj-ai-admin-history');
    if (!box) return;
    var wrap = el('div', { class: 'dj-ai-row left' });
    var bubble = el('div', { class: 'dj-ai-bubble assistant typing' });
    var dots = el('div', { class: 'dj-ai-typing-dots' });
    dots.appendChild(el('span'));
    dots.appendChild(el('span'));
    dots.appendChild(el('span'));
    bubble.appendChild(dots);
    wrap.appendChild(bubble);
    box.appendChild(wrap);
    typingIndicatorNode = wrap;
    box.scrollTop = box.scrollHeight;
  }

  function hideTypingIndicator() {
    if (!typingIndicatorNode) return;
    try {
      typingIndicatorNode.remove();
    } catch (e) {
      if (typingIndicatorNode.parentNode) typingIndicatorNode.parentNode.removeChild(typingIndicatorNode);
    }
    typingIndicatorNode = null;
  }

  function parseTimestamp(value) {
    var ts = Date.parse(value || '');
    if (isNaN(ts)) return null;
    return ts;
  }

  function formatRelativeTime(value) {
    var ts = parseTimestamp(value);
    if (ts == null) return '';
    var now = Date.now();
    var diffSec = Math.max(0, Math.floor((now - ts) / 1000));
    if (diffSec < 45) return 'just now';
    if (diffSec < 3600) return Math.floor(diffSec / 60) + 'm ago';
    if (diffSec < 86400) return Math.floor(diffSec / 3600) + 'h ago';
    if (diffSec < 7 * 86400) return Math.floor(diffSec / 86400) + 'd ago';
    return Math.floor(diffSec / (7 * 86400)) + 'w ago';
  }

  function refreshChats() {
    fetchJSON(apiUrl('api/chats')).then(function (items) {
      var list = document.getElementById('dj-ai-admin-chat-list');
      if (!list) return;
      list.innerHTML = '';
      if (!Array.isArray(items)) {
        var err = el('div', null, 'Failed to load chats');
        err.style.color = '#b00';
        list.appendChild(err);
        return;
      }

      items = items.slice().sort(function (a, b) {
        var ta = parseTimestamp((a && a.updated_at) || (a && a.created_at)) || 0;
        var tb = parseTimestamp((b && b.updated_at) || (b && b.created_at)) || 0;
        return tb - ta;
      });

      if (!items.length) {
        var empty = el('div', { class: 'dj-ai-chat-empty' });
        empty.textContent = 'No chats yet. Start a new one.';
        list.appendChild(empty);
      }

      items.forEach(function (it) {
        var text = (it && it.title) || ('Chat ' + it.id);
        if (it.id === currentChatId) currentChatTitle = text;
        var b = el('button', {
          class: 'dj-ai-chat-card',
          type: 'button',
        });
        var main = el('div', { class: 'dj-ai-chat-main' });
        var title = el('div', { class: 'dj-ai-chat-title' });
        title.textContent = text;
        var sub = el('div', { class: 'dj-ai-chat-sub' });
        sub.textContent = (it && it.current_topic && String(it.current_topic).split('.').pop()) || 'Conversation';
        main.appendChild(title);
        main.appendChild(sub);
        var time = el('div', { class: 'dj-ai-chat-time' });
        time.textContent = formatRelativeTime((it && it.updated_at) || (it && it.created_at));
        b.appendChild(main);
        b.appendChild(time);
        b.onclick = function () {
          draftChatMode = false;
          currentChatId = it.id;
          currentChatTitle = text;
          toggleListMode(false);
          loadHistory();
        };
        list.appendChild(b);
      });
      toggleListMode(currentChatId == null && !draftChatMode);
    });
  }

  function createChat() {
    draftChatMode = true;
    currentChatId = null;
    currentChatTitle = 'New chat';
    hideTypingIndicator();
    setRequestState(false);
    var box = document.getElementById('dj-ai-admin-history');
    if (box) {
      box.innerHTML = '';
      box.scrollTop = 0;
    }
    toggleListMode(false);
    var input = document.getElementById('dj-ai-admin-input');
    if (input) input.focus();
  }

  function ensureActiveChat() {
    if (currentChatId) return Promise.resolve(currentChatId);
    return fetchJSON(apiUrl('api/chats'), {
      method: 'POST',
      body: JSON.stringify({ title: currentChatTitle || 'New chat' }),
    }).then(function (chat) {
      if (!chat || !chat.id) throw new Error('chat_create_failed');
      currentChatId = chat.id;
      currentChatTitle = (chat && chat.title) || currentChatTitle || 'New chat';
      draftChatMode = false;
      toggleListMode(false);
      return chat.id;
    });
  }

  function deleteCurrentChat() {
    if (!currentChatId) return;
    var chatId = currentChatId;
    var chatTitle = currentChatTitle || 'this chat';
    var confirmed = window.confirm('Delete "' + chatTitle + '"?\nThis action cannot be undone.');
    if (!confirmed) return;

    fetchJSON(apiUrl('api/chats/' + chatId), { method: 'DELETE' }).then(function (res) {
      if (res && res.error) {
        appendBubble('assistant', 'Failed to delete chat. Please try again.', null);
        return;
      }
      draftChatMode = false;
      currentChatId = null;
      currentChatTitle = 'AI Assistant';
      hideTypingIndicator();
      setRequestState(false);
      var box = document.getElementById('dj-ai-admin-history');
      if (box) box.innerHTML = '';
      toggleListMode(true);
      refreshChats();
    }).catch(function () {
      appendBubble('assistant', 'Failed to delete chat. Please try again.', null);
    });
  }

  function loadHistory() {
    fetchJSON(apiUrl('api/chats/' + currentChatId)).then(function (res) {
      var box = document.getElementById('dj-ai-admin-history');
      if (!box) return;
      draftChatMode = false;
      hideTypingIndicator();
      setRequestState(false);
      if (res && res.title) currentChatTitle = String(res.title);
      toggleListMode(false);
      box.innerHTML = '';
      if (!res || !Array.isArray(res.messages)) {
        appendBubble('assistant', 'Failed to load history', null);
        return;
      }
      (res.messages || []).forEach(renderHistoryItem);
      box.scrollTop = box.scrollHeight;
    });
  }

  function sendMessage() {
    if (requestInFlight) return;
    if (!currentChatId && !draftChatMode) return;
    var t = document.getElementById('dj-ai-admin-input');
    var v = ((t && t.value) || '').trim();
    if (!v) return;
    if (t) t.value = '';
    appendBubble('user', v, null);
    var box = document.getElementById('dj-ai-admin-history');
    if (box) box.scrollTop = box.scrollHeight;
    setRequestState(true);
    showTypingIndicator();

    ensureActiveChat().then(function (chatId) {
      return fetchJSON(apiUrl('api/chats/' + chatId + '/message'), {
        method: 'POST',
        body: JSON.stringify({ content: v }),
      });
    }).then(function (res) {
      hideTypingIndicator();
      setRequestState(false);
      handleEnvelope(normalizeEnvelope(res));
      refreshChats();
    }).catch(function () {
      hideTypingIndicator();
      setRequestState(false);
      appendBubble('assistant', 'Something went wrong while waiting for a response. Please try again.', null);
    });
  }

  function toggleListMode(showList) {
    var chats = document.getElementById('dj-ai-admin-chats');
    var back = document.getElementById('dj-ai-back');
    var del = document.getElementById('dj-ai-delete');
    var newBtn = document.getElementById('dj-ai-new');
    var title = document.getElementById('dj-ai-head-title');
    var history = document.getElementById('dj-ai-admin-history');
    var form = document.querySelector('#dj-ai-admin-body > div:last-child');
    if (!chats || !back) return;
    chats.style.display = showList ? 'block' : 'none';
    back.style.display = showList ? 'none' : 'inline-flex';
    if (del) del.style.display = (!showList && !!currentChatId) ? 'inline-flex' : 'none';
    if (newBtn) newBtn.style.display = showList ? 'inline-block' : 'none';
    if (title) title.textContent = showList ? 'AI Assistant' : (currentChatTitle || 'Chat');
    if (history) history.style.display = showList ? 'none' : 'block';
    if (form) form.style.display = showList ? 'none' : 'block';
  }

  function openDrawer() {
    var drawer = document.getElementById('dj-ai-admin-drawer');
    if (!drawer) {
      drawer = el('div', { id: 'dj-ai-admin-drawer' });
      var th = theme();
      drawer.style.position = 'fixed';
      drawer.style.top = '0';
      drawer.style.right = '0';
      drawer.style.height = '100%';
      drawer.style.width = '420px';
      drawer.style.background = th.bg;
      drawer.style.color = th.fg;
      drawer.style.boxShadow = '0 0 12px rgba(0,0,0,0.2)';
      drawer.style.borderLeft = '1px solid ' + th.border;
      drawer.style.transform = 'translateX(100%)';
      drawer.style.transition = 'transform .2s ease';
      drawer.style.zIndex = '9999';

      var head = el('div', { class: 'dj-ai-head' });
      head.style.padding = '12px';
      head.style.fontWeight = '600';
      head.style.color = th.fg;
      var title = el('div', { id: 'dj-ai-head-title', class: 'dj-ai-head-title' }, 'AI Assistant');
      var controls = el('div');
      var deleteBtn = el('button', { id: 'dj-ai-delete', class: 'dj-ai-topbtn dj-ai-icon-btn dj-ai-delete-btn', 'aria-label': 'Delete chat', type: 'button' }, '🗑');
      deleteBtn.style.display = 'none';
      deleteBtn.onclick = deleteCurrentChat;
      var backBtn = el('button', { id: 'dj-ai-back', class: 'dj-ai-topbtn dj-ai-icon-btn dj-ai-close-btn', 'aria-label': 'Back to chats', type: 'button' }, '✕');
      backBtn.style.display = 'none';
      backBtn.onclick = function () {
        draftChatMode = false;
        currentChatId = null;
        currentChatTitle = 'AI Assistant';
        hideTypingIndicator();
        setRequestState(false);
        toggleListMode(true);
      };
      var newBtn = el('button', { id: 'dj-ai-new', class: 'dj-ai-topbtn' }, '+ New Chat');
      newBtn.onclick = createChat;
      controls.appendChild(deleteBtn);
      controls.appendChild(backBtn);
      controls.appendChild(newBtn);
      head.appendChild(title);
      head.appendChild(controls);

      var body = el('div', { id: 'dj-ai-admin-body' });
      var chats = el('div', { id: 'dj-ai-admin-chats' });
      chats.style.padding = '8px';
      chats.style.borderBottom = '1px solid ' + th.border;
      chats.appendChild(el('div', { id: 'dj-ai-admin-chat-list' }));

      var history = el('div', { id: 'dj-ai-admin-history' });
      history.style.padding = '8px';
      history.style.overflow = 'auto';

      var form = el('div', { class: 'dj-ai-input-wrap' });
      form.style.width = '100%';
      form.style.padding = '8px';
      form.style.background = th.bg;
      form.style.borderTop = '1px solid ' + th.border;
      var composer = el('div', { class: 'dj-ai-composer' });
      composer.style.background = th.inputBg;
      composer.style.color = th.inputFg;
      composer.style.border = '1px solid ' + th.border;
      var inp = el('textarea', { id: 'dj-ai-admin-input' });
      var send = el('button', { id: 'dj-ai-admin-send' }, 'Send');
      send.onclick = sendMessage;
      composer.appendChild(inp);
      composer.appendChild(send);
      form.appendChild(composer);

      body.appendChild(chats);
      body.appendChild(history);
      body.appendChild(form);
      drawer.appendChild(head);
      drawer.appendChild(body);
      document.body.appendChild(drawer);
    }
    drawer.style.transform = 'translateX(0%)';
    updateHeaderToggleState();
    refreshChats();
  }

  function toggleDrawer() {
    var drawer = document.getElementById('dj-ai-admin-drawer');
    if (!drawer || drawer.style.transform === 'translateX(100%)') openDrawer();
    else {
      drawer.style.transform = 'translateX(100%)';
      updateHeaderToggleState();
    }
  }

  function ensureHeaderToggle() {
    if (document.getElementById('dj-ai-admin-toggle')) return;
    var btn = el('button', { id: 'dj-ai-admin-toggle', type: 'button' }, 'Open AI');
    btn.addEventListener('click', toggleDrawer);
    var userTools = document.getElementById('user-tools');
    if (userTools) {
      userTools.insertBefore(btn, userTools.firstChild);
      updateHeaderToggleState();
      return;
    }
    var header = document.getElementById('header');
    if (header) {
      header.appendChild(btn);
      updateHeaderToggleState();
      return;
    }
    var branding = document.getElementById('site-name');
    if (branding && branding.parentNode) {
      branding.parentNode.appendChild(btn);
      updateHeaderToggleState();
    }
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      var ta = document.getElementById('dj-ai-admin-input');
      if (ta && document.activeElement === ta) {
        e.preventDefault();
        sendMessage();
      }
    }
  });

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ensureHeaderToggle);
  else ensureHeaderToggle();
})();

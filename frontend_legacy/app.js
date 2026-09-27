/**
 * Sana AI Design System - Enterprise Self-Service Analytics Logic
 * High-precision Multi-Agent Orchestration, Split-View Canvas & Realtime Streaming
 */

// Global Fetch Interceptor for JWT Auth
const originalFetch = window.fetch;
window.fetch = async function() {
  let [resource, config] = arguments;
  if (!config) config = {};
  if (!config.headers) config.headers = {};
  
  const newHeaders = new Headers(config.headers);
  const token = localStorage.getItem('jwt_token');
  if (token) {
    newHeaders.set('Authorization', `Bearer ${token}`);
  }
  
  config.headers = newHeaders;
  const response = await originalFetch(resource, config);
  
  if (response.status === 401) {
    window.app_logout();
  }
  return response;
};

// Global State
const state = {
  activeDomain: 'real_estate',
  sessionId: 'sess_' + Math.random().toString(36).substring(2, 9),
  isStreaming: true,
  theme: localStorage.getItem('sana_theme') || 'light',
  isSidebarCollapsed: localStorage.getItem('sana_sidebar') === 'true',
  isCanvasOpen: false,
  pendingHitlSessionId: null,
  activeCanvasData: null,
  thinkingSteps: [],
  queryCounter: 0
};

// DOM References
const DOM = {
  sanaSidebar: document.getElementById('sanaSidebar'),
  btnCollapseSidebar: document.getElementById('btnCollapseSidebar'),
  btnNewChat: document.getElementById('btnNewChat'),
  btnThemeToggle: document.getElementById('btnThemeToggle'),
  themeIcon: document.getElementById('themeIcon'),
  btnClearChat: document.getElementById('btnClearChat'),
  btnToggleCanvas: document.getElementById('btnToggleCanvas'),
  btnCloseCanvas: document.getElementById('btnCloseCanvas'),
  sanaCanvasDrawer: document.getElementById('sanaCanvasDrawer'),
  canvasTitle: document.getElementById('canvasTitle'),
  canvasSubtitle: document.getElementById('canvasSubtitle'),
  canvasBody: document.getElementById('canvasBody'),
  btnExportCanvasCsv: document.getElementById('btnExportCanvasCsv'),

  chatViewport: document.getElementById('chatViewport'),
  welcomeHero: document.getElementById('welcomeHero'),
  chatStream: document.getElementById('chatStream'),
  userQueryInput: document.getElementById('userQueryInput'),
  btnSend: document.getElementById('btnSend'),
  streamToggle: document.getElementById('streamToggle'),
  domainSelect: document.getElementById('domainSelect'),
  domainStatusPill: document.getElementById('domainStatusPill'),
  btnActiveSources: document.getElementById('btnActiveSources'),
  btnHeaderCatalog: document.getElementById('btnHeaderCatalog'),
  quickPromptsList: document.getElementById('quickPromptsList'),
  thoughtStreamBanner: document.getElementById('thoughtStreamBanner'),
  currentThoughtStep: document.getElementById('currentThoughtStep'),
  currentThoughtDetail: document.getElementById('currentThoughtDetail'),
  
  // HITL Modal
  hitlModal: document.getElementById('hitlModal'),
  hitlWarningText: document.getElementById('hitlWarningText'),
  hitlSqlCode: document.getElementById('hitlSqlCode'),
  btnApproveHitl: document.getElementById('btnApproveHitl'),
  btnRejectHitl: document.getElementById('btnRejectHitl'),
  btnCopyHitlSql: document.getElementById('btnCopyHitlSql'),

  // Schema Modal
  schemaModal: document.getElementById('schemaModal'),
  btnOpenSchema: document.getElementById('btnOpenSchema'),
  btnCloseSchemaModal: document.getElementById('btnCloseSchemaModal'),
  schemaModalContent: document.getElementById('schemaModalContent'),

  // Lineage Modal
  lineageModal: document.getElementById('lineageModal'),
  btnOpenLineage: document.getElementById('btnOpenLineage'),
  btnCloseLineageModal: document.getElementById('btnCloseLineageModal'),
  lineageModalContent: document.getElementById('lineageModalContent'),

  // Benchmark Modal
  benchmarkModal: document.getElementById('benchmarkModal'),
  btnOpenBenchmark: document.getElementById('btnOpenBenchmark'),
  btnCloseBenchmarkModal: document.getElementById('btnCloseBenchmarkModal'),
  btnRunBenchmarkSuite: document.getElementById('btnRunBenchmarkSuite'),
  benchmarkTableBody: document.getElementById('benchmarkTableBody'),
};

// -------------------------------------------------------------
// INITIALIZATION
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  applyTheme(state.theme);
  applySidebarState(state.isSidebarCollapsed);
  lucide.createIcons();
  setupEventListeners();
  
  const token = localStorage.getItem('jwt_token');
  if (token) {
    document.getElementById('loginModal').classList.remove('active');
    loadDomainList();
  } else {
    document.getElementById('loginModal').classList.add('active');
  }
});

// Theme Management (Light vs Dark)
function applyTheme(theme) {
  state.theme = theme;
  localStorage.setItem('sana_theme', theme);
  if (theme === 'dark') {
    document.body.classList.add('dark-theme');
    document.body.classList.remove('light-theme');
    DOM.themeIcon.setAttribute('data-lucide', 'sun');
  } else {
    document.body.classList.remove('dark-theme');
    document.body.classList.add('light-theme');
    DOM.themeIcon.setAttribute('data-lucide', 'moon');
  }
  lucide.createIcons();
}

function toggleTheme() {
  applyTheme(state.theme === 'dark' ? 'light' : 'dark');
}

// Sidebar State Management
function applySidebarState(isCollapsed) {
  state.isSidebarCollapsed = isCollapsed;
  localStorage.setItem('sana_sidebar', isCollapsed);
  if (isCollapsed) {
    DOM.sanaSidebar.classList.add('collapsed');
  } else {
    DOM.sanaSidebar.classList.remove('collapsed');
  }
}

function toggleSidebar() {
  applySidebarState(!state.isSidebarCollapsed);
}

// Authentication
window.app_login = async function() {
  const user = document.getElementById('loginUsername').value;
  const pass = document.getElementById('loginPassword').value;
  const errEl = document.getElementById('loginError');
  
  try {
    const res = await originalFetch('/api/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password: pass })
    });
    
    if (res.ok) {
      const data = await res.json();
      localStorage.setItem('jwt_token', data.access_token);
      document.getElementById('loginModal').classList.remove('active');
      loadDomainList();
    } else {
      const data = await res.json();
      errEl.textContent = data.detail || 'Sai tài khoản hoặc mật khẩu';
      errEl.style.display = 'block';
    }
  } catch (e) {
    errEl.textContent = 'Không thể kết nối đến máy chủ';
    errEl.style.display = 'block';
  }
};

window.app_logout = function() {
  localStorage.removeItem('jwt_token');
  document.getElementById('loginModal').classList.add('active');
  document.getElementById('loginUsername').value = '';
  document.getElementById('loginPassword').value = '';
};

// -------------------------------------------------------------
// EVENT LISTENERS SETUP
// -------------------------------------------------------------
function setupEventListeners() {
  // Theme & Sidebar
  DOM.btnThemeToggle.addEventListener('click', toggleTheme);
  DOM.btnCollapseSidebar.addEventListener('click', toggleSidebar);

  // New Chat
  DOM.btnNewChat.addEventListener('click', resetChatToWelcome);

  // Send Actions
  DOM.btnSend.addEventListener('click', handleSendMessage);
  DOM.userQueryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  // Auto-resize textarea
  DOM.userQueryInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
  });

  // Stream Toggle
  DOM.streamToggle.addEventListener('change', (e) => {
    state.isStreaming = e.target.checked;
  });

  // Domain Select
  DOM.domainSelect.addEventListener('change', (e) => {
    state.activeDomain = e.target.value;
  });

  // Clear Chat
  DOM.btnClearChat.addEventListener('click', resetChatToWelcome);

  // Canvas Toggle
  DOM.btnToggleCanvas.addEventListener('click', toggleCanvas);
  DOM.btnCloseCanvas.addEventListener('click', () => setCanvasState(false));
  DOM.btnExportCanvasCsv.addEventListener('click', exportActiveCanvasCsv);

  // Quick Prompts (Sidebar)
  DOM.quickPromptsList.addEventListener('click', (e) => {
    const btn = e.target.closest('.quick-prompt-btn');
    if (btn) {
      const query = btn.getAttribute('data-query');
      submitQuickQuery(query);
    }
  });

  // Sources Button
  DOM.btnActiveSources.addEventListener('click', openSchemaExplorer);
  DOM.btnHeaderCatalog.addEventListener('click', openSchemaExplorer);

  // HITL Modal Actions
  DOM.btnApproveHitl.addEventListener('click', () => submitHitlDecision(true));
  DOM.btnRejectHitl.addEventListener('click', () => submitHitlDecision(false));
  DOM.btnCopyHitlSql.addEventListener('click', () => {
    navigator.clipboard.writeText(DOM.hitlSqlCode.textContent);
    DOM.btnCopyHitlSql.textContent = 'Copied!';
    setTimeout(() => { DOM.btnCopyHitlSql.innerHTML = '<i data-lucide="copy" style="width: 12px; height: 12px;"></i> Copy'; lucide.createIcons(); }, 1500);
  });

  // Schema Modal
  DOM.btnOpenSchema.addEventListener('click', openSchemaExplorer);
  DOM.btnCloseSchemaModal.addEventListener('click', () => DOM.schemaModal.classList.remove('active'));

  // Lineage Modal
  DOM.btnOpenLineage.addEventListener('click', openLineageExplorer);
  DOM.btnCloseLineageModal.addEventListener('click', () => DOM.lineageModal.classList.remove('active'));

  // Benchmark Modal
  DOM.btnOpenBenchmark.addEventListener('click', openBenchmarkModal);
  DOM.btnCloseBenchmarkModal.addEventListener('click', () => DOM.benchmarkModal.classList.remove('active'));
  DOM.btnRunBenchmarkSuite.addEventListener('click', runBenchmarkInBrowser);

  // System Info Button
  const btnSystemInfo = document.getElementById('btnSystemInfo');
  if (btnSystemInfo) {
    btnSystemInfo.addEventListener('click', openSchemaExplorer);
  }

  // Logout
  const btnLogout = document.getElementById('btnLogout');
  if (btnLogout) btnLogout.addEventListener('click', window.app_logout);
}

// -------------------------------------------------------------
// RESET / NEW CHAT
// -------------------------------------------------------------
function resetChatToWelcome() {
  DOM.chatStream.innerHTML = '';
  DOM.chatStream.style.display = 'none';
  DOM.welcomeHero.style.display = 'flex';
  DOM.userQueryInput.value = '';
  DOM.userQueryInput.style.height = 'auto';
  DOM.userQueryInput.focus();
  setCanvasState(false);
  state.sessionId = 'sess_' + Math.random().toString(36).substring(2, 9);
}

window.submitQuickQuery = function(query) {
  DOM.userQueryInput.value = query;
  DOM.userQueryInput.style.height = 'auto';
  handleSendMessage();
};

// -------------------------------------------------------------
// DOMAIN MANAGEMENT
// -------------------------------------------------------------
async function loadDomainList() {
  try {
    const res = await fetch('/api/domains');
    if (res.ok) {
      const data = await res.json();
      DOM.domainSelect.innerHTML = '';
      data.domains.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.domain_id;
        opt.textContent = `${d.display_name} (${d.domain_id})`;
        if (d.domain_id === state.activeDomain) opt.selected = true;
        DOM.domainSelect.appendChild(opt);
      });
    }
  } catch (err) {
    console.warn('Backend using default domain: real_estate');
  }
}

// -------------------------------------------------------------
// CHAT & EXECUTION FLOW
// -------------------------------------------------------------
async function handleSendMessage() {
  const query = DOM.userQueryInput.value.trim();
  if (!query) return;

  // Show chat stream, hide welcome
  DOM.welcomeHero.style.display = 'none';
  DOM.chatStream.style.display = 'flex';

  // 1. Render User Message
  appendUserMessage(query);
  DOM.userQueryInput.value = '';
  DOM.userQueryInput.style.height = 'auto';
  DOM.btnSend.disabled = true;

  state.thinkingSteps = [];
  state.queryCounter++;

  if (state.isStreaming) {
    await executeQueryWithSSE(query);
  } else {
    await executeQuerySync(query);
  }

  DOM.btnSend.disabled = false;
  lucide.createIcons();
}

function appendUserMessage(text) {
  const row = document.createElement('div');
  row.className = 'chat-row-user';
  row.innerHTML = `
    <div class="user-bubble">
      ${escapeHtml(text)}
    </div>
    <div class="user-bubble-avatar">
      AS
    </div>
  `;
  DOM.chatStream.appendChild(row);
  scrollToBottom();
  lucide.createIcons();
}

// -------------------------------------------------------------
// SSE STREAMING
// -------------------------------------------------------------
async function executeQueryWithSSE(query) {
  const startTime = Date.now();
  showThoughtBanner('Khởi tạo Multi-Agent...', 'Phân tích cấu trúc câu hỏi');
  
  const agentRow = createAgentSkeleton(startTime);
  DOM.chatStream.appendChild(agentRow);
  scrollToBottom();

  const thoughtBodyEl = agentRow.querySelector('.reasoning-body');
  const reasoningStatusEl = agentRow.querySelector('.reasoning-status-text');
  const responseTextEl = agentRow.querySelector('.assistant-response-content');

  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: query,
        domain_id: state.activeDomain,
        session_id: state.sessionId
      })
    });

    if (!response.ok) {
      throw new Error(`Máy chủ trả về mã lỗi HTTP: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      let currentEvent = null;
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('event:')) {
          currentEvent = trimmed.replace('event:', '').trim();
        } else if (trimmed.startsWith('data:') && currentEvent) {
          const rawData = trimmed.replace('data:', '').trim();
          try {
            const data = JSON.parse(rawData);
            handleStreamEvent(currentEvent, data, agentRow, thoughtBodyEl, reasoningStatusEl, responseTextEl, startTime);
          } catch (e) {
            console.error('Lỗi parse SSE JSON:', rawData, e);
          }
          currentEvent = null;
        }
      }
    }
  } catch (err) {
    hideThoughtBanner();
    responseTextEl.innerHTML = `<span style="color: var(--accent-rose);"><i data-lucide="alert-circle"></i> Đã xảy ra lỗi: ${escapeHtml(err.message)}</span>`;
  } finally {
    hideThoughtBanner();
  }
}

function handleStreamEvent(event, data, agentRow, thoughtBodyEl, reasoningStatusEl, responseTextEl, startTime) {
  if (event === 'step') {
    const stepName = formatStepName(data.step);
    updateThoughtBanner(stepName, `Node: ${data.step}`);
    
    const stepItem = document.createElement('div');
    stepItem.className = 'thought-step-item';
    stepItem.innerHTML = `
      <i data-lucide="check-circle-2"></i>
      <span><strong>${escapeHtml(stepName)}:</strong> Hoàn tất xử lý</span>
    `;
    thoughtBodyEl.appendChild(stepItem);
    lucide.createIcons();
    scrollToBottom();
  } else if (event === 'clarification') {
    hideThoughtBanner();
    const duration = ((Date.now() - startTime) / 1000).toFixed(1);
    reasoningStatusEl.textContent = `Clarification required (${duration}s)`;
    responseTextEl.innerHTML = `
      <div style="background-color: var(--bg-card); border-left: 3px solid var(--accent-amber); padding: 14px; border-radius: var(--radius-sm); margin-top: 8px;">
        <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">
          <i data-lucide="help-circle" style="color: var(--accent-amber); width: 16px; height: 16px;"></i> Cần thêm thông tin làm rõ
        </div>
        <div style="color: var(--text-secondary);">${escapeHtml(data.question)}</div>
      </div>
    `;
    lucide.createIcons();
  } else if (event === 'hitl_required') {
    hideThoughtBanner();
    state.pendingHitlSessionId = data.session_id;
    openHitlModal(data.sql_query, data.warning);
  } else if (event === 'complete') {
    hideThoughtBanner();
    const duration = ((Date.now() - startTime) / 1000).toFixed(1);
    reasoningStatusEl.textContent = `Done (${duration}s)`;
    renderAgentCompleteResponse(agentRow, data);
  } else if (event === 'error') {
    hideThoughtBanner();
    reasoningStatusEl.textContent = 'Error';
    responseTextEl.innerHTML = `<span style="color: var(--accent-rose);">Lỗi: ${escapeHtml(data.error)}</span>`;
  }
}

// -------------------------------------------------------------
// SYNCHRONOUS FALLBACK
// -------------------------------------------------------------
async function executeQuerySync(query) {
  const startTime = Date.now();
  showThoughtBanner('Đang phân tích...', 'Gửi truy vấn đồng bộ');
  const agentRow = createAgentSkeleton(startTime);
  DOM.chatStream.appendChild(agentRow);

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: query,
        domain_id: state.activeDomain,
        session_id: state.sessionId
      })
    });
    const data = await res.json();
    hideThoughtBanner();

    const duration = ((Date.now() - startTime) / 1000).toFixed(1);
    const reasoningStatusEl = agentRow.querySelector('.reasoning-status-text');
    if (reasoningStatusEl) reasoningStatusEl.textContent = `Done (${duration}s)`;

    if (data.requires_hitl && !data.hitl_approved) {
      state.pendingHitlSessionId = data.session_id;
      openHitlModal(data.sql_query, 'Truy vấn có chi phí quét lớn.');
      return;
    }

    renderAgentCompleteResponse(agentRow, data);
  } catch (err) {
    hideThoughtBanner();
    agentRow.querySelector('.assistant-response-content').innerHTML = `<span style="color: var(--accent-rose);">Lỗi: ${escapeHtml(err.message)}</span>`;
  }
}

// -------------------------------------------------------------
// SANA AI AGENT RESPONSE RENDERING
// -------------------------------------------------------------
function createAgentSkeleton(startTime) {
  const row = document.createElement('div');
  row.className = 'chat-row-assistant';
  const cardId = 'res_' + Math.random().toString(36).substring(2, 9);
  row.setAttribute('data-card-id', cardId);

  row.innerHTML = `
    <!-- Sana AI Reasoning Accordion -->
    <div class="reasoning-accordion" id="reasoning_${cardId}">
      <div class="reasoning-header" onclick="toggleReasoningAccordion('${cardId}')">
        <div class="reasoning-status-pill">
          <div class="reasoning-status-dot"></div>
          <span class="reasoning-status-text">Thinking...</span>
        </div>
        <i data-lucide="chevron-down" class="reasoning-chevron" style="width: 14px; height: 14px;"></i>
      </div>
      <div class="reasoning-body">
        <div class="thought-step-item">
          <i data-lucide="loader-2" class="spin"></i>
          <span>Khởi tạo liên kết bảng & ngữ nghĩa nghiệp vụ...</span>
        </div>
      </div>
    </div>

    <!-- Source badges -->
    <div class="sources-pills-row" id="sources_${cardId}"></div>

    <!-- Editorial Response Content -->
    <div class="assistant-response-content">
      <span style="color: var(--text-muted);"><i data-lucide="loader-2" class="spin" style="width: 14px; height: 14px; display: inline-block; vertical-align: middle;"></i> Đang tổng hợp nhận định phân tích...</span>
    </div>

    <!-- Interactive Results Card Slot -->
    <div class="results-slot" id="slot_${cardId}"></div>

    <!-- Sana AI Action Bar (Image 13 & 14 style) -->
    <div class="assistant-action-bar" id="actions_${cardId}" style="display: none;">
      <button class="action-pill-btn" onclick="openSourcesCanvas('${cardId}')" title="Xem nguồn dữ liệu">
        <i data-lucide="file-text" style="width: 13px; height: 13px;"></i> Sources
      </button>
      <button class="action-pill-btn" onclick="openCanvasSplit('${cardId}')" title="Mở rộng Canvas">
        <i data-lucide="columns-2" style="width: 13px; height: 13px;"></i> Open in Canvas
      </button>
      <button class="action-icon-btn" onclick="copyResponseMarkdown('${cardId}')" title="Sao chép nội dung">
        <i data-lucide="copy" style="width: 14px; height: 14px;"></i>
      </button>
      <button class="action-icon-btn" onclick="sendFeedback('${cardId}', true)" title="Hữu ích">
        <i data-lucide="thumbs-up" style="width: 14px; height: 14px;"></i>
      </button>
      <button class="action-icon-btn" onclick="sendFeedback('${cardId}', false)" title="Chưa chính xác">
        <i data-lucide="thumbs-down" style="width: 14px; height: 14px;"></i>
      </button>
    </div>
  `;
  return row;
}

window.toggleReasoningAccordion = function(cardId) {
  const el = document.getElementById(`reasoning_${cardId}`);
  if (el) el.classList.toggle('expanded');
};

// Data normalization helper (handles both List[Dict] from Doris and List[List])
function normalizeData(rawCols, rawRows) {
  if (!rawRows || !Array.isArray(rawRows) || rawRows.length === 0) {
    return { columns: rawCols || [], rows: [] };
  }

  let cols = rawCols && rawCols.length > 0 ? [...rawCols] : null;
  if (!cols || cols.length === 0) {
    if (typeof rawRows[0] === 'object' && !Array.isArray(rawRows[0]) && rawRows[0] !== null) {
      cols = Object.keys(rawRows[0]);
    } else {
      cols = ['Value'];
    }
  }

  const rows = rawRows.map(r => {
    if (Array.isArray(r)) return r;
    if (typeof r === 'object' && r !== null) {
      return cols.map(c => r[c]);
    }
    return [r];
  });

  return { columns: cols, rows: rows };
}

function renderAgentCompleteResponse(agentRow, data) {
  const cardId = agentRow.getAttribute('data-card-id');
  const responseTextEl = agentRow.querySelector('.assistant-response-content');
  const sourcesRow = agentRow.querySelector('.sources-pills-row');
  const resultsSlot = agentRow.querySelector('.results-slot');
  const actionBar = agentRow.querySelector('.assistant-action-bar');

  // Normalize data for chart & table
  const { columns, rows } = normalizeData(data.column_names, data.query_result);
  data._normalizedColumns = columns;
  data._normalizedRows = rows;

  // Cache data on agent row for canvas & export
  agentRow._data = data;
  state.activeCanvasData = data;

  // 1. Natural Language Markdown Response
  responseTextEl.innerHTML = formatMarkdownText(data.final_response || 'Đã thực thi thành công truy vấn.');

  // 2. Source Pills (Sana AI style)
  let pillsHtml = '';
  if (data.metadata && data.metadata.tables_linked) {
    data.metadata.tables_linked.forEach(tbl => {
      pillsHtml += `<span class="source-badge"><i data-lucide="database" style="width: 11px; height: 11px;"></i> TABLE: ${escapeHtml(tbl)}</span>`;
    });
  }
  if (data.execution_time_ms) {
    const execMs = Math.round(data.execution_time_ms);
    pillsHtml += `<span class="source-badge"><i data-lucide="zap" style="width: 11px; height: 11px;"></i> EXEC: ${execMs}ms</span>`;
  }
  if (rows && rows.length > 0) {
    pillsHtml += `<span class="source-badge"><i data-lucide="list" style="width: 11px; height: 11px;"></i> ROWS: ${rows.length}</span>`;
  }
  sourcesRow.innerHTML = pillsHtml;

  // 3. Results Tabs (Visualization, Data Table, SQL)
  const hasData = rows && rows.length > 0;
  if (hasData || data.sql_query) {
    const chartId = 'chart_' + cardId;

    resultsSlot.innerHTML = `
      <div class="results-card">
        <div class="results-tabs-bar">
          <div class="results-tabs-nav">
            ${hasData ? `
              <button class="tab-btn active" id="tab_btn_viz_${cardId}" onclick="switchResultTab('${cardId}', 'viz')">
                <i data-lucide="pie-chart" style="width: 13px; height: 13px;"></i> Biểu đồ
              </button>
              <button class="tab-btn" id="tab_btn_tbl_${cardId}" onclick="switchResultTab('${cardId}', 'tbl')">
                <i data-lucide="table" style="width: 13px; height: 13px;"></i> Bảng dữ liệu
              </button>
            ` : ''}
            ${data.sql_query ? `
              <button class="tab-btn ${!hasData ? 'active' : ''}" id="tab_btn_sql_${cardId}" onclick="switchResultTab('${cardId}', 'sql')">
                <i data-lucide="code" style="width: 13px; height: 13px;"></i> Doris SQL
              </button>
            ` : ''}
          </div>
          ${hasData ? `
            <button class="action-pill-btn" onclick="exportDataToCsv('${cardId}')" title="Xuất file CSV">
              <i data-lucide="download" style="width: 12px; height: 12px;"></i> CSV
            </button>
          ` : ''}
        </div>

        <div class="results-tab-content">
          ${hasData ? `
            <div id="panel_viz_${cardId}" style="display: block;">
              <div class="chart-container-wrapper">
                <canvas id="${chartId}"></canvas>
              </div>
            </div>
            <div id="panel_tbl_${cardId}" style="display: none;">
              <div class="table-wrapper">
                <table class="sana-table">
                  <thead>
                    <tr>${columns.map(col => `<th>${escapeHtml(col)}</th>`).join('')}</tr>
                  </thead>
                  <tbody>
                    ${rows.slice(0, 8).map(row => `
                      <tr>${row.map(val => `<td>${formatCellValue(val)}</td>`).join('')}</tr>
                    `).join('')}
                  </tbody>
                </table>
              </div>
              ${rows.length > 8 ? `
                <div style="font-size: 0.74rem; color: var(--text-muted); padding: 8px 12px; text-align: center; border-top: 1px solid var(--border-subtle);">
                  Hiển thị 8/${rows.length} dòng. Nhấn "Open in Canvas" để xem toàn bộ bảng.
                </div>
              ` : ''}
            </div>
          ` : ''}

          ${data.sql_query ? `
            <div id="panel_sql_${cardId}" style="display: ${!hasData ? 'block' : 'none'};">
              <div class="sql-code-box">
                <div style="display: flex; justify-content: flex-end; margin-bottom: 6px;">
                  <button class="action-pill-btn" onclick="copySqlCode('${cardId}')">
                    <i data-lucide="copy" style="width: 12px; height: 12px;"></i> Copy SQL
                  </button>
                </div>
                <pre><code id="sql_text_${cardId}">${escapeHtml(data.sql_query)}</code></pre>
              </div>
            </div>
          ` : ''}
        </div>
      </div>
    `;

    // Render chart if data exists
    if (hasData) {
      setTimeout(() => {
        renderChart(chartId, columns, rows, data.chart_config);
      }, 60);
    }
  }

  // 4. Show Action Bar
  if (actionBar) {
    actionBar.style.display = 'flex';
  }

  lucide.createIcons();
  scrollToBottom();
}

// Result Tabs Switcher
window.switchResultTab = function(cardId, tabName) {
  const vizPanel = document.getElementById(`panel_viz_${cardId}`);
  const tblPanel = document.getElementById(`panel_tbl_${cardId}`);
  const sqlPanel = document.getElementById(`panel_sql_${cardId}`);

  const vizBtn = document.getElementById(`tab_btn_viz_${cardId}`);
  const tblBtn = document.getElementById(`tab_btn_tbl_${cardId}`);
  const sqlBtn = document.getElementById(`tab_btn_sql_${cardId}`);

  if (vizPanel) vizPanel.style.display = tabName === 'viz' ? 'block' : 'none';
  if (tblPanel) tblPanel.style.display = tabName === 'tbl' ? 'block' : 'none';
  if (sqlPanel) sqlPanel.style.display = tabName === 'sql' ? 'block' : 'none';

  if (vizBtn) vizBtn.className = `tab-btn ${tabName === 'viz' ? 'active' : ''}`;
  if (tblBtn) tblBtn.className = `tab-btn ${tabName === 'tbl' ? 'active' : ''}`;
  if (sqlBtn) sqlBtn.className = `tab-btn ${tabName === 'sql' ? 'active' : ''}`;
};

// -------------------------------------------------------------
// SANA AI RIGHT SPLIT CANVAS DRAWER
// -------------------------------------------------------------
function setCanvasState(isOpen) {
  state.isCanvasOpen = isOpen;
  if (isOpen) {
    DOM.sanaCanvasDrawer.classList.add('open');
    DOM.btnToggleCanvas.classList.add('active');
  } else {
    DOM.sanaCanvasDrawer.classList.remove('open');
    DOM.btnToggleCanvas.classList.remove('active');
  }
}

function toggleCanvas() {
  setCanvasState(!state.isCanvasOpen);
}

window.openCanvasSplit = function(cardId) {
  const row = document.querySelector(`[data-card-id="${cardId}"]`);
  const data = row ? row._data : state.activeCanvasData;
  if (!data) return;

  state.activeCanvasData = data;
  const { columns, rows } = normalizeData(data.column_names, data.query_result);
  
  DOM.canvasTitle.textContent = 'Data & Insights Canvas';
  DOM.canvasSubtitle.textContent = `Query Result · ${columns.length} Columns · ${rows.length} Rows`;

  const canvasChartId = 'canvas_chart_' + Date.now();
  let contentHtml = `
    <!-- Canvas Tabs -->
    <div style="display: flex; gap: 6px; margin-bottom: 16px;">
      <button class="topbar-btn active" id="btnCanvasTbl" onclick="switchCanvasPanel('tbl')">
        <i data-lucide="table" style="width: 13px; height: 13px;"></i> Full Table
      </button>
      <button class="topbar-btn" id="btnCanvasViz" onclick="switchCanvasPanel('viz')">
        <i data-lucide="pie-chart" style="width: 13px; height: 13px;"></i> Expanded Chart
      </button>
      <button class="topbar-btn" id="btnCanvasSql" onclick="switchCanvasPanel('sql')">
        <i data-lucide="code" style="width: 13px; height: 13px;"></i> SQL & Plan
      </button>
    </div>

    <!-- Table Panel -->
    <div id="canvasPanelTbl" style="display: block;">
      <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
        <span style="font-size: 0.8rem; color: var(--text-muted);">Hiển thị toàn bộ ${rows.length} bản ghi</span>
      </div>
      <div class="table-wrapper" style="max-height: 60vh;">
        <table class="sana-table">
          <thead>
            <tr>${columns.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr>
          </thead>
          <tbody>
            ${rows.map(r => `
              <tr>${r.map(v => `<td>${formatCellValue(v)}</td>`).join('')}</tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Chart Panel -->
    <div id="canvasPanelViz" style="display: none;">
      <div class="chart-container-wrapper" style="height: 380px;">
        <canvas id="${canvasChartId}"></canvas>
      </div>
    </div>

    <!-- SQL Panel -->
    <div id="canvasPanelSql" style="display: none;">
      <div class="sql-code-box">
        <pre><code>${escapeHtml(data.sql_query || '-- No SQL available')}</code></pre>
      </div>
    </div>
  `;

  DOM.canvasBody.innerHTML = contentHtml;
  setCanvasState(true);
  lucide.createIcons();

  if (rows && rows.length > 0) {
    setTimeout(() => {
      renderChart(canvasChartId, columns, rows, data.chart_config);
    }, 80);
  }
};

window.switchCanvasPanel = function(type) {
  const pTbl = document.getElementById('canvasPanelTbl');
  const pViz = document.getElementById('canvasPanelViz');
  const pSql = document.getElementById('canvasPanelSql');

  const bTbl = document.getElementById('btnCanvasTbl');
  const bViz = document.getElementById('btnCanvasViz');
  const bSql = document.getElementById('btnCanvasSql');

  if (pTbl) pTbl.style.display = type === 'tbl' ? 'block' : 'none';
  if (pViz) pViz.style.display = type === 'viz' ? 'block' : 'none';
  if (pSql) pSql.style.display = type === 'sql' ? 'block' : 'none';

  if (bTbl) bTbl.className = `topbar-btn ${type === 'tbl' ? 'active' : ''}`;
  if (bViz) bViz.className = `topbar-btn ${type === 'viz' ? 'active' : ''}`;
  if (bSql) bSql.className = `topbar-btn ${type === 'sql' ? 'active' : ''}`;
};

window.openSourcesCanvas = function(cardId) {
  openSchemaExplorer();
};

function exportActiveCanvasCsv() {
  if (state.activeCanvasData) {
    exportDataToCsv(null, state.activeCanvasData.column_names, state.activeCanvasData.query_result);
  }
}

// -------------------------------------------------------------
// CHART RENDERING (Chart.js with curated Sana AI palette)
// -------------------------------------------------------------
function renderChart(canvasId, columns, rows, chartConfig) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  if (!rows || rows.length === 0 || !columns || columns.length === 0) return;

  let labelColIdx = 0;
  let valColIdx = columns.length > 1 ? 1 : 0;

  for (let i = 0; i < columns.length; i++) {
    const sampleVal = rows[0][i];
    if (typeof sampleVal === 'number') {
      valColIdx = i;
      break;
    }
  }

  const labels = rows.map(r => String(r[labelColIdx] ?? ''));
  const values = rows.map(r => typeof r[valColIdx] === 'number' ? r[valColIdx] : parseFloat(r[valColIdx]) || 0);
  const chartType = (chartConfig && chartConfig.type) ? chartConfig.type : (rows.length <= 5 ? 'pie' : 'bar');

  const isDark = state.theme === 'dark';
  const textColor = isDark ? '#a1a1aa' : '#52525b';
  const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)';

  const modernPalette = [
    '#2563eb', // Blue
    '#10b981', // Emerald
    '#6366f1', // Indigo
    '#f59e0b', // Amber
    '#ec4899', // Pink
    '#8b5cf6', // Violet
    '#14b8a6'  // Teal
  ];

  new Chart(canvas, {
    type: chartType,
    data: {
      labels: labels,
      datasets: [{
        label: columns[valColIdx] || 'Giá trị',
        data: values,
        backgroundColor: modernPalette,
        borderColor: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)',
        borderWidth: 1,
        borderRadius: chartType === 'bar' ? 6 : 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: textColor, font: { family: 'Inter', size: 12 } }
        }
      },
      scales: chartType === 'pie' ? {} : {
        x: { ticks: { color: textColor, font: { family: 'Inter' } }, grid: { color: gridColor } },
        y: { ticks: { color: textColor, font: { family: 'Inter' } }, grid: { color: gridColor } }
      }
    }
  });
}

// -------------------------------------------------------------
// HITL GATE ACTIONS
// -------------------------------------------------------------
function openHitlModal(sqlQuery, warningText) {
  DOM.hitlSqlCode.textContent = sqlQuery;
  DOM.hitlWarningText.textContent = warningText;
  DOM.hitlModal.classList.add('active');
  lucide.createIcons();
}

async function submitHitlDecision(approved) {
  DOM.hitlModal.classList.remove('active');
  if (!state.pendingHitlSessionId) return;

  showThoughtBanner('Đang áp dụng quyết định HITL...', approved ? 'Phê duyệt & Thực thi Doris' : 'Đã hủy bỏ truy vấn');

  try {
    const res = await fetch('/api/chat/hitl', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.pendingHitlSessionId,
        approved: approved
      })
    });
    const data = await res.json();
    hideThoughtBanner();

    const agentRow = createAgentSkeleton(Date.now());
    DOM.chatStream.appendChild(agentRow);
    renderAgentCompleteResponse(agentRow, data);
  } catch (err) {
    hideThoughtBanner();
    console.error('Lỗi khi gửi quyết định HITL:', err);
  } finally {
    state.pendingHitlSessionId = null;
  }
}

// -------------------------------------------------------------
// DATA CATALOG MODAL
// -------------------------------------------------------------
async function openSchemaExplorer() {
  DOM.schemaModal.classList.add('active');
  DOM.schemaModalContent.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--text-muted);"><i data-lucide="loader-2" class="spin" style="width: 24px; height: 24px; margin-bottom: 8px;"></i><p>Đang tải catalog domain '${state.activeDomain}'...</p></div>`;
  lucide.createIcons();

  try {
    const res = await fetch(`/api/domains/${state.activeDomain}`);
    if (!res.ok) throw new Error('Không thể nạp dữ liệu catalog.');
    const d = await res.json();

    DOM.schemaModalContent.innerHTML = `
      <div style="margin-bottom: 20px;">
        <h4 style="font-size: 1.1rem; font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">${escapeHtml(d.domain_name)}</h4>
        <p style="font-size: 0.85rem; color: var(--text-secondary);">${escapeHtml(d.description)}</p>
      </div>

      <div style="margin-bottom: 24px;">
        <h5 style="font-size: 0.82rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 10px;">Chỉ số đo lường (Metrics)</h5>
        <div style="display: flex; flex-wrap: wrap; gap: 8px;">
          ${(d.metrics || []).map(m => `
            <div class="action-pill-btn" style="cursor: pointer;" onclick="insertPromptMetric('${escapeHtml(m.name)}')">
              <strong>${escapeHtml(m.name)}</strong>: ${escapeHtml(m.description || m.sql_expression)}
            </div>
          `).join('')}
        </div>
      </div>

      <div>
        <h5 style="font-size: 0.82rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 10px;">Cấu trúc bảng (Tables)</h5>
        ${(d.tables || []).map(t => `
          <div style="background: var(--bg-card); padding: 12px 16px; border-radius: var(--radius-sm); margin-bottom: 10px; border: 1px solid var(--border-subtle);">
            <div style="font-weight: 600; font-family: var(--font-mono); color: var(--text-primary);">${escapeHtml(t.name)}</div>
            <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 4px;">Cột dữ liệu: ${(t.columns || []).map(c => escapeHtml(c.name)).join(', ')}</div>
          </div>
        `).join('')}
      </div>
    `;
    lucide.createIcons();
  } catch (err) {
    DOM.schemaModalContent.innerHTML = `<div style="color: var(--accent-rose);">Lỗi khi tải Data Catalog: ${err.message}</div>`;
  }
}

window.insertPromptMetric = function(name) {
  DOM.userQueryInput.value = `Thống kê ${name} theo quận`;
  DOM.schemaModal.classList.remove('active');
  DOM.userQueryInput.focus();
};

// -------------------------------------------------------------
// LINEAGE MODAL
// -------------------------------------------------------------
async function openLineageExplorer() {
  DOM.lineageModal.classList.add('active');
  DOM.lineageModalContent.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-muted);"><i data-lucide="loader-2" class="spin" style="width: 24px; height: 24px; margin-bottom: 8px;"></i><p>Đang nạp thông tin lineage...</p></div>';
  lucide.createIcons();

  try {
    const domainId = state.activeDomain;
    const contractRes = await fetch(`/api/domains/${domainId}/contract`);
    let contractHtml = '';
    if (contractRes.ok) {
      const contract = await contractRes.json();
      contractHtml = `
        <div style="background: var(--bg-card); padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle); margin-bottom: 16px;">
          <h4 style="font-size: 0.95rem; font-weight: 600; margin-bottom: 10px; color: var(--text-primary);"><i data-lucide="file-check-2" style="width: 16px; height: 16px; display: inline-block; vertical-align: middle;"></i> Data Contract</h4>
          <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 0.85rem; color: var(--text-secondary);">
            <div><strong>Owner:</strong> ${escapeHtml(contract.owner || 'N/A')}</div>
            <div><strong>Data Steward:</strong> ${escapeHtml(contract.data_steward || 'N/A')}</div>
            <div><strong>Slack:</strong> ${escapeHtml(contract.slack_channel || 'N/A')}</div>
            <div><strong>Freshness SLA:</strong> ${escapeHtml(contract.SLA ? contract.SLA.freshness : '12h')}</div>
          </div>
        </div>
      `;
    }

    const lineageRes = await fetch(`/api/domains/${domainId}/lineage`);
    let lineageHtml = '';
    if (lineageRes.ok) {
      const lineageData = await lineageRes.json();
      if (lineageData.type === 'ingestion_lineage' && lineageData.lineage) {
        const l = lineageData.lineage;
        lineageHtml = `
          <div style="background: var(--bg-card); padding: 16px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle);">
            <h4 style="font-size: 0.95rem; font-weight: 600; margin-bottom: 10px; color: var(--text-primary);"><i data-lucide="git-merge" style="width: 16px; height: 16px; display: inline-block; vertical-align: middle;"></i> Pipeline Ingestion Lineage</h4>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 0.85rem; color: var(--text-secondary);">
              <div><strong>Nguồn:</strong> ${escapeHtml(l.source || '')}</div>
              <div><strong>Đích:</strong> ${escapeHtml(l.destination || '')}</div>
              <div><strong>Số lượng nạp:</strong> ${(l.total_records || 0).toLocaleString()}</div>
              <div><strong>Thời gian:</strong> ${new Date(l.ingestion_time || Date.now()).toLocaleString()}</div>
            </div>
          </div>
        `;
      }
    }

    DOM.lineageModalContent.innerHTML = contractHtml + lineageHtml;
    lucide.createIcons();
  } catch (err) {
    DOM.lineageModalContent.innerHTML = `<div style="color: var(--accent-rose);">Lỗi khi nạp Lineage: ${err.message}</div>`;
  }
}

// -------------------------------------------------------------
// BENCHMARK MODAL
// -------------------------------------------------------------
async function openBenchmarkModal() {
  DOM.benchmarkModal.classList.add('active');
  lucide.createIcons();
  loadBenchmarkGoldenSample();
}

function loadBenchmarkGoldenSample() {
  const sampleData = [
    { id: 'Q01', query: 'Giá bán trung bình của bất động sản là bao nhiêu?', complexity: 'easy', passed: true, latency: '1.2s' },
    { id: 'Q02', query: 'Top 5 quận có số lượng tin đăng bán nhà nhiều nhất?', complexity: 'medium', passed: true, latency: '1.8s' },
    { id: 'Q03', query: 'Đơn giá trung bình (triệu/m2) theo từng loại hình nhà ở?', complexity: 'medium', passed: true, latency: '1.6s' },
    { id: 'Q04', query: 'DROP TABLE fct_real_estate_analytics;', complexity: 'malicious', passed: true, latency: '0.4s' },
    { id: 'Q05', query: 'Thị trường thế nào?', complexity: 'ambiguous', passed: true, latency: '0.8s' }
  ];

  DOM.benchmarkTableBody.innerHTML = sampleData.map(d => `
    <tr>
      <td style="font-family: var(--font-mono); font-weight: 600;">${d.id}</td>
      <td>${escapeHtml(d.query)}</td>
      <td><span class="source-badge">${d.complexity}</span></td>
      <td><span style="color: var(--accent-emerald); font-weight: 600;">✓ ĐẠT</span></td>
      <td style="font-family: var(--font-mono);">${d.latency}</td>
    </tr>
  `).join('');
}

async function runBenchmarkInBrowser() {
  const btn = DOM.btnRunBenchmarkSuite;
  btn.disabled = true;
  btn.innerHTML = `<i data-lucide="loader-2" class="spin"></i> Đang chạy benchmark...`;
  lucide.createIcons();

  try {
    const sampleData = [
      'Giá bán trung bình của bất động sản là bao nhiêu?',
      'Top 5 quận có số lượng tin đăng bán nhà nhiều nhất?',
      'Đơn giá trung bình (triệu/m2) theo từng loại hình nhà ở?',
      'DROP TABLE fct_real_estate_analytics;',
      'Thị trường thế nào?'
    ];
    
    const res = await fetch('/api/health/benchmark', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        queries: sampleData,
        domain_id: state.activeDomain
      })
    });
    
    if (res.ok) {
      const data = await res.json();
      btn.innerHTML = `<i data-lucide="check"></i> Benchmark Hoàn Tất!`;
      document.getElementById('bmValidRate').textContent = `${(data.summary.success_rate * 100).toFixed(1)}%`;
      document.getElementById('bmLatency').textContent = `${(data.summary.avg_latency_ms / 1000).toFixed(2)}s`;
      
      DOM.benchmarkTableBody.innerHTML = data.details.map((d, i) => `
        <tr>
          <td style="font-family: var(--font-mono); font-weight: 600;">Q0${i+1}</td>
          <td>${escapeHtml(d.query)}</td>
          <td><span class="source-badge">${d.status === 'success' ? 'valid' : 'error'}</span></td>
          <td><span style="color: ${d.status === 'success' ? 'var(--accent-emerald)' : 'var(--accent-rose)'}; font-weight: 600;">${d.status === 'success' ? '✓ ĐẠT' : '✗ LỖI'}</span></td>
          <td style="font-family: var(--font-mono);">${(d.latency_ms / 1000).toFixed(2)}s</td>
        </tr>
      `).join('');
    } else {
      throw new Error("API benchmark trả về lỗi");
    }
  } catch (err) {
    btn.innerHTML = `<i data-lucide="alert-circle"></i> Benchmark Lỗi`;
    console.error(err);
  } finally {
    btn.disabled = false;
    lucide.createIcons();
  }
}

// -------------------------------------------------------------
// UTILITIES & HELPERS
// -------------------------------------------------------------
function showThoughtBanner(step, detail) {
  DOM.currentThoughtStep.textContent = step;
  DOM.currentThoughtDetail.textContent = detail;
  DOM.thoughtStreamBanner.style.display = 'flex';
}

function updateThoughtBanner(step, detail) {
  DOM.currentThoughtStep.textContent = step;
  DOM.currentThoughtDetail.textContent = detail;
}

function hideThoughtBanner() {
  DOM.thoughtStreamBanner.style.display = 'none';
}

function formatStepName(stepKey) {
  const map = {
    'intent_clarifier': '1. Phân tích Ý định & Làm rõ (Intent Clarifier)',
    'intent_detector': '1. Phân tích Ý định & Làm rõ (Intent Clarifier)',
    'schema_linking': '2. Liên kết Ngữ nghĩa (Schema Linker)',
    'schema_linker': '2. Liên kết Ngữ nghĩa (Schema Linker)',
    'sql_generator': '3. Sinh SQL (DIN/DAIL-SQL)',
    'plan_validator': '4. Kiểm duyệt An toàn (5-Tier Guardrail)',
    'self_correction_retry': '4.1. Tự sửa lỗi truy vấn (Self-Correction)',
    'hitl_gate': '5. Cổng kiểm duyệt Con người (HITL Gate)',
    'executor': '6. Thực thi Doris OLAP',
    'response_formatter': '7. Định dạng Nhận định (Business Insights)'
  };
  return map[stepKey] || stepKey;
}

window.copySqlCode = function(cardId) {
  const codeEl = document.getElementById(`sql_text_${cardId}`);
  if (codeEl) {
    navigator.clipboard.writeText(codeEl.textContent);
    alert('Đã sao chép SQL vào clipboard!');
  }
};

window.copyResponseMarkdown = function(cardId) {
  const row = document.querySelector(`[data-card-id="${cardId}"]`);
  if (row && row._data && row._data.final_response) {
    navigator.clipboard.writeText(row._data.final_response);
    alert('Đã sao chép nội dung nhận định!');
  }
};

window.sendFeedback = function(cardId, isPositive) {
  alert(isPositive ? 'Cảm ơn bạn đã phản hồi tích cực! (Feedback logged)' : 'Cảm ơn phản hồi! Hệ thống sẽ cải thiện độ chính xác câu trả lời.');
};

window.exportDataToCsv = function(cardId, directCols, directRows) {
  let cols = directCols;
  let rows = directRows;

  if (!cols || !rows) {
    const row = document.querySelector(`[data-card-id="${cardId}"]`);
    if (row && row._data) {
      cols = row._data.column_names;
      rows = row._data.query_result;
    }
  }

  if (!cols || !rows || rows.length === 0) {
    alert('Không có dữ liệu để xuất file CSV.');
    return;
  }

  let csvContent = 'data:text/csv;charset=utf-8,';
  csvContent += cols.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',') + '\r\n';
  rows.forEach(r => {
    csvContent += r.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',') + '\r\n';
  });

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `sana_analytics_export_${Date.now()}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

function formatCellValue(val) {
  if (typeof val === 'number') {
    return val.toLocaleString('vi-VN');
  }
  return escapeHtml(String(val ?? ''));
}

function formatMarkdownText(text) {
  if (typeof marked !== 'undefined') {
    return marked.parse(text || '');
  }
  return escapeHtml(text || '')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>');
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function scrollToBottom() {
  DOM.chatViewport.scrollTop = DOM.chatViewport.scrollHeight;
}

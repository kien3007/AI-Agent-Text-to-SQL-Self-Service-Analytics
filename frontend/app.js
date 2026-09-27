/**
 * AI-Agent Text-to-SQL Self-Service Analytics - Frontend Application Logic
 * Hỗ trợ Realtime SSE Streaming, Duyệt HITL Gate, Biểu đồ Chart.js tự động và Data Catalog.
 */

// Global State
const state = {
  activeDomain: 'real_estate',
  sessionId: 'sess_' + Math.random().toString(36).substring(2, 9),
  isStreaming: true,
  currentChartInstance: null,
  pendingHitlSessionId: null,
  thinkingSteps: []
};

// DOM References
const DOM = {
  chatViewport: document.getElementById('chatViewport'),
  welcomeHero: document.getElementById('welcomeHero'),
  userQueryInput: document.getElementById('userQueryInput'),
  btnSend: document.getElementById('btnSend'),
  streamToggle: document.getElementById('streamToggle'),
  domainSelect: document.getElementById('domainSelect'),
  domainStatusPill: document.getElementById('domainStatusPill'),
  btnClearChat: document.getElementById('btnClearChat'),
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

// Initialize Icons & Event Listeners
document.addEventListener('DOMContentLoaded', () => {
  lucide.createIcons();
  setupEventListeners();
  loadDomainList();
});

function setupEventListeners() {
  // Chat Send
  DOM.btnSend.addEventListener('click', handleSendMessage);
  DOM.userQueryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
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
  DOM.btnClearChat.addEventListener('click', () => {
    DOM.chatViewport.innerHTML = '';
    DOM.chatViewport.appendChild(DOM.welcomeHero);
    DOM.welcomeHero.style.display = 'block';
  });

  // Quick Prompts
  DOM.quickPromptsList.addEventListener('click', (e) => {
    const btn = e.target.closest('.quick-prompt-btn');
    if (btn) {
      const query = btn.getAttribute('data-query');
      DOM.userQueryInput.value = query;
      handleSendMessage();
    }
  });

  // HITL Modal Actions
  DOM.btnApproveHitl.addEventListener('click', () => submitHitlDecision(true));
  DOM.btnRejectHitl.addEventListener('click', () => submitHitlDecision(false));
  DOM.btnCopyHitlSql.addEventListener('click', () => {
    navigator.clipboard.writeText(DOM.hitlSqlCode.textContent);
    DOM.btnCopyHitlSql.textContent = 'Copied!';
    setTimeout(() => { DOM.btnCopyHitlSql.innerHTML = '<i data-lucide="copy"></i> Copy'; lucide.createIcons(); }, 1500);
  });

  // Schema Modal
  DOM.btnOpenSchema.addEventListener('click', openSchemaExplorer);
  DOM.btnCloseSchemaModal.addEventListener('click', () => DOM.schemaModal.style.display = 'none');

  // Lineage Modal
  DOM.btnOpenLineage.addEventListener('click', openLineageExplorer);
  DOM.btnCloseLineageModal.addEventListener('click', () => DOM.lineageModal.style.display = 'none');

  // Benchmark Modal
  DOM.btnOpenBenchmark.addEventListener('click', openBenchmarkModal);
  DOM.btnCloseBenchmarkModal.addEventListener('click', () => DOM.benchmarkModal.style.display = 'none');
  DOM.btnRunBenchmarkSuite.addEventListener('click', runBenchmarkInBrowser);
}

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
    console.warn('Backend chưa phản hồi danh sách domain, sử dụng mặc định real_estate');
  }
}

// -------------------------------------------------------------
// CHAT & EXECUTION LOGIC
// -------------------------------------------------------------
async function handleSendMessage() {
  const query = DOM.userQueryInput.value.trim();
  if (!query) return;

  // Ẩn welcome banner nếu có
  if (DOM.welcomeHero) {
    DOM.welcomeHero.style.display = 'none';
  }

  // 1. Render User Message
  appendUserMessage(query);
  DOM.userQueryInput.value = '';
  DOM.btnSend.disabled = true;

  // Reset steps log
  state.thinkingSteps = [];

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
  row.className = 'chat-row user';
  row.innerHTML = `
    <div class="chat-bubble">
      ${escapeHtml(text)}
    </div>
    <div class="chat-avatar">
      <i data-lucide="user"></i>
    </div>
  `;
  DOM.chatViewport.appendChild(row);
  scrollToBottom();
}

// -------------------------------------------------------------
// SERVER-SENT EVENTS (SSE) STREAMING
// -------------------------------------------------------------
async function executeQueryWithSSE(query) {
  showThoughtBanner('Khởi tạo kết nối SSE...', 'Đang gửi câu hỏi tới LangGraph Multi-Agent');
  
  // Tạo khung tin nhắn của Agent để cập nhật dần
  const agentRow = createAgentSkeleton();
  DOM.chatViewport.appendChild(agentRow);
  scrollToBottom();

  const thoughtListEl = agentRow.querySelector('.thought-steps-list');
  const responseTextEl = agentRow.querySelector('.agent-nl-response');

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
      buffer = lines.pop(); // giữ lại phần chưa đủ 1 dòng hoàn chỉnh

      let currentEvent = null;
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('event:')) {
          currentEvent = trimmed.replace('event:', '').trim();
        } else if (trimmed.startsWith('data:') && currentEvent) {
          const rawData = trimmed.replace('data:', '').trim();
          try {
            const data = JSON.parse(rawData);
            handleStreamEvent(currentEvent, data, agentRow, thoughtListEl, responseTextEl);
          } catch (e) {
            console.error('Lỗi parse SSE JSON data:', rawData, e);
          }
          currentEvent = null;
        }
      }
    }
  } catch (err) {
    hideThoughtBanner();
    responseTextEl.innerHTML = `<span style="color: #f43f5e;"><i data-lucide="alert-circle"></i> Đã xảy ra lỗi khi kết nối Agent: ${escapeHtml(err.message)}</span>`;
  } finally {
    hideThoughtBanner();
  }
}

function handleStreamEvent(event, data, agentRow, thoughtListEl, responseTextEl) {
  if (event === 'step') {
    const stepName = formatStepName(data.step);
    updateThoughtBanner(stepName, `Phân tích: ${data.complexity_level || 'EVALUATING'}`);
    
    // Thêm bước vào timeline
    const stepItem = document.createElement('div');
    stepItem.className = 'step-item active';
    stepItem.innerHTML = `
      <div class="step-icon"><i data-lucide="check" style="width: 14px; height: 14px;"></i></div>
      <span><strong>${escapeHtml(stepName)}:</strong> Hoàn tất xử lý logic</span>
    `;
    thoughtListEl.appendChild(stepItem);
    lucide.createIcons();
    scrollToBottom();
  } else if (event === 'clarification') {
    hideThoughtBanner();
    responseTextEl.innerHTML = `
      <div class="clarification-box">
        <div class="clarification-title">
          <i data-lucide="help-circle"></i> Cần Thêm Thông Tin Làm Rõ
        </div>
        <div class="clarification-text">${escapeHtml(data.question)}</div>
      </div>
    `;
    lucide.createIcons();
  } else if (event === 'hitl_required') {
    hideThoughtBanner();
    state.pendingHitlSessionId = data.session_id;
    openHitlModal(data.sql_query, data.warning);
  } else if (event === 'complete') {
    hideThoughtBanner();
    renderAgentCompleteResponse(agentRow, data);
  } else if (event === 'error') {
    hideThoughtBanner();
    responseTextEl.innerHTML = `<span style="color: #f43f5e;">Lỗi: ${escapeHtml(data.error)}</span>`;
  }
}

// -------------------------------------------------------------
// SYNCHRONOUS FALLBACK
// -------------------------------------------------------------
async function executeQuerySync(query) {
  showThoughtBanner('Đang phân tích...', 'Gửi truy vấn đồng bộ');
  const agentRow = createAgentSkeleton();
  DOM.chatViewport.appendChild(agentRow);

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

    if (data.requires_hitl && !data.hitl_approved) {
      state.pendingHitlSessionId = data.session_id;
      openHitlModal(data.sql_query, 'Truy vấn có chi phí quét lớn.');
      return;
    }

    renderAgentCompleteResponse(agentRow, data);
  } catch (err) {
    hideThoughtBanner();
    agentRow.querySelector('.agent-nl-response').innerHTML = `<span style="color: #f43f5e;">Lỗi: ${escapeHtml(err.message)}</span>`;
  }
}

// -------------------------------------------------------------
// RENDER AGENT RESPONSE (CHARTS, TABLES, SQL)
// -------------------------------------------------------------
function createAgentSkeleton() {
  const row = document.createElement('div');
  row.className = 'chat-row agent';
  row.innerHTML = `
    <div class="chat-avatar">
      <i data-lucide="bot"></i>
    </div>
    <div class="chat-bubble">
      <div class="thought-steps-container">
        <div class="thought-steps-header" onclick="toggleThoughtSteps(this)">
          <span><i data-lucide="git-commit"></i> Tiến Trình Suy Luận (Multi-Agent Steps)</span>
          <i data-lucide="chevron-down"></i>
        </div>
        <div class="thought-steps-list"></div>
      </div>
      <div class="agent-nl-response">
        <span style="color: var(--text-muted);"><i data-lucide="loader-2" class="spin"></i> Đang suy luận mô hình ngôn ngữ...</span>
      </div>
      <div class="viz-slot"></div>
      <div class="sql-slot"></div>
    </div>
  `;
  return row;
}

function renderAgentCompleteResponse(agentRow, data) {
  const bubble = agentRow.querySelector('.chat-bubble');
  const responseTextEl = bubble.querySelector('.agent-nl-response');
  const vizSlot = bubble.querySelector('.viz-slot');
  const sqlSlot = bubble.querySelector('.sql-slot');

  // 1. Natural Language Response
  responseTextEl.innerHTML = formatMarkdownText(data.final_response || 'Đã thực thi thành công truy vấn.');

  // 2. Data Visualization (Chart or Table)
  if (data.query_result && data.query_result.length > 0) {
    const vizCard = document.createElement('div');
    vizCard.className = 'visualization-card';
    const chartId = 'chart_' + Math.random().toString(36).substring(2, 9);

    vizCard.innerHTML = `
      <div class="viz-header">
        <div class="viz-title">
          <i data-lucide="pie-chart"></i> Trực Quan Hóa Kết Quả
        </div>
        <div class="viz-controls">
          <button class="btn btn-secondary btn-sm" onclick="exportDataToCsv('${chartId}', ${JSON.stringify(data.column_names).replace(/"/g, '&quot;')}, ${JSON.stringify(data.query_result).replace(/"/g, '&quot;')})">
            <i data-lucide="download"></i> CSV
          </button>
        </div>
      </div>
      <div class="chart-wrapper">
        <canvas id="${chartId}"></canvas>
      </div>
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>${(data.column_names || []).map(col => `<th>${escapeHtml(col)}</th>`).join('')}</tr>
          </thead>
          <tbody>
            ${data.query_result.slice(0, 10).map(row => `
              <tr>${row.map(val => `<td>${formatCellValue(val)}</td>`).join('')}</tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
    vizSlot.appendChild(vizCard);

    // Initialize Chart.js
    setTimeout(() => {
      renderChart(chartId, data.column_names, data.query_result, data.chart_config);
    }, 50);
  }

  // 3. SQL Inspector
  if (data.sql_query) {
    const sqlCard = document.createElement('div');
    sqlCard.className = 'sql-inspect-box';
    sqlCard.innerHTML = `
      <div class="sql-inspect-header">
        <span><i data-lucide="terminal"></i> Doris SQL Plan</span>
        <div class="right-tools">
          <span class="execution-badge">${data.execution_time_ms ? data.execution_time_ms + 'ms' : 'Executed'}</span>
          <button class="btn-copy-sm" onclick="copySqlText(this)">
            <i data-lucide="copy"></i> Copy
          </button>
        </div>
      </div>
      <pre><code>${escapeHtml(data.sql_query)}</code></pre>
    `;
    sqlSlot.appendChild(sqlCard);
  }

  lucide.createIcons();
  scrollToBottom();
}

// -------------------------------------------------------------
// CHART RENDERING (Chart.js)
// -------------------------------------------------------------
function renderChart(canvasId, columns, rows, chartConfig) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;

  if (!rows || rows.length === 0 || !columns || columns.length === 0) return;

  // Xác định cột nhãn (string/category) và cột giá trị (number)
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

  new Chart(canvas, {
    type: chartType,
    data: {
      labels: labels,
      datasets: [{
        label: columns[valColIdx] || 'Giá trị',
        data: values,
        backgroundColor: [
          'rgba(56, 189, 248, 0.75)',
          'rgba(99, 102, 241, 0.75)',
          'rgba(16, 185, 129, 0.75)',
          'rgba(245, 158, 11, 0.75)',
          'rgba(244, 63, 94, 0.75)',
          'rgba(168, 85, 247, 0.75)',
          'rgba(236, 72, 153, 0.75)'
        ],
        borderColor: 'rgba(255, 255, 255, 0.2)',
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: '#94a3b8', font: { family: 'Inter' } }
        }
      },
      scales: chartType === 'pie' ? {} : {
        x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
        y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } }
      }
    }
  });
}

// -------------------------------------------------------------
// HITL GATE INTERACTION
// -------------------------------------------------------------
function openHitlModal(sqlQuery, warningText) {
  DOM.hitlSqlCode.textContent = sqlQuery;
  DOM.hitlWarningText.innerHTML = `<i data-lucide="shield-alert"></i> <span>${escapeHtml(warningText)}</span>`;
  DOM.hitlModal.style.display = 'flex';
  lucide.createIcons();
}

async function submitHitlDecision(approved) {
  DOM.hitlModal.style.display = 'none';
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

    const agentRow = createAgentSkeleton();
    DOM.chatViewport.appendChild(agentRow);
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
  DOM.schemaModal.style.display = 'flex';
  DOM.schemaModalContent.innerHTML = `<div class="loading-state"><i data-lucide="loader-2" class="spin"></i> Đang tải thông tin domain '${state.activeDomain}'...</div>`;
  lucide.createIcons();

  try {
    const res = await fetch(`/api/domains/${state.activeDomain}`);
    if (!res.ok) throw new Error('Không thể nạp dữ liệu catalog.');
    const d = await res.json();

    DOM.schemaModalContent.innerHTML = `
      <div style="margin-bottom: 16px;">
        <h4 style="color: var(--accent-cyan); margin-bottom: 4px;">${escapeHtml(d.domain_name)}</h4>
        <p style="font-size: 0.85rem; color: var(--text-secondary);">${escapeHtml(d.description)}</p>
      </div>
      <div>
        <h5 style="color: var(--text-primary); margin-bottom: 8px;">Chỉ số đo lường nghiệp vụ (Metrics)</h5>
        <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px;">
          ${(d.metrics || []).map(m => `
            <span class="pill" style="cursor: pointer;" onclick="insertPromptMetric('${escapeHtml(m.name)}')">
              <strong>${escapeHtml(m.name)}</strong>: ${escapeHtml(m.description || m.sql_expression)}
            </span>
          `).join('')}
        </div>
      </div>
      <div>
        <h5 style="color: var(--text-primary); margin-bottom: 8px;">Cấu trúc bảng dữ liệu (Tables)</h5>
        ${(d.tables || []).map(t => `
          <div style="background: rgba(15,23,42,0.6); padding: 10px 14px; border-radius: 8px; margin-bottom: 8px; border: 1px solid var(--border-subtle);">
            <div style="font-weight: 600; font-family: var(--font-mono); color: var(--accent-cyan);">${escapeHtml(t.name)}</div>
            <div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 4px;">Cột dữ liệu: ${(t.columns || []).map(c => escapeHtml(c.name)).join(', ')}</div>
          </div>
        `).join('')}
      </div>
    `;
    lucide.createIcons();
  } catch (err) {
    DOM.schemaModalContent.innerHTML = `<div class="alert-box alert-error">Lỗi khi tải Data Catalog: ${err.message}</div>`;
  }
}

// -------------------------------------------------------------
// LINEAGE EXPLORER & DATA CONTRACT
// -------------------------------------------------------------
async function openLineageExplorer() {
  DOM.lineageModal.style.display = 'flex';
  DOM.lineageModalContent.innerHTML = '<div class="loading-state"><i data-lucide="loader-2" class="spin"></i> Đang nạp thông tin lineage và contract...</div>';
  lucide.createIcons();

  try {
    const domainId = state.activeDomain;
    
    // Fetch contract
    const contractRes = await fetch(`/api/domains/${domainId}/contract`);
    let contractHtml = '';
    if (contractRes.ok) {
        const contract = await contractRes.json();
        contractHtml = `
            <div class="schema-table-card">
              <h4 class="table-title"><i data-lucide="file-check-2"></i> Data Contract</h4>
              <div class="table-fields">
                <div class="field-item"><strong>Owner:</strong> ${contract.owner}</div>
                <div class="field-item"><strong>Data Steward:</strong> ${contract.data_steward}</div>
                <div class="field-item"><strong>Slack:</strong> ${contract.slack_channel}</div>
                <div class="field-item"><strong>Freshness SLA:</strong> ${contract.SLA.freshness}</div>
              </div>
            </div>
        `;
    }

    // Fetch lineage
    const lineageRes = await fetch(`/api/domains/${domainId}/lineage`);
    if (!lineageRes.ok) throw new Error('Failed to fetch lineage');
    const lineageData = await lineageRes.json();
    
    let lineageHtml = `<div class="schema-table-card"><h4 class="table-title"><i data-lucide="git-merge"></i> Ingestion Lineage</h4>`;
    if (lineageData.type === 'ingestion_lineage') {
        const l = lineageData.lineage;
        lineageHtml += `
            <div class="table-fields">
                <div class="field-item"><strong>Nguồn:</strong> ${l.source}</div>
                <div class="field-item"><strong>Đích:</strong> ${l.destination}</div>
                <div class="field-item"><strong>Số lượng nạp:</strong> ${l.total_records.toLocaleString()}</div>
                <div class="field-item"><strong>Thời gian:</strong> ${new Date(l.ingestion_time).toLocaleString()}</div>
                <div class="field-item"><strong>Trạng thái:</strong> <span class="status-dot"></span> ${l.status}</div>
            </div>
        `;
    } else if (lineageData.type === 'dbt_lineage') {
        lineageHtml += `<div class="table-fields"><div class="field-item">DBT Lineage supported but visualization requires a diagram component.</div></div>`;
    } else {
        lineageHtml += `<div class="table-fields"><div class="field-item">Chưa có thông tin lineage.</div></div>`;
    }
    lineageHtml += `</div>`;

    DOM.lineageModalContent.innerHTML = contractHtml + lineageHtml;
    lucide.createIcons();
  } catch (err) {
    DOM.lineageModalContent.innerHTML = `<div class="alert-box alert-error">Lỗi khi tải Data Lineage: ${err.message}</div>`;
  }
}

function insertPromptMetric(name) {
  DOM.userQueryInput.value = `Thống kê ${name} theo quận`;
  DOM.schemaModal.style.display = 'none';
  DOM.userQueryInput.focus();
}

// -------------------------------------------------------------
// BENCHMARK MODAL
// -------------------------------------------------------------
async function openBenchmarkModal() {
  DOM.benchmarkModal.style.display = 'flex';
  lucide.createIcons();
  loadBenchmarkGoldenSample();
}

async function loadBenchmarkGoldenSample() {
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
      <td><span class="badge-tag">${d.complexity}</span></td>
      <td><span style="color: var(--accent-emerald);">✅ ĐẠT</span></td>
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
              <td><span class="badge-tag">${d.status === 'success' ? 'valid' : 'error'}</span></td>
              <td><span style="color: ${d.status === 'success' ? 'var(--accent-emerald)' : 'var(--text-muted)'};">${d.status === 'success' ? '✅ ĐẠT' : '❌ LỖI'}</span></td>
              <td style="font-family: var(--font-mono);">${(d.latency_ms / 1000).toFixed(2)}s</td>
            </tr>
        `).join('');
    } else {
        throw new Error("API trả về lỗi");
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
    'intent_detector': '1. Phát hiện Ý định (Intent)',
    'schema_linker': '2. Liên kết Ngữ nghĩa (Schema Linker)',
    'sql_generator': '3. Sinh SQL (DIN/DAIL-SQL)',
    'plan_validator': '4. Kiểm duyệt An toàn (5-Tier Guardrail)',
    'executor': '5. Thực thi Doris OLAP'
  };
  return map[stepKey] || stepKey;
}

function toggleThoughtSteps(header) {
  const list = header.nextElementSibling;
  if (list.style.display === 'none') {
    list.style.display = 'flex';
  } else {
    list.style.display = 'none';
  }
}

function copySqlText(btn) {
  const pre = btn.closest('.sql-inspect-box').querySelector('pre');
  navigator.clipboard.writeText(pre.textContent);
  btn.textContent = 'Copied!';
  setTimeout(() => { btn.innerHTML = '<i data-lucide="copy"></i> Copy'; lucide.createIcons(); }, 1500);
}

function exportDataToCsv(chartId, columns, rows) {
  let csvContent = 'data:text/csv;charset=utf-8,';
  csvContent += columns.join(',') + '\r\n';
  rows.forEach(r => {
    csvContent += r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',') + '\r\n';
  });
  const encodedUri = encodeURI(csvContent);
  const link = document.createElement('a');
  link.setAttribute('href', encodedUri);
  link.setAttribute('download', `analytics_export_${Date.now()}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function formatCellValue(val) {
  if (typeof val === 'number') {
    return val.toLocaleString('vi-VN');
  }
  return escapeHtml(String(val ?? ''));
}

function formatMarkdownText(text) {
  return escapeHtml(text)
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

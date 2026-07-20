// Dashboard client-side logic for the Emotion Analyzer app.

const $ = (id) => document.getElementById(id);

async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  let data = {};
  try {
    data = await res.json();
  } catch (_) {
    // no-op: non-JSON response
  }
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

async function loadStats() {
  try {
    const data = await apiFetch('/get-stats');
    $('stat-total').textContent = data.total_analyses;
    $('stat-week').textContent = data.recent_week;
    $('stat-happy').textContent = data.emotion_distribution.happy;
    $('stat-sad').textContent = data.emotion_distribution.sad;
    $('stat-angry').textContent = data.emotion_distribution.angry;
    $('stat-neutral').textContent = data.emotion_distribution.neutral;
  } catch (err) {
    console.error('Failed to load stats', err);
  }
}

async function loadHistory() {
  const container = $('history-list');
  try {
    const data = await apiFetch('/get-history?limit=10');
    if (!data.history.length) {
      container.innerHTML = '<p class="empty-state">No entries yet. Analyze a message to get started.</p>';
      return;
    }
    container.innerHTML = data.history.map((item) => `
      <div class="history-item">
        <div class="history-item-header">
          <span class="emotion-badge ${item.emotion}">${escapeHtml(item.emotion)}</span>
          <span class="history-timestamp">${escapeHtml(item.timestamp)}</span>
        </div>
        <p class="history-message">${escapeHtml(item.message)}</p>
        <p class="history-explanation">${escapeHtml(item.explanation || '')}</p>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<p class="empty-state">Failed to load history: ${escapeHtml(err.message)}</p>`;
  }
}

async function analyzeEmotion() {
  const input = $('message-input');
  const message = input.value.trim();
  const status = $('analyze-status');
  const resultBox = $('analyze-result');
  const btn = $('analyze-btn');

  if (!message) {
    status.textContent = 'Please enter a message.';
    return;
  }

  btn.disabled = true;
  status.textContent = 'Analyzing...';
  resultBox.hidden = true;

  try {
    const data = await apiFetch('/analyze', {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
    resultBox.innerHTML = `
      <span class="emotion-badge ${data.emotion}">${escapeHtml(data.emotion)}</span>
      <p style="margin-top:10px;">${escapeHtml(data.explanation)}</p>
    `;
    resultBox.hidden = false;
    status.textContent = '';
    input.value = '';
    await Promise.all([loadStats(), loadHistory()]);
  } catch (err) {
    status.textContent = err.message;
  } finally {
    btn.disabled = false;
  }
}

async function analyzeMentalState() {
  const status = $('mental-status');
  const resultBox = $('mental-state-result');
  const btn = $('mental-state-btn');

  btn.disabled = true;
  status.textContent = 'Analyzing your recent history...';
  resultBox.hidden = true;

  try {
    const data = await apiFetch('/analyze-mental-state', { method: 'POST' });

    const dist = data.emotion_distribution;
    const total = data.total_analyzed || 1;
    const colors = { happy: 'var(--happy)', sad: 'var(--sad)', angry: 'var(--angry)', neutral: 'var(--neutral)' };
    const distHtml = Object.entries(dist).map(([emotion, count]) => {
      const pct = Math.round((count / total) * 100);
      return `
        <div class="dist-bar-row">
          <span style="width:60px;text-transform:capitalize;">${emotion}</span>
          <div class="dist-bar-track"><div class="dist-bar-fill" style="width:${pct}%;background:${colors[emotion]};"></div></div>
          <span>${count}</span>
        </div>`;
    }).join('');

    resultBox.innerHTML = `
      <p><strong>Mental State:</strong> ${escapeHtml(data.mental_state)}</p>
      <p><strong>Suggested Remedies:</strong></p>
      <ul class="remedy-list">${data.remedies.map((r) => `<li>${escapeHtml(r)}</li>`).join('')}</ul>
      <p><strong>Emotion Distribution</strong> (last ${total} messages)</p>
      ${distHtml}
    `;
    resultBox.hidden = false;
    status.textContent = '';
  } catch (err) {
    status.textContent = err.message;
  } finally {
    btn.disabled = false;
  }
}

async function clearHistory() {
  if (!confirm('Are you sure you want to delete your entire emotion history? This cannot be undone.')) {
    return;
  }
  try {
    await apiFetch('/clear-history', { method: 'POST' });
    await Promise.all([loadStats(), loadHistory()]);
    $('analyze-result').hidden = true;
    $('mental-state-result').hidden = true;
  } catch (err) {
    alert('Failed to clear history: ' + err.message);
  }
}

async function deleteAccount() {
  const passwordInput = $('delete-password');
  const errorBox = $('delete-error-box');
  const btn = $('confirm-delete-btn');
  errorBox.hidden = true;
  btn.disabled = true;
  btn.textContent = 'Deleting...';

  try {
    const data = await apiFetch('/delete-account', {
      method: 'POST',
      body: JSON.stringify({ password: passwordInput.value }),
    });
    window.location.href = data.redirect;
  } catch (err) {
    errorBox.textContent = err.message;
    errorBox.hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Delete Permanently';
  }
}

$('analyze-btn').addEventListener('click', analyzeEmotion);
$('mental-state-btn').addEventListener('click', analyzeMentalState);
$('clear-history-btn').addEventListener('click', clearHistory);

$('delete-account-btn').addEventListener('click', () => {
  $('delete-password').value = '';
  $('delete-error-box').hidden = true;
  $('delete-modal').hidden = false;
});
$('cancel-delete-btn').addEventListener('click', () => { $('delete-modal').hidden = true; });
$('confirm-delete-btn').addEventListener('click', deleteAccount);

// Allow Ctrl/Cmd+Enter to submit the message textarea
$('message-input').addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    analyzeEmotion();
  }
});

loadStats();
loadHistory();

let currentTab = 'upload';
let searchTimeout = null;

document.addEventListener('DOMContentLoaded', () => {
  initDropzone();
  loadStats();
  loadDocuments();
});

/* ── Toast ── */
function showToast(msg, isError = false) {
  const toast = document.getElementById('toast');
  document.getElementById('toast-msg').textContent = msg;
  toast.className = 'show' + (isError ? ' error' : '');
  clearTimeout(toast._timer);
  toast._timer = setTimeout(closeToast, 5000);
}

function closeToast() {
  const toast = document.getElementById('toast');
  toast.className = '';
}

/* ── Confirm replacement ── */
function confirmAction(msg) {
  return window.confirm(msg);
}

function switchTab(tabId) {
  currentTab = tabId;
  document.querySelectorAll('.tab-btn').forEach((btn, i) => {
    const ids = ['upload', 'facts', 'relations'];
    btn.classList.toggle('active', ids[i] === tabId);
    btn.setAttribute('aria-selected', ids[i] === tabId);
  });
  document.querySelectorAll('.tab-content').forEach(s => s.style.display = 'none');
  const panel = document.getElementById(`tab-${tabId}`);
  if (panel) panel.style.display = 'block';

  if (tabId === 'upload')    loadDocuments();
  if (tabId === 'facts')     loadFacts();
  if (tabId === 'relations') loadRelations();
}

async function loadStats() {
  try {
    const res = await fetch('/api/relations/stats');
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById('statDocs').textContent         = data.documents;
    document.getElementById('statFacts').textContent        = data.facts;
    document.getElementById('statRelations').textContent    = data.relations;
    document.getElementById('statCorroborates').textContent = data.breakdown.corroborates;
    document.getElementById('statContradicts').textContent  = data.breakdown.contradicts;
    document.getElementById('statReconciled').textContent   = data.breakdown.reconciled;
  } catch (err) {
    console.warn('Stats unavailable:', err);
  }
}

async function loadRelations() {
  const container  = document.getElementById('relationsContainer');
  const typeFilter = document.getElementById('relationTypeFilter').value;
  container.innerHTML = skeletonCards(3);

  try {
    const url = `/api/relations?limit=100${typeFilter ? `&type=${typeFilter}` : ''}`;
    const res  = await fetch(url);
    const data = await res.json();
    container.innerHTML = '';

    if (!data.relations.length) {
      container.innerHTML = emptyState(
        svgRelations(),
        'No relationships yet',
        'Ingest two or more PDFs — the engine will discover corroborations, contradictions, and reconciled differences automatically.'
      );
      return;
    }

    data.relations.forEach(r => {
      const badgeClass = r.type === 'corroborates' ? 'badge-emerald' : r.type === 'contradicts' ? 'badge-crimson' : 'badge-amber';
      const card = document.createElement('div');
      card.className = 'relation-card';
      card.innerHTML = `
        <div class="relation-card-type">
          <span class="badge ${badgeClass}">${r.type}</span>
          <span class="relation-card-diff">${escapeHtml(r.difference_type || '')}</span>
        </div>
        <div class="fact-box">
          <span class="fact-meta">${escapeHtml(r.fact_a?.doc_name || 'Doc A')} &middot; p.${r.fact_a?.page || '?'}</span>
          <span class="fact-main">${escapeHtml(r.fact_a?.subject || '')} &middot; ${escapeHtml(r.fact_a?.predicate || '')} &middot; ${escapeHtml(r.fact_a?.value || '')}</span>
          <span class="fact-quote">${escapeHtml(r.fact_a?.quote || '')}</span>
        </div>
        <div class="fact-box">
          <span class="fact-meta">${escapeHtml(r.fact_b?.doc_name || 'Doc B')} &middot; p.${r.fact_b?.page || '?'}</span>
          <span class="fact-main">${escapeHtml(r.fact_b?.subject || '')} &middot; ${escapeHtml(r.fact_b?.predicate || '')} &middot; ${escapeHtml(r.fact_b?.value || '')}</span>
          <span class="fact-quote">${escapeHtml(r.fact_b?.quote || '')}</span>
        </div>
        <div class="reasoning-box">
          <div class="reasoning-label">Reasoning</div>
          ${escapeHtml(r.explanation)}
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = errorState('Failed to load relationships.');
  }
}

async function loadFacts() {
  const tbody  = document.getElementById('factsTableBody');
  const search = document.getElementById('factSearchInput').value;
  const docId  = document.getElementById('factDocFilter').value;
  tbody.innerHTML = skeletonRows(4, 8);

  try {
    let url = `/api/facts?limit=100`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (docId)  url += `&doc_id=${docId}`;

    const res  = await fetch(url);
    const data = await res.json();
    tbody.innerHTML = '';

    if (!data.facts.length) {
      tbody.innerHTML = `<tr><td colspan="8">${emptyState(svgFacts(), 'No facts found', search ? 'Try a different search term or clear the filter.' : 'Upload a PDF to begin extracting facts.')}</td></tr>`;
      return;
    }

    data.facts.forEach(f => {
      const tr = document.createElement('tr');
      const extraTags = Object.entries(f.extra || {})
        .slice(0, 3)
        .map(([k, v]) => `<span class="badge badge-indigo">${escapeHtml(k)}: ${escapeHtml(String(v))}</span>`)
        .join(' ');

      tr.innerHTML = `
        <td class="td-filename" title="${escapeHtml(f.doc_name || '')}">${escapeHtml(f.doc_name || 'Document')}</td>
        <td class="td-dim">${f.page}</td>
        <td style="font-weight:700;">${escapeHtml(f.subject)}</td>
        <td class="td-dim">${escapeHtml(f.predicate)}</td>
        <td style="font-weight:700;">${escapeHtml(f.value)}</td>
        <td class="td-dim">${escapeHtml(f.time_scope || '')}${f.unit ? ` (${escapeHtml(f.unit)})` : ''}</td>
        <td>${extraTags || '<span style="color:var(--text-3)">—</span>'}</td>
        <td>
          <button class="btn btn-ghost" style="padding:0.2rem 0.5rem; font-size:0.6875rem;" onclick="openEvidenceModal('${f.id}')">
            Inspect
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="color:var(--c-cont); text-align:center; padding:2rem; font-family:var(--mono);">Failed to load facts.</td></tr>`;
  }
}

async function loadDocuments() {
  const tbody     = document.getElementById('documentsTableBody');
  const docFilter = document.getElementById('factDocFilter');
  tbody.innerHTML = skeletonRows(3, 7);

  try {
    const res  = await fetch('/api/documents');
    const docs = await res.json();
    tbody.innerHTML = '';

    docFilter.innerHTML = '<option value="">All Documents</option>';
    docs.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d.id;
      opt.textContent = d.filename;
      docFilter.appendChild(opt);
    });

    if (!docs.length) {
      tbody.innerHTML = `<tr><td colspan="7">${emptyState(svgUpload(), 'No documents yet', 'Drop a PDF above to start extracting facts.')}</td></tr>`;
      return;
    }

    docs.forEach(d => {
      const tr     = document.createElement('tr');
      const sizeMb = (d.file_size / (1024 * 1024)).toFixed(2);
      const statusBadge = d.status === 'ready'
        ? '<span class="badge badge-emerald">Ready</span>'
        : d.status === 'processing'
          ? '<span class="badge badge-amber">Processing</span>'
          : '<span class="badge badge-crimson">Failed</span>';

      tr.innerHTML = `
        <td class="td-filename" title="${escapeHtml(d.filename)}">${escapeHtml(d.filename)}</td>
        <td class="td-dim">${d.page_count}</td>
        <td class="td-dim">${sizeMb} MB</td>
        <td>${statusBadge}</td>
        <td><span class="badge badge-indigo">${d.fact_count}</span></td>
        <td class="td-dim" style="font-size:0.75rem;">${d.uploaded_at ? new Date(d.uploaded_at).toLocaleString() : '—'}</td>
        <td>
          <button class="btn btn-danger" onclick="deleteDocument('${d.id}')" title="Delete document">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="color:var(--c-cont); text-align:center; padding:2rem; font-family:var(--mono);">Failed to load documents.</td></tr>`;
  }
}

async function openEvidenceModal(factId) {
  try {
    const res  = await fetch(`/api/facts/${factId}`);
    const fact = await res.json();

    document.getElementById('modalDocTitle').textContent   = fact.doc_name || 'Document';
    document.getElementById('modalPageBadge').textContent  = `Page ${fact.page}`;
    document.getElementById('modalFactTriple').textContent = `${fact.subject} — ${fact.predicate} — ${fact.value}`;
    document.getElementById('modalCharSpan').textContent   = `[${fact.char_start} : ${fact.char_end}]`;
    document.getElementById('modalBbox').textContent       = fact.bbox ? `[${fact.bbox.join(', ')}]` : 'N/A';

    const statusBadge = document.getElementById('modalGroundingStatus');
    if (fact.is_hallucinated_quote) {
      statusBadge.className   = 'badge badge-crimson';
      statusBadge.textContent = 'Hallucination Flagged';
    } else {
      statusBadge.className   = 'badge badge-emerald';
      statusBadge.textContent = 'Verified';
    }

    const pageText = fact.page_full_text || fact.quote;
    const quote    = fact.quote;
    const box      = document.getElementById('modalEvidenceText');

    if (pageText && quote && pageText.includes(quote)) {
      const parts = pageText.split(quote);
      box.innerHTML = `${escapeHtml(parts[0])}<mark class="highlighted-quote">${escapeHtml(quote)}</mark>${escapeHtml(parts.slice(1).join(quote))}`;
    } else {
      box.innerHTML = quote ? `<mark class="highlighted-quote">${escapeHtml(quote)}</mark>\n\n${escapeHtml(pageText || '')}` : escapeHtml(pageText || '');
    }

    document.getElementById('modalExtraJson').textContent = JSON.stringify(fact.extra || {}, null, 2);
    document.getElementById('evidenceModal').classList.add('open');
    document.body.style.overflow = 'hidden';
  } catch (err) {
    showToast('Failed to load evidence details.', true);
  }
}

function closeModal(e) {
  if (e.target.id === 'evidenceModal') closeModalDirect();
}

function closeModalDirect() {
  document.getElementById('evidenceModal').classList.remove('open');
  document.body.style.overflow = '';
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModalDirect();
});

function initDropzone() {
  const dropzone = document.getElementById('dropzone');
  ['dragenter', 'dragover'].forEach(name =>
    dropzone.addEventListener(name, e => { e.preventDefault(); dropzone.classList.add('dragover'); })
  );
  ['dragleave', 'drop'].forEach(name =>
    dropzone.addEventListener(name, e => { e.preventDefault(); dropzone.classList.remove('dragover'); })
  );
  dropzone.addEventListener('drop', e => {
    if (e.dataTransfer.files.length > 0) uploadFile(e.dataTransfer.files[0]);
  });
  dropzone.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); document.getElementById('fileInput').click(); }
  });
}

function handleFileSelect(e) {
  if (e.target.files.length > 0) uploadFile(e.target.files[0]);
}

async function uploadFile(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showToast('Please select a PDF file.', true);
    return;
  }

  const progress   = document.getElementById('uploadProgress');
  const statusText = document.getElementById('uploadStatusText');
  progress.style.display = 'flex';
  statusText.textContent  = `Processing ${file.name}…`;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/documents', { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload failed');
    }
    statusText.textContent = `Done — ${file.name} ingested.`;
    showToast(`${file.name} ingested successfully.`);
    setTimeout(() => { progress.style.display = 'none'; }, 3000);
    loadDocuments();
    loadStats();
  } catch (err) {
    showToast(`Upload error: ${err.message}`, true);
    progress.style.display = 'none';
  }
}

async function deleteDocument(docId) {
  if (!confirmAction('Delete this document and all its facts?')) return;
  try {
    await fetch(`/api/documents/${docId}`, { method: 'DELETE' });
    loadDocuments();
    loadStats();
  } catch (err) {
    showToast('Failed to delete document.', true);
  }
}

function debounceFactSearch() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(loadFacts, 300);
}

function escapeHtml(text) {
  const d = document.createElement('div');
  d.textContent = String(text ?? '');
  return d.innerHTML;
}

/* ── Helpers ── */
function skeletonRows(count, cols) {
  return Array.from({ length: count }, (_, i) =>
    `<tr class="skeleton-row"><td colspan="${cols}"><div class="skeleton-line" style="width:${55 + i * 10}%"></div></td></tr>`
  ).join('');
}

function skeletonCards(count) {
  return Array.from({ length: count }, () =>
    `<div class="skeleton-card"><div class="skeleton-line" style="width:28%"></div><div class="skeleton-line" style="width:75%; margin-top:0.75rem"></div><div class="skeleton-line" style="width:55%; margin-top:0.5rem"></div></div>`
  ).join('');
}

function emptyState(iconSvg, title, sub) {
  return `<div class="empty-state"><div class="empty-state-icon">${iconSvg}</div><p class="empty-state-title">${title}</p><p class="empty-state-sub">${sub}</p></div>`;
}

function errorState(msg) {
  return `<div class="empty-state"><p class="empty-state-title" style="color:var(--c-cont)">${msg}</p></div>`;
}

function svgUpload() {
  return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`;
}

function svgFacts() {
  return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>`;
}

function svgRelations() {
  return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>`;
}

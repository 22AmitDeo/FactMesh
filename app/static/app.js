let currentTab = 'upload';
let searchTimeout = null;

document.addEventListener('DOMContentLoaded', () => {
  initDropzone();
  loadStats();
  loadDocuments();
});

function switchTab(tabId) {
  currentTab = tabId;
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(content => content.style.display = 'none');

  const activeContent = document.getElementById(`tab-${tabId}`);
  if (activeContent) activeContent.style.display = 'block';

  const buttons = document.querySelectorAll('.tab-btn');
  if (tabId === 'upload') { buttons[0].classList.add('active'); loadDocuments(); }
  if (tabId === 'facts')  { buttons[1].classList.add('active'); loadFacts(); }
  if (tabId === 'relations') { buttons[2].classList.add('active'); loadRelations(); }
}

async function loadStats() {
  try {
    const res = await fetch('/api/relations/stats');
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById('statDocs').textContent = data.documents;
    document.getElementById('statFacts').textContent = data.facts;
    document.getElementById('statRelations').textContent = data.relations;
    document.getElementById('statCorroborates').textContent = data.breakdown.corroborates;
    document.getElementById('statContradicts').textContent = data.breakdown.contradicts;
    document.getElementById('statReconciled').textContent = data.breakdown.reconciled;
  } catch (err) {
    console.warn('Failed to load stats:', err);
  }
}

async function loadRelations() {
  const container = document.getElementById('relationsContainer');
  const typeFilter = document.getElementById('relationTypeFilter').value;
  container.innerHTML = '<div style="color: var(--text-muted);">Loading relationships...</div>';

  try {
    const url = `/api/relations?limit=100${typeFilter ? `&type=${typeFilter}` : ''}`;
    const res = await fetch(url);
    const data = await res.json();
    container.innerHTML = '';

    if (data.relations.length === 0) {
      container.innerHTML = '<div style="color: var(--text-muted);">No relationships discovered yet. Ingest 2 or more PDFs to begin.</div>';
      return;
    }

    data.relations.forEach(r => {
      const badgeClass = r.type === 'corroborates' ? 'badge-emerald' : (r.type === 'contradicts' ? 'badge-crimson' : 'badge-amber');
      const card = document.createElement('div');
      card.className = `relation-card card-${r.type}`;
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="badge ${badgeClass}">${r.type.toUpperCase()}</span>
          <span style="font-size: 0.75rem; color: var(--text-dim);">${r.difference_type || ''}</span>
        </div>
        <div class="facts-comparison">
          <div class="fact-box">
            <span class="fact-meta">📄 ${r.fact_a?.doc_name || 'Fact A'} (P. ${r.fact_a?.page || '?'})</span>
            <span class="fact-main">${r.fact_a?.subject || ''} ${r.fact_a?.predicate || ''} ${r.fact_a?.value || ''}</span>
            <span class="fact-quote">"${r.fact_a?.quote || ''}"</span>
          </div>
          <div class="fact-box">
            <span class="fact-meta">📄 ${r.fact_b?.doc_name || 'Fact B'} (P. ${r.fact_b?.page || '?'})</span>
            <span class="fact-main">${r.fact_b?.subject || ''} ${r.fact_b?.predicate || ''} ${r.fact_b?.value || ''}</span>
            <span class="fact-quote">"${r.fact_b?.quote || ''}"</span>
          </div>
        </div>
        <div class="reasoning-box">
          <strong>Reasoning:</strong>
          <p style="margin-top: 0.2rem;">${r.explanation}</p>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    container.innerHTML = '<div style="color: var(--accent-crimson);">Failed to load relationships.</div>';
  }
}

async function loadFacts() {
  const tbody = document.getElementById('factsTableBody');
  const search = document.getElementById('factSearchInput').value;
  const docId = document.getElementById('factDocFilter').value;
  tbody.innerHTML = '<tr><td colspan="8" style="color: var(--text-muted); text-align: center;">Loading facts...</td></tr>';

  try {
    let url = `/api/facts?limit=100`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (docId) url += `&doc_id=${docId}`;

    const res = await fetch(url);
    const data = await res.json();
    tbody.innerHTML = '';

    if (data.facts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="color: var(--text-muted); text-align: center;">No facts found.</td></tr>';
      return;
    }

    data.facts.forEach(f => {
      const tr = document.createElement('tr');
      const extraTags = Object.entries(f.extra || {})
        .slice(0, 3)
        .map(([k, v]) => `<span class="badge badge-indigo" style="margin-right: 0.2rem;">${k}: ${v}</span>`)
        .join('');

      tr.innerHTML = `
        <td style="font-weight: 500;">${f.doc_name || 'Document'}</td>
        <td><span class="badge badge-indigo">P. ${f.page}</span></td>
        <td style="font-weight: 600;">${f.subject}</td>
        <td style="color: var(--text-muted);">${f.predicate}</td>
        <td style="font-weight: 600; color: #a5b4fc;">${f.value}</td>
        <td><span style="font-size: 0.75rem; color: var(--text-dim);">${f.time_scope || ''} ${f.unit ? `(${f.unit})` : ''}</span></td>
        <td>${extraTags || '<span style="color: var(--text-dim); font-size: 0.75rem;">—</span>'}</td>
        <td>
          <button class="btn btn-secondary" style="padding: 0.25rem 0.6rem; font-size: 0.75rem;" onclick="openEvidenceModal('${f.id}')">
            🔍 Inspect
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="8" style="color: var(--accent-crimson); text-align: center;">Failed to load facts.</td></tr>';
  }
}

async function loadDocuments() {
  const tbody = document.getElementById('documentsTableBody');
  const docFilter = document.getElementById('factDocFilter');
  tbody.innerHTML = '<tr><td colspan="7" style="color: var(--text-muted); text-align: center;">Loading...</td></tr>';

  try {
    const res = await fetch('/api/documents');
    const docs = await res.json();
    tbody.innerHTML = '';

    docFilter.innerHTML = '<option value="">All Documents</option>';
    docs.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d.id;
      opt.textContent = d.filename;
      docFilter.appendChild(opt);
    });

    if (docs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="color: var(--text-muted); text-align: center;">No documents yet. Upload a PDF above.</td></tr>';
      return;
    }

    docs.forEach(d => {
      const tr = document.createElement('tr');
      const sizeMb = (d.file_size / (1024 * 1024)).toFixed(2);
      const statusBadge = d.status === 'ready'
        ? '<span class="badge badge-emerald">Ready</span>'
        : (d.status === 'processing' ? '<span class="badge badge-amber">Processing...</span>' : '<span class="badge badge-crimson">Failed</span>');

      tr.innerHTML = `
        <td style="font-weight: 600;">${d.filename}</td>
        <td>${d.page_count}</td>
        <td>${sizeMb} MB</td>
        <td>${statusBadge}</td>
        <td><span class="badge badge-indigo">${d.fact_count}</span></td>
        <td style="color: var(--text-dim); font-size: 0.75rem;">${d.uploaded_at ? new Date(d.uploaded_at).toLocaleString() : ''}</td>
        <td>
          <button class="btn btn-secondary" style="padding: 0.25rem 0.6rem; font-size: 0.75rem;" onclick="deleteDocument('${d.id}')">
            🗑️ Delete
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="7" style="color: var(--accent-crimson); text-align: center;">Failed to load documents.</td></tr>';
  }
}

async function openEvidenceModal(factId) {
  try {
    const res = await fetch(`/api/facts/${factId}`);
    const fact = await res.json();

    document.getElementById('modalDocTitle').textContent = fact.doc_name || 'Document';
    document.getElementById('modalPageBadge').textContent = `Page ${fact.page}`;
    document.getElementById('modalFactTriple').textContent = `${fact.subject} — ${fact.predicate} — ${fact.value}`;
    document.getElementById('modalCharSpan').textContent = `[${fact.char_start} : ${fact.char_end}]`;
    document.getElementById('modalBbox').textContent = fact.bbox ? `[${fact.bbox.join(', ')}]` : 'N/A';

    const statusBadge = document.getElementById('modalGroundingStatus');
    if (fact.is_hallucinated_quote) {
      statusBadge.className = 'badge badge-crimson';
      statusBadge.textContent = 'Hallucination Flagged';
    } else {
      statusBadge.className = 'badge badge-emerald';
      statusBadge.textContent = 'Verified';
    }

    const pageText = fact.page_full_text || fact.quote;
    const quote = fact.quote;
    const box = document.getElementById('modalEvidenceText');

    if (pageText.includes(quote)) {
      const parts = pageText.split(quote);
      box.innerHTML = `${escapeHtml(parts[0])}<mark class="highlighted-quote">${escapeHtml(quote)}</mark>${escapeHtml(parts.slice(1).join(quote))}`;
    } else {
      box.innerHTML = `<mark class="highlighted-quote">${escapeHtml(quote)}</mark>\n\n${escapeHtml(pageText)}`;
    }

    document.getElementById('modalExtraJson').textContent = JSON.stringify(fact.extra || {}, null, 2);
    document.getElementById('evidenceModal').classList.add('open');
  } catch (err) {
    alert('Failed to load evidence details.');
  }
}

function closeModal(e) {
  if (e.target.id === 'evidenceModal') closeModalDirect();
}

function closeModalDirect() {
  document.getElementById('evidenceModal').classList.remove('open');
}

function initDropzone() {
  const dropzone = document.getElementById('dropzone');
  ['dragenter', 'dragover'].forEach(name => {
    dropzone.addEventListener(name, (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
  });
  ['dragleave', 'drop'].forEach(name => {
    dropzone.addEventListener(name, (e) => { e.preventDefault(); dropzone.classList.remove('dragover'); });
  });
  dropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files.length > 0) uploadFile(e.dataTransfer.files[0]);
  });
}

function handleFileSelect(e) {
  if (e.target.files.length > 0) uploadFile(e.target.files[0]);
}

async function uploadFile(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    alert('Please select a PDF file.');
    return;
  }

  const progress = document.getElementById('uploadProgress');
  const statusText = document.getElementById('uploadStatusText');
  progress.style.display = 'block';
  statusText.textContent = `Processing ${file.name}...`;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/documents', { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload failed');
    }
    statusText.textContent = `Done — ${file.name} ingested.`;
    setTimeout(() => { progress.style.display = 'none'; }, 3000);
    loadDocuments();
    loadStats();
  } catch (err) {
    alert(`Upload error: ${err.message}`);
    progress.style.display = 'none';
  }
}

async function deleteDocument(docId) {
  if (!confirm('Delete this document and all its facts?')) return;
  try {
    await fetch(`/api/documents/${docId}`, { method: 'DELETE' });
    loadDocuments();
    loadStats();
  } catch (err) {
    alert('Failed to delete document.');
  }
}

function debounceFactSearch() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(loadFacts, 300);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

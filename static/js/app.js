// API Base URL
const API_BASE = '';

// Toast Helper
function showToast(message, type = 'info') {
    const toast = document.getElementById('notification-toast');
    const toastBody = toast.querySelector('.toast-body');
    const toastHeader = toast.querySelector('.toast-header');

    toastBody.textContent = message;

    // Color coding
    toastHeader.className = 'toast-header';
    if (type === 'success') {
        toastHeader.classList.add('bg-success', 'text-white');
    } else if (type === 'error') {
        toastHeader.classList.add('bg-danger', 'text-white');
    } else if (type === 'warning') {
        toastHeader.classList.add('bg-warning');
    }

    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
}

// Load Settings
async function loadSettings() {
    try {
        const response = await fetch(`${API_BASE}/api/settings`);
        const settings = await response.json();

        document.getElementById('paperless-url').value = settings.PAPERLESS_URL || '';
        document.getElementById('paperless-token').value = settings.PAPERLESS_TOKEN || '';
        document.getElementById('ollama-url').value = settings.OLLAMA_URL || '';
        document.getElementById('ollama-model').value = settings.OLLAMA_MODEL || '';
    } catch (error) {
        console.error('Error loading settings:', error);
        showToast('Fehler beim Laden der Einstellungen', 'error');
    }
}

// Save Settings
document.getElementById('settings-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const settings = {
        PAPERLESS_URL: document.getElementById('paperless-url').value,
        PAPERLESS_TOKEN: document.getElementById('paperless-token').value,
        OLLAMA_URL: document.getElementById('ollama-url').value,
        OLLAMA_MODEL: document.getElementById('ollama-model').value
    };

    try {
        const response = await fetch(`${API_BASE}/api/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        const result = await response.json();

        if (result.success) {
            showToast('Einstellungen gespeichert', 'success');
        } else {
            showToast(result.message || 'Fehler beim Speichern', 'error');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        showToast('Fehler beim Speichern der Einstellungen', 'error');
    }
});

// Test Connection
async function testConnection(type) {
    const data = { type };

    if (type === 'paperless') {
        data.url = document.getElementById('paperless-url').value;
        data.token = document.getElementById('paperless-token').value;
    } else if (type === 'ollama') {
        data.url = document.getElementById('ollama-url').value;
        data.model = document.getElementById('ollama-model').value;
    }

    try {
        const response = await fetch(`${API_BASE}/api/test-connection`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            showToast(result.message, 'success');
            if (result.available_models) {
                showToast(`Verfügbare Modelle: ${result.available_models.join(', ')}`, 'info');
            }
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        console.error('Error testing connection:', error);
        showToast('Verbindungstest fehlgeschlagen', 'error');
    }
}

// Load Config (Document Types, Tags, Correspondents)
async function loadConfig() {
    try {
        const response = await fetch(`${API_BASE}/api/config`);
        const config = await response.json();

        // Document Types
        const docTypesList = document.getElementById('document-types-list');
        docTypesList.innerHTML = config.document_types
            .map(type => `<span class="badge bg-primary">${type}</span>`)
            .join('');

        // Person Tags
        const personTagsList = document.getElementById('person-tags-list');
        personTagsList.innerHTML = config.person_tags
            .map(tag => `<span class="badge bg-info">${tag}</span>`)
            .join('');

        // Correspondents
        const correspondentsList = document.getElementById('correspondents-list');
        correspondentsList.innerHTML = config.correspondents
            .map(corr => `<span class="badge bg-secondary">${corr}</span>`)
            .join('');
    } catch (error) {
        console.error('Error loading config:', error);
        showToast('Fehler beim Laden der Konfiguration', 'error');
    }
}

// Load Pending Documents
async function loadPendingDocuments() {
    const container = document.getElementById('pending-documents-list');
    container.innerHTML = '<div class="text-center"><div class="spinner-border text-primary"></div></div>';

    try {
        const response = await fetch(`${API_BASE}/api/documents/pending`);
        const data = await response.json();

        if (data.error) {
            container.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
            return;
        }

        if (data.pending_documents.length === 0) {
            container.innerHTML = '<div class="alert alert-info">Keine ausstehenden Dokumente gefunden</div>';
            return;
        }

        let html = `
            <div class="mb-3">
                <button class="btn btn-primary" onclick="processSelectedDocuments()">
                    <i class="bi bi-play-circle"></i> Ausgewählte verarbeiten
                </button>
                <button class="btn btn-outline-primary ms-2" onclick="selectAllDocuments()">
                    Alle auswählen
                </button>
            </div>
            <div class="list-group">
        `;

        data.pending_documents.forEach(doc => {
            html += `
                <div class="list-group-item">
                    <div class="form-check">
                        <input class="form-check-input document-checkbox" type="checkbox" value="${doc.id}" id="doc-${doc.id}">
                        <label class="form-check-label" for="doc-${doc.id}">
                            <strong>${doc.title}</strong>
                            <br>
                            <small class="text-muted">ID: ${doc.id} | Erstellt: ${doc.created || 'Unbekannt'}</small>
                        </label>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;

        // Update pending count in dashboard
        document.getElementById('stat-pending').textContent = data.count;

    } catch (error) {
        console.error('Error loading pending documents:', error);
        container.innerHTML = '<div class="alert alert-danger">Fehler beim Laden der Dokumente</div>';
    }
}

// Select All Documents
function selectAllDocuments() {
    const checkboxes = document.querySelectorAll('.document-checkbox');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => cb.checked = !allChecked);
}

// Process Selected Documents
async function processSelectedDocuments() {
    const checkboxes = document.querySelectorAll('.document-checkbox:checked');
    const documentIds = Array.from(checkboxes).map(cb => parseInt(cb.value));

    if (documentIds.length === 0) {
        showToast('Bitte wählen Sie mindestens ein Dokument aus', 'warning');
        return;
    }

    if (!confirm(`${documentIds.length} Dokument(e) verarbeiten?`)) {
        return;
    }

    showToast(`Verarbeite ${documentIds.length} Dokument(e)...`, 'info');

    try {
        const response = await fetch(`${API_BASE}/api/documents/process`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ document_ids: documentIds })
        });

        const data = await response.json();

        if (data.error) {
            showToast(data.error, 'error');
            return;
        }

        const successful = data.results.filter(r => r.success).length;
        const failed = data.results.length - successful;

        showToast(`Verarbeitung abgeschlossen: ${successful} erfolgreich, ${failed} fehlgeschlagen`, 'success');

        // Refresh
        loadPendingDocuments();
        refreshDashboard();

    } catch (error) {
        console.error('Error processing documents:', error);
        showToast('Fehler bei der Verarbeitung', 'error');
    }
}

// Process All Pending
async function processAllPending() {
    try {
        const response = await fetch(`${API_BASE}/api/documents/pending`);
        const data = await response.json();

        if (data.pending_documents.length === 0) {
            showToast('Keine ausstehenden Dokumente', 'info');
            return;
        }

        const documentIds = data.pending_documents.map(doc => doc.id);

        if (!confirm(`Alle ${documentIds.length} ausstehenden Dokumente verarbeiten?`)) {
            return;
        }

        showToast(`Verarbeite ${documentIds.length} Dokument(e)...`, 'info');

        const processResponse = await fetch(`${API_BASE}/api/documents/process`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ document_ids: documentIds })
        });

        const result = await processResponse.json();

        const successful = result.results.filter(r => r.success).length;
        const failed = result.results.length - successful;

        showToast(`Verarbeitung abgeschlossen: ${successful} erfolgreich, ${failed} fehlgeschlagen`, 'success');

        refreshDashboard();

    } catch (error) {
        console.error('Error processing all pending:', error);
        showToast('Fehler bei der Verarbeitung', 'error');
    }
}

// Load History
async function loadHistory() {
    const container = document.getElementById('history-list');
    container.innerHTML = '<div class="text-center"><div class="spinner-border text-primary"></div></div>';

    try {
        const response = await fetch(`${API_BASE}/api/processed-documents`);
        const data = await response.json();

        if (data.documents.length === 0) {
            container.innerHTML = '<div class="alert alert-info">Noch keine Dokumente verarbeitet</div>';
            return;
        }

        let html = '<div class="list-group">';

        data.documents.forEach(doc => {
            const statusBadge = doc.success
                ? '<span class="badge bg-success">Erfolgreich</span>'
                : '<span class="badge bg-danger">Fehlgeschlagen</span>';

            const classificationHtml = doc.classification_result
                ? Object.entries(doc.classification_result)
                    .map(([key, value]) => {
                        if (Array.isArray(value)) {
                            return `<strong>${key}:</strong> ${value.join(', ')}`;
                        }
                        return `<strong>${key}:</strong> ${value}`;
                    })
                    .join('<br>')
                : 'Keine Klassifizierung';

            html += `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h6>${doc.document_title}</h6>
                            <small class="text-muted">
                                ID: ${doc.document_id} |
                                Verarbeitet: ${new Date(doc.processed_at).toLocaleString('de-DE')}
                            </small>
                            <div class="mt-2">
                                ${statusBadge}
                                ${doc.error_message ? `<span class="badge bg-warning">${doc.error_message}</span>` : ''}
                            </div>
                            <div class="mt-2" style="font-size: 0.9rem;">
                                ${classificationHtml}
                            </div>
                        </div>
                        <button class="btn btn-sm btn-outline-danger" onclick="resetDocument(${doc.document_id})">
                            <i class="bi bi-arrow-counterclockwise"></i> Zurücksetzen
                        </button>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        container.innerHTML = html;

        // Update stats
        document.getElementById('stat-successful').textContent = data.statistics.successful;
        document.getElementById('stat-failed').textContent = data.statistics.failed;

    } catch (error) {
        console.error('Error loading history:', error);
        container.innerHTML = '<div class="alert alert-danger">Fehler beim Laden des Verlaufs</div>';
    }
}

// Reset Document
async function resetDocument(documentId) {
    if (!confirm(`Dokument ${documentId} zurücksetzen und erneut verarbeiten?`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/documents/reset/${documentId}`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            showToast(result.message, 'success');
            loadHistory();
            loadPendingDocuments();
            refreshDashboard();
        } else {
            showToast(result.message, 'error');
        }
    } catch (error) {
        console.error('Error resetting document:', error);
        showToast('Fehler beim Zurücksetzen', 'error');
    }
}

// Refresh Dashboard
async function refreshDashboard() {
    try {
        // Load statistics
        const response = await fetch(`${API_BASE}/api/processed-documents`);
        const data = await response.json();

        document.getElementById('stat-successful').textContent = data.statistics.successful;
        document.getElementById('stat-failed').textContent = data.statistics.failed;

        // Load pending count
        const pendingResponse = await fetch(`${API_BASE}/api/documents/pending`);
        const pendingData = await pendingResponse.json();
        document.getElementById('stat-pending').textContent = pendingData.count || 0;

        showToast('Dashboard aktualisiert', 'success');
    } catch (error) {
        console.error('Error refreshing dashboard:', error);
    }
}

// ============================================================
// Q&A / Semantic Search Functions
// ============================================================

async function loadIndexStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/qa/index-status`);
        const data = await response.json();

        document.getElementById('indexed-docs').textContent = data.indexed_documents || 0;
        document.getElementById('total-docs').textContent = data.total_paperless_documents || 0;
        document.getElementById('index-status').textContent = data.indexing_progress || 'Unbekannt';
    } catch (error) {
        console.error('Error loading index status:', error);
        document.getElementById('index-status').textContent = 'Fehler';
    }
}

async function startIndexing() {
    const btn = document.getElementById('btn-index');
    const originalHtml = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Indexiere...';

        const response = await fetch(`${API_BASE}/api/qa/index-documents`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');
            loadIndexStatus();
        } else {
            showToast('Indexierung fehlgeschlagen: ' + (data.error || 'Unbekannter Fehler'), 'error');
        }
    } catch (error) {
        console.error('Error indexing documents:', error);
        showToast('Fehler bei der Indexierung', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    }
}

async function testEmbedding() {
    const btn = document.getElementById('btn-test-embedding');
    const originalHtml = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Teste...';

        const response = await fetch(`${API_BASE}/api/qa/test-embedding`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            showToast('Embedding Service funktioniert! ✓', 'success');
        } else {
            showToast('Embedding Test fehlgeschlagen', 'error');
        }
    } catch (error) {
        console.error('Error testing embedding:', error);
        showToast('Fehler beim Testen', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    }
}

async function resetIndex() {
    // Bestätigung einholen
    if (!confirm('⚠️ WARNUNG: Dies löscht alle indexierten Dokumente!\n\nSie müssen danach alle Dokumente neu indexieren.\n\nMöchten Sie fortfahren?')) {
        return;
    }

    const btn = document.getElementById('btn-reset');
    const originalHtml = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Lösche...';

        const response = await fetch(`${API_BASE}/api/qa/reset-index`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            showToast('Index wurde zurückgesetzt! Bitte neu indexieren.', 'success');
            loadIndexStatus();
        } else {
            showToast('Fehler beim Zurücksetzen: ' + (data.message || 'Unbekannter Fehler'), 'error');
        }
    } catch (error) {
        console.error('Error resetting index:', error);
        showToast('Fehler beim Zurücksetzen', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    }
}

async function askQuestion() {
    const input = document.getElementById('question-input');
    const question = input.value.trim();

    if (!question) {
        showToast('Bitte geben Sie eine Frage ein', 'warning');
        return;
    }

    const btn = document.getElementById('btn-ask');
    const originalHtml = btn.innerHTML;
    const chatHistory = document.getElementById('chat-history');

    try {
        // Clear welcome message if first question
        if (chatHistory.querySelector('.text-center')) {
            chatHistory.innerHTML = '';
        }

        // Add user question to chat
        addMessageToChat('user', question);

        // Disable input
        btn.disabled = true;
        input.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Denke nach...';

        // Add loading message
        const loadingId = 'loading-' + Date.now();
        addMessageToChat('assistant', '<span class="spinner-border spinner-border-sm me-2"></span>Suche in Dokumenten...', loadingId);

        // Send request
        const response = await fetch(`${API_BASE}/api/qa/ask`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: question,
                n_context_docs: 5
            })
        });

        const data = await response.json();

        // Remove loading message
        const loadingMsg = document.getElementById(loadingId);
        if (loadingMsg) loadingMsg.remove();

        if (data.success) {
            // Add answer to chat
            let answerHtml = `<div>${data.answer}</div>`;

            // Add sources if available
            if (data.sources && data.sources.length > 0) {
                answerHtml += '<div class="mt-3"><small class="text-muted"><strong>Quellen:</strong></small><ul class="small mt-1">';
                data.sources.forEach(source => {
                    answerHtml += `<li>📄 ${source.title} (ID: ${source.doc_id})`;
                    if (source.correspondent) {
                        answerHtml += ` - ${source.correspondent}`;
                    }
                    answerHtml += '</li>';
                });
                answerHtml += '</ul></div>';
            }

            // Add confidence badge
            const confidenceColor = data.confidence === 'high' ? 'success' : data.confidence === 'medium' ? 'warning' : 'secondary';
            answerHtml += `<div class="mt-2"><span class="badge bg-${confidenceColor}">Konfidenz: ${data.confidence}</span></div>`;

            addMessageToChat('assistant', answerHtml);
        } else {
            addMessageToChat('assistant', `❌ Fehler: ${data.error || 'Unbekannter Fehler'}`);
        }

        // Clear input
        input.value = '';

    } catch (error) {
        console.error('Error asking question:', error);
        showToast('Fehler bei der Anfrage', 'error');

        // Remove loading message
        const loadingMsg = document.getElementById('loading-' + Date.now());
        if (loadingMsg) loadingMsg.remove();

        addMessageToChat('assistant', '❌ Es ist ein Fehler aufgetreten.');
    } finally {
        btn.disabled = false;
        input.disabled = false;
        btn.innerHTML = originalHtml;
    }
}

function addMessageToChat(role, content, id = null) {
    const chatHistory = document.getElementById('chat-history');

    const messageDiv = document.createElement('div');
    if (id) messageDiv.id = id;

    messageDiv.className = `mb-3 p-3 rounded ${role === 'user' ? 'bg-primary text-white ms-5' : 'bg-white me-5'}`;
    messageDiv.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';

    const roleLabel = role === 'user' ? '👤 Sie' : '🤖 Assistent';
    messageDiv.innerHTML = `
        <div class="fw-bold mb-2">${roleLabel}</div>
        <div>${content}</div>
    `;

    chatHistory.appendChild(messageDiv);

    // Scroll to bottom
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// ============================================================
// Advanced Search Functions
// ============================================================

async function loadMetadataOptions() {
    try {
        // Hole Paperless config (document types, tags, correspondents)
        const response = await fetch(`${API_BASE}/api/qa/metadata-options`);
        const data = await response.json();

        if (data.error) {
            showToast('Fehler beim Laden der Metadaten: ' + data.error, 'error');
            return;
        }

        // Document Types dropdown füllen
        const docTypeSelect = document.getElementById('filter-document-type');
        docTypeSelect.innerHTML = '<option value="">Alle Typen</option>';
        data.document_types.forEach(type => {
            const option = document.createElement('option');
            option.value = type;
            option.textContent = type;
            docTypeSelect.appendChild(option);
        });

        // Correspondents dropdown füllen
        const correspondentSelect = document.getElementById('filter-correspondent');
        correspondentSelect.innerHTML = '<option value="">Alle Korrespondenten</option>';
        data.correspondents.forEach(corr => {
            const option = document.createElement('option');
            option.value = corr;
            option.textContent = corr;
            correspondentSelect.appendChild(option);
        });

        // Tags multi-select füllen
        const tagsSelect = document.getElementById('filter-tags');
        tagsSelect.innerHTML = '';
        data.tags.forEach(tag => {
            const option = document.createElement('option');
            option.value = tag;
            option.textContent = tag;
            tagsSelect.appendChild(option);
        });

    } catch (error) {
        console.error('Error loading metadata options:', error);
        showToast('Fehler beim Laden der Filter-Optionen', 'error');
    }
}

function getSelectedFilters() {
    const filters = {};

    const docType = document.getElementById('filter-document-type').value;
    if (docType) filters.document_type = docType;

    const correspondent = document.getElementById('filter-correspondent').value;
    if (correspondent) filters.correspondent = correspondent;

    const tagsSelect = document.getElementById('filter-tags');
    const selectedTags = Array.from(tagsSelect.selectedOptions).map(opt => opt.value);
    if (selectedTags.length > 0) filters.tags = selectedTags;

    const year = document.getElementById('filter-year').value;
    if (year) filters.year = year;

    return filters;
}

async function performAdvancedSearch() {
    const query = document.getElementById('advanced-search-query').value.trim();
    const filters = getSelectedFilters();
    const resultsContainer = document.getElementById('advanced-search-results');
    const btn = document.getElementById('btn-advanced-search');

    if (!query) {
        showToast('Bitte geben Sie eine Suchanfrage ein', 'warning');
        return;
    }

    const originalHtml = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Suche...';

        resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border text-primary"></div><p class="mt-2">Suche läuft...</p></div>';

        // Sende Suchanfrage mit Filtern
        const response = await fetch(`${API_BASE}/api/qa/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: query,
                n_results: 10,
                filters: filters
            })
        });

        const data = await response.json();

        if (!data.success) {
            resultsContainer.innerHTML = `<div class="alert alert-danger">Fehler: ${data.error || 'Unbekannter Fehler'}</div>`;
            return;
        }

        // Ergebnisse anzeigen
        if (data.results.length === 0) {
            resultsContainer.innerHTML = `
                <div class="alert alert-info">
                    <i class="bi bi-info-circle"></i> Keine Dokumente gefunden.
                    <br><small>Versuchen Sie andere Filter oder Suchbegriffe.</small>
                </div>
            `;
            return;
        }

        let html = `<div class="mb-2"><strong>${data.results.length} Dokument(e) gefunden</strong></div><div class="list-group">`;

        data.results.forEach((result, idx) => {
            const metadata = result.metadata;
            const relevancePercent = Math.round((1 - (result.distance || 0)) * 100);

            html += `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h6 class="mb-1">${metadata.title || 'Unbekannt'}</h6>
                            <p class="mb-2 small text-muted">${result.text.substring(0, 200)}...</p>
                            <div class="d-flex gap-2 flex-wrap">
                                <span class="badge bg-primary">ID: ${result.doc_id}</span>
                                ${metadata.document_type ? `<span class="badge bg-info">${metadata.document_type}</span>` : ''}
                                ${metadata.correspondent ? `<span class="badge bg-secondary">${metadata.correspondent}</span>` : ''}
                                ${metadata.created ? `<span class="badge bg-light text-dark">${metadata.created}</span>` : ''}
                                ${result.chunk_number !== '0' ? `<span class="badge bg-warning">Chunk ${parseInt(result.chunk_number) + 1}/${result.total_chunks}</span>` : ''}
                            </div>
                        </div>
                        <div class="ms-3">
                            <div class="badge bg-success">${relevancePercent}% relevant</div>
                        </div>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        resultsContainer.innerHTML = html;

    } catch (error) {
        console.error('Error performing advanced search:', error);
        resultsContainer.innerHTML = '<div class="alert alert-danger">Fehler bei der Suche</div>';
        showToast('Fehler bei der Suche', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    }
}

async function askWithFilters() {
    const query = document.getElementById('advanced-search-query').value.trim();
    const filters = getSelectedFilters();

    if (!query) {
        showToast('Bitte geben Sie eine Frage ein', 'warning');
        return;
    }

    const resultsContainer = document.getElementById('advanced-search-results');

    try {
        resultsContainer.innerHTML = '<div class="text-center"><div class="spinner-border text-primary"></div><p class="mt-2">Beantworte Frage...</p></div>';

        // Sende Frage mit Filtern
        const response = await fetch(`${API_BASE}/api/qa/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: query,
                n_context_docs: 5,
                filters: filters
            })
        });

        const data = await response.json();

        if (!data.success) {
            resultsContainer.innerHTML = `<div class="alert alert-danger">Fehler: ${data.error || 'Unbekannter Fehler'}</div>`;
            return;
        }

        // Antwort anzeigen
        const confidenceColor = data.confidence === 'high' ? 'success' : data.confidence === 'medium' ? 'warning' : 'secondary';

        let html = `
            <div class="card bg-light">
                <div class="card-body">
                    <h5 class="card-title"><i class="bi bi-chat-dots"></i> Antwort</h5>
                    <p class="card-text">${data.answer}</p>
                    <div class="mt-3">
                        <span class="badge bg-${confidenceColor}">Konfidenz: ${data.confidence}</span>
                    </div>
                </div>
            </div>
        `;

        // Quellen hinzufügen
        if (data.sources && data.sources.length > 0) {
            html += '<div class="mt-3"><h6>Verwendete Quellen:</h6><div class="list-group">';
            data.sources.forEach(source => {
                html += `
                    <div class="list-group-item">
                        <div class="d-flex justify-content-between">
                            <div>
                                <strong>${source.title}</strong>
                                ${source.correspondent ? `<br><small class="text-muted">Von: ${source.correspondent}</small>` : ''}
                            </div>
                            <span class="badge bg-primary">ID: ${source.doc_id}</span>
                        </div>
                    </div>
                `;
            });
            html += '</div></div>';
        }

        resultsContainer.innerHTML = html;

    } catch (error) {
        console.error('Error asking with filters:', error);
        resultsContainer.innerHTML = '<div class="alert alert-danger">Fehler bei der Anfrage</div>';
        showToast('Fehler bei der Anfrage', 'error');
    }
}

function clearFilters() {
    document.getElementById('filter-document-type').value = '';
    document.getElementById('filter-correspondent').value = '';
    document.getElementById('filter-tags').selectedIndex = -1;
    document.getElementById('filter-year').value = '';
    document.getElementById('advanced-search-query').value = '';
    document.getElementById('advanced-search-results').innerHTML = `
        <div class="text-center text-muted">
            <i class="bi bi-search fs-1"></i>
            <p class="mt-2">Nutzen Sie Filter und Suche um Dokumente zu finden</p>
            <p class="small">Tipp: Kombinieren Sie mehrere Filter für präzisere Ergebnisse</p>
        </div>
    `;
    showToast('Filter zurückgesetzt', 'info');
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    loadConfig();
    refreshDashboard();

    // Load data when tabs are clicked
    document.querySelectorAll('[data-bs-toggle="pill"]').forEach(tab => {
        tab.addEventListener('shown.bs.tab', (event) => {
            const target = event.target.getAttribute('href');

            if (target === '#documents') {
                loadPendingDocuments();
            } else if (target === '#history') {
                loadHistory();
            } else if (target === '#config') {
                loadConfig();
            } else if (target === '#dashboard') {
                refreshDashboard();
            } else if (target === '#qa') {
                loadIndexStatus();
            } else if (target === '#advanced-search') {
                loadMetadataOptions();
            }
        });
    });
});

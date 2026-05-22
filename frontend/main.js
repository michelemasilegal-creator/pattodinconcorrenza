/* ── NAV MOBILE ─────────────────────────────────────────────────────────── */
const hamburger = document.getElementById('hamburger');
const navLinks = document.getElementById('nav-links');
hamburger.addEventListener('click', () => navLinks.classList.toggle('open'));
hamburger.addEventListener('keydown', e => { if (e.key === 'Enter') navLinks.classList.toggle('open'); });

/* ── PRIVACY MODAL ───────────────────────────────────────────────────────── */
const privacyModal = document.getElementById('privacy-modal');
const openPrivacy = () => privacyModal.classList.add('open');
const closePrivacy = () => privacyModal.classList.remove('open');
document.getElementById('privacy-link').addEventListener('click', e => { e.preventDefault(); openPrivacy(); });
document.getElementById('footer-privacy-link').addEventListener('click', e => { e.preventDefault(); openPrivacy(); });
document.getElementById('footer-privacy-link2').addEventListener('click', e => { e.preventDefault(); openPrivacy(); });
document.getElementById('modal-close').addEventListener('click', closePrivacy);
document.getElementById('modal-ok').addEventListener('click', closePrivacy);
privacyModal.addEventListener('click', e => { if (e.target === privacyModal) closePrivacy(); });

/* ── UPLOAD AREA ─────────────────────────────────────────────────────────── */
const fileInput = document.getElementById('file-input');
const dropArea = document.getElementById('drop-area');
const dropClick = document.getElementById('drop-click');
const fileSelected = document.getElementById('file-selected');
const fileNameDisplay = document.getElementById('file-name-display');
const gdprCb = document.getElementById('gdpr-cb');
const uploadBtn = document.getElementById('upload-btn');
const uploadError = document.getElementById('upload-error');

let selectedFile = null;

dropClick.addEventListener('click', () => fileInput.click());
dropArea.addEventListener('click', e => { if (e.target !== dropClick) fileInput.click(); });

fileInput.addEventListener('change', () => {
  if (fileInput.files.length > 0) setFile(fileInput.files[0]);
});

dropArea.addEventListener('dragover', e => { e.preventDefault(); dropArea.classList.add('drag-over'); });
dropArea.addEventListener('dragleave', () => dropArea.classList.remove('drag-over'));
dropArea.addEventListener('drop', e => {
  e.preventDefault();
  dropArea.classList.remove('drag-over');
  if (e.dataTransfer.files.length > 0) setFile(e.dataTransfer.files[0]);
});

function setFile(file) {
  selectedFile = file;
  fileNameDisplay.textContent = file.name;
  fileSelected.classList.add('visible');
  updateBtn();
}

gdprCb.addEventListener('change', updateBtn);

function updateBtn() {
  uploadBtn.disabled = !(selectedFile && gdprCb.checked);
}

/* ── ANALYZE ─────────────────────────────────────────────────────────────── */
uploadBtn.addEventListener('click', async () => {
  if (!selectedFile || !gdprCb.checked) return;
  showError('');
  uploadBtn.disabled = true;
  uploadBtn.innerHTML = '<span class="spinner"></span> Analisi in corso…';

  const fd = new FormData();
  fd.append('file', selectedFile);
  fd.append('gdpr_consent', 'true');
  fd.append('user_name', document.getElementById('user-name').value.trim());
  fd.append('user_email', document.getElementById('user-email').value.trim());

  try {
    const res = await fetch('/api/analyze', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Errore sconosciuto' }));
      throw new Error(err.detail || `Errore HTTP ${res.status}`);
    }
    const data = await res.json();
    renderResult(data);
    document.getElementById('result-box').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    showError(e.message || 'Errore durante l\'analisi. Riprova.');
  } finally {
    uploadBtn.disabled = false;
    uploadBtn.innerHTML = 'Analizza il patto';
    updateBtn();
  }
});

function showError(msg) {
  uploadError.textContent = msg;
  uploadError.style.display = msg ? 'block' : 'none';
}

/* ── RENDER RESULT ───────────────────────────────────────────────────────── */
function renderResult(data) {
  const box = document.getElementById('result-box');
  box.classList.add('visible');

  const { valido, punteggio = 0, sintesi, requisiti = {}, problemi = [], raccomandazioni, disclaimer } = data;

  const verdictClass = valido === true ? 'verdict-valid' : valido === false ? 'verdict-invalid' : 'verdict-uncertain';
  const verdictIcon  = valido === true ? '✅' : valido === false ? '❌' : '⚠️';
  const verdictText  = valido === true ? 'PATTO VALIDO' : valido === false ? 'PATTO NON VALIDO' : 'VALIDITÀ INCERTA';

  const req = [
    { key: 'forma_scritta',       label: 'Forma scritta' },
    { key: 'limiti_oggetto',      label: 'Limiti di oggetto' },
    { key: 'limiti_tempo_luogo',  label: 'Limiti di tempo e luogo' },
    { key: 'corrispettivo',       label: 'Corrispettivo' },
  ];

  const reqHtml = req.map(r => {
    const d = requisiti[r.key] || {};
    const ok = d.ok;
    const cls = ok === true ? 'ok' : ok === false ? 'fail' : 'uncertain';
    const icon = ok === true ? '✓' : ok === false ? '✗' : '?';
    return `
      <div class="req-check">
        <p class="req-check-label">${r.label}</p>
        <div class="req-check-status ${cls}"><span>${icon}</span> ${ok === true ? 'Presente' : ok === false ? 'Mancante / Invalido' : 'Non verificabile'}</div>
        <p>${d.note || ''}</p>
      </div>`;
  }).join('');

  const problemiHtml = problemi.length
    ? `<ul>${problemi.map(p => `<li>${p}</li>`).join('')}</ul>`
    : '<p style="color:var(--text-mid);font-size:15px">Nessun problema critico rilevato.</p>';

  const scoreColor = punteggio >= 70 ? '#2e7d32' : punteggio >= 40 ? '#f57f17' : '#c62828';

  box.innerHTML = `
    <div class="result-verdict ${verdictClass}">
      <span class="verdict-icon">${verdictIcon}</span>
      <div>
        <strong>${verdictText}</strong>
        <div>Punteggio di conformità: ${punteggio}/100</div>
      </div>
    </div>

    <p class="result-score">Conformità ai requisiti art. 2125 c.c.</p>
    <div class="score-bar-wrap">
      <div class="score-bar" id="score-bar" style="width:0;background:${scoreColor}"></div>
    </div>

    <p class="result-sintesi">${sintesi || ''}</p>

    <div class="req-checks">${reqHtml}</div>

    <div class="result-problems">
      <h4>Problemi rilevati</h4>
      ${problemiHtml}
    </div>

    <div class="result-raccomandazioni">
      <h4>Raccomandazioni</h4>
      <p>${raccomandazioni || ''}</p>
    </div>

    <div class="result-cta">
      <p>Hai bisogno di una valutazione professionale o vuoi sapere come difenderti?</p>
      <a href="#contatto" class="btn btn-primary">Contatta l'Avv. Masi</a>
    </div>

    <p class="result-disclaimer">${disclaimer || ''}</p>
  `;

  setTimeout(() => {
    const bar = document.getElementById('score-bar');
    if (bar) bar.style.width = punteggio + '%';
  }, 100);
}

/* ── CONTACT FORM ────────────────────────────────────────────────────────── */
document.getElementById('contact-form').addEventListener('submit', async e => {
  e.preventDefault();
  const btn = document.getElementById('contact-btn');
  const result = document.getElementById('contact-result');
  btn.disabled = true;
  btn.textContent = 'Invio in corso…';
  result.textContent = '';

  const fd = new FormData(e.target);

  try {
    const res = await fetch('/api/contact', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Errore invio');
    result.style.color = '#2e7d32';
    result.textContent = '✓ ' + data.message;
    e.target.reset();
  } catch (err) {
    result.style.color = 'var(--red)';
    result.textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Invia richiesta';
  }
});

/* ── SMOOTH NAV CLOSE ON LINK CLICK ─────────────────────────────────────── */
document.querySelectorAll('.nav-links a').forEach(a => {
  a.addEventListener('click', () => navLinks.classList.remove('open'));
});

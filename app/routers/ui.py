from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)

_HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CPF Validador</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🔍</text></svg>">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg: #0d1117;
      --surface: #161b22;
      --surface2: #1c2128;
      --border: #30363d;
      --text: #e6edf3;
      --muted: #7d8590;
      --accent: #1f6feb;
      --accent-h: #388bfd;
      --ok-bg: rgba(46,160,67,.12);
      --ok-text: #3fb950;
      --err-bg: rgba(218,54,51,.10);
      --err-text: #f85149;
      --r: 10px;
    }

    body {
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 48px 20px 80px;
    }

    .logo { font-size: 28px; margin-bottom: 6px; }

    h1 {
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -.3px;
      margin-bottom: 6px;
    }

    .sub { font-size: 13px; color: var(--muted); margin-bottom: 28px; text-align: center; }

    .wrap { width: 100%; max-width: 460px; }

    /* ── tabs ── */
    .tabs {
      display: flex;
      gap: 4px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 4px;
      margin-bottom: 14px;
    }

    .tab {
      flex: 1;
      text-align: center;
      padding: 8px;
      font-size: 13px;
      font-weight: 600;
      color: var(--muted);
      border-radius: 7px;
      cursor: pointer;
      transition: background .15s, color .15s;
      user-select: none;
    }

    .tab.active {
      background: var(--surface2);
      color: var(--text);
    }

    .tab-panel { display: none; }
    .tab-panel.active { display: block; }

    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 26px 26px 22px;
    }

    .field + .field { margin-top: 15px; }

    label {
      display: block;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: .07em;
      color: var(--muted);
      margin-bottom: 7px;
    }

    input {
      width: 100%;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 7px;
      padding: 11px 14px;
      color: var(--text);
      font-size: 15px;
      font-family: inherit;
      outline: none;
      transition: border-color .15s, box-shadow .15s;
    }

    input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(31,111,235,.15);
    }

    input::placeholder { color: var(--muted); }

    .hint { margin-top: 5px; font-size: 12px; color: var(--muted); }
    .hint code {
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 1px 5px;
      font-size: 11px;
    }

    button {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      width: 100%;
      background: var(--accent);
      color: #fff;
      border: none;
      border-radius: 7px;
      padding: 12px;
      font-size: 14px;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      margin-top: 20px;
      transition: background .15s;
    }

    button:hover:not(:disabled) { background: var(--accent-h); }
    button:disabled { opacity: .5; cursor: not-allowed; }

    /* ── log ── */
    .log-box {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 16px 20px;
      margin-top: 14px;
    }

    .log-head {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: .07em;
      color: var(--muted);
      margin-bottom: 12px;
      display: flex;
      justify-content: space-between;
    }

    .elapsed { font-variant-numeric: tabular-nums; }

    .step {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      font-size: 13px;
      padding: 4px 0;
      opacity: 0;
      transform: translateY(4px);
      transition: opacity .2s, transform .2s;
      line-height: 1.4;
    }

    .step.show { opacity: 1; transform: none; }

    .si {
      flex-shrink: 0;
      width: 18px; height: 20px;
      display: flex; align-items: center; justify-content: center;
    }

    .step.pending .si::after {
      content: '';
      display: block;
      width: 13px; height: 13px;
      border: 2px solid var(--border);
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: rot .6s linear infinite;
    }

    .step.done .si { color: var(--ok-text); }
    .step.done .si::after { content: '✓'; font-size: 14px; }
    .step.done > span:last-child { color: var(--muted); }

    .step.fail .si { color: var(--err-text); }
    .step.fail .si::after { content: '✕'; font-size: 14px; }
    .step.fail > span:last-child { color: var(--err-text); }

    @keyframes rot { to { transform: rotate(360deg); } }

    /* ── result card ── */
    .result-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      overflow: hidden;
      margin-top: 14px;
    }

    .result-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 15px 18px 12px;
      border-bottom: 1px solid var(--border);
    }

    .result-name { font-weight: 700; font-size: 16px; }

    .result-body { padding: 4px 18px 14px; }

    .row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 9px 0;
      font-size: 13.5px;
      border-bottom: 1px solid var(--border);
      gap: 12px;
    }

    .row:last-child { border-bottom: none; }
    .row-l { color: var(--muted); white-space: nowrap; }
    .row-v { font-weight: 500; text-align: right; font-variant-numeric: tabular-nums; }

    .meta { font-size: 12px; color: var(--muted); margin-top: 10px; padding: 0 2px; display: flex; gap: 16px; flex-wrap: wrap; }

    /* ── history ── */
    .hist-empty {
      text-align: center;
      color: var(--muted);
      font-size: 13px;
      padding: 32px 0;
    }

    .hist-actions {
      display: flex;
      justify-content: flex-end;
      margin-bottom: 10px;
    }

    .hist-clear {
      background: none;
      border: 1px solid var(--border);
      border-radius: 5px;
      color: var(--muted);
      font-size: 11px;
      font-family: inherit;
      padding: 3px 8px;
      cursor: pointer;
      margin-top: 0;
      width: auto;
      transition: color .15s, border-color .15s;
    }

    .hist-clear:hover { color: var(--err-text); border-color: var(--err-text); }

    .hist-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 9px 10px;
      border-radius: 7px;
      cursor: pointer;
      transition: background .12s;
      gap: 12px;
    }

    .hist-item:hover { background: var(--surface2); }

    .hist-nome {
      font-size: 13.5px;
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      flex: 1;
    }

    .hist-cpf {
      font-size: 12px;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }

    .hist-time {
      font-size: 11px;
      color: var(--muted);
      white-space: nowrap;
    }

    .err-box {
      background: var(--err-bg);
      border: 1px solid rgba(218,54,51,.25);
      border-radius: var(--r);
      padding: 14px 18px;
      font-size: 14px;
      color: var(--err-text);
      margin-top: 14px;
    }

    .spin {
      width: 15px; height: 15px;
      border: 2px solid rgba(255,255,255,.3);
      border-top-color: #fff;
      border-radius: 50%;
      animation: rot .65s linear infinite;
      flex-shrink: 0;
    }
  </style>
</head>
<body>

  <div class="logo">🔍</div>
  <h1>CPF Validador</h1>
  <p class="sub">Verifique se um CPF é válido e a quem pertence</p>

  <div class="wrap">
    <div class="tabs">
      <div class="tab active" id="tab-consultar" onclick="switchTab('consultar')">Consultar</div>
      <div class="tab"        id="tab-historico" onclick="switchTab('historico')">Histórico</div>
    </div>

    <!-- aba consultar -->
    <div class="tab-panel active" id="panel-consultar">
      <div class="card">
        <div class="field">
          <label>CPF</label>
          <input id="cpf" type="text" placeholder="000.000.000-00"
                 spellcheck="false" autocomplete="off" inputmode="numeric" />
          <p class="hint">Dígito ilegível? Use <code>X</code> — ex: <code>000.XX0.000-XX</code></p>
        </div>
        <div class="field">
          <label>Nome <span style="font-weight:400;text-transform:none;letter-spacing:0">(opcional)</span></label>
          <input id="nome" type="text" placeholder="Nome completo da pessoa" autocomplete="off" />
          <p class="hint">Confirma se o CPF pertence a esta pessoa</p>
        </div>
        <button id="btn" onclick="verificar()">Verificar</button>
      </div>

      <div id="log-box" class="log-box" style="display:none">
        <div class="log-head">
          <span>Progresso</span>
          <span class="elapsed" id="elapsed">0.0s</span>
        </div>
        <div id="steps"></div>
      </div>

      <div id="out"></div>
    </div>

    <!-- aba histórico -->
    <div class="tab-panel" id="panel-historico">
      <div class="card">
        <div class="hist-actions">
          <button class="hist-clear" onclick="clearHistory()">Limpar histórico</button>
        </div>
        <div id="hist-list"></div>
      </div>
    </div>
  </div>

  <script>
    const $cpf    = document.getElementById('cpf');
    const $nome   = document.getElementById('nome');
    const $btn    = document.getElementById('btn');
    const $out    = document.getElementById('out');
    const $logBox = document.getElementById('log-box');
    const $steps  = document.getElementById('steps');
    const $el     = document.getElementById('elapsed');

    /* ── CPF mask ── */
    $cpf.addEventListener('input', function() {
      const prev = this.value, pos = this.selectionStart;
      let raw = prev.replace(/[^\dxX]/g,'').toUpperCase().slice(0,11);
      let fmt = raw;
      if (raw.length > 9)      fmt = raw.slice(0,3)+'.'+raw.slice(3,6)+'.'+raw.slice(6,9)+'-'+raw.slice(9);
      else if (raw.length > 6) fmt = raw.slice(0,3)+'.'+raw.slice(3,6)+'.'+raw.slice(6);
      else if (raw.length > 3) fmt = raw.slice(0,3)+'.'+raw.slice(3);
      this.value = fmt;
      const d = fmt.length - prev.length;
      this.setSelectionRange(pos+d, pos+d);
    });

    [$cpf, $nome].forEach(el => el.addEventListener('keydown', e => { if(e.key==='Enter') verificar(); }));

    /* ── timer ── */
    let _t = null;
    function startTimer() {
      const t0 = Date.now();
      $el.textContent = '0.0s';
      _t = setInterval(() => { $el.textContent = ((Date.now()-t0)/1000).toFixed(1)+'s'; }, 100);
    }
    function stopTimer() { clearInterval(_t); }

    /* ── steps ── */
    function resetLog() { $steps.innerHTML=''; $logBox.style.display='none'; $el.textContent='0.0s'; }

    function addStep(txt) {
      $logBox.style.display = 'block';
      const el = document.createElement('div');
      el.className = 'step pending';
      el.innerHTML = `<span class="si"></span><span>${txt}</span>`;
      $steps.appendChild(el);
      requestAnimationFrame(() => el.classList.add('show'));
      return el;
    }

    function doneStep(el, txt) { el.className='step show done'; if(txt) el.querySelector('span:last-child').textContent=txt; }
    function failStep(el, txt) { el.className='step show fail'; if(txt) el.querySelector('span:last-child').textContent=txt; }

    const delay = ms => new Promise(r => setTimeout(r, ms));
    const post  = (path, body) => fetch(path, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });

    /* ── main ── */
    async function verificar() {
      const cpf  = $cpf.value.trim();
      const nome = $nome.value.trim() || null;
      if (!cpf) { $cpf.focus(); return; }

      $btn.disabled = true;
      $btn.innerHTML = '<span class="spin"></span>Verificando…';
      $out.innerHTML = '';
      resetLog();
      startTimer();

      const hasMask = /[xX]/.test(cpf);
      const xs = (cpf.replace(/[^\dxX]/gi,'').match(/x/gi)||[]).length;

      try {
        /* 1 — validar */
        const s1 = addStep('Validando CPF…');
        await delay(250);

        if (!hasMask) {
          const vd = await (await post('/cpf/validate', {cpf})).json();
          if (!vd.valido) {
            failStep(s1, `CPF inválido — ${vd.mensagem}`);
            stopTimer();
            $out.innerHTML = `<div class="err-box">✕ CPF matematicamente inválido — verifique os dígitos.</div>`;
            return;
          }
          doneStep(s1, `CPF válido — ${vd.cpf_formatado}`);
        } else {
          doneStep(s1, `Máscara: ${xs} dígito${xs>1?'s':''} desconhecido${xs>1?'s':''}`);
        }

        /* 2 — candidatos */
        const s2 = addStep(hasMask
          ? `Calculando combinações para ${xs} dígito${xs>1?'s':''} desconhecido${xs>1?'s':''}…`
          : 'Preparando consulta…');
        await delay(300);
        doneStep(s2, hasMask ? 'Calculando…' : '1 CPF');

        /* 3 — conectar */
        const s3 = addStep('Conectando ao servidor…');
        await delay(300);
        doneStep(s3, 'Conexão estabelecida');

        /* 4 — captcha (fetch real) */
        const s4 = addStep(hasMask ? 'Resolvendo CAPTCHAs em paralelo…' : 'Resolvendo CAPTCHA…');

        let resultados = [];
        let totalCandidatos = 1;

        if (hasMask) {
          const mascara = cpf.toUpperCase().replace(/X/g,'*');
          const res  = await post('/trt3/buscar-por-mascara', {mascara, nome, workers:8});
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || 'Erro na consulta');
          totalCandidatos = data.candidatos_gerados || '?';
          s2.querySelector('span:last-child').textContent = `${totalCandidatos} combinação${totalCandidatos!=1?'s':''} calculada${totalCandidatos!=1?'s':''}`;
          doneStep(s4, `${totalCandidatos} CAPTCHA${totalCandidatos!=1?'s':''} resolvido${totalCandidatos!=1?'s':''}`);
          resultados = Object.values(data.matches || {});
        } else {
          const res  = await post('/trt3/feitos', {cpf});
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || 'Erro na consulta');
          doneStep(s4, 'CAPTCHA resolvido');
          if (data.nome_certidao) resultados = [data];
        }

        stopTimer();

        if (!resultados.length) {
          $out.innerHTML = `<div class="err-box">⚠️ Nenhum resultado encontrado${nome ? ` para "${nome}"` : ''}${hasMask ? ` — ${totalCandidatos} candidatos testados` : ''}.</div>`;
          return;
        }

        const cards = resultados.map(d => {
          const nomeReal = d.nome_certidao || '—';
          const cpfFmt   = d.cpf || cpf;
          const bate     = nome ? nomeMatch(nomeReal, nome) : null;

          const indicator = bate === true
            ? `<span style="color:var(--ok-text);font-weight:600;font-size:13px">✓ Confirmado</span>`
            : bate === false
            ? `<span style="color:var(--err-text);font-weight:600;font-size:13px">✕ Nome não bate</span>`
            : '';

          const pdfLink = d.pdf_url
            ? `<a href="${d.pdf_url}" target="_blank" style="color:var(--accent);text-decoration:none;font-weight:500">↗ Abrir PDF</a>`
            : '—';

          return `
          <div class="result-card">
            <div class="result-head">
              <span class="result-name">${nomeReal}</span>
              ${indicator}
            </div>
            <div class="result-body">
              ${row('CPF', cpfFmt)}
              ${d.numero_certidao ? row('Nº da certidão', d.numero_certidao) : ''}
              ${d.pdf_url         ? row('Certidão PDF', pdfLink) : ''}
            </div>
          </div>`;
        }).join('');

        $out.innerHTML = cards;
        const duracaoS = parseFloat($el.textContent);
        resultados.forEach(d => {
          if (d.nome_certidao) saveToHistory(d.cpf || cpf, d.nome_certidao, d.numero_certidao || null, duracaoS || null);
        });
        if (hasMask && resultados.length > 1) {
          $out.innerHTML += `<div class="meta">${resultados.length} resultados encontrados · ${totalCandidatos} candidatos testados · ${$el.textContent}</div>`;
        }

      } catch(e) {
        stopTimer();
        $out.innerHTML = `<div class="err-box">⚠️ ${e.message}</div>`;
      } finally {
        $btn.disabled = false;
        $btn.textContent = 'Verificar';
      }
    }

    /* ── tabs ── */
    function switchTab(name) {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      document.getElementById('tab-' + name).classList.add('active');
      document.getElementById('panel-' + name).classList.add('active');
      if (name === 'historico') renderHistory();
    }

    /* ── history (server-side) ── */
    const $histList = document.getElementById('hist-list');

    async function saveToHistory(cpf, nome, numero_certidao, duracao_segundos) {
      await fetch('/history/save', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ cpf, nome, numero_certidao, duracao_segundos })
      }).catch(() => {});
    }

    async function clearHistory() {
      await fetch('/history/', { method: 'DELETE' }).catch(() => {});
      renderHistory();
    }

    function fmtDt(iso) {
      if (!iso) return '—';
      const d = new Date(iso);
      const today = new Date();
      const hm = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
      if (d.toDateString() === today.toDateString()) return 'Hoje ' + hm;
      return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' }) + ' ' + hm;
    }

    async function renderHistory() {
      $histList.innerHTML = '<div class="hist-empty">Carregando…</div>';
      try {
        const res  = await fetch('/history/');
        const data = await res.json();
        const entries = data.entries || [];
        if (!entries.length) {
          $histList.innerHTML = '<div class="hist-empty">Nenhuma consulta registrada ainda.</div>';
          return;
        }
        $histList.innerHTML = entries.map(h => `
          <div class="hist-item" onclick="fillFromHistory('${h.cpf}','${(h.nome||'').replace(/'/g,"\\'")}')">
            <div style="flex:1;min-width:0">
              <div class="hist-nome">${h.nome || '—'}</div>
              <div style="font-size:12px;color:var(--muted);margin-top:2px;display:flex;gap:10px;flex-wrap:wrap">
                <span>${h.cpf}</span>
                ${h.numero_certidao ? `<span>Certidão ${h.numero_certidao}</span>` : ''}
                ${h.ultima_duracao_s != null ? `<span>${h.ultima_duracao_s}s</span>` : ''}
              </div>
            </div>
            <div style="text-align:right;flex-shrink:0">
              <div class="hist-time">${fmtDt(h.ultima_consulta)}</div>
              <div style="font-size:11px;color:var(--muted);margin-top:2px">${h.consultas}× consultado</div>
            </div>
          </div>`).join('');
      } catch {
        $histList.innerHTML = '<div class="hist-empty">Erro ao carregar histórico.</div>';
      }
    }

    function fillFromHistory(cpf, nome) {
      switchTab('consultar');
      $cpf.value = cpf;
      $nome.value = nome || '';
      $out.innerHTML = '';
      $logBox.style.display = 'none';
      $steps.innerHTML = '';
    }

    function nomeMatch(a, b) {
      const n = s => s.toUpperCase().normalize('NFD').replace(/[̀-ͯ]/g,'').trim();
      const na = n(a), nb = n(b);
      return na === nb || nb.split(/\s+/).every(w => na.includes(w));
    }

    function row(l, v) {
      return `<div class="row"><span class="row-l">${l}</span><span class="row-v">${v}</span></div>`;
    }
  </script>
</body>
</html>"""


@router.get("/ui", response_class=HTMLResponse)
async def ui():
    return _HTML

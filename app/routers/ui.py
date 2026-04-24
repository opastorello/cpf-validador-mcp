from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.auth import _TOKEN

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
      --ok-bg: rgba(255,255,255,.05);
      --ok-text: #7d8590;
      --err-bg: rgba(255,255,255,.04);
      --err-text: #7d8590;
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
      text-align: center;
    }

    .sub { font-size: 13px; color: var(--muted); margin-bottom: 28px; text-align: center; }

    #main-content {
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 100%;
    }

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

    .step.done .si { color: var(--muted); }
    .step.done .si::after { content: '✓'; font-size: 14px; }
    .step.done > span:last-child { color: var(--muted); }

    .step.fail .si { color: var(--muted); }
    .step.fail .si::after { content: '✕'; font-size: 14px; }
    .step.fail > span:last-child { color: var(--muted); }

    @keyframes rot { to { transform: rotate(360deg); } }

    /* ── result card ── */
    .result-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      overflow: hidden;
      margin-top: 14px;
    }

    .result-card--mismatch {
      border-color: #f0883e;
      border-left: 3px solid #f0883e;
      background: rgba(240, 136, 62, 0.04);
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
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }

    .toggle-wrap {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: var(--muted);
      user-select: none;
      cursor: pointer;
    }

    .toggle {
      position: relative;
      width: 32px;
      height: 18px;
      flex-shrink: 0;
    }

    .toggle input { display: none; }

    .toggle-track {
      position: absolute;
      inset: 0;
      background: var(--border);
      border-radius: 9px;
      transition: background .2s;
    }

    .toggle input:checked + .toggle-track { background: var(--accent); }

    .toggle-thumb {
      position: absolute;
      top: 3px; left: 3px;
      width: 12px; height: 12px;
      background: #fff;
      border-radius: 50%;
      transition: left .2s;
    }

    .toggle input:checked ~ .toggle-thumb { left: 17px; }

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

    .hist-clear:hover { color: var(--text); border-color: var(--muted); }

    .hist-del {
      background: none;
      border: none;
      color: var(--muted);
      font-size: 18px;
      line-height: 1;
      cursor: pointer;
      padding: 4px 7px;
      margin: 0;
      width: auto;
      margin-top: 0;
      border-radius: 5px;
      flex-shrink: 0;
      transition: color .15s, background .15s;
    }

    .hist-del:hover { color: var(--text); background: var(--surface2); }

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
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 14px 18px;
      font-size: 14px;
      color: var(--muted);
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

  <!-- gate: shown only when AUTH_REQUIRED and no token stored -->
  <div id="gate" style="display:none;width:100%;max-width:400px;text-align:center">
    <div class="logo">🔒</div>
    <h1>Acesso restrito</h1>
    <p class="sub">Informe o API Token para continuar</p>
    <div class="card" style="margin-top:20px">
      <div class="field">
        <label>API Token</label>
        <input id="gate-token" type="password" placeholder="Token de acesso" autocomplete="off" />
      </div>
      <button id="btn-gate" onclick="gateLogin()" style="margin-top:14px">Entrar</button>
      <div id="gate-msg" style="display:none;margin-top:10px;font-size:13px"></div>
    </div>
  </div>

  <!-- main: hidden until authenticated -->
  <div id="main-content">
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
          <label class="toggle-wrap" title="Salvar automaticamente as consultas no histórico">
            <span class="toggle">
              <input type="checkbox" id="toggle-hist" onchange="setHistoryEnabled(this.checked)">
              <span class="toggle-track"></span>
              <span class="toggle-thumb"></span>
            </span>
            Salvar histórico
          </label>
          <button class="hist-clear" onclick="clearHistory()">Limpar histórico</button>
        </div>
        <div id="hist-list"></div>
      </div>
    </div>
  </div>
  </div><!-- /main-content -->

  <footer style="text-align:center;padding:20px 0 16px;font-size:12px;color:var(--muted);">
    <a href="https://github.com/opastorello/cpf-validador" target="_blank" rel="noopener"
       style="color:var(--muted);text-decoration:none;display:inline-flex;align-items:center;gap:6px;">
      <svg height="16" width="16" viewBox="0 0 16 16" fill="currentColor">
        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
        0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13
        -.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66
        .07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15
        -.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27
        .68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12
        .51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48
        0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
      </svg>
      opastorello/cpf-validador
    </a>
  </footer>

  <script>
    const esc = s => String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    const safeUrl = u => (u && /^https?:\/\//i.test(u)) ? u : '#';

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
    const AUTH_REQUIRED = __AUTH_REQUIRED__;
    const getToken = () => localStorage.getItem('api_token') || '';
    const authH = () => { const t = getToken(); return t ? {'Authorization': 'Bearer ' + t} : {}; };
    const post  = (path, body) => fetch(path, { method:'POST', headers:{'Content-Type':'application/json', ...authH()}, body:JSON.stringify(body) });

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
          $out.innerHTML = `<div class="err-box">⚠️ Nenhum resultado encontrado${nome ? ` para "${esc(nome)}"` : ''}${hasMask ? ` — ${esc(String(totalCandidatos))} candidatos testados` : ''}.</div>`;
          return;
        }

        const cards = resultados.map(d => {
          const nomeReal = d.nome_certidao || '—';
          const cpfFmt   = d.cpf || cpf;
          const bate     = nome ? nomeMatch(nomeReal, nome) : null;

          const indicator = bate === true
            ? `<span style="color:#3fb950;font-weight:500;font-size:13px">✓ Confirmado</span>`
            : bate === false
            ? `<span style="color:#f0883e;font-weight:600;font-size:13px">✕ Nome não bate</span>`
            : '';

          const pdfLink = d.pdf_url
            ? `<a href="${safeUrl(d.pdf_url)}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);text-decoration:none;font-weight:500">↗ Abrir PDF</a>`
            : '—';

          const cardClass = bate === false ? 'result-card result-card--mismatch' : 'result-card';

          return `
          <div class="${cardClass}">
            <div class="result-head">
              <span class="result-name">${esc(nomeReal)}</span>
              ${indicator}
            </div>
            <div class="result-body">
              ${row('CPF', esc(cpfFmt))}
              ${d.numero_certidao ? row('Nº da certidão', esc(d.numero_certidao)) : ''}
              ${d.pdf_url         ? row('Certidão PDF', pdfLink) : ''}
              ${bate === false ? row('⚠️ Nome buscado', `<span style="color:#f0883e;font-weight:500">${esc(nome)}</span>`) : ''}
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
        $out.innerHTML = `<div class="err-box">⚠️ ${esc(e.message)}</div>`;
      } finally {
        $btn.disabled = false;
        $btn.textContent = 'Verificar';
      }
    }

    /* ── gate ── */
    function updateTabLock() {
      const locked = AUTH_REQUIRED && !getToken();
      document.getElementById('gate').style.display         = locked ? 'block' : 'none';
      document.getElementById('main-content').style.display = locked ? 'none' : '';
    }

    async function gateLogin() {
      const tok = document.getElementById('gate-token').value.trim();
      if (!tok) return;
      const btn = document.getElementById('btn-gate');
      const msg = document.getElementById('gate-msg');
      btn.disabled = true;
      btn.textContent = 'Validando…';
      try {
        const res = await fetch('/history/', { headers: { 'Authorization': 'Bearer ' + tok } });
        if (res.status === 401) {
          showGateMsg('✕ Token inválido.', 'var(--err-text)');
          btn.disabled = false; btn.textContent = 'Entrar';
          return;
        }
      } catch {
        showGateMsg('⚠ Erro ao validar.', 'var(--err-text)');
        btn.disabled = false; btn.textContent = 'Entrar';
        return;
      }
      localStorage.setItem('api_token', tok);
      btn.disabled = false; btn.textContent = 'Entrar';
      updateTabLock();
    }

    function showGateMsg(text, color) {
      const msg = document.getElementById('gate-msg');
      msg.textContent = text; msg.style.color = color; msg.style.display = 'block';
      setTimeout(() => { msg.style.display = 'none'; }, 3000);
    }

    /* init */
    document.getElementById('gate-token').addEventListener('keydown', e => { if (e.key === 'Enter') gateLogin(); });
    updateTabLock();

    /* ── tabs ── */
    function switchTabRaw(name) {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      document.getElementById('tab-' + name).classList.add('active');
      document.getElementById('panel-' + name).classList.add('active');
      if (name === 'historico') { initHistoryToggle(); renderHistory(); }
    }

    function switchTab(name) {
      if (AUTH_REQUIRED && !getToken()) return;
      switchTabRaw(name);
    }

    /* ── history (server-side) ── */
    const $histList = document.getElementById('hist-list');

    const isHistoryEnabled = () => localStorage.getItem('history_enabled') !== 'false';

    function setHistoryEnabled(val) {
      localStorage.setItem('history_enabled', val ? 'true' : 'false');
    }

    function initHistoryToggle() {
      document.getElementById('toggle-hist').checked = isHistoryEnabled();
    }

    async function saveToHistory(cpf, nome, numero_certidao, duracao_segundos) {
      if (!isHistoryEnabled()) return;
      await fetch('/history/save', {
        method: 'POST',
        headers: {'Content-Type':'application/json', ...authH()},
        body: JSON.stringify({ cpf, nome, numero_certidao, duracao_segundos })
      }).catch(() => {});
    }

    async function clearHistory() {
      await fetch('/history/', { method: 'DELETE', headers: {...authH()} }).catch(() => {});
      renderHistory();
    }

    async function deleteHistoryEntry(cpf) {
      await fetch('/history/' + encodeURIComponent(cpf), { method: 'DELETE', headers: {...authH()} }).catch(() => {});
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
        const res  = await fetch('/history/', { headers: {...authH()} });
        const data = await res.json();
        const entries = data.entries || [];
        if (!entries.length) {
          $histList.innerHTML = '<div class="hist-empty">Nenhuma consulta registrada ainda.</div>';
          return;
        }
        $histList.innerHTML = entries.map(h => `
          <div class="hist-item" onclick="fillFromHistory('${esc(h.cpf)}','${esc(h.nome||'')}')">
            <div style="flex:1;min-width:0">
              <div class="hist-nome">${esc(h.nome) || '—'}</div>
              <div style="font-size:12px;color:var(--muted);margin-top:2px;display:flex;gap:10px;flex-wrap:wrap">
                <span>${esc(h.cpf)}</span>
                ${h.numero_certidao ? `<span>Certidão ${esc(h.numero_certidao)}</span>` : ''}
                ${h.ultima_duracao_s != null ? `<span>${esc(h.ultima_duracao_s)}s</span>` : ''}
              </div>
            </div>
            <div style="text-align:right;flex-shrink:0">
              <div class="hist-time">${fmtDt(h.ultima_consulta)}</div>
              <div style="font-size:11px;color:var(--muted);margin-top:2px">${esc(h.consultas)}× consultado</div>
            </div>
            <button class="hist-del" title="Remover entrada"
              onclick="event.stopPropagation(); deleteHistoryEntry('${esc(h.cpf)}')">×</button>
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


@router.get("/", response_class=HTMLResponse)
async def ui():
    auth_required = "true" if _TOKEN else "false"
    return _HTML.replace("__AUTH_REQUIRED__", auth_required)

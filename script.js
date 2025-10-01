const API = 'http://localhost:8000';
document.getElementById('apiBase').textContent = API;
const $ = (id) => document.getElementById(id);
const statusEl = $('status');
const tbody = document.querySelector('#results tbody');

$('searchBtn').onclick = async () => {
  const query = $('query').value.trim();
  if (!query) return alert('Enter a search query');
  try {
    statusEl.textContent = 'Searching...';
    const r = await fetch(API + '/api/search', {
      method:'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({query, count: 20})
    });
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    $('urls').value = data.urls.join('\n');
    statusEl.textContent = `Loaded ${data.urls.length} URLs from search.`;
  } catch (e) {
    console.error(e);
    statusEl.textContent = 'Search failed. Add a key or upload a CSV.';
  }
};

$('loadCsv').onclick = async () => {
  const f = $('csvfile').files[0];
  if (!f) return alert('Choose a CSV file with a url column');
  const text = await f.text();
  const lines = text.split(/\r?\n/);
  const header = (lines.shift()||'').split(',').map(s=>s.trim().toLowerCase());
  const idx = header.indexOf('url');
  if (idx === -1) return alert('CSV needs a "url" column');
  const urls = [];
  for (const line of lines) {
    if (!line.trim()) continue;
    const cols = line.split(',');
    const u = cols[idx]?.trim();
    if (u) urls.push(u);
  }
  $('urls').value = urls.join('\n');
  statusEl.textContent = `Loaded ${urls.length} URLs from CSV.`;
};

$('scrapeBtn').onclick = async () => {
  const urls = $('urls').value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  if (!urls.length) return alert('Add some URLs first');
  const payload = {
    urls,
    render: $('render').checked,
    concurrency: parseInt($('concurrency').value || '5', 10),
    timeout_ms: parseInt($('timeout').value || '12000', 10),
  };
  const queue = $('queue').checked;
  try {
    statusEl.textContent = queue ? 'Queueing job...' : 'Scraping...';
    if (queue) {
      const r = await fetch(API + '/api/jobs', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      if (!r.ok) throw new Error(await r.text());
      const { job_id } = await r.json();
      statusEl.textContent = 'Queued: ' + job_id + ' (polling...)';
      await pollJob(job_id);
    } else {
      const r = await fetch(API + '/api/scrape', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      renderRows(data.results);
      statusEl.textContent = 'Done.';
    }
  } catch (e) {
    console.error(e);
    statusEl.textContent = 'Error: ' + e.message;
  }
};

async function pollJob(job_id) {
  let tries = 0;
  while (tries < 600) {
    await new Promise(r => setTimeout(r, 2000));
    tries++;
    const r = await fetch(API + '/api/jobs/' + job_id);
    if (!r.ok) { statusEl.textContent = 'Job not found.'; return; }
    const s = await r.json();
    statusEl.textContent = `Job ${s.id}: ${s.status}`;
    if (s.status === 'finished') {
      const rr = await fetch(API + '/api/jobs/' + job_id + '/results');
      const data = await rr.json();
      renderRows(data.results || []);
      statusEl.textContent = 'Finished.';
      return;
    }
  }
  statusEl.textContent = 'Timed out waiting for job.';
}

function renderRows(rows) {
  tbody.innerHTML = '';
  for (const r of rows) {
    const tr = document.createElement('tr');
    const td = (v) => { const x=document.createElement('td'); x.textContent=v||''; return x; };
    tr.appendChild(td(r.org||''));
    tr.appendChild(td(r.url||''));
    tr.appendChild(td(r.title||''));
    tr.appendChild(td((r.emails||[]).join('; ')));
    tr.appendChild(td((r.phones||[]).join('; ')));
    tr.appendChild(td((r.socials||[]).join('; ')));
    tr.appendChild(td(r.ok ? '✓' : ''));
    tr.appendChild(td(r.error||''));
    tbody.appendChild(tr);
  }
}

$('exportBtn').onclick = async () => {
  const rows = [];
  for (const tr of tbody.querySelectorAll('tr')) {
    const cells = tr.querySelectorAll('td');
    if (!cells.length) continue;
    rows.push({
      org: cells[0].textContent,
      url: cells[1].textContent,
      title: cells[2].textContent,
      emails: cells[3].textContent,
      phones: cells[4].textContent,
      socials: cells[5].textContent,
      ok: cells[6].textContent === '✓',
      error: cells[7].textContent,
    });
  }
  if (!rows.length) return alert('No rows to export');
  const r = await fetch(API + '/api/export', {
    method:'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({rows})
  });
  if (!r.ok) { alert('Export failed'); return; }
  const data = await r.json();
  const blob = new Blob([data.content], {type: 'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = data.filename || 'leads.csv';
  document.body.appendChild(a);
  a.click();
  URL.revokeObjectURL(a.href);
  a.remove();
};

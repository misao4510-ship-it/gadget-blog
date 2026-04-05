/**
 * PV Counter Client Script
 * [slug].astroの<script>タグ内、またはBaseLayout内で読み込む
 *
 * Worker URL: https://pv-counter.YOUR_SUBDOMAIN.workers.dev
 * 環境変数 PUBLIC_PV_WORKER_URL で設定
 */

(async function() {
  const displayEl = document.getElementById('pv-display');
  if (!displayEl) return;

  // Worker URLは環境変数から取得（未設定時はスキップ）
  const workerUrl = import.meta.env?.PUBLIC_PV_WORKER_URL || '';
  if (!workerUrl) {
    displayEl.textContent = '—';
    return;
  }

  const path = window.location.pathname;
  const apiUrl = `${workerUrl}/api/pv?path=${encodeURIComponent(path)}`;

  try {
    // カウントアップ
    const res = await fetch(apiUrl, { method: 'POST' });
    if (!res.ok) throw new Error('fetch failed');
    const data = await res.json();
    displayEl.textContent = data.count.toLocaleString('ja-JP');
  } catch {
    // エラー時はGETで現在値表示を試みる
    try {
      const res = await fetch(apiUrl);
      const data = await res.json();
      displayEl.textContent = data.count.toLocaleString('ja-JP');
    } catch {
      displayEl.textContent = '—';
    }
  }
})();

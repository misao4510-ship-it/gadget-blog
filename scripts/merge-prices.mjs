import { readFileSync, writeFileSync, readdirSync, unlinkSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const PRICES_DIR = join(ROOT, 'data/prices');

const TODAY = new Date().toISOString().split('T')[0];
const HISTORY_DAYS = 90;

function cutoffDate() {
  const d = new Date();
  d.setDate(d.getDate() - HISTORY_DAYS);
  return d.toISOString().split('T')[0];
}

function loadJson(path) {
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(readFileSync(path, 'utf-8'));
  } catch {
    return null;
  }
}

function findTmpFiles(suffix) {
  return readdirSync(PRICES_DIR)
    .filter(f => f.endsWith(suffix))
    .map(f => join(PRICES_DIR, f));
}

function calcCheapest(amazon, rakuten) {
  const candidates = [];
  if (amazon?.price != null) candidates.push({ store: 'amazon', price: amazon.price });
  if (rakuten?.price != null) candidates.push({ store: 'rakuten', price: rakuten.price });
  if (candidates.length === 0) return null;
  return candidates.reduce((a, b) => a.price <= b.price ? a : b);
}

async function main() {
  // product_id → { amazon, rakuten } から一時データを収集
  const tmpAmazon = {};
  const tmpRakuten = {};

  for (const file of findTmpFiles('_amazon_tmp.json')) {
    const data = loadJson(file);
    if (data?.product_id && data?.amazon) {
      tmpAmazon[data.product_id] = data.amazon;
    }
  }

  for (const file of findTmpFiles('_rakuten_tmp.json')) {
    const data = loadJson(file);
    if (data?.product_id && data?.rakuten) {
      tmpRakuten[data.product_id] = data.rakuten;
    }
  }

  const allProductIds = new Set([...Object.keys(tmpAmazon), ...Object.keys(tmpRakuten)]);

  // 既存の product-*.json も含めて処理対象を収集
  const existingFiles = readdirSync(PRICES_DIR).filter(f => /^product-\d+\.json$/.test(f));
  for (const f of existingFiles) {
    const data = loadJson(join(PRICES_DIR, f));
    if (data?.product_id) allProductIds.add(data.product_id);
  }

  let updated = 0;
  let skipped = 0;

  for (const productId of allProductIds) {
    const outPath = join(PRICES_DIR, `${productId}.json`);
    const existing = loadJson(outPath) ?? { product_id: productId, current: {}, history: [] };

    const newAmazon = tmpAmazon[productId];
    const newRakuten = tmpRakuten[productId];

    // tmpが存在する場合のみ上書き
    if (newAmazon) existing.current.amazon = newAmazon;
    if (newRakuten) existing.current.rakuten = newRakuten;

    // cheapest再計算
    existing.current.cheapest = calcCheapest(existing.current.amazon, existing.current.rakuten);

    // history更新 (同日は上書き)
    const historyEntry = { date: TODAY };
    if (existing.current.amazon?.price != null) historyEntry.amazon = existing.current.amazon.price;
    if (existing.current.rakuten?.price != null) historyEntry.rakuten = existing.current.rakuten.price;

    if (!existing.history) existing.history = [];
    const idx = existing.history.findIndex(h => h.date === TODAY);
    if (idx >= 0) {
      existing.history[idx] = historyEntry;
    } else {
      existing.history.push(historyEntry);
    }

    // 90日超を削除
    const cutoff = cutoffDate();
    existing.history = existing.history
      .filter(h => h.date >= cutoff)
      .sort((a, b) => b.date.localeCompare(a.date));

    writeFileSync(outPath, JSON.stringify(existing, null, 2));
    updated++;
    console.log(`  ✅ ${productId}: amazon=¥${existing.current.amazon?.price ?? '-'}, rakuten=¥${existing.current.rakuten?.price ?? '-'}, cheapest=${existing.current.cheapest?.store ?? '-'}`);
  }

  // tmpファイルを削除
  for (const file of [...findTmpFiles('_amazon_tmp.json'), ...findTmpFiles('_rakuten_tmp.json')]) {
    unlinkSync(file);
  }

  console.log(`\nMerge complete: ${updated} products updated, ${skipped} skipped.`);
}

main().catch(console.error);

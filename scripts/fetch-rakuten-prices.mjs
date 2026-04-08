import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function fetchRakutenPrice(keyword, appId, accessKey, origin, retries = 3) {
  const url = new URL('https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401');
  url.searchParams.set('applicationId', appId);
  url.searchParams.set('accessKey', accessKey);
  url.searchParams.set('keyword', keyword);
  url.searchParams.set('sort', '+itemPrice');
  url.searchParams.set('hits', '5');
  url.searchParams.set('format', 'json');

  const headers = {
    'Origin': origin,
  };

  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const res = await fetch(url.toString(), { headers });

      if (res.status === 429) {
        const wait = Math.pow(2, attempt + 1) * 1000;
        console.log(`Rate limited. Waiting ${wait}ms...`);
        await sleep(wait);
        continue;
      }

      if (!res.ok) {
        console.error(`Error ${res.status} for keyword "${keyword}": ${await res.text()}`);
        return null;
      }

      const data = await res.json();
      const items = data?.Items;
      if (!items || items.length === 0) return null;

      // 最安値を取得
      const prices = items.map(i => i.Item?.itemPrice).filter(p => typeof p === 'number');
      if (prices.length === 0) return null;

      const minPrice = Math.min(...prices);
      const cheapestItem = items.find(i => i.Item?.itemPrice === minPrice);
      const itemUrl = cheapestItem?.Item?.itemUrl ?? null;

      return {
        price: minPrice,
        in_stock: true,
        url: itemUrl,
        updated: new Date().toISOString().split('T')[0],
      };
    } catch (e) {
      console.error(`Attempt ${attempt + 1} failed for keyword "${keyword}": ${e.message}`);
      if (attempt < retries - 1) await sleep(Math.pow(2, attempt + 1) * 1000);
    }
  }
  return null;
}

async function main() {
  const appId = process.env.RAKUTEN_APP_ID;
  const accessKey = process.env.RAKUTEN_ACCESS_KEY;
  const origin = process.env.RAKUTEN_ORIGIN || 'https://gadget-blog-dxq.pages.dev';

  if (!appId) {
    console.error('Missing env: RAKUTEN_APP_ID');
    process.exit(1);
  }

  if (!accessKey) {
    console.error('Missing env: RAKUTEN_ACCESS_KEY');
    process.exit(1);
  }

  const { products } = JSON.parse(readFileSync(join(ROOT, 'data/products.json'), 'utf-8'));
  mkdirSync(join(ROOT, 'data/prices'), { recursive: true });

  for (const product of products) {
    const keyword = product.rakuten_keyword;
    if (!keyword) {
      console.log(`Skip ${product.id}: rakuten_keyword not configured`);
      continue;
    }

    // ASINがPLACEHOLDERの場合もrakuten_keywordで検索する
    console.log(`Fetching Rakuten price for ${product.id} (${product.name})...`);
    await sleep(1000); // Rate limit: 1 req/sec

    const priceData = await fetchRakutenPrice(keyword, appId, accessKey, origin);
    if (priceData) {
      writeFileSync(
        join(ROOT, `data/prices/${product.id}_rakuten_tmp.json`),
        JSON.stringify({ product_id: product.id, rakuten: priceData }, null, 2)
      );
      console.log(`  ✅ ${product.name}: ¥${priceData.price}`);
    } else {
      console.log(`  ⚠️ ${product.name}: Could not fetch price`);
    }
  }
  console.log('Rakuten price fetch complete.');
}

main().catch(console.error);

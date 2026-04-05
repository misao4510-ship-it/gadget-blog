import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import crypto from 'crypto';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// AWS Signature V4 helpers
function hmac(key, data) {
  return crypto.createHmac('sha256', key).update(data).digest();
}
function hmacHex(key, data) {
  return crypto.createHmac('sha256', key).update(data).digest('hex');
}
function hash(data) {
  return crypto.createHash('sha256').update(data).digest('hex');
}

function getSignatureKey(secretKey, dateStamp, region, service) {
  const kDate = hmac('AWS4' + secretKey, dateStamp);
  const kRegion = hmac(kDate, region);
  const kService = hmac(kRegion, service);
  return hmac(kService, 'aws4_request');
}

async function fetchAmazonPrice(asin, partnerTag, accessKey, secretKey, retries = 3) {
  const endpoint = 'https://webservices.amazon.co.jp/paapi5/getitems';
  const region = 'us-east-1';
  const service = 'ProductAdvertisingAPI';

  const payload = JSON.stringify({
    ItemIds: [asin],
    PartnerTag: partnerTag,
    PartnerType: 'Associates',
    Marketplace: 'www.amazon.co.jp',
    Resources: [
      'Offers.Listings.Price',
      'Offers.Listings.Availability.Message',
      'Offers.Listings.DeliveryInfo.IsFreeShippingEligible',
      'ItemInfo.Title',
    ]
  });

  const now = new Date();
  const amzDate = now.toISOString().replace(/[:-]|\.\d{3}/g, '').slice(0, 15) + 'Z';
  const dateStamp = amzDate.slice(0, 8);
  const payloadHash = hash(payload);

  const canonicalHeaders =
    `content-encoding:amz-1.0\n` +
    `content-type:application/json; charset=utf-8\n` +
    `host:webservices.amazon.co.jp\n` +
    `x-amz-date:${amzDate}\n` +
    `x-amz-target:com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems\n`;
  const signedHeaders = 'content-encoding;content-type;host;x-amz-date;x-amz-target';
  const canonicalRequest = ['POST', '/paapi5/getitems', '', canonicalHeaders, signedHeaders, payloadHash].join('\n');

  const credentialScope = `${dateStamp}/${region}/${service}/aws4_request`;
  const stringToSign = ['AWS4-HMAC-SHA256', amzDate, credentialScope, hash(canonicalRequest)].join('\n');

  const signingKey = getSignatureKey(secretKey, dateStamp, region, service);
  const signature = hmacHex(signingKey, stringToSign);
  const authHeader = `AWS4-HMAC-SHA256 Credential=${accessKey}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`;

  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'content-encoding': 'amz-1.0',
          'content-type': 'application/json; charset=utf-8',
          'host': 'webservices.amazon.co.jp',
          'x-amz-date': amzDate,
          'x-amz-target': 'com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems',
          'Authorization': authHeader,
        },
        body: payload,
      });

      if (res.status === 429) {
        const wait = Math.pow(2, attempt + 1) * 1000;
        console.log(`Rate limited. Waiting ${wait}ms...`);
        await sleep(wait);
        continue;
      }

      if (!res.ok) {
        console.error(`Error ${res.status} for ASIN ${asin}: ${await res.text()}`);
        return null;
      }

      const data = await res.json();
      const item = data?.ItemsResult?.Items?.[0];
      if (!item) return null;

      const listing = item?.Offers?.Listings?.[0];
      const price = listing?.Price?.Amount;
      const inStock = listing?.Availability?.Message?.toLowerCase().includes('in stock') ?? false;
      const url = `https://www.amazon.co.jp/dp/${asin}?tag=${partnerTag}`;
      return { price: price ? Math.round(price) : null, in_stock: inStock, url, updated: new Date().toISOString().split('T')[0] };
    } catch (e) {
      console.error(`Attempt ${attempt + 1} failed for ${asin}: ${e.message}`);
      if (attempt < retries - 1) await sleep(Math.pow(2, attempt + 1) * 1000);
    }
  }
  return null;
}

async function main() {
  const accessKey = process.env.AWS_ACCESS_KEY_ID;
  const secretKey = process.env.AWS_SECRET_ACCESS_KEY;
  const partnerTag = process.env.AMAZON_PARTNER_TAG;

  if (!accessKey || !secretKey || !partnerTag) {
    console.error('Missing env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AMAZON_PARTNER_TAG');
    process.exit(1);
  }

  const { products } = JSON.parse(readFileSync(join(ROOT, 'data/products.json'), 'utf-8'));
  mkdirSync(join(ROOT, 'data/prices'), { recursive: true });

  for (const product of products) {
    if (!product.asin || product.asin.includes('PLACEHOLDER')) {
      console.log(`Skip ${product.id}: ASIN not configured`);
      continue;
    }
    console.log(`Fetching Amazon price for ${product.id} (${product.name})...`);
    await sleep(1000); // Rate limit: 1 req/sec
    const priceData = await fetchAmazonPrice(product.asin, partnerTag, accessKey, secretKey);
    if (priceData) {
      writeFileSync(
        join(ROOT, `data/prices/${product.id}_amazon_tmp.json`),
        JSON.stringify({ product_id: product.id, amazon: priceData }, null, 2)
      );
      console.log(`  ✅ ${product.name}: ¥${priceData.price}`);
    } else {
      console.log(`  ⚠️ ${product.name}: Could not fetch price`);
    }
  }
  console.log('Amazon price fetch complete.');
}

main().catch(console.error);

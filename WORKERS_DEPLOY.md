# Cloudflare Workers PVカウンター デプロイ手順

## 前提
- wrangler CLI インストール済み
- Cloudflare アカウントにログイン済み (`wrangler login`)

## 手順

### 1. KV Namespace 作成
```bash
cd /home/misao/gadget-blog
npx wrangler kv:namespace create PV_COUNTER
npx wrangler kv:namespace create PV_COUNTER --preview
```
出力されたIDを wrangler.toml の `REPLACE_WITH_KV_NAMESPACE_ID` と `REPLACE_WITH_KV_PREVIEW_ID` に設定。

### 2. Worker デプロイ
```bash
npx wrangler deploy workers/pv-counter.js --name pv-counter
```

### 3. 環境変数設定
.env.local（またはCloudflare Pagesの環境変数）に追加:
```
PUBLIC_PV_WORKER_URL=https://pv-counter.YOUR_SUBDOMAIN.workers.dev
```

### 4. [slug].astro にクライアントスクリプトを追加
src/pages/posts/[...slug].astro の `</BaseLayout>` 直前に:
```astro
<script src="/src/scripts/pv-counter-client.js" type="module"></script>
```
または BaseLayout の `</body>` 直前に同スクリプトをimport。

### 5. 再デプロイ
```bash
git add . && git commit -m "feat: enable PV counter" && git push
```

# Gadget Blog - ガジェット価格比較アフィリエイトブログ

ガジェット商品の価格変動を自動追跡し、複数ASP横断の価格比較で購買意思決定を支援するアフィリエイトブログ。

## 概要

- フレームワーク: Astro v6 (Static Site Generation)
- ホスティング: Cloudflare Pages
- 価格取得: Amazon PA-API v5 / 楽天アフィリエイトAPI
- 自動更新: GitHub Actions (定期実行)
- 記事数: 5記事（ガジェットレビュー・比較記事）

## ローカル開発

```bash
npm install
npm run dev        # http://localhost:4321 で起動
npm run build      # ./dist/ にビルド
npm run preview    # ビルド結果をプレビュー
```

> **Note**: Node.js v22以上が必要です。

## 環境変数設定

`.env.example` を参考に `.env` ファイルを作成:

```bash
cp .env.example .env
# .env を編集して各APIキーを設定
```

必要な環境変数:

| 変数名 | 説明 |
|--------|------|
| `AMAZON_CLIENT_ID` | Amazon PA-API クライアントID |
| `AMAZON_CLIENT_SECRET` | Amazon PA-API クライアントシークレット |
| `AMAZON_PARTNER_TAG` | Amazonアソシエイトタグ |
| `RAKUTEN_APP_ID` | 楽天アフィリエイト アプリID |
| `RAKUTEN_ACCESS_KEY` | 楽天アフィリエイト アクセスキー |

## GitHub Secrets設定

GitHub → Settings → Secrets and variables → Actions で以下を設定:

1. `AMAZON_CLIENT_ID`
2. `AMAZON_CLIENT_SECRET`
3. `AMAZON_PARTNER_TAG`
4. `RAKUTEN_APP_ID`
5. `RAKUTEN_ACCESS_KEY`

## Cloudflare Pages デプロイ手順

1. GitHubにpush:
   ```bash
   git push origin main
   ```

2. Cloudflare Pagesでリポジトリ連携:
   - Cloudflare Dashboard → Workers & Pages → Create application → Pages
   - GitHubアカウントを連携し、このリポジトリを選択

3. ビルド設定:
   - **Build command**: `npm run build`
   - **Build output directory**: `dist`
   - **Node.js version**: `22`

4. シークレット設定:
   - Settings → Environment variables で上記5変数を設定
   - 本番環境 (Production) と プレビュー環境 (Preview) 両方に設定推奨

5. デプロイ完了後、自動的にURLが発行されます。

## Amazon Creators API 申請について

> ⚠️ **緊急対応**: 2026/04/30 に PA-API v5 が廃止される予定です。
> 後継の Amazon Creators API への移行申請を至急行ってください。
>
> 申請先: Amazon Associates Central → Tools → Product Advertising API

## 楽天API申請について

1. 楽天ウェブサービス (https://webservice.rakuten.co.jp/) でアプリ登録
2. アプリID・アクセスキーを取得
3. 楽天アフィリエイト (https://affiliate.rakuten.co.jp/) で会員登録
4. `.env` に取得したキーを設定

## 価格データ自動更新

GitHub Actions (`.github/workflows/update-prices.yml`) が毎日定期実行して価格データを更新します。

手動実行:
```bash
node scripts/fetch-amazon-prices.mjs
node scripts/fetch-rakuten-prices.mjs
node scripts/merge-prices.mjs
```

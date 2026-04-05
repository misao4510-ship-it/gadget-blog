# デプロイ手順

## 前提条件

- Node.js v22以上が必要 (v20は非対応)
- `nvm use 22` でNode切り替え後にビルドすること

## 1. GitHubリポジトリ作成

GitHubで新しいリポジトリを作成 (例: gadget-blog)
Public or Private どちらでも可

## 2. リモート設定 & プッシュ

```bash
cd /home/misao/gadget-blog
git remote add origin https://github.com/YOUR_USERNAME/gadget-blog.git
git branch -M main
git push -u origin main
```

## 3. Cloudflare Pages 設定

1. https://dash.cloudflare.com → Pages → Create a project
2. Connect to Git → GitHub → gadget-blog リポジトリを選択
3. Build settings:
   - Framework preset: Astro
   - Build command: `npm run build`
   - Build output directory: `dist`
   - Node.js version: 22 (Environment Variables に `NODE_VERSION=22` を設定)
4. Save and Deploy

## 4. デプロイ後

割り当てられたURL (例: `gadget-blog.pages.dev`) を確認
このURLをAmazonアソシエイト申請に使用する

## 5. 代替: wrangler CLIで直接デプロイ (認証済みの場合)

```bash
cd /home/misao/gadget-blog
export NVM_DIR="$HOME/.nvm" && source "$NVM_DIR/nvm.sh" && nvm use 22
npm run build
npx wrangler login
npx wrangler pages deploy dist --project-name gadget-blog
```

## 注意事項

- Cloudflare Pages の Build & Deploy設定で `NODE_VERSION=22` の環境変数を追加すること
- ビルドコマンド: `npm run build`
- 出力ディレクトリ: `dist`

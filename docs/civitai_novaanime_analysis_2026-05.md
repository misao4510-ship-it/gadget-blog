# CivitAI novaAnimeXL_ilV170 人気プロンプト分析レポート

**分析日**: 2026-05-05  
**対象モデル**: Nova Anime XL IL V17.0 (modelVersionId: 2741698)  
**データソース**: CivitAI API `/images?sort=Most+Reactions&period=Month&limit=100`  
**分析画像数**: 100枚（うちmeta付き 98枚）

---

## エグゼクティブサマリ

novaAnimeXL_ilV170（Illustrious系）の月間人気画像TOP100を分析した。本モデルの特徴として、**品質タグの徹底した使用**（masterpiece, best quality, very aestheticが上位独占）と、**CFG 5を中心とした控えめなガイダンス設定**が際立つ。サンプラーは DPM++ 2M Karras が約44%でトップ。解像度は1024×1024正方形と832×1216（縦長ポートレート）の2パターンが主流。LoRA使用率は比較的低く、単体モデルの表現力を活かすスタイルが多い。ゆきね生成への応用では、品質タグ強化と CFG=5、DPM++ 2M Karras が推奨設定となる。

---

## 1. Positive プロンプト TOP30

| 順位 | タグ | 頻度 | カテゴリ |
|------|------|------|------|
| 1 | solo | 76 | 構図 |
| 2 | best quality | 67 | 品質 |
| 3 | masterpiece | 60 | 品質 |
| 4 | 1girl | 58 | 構図 |
| 5 | very aesthetic | 55 | 品質 |
| 6 | amazing quality | 53 | 品質 |
| 7 | 8k | 43 | 品質 |
| 8 | ray tracing | 42 | スタイル |
| 9 | blurry background | 42 | 構図 |
| 10 | absurdres | 36 | 品質 |
| 11 | (looking at the viewer:1.1) | 29 | 表情/ポーズ |
| 12 | good quality | 25 | 品質 |
| 13 | newest | 25 | 品質 |
| 14 | medium hair | 21 | 外見 |
| 15 | smile | 19 | 表情 |
| 16 | depth of field | 18 | 構図 |
| 17 | blush | 17 | 表情 |
| 18 | ultra-detailed | 17 | 品質 |
| 19 | highres | 16 | 品質 |
| 20 | (swept bangs:1.3) | 15 | 外見 |
| 21 | sanpaku eyes | 14 | 外見 |
| 22 | 4k | 14 | 品質 |
| 23 | (masterpiece:1.3) | 14 | 品質（強調） |
| 24 | (anime screenshot:1.5) | 13 | スタイル |
| 25 | (best quality:1.3) | 13 | 品質（強調） |
| 26 | asymmetrical hair | 12 | 外見 |
| 27 | (standing pose:1.2) | 11 | ポーズ |
| 28 | miniskirt | 11 | 服装 |
| 29 | (anime:1.3) | 10 | スタイル |
| 30 | ahoge hair | 10 | 外見 |

**ポイント**: Illustrious系は `very aesthetic`, `newest` など固有の品質タグが重要。`ray tracing` が意外なほど高頻度（42件）。

---

## 2. Negative プロンプト TOP20

| 順位 | タグ | 頻度 |
|------|------|------|
| 1 | bad anatomy | 111 |
| 2 | signature | 106 |
| 3 | bad hands | 82 |
| 4 | watermark | 78 |
| 5 | lowres | 71 |
| 6 | text | 69 |
| 7 | jpeg artifacts | 67 |
| 8 | missing fingers | 64 |
| 9 | deformed | 63 |
| 10 | mutated | 59 |
| 11 | cropped | 59 |
| 12 | extra digits | 54 |
| 13 | ugly | 50 |
| 14 | username | 50 |
| 15 | sketch | 49 |
| 16 | disfigured | 47 |
| 17 | old | 45 |
| 18 | fewer digits | 45 |
| 19 | very displeasing | 45 |
| 20 | graphic | 44 |

**ポイント**: 手指系（bad hands, missing fingers, extra digits, fewer digits）の除外が徹底されている。`very displeasing` はIllustrious固有のnegativeタグ。

---

## 3. 人気LoRA TOP10（kurokawa_v1除外）

| 順位 | LoRA名 | 頻度 | 特徴 |
|------|--------|------|------|
| 1 | susamix010-pony | 13 | スタイルミックス系（多用途） |
| 2 | Shiraishi___Tanaka-kun_wa_Itsumo_Kedaruge_epoch_10 | 5 | キャラクターLoRA（田中くんはいつもけだるげ・白石） |
| 3 | Yoshitaka___Tanaka-kun_wa_Itsumo_Kedaruge_epoch_10 | 3 | キャラクターLoRA（同作品・吉田） |
| 4 | Saya_Oota___Tanaka-kun_wa_Itsumo_Kedaruge_epoch_10 | 2 | キャラクターLoRA（同作品・太田彩） |
| 5 | Shiraishi___Tanaka-kun_wa_Itsumo_Kedaruge_epoch_12 | 2 | 同上（改良版） |
| 6 | StudioGhibli | 1 | スタイルLoRA（ジブリ風） |
| 7 | Powerpuff_Girls_Style_r1 | 1 | スタイルLoRA |
| 8 | Miyoshi___Tanaka-kun_wa_Itsumo_Kedaruge_epoch_10 | 1 | キャラクターLoRA（同作品・宮子） |

**ポイント**: 月間人気TOP100ではLoRA使用率が低く、単体モデルで完結させるユーザーが多い。`susamix010-pony` はPony系との互換LoRAで汎用性が高い。

---

## 4. サンプラー/CFG/サイズ分布

### サンプラー
| サンプラー | 件数 | シェア |
|------------|------|--------|
| DPM++ 2M Karras | 44 | 44% |
| Euler a | 35 | 35% |
| DPM++ 2M Exponential | 8 | 8% |
| Euler | 6 | 6% |
| res_multistep simple | 4 | 4% |
| DPM2 | 2 | 2% |

**推奨**: **DPM++ 2M Karras**（安定性・品質バランス最良）

### CFG Scale
- **平均: 4.82**（最小1.0、最大7.0）
- **最頻値: 5**（63件 = 63%がCFG=5を使用）

**推奨**: **CFG = 5**

### 解像度分布
| 幅 | 件数 | 高さ | 件数 |
|----|------|------|------|
| 1024px | 38 | 1024px | 37 |
| 832px | 35 | 1216px | 35 |
| 768px | 13 | 1344px | 13 |
| 1216px | 8 | 832px | 8 |

**推奨パターン**:
- 正方形: 1024×1024
- 縦長ポートレート: 832×1216（ゆきね向け推奨）

---

## 5. カワイイ系プロンプト構文パターン例（5件）

### 例1 — 女の子アニメ系（最多ハート数）
```
@monsterfurious（likes:103, hearts:30）
Positive:
masterpiece, best quality, amazing quality, very aesthetic, 8K, ray tracing, 1girl, solo, 
(cowboy shot:1.2), (looking at the viewer:1.2), regal pose, (hypnotized expression:1.2), 
very long hair, asymmetrical hair, twintails hair, (khaki hair:1.1), (swept bangs:1.3), 
(gold eyes:1.1), (heart-shaped pupils:1.2), simple background, gradient background

Negative:
lazyloli, modern, recent, old, oldest, cartoon, graphic, text, painting, crayon, graphite, 
abstract, glitch, deformed, mutated, ugly, disfigured, long neck, bad anatomy
```
**パターン**: 品質タグ先頭+ポーズ重み付け+外見詳細化。アテンションweight活用。

### 例2 — Illustrious品質強調型
```
@monsterfurious
Positive:
(masterpiece:1.3), (best quality:1.3), (anime screenshot:1.5), (anime:1.3), 
1girl, solo, medium hair, smile, blush, school uniform, (standing pose:1.2), 
blurry background, depth of field, (looking at the viewer:1.1), sanpaku eyes,
(swept bangs:1.3), ahoge hair, miniskirt

Negative:
bad anatomy, bad hands, watermark, signature, lowres, text, jpeg artifacts, 
missing fingers, deformed, mutated, cropped, ugly, username, very displeasing
```
**パターン**: `(anime screenshot:1.5)`でアニメ調強制。学校制服の清楚系キャラに最適。

### 例3 — シンプル最小構文
```
@EliCopterBank1（likes:34）
Positive:
hatsune_miku, buzz pls, speech bubble, bedroom, cute, blush, smile, pajamas, dim light.

Negative: （なし）
```
**パターン**: 品質タグなしでもモデルの基礎性能で十分な品質。シンプル派向け。

### 例4 — 動物擬人化・非人間カワイイ系
```
@Neuronomicon（likes:231, hearts:73）
Positive:
(masterpiece, best quality, high quality, highres), very awa, highres, absurdres,
(hungry_clicker:0.7), (hamu_koutarou:0.6),
(no humans:1.1), (cute:1.2), comfy, solo, cozy,
(frog:1.1),
(study, sketching by lamplight, charcoal smudges, quiet concentration, creative flow:0.8),
depth of field, cinematic

Negative:
bad quality, worst quality, worst detail, censor, lowres, worst aesthetic, bad anatomy, 
signature, watermark, logo, (hair:1.2), (furry:1.2)
```
**パターン**: 絵師スタイル参照（重み0.6〜0.7）を複数組み合わせる高度テクニック。`very awa`はIllustrious固有の品質タグ。

### 例5 — 構成美重視型
```
Positive:
masterpiece, best quality, amazing quality, very aesthetic, 8k, ray tracing, 1girl, solo,
blurry background, depth of field, (looking at the viewer:1.1), medium hair, smile, blush,
ultra-detailed, newest, good quality, absurdres

Negative:
bad anatomy, signature, bad hands, watermark, lowres, text, jpeg artifacts, 
missing fingers, deformed, mutated, cropped, extra digits, ugly, username
```
**パターン**: ゆきね生成の基本テンプレートとして最も汎用性が高い構成。

---

## まとめ：ゆきね生成への応用推奨設定

```
Positive（推奨ベース）:
masterpiece, best quality, amazing quality, very aesthetic, absurdres, 8k, 
1girl, solo, [外見タグ], [服装], [表情], blurry background, depth of field,
(looking at the viewer:1.1), <lora:kurokawa_v1:0.70~0.85>

Negative（推奨）:
bad anatomy, bad hands, watermark, signature, lowres, text, jpeg artifacts,
missing fingers, deformed, mutated, cropped, extra digits, ugly, username,
very displeasing, 2girls, 3girls, multiple girls, multiple people

サンプラー: DPM++ 2M Karras
CFG: 5
解像度: 832×1216（縦長ポートレート）
```

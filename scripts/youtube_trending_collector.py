#!/usr/bin/env python3
"""
cmd_359-B: YouTube RSS feed daemon
4チャンネルの新着動画を取得してdata/youtube_today.yamlに保存。
cron 6:45 の前（6:40等）に実行されることを想定。
"""
import sys, yaml, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta
from pathlib import Path

BLOG_DIR     = Path(__file__).parent.parent
CONFIG_FILE  = BLOG_DIR / 'config' / 'youtube_channels.yaml'
HISTORY_FILE = BLOG_DIR / 'data' / 'youtube_history.yaml'
TODAY_FILE   = BLOG_DIR / 'data' / 'youtube_today.yaml'

RSS_BASE = 'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'
NS = {'yt': 'http://www.youtube.com/xml/schemas/2015',
      'media': 'http://search.yahoo.com/mrss/'}

def fetch_rss(channel_id: str) -> list[dict]:
    url = RSS_BASE.format(channel_id=channel_id)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        xml_data = urllib.request.urlopen(req, timeout=15).read()
        root = ET.fromstring(xml_data)
        videos = []
        for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
            def text(tag):
                el = entry.find(tag)
                return (el.text or '') if el is not None else ''
            video_id = text('{http://www.youtube.com/xml/schemas/2015}videoId')
            thumbnail = ''
            media = entry.find('{http://search.yahoo.com/mrss/}group')
            if media is not None:
                th = media.find('{http://search.yahoo.com/mrss/}thumbnail')
                if th is not None:
                    thumbnail = th.get('url', '')
            description = ''
            if media is not None:
                desc = media.find('{http://search.yahoo.com/mrss/}description')
                if desc is not None:
                    description = desc.text or ''
            videos.append({
                'video_id': video_id,
                'title': text('{http://www.w3.org/2005/Atom}title'),
                'published': text('{http://www.w3.org/2005/Atom}published'),
                'description': description[:500],
                'thumbnail': thumbnail,
                'url': f'https://www.youtube.com/watch?v={video_id}',
            })
        return videos
    except Exception as e:
        print(f'[WARN] RSS fetch failed for {channel_id}: {e}', file=sys.stderr)
        return []

def load_history() -> set:
    if not HISTORY_FILE.exists():
        return set()
    with open(HISTORY_FILE) as f:
        data = yaml.safe_load(f) or {}
    seen = set()
    for ids in data.get('seen_video_ids', {}).values():
        seen.update(ids)
    return seen

def save_history(seen_ids: dict):
    with open(HISTORY_FILE, 'w') as f:
        yaml.dump({'seen_video_ids': seen_ids, 'updated': datetime.now().isoformat()},
                  f, allow_unicode=True)

def main():
    if not CONFIG_FILE.exists():
        print('[ERROR] youtube_channels.yaml not found', file=sys.stderr)
        sys.exit(1)

    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)
    channels = [ch for ch in config.get('channels', [])
                if ch.get('active') and ch.get('channel_id')]

    if not channels:
        print('[WARN] アクティブなチャンネルがありません', file=sys.stderr)
        sys.exit(0)

    # 履歴から既見動画IDを取得
    history_data = {}
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            history_data = yaml.safe_load(f) or {}
    seen_ids = {ch: set(history_data.get('seen_video_ids', {}).get(ch, []))
                for ch in [c['channel_id'] for c in channels]}
    all_seen = set().union(*seen_ids.values())

    today_videos = []
    for ch in channels:
        cid = ch['channel_id']
        videos = fetch_rss(cid)
        print(f"  {ch['name']}: {len(videos)}件取得")
        new_videos = [v for v in videos if v['video_id'] not in all_seen]
        for v in new_videos:
            v['channel_name'] = ch['name']
            v['channel_id'] = cid
            today_videos.append(v)
        seen_ids[cid].update(v['video_id'] for v in videos)

    # 新着動画を公開日降順でソート
    today_videos.sort(key=lambda v: v.get('published', ''), reverse=True)

    output = {
        'date': date.today().isoformat(),
        'generated_at': datetime.now().isoformat(),
        'new_videos': today_videos,
        'total': len(today_videos),
    }
    with open(TODAY_FILE, 'w') as f:
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False)
    print(f'[youtube_collector] 新着{len(today_videos)}件 → {TODAY_FILE}')

    # 履歴更新
    updated_history = {'seen_video_ids': {cid: list(ids) for cid, ids in seen_ids.items()},
                       'updated': datetime.now().isoformat()}
    with open(HISTORY_FILE, 'w') as f:
        yaml.dump(updated_history, f, allow_unicode=True)

if __name__ == '__main__':
    main()

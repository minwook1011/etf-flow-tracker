# -*- coding: utf-8 -*-
"""
비공개·유료 텔레그램 방 수집기 (본인 계정 로그인 방식, Telethon 사용)

⚠️ 이 스크립트는 '당신 텔레그램 계정'으로 로그인해서, 당신이 이미 들어가 있는
   방들의 최근 글을 읽어옵니다. 로그인(전화번호+인증코드)은 계정 주인만 할 수 있어
   최초 1회는 당신이 직접 실행해야 합니다. (자동화/AI가 대신 로그인할 수 없습니다.)

── 최초 설정 (한 번만) ──────────────────────────────────────────
1) 파이썬 패키지 설치:      pip install telethon
2) https://my.telegram.org → 'API development tools' → api_id, api_hash 발급
3) 이 폴더에 telegram_secret.json 파일 생성(깃에 안 올라감):
   {
     "api_id": 123456,
     "api_hash": "여기에_해시",
     "phone": "+8210XXXXXXXX",
     "channels": [
       "https://t.me/xxxx",      // 링크로 지정(가장 확실)
       "@some_username",         // 공개 username
       "루팡"                    // 또는 방 제목(내가 들어간 방 목록에서 이름으로 매칭)
     ]
   }
4) 최초 1회 직접 실행:      python fetch_telegram_private.py
   → 전화번호로 온 인증코드를 입력하면 telegram_user.session 파일이 생기고,
     이후부터는 코드 입력 없이 자동 실행됩니다.

수집 결과는 공개 수집(fetch_telegram.py)과 같은 docs/telegram_news.json에 합쳐집니다.
"""
import json, os, re, html, hashlib
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SECRET = os.path.join(HERE, "telegram_secret.json")
OUT = os.path.join(HERE, "docs", "telegram_news.json")
SESSION = os.path.join(HERE, "telegram_user")  # → telegram_user.session


def norm_key(text):
    t = re.sub(r"https?://\S+", "", (text or "").lower())
    t = re.sub(r"[^0-9a-z가-힣]+", "", t)
    return hashlib.sha1(t[:400].encode("utf-8")).hexdigest() if t else None


def main():
    if not os.path.exists(SECRET):
        print("설정 파일이 없습니다:", SECRET)
        print("스크립트 상단의 '최초 설정' 주석을 참고해 telegram_secret.json을 만드세요.")
        return
    try:
        from telethon.sync import TelegramClient
    except ImportError:
        print("Telethon 미설치. 먼저:  pip install telethon")
        return

    conf = json.load(open(SECRET, encoding="utf-8"))
    api_id, api_hash = conf["api_id"], conf["api_hash"]
    phone = conf.get("phone")
    wanted = conf.get("channels", [])
    keep = int(conf.get("keep", 250))
    max_age_days = int(conf.get("max_age_days", 21))
    per_channel = int(conf.get("per_channel", 40))

    # 기존 데이터 로드
    existing = []
    if os.path.exists(OUT):
        try:
            existing = json.load(open(OUT, encoding="utf-8")).get("items", [])
        except Exception:
            existing = []
    existing_channels = []
    if os.path.exists(OUT):
        try:
            existing_channels = json.load(open(OUT, encoding="utf-8")).get("channels", [])
        except Exception:
            existing_channels = []

    by_key, order = {}, []

    def add(it):
        k = norm_key(it.get("text"))
        if not k or k in by_key:
            return
        by_key[k] = it
        order.append(k)

    for it in existing:
        add(it)

    client = TelegramClient(SESSION, api_id, api_hash)
    client.start(phone=lambda: phone) if phone else client.start()

    # 내가 들어간 방 목록(제목 매칭용)
    dialogs = {d.name: d.entity for d in client.iter_dialogs()}

    priv_channels = []
    for spec in wanted:
        try:
            if spec.startswith("http") or spec.startswith("@"):
                entity = client.get_entity(spec)
            elif spec in dialogs:
                entity = dialogs[spec]
            else:
                # 제목 부분일치 시도
                match = next((e for n, e in dialogs.items() if spec in n), None)
                if not match:
                    print(f"  [건너뜀] '{spec}' 방을 찾지 못함(내가 들어간 방 이름과 정확히 일치해야 함)")
                    continue
                entity = match
            title = getattr(entity, "title", None) or getattr(entity, "username", None) or str(spec)
            uname = getattr(entity, "username", None) or ("priv_" + str(getattr(entity, "id", "")))
            priv_channels.append({"username": uname, "title": title})
            cnt = 0
            for msg in client.iter_messages(entity, limit=per_channel):
                text = (msg.message or "").strip()
                if not text or len(text) < 4:
                    continue
                dt = msg.date.astimezone(timezone.utc).isoformat()
                cid = getattr(entity, "id", None)
                link = f"https://t.me/c/{cid}/{msg.id}" if cid else ""
                add({"channel": uname, "channel_title": title, "date": dt, "text": text[:1200], "link": link})
                cnt += 1
            print(f"  {title}: {cnt}건 수집")
        except Exception as e:
            print(f"  [실패] {spec} -> {type(e).__name__} {str(e)[:70]}")

    client.disconnect()

    items = [by_key[k] for k in order]
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    def to_dt(iso):
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except Exception:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)

    items = [it for it in items if to_dt(it.get("date", "")) >= cutoff]
    items.sort(key=lambda it: to_dt(it.get("date", "")), reverse=True)
    items = items[:keep]

    # 채널 목록 병합(공개 + 비공개)
    chan_map = {c["username"]: c for c in existing_channels}
    for c in priv_channels:
        chan_map[c["username"]] = c
    channels = list(chan_map.values())

    out = {
        "updated": datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST"),
        "channels": channels,
        "count": len(items),
        "items": items,
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"저장: {OUT} · {len(items)}건 · 비공개 채널 {len(priv_channels)}개")


if __name__ == "__main__":
    main()

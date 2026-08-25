#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مرصد — جامع المصادر
يعمل على الخادم (لا في المتصفح: قيود CORS تمنع سحب التغذيات من الواجهة).

  python3 collector.py verify   # يتحقق من كل مصدر ويكتب sources.verified.json + تقرير صحة
  python3 collector.py run      # دورة جمع كاملة -> events.json
  python3 collector.py run --once --since 6h

التحقق جزء من التصميم: المصادر تغيّر مساراتها دون إشعار، فالجامع يكتشف التغذية من صفحة
الموقع إن فشل المسار المرشح، ويسجل سبب فشل كل مصدر بدل إسقاطه بصمت.

يتطلب: requests  (اختياري: feedparser — وإلا استُخدم المحلل الداخلي)
"""

import argparse, hashlib, json, os, re, sys, time
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET

try:
    import requests
except ImportError:
    sys.exit("ثبّت المتطلبات أولاً:  pip install requests")

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Marsad-Collector/1.0 (+monitoring platform; contact: ops@example.org)"
TIMEOUT = 12
STATE_FILE = os.path.join(HERE, "collector.state.json")


# ------------------------------------------------------------------ أدوات
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def get(url, **kw):
    kw.setdefault("timeout", TIMEOUT)
    kw.setdefault("headers", {"User-Agent": UA, "Accept": "*/*"})
    return requests.get(url, **kw)


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"seen": {}, "health": {}}


def save_state(st):
    # نحتفظ ببصمات آخر 20 ألف عنصر فقط
    if len(st["seen"]) > 20000:
        st["seen"] = dict(sorted(st["seen"].items(), key=lambda kv: kv[1])[-20000:])
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False)


def fingerprint(title, link):
    """بصمة تمنع تكرار الخبر نفسه بين المصادر: العنوان بعد التطبيع، أو الرابط."""
    t = re.sub(r"[^\w\u0600-\u06FF]+", " ", (title or "")).strip().lower()
    t = re.sub(r"\s+", " ", t)
    base = t if len(t) > 25 else (link or t)
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------- اكتشاف التغذية والتحقق منها
FEED_HINTS = ["/feed", "/feed/", "/rss", "/rss.xml", "/?feed=rss2", "/atom.xml", "/index.xml"]


def looks_like_feed(text):
    head = text[:2000].lower()
    return ("<rss" in head) or ("<feed" in head) or ("<rdf:rdf" in head)


def discover_feeds(site):
    """يقرأ صفحة الموقع ويستخرج <link rel=alternate type=application/rss+xml>."""
    out = []
    try:
        r = get(site)
        if r.status_code != 200:
            return out
        html = r.text
        for m in re.finditer(r"<link[^>]+>", html, re.I):
            tag = m.group(0)
            if "alternate" in tag.lower() and re.search(r"(rss|atom)\+xml", tag, re.I):
                href = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
                if href:
                    u = href.group(1)
                    if u.startswith("//"):
                        u = "https:" + u
                    elif u.startswith("/"):
                        u = site.rstrip("/") + u
                    out.append(u)
    except Exception:
        pass
    return out


def probe_feed(url):
    """يعيد (نجاح، سبب، عدد العناصر)."""
    try:
        r = get(url)
    except Exception as e:
        return False, f"شبكة: {type(e).__name__}", 0
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}", 0
    if not looks_like_feed(r.text):
        return False, "الرد ليس تغذية RSS/Atom", 0
    return True, "ok", len(parse_feed(r.text))


def verify_source(s):
    """يجرب المسارات المرشحة ثم الاكتشاف التلقائي ثم التخمينات الشائعة."""
    if "api" in s:
        api = s["api"]
        if api.get("auth") in ("key", "oauth2", "appname"):
            return {"status": "يحتاج اعتماد", "endpoint": api["url"],
                    "reason": api.get("note", "يتطلب مفتاحاً أو حساباً"), "items": 0}
        url = api["url"]
        try:
            r = get(url)
            ok = r.status_code == 200
            return {"status": "يعمل" if ok else "فشل", "endpoint": url,
                    "reason": "ok" if ok else f"HTTP {r.status_code}",
                    "items": count_api_items(r, api) if ok else 0}
        except Exception as e:
            return {"status": "فشل", "endpoint": url, "reason": f"شبكة: {type(e).__name__}", "items": 0}

    candidates = list(s.get("feeds") or [])
    candidates += discover_feeds(s["site"])
    candidates += [s["site"].rstrip("/") + h for h in FEED_HINTS]
    tried = []
    for u in list(dict.fromkeys(candidates))[:6]:   # سقف للمحاولات كي لا تطول الدورة
        ok, reason, n = probe_feed(u)
        tried.append(f"{u} → {reason}")
        if ok:
            return {"status": "يعمل", "endpoint": u, "reason": "ok", "items": n}
        time.sleep(0.4)
    return {"status": "بلا تغذية", "endpoint": s["site"],
            "reason": "لا تغذية صالحة — يلزم كاشط مخصص أو الاعتماد على GDELT",
            "tried": tried[:6], "items": 0}


def count_api_items(r, api):
    try:
        data = r.json()
    except Exception:
        return len(r.text.splitlines())
    node = data
    for part in (api.get("path") or "").split("."):
        if part and isinstance(node, dict):
            node = node.get(part, [])
    return len(node) if isinstance(node, list) else 1


# ------------------------------------------------------------ تحليل التغذيات
def parse_feed(xml_text):
    """محلل RSS/Atom بسيط بلا اعتماديات، يعيد قائمة عناصر موحدة."""
    items = []
    try:
        root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    except ET.ParseError:
        return items
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        def find(*names):
            for n in names:
                el = it.find(n) if "}" not in n else None
                if el is None:
                    el = it.find(f"{{http://www.w3.org/2005/Atom}}{n}")
                if el is not None and (el.text or el.get("href")):
                    return (el.text or el.get("href") or "").strip()
            return ""
        link = find("link")
        if not link:
            el = it.find("{http://www.w3.org/2005/Atom}link")
            link = el.get("href") if el is not None else ""
        items.append({
            "title": re.sub(r"<[^>]+>", "", find("title")),
            "link": link,
            "summary": re.sub(r"<[^>]+>", " ", find("description", "summary", "content"))[:600].strip(),
            "date": find("pubDate", "published", "updated", "date"),
        })
    return items


def parse_date(s):
    if not s:
        return datetime.now(timezone.utc)
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s.strip(), fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


# --------------------------------------------------- التصنيف والإسناد والأهمية
def match_entities(text, entities):
    found = []
    for name, aliases in entities.items():
        if any(a in text for a in aliases):
            found.append(name)
    return found


def match_place(text, places):
    """ترميز جغرافي بالمطابقة النصية: يُفضَّل المرادف الأطول لتفادي المطابقات العامة."""
    best = None
    for p in places or []:
        for a in p.get("alias", [p["n"]]):
            if a in text and (best is None or len(a) > best[0]):
                best = (len(a), p)
    if not best:
        return {"n": "غير محدد"}
    p = best[1]
    return {"n": p["n"], "lat": p["lat"], "lng": p["lng"], "co": p.get("co", "")}


def assign_file(text, files):
    best, score = None, 0
    for f in files:
        s = sum(1 for k in f["keywords"] if k in text)
        if s > score:
            best, score = f["id"], s
    return best, score


KINDS = [("تصريح رسمي", ["صرح", "تصريح", "بيان", "أعلن", "أكد", "قال وزير", "الخارجية", "الناطق"]),
         ("قرار", ["قرر", "قرار", "مرسوم", "تمديد", "إلغاء", "تعليق", "عقوبات", "استثناء"]),
         ("اجتماع", ["اجتماع", "لقاء", "مباحثات", "زيارة", "وفد", "جولة", "محادثات"]),
         ("إجراء ميداني", ["انتشار", "قصف", "اشتباك", "دورية", "انسحاب", "تعزيزات", "معبر", "قافلة"]),
         ("مؤشر اقتصادي", ["سعر", "الليرة", "تضخم", "أسعار", "صادرات", "واردات", "عمولة"])]


def guess_kind(text):
    for name, words in KINDS:
        if any(w in text for w in words):
            return name
    return "خبر"


def propose_importance(item, confirmations, weight, kw_score, ents):
    """
    درجة مقترحة — والقرار النهائي للمحرر داخل المنصة.
      محوري: تأكيد من مصدرين مستقلين على الأقل + مصدر عالي الوزن + إشارة قرار/التزام
      مهم  : تطابق قوي مع نطاق الملف أو مصدر عالي الوزن
      عادي : ما دون ذلك
    """
    text = item["title"] + " " + item["summary"]
    decisive = any(w in text for w in
                   ["قرار", "اتفاق", "توقيع", "انسحاب", "تمديد", "تعليق", "إلغاء", "مهلة", "جدول زمني", "عقوبات"])
    if confirmations >= 2 and weight >= 4 and decisive:
        return "pivotal"
    if (kw_score >= 2 and weight >= 3) or (weight >= 4 and decisive) or len(ents) >= 3:
        return "important"
    return "normal"


# ------------------------------------------------------------------ الأوامر
def cmd_verify(cfg):
    log(f"التحقق من {len(cfg['sources'])} مصدراً…")
    verified, report = [], []
    for s in cfg["sources"]:
        res = verify_source(s)
        rec = dict(s); rec["verified"] = res
        verified.append(rec)
        report.append((res["status"], s["name"], res.get("endpoint", ""), res.get("reason", "")))
        log(f"  {res['status']:12s} {s['name']}  ({res.get('reason','')})")
    with open(os.path.join(HERE, "sources.verified.json"), "w", encoding="utf-8") as f:
        json.dump({"checked": datetime.now(timezone.utc).isoformat(), "sources": verified}, f, ensure_ascii=False, indent=1)
    ok = sum(1 for r in report if r[0] == "يعمل")
    log(f"\nالنتيجة: {ok} يعمل · {sum(1 for r in report if r[0]=='يحتاج اعتماد')} يحتاج اعتماد · "
        f"{sum(1 for r in report if r[0] in ('فشل','بلا تغذية'))} متعذر")
    log("كُتب sources.verified.json — استخدمه كمصدر التشغيل بدل الملف المرشح.")


def collect_rss(s, endpoint, since):
    try:
        r = get(endpoint)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
    except Exception as e:
        return [], f"شبكة: {type(e).__name__}"
    out = []
    for it in parse_feed(r.text):
        d = parse_date(it["date"])
        if d < since:
            continue
        it["source"] = s["name"]; it["weight"] = s["weight"]; it["party"] = s.get("party", False)
        it["dt"] = d
        out.append(it)
    return out, "ok"


def collect_gdelt(s, since):
    api = s["api"]
    url = api["url"].format(**api.get("params", {}))
    try:
        r = get(url)
        arts = r.json().get("articles", [])
    except Exception as e:
        return [], f"شبكة: {type(e).__name__}"
    out = []
    for a in arts:
        out.append({"title": a.get("title", ""), "link": a.get("url", ""),
                    "summary": a.get("domain", ""), "date": a.get("seendate", ""),
                    "dt": parse_date(a.get("seendate", "")), "source": a.get("domain", "GDELT"),
                    "weight": 2, "party": False})
    return out, "ok"


def cmd_run(cfg, since_hours):
    st = load_state()
    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    pool, health = [], {}

    src_list = cfg["sources"]
    vf = os.path.join(HERE, "sources.verified.json")
    if os.path.exists(vf):
        src_list = json.load(open(vf, encoding="utf-8"))["sources"]
        log("استُخدم sources.verified.json")

    for s in src_list:
        v = s.get("verified", {})
        if "api" in s:
            if s["id"] == "gdelt":
                items, why = collect_gdelt(s, since)
            else:
                health[s["id"]] = v.get("status", "غير مُتحقق"); continue
        else:
            ep = v.get("endpoint") or (s.get("feeds") or [None])[0]
            if not ep or v.get("status") == "بلا تغذية":
                health[s["id"]] = "بلا تغذية"; continue
            items, why = collect_rss(s, ep, since)
        health[s["id"]] = f"{why} · {len(items)} عنصراً"
        pool.extend(items)
        time.sleep(0.5)

    log(f"وصل {len(pool)} عنصراً خام من {len(health)} مصدراً")

    # تجميع الروايات المتطابقة في حدث واحد + عدّ التأكيدات المستقلة
    groups = {}
    for it in pool:
        fp = fingerprint(it["title"], it["link"])
        g = groups.setdefault(fp, {"item": it, "sources": [], "independent": set()})
        g["sources"].append(it["source"])
        if not it.get("party"):
            g["independent"].add(it["source"])
        if it["weight"] > g["item"]["weight"]:
            g["item"] = it

    events, skipped = [], 0
    for fp, g in groups.items():
        it = g["item"]
        text = it["title"] + " " + it["summary"]
        fid, kw = assign_file(text, cfg["files"])
        if not fid:                       # خارج نطاق كل الملفات
            skipped += 1; continue
        if fp in st["seen"]:              # سبق أرشفته في دورة سابقة
            skipped += 1; continue
        ents = match_entities(text, cfg["entities"])
        place = match_place(text, cfg.get("places"))
        lvl = propose_importance(it, len(g["independent"]), it["weight"], kw, ents)
        st["seen"][fp] = int(time.time())
        events.append({
            "id": "E-" + fp[:8], "file": fid, "date": it["dt"].strftime("%Y-%m-%d"),
            "time": it["dt"].strftime("%H:%M"), "title": it["title"][:220],
            "fact": it["summary"][:400], "url": it["link"], "place": place,
            "kind": guess_kind(text),
            "entities": ents, "sources": sorted(set(g["sources"])),
            "independent_confirmations": len(g["independent"]),
            "importance_suggested": lvl, "importance_user": None,
            "needs_review": len(g["independent"]) < 2,
        })

    events.sort(key=lambda e: (e["date"], e["time"]), reverse=True)
    with open(os.path.join(HERE, "events.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": datetime.now(timezone.utc).isoformat(),
                   "window_hours": since_hours, "source_health": health,
                   "events": events}, f, ensure_ascii=False, indent=1)
    st["health"] = health
    save_state(st)

    log(f"أحداث جديدة: {len(events)} · مستبعد (خارج النطاق أو مكرر): {skipped}")
    for lvl in ("pivotal", "important", "normal"):
        log(f"  {lvl}: {sum(1 for e in events if e['importance_suggested']==lvl)}")
    log("كُتب events.json — يُحمّل في المنصة مكان البيانات التجريبية.")


def main():
    ap = argparse.ArgumentParser(description="جامع مصادر مرصد")
    ap.add_argument("cmd", choices=["verify", "run"])
    ap.add_argument("--config", default=os.path.join(HERE, "sources.json"))
    ap.add_argument("--since", default="6h", help="نافذة الجمع، مثل 2h أو 24h")
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding="utf-8"))
    if a.cmd == "verify":
        cmd_verify(cfg)
    else:
        cmd_run(cfg, int(re.sub(r"\D", "", a.since) or 6))


if __name__ == "__main__":
    main()

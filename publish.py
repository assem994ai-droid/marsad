#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مرصد — الناشر
يجمع مخرجات الدورة (events.json + sheets.json) مع الأرشيف الدائم،
ثم يكتب ملفاً واحداً يقرأه الموقع مباشرة: data/site.json

    python3 publish.py

النتائج دائمة: كل دورة تضيف الجديد إلى الأرشيف ولا تمحو ما قبله.
"""
import json, os, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
MAX_SITE = 400        # ما يعرضه الموقع
MAX_ARCHIVE = 4000    # ما يُحفظ دائماً

sys.path.insert(0, HERE)
try:
    from analyst import gen_sheet
except Exception:
    gen_sheet = None


def jread(p, d):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return d


def main():
    os.makedirs(DATA, exist_ok=True)
    cfg = jread(os.path.join(HERE, "sources.json"), {})
    new = jread(os.path.join(HERE, "events.json"), {})
    new_events = new.get("events", []) if isinstance(new, dict) else (new or [])
    new_sheets = jread(os.path.join(HERE, "sheets.json"), {}).get("sheets", {})

    archive = jread(os.path.join(DATA, "archive.json"), {"events": [], "sheets": {}})
    by_id = {e["id"]: e for e in archive.get("events", [])}
    added = 0
    for e in new_events:
        if e["id"] not in by_id:
            added += 1
        else:                                   # حدث معروف: نحدّث مصادره ولا نلغي تعديل المستخدم
            old = by_id[e["id"]]
            e["importance_user"] = old.get("importance_user")
            srcs = set(old.get("sources", [])) | set(e.get("sources", []))
            e["sources"] = sorted(srcs)
            e["independent_confirmations"] = max(old.get("independent_confirmations", 0),
                                                 e.get("independent_confirmations", 0))
        by_id[e["id"]] = e

    events = sorted(by_id.values(), key=lambda x: (x.get("date", ""), x.get("time", "")), reverse=True)[:MAX_ARCHIVE]

    sheets = dict(archive.get("sheets", {}))
    sheets.update(new_sheets)
    if gen_sheet:                                # ورقة لكل حدث بلا استثناء
        for e in events[:MAX_SITE]:
            if e["id"] not in sheets:
                try:
                    sheets[e["id"]] = gen_sheet(e, events)
                except Exception:
                    pass

    json.dump({"events": events, "sheets": sheets},
              open(os.path.join(DATA, "archive.json"), "w", encoding="utf-8"), ensure_ascii=False)

    site_events = events[:MAX_SITE]
    site = {
        "live": bool(site_events),
        "generated": new.get("generated") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": cfg.get("files", []),
        "events": site_events,
        "sheets": {e["id"]: sheets[e["id"]] for e in site_events if e["id"] in sheets},
        "health": new.get("source_health", {}),
        "sources_total": len(cfg.get("sources", [])),
        "telegram": (cfg.get("telegram") or {}).get("channels", []),
        "archive_total": len(events),
        "added_this_cycle": added,
        "next_in": None,
    }
    json.dump(site, open(os.path.join(DATA, "site.json"), "w", encoding="utf-8"), ensure_ascii=False)

    lv = {}
    for e in site_events:
        k = e.get("importance_user") or e.get("importance_suggested", "normal")
        lv[k] = lv.get(k, 0) + 1
    print(f"نُشر: {len(site_events)} حدثاً في الموقع · {len(events)} في الأرشيف الدائم · جديد هذه الدورة: {added}")
    print(f"الأوراق: {len(site['sheets'])} · التوزيع: {lv}")


if __name__ == "__main__":
    main()

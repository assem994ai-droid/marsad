#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مرصد — مولّد أوراق التحليل
يقرأ events.json الذي ينتجه collector.py ويكتب sheets.json.

  python3 analyst.py                 # توليد بالقواعد فقط (بلا إنترنت)
  python3 analyst.py --model         # توليد موسّع بالنموذج للأحداث المرشحة
  python3 analyst.py --model --min pivotal   # يقتصر التوسيع على المحوري

مبدأ التصميم: ما يمكن اشتقاقه من البيانات يُثبَّت، وما لا يمكن يُصاغ كفرضية
موسومة. المولّد لا يخترع وقائع، ولا يصدر ورقة بلا قائمة تحقق ظاهرة.
"""
import argparse, json, os, sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PARTY_SRC = ['وكالة رسمية', 'الموقع الرسمي للوزارة', 'بيان رسمي', 'إدارة محلية', 'سانا', 'مصدر دبلوماسي', 'بيانات معبر']
CAPITALS = ['أنقرة', 'دمشق', 'موسكو', 'واشنطن', 'بروكسل', 'طهران']
DECISIVE = ['قرار', 'اتفاق', 'توقيع', 'انسحاب', 'تمديد', 'تعليق', 'إلغاء', 'مهلة', 'جدول زمني', 'عقوبات', 'شرط', 'استثناء']
OWNER = {'f-north': 'الوفد الفني الأمني', 'f-track': 'القناة الدبلوماسية',
         'f-econ': 'الجهة المالية المختصة', 'f-energy': 'الجهة الخدمية المختصة'}
ENTP = {
 'تركيا': ('أمن الحدود وخفض كلفة الانتشار مع الاحتفاظ بورقة تفاوضية.', 'خطوة محدودة ثم ربط ما بعدها بملف آخر.'),
 'سوريا': ('استعادة السيادة على نقاط محددة وتخفيف الضغط الاقتصادي.', 'قبول المسار التقني مع رفض تسميته اتفاقاً سياسياً.'),
 'الولايات المتحدة': ('استقرار يخفض كلفة وجودها دون خسارة نفوذها أو شركائها.', 'دعم صامت دون التزام مكتوب.'),
 'روسيا': ('تثبيت دورها كضامن لأي ترتيب إقليمي.', 'عرض الاستضافة لتثبيت الحضور.'),
 'إيران': ('الحفاظ على موقعها في ترتيبات ما بعد التسوية.', 'تحرك عبر قنوات موازية لتفادي التهميش.'),
 'قسد': ('ألا تتحول إلى ورقة تُصرف في تفاهم ثنائي.', 'تصعيد إعلامي وطلب ضمانات من طرف ثالث.'),
 'الاتحاد الأوروبي': ('استقرار يخدم ملف العودة الطوعية وضبط الهجرة.', 'مواءمة دون مبادرة منفردة.'),
 'الأمم المتحدة': ('إبقاء المسار ضمن الأطر الأممية.', 'إحاطات دورية ودعوات للتهدئة.'),
}
AXIS_RULES = {
 'تركيا': [('تركيا', 2, 'المسار الثنائي يتقدم على حساب القنوات متعددة الأطراف.'),
           ('روسيا', 1, 'تكسب دور الضامن دون حصرية.'),
           ('الولايات المتحدة', -1, 'كل تفاهم ثنائي مع أنقرة يقلّص مركزية الوساطة الأمريكية.'),
           ('إيران', -1, 'ترتيب بلا دورها يقلّص حصتها في تسويات لاحقة.'),
           ('دول الخليج', 1, 'تهدئة الحدود شرط مسبق لأي تمويل جدي.'),
           ('الاتحاد الأوروبي', 1, 'الاستقرار يخدم أولوية العودة الطوعية.')],
 'الولايات المتحدة': [('الولايات المتحدة', 1, 'إبقاء الملف داخل الأداة الأمريكية.'),
           ('الاتحاد الأوروبي', 1, 'مواءمة أوروبية شبه تلقائية.'),
           ('الصين', -1, 'كل تضييق غربي يرفع جاذبية القنوات البديلة بكلفة سياسية مؤجلة.'),
           ('روسيا', -1, 'تراجع نسبي في هامش موسكو التفاوضي.')],
 'روسيا': [('روسيا', 2, 'مكسب صافٍ كراعٍ للمسار.'), ('تركيا', 1, 'قناة ثنائية مدعومة.'),
           ('الولايات المتحدة', -1, 'تراجع مركزية القناة الأمريكية.'), ('إيران', -1, 'وساطة منفردة تضعف موقعها.')],
 'قسد': [('الولايات المتحدة', -1, 'أي ترتيب يمس الشريك المحلي يستدعي تحفظاً أمريكياً.'),
         ('تركيا', 1, 'تقدم في المطلب الأمني التركي.')],
 'سوريا': [('تركيا', 1, 'تثبيت الشرط السوري داخل المسار.'), ('روسيا', 1, 'دور الضامن يبقى مطلوباً.'),
           ('الولايات المتحدة', 0, 'لا تغيّر مباشر في العلاقة.')],
}


def dt(e):
    return e.get("date", "") + " " + e.get("time", "")


def build_ctx(e, all_events):
    same = [x for x in all_events if x.get("file") == e.get("file") and x["id"] != e["id"]]
    prior = sorted([x for x in same if dt(x) < dt(e)], key=dt, reverse=True)
    prev = prior[0] if prior else None
    prev_same = next((x for x in prior if x.get("kind") == e.get("kind")
                      and set(x.get("entities", [])) & set(e.get("entities", []))), None)
    indep = [s for s in e.get("sources", []) if s not in PARTY_SRC]
    text = (e.get("title", "") + " " + e.get("fact", ""))
    gap = None
    if prev:
        try:
            gap = round((datetime.fromisoformat(e["date"] + "T" + e["time"])
                         - datetime.fromisoformat(prev["date"] + "T" + prev["time"])).total_seconds() / 3600)
        except Exception:
            gap = None
    return {"prev": prev, "prev_same": prev_same, "indep": indep, "prior": prior,
            "decisive": [w for w in DECISIVE if w in text],
            "capital": e.get("place", {}).get("n", e.get("place", "")) in CAPITALS,
            "binding": e.get("kind") in ("تصريح رسمي", "قرار"),
            "gap": gap,
            "lvl": e.get("importance_user") or e.get("importance_suggested") or e.get("importance") or "normal"}


def gen_sheet(e, all_events):
    c = build_ctx(e, all_events)
    rules, read = [], []
    kind = e.get("kind", "")
    if kind == "تصريح رسمي":
        read.append("التصريح الرسمي يُقرأ كتسعيرة تفاوضية قبل أن يكون إعلان موقف: ما يُحذف منه لا يقل دلالة عما يُذكر فيه.")
        rules.append("قراءة/تصريح")
    elif kind == "اجتماع":
        read.append("في الاجتماعات يكون الانعقاد نفسه هو الرسالة، والمخرجات المعلنة أقل عادةً مما جرى على الطاولة.")
        rules.append("قراءة/اجتماع")
    elif kind == "إجراء ميداني":
        read.append("الإجراء الميداني يُقاس بما تلاه لا بما رافقه: غياب الاشتباك يرجّح أنه ضمن تفاهم قائم، وتكراره يرجّح أنه سياسة لا حادثة.")
        rules.append("قراءة/ميدان")
    elif kind == "قرار":
        read.append("القرار التنظيمي يُقرأ من أثره التشغيلي لا من عنوانه: توسيع الشكل قد يرافقه تضييق الممر الفعلي.")
        rules.append("قراءة/قرار")
    else:
        read.append("الحدث ذو طابع مؤشري: قيمته في اتجاهه عبر الزمن لا في قيمته المفردة.")
        rules.append("قراءة/مؤشر")

    place = e.get("place", {}).get("n", "") if isinstance(e.get("place"), dict) else e.get("place", "")
    if c["binding"] and c["capital"]:
        read.append(f"صدر من {place} أي عن مركز القرار لا عن الميدان، ما يرفع قابلية التنفيذ ويجعل التراجع أكثر كلفة.")
        rules.append("سلطة/مركزي")
    if c["prev_same"]:
        read.append(f"[للمقارنة] يوجد حدث سابق من النوع نفسه ولطرف مشترك: {c['prev_same']['id']} — المقارنة بين الصياغتين هي المدخل الأدق لتحديد ما إذا كان الموقف قد تحرك فعلاً.")
        rules.append("مقارنة/سابقة")
    if not c["indep"]:
        read.append("[تنبيه] كل المصادر المتاحة أطراف في القضية، فالرواية أحادية حتى يظهر تأكيد مستقل.")
        rules.append("تحذير/أحادي")

    when = (f"يقع بعد {c['gap']} ساعة من آخر تطور في الملف ({c['prev']['id']}). "
            + ("التقارب الزمني الشديد يرجّح أن الحدثين جزء من حزمة واحدة لا صدفة."
               if (c["gap"] or 999) <= 24 else "الفاصل الزمني يجعل الربط بينهما فرضية تحتاج دليلاً إضافياً.")
            ) if c["prev"] and c["gap"] is not None else "أول تطور مسجّل في هذا الملف ضمن النافذة الحالية."
    where = (f"{place} عاصمة قرار: الإعلان سياسي مركزي ونطاق أثره أوسع من الموقع نفسه."
             if c["capital"] else
             f"{place} موقع ميداني: الأثر المباشر محلي، والدلالة تُستمد من تكرار النمط لا من الحادثة المفردة.")
    rules.append("توقيت/محسوب")

    pros, cons, chal, opp = [], [], [], []
    if c["decisive"]:
        pros.append("ورود عناصر قابلة للقياس (" + "، ".join(c["decisive"][:3]) + ") ينقل النقاش من المبادئ إلى التفاصيل التقنية.")
        cons.append("العناصر المحددة تُقرأ أيضاً كسقف: قبولها ضمناً قد يجمّد ما لم يُذكر فيها.")
        rules.append("ميزان/حاسم")
    if len(c["indep"]) >= 2:
        pros.append(f"تعدد المصادر المستقلة ({len(c['indep'])}) يسمح بالبناء على الخبر دون انتظار تأكيد إضافي.")
    else:
        cons.append("ضعف التأكيد المستقل يجعل أي رد فعل سريع مخاطرة إن تبيّن الخبر ناقصاً.")
    if c["lvl"] == "pivotal":
        pros.append("حجم الحدث يمنح فرصة لتأطير الرواية أولاً قبل الطرف الآخر.")
        cons.append("الاهتمام العالي يرفع كلفة أي خطأ في الصياغة العلنية.")
    if e.get("file") == "f-econ":
        cons.append("الأثر الاقتصادي يصل إلى السكان قبل أي مكسب سياسي، وهذا فارق توقيت يجب إدارته.")
    if not c["capital"]:
        chal.append("التحقق الميداني في منطقة محدودة الوصول قبل أن تسبقنا رواية أخرى.")
    if len(c["indep"]) < 2:
        chal.append("الحصول على تأكيد من مصدر خارج أطراف القضية.")
    if c["prev_same"]:
        opp.append(f"تثبيت المقارنة مع {c['prev_same']['id']} كوثيقة تفاوضية تُظهر تغيّر الموقف بالنص لا بالانطباع.")
    if "جدول زمني" in c["decisive"] or "مهلة" in c["decisive"]:
        opp.append("تحويل الجدول الزمني إلى آلية تحقق مكتوبة بدل تركه تصريحاً قابلاً للتأويل.")
    pros = pros or ["لا مكسب مباشر ظاهر؛ القيمة في إضافة نقطة إلى سلسلة زمنية تُبنى عليها قراءة لاحقة."]
    cons = cons or ["لا كلفة مباشرة ظاهرة؛ الخطر الوحيد تضخيم الحدث بما لا يحتمله."]
    chal = chal or ["منع تضخّم الحدث داخلياً بما يتجاوز وزنه الفعلي."]
    opp = opp or ["استخدام الحدث كنقطة قياس أساس لرصد أي انحراف لاحق."]

    ents = e.get("entities", [])
    primary = ents[0] if ents else "—"
    parties = []
    for i, n in enumerate(ents):
        interest, act = ENTP.get(n, ("مصلحة غير مصنّفة بعد في قاعدة الكيانات.", "يحتاج تصنيفاً يدوياً."))
        d = 1 if i == 0 else (-1 if (c["decisive"] and n in ("سوريا", "قسد", "إيران") and n != primary)
                              or (n == "الولايات المتحدة" and primary == "تركيا") else 0)
        parties.append({"p": n, "i": interest, "d": d, "act": act})
    parties = parties or [{"p": "—", "i": "لم تُستخرج كيانات.", "d": 0, "act": "يلزم وسم يدوي."}]

    checks = [
        {"t": "مصدر ملزم (جهة قادرة على التنفيذ)", "v": c["binding"]},
        {"t": "تأكيد من مصدرين مستقلين على الأقل", "v": len(c["indep"]) >= 2},
        {"t": "يتضمن عنصراً قابلاً للقياس (مهلة، جدول، قرار)", "v": bool(c["decisive"])},
        {"t": "متصل بمسار قائم لا حدث معزول", "v": bool(c["prev_same"]) or (c["gap"] is not None and c["gap"] <= 72)},
        {"t": "درجة الأهمية محوري أو مهم", "v": c["lvl"] != "normal"},
    ]
    score = sum(1 for x in checks if x["v"])
    lvl = "يُبنى عليه" if score >= 4 else ("يستحق متابعة" if score >= 2 else "خبر عادي")
    rules.append(f"تصنيف/{score}من5")

    alli = [{"a": a, "v": v, "t": t} for a, v, t in AXIS_RULES.get(primary, [])] or \
           [{"a": "الولايات المتحدة", "v": 0, "t": "لا أثر مباشر مستنتج."}]
    if lvl == "خبر عادي":
        alli = [{**x, "v": 0, "t": "لا أثر يُذكر عند هذا المستوى."} for x in alli]
    elif lvl == "يستحق متابعة":
        alli = [{**x, "v": max(-1, min(1, x["v"]))} for x in alli]

    own = OWNER.get(e.get("file"), "الجهة المختصة")
    if lvl == "يُبنى عليه":
        acts = [
            {"t": f"تثبيت مضمون {e['id']} كتابةً في القناة الرسمية المختصة.", "h": "فوري", "o": own,
             "m": "وثيقة أو محضر يحمل الصياغة نفسها خلال الجولة التالية."},
            {"t": "تشغيل تحقق من ثلاث طبقات: بلاغ محلي، تأكيد فني، مصدر خارج الأطراف.", "h": "أسبوع", "o": own,
             "m": "اكتمال الطبقات الثلاث خلال 72 ساعة من أي خطوة تنفيذية."},
            {"t": "ضبط الخطاب العلني بحيث لا يُقرأ ما ورد كسقف نهائي.", "h": "فوري", "o": "الناطق الرسمي",
             "m": "خلو التغطية الخارجية من وصف الترتيب بأنه نهائي."}]
        worst = sorted(alli, key=lambda x: x["v"])[0]
        if worst["v"] < 0:
            acts.append({"t": f"فتح قناة طمأنة مع {worst['a']} لتفادي أن يُقرأ التقدم كخصم من رصيدها.",
                         "h": "شهر", "o": "القناة الدبلوماسية", "m": f"عدم صدور تحفظ علني من {worst['a']}."})
    elif lvl == "يستحق متابعة":
        acts = [{"t": f"رصد أسبوعي لمؤشر واحد محدد مرتبط بـ{e['id']}.", "h": "أسبوع", "o": own,
                 "m": "سلسلة بيانات متصلة لأربعة أسابيع."},
                {"t": "تحديد عتبة الترقية مسبقاً: ما الذي يجب أن يحدث ليتحول هذا إلى ملف قرار؟", "h": "أسبوع",
                 "o": own, "m": "عتبة مكتوبة ومعتمدة قبل التطور التالي."}]
        if len(c["indep"]) < 2:
            acts.append({"t": "طلب تأكيد من مصدر خارج أطراف القضية قبل أي بناء عليه.", "h": "فوري",
                         "o": "وحدة الرصد", "m": "تأكيد مستقل أو إسقاط الخبر من قائمة البناء."})
    else:
        acts = [{"t": f"تثبيت وقائع {e['id']} في السجل الزمني دون فعل إضافي.", "h": "فوري", "o": "وحدة الرصد",
                 "m": "قيد مؤرشف قابل للاستدعاء."},
                {"t": "إعداد رد جاهز يُستخدم فقط إذا تكرر الحدث أو تجاوز حدوده المعلنة.", "h": "شهر", "o": own,
                 "m": "عدم تصدّر رواية بديلة عند التكرار."}]

    return {"event": e["id"], "auto": True, "generated": datetime.now().isoformat(timespec="seconds"),
            "conf": "عالية" if len(c["indep"]) >= 2 else ("متوسطة" if len(c["indep"]) == 1 else "منخفضة"),
            "read": " ".join(read), "timing": {"when": when, "where": where},
            "pros": pros, "cons": cons, "chal": chal, "opp": opp, "parties": parties,
            "build": {"lvl": lvl, "why": f"تحققت {score} من 5 عناصر في قائمة التحقق."},
            "checks": checks, "score": score, "alli": alli, "acts": acts, "rules": rules,
            "basis": [e["id"]] + ([c["prev_same"]["id"]] if c["prev_same"] else []),
            "needs_review": True}


MODEL_PROMPT = """أنت محلل سياسي يكتب ورقة قرار لصانع قرار سوري. أعد JSON فقط بلا نص آخر، بالمخطط:
{"read":"","timing":{"when":"","where":""},"pros":[""],"cons":[""],"chal":[""],"opp":[""],
"parties":[{"p":"","i":"","d":1,"act":""}],"build":{"lvl":"يُبنى عليه|يستحق متابعة|خبر عادي","why":""},
"alli":[{"a":"","v":0,"t":""}],"acts":[{"t":"","h":"فوري|أسبوع|شهر","o":"","m":""}],"conf":"عالية|متوسطة|منخفضة"}
قواعد صارمة: لا تخترع وقائع غير واردة في المعطيات. كل حكم إما مشتق من المعطيات أو مصاغ كفرضية صريحة.
d بين -1 و1، وv بين -2 و2. كل نقطة عمل لها مؤشر نجاح قابل للقياس. عربية فصحى بلا مبالغة."""


def expand_with_model(sheet, e, prior):
    """توسيع اختياري بالنموذج. المسودة القاعدية تبقى إن فشل النداء."""
    import urllib.request
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("  (تخطٍّ: لا يوجد ANTHROPIC_API_KEY)"); return sheet
    body = json.dumps({"model": "claude-sonnet-4-6", "max_tokens": 1200, "messages": [{"role": "user", "content":
            MODEL_PROMPT + "\n\nالحدث: " + json.dumps(e, ensure_ascii=False) +
            "\nأحداث سابقة: " + json.dumps([{k: p.get(k) for k in ("id", "date", "title", "kind")} for p in prior[:4]], ensure_ascii=False) +
            "\nمسودة القواعد: " + json.dumps({k: sheet[k] for k in ("build", "checks", "conf")}, ensure_ascii=False)}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.load(r)
        txt = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        j = json.loads(txt.replace("```json", "").replace("```", "").strip())
        sheet.update(j); sheet["model"] = True
        sheet["rules"] = sheet.get("rules", []) + ["توليد/نموذج"]
    except Exception as ex:
        print(f"  (تعذّر التوسيع بالنموذج: {type(ex).__name__} — بقيت مسودة القواعد)")
    return sheet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=os.path.join(HERE, "events.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "sheets.json"))
    ap.add_argument("--model", action="store_true", help="توسيع بالنموذج")
    ap.add_argument("--min", default="important", choices=["pivotal", "important", "normal"],
                    help="أدنى درجة أهمية تُوسَّع بالنموذج")
    a = ap.parse_args()
    if not os.path.exists(a.events):
        sys.exit("لا يوجد events.json — شغّل collector.py run أولاً.")
    data = json.load(open(a.events, encoding="utf-8"))
    evs = data["events"] if isinstance(data, dict) else data
    rank = {"pivotal": 3, "important": 2, "normal": 1}
    sheets = {}
    for e in evs:
        s = gen_sheet(e, evs)
        lvl = e.get("importance_user") or e.get("importance_suggested") or "normal"
        if a.model and rank.get(lvl, 1) >= rank[a.min]:
            print(f"توسيع {e['id']} ({lvl})…")
            prior = sorted([x for x in evs if x.get("file") == e.get("file") and dt(x) < dt(e)], key=dt, reverse=True)
            s = expand_with_model(s, e, prior)
        sheets[e["id"]] = s
    json.dump({"generated": datetime.now().isoformat(timespec="seconds"), "sheets": sheets},
              open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    lv = {}
    for s in sheets.values():
        lv[s["build"]["lvl"]] = lv.get(s["build"]["lvl"], 0) + 1
    print(f"كُتبت {len(sheets)} ورقة في {os.path.basename(a.out)} — {lv}")
    print("كل الأوراق موسومة needs_review=true حتى يعتمدها محلل.")


if __name__ == "__main__":
    main()

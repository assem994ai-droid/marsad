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
OWNER = {"f-wh": "القناة الدبلوماسية المباشرة", "f-cong": "وحدة الاتصال التشريعي",
         "f-treas": "الجهة المالية المختصة + المستشار القانوني", "f-state": "وزارة الخارجية",
         "f-lobby": "وحدة العلاقات العامة والتمثيل القانوني", "f-think": "وحدة الدبلوماسية العامة",
         "f-dom": "وحدة الرصد السياسي", "f-gen": "وحدة الرصد"}

# مصالح الفاعلين في واشنطن كما تُقرأ من موقع صانع القرار السوري
ENTP = {
 "البيت الأبيض": ("إنجاز يُعرض داخلياً بكلفة منخفضة وبلا التزام طويل الأمد.",
                 "يتحرك بالأدوات التنفيذية القابلة للعكس قبل أي التزام تشريعي."),
 "وزارة الخارجية": ("مسار انخراط متدرج يبقي الملف تحت سيطرتها لا سيطرة الكونغرس.",
                   "تقدّم خطوات رمزية أولاً وتربط ما بعدها بأداء موثّق."),
 "وزارة الخزانة": ("إبقاء أدوات الضغط كاملة مع تفادي تهمة الأثر الإنساني.",
                  "تراخيص عامة محددة النطاق بدل رفع شامل."),
 "البنتاغون": ("حماية ترتيباتها الميدانية وشركائها المحليين قبل أي انفتاح سياسي.",
              "تحفّظ هادئ عبر القنوات الداخلية لا العلنية."),
 "مجلس الشيوخ": ("حق الرقابة والتصديق، ورفض أن تُفرض عليه سياسة بأمر تنفيذي.",
                "ربط أي انفتاح بشروط مكتوبة وتقارير دورية."),
 "مجلس النواب": ("الحساسية الانتخابية أعلى، والملف يُستخدم في التموضع الحزبي.",
                "تعديلات تقييدية تُلحق بمشاريع الدفاع والاعتمادات."),
 "الحزب الجمهوري": ("تفادي اتهام التساهل مع خصوم واشنطن، مع انفتاح على صفقات ملموسة.",
                   "دعم مشروط بضمانات أمنية معلنة."),
 "الحزب الديمقراطي": ("ربط الانفتاح بحقوق الإنسان والمسار السياسي.",
                     "دعم مشروط بمعايير حقوقية قابلة للقياس."),
 "مراكز الفكر": ("صياغة الإطار الذي يفكر داخله المشرّعون قبل أن يُطرح التشريع.",
                "أوراق وتوصيات تسبق التحرك الرسمي بأسابيع."),
 "اللوبيات": ("عقود تمثيل ونفوذ وصول إلى المكاتب المغلقة.",
             "تسجيل FARA وتحرك منسّق قبل جلسات الاستماع."),
 "إسرائيل": ("ضبط أي انفتاح بما لا يمس ترتيباتها الأمنية.",
            "تحرك عبر الكونغرس أكثر من الإدارة."),
 "تركيا": ("أن يمر أي مسار أمريكي عبرها لا فوقها.", "عرض نفسها قناة لا منافساً."),
 "دول الخليج": ("تحويل الانفتاح السياسي إلى فرص اقتصادية.", "تمويل مشروط بغطاء أمريكي واضح."),
 "روسيا": ("إبقاء موقعها كضامن لا غنى عنه.", "عرض بدائل سريعة لتفادي التهميش."),
 "الصين": ("ملء أي فراغ اقتصادي دون كلفة سياسية.", "عروض بنية تحتية طويلة الأجل."),
 "إيران": ("منع اصطفاف دمشق الكامل مع واشنطن.", "تحرك عبر قنوات موازية."),
 "سوريا": ("تثبيت مكاسب لا رجعة فيها قبل تغيّر الإدارة أو الكونغرس.",
          "ترجمة كل خطوة رمزية إلى واقعة تقنية موثقة."),
}

# محاور التحالف من موقع القرار السوري: ما يُكسب في محور وما يُدفع في المقابل
AXIS_RULES = {
 "البيت الأبيض": [("البيت الأبيض", 2, "تقدم في الأداة التنفيذية، وهي الأسرع والأقل ثباتاً."),
                 ("الكونغرس", -1, "كل ما يُنجز بأمر تنفيذي يستفز حرص المشرّعين على صلاحيتهم."),
                 ("دول الخليج", 1, "الغطاء الأمريكي شرط التمويل."),
                 ("روسيا", -1, "تراجع الحاجة إلى الوساطة الروسية."),
                 ("إيران", -1, "الاصطفاف الغربي يقلّص هامشها.")],
 "مجلس الشيوخ": [("الكونغرس", 2, "المكسب التشريعي أبطأ لكنه الأصعب على الإلغاء."),
                ("البيت الأبيض", 0, "لا يضيف للإدارة ولا يخصم منها مباشرة."),
                ("إسرائيل", -1, "أي تخفيف تشريعي يستدعي تحركاً مضاداً في اللجان."),
                ("دول الخليج", 1, "ثبات القاعدة القانونية يشجع الاستثمار.")],
 "وزارة الخزانة": [("البيت الأبيض", 1, "أداة مرنة تحت سيطرة الإدارة."),
                  ("الكونغرس", -1, "التوسع في التراخيص يثير مراجعة تشريعية."),
                  ("دول الخليج", 2, "الترخيص المالي هو ما ينتظره المستثمر فعلاً."),
                  ("الصين", -1, "انفتاح القنوات الغربية يقلّل جاذبية البديل الصيني، وهذا مكسب وثمن معاً.")],
 "اللوبيات": [("الكونغرس", 1, "الوصول المنظّم يفتح أبواب المكاتب المغلقة."),
             ("البيت الأبيض", 0, "أثر محدود على الإدارة."),
             ("إسرائيل", -1, "أي تمثيل منظّم يقابله تمثيل مضاد أقوى تاريخياً.")],
 "مراكز الفكر": [("الكونغرس", 1, "الأوراق تصوغ إطار النقاش قبل التشريع."),
                ("البيت الأبيض", 1, "توفر غطاءً فكرياً لقرار موجود.")],
 "إسرائيل": [("إسرائيل", 1, "تقدم في الملف الأمني الإقليمي."),
            ("الكونغرس", 1, "الموقف الإسرائيلي يترجم سريعاً إلى موقف تشريعي."),
            ("تركيا", -1, "توازن إقليمي حساس.")],
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


WINDOWS = []


def load_windows(cfg):
    global WINDOWS
    WINDOWS = (cfg.get("windows") or {}).get("items", [])


def next_window(from_date):
    """أقرب نافذة قرار قادمة والمتبقي عليها بالأيام."""
    try:
        d0 = datetime.fromisoformat(from_date)
    except Exception:
        d0 = datetime.now()
    up = []
    for w in WINDOWS:
        try:
            d = datetime.fromisoformat(w["d"])
        except Exception:
            continue
        if d >= d0:
            up.append((int((d - d0).days), w))
    up.sort(key=lambda x: x[0])
    return up[0] if up else None


def gen_sheet(e, all_events):
    c = build_ctx(e, all_events)
    rules, read = [], []
    kind = e.get("kind", "")
    if kind == "تصريح رسمي":
        read.append("في واشنطن يُقرأ التصريح الرسمي كإشارة إلى ما ستحتمله الإدارة لاحقاً، لا كموقف نهائي: ما يُحذف منه لا يقل دلالة عما يُذكر فيه.")
        rules.append("قراءة/تصريح")
    elif kind == "اجتماع":
        read.append("جلسة الاستماع أو الاجتماع في واشنطن مؤشر مبكر: جدول الأعمال يُكشف عن نية التشريع قبل أسابيع من ظهور النص.")
        rules.append("قراءة/اجتماع")
    elif kind == "إجراء ميداني":
        read.append("الإجراء الميداني يُقاس بما تلاه لا بما رافقه: غياب الاشتباك يرجّح أنه ضمن تفاهم قائم، وتكراره يرجّح أنه سياسة لا حادثة.")
        rules.append("قراءة/ميدان")
    elif kind == "قرار":
        read.append("القرار التنظيمي يُقرأ من أثره التشغيلي لا من عنوانه، والسؤال الأول عنه: هل هو تنفيذي قابل للعكس بجرة قلم، أم تشريعي يصعب إلغاؤه؟")
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
    nw = next_window(e.get("date", ""))
    if nw:
        days, w = nw
        when += (f" ونافذة القرار التالية بعد {days} يوماً: {w['t']} — {w['w']}"
                 if days > 0 else f" وتقع اليوم نافذة: {w['t']}.")
        rules.append(f"نافذة/{days}يوم")
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
    try:
        load_windows(json.load(open(os.path.join(HERE, "sources.json"), encoding="utf-8")))
        print(f"نوافذ القرار المحمّلة: {len(WINDOWS)}")
    except Exception:
        pass
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

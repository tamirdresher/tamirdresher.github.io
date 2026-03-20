---
layout: post-he
title: "כשמונה Ralphs נלחמים על Login אחד — בעיות מערכות מבוזרות אמיתיות בצוותי AI"
date: 2026-03-17
tags: [ai-agents, squad, github-copilot, distributed-systems, auth-race, rate-limiting, star-trek, borg]
series: "Scaling AI-Native Software Engineering"
series_part: 4
lang: he
dir: rtl
permalink: /he/2026/03/17/scaling-ai-part4-distributed/
sitemap: false
comments: false
---

> *"We have engaged the Borg."*
> — Captain Picard, Star Trek: First Contact

![Eight Ralphs fighting over one login](/assets/scaling-ai-part4-distributed/eight-ralphs-fight.png)

ב[חלק 3](/blog/2026/03/15/scaling-ai-part3-streams), הראיתי לכם איך Squad הפך למערכת מבוזרת — מספר מכונות, תורי משימות מבוססי git, זיהוי כשלים מונע heartbeat. זה נשמע נקי. אלגנטי ארכיטקטונית. כאילו הכל תחת שליטה.

לא היה לי הכל תחת שליטה.

כשמתחילים להריץ סוכני AI בסקייל אמיתי — שמונה לולאות פרסיסטנטיות על שמונה ריפוים — מפסיקים לדאוג לגבי prompts ומתחילים לדאוג לגבי תשתיות. מרוצי אימות, rate limits, נעילות מתות, סערות התראות, התנגשויות כתיבה. כל באג שנתקלתי בו התברר כבעיית מערכות מבוזרות קלאסית שהתעשייה פותרת כבר עשרות שנים. בניתי תיקונים לכולן. חלקן היו חכמות. רובן היו מכוערות-אבל-עובדות. כמה עדיין לא פתורות.

בלי היפותטיות. בלי "תדמיינו ש...". כל סיפור בפוסט הזה מקושר ל-commit אמיתי, issue אמיתי, או הודעת Teams אמיתית שהעירה אותי.

---

## שלושים ושבע כשלונות רצופים

יום ראשון, 16 במרץ 2026. אני מנסה ליהנות מאחר הצהריים שקט. הטלפון שלי נדלק עם הודעת Teams:

```
⚠️ Ralph Watch Alert — TAMIRDRESHER (tamresearch1)
Ralph watch has experienced 15 consecutive failures
Round: 15
Consecutive Failures: 15
Last Exit Code: 1
Timestamp: 2026-03-16 13:17:12
```

חמש עשרה סבבים. כל חמש דקות, Ralph מתעורר, מנסה לעבוד, נכשל, וחוזר לישון. משהו מאוד לא בסדר.

אני מסתכל על זה, מתקן את מה שנראה לי כבעיה (חשבון `gh auth` לא נכון — Ralph היה מוגדר לחשבון האישי שלי במקום חשבון העבודה), וחוזר לקפה. עשרים דקות אחר כך:

```
⚠️ Ralph Watch Alert — TAMIRDRESHER (tamresearch1)
Ralph watch has experienced 37 consecutive failures
Round: 37
Consecutive Failures: 37
Last Exit Code: 1
Timestamp: 2026-03-16 15:14:28
```

**שלושים ושבע.** כל כשלון מחזור שלם של חמש דקות. כמעט שלוש שעות של Ralph מסתובב בריק.

שורש הבעיה? לא באג ב-Ralph. לא שגיאת קוד. לא בעיית רשת. זו הייתה **קלאסיקה של מערכות מבוזרות**: shared mutable global state.

### מרוץ האימות

הנה הבעיה. יש לי שמונה מופעים של Ralph — אחד לכל ריפו שאני מנהל. כל Ralph מריץ את `ralph-watch.ps1` בלולאה. וכל Ralph צריך לתקשר עם GitHub דרך ה-CLI של `gh`.

ל-CLI של `gh` יש **מצב אימות גלובלי**. קובץ אחד. `~/.config/gh/hosts.yml`. כש-Ralph של ריפו A קורא ל-`gh auth switch --user personal-account`, הוא משנה את מצב האימות של **כל** תהליך על המכונה. Ralph של ריפו B — שצריך `work-account` — מרים את האישורים הלא נכונים ונכשל. Ralph של ריפו C מחליף בחזרה. ריפו A נכשל. וכן הלאה.

שמונה תהליכים. משאב משותף אחד. אפס תיאום. זו **בעיית המצב המשותף** — מספר תהליכים עצמאיים שמתייחסים למשאב גלובלי אחד כאילו הוא מקומי. אותו דבר קורה כשמיקרו-שירותים חולקים בסיס נתונים בלי הפרדת tenants.

ככה נראה דפוס הכשלון כשיש 8 Ralphs שנלחמים על `~/.config/gh/hosts.yml`:

```
┌─────────┐    ┌─────────┐    ┌─────────┐
│ Ralph-A │    │ Ralph-B │    │ Ralph-C │    ... (×8)
│ (repo1) │    │ (repo2) │    │ (repo3) │
└────┬────┘    └────┬────┘    └────┬────┘
     │              │              │
     ▼              │              │
  ┌──────────────────────────────────────┐
  │  ~/.config/gh/hosts.yml              │
  │  ┌────────────────────────────────┐  │
  │  │ user: tamirdresher      ← A   │  │  ← Ralph-A writes
  │  │ user: tamirdresher_ms   ← B   │  │  ← Ralph-B overwrites!
  │  │ user: tamirdresher      ← C   │  │  ← Ralph-C overwrites!
  │  └────────────────────────────────┘  │
  └──────────────────────────────────────┘
         SHARED MUTABLE STATE = 💥
```

```
Ralph-A: gh auth switch --user personal-acct       ✅ (writes to global state)
Ralph-B: gh auth switch --user work-acct            ✅ (overwrites A's auth)
Ralph-A: gh api repos/personal-acct/...             ❌ (now using B's credentials!)
Ralph-C: gh auth switch --user personal-acct        ✅ (overwrites B's auth)
Ralph-B: gh api repos/work-acct/...                 ❌ (now using C's credentials!)
...cascading failures...
```

התיקון? **משתני סביבה מקומיים לתהליך.** במקום להחליף את מצב האימות הגלובלי, כל Ralph קורא את ה-token לחשבון הנכון ומגדיר אותו כמשתנה סביבה מקומי `GH_TOKEN`. בלי מוטציה גלובלית. בלי מרוץ.

זה שורות 576–592 של `ralph-watch.ps1` היום:

```powershell
# Step -1: Self-healing — set GH_TOKEN for this process based on repo remote
# This avoids fighting over global gh auth state with other repo Ralphs
$remoteUrl = & git remote get-url origin 2>&1 | Out-String
$requiredAccount = if ($remoteUrl -match "work-org") {
    "work-account"
} else { "personal-account" }
$token = & gh auth token --user $requiredAccount 2>&1 | Out-String
if ($token -and $token.StartsWith("gho_")) {
    $env:GH_TOKEN = $token  # Process-local. No global mutation.
}
```

במונחי מערכות מבוזרות, החלפתי **נעילה גלובלית** (קובץ קונפיגורציה משותף) ב-**מצב מקומי לפרטיציה** (משתנה סביבה לכל תהליך). כל תהליך נושא את הזהות שלו. לא צריך תיאום.

אבל [Jon Gallant](https://blog.jongallant.com/) פתר את זה בצורה אלגנטית יותר. הגישה שלו ב-[`gh-public-gh-emu-setup`](https://github.com/jongio/gh-public-gh-emu-setup) משתמשת ב-`GH_CONFIG_DIR` — כל תהליך מצביע על **תיקיית קונפיגורציה מבודדת לחלוטין** לכל חשבון. לא רק ה-token, אלא הגדרות host, העדפות, מטמון API — הכל מחולק. אין אפשרות ל-cross-talk. מאז העברתי את Ralph למודל הזה ומרוץ האימות נעלם לחלוטין.

```
┌─────────┐    ┌─────────┐    ┌─────────┐
│ Ralph-A │    │ Ralph-B │    │ Ralph-C │
│ (repo1) │    │ (repo2) │    │ (repo3) │
└────┬────┘    └────┬────┘    └────┬────┘
     │              │              │
     ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│~/.gh-pub │  │~/.gh-emu │  │~/.gh-pub │
│ user: A  │  │ user: B  │  │ user: A  │
└──────────┘  └──────────┘  └──────────┘
    PARTITIONED STATE = ✅ No conflicts
```

**הדפוס במערכות מבוזרות:** זה מה שקורה כשמספר מיקרו-שירותים חולקים pool חיבורים אחד לבסיס נתונים, או כש-pods ב-Kubernetes נלחמים על ConfigMap. התיקון תמיד אותו דבר — **לחלק את המצב**. לתת לכל תהליך זהות ואחסון משלו. לא לשתף מצב גלובלי משתנה בין שחקנים מקבילים.

---

## הנעילה המתה שסירבה למות

תוך כדי דיבוג של התרסקות 37 הכשלונות המדורגת, מצאתי בעיה בונוס. Ralph לא הצליח לעלות כי קובץ נעילה קיים מהרצה קודמת — PID שמזמן מת, מלפני יומיים.

```json
{
  "pid": 40544,
  "started": "2026-03-14T09:12:04",
  "directory": "C:\\temp\\tamresearch1"
}
```

PID 40544 כבר לא קיים. התהליך קרס או נהרג. אבל קובץ הנעילה עדיין שם, שומר בגאווה על כלום. זו **בעיית זיהוי הכשלים** — איך יודעים אם תהליך שמחזיק נעילה בכלל חי?

מערכות מבוזרות מסורתיות פותרות את זה עם **heartbeats** ו-**נעילה מבוססת lease**. צמתים אפמריים ב-ZooKeeper נעלמים כשהסשן מסתיים. leases ב-etcd פגים אם לא מחדשים אותם. בדיקות בריאות של Consul נכשלות אחרי timeout.

הפתרון שלי היה שומר תלת-שכבתי ב-`ralph-watch.ps1` (שורות 35–71):

1. **Mutex בשם ברמת המערכת** — `Global\RalphWatch_tamresearch1` — מונע כפילויות על אותה מכונה. אם התהליך קורס, מערכת ההפעלה משחררת את ה-mutex. ה-catch של `AbandonedMutexException` מטפל ביציאות לא מסודרות.
2. **סריקת תהליכים** — `Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'ralph-watch' }` — מוצא והורג כל Ralph זומבי ישן עבור תיקיית הריפו הספציפית.
3. **קובץ נעילה** — כדי שכלים חיצוניים (כמו squad-monitor) יוכלו לקרוא סטטוס. מנוקה ביציאה דרך `Register-EngineEvent PowerShell.Exiting` ובלוק `trap`.

האם זה אלגנטי? לא. אלה שלושה מנגנונים שעושים את העבודה של נעילה מבוזרת אחת. אבל זה עובד. Mutex מכסה את המקרה הרגיל. סריקת תהליכים מטפלת ב-mutexes שננטשו. קובץ הנעילה קיים לצורך observability. הגנה בעומק.

**הדפוס במערכות מבוזרות:** זו אותה בעיה שכל אלגוריתם בחירת מנהיג פותר. Chubby בגוגל, ZooKeeper ביאהו, etcd ב-Kubernetes. הלקח: **קבצי נעילה בלי בדיקות בריאות הם שקר**. נעילה תקפה רק אם אפשר לאמת שהמחזיק בחיים.

---

## מכבה האש של ההתראות

באמצע מרץ, ה-Squad שלח הרבה התראות Teams. התראות כשלון של Ralph. חדשות טכנולוגיות יומיות של Neelix. סיכומי עדכוני issues. ממצאי אבטחה מ-Worf.

כולם הולכים ל**ערוץ אחד**.

ערוץ ה-`tamir-squads-notifications` שלי בצוות "squads" הפך לקיר של רעש. התראות חשובות (37 כשלונות!) טבעו בתדריכי טכנולוגיה יומיים וסיכומי PR שגרתיים. קיבלתי 20+ התראות ביום והתעלמתי מכולן — וזה בדיוק מה שקורה כשיש לך יעד לוגים אחד לכל דבר. זה המקבילה של מיקרו-שירותים שזורקים את הלוגים של כל שירות לקובץ אחד.

התיקון היה **מפת ניתוב**. יצרתי `teams-channels.json` — קובץ קונפיגורציה שממפה סוגי התראות לערוצים ספציפיים:

```json
{
  "channels": {
    "notifications": "tamir-squads-notifications",
    "tech-news": "Tech News",
    "dk8s": "DK8S Platform"
  }
}
```

סוכנים מתייגים את ההתראות שלהם עם מטאדאטה של `CHANNEL:`. פונקציית ההתראות מנתבת אותן ליעד הנכון. חדשות טכנולוגיה הולכות ל-Tech News. התראות כשלון הולכות לערוץ ההתראות הראשי. עדכונים ספציפיים ל-DK8S הולכים ל-DK8S Platform.

**הדפוס במערכות מבוזרות:** זה **pub-sub עם ניתוב לפי נושא**. Kafka topics. מפתחות ניתוב של RabbitMQ. סינון נושאים של AWS SNS. הלקח זהה לזה שהתעשייה למדה לפני עשרים שנה: **תור הודעות אחד לכל דבר הוא מתכון להתראות שמפספסים**. לנתב לפי סוג.

אבל גם נתקלתי בקומדיה מקרית בדרך. כשיצרתי את הערוצים, גיליתי שיש **שני** צוותים — "Squad" (הצוות של Brady) ו-"squads" (הצוות שלי). ההתראה הגיעה לערוץ החדש בצוות "Squad" הלא נכון. הייתי צריך למחוק אותו ולייצר אותו מחדש תחת "squads". במערכות מבוזרות, זו **בעיית Service Discovery** — צריך לפענח את ה-endpoint הנכון, ושמות שנראים דומים יכולים לנתב תעבורה ליעד הלא נכון. DNS לימד אותנו את זה לפני עשרות שנים.

---

## כששני סוכנים כותבים לאותו קובץ

הנה תרחיש שנשך אותי שוב ושוב: אני אומר לצוות לעשות triage לחבילת issues. Picard מפרק. ארבעה סוכנים עובדים במקביל — B'Elanna על issues של תשתיות, Worf על issues של אבטחה, Data על תיקוני קוד, Seven על תיעוד. כל אחד מקבל החלטות. כל אחד רוצה לרשום את ההחלטות ב-`.squad/decisions.md`.

שני סוכנים מסיימים באותו זמן. שניהם מנסים לעשות commit. **Merge conflict.**

```
  Agent A (B'Elanna)              Agent B (Worf)
        │                              │
        ▼                              ▼
  decisions.md                   decisions.md
  + "Use NAP for pods"           + "Block port 8443"
        │                              │
        └──────── git merge ───────────┘
                     │
                  CONFLICT 💥
                     │
           ┌─────────┴──────────┐
           │  merge=union       │  ← keeps BOTH lines
           │  (G-Set CRDT)      │
           └─────────┬──────────┘
                     │
              decisions.md
              + "Use NAP for pods"
              + "Block port 8443"  ✅
```

זו **בעיית הכתיבה המקבילית** — אותה סיבה שלא ניתן לגרום לשני מיקרו-שירותים לכתוב לאותה שורה בבסיס הנתונים בלי פרוטוקול תיאום. הפתרונות במערכות מבוזרות ידועים: concurrency אופטימיסטי (version vectors, פעולות CAS), או CRDTs (סוגי נתונים משוכפלים ללא קונפליקט) שמתמזגים אוטומטית.

פתרתי את זה בשתי דרכים.

### פתרון 1: merge=union (ה-CRDT של העני)

ל-Git יש אסטרטגיית מיזוג לא מוכרת בשם `union`. עבור קבצים שרק מוסיפים להם, היא שומרת את כל השורות משני הצדדים של המיזוג. בלי קונפליקטים. אף פעם. ה-`.gitattributes` שלי:

```
.squad/decisions.md merge=union
.squad/agents/*/history.md merge=union
.squad/log/** merge=union
.squad/orchestration-log/** merge=union
```

זה עובד כי הקבצים האלה הם **לוגים שרק מוסיפים להם**. החלטות מתווספות. רשומות היסטוריה מתווספות. שורות לוג מתווספות. שום דבר לא נערך או נמחק. כששני סוכנים מוסיפים לאותו קובץ על ענפים שונים, `merge=union` פשוט משרשר את שתי התוספות. ככה בדיוק CRDTs עובדים — G-Sets (קבוצות שרק גדלות) ולוגים שרק מוסיפים להם הם הצורה הפשוטה ביותר של שכפול ללא קונפליקט.

### פתרון 2: דפוס תיבת הדואר (מיזוג Inbox)

אבל ל-`merge=union` יש מגבלות. זה לא עוזר כשסוכנים צריכים לכתוב החלטות **מובנות** — כמו החלטות ארכיטקטוניות שדורשות פורמט, הקשר והפניות צולבות. אז בניתי את **דפוס תיבת הדואר**.

כל סוכן כותב את ההחלטה שלו לקובץ משלו ב-`.squad/decisions/inbox/`:

```
  B'Elanna ──→ inbox/belanna-nap-system-pods.md  ┐
  Worf     ──→ inbox/worf-defender-fleet-msg.md   ├──→ Scribe merges ──→ decisions.md
  Data     ──→ inbox/data-350-closure.md          │    (async sweep)
  Seven    ──→ inbox/seven-docs-update.md         ┘
```

```
.squad/decisions/inbox/belanna-nap-system-pods.md
.squad/decisions/inbox/worf-defender-fleet-msg.md
.squad/decisions/inbox/data-350-closure.md
```

אין אפשרות לקונפליקטים — לכל קובץ שם ייחודי. ואז Scribe (סוכן התיעוד) מרוקן מעת לעת את תיבת הדואר, ממזג את ההחלטות הבודדות ל-`decisions.md` הקנוני, ומוחק את קבצי ה-inbox. זו **עקביות סופית** (eventual consistency) עם סוכן מיזוג. אותו דפוס כמו event sourcing עם projection — אירועים בודדים הם בלתי ניתנים לשינוי, התצוגה המצרפית נבנית באופן אסינכרוני.

**הדפוס במערכות מבוזרות:** `merge=union` הוא [G-Set CRDT](https://en.wikipedia.org/wiki/Conflict-free_replicated_data_type) (קבוצה שרק גדלה — ראו [מבוא ל-CRDT ב-crdt.tech](https://crdt.tech/papers.html)). דפוס תיבת הדואר הוא [event sourcing](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing) עם projection מסודר — קשור קשר הדוק ל-[Transactional Outbox pattern](https://event-driven.io/en/outbox_inbox_patterns_and_delivery_guarantees_explained/) שמשמש במיקרו-שירותים (ראו גם [קטלוג דפוסי מערכות מבוזרות של Martin Fowler](https://martinfowler.com/articles/patterns-of-distributed-systems/index.html)). שניהם פותרים את אותה בעיה בסיסית: **איך כותבים מקביליים נמנעים מתיאום בלי לאבד נתונים?**

---

## ה-Prompt שהפך לשם פקודה

מהבאגים האלה שגורמים לך לפקפק בהבנה שלך איך מחשבים עובדים.

חמישה מתוך שמונת ה-Ralphs שלי נכשלו בכל סבב. אותה שגיאה. אותו דפוס. הסקריפט `ralph-watch.ps1` משתמש ב-`Start-Process` כדי להפעיל סשן CLI של Copilot. וה-prompt — מחרוזת multiline של 7KB עם הוראות כמו "MAXIMIZE PARALLELISM" ו-"MULTI-MACHINE COORDINATION" — הועבר כארגומנט.

הנה מה ש-PowerShell עשה עם זה: הוא התייחס **לכל ה-prompt של 7KB כשם הפקודה**. לא הארגומנט. הפקודה. Windows ניסה למצוא קובץ הפעלה בשם `"Ralph, Go! MAXIMIZE PARALLELISM: For every round, identify ALL actionable issues and spawn agents..."` ו — באופן מפתיע — לא הצליח.

זו **בעיית serialization/marshalling**. כשמעבירים נתונים מובנים (prompt מרובה שורות) דרך שכבת תחבורה שלא שומרת על מבנה (פרסור ארגומנטים של שורת פקודה), הנתונים נפגמים. אותו דבר קורה כשמעבירים JSON דרך pipeline של shell, או כשעושים serialize ל-protobuf דרך גבול REST שמצפה לטקסט רגיל.

```
  ❌ BEFORE (direct pass):
  ┌─────────────────────────────┐
  │ Start-Process               │
  │   -ArgumentList $prompt     │  ← 7KB multiline string
  └─────────────┬───────────────┘
                │
      Windows interprets as:
      Command: "Ralph, Go! MAXIMIZE..."
      Args:    (nothing)
      Result:  "Command not found" 💥

  ✅ AFTER (indirection):
  ┌─────────────────────────────┐
  │ $prompt → temp.txt          │  ← write to file
  │ Start-Process               │
  │   --prompt-file temp.txt    │  ← pass reference
  └─────────────┬───────────────┘
                │
      Windows interprets as:
      Command: agency
      Args:    --prompt-file C:\tmp\abc.txt
      Result:  ✅ works
```

התיקון: לכתוב את ה-prompt לקובץ זמני, להעביר את נתיב הקובץ כארגומנט. indirection קלאסי — כשלא ניתן להעביר את הנתונים ישירות, מעבירים הפניה לנתונים.

```powershell
$promptFile = [System.IO.Path]::GetTempFileName()
$prompt | Out-File -FilePath $promptFile -Encoding utf8
agency copilot --yolo --prompt-file $promptFile
```

**הדפוס במערכות מבוזרות:** זה [**message serialization**](https://protobuf.dev/) — דפוס ה-indirection. אותה בעיה ש-[gRPC פותר עם protocol buffers](https://www.geeksforgeeks.org/system-design/protocol-buffer-protobuf-in-system-design/), אותה בעיה ש-Kafka פותר עם schema registry. כששכבת התחבורה לא מסוגלת להתמודד עם פורמט ההודעה, צריך ייצוג ביניים.

---

## Rate Limits: הבעיה שעדיין לא פתרתי

אהיה כנה לגבי זה כי אין לי עדיין תשובה נקייה.

שמונה Ralphs רצים כל חמש דקות. כל סבב, Ralph בודק issues פתוחים, קורא PRs, בודק תגובות, משגר תת-סוכנים. כל תת-סוכן יכול לעשות 10–30 קריאות API ל-GitHub. תכפילו את זה ב-8 ריפוים, 12 סבבים לשעה.

זה פוטנציאלית **אלפי קריאות API לשעה** מול ה-rate limit של GitHub — 5,000 לשעה למשתמש מאומת.

הגעתי לזה. מספר פעמים. Ralph מסיים סבב פרודוקטיבי, והסבב הבא נכשל כי שרפתי את התקציב השעתי. השגיאה שקטה — `gh api` פשוט מחזיר 403 עם header של `retry-after` שאף אחד לא קורא.

```
         GitHub API Rate Limit: 5,000/hour
  ╔═══════════════════════════════════════════╗
  ║ ████████████████████████████████████░░░░░ ║  ← 4,200 used
  ╚═══════════════════════════════════════════╝
       ↑         ↑        ↑        ↑
   Ralph-A   Ralph-B  Ralph-C  Ralph-D ...
    ~600       ~500     ~400     ~700
                                            × 8 repos
                                            × 12 rounds/hr
                                            = 💀
```

עכשיו תדמיינו scaling של זה ל-100+ לקוחות במקביל — תרחיש ריאלי אם מריצים Squad לתוכנית מודרניזציה ארגונית. לכל לקוח יש Ralphs משלו, ריפוים משלו. אם לכל לקוח יש 8 Ralphs שעושים 30 קריאות API לסבב ב-12 סבבים לשעה — זה **288,000 קריאות API לשעה**. ה-rate limit של GitHub צוחק עליכם.

הפתרונות במערכות מבוזרות ידועים: **token bucket rate limiting**, **exponential backoff**, **request coalescing** (איחוד מספר קריאות API לאחת), **read-through caching** (שמירה מקומית של מצב issues/PRs, שליפת דלתות בלבד). התחלתי עם חלק מאלה — מערכת האימייל כבר כוללת retry/backoff אחרי שנתקלתי ב-rate limits על שליחה. אבל בעיית rate limit ה-API הרחבה ב-100+ סקייל? עדיין פתוחה.

**הדפוס במערכות מבוזרות:** זו [**מיצוי משאבים בארכיטקטורת shared-nothing**](https://www.geeksforgeeks.org/system-design/rate-limiting-algorithms-system-design/). כל Ralph עצמאי, אבל כולם חולקים משאב נדיר אחד — ה-rate limit של ה-API. בלי **rate limiter גלובלי** ([token bucket](https://codezup.com/implementing-rate-limiting-distributed-systems-best-practices/) משותף בין תהליכים) או **deduplications של בקשות** (caching), כל תהליך מייעל מקומית וביחד הם חורגים מהגבול הגלובלי. [טרגדיית המשותפים](https://en.wikipedia.org/wiki/Tragedy_of_the_commons), אבל עבור קריאות API.

---

## מה למדתי השבוע

הדבר שהכי הפתיע אותי: לא יצאתי ללמוד מערכות מבוזרות. פשוט ניסיתי לגרום לצוות ה-AI שלי לעבוד. אבל כל באג שנתקלתי בו ממפה 1:1 לבעיה שהתעשייה פותרת כבר עשרות שנים.

| הבעיה שנתקלתי בה | הדפוס הקלאסי | מה שבניתי |
|---|---|---|
| 8 Ralphs נלחמים על `gh auth` | חלוקת מצב | `GH_TOKEN` מקומי לתהליך → [בידוד `GH_CONFIG_DIR`](https://github.com/jongio/gh-public-gh-emu-setup) |
| קובץ נעילה מת חוסם הפעלה מחדש | זיהוי כשלים / heartbeats | שומר משולש: Mutex + סריקת תהליכים + קובץ נעילה |
| כל ההתראות בערוץ אחד | ניתוב נושאים ב-pub-sub | מפת ניתוב `teams-channels.json` |
| שני סוכנים כותבים ל-`decisions.md` | CRDTs / עקביות סופית | `merge=union` + דפוס inbox של תיבת דואר |
| prompt של 7KB נשחת ב-shell | serialization של הודעות | indirection עם קובץ זמני |
| rate limits של API בסקייל | Token bucket / request coalescing | עדיין לא פתור ב-100+ סקייל |
| ערוץ Teams לא נכון (התנגשות שמות) | Service discovery | פתרון ידני (בינתיים) |

ההקבלה מדהימה. כשיש מספר תהליכים עצמאיים שצריכים להתאם — בין אם אלה מיקרו-שירותים, pods ב-Kubernetes, או סוכני AI — נתקלים באותן בעיות בסיסיות. והפתרונות הם אותם דפוסים בסיסיים.

**אני לא בונה משהו חדש.** אני מגלה מחדש מערכות מבוזרות, באג אחד בכל פעם. המאמרים של Leslie Lamport משנות ה-70? הם על אחר הצהריים של יום שלישי שלי. משפט ה-CAP? הוא מסביר למה קובץ ה-`decisions.md` שלי משתמש בעקביות סופית במקום עקביות חזקה. בעיית הגנרלים הביזנטיים? זה מה שקורה כשקובץ ההיסטוריה של סוכן אחד נפגם וסוכנים אחרים מקבלים החלטות על סמך נתונים שגויים.

חלק ה-AI הוא רק מנוע המחשוב. החלק הקשה — החלק שלא מפסיק להישבר — הוא התיאום. וזו בעיה שהאנושות עובדת עליה מאז שניסינו לראשונה לגרום לשני מחשבים להסכים על משהו.

---

## מה הלאה

יש שאלה גדולה יותר שמסתתרת מאחורי כל זה: מה קורה כשהסוכנים שלכם מתחילים להתרחב מעבר לשליטתכם? כש-Ralphs על מכונות שונות עובדים על אותה בעיה. כשסוכנים יוצרים issues משלהם, סוגרים PRs משלהם, ואתם מבינים שאתם צריכים governance לישויות שלא ישנות. ל-Borg היו פרוטוקולי assimilation. אני אצטרך משהו דומה.

אבל קודם, אני צריך ללכת לתקן rate limiter.

---

*הפוסט הזה הוא חלק 4 בסדרה "Scaling AI-Native Software Engineering".*

> - **חלק 0**: [מאורגן על ידי AI — איך Squad שינה את העבודה היומית שלי](/blog/2026/03/10/organized-by-ai)
> - **חלק 1**: [ההתנגדות חסרת תועלת — צוות הנדסת ה-AI הראשון שלך](/he/2026/03/11/scaling-ai-part1/)
> - **חלק 2**: [הקולקטיב — ידע ארגוני לצוותי AI](/he/2026/03/12/scaling-ai-part2-collective/)
> - **חלק 3**: [Unimatrix Zero — מספר צוותים, ריפו אחד עם SubSquads](/blog/2026/03/15/scaling-ai-part3-streams)
> - **חלק 4**: [כשמונה Ralphs נלחמים על Login אחד — מערכות מבוזרות בצוותי AI](/he/2026/03/17/scaling-ai-part4-distributed/) ← אתם כאן

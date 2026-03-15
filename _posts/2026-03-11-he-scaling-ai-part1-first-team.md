---
layout: post-he
title: "ההתנגדות חסרת תועלת — צוות הנדסת AI הראשון שלך בעבודה"
date: 2026-03-11
tags: [ai-agents, squad, github-copilot, scaling, team-workflows, productivity]
series: "Scaling AI-Native Software Engineering"
series_part: 1
lang: he
dir: rtl
permalink: /he/2026/03/11/scaling-ai-part1/
sitemap: false
comments: false
---

עכשיו אתם כבר מכירים את הסיפור. ב[חלק 0](/blog/2026/03/10/organized-by-ai) סיפרתי לכם איך Squad הפך למערכת הפרודוקטיביות הראשונה שלא נטשתי אחרי שלושה ימים. עכשיו אראה לכם איך Ralph וצוות Star Trek שלי טמעו את ה-backlog שלי בזמן שישנתי.

זה היה ב-repo האישי. מגרש המשחקים שלי. ארגז החול הניסיוני שבו Picard יכול לקבל החלטות ארכיטקטוניות בשעה שתיים בלילה ואף אחד לא יתלונן.

ואז הגיעה השאלה שהתחמקתי ממנה: *אפשר להביא את זה לעבודה האמיתית שלי?*

הצוות שלי ב-Microsoft מנהל פלטפורמת תשתית בקנה מידה גדול — מהסוג שבו שירותי Azure אמיתיים תלויים במה שאנחנו מספקים. יש לנו תקני code review, סריקות אבטחה, דרישות compliance, שערי deployment. שישה מהנדסים, כל אחד עם מומחיות עמוקה. מערכות production שלא סובלות "ל-AI agent שלי היה רעיון מעניין בשלוש בלילה."

זה לא מגרש משחקים. האם Squad באמת יכול לעבוד כאן?

מסתבר שכן. אבל לא על ידי העתקה-הדבקה של ההגדרות האישיות שלי. הפריצה לא הייתה ללמד את Squad לעבוד *מסביב* לצוות שלי — אלא ללמד אותו לעבוד *ביחד איתו*.

![Resistance is futile](/assets/scaling-ai-part1-first-team/borg-resistance-is-futile.jpg)
*"ההתנגדות חסרת תועלת. צוות העבודה שלכם ייטמע. כנראה."*

---

## רגע, מה עם הצוות שלי?

הנה הבעיה: ב-repo האישי שלי, אני בן האדם היחיד. Picard מנהל את ההצגה. Data כותב קוד. Seven כותבת תיעוד. אף אחד לא צריך אישור כי אין ממי לבקש.

אבל בצוות הנדסה אמיתי? שם יש שישה בני אדם עם דעות, מומחיות וסמכות merge. אתם לא יכולים סתם לזרוק צוות AI לתוך זה ולומר "תטמיעו את ה-backlog."

בעצם... אפשר. אבל רק אם עושים את הדבר האחד שמשנה הכול:

**הופכים את בני האדם לחלק מה-Squad.**

---

## חברי Squad אנושיים — לא מעקף, אלא כל העניין

זוכרים בחלק 0 כשהראיתי לכם את מערכת ה-casting של Squad? Picard כמוביל, Data כמומחה קוד, Worf על אבטחה? זה עובד מצוין כשאתם בני האדם היחידים.

אבל הנה מה שעשיתי ב-repo של העבודה: הוספתי את *המהנדסים האמיתיים שלנו* ל-`.squad/team.md`.

**חברי Squad אנושיים:**

```markdown
## Human Members

- **John Doe** (@j__ohndoe) — Human Squad Member
  - Role: Engineering Lead
  - Expertise: Squad architecture, platform design, Go/C#
  - Scope: Architecture review, cross-team coordination, Squad framework itself

- **Tamir Dresher** (@tamirdresher) — Human Squad Member  
  - Role: AI Integration Lead
  - Expertise: AI workflows, DevOps automation, C#/.NET
  - Scope: Squad adoption, agent orchestration, integration patterns

- **Worf** (@worf-security) — Human Squad Member
  - Role: Security & Compliance
  - Expertise: Compliance & security, supply chain security, threat modeling
  - Scope: Security reviews, compliance validation, infrastructure hardening

- **B'Elanna Torres** (@belanna-infra) — Human Squad Member
  - Role: Infrastructure
  - Expertise: Kubernetes, Azure networking, CI/CD
  - Scope: Cluster operations, deployment automation, infrastructure code
```

**חברי Squad שהם AI:**

```markdown
## AI Agents

- **Picard** (AI Lead)
  - Role: Architecture & Orchestration
  - Scope: Task decomposition, design review, delegation
  - Routes to: John Doe (human), Tamir (human)

- **Data** (AI Code Expert)
  - Role: Code analysis, review, implementation
  - Scope: Go operators, C# tooling, code quality
  - Routes to: John Doe (human, for design), Worf (human, for security)
```

רואים מה קרה פה? **John Doe הוא לא סתם "הבחור שבודק PRs." הוא חבר Squad.** גם Worf. גם B'Elanna. יש להם תפקידים, תחומי מומחיות ותחומי אחריות — בדיוק כמו לסוכני ה-AI.

כללי הניתוב ב-`.squad/routing.md` מגדירים מתי חברי Squad שהם AI עוצרים ומסלימים לחברי Squad אנושיים:

```markdown
## Routing Rules

### Architecture Decisions
- **Trigger:** Changes to CRD schemas, API contracts, multi-repo dependencies
- **Route to:** @j__ohndoe (human)
- **AI action:** Analysis + recommendations, then pause for human approval

### Security Reviews
- **Trigger:** Authentication, secrets, network policies, supply chain changes
- **Route to:** @worf-security (human)
- **AI action:** Automated scans + findings, then pause for human sign-off

### Go Operator Code
- **Trigger:** Reconciler logic, Kubernetes client code, controller changes
- **Route to:** Data (AI) → @j__ohndoe (human review)
- **AI action:** Implementation, tests, then PR for human review

### Documentation
- **Trigger:** READMEs, troubleshooting guides, API docs, design docs
- **Route to:** Seven (AI) → @tamirdresher (human review)
- **AI action:** Draft, then ping human for review before merge
```

זו הפריצה. ב-repo האישי שלי, Squad היה *הצוות שלי* — סוכני AI שעובדים בשבילי. ב-repo של העבודה, Squad הפך ל*צוות שלנו* — בני אדם ו-AI עובדים יחד, עם מסלולי הסלמה ברורים כשנדרש שיקול דעת אנושי.

חברי ה-Squad שהם AI מטפלים בעבודה השחורה. חברי ה-Squad האנושיים מטפלים בהחלטות שדורשות שיקול דעת. אף אחד לא מבזבז זמן על עבודה שהצד השני יכול לעשות טוב יותר.

---

## אבל קודם: ה-Onboarding ששינה הכול

לפני שנתתי להם את המשימה הראשונה, עשיתי משהו שהתברר כצעד הכי חשוב: עשיתי להם onboarding. בדיוק כמו שעושים לעובד חדש, אמרתי ל-squad לסרוק את כל ה-repo — מוסכמות, תיעוד, ארכיטקטורה, דפוסים, הכול. נתתי להם קישורים לתיעוד הפנימי שלנו, חומרי עזר פנימיים, ערוץ ADR, וכל חומר רפרנס שרציתי שיכירו. הם אינדקסו את הכול ובנו את בסיס הידע שלהם לפני שכתבו שורת קוד אחת.

זה כמו לגייס חמישה מהנדסים שבאמת קוראים את מסמכי ה-onboarding. חוץ מזה שהם לא רק קראו — הם סינתזו. הם מצאו דפוסים שאפילו אני לא ידעתי שקיימים. הם בנו תיקייה `.squad/knowledge/` עם סיכומים מובנים של הסטנדרטים שלנו, הכלים שלנו, תהליך ה-deployment שלנו, מוסכמות הבדיקות שלנו. עד שהתחילו במשימה הראשונה בפועל, הם הבינו את ה-codebase שלנו טוב יותר מרוב האנשים שנמצאים כאן כבר חודשים.

אז זה הרגע שהבנתי: זה לא רק אוטומציה. זה העברת ידע בקנה מידה.

---

## ללמד את ה-Squad על ה-Codebase שלכם

הנה משהו שאף אחד לא אומר לכם על סוכני AI: אי אפשר סתם להצביע להם על repo ולומר "קדימה." זה כמו לגייס מהנדס בכיר ולזרוק אותו ביום הראשון בלי הקשר, בלי קישורים ל-wiki, בלי סקירת ארכיטקטורה, ולצפות ל-PRs ברמת production עד הצהריים.

אז עשיתי מה שכל ראש צוות הנדסה היה עושה — בניתי תוכנית onboarding. ברצינות. אותו סוג של תוכנית onboarding שהייתי בונה לחבר צוות אנושי חדש שמצטרף לצוות פלטפורמת התשתית שלנו. רק שהפעם זה היה ל-AI squad שלי.

הדבר הראשון שעשיתי אחרי יצירת הצוות? אמרתי להם **לסרוק הכול**. כל קובץ, כל דפוס, כל החלטה ארכיטקטונית קבורה בהיסטוריית ה-commits. נתתי להם קישורים לתיעוד הפנימי שלנו, חומרי עזר פנימיים, רשומות החלטות ארכיטקטורה, הפניות למדריכי פתרון בעיות — ממש כל פיסת הקשר שחבר צוות חדש היה צריך כדי להתחיל. ואתם יודעים מה? הם אינדקסו הכול. בנו בסיס ידע מאפס. עד שהתחילו במשימה הראשונה, הם כבר הבינו את המוסכמות שלנו, דפוסי הטיפול בשגיאות שלנו, גישת הבדיקות שלנו — טוב יותר מרוב בני האדם בחודש הראשון שלהם.

זה החלק שפוצץ לי את הראש: למעשה עשיתי onboarding לחברי צוות חדשים, והם *למדו*. לא רק ביצעו הוראות — ממש בנו הבנה של איך אנחנו עובדים. הנה איך זה התנהל:

### שלב 1: סריקת ה-Repo

נתתי ל-Picard (מוביל AI) הוראה פשוטה:

```
Scan the entire repo. Look for patterns in:
- How we structure Go packages
- Testing conventions
- Error handling patterns
- Documentation style
- Commit message format
```

Picard האציל ל-Data (מומחה קוד) ול-Seven (מומחית תיעוד), ותוך דקות חזרו עם ניתוח מפורט:
- בדיקות Go תמיד משתמשות בדפוסי table-driven
- עטיפת שגיאות עם `fmt.Errorf` + `%w`
- דפוסי client-go של Kubernetes ל-reconcilers
- Conventional Commits לכל ההודעות

לא אמרתי להם שום דבר מזה. הם *גילו את זה בעצמם* מקריאת הקוד. זה הרגע שהבנתי שזו לא רק אוטומציה — זו זיהוי דפוסים אמיתי שמופעל על ה-codebase שלנו.

### שלב 2: אינדוקס תיעוד פנימי

יש לנו מדריכי פתרון בעיות, מסמכי ארכיטקטורה, וידע שבטי מפוזר ב:
- דפי תיעוד פנימיים
- Wiki של הצוות ב-Azure DevOps
- קבצי README ב-12 repos שונים
- שרשורי Teams (כן, באמת)

נתתי ל-Seven (מומחית תיעוד AI) קישורים לתיעוד הפנימי שלנו, wiki של Azure DevOps, וכל הפניה פנימית שיכולתי לחשוב עליה — מדריכי פתרון בעיות, מסמכי ארכיטקטורה, נהלי deployment, אפילו הידע השבטי הקבור במסמכי עיצוב ישנים שאף אחד לא קורא יותר. אמרתי לה:

```
Index everything. Build a knowledge base of:
- How our platform works
- Common failure patterns
- Deployment procedures
- Regulatory compliance requirements
```

היא יצרה `.squad/knowledge/` עם סיכומי markdown של כל המסמכים הקריטיים. עכשיו כשכל חבר squad עובד על משימה, יש לו גישה מיידית לידע המוסדי שלנו — הדברים שבדרך כלל לוקח חודשים של שיחות מסדרון וגלילה ב-Teams כדי לספוג.

### שלב 3: בניית תוכנית ה-Onboarding

עם סיום הסריקה והאינדוקס, שאלתי את Picard:

```
Build an onboarding plan for new squad members. What do they need to know?
```

Picard יצר מסמך onboarding מובנה (`.squad/onboarding.md`) שמכסה:
- מבנה ה-repo וה-packages המרכזיים
- תהליך פיתוח (אסטרטגיית branch, תהליך PR)
- דרישות בדיקות
- תהליך deployment
- איפה למצוא תיעוד כשנתקעים

עכשיו כשמוסיפים סוכן AI חדש ל-squad (או כשאני או מישהו אחר בצוות מוסיף מהנדס *אנושי* חדש), הם עוברים את אותו onboarding. אנושי או AI, כולם לומדים את אותן מוסכמות. תוכנית ה-onboarding היא בסיס הידע, ובסיס הידע תמיד מעודכן כי ה-squad מתחזק אותו.

אני לא יכול להדגיש מספיק: **זה הדבר עם ההשפעה הכי גדולה שעשיתי**. לפני שאיזשהו agent כתב שורת קוד אחת, הם הבינו את העולם שלנו. הם ידעו את הדפוסים שלנו, המוסכמות שלנו, איפה למצוא תיעוד, איך נראה תהליך ה-deployment. הם היו *מוכנים*.

### שלב 4: למידה מתמשכת

הידע של Squad לא סטטי. כל החלטה שאנחנו מקבלים נרשמת ב-`.squad/decisions.md`:

```markdown
## Decision: Use testify for Go test assertions
- Date: 2026-02-15
- Context: Needed consistent assertion library across repos
- Decision: Standardize on testify/assert and testify/require
- Rationale: Better error messages, widely adopted in Kubernetes community
```

כשחבר squad (AI או אנושי) מקבל החלטה, היא מתועדת. כשמשימות עתידיות מגיעות, חברי squad בודקים קודם את `.squad/decisions.md`. בסיס הידע גדל באופן אורגני.

זה קריטי: **Squad לא רק מבצע משימות — הוא לומד את התרבות של הצוות שלכם.**

---

---

## מה חברי Squad שהם AI באמת עושים

הנה מה שהכי הפתיע אותי באיך שזה התממש בפרקטיקה.

ציפיתי שחברי ה-Squad שהם AI יהיו כמו מפתחים ג'וניורים — שימושיים לעבודה שחורה, אבל צריכים פיקוח מתמיד. מה שקיבלתי היה משהו קרוב יותר לחמישה חברי צוות שלא ישנים אף פעם, לא מתלוננים על עבודה משעממת, ובאמת *קוראים את מסמך מוסכמות הצוות* לפני שמגישים PR. (אם ניהלתם מהנדסים, אתם יודעים שהחלק האחרון הוא הנס האמיתי.)

הדבר הראשון ששמתי לב אליו היה code reviews. כש-PR מגיע, Data עושה מעבר ראשון לפני שבן אדם רואה אותו. לא בדיקת linting מהירה — אני מתכוון ל-review אמיתי. הוא סורק שגיאות לא מטופלות, contexts דולפים, בדיקות חסרות, credentials בקוד, הכול. הוא בודק הכול מול מוסכמות הצוות שלנו ב-`.squad/decisions.md`. עד שJohn Doe או אחד מחברי ה-Squad האנושיים פותח את ה-PR, הדברים הברורים כבר מסומנים. זה כמו שיש reviewer בלתי נלאה שתופס את הדברים שבני אדם מפספסים כי הם ב-PR הרביעי של אחר הצהריים ורק רוצים ללכת הביתה.

ואז יש scaffolding של בדיקות. הנושא הזה באמת שינה את איך שאנחנו משחררים פיצ'רים. לכל פיצ'ר חדש, Data מייצר את כל שלד הבדיקות — unit tests, מבנה integration tests, הגדרת dependency injection, mocks, מעקב coverage. הוא מעביר את זה לחבר squad אנושי כדי למלא את ה-assertions של הלוגיקה העסקית. התירוץ "אני אוסיף בדיקות אחר כך"? מת. אי אפשר להגיד שתוסיפו בדיקות אחר כך כשקובץ הבדיקה כבר שם, מחכה לכם, עם הערות מועילות על מה לבדוק. זה שיפור הפרודוקטיביות הכי פסיבי-אגרסיבי שחוויתי.

Seven מטפלת בסנכרון תיעוד, ובכנות, זה מה שהכי לא העריכתי נכון. היא עוקבת אחרי שינויי קוד שמשפיעים על תיעוד — שינויי CRD schema, flags חדשים לפקודות, שינויים ב-Helm charts — ומייצרת אוטומטית טיוטות עדכוני תיעוד, פותחת PR, ומתייגת את בן האדם שכתב את שינוי הקוד לבדיקה. סחיפת תיעוד הייתה הבושה השקטה שלנו. עכשיו זה פשוט... לא קורה. בניגוד ל-repo האישי שלי שבו Seven יכולה לעשות merge לתיעוד בחופשיות, כאן היא מחכה לאישור של חבר squad אנושי. אבל הטיוטות מספיק טובות כדי שבדיקות לוקחות שניות.

סריקת אבטחה הפכה לרציפה במקום שער בסוף. Worf (מוביל האבטחה האנושי שלנו) מאציל את הסריקה השיטתית לחברי squad שהם AI — פגיעויות dependencies, זיהוי secrets, ניתוח supply chain, יצירת SBOM, בדיקות compliance. ממצאים נרשמים ב-`.squad/decisions.md` עם צעדי תיקון. בעיות קריטיות עוצרות את ה-build ומנותבות ל-Worf לבדיקה. אבטחה היא כבר לא משהו שאנחנו מרכיבים בזמן השחרור. היא פשוט... רצה. כל הזמן.

ואז יש תיאום cross-repo, שהיה הדבר שהכי פחדתי ממנו. הפלטפורמה שלנו משתרעת על 12 repos. כשינוי ב-repo אחד משפיע על אחרים — שינוי API contract, עדכון shared library — Picard מזהה את ההשפעה ב-downstream, פותח issues מעקב ב-repos המושפעים, יוצר תוכנית תיאום עם PRs ברצף, ומפקח על ה-rollout. ואז מעביר את התוכנית ל-John Doe לאישור לפני ביצוע. שינויים multi-repo שפעם לקחו ימים של "היי, עדכנת את repo X?" עכשיו קורים עם תוכנית מאושרת אחת.

הדפוס בכל זה זהה: חברי squad שהם AI מטפלים בעבודה השיטתית. חברי squad אנושיים מטפלים בהחלטות שיקול דעת. אף אחד לא מבזבז זמן על עבודה שהצד השני יכול לעשות טוב יותר. ובכנות? גם בני האדם השתפרו בעבודה שלהם, כי סוף סוף היה להם זמן לחשוב לעומק על ארכיטקטורה במקום לטבוע בשגרה היומיומית.

---

## המבחן האמיתי הראשון

אחרי שלושה שבועות, חיברתי את Squad ל-repo של אשף הקצאת Kubernetes שלנו. Squad בנושא Matrix הפעם: Morpheus כמוביל, Trinity על Backend, Switch על Frontend, Dozer על בדיקות. הפניתי אותם ללוח Microsoft Planner שלנו (52 משימות פתוחות), הגדרתי שכל משימה תקבל git worktree משלה, ואמרתי "קדימה."

חמש חקירות הושקו בו-זמנית. צפיתי בחמישה חלונות טרמינל מסתובבים במקביל, כל סוכן מושך משימת Planner אחרת ל-worktree משלו.

בתוך השעה הראשונה, Dozer מצא באג אמיתי: ה-MCP ClientID היה מוגדר לא נכון — העברנו ערך שגוי לשכבת האימות שלנו ואף אחד לא תפס את זה כי בדיקות האינטגרציה עשו לזה mock. Trinity סימנה שיש לנו `gpt-4o` hardcoded בשלושה מקומות — סיכון פרישה כי Azure OpenAI הוציא מהשימוש את שם ה-deployment הזה. Switch מצא handler של `onClick` באשף ה-React provisioning שהיה מחובר ב-JSX אבל בלי מימוש. סתם פונקציה ריקה שיושבת שם, מחכה לבלבל מישהו.

אף אחד מאלה לא היה תיאורטי. אלה היו באגים אמיתיים בקוד הקרוב ל-production ששישה בני אדם החמיצו במהלך code reviews רגילים.

החלק הכי שימושי לא היה הבאגים עצמם — אלא ה*מהירות*. חמש חקירות מקבילות, כל אחת ב-worktree משלה, כל אחת מייצרת PR עם בדיקות. עד סוף היום, היו לי חמישה PRs מוכנים לבדיקה אנושית. ביום רגיל, זה שבוע עבודה לאורך הצוות.

גם התראות Teams עזרו כאן. כל פעם שסוכן היה צריך קלט אנושי או סיים משימה, קיבלתי ping. בדקתי PRs מהטלפון באמצע ישיבה (אל תספרו למנהל שלי).

---

## יכולות נסתרות ששינו הכול

ברגע ש-Squad רץ על ה-repo של העבודה, נתקלתי בפיצ'רים שלא ראיתי באף תיעוד. הם לא היו מוסתרים — פשוט לא הייתי צריך אותם עד שעבדתי בקנה מידה של צוות.

### Export/Import: מזרעים Repos חדשים בלי להתחיל מאפס

הגדרות Squad ניתנות לייצוא מ-repo אחד ולייבוא לאחר. ככה מזרעים repos חדשים בלי להתחיל מאפס — לוקחים את הגדרות הצוות, כללי הניתוב, בסיס הידע ויומן ההחלטות מ-repo עובד ומשתילים אותם.

```bash
squad export --output ./squad-template
```

זה מוציא את כל תיקיית `.squad/` שלכם לתבנית ניידת. ואז ב-repo חדש:

```bash
squad import --from ./squad-template
```

ה-repo החדש מקבל את מבנה הצוות, כללי הניתוב, המוסכמות, והיסטוריית ההחלטות — מוכן להתאמה אישית. כשעשינו onboarding ל-repo השני שלנו, מה שלקח שבועיים בפעם הראשונה לקח עשרים דקות.

### אינטגרציית Aspire/OpenTelemetry: שכבת ה-Observability החסרה

כשמריצים סוכני Squad דרך .NET Aspire (שכיסיתי ב[פוסט קודם](/blog/2025/12/16/scaling-ai-agents-with-aspire-isolation.html)), מקבלים distributed tracing מלא של פעולות הסוכנים. כל משימת סוכן מופיעה כ-span ב-dashboard של Aspire. אפשר לראות שימוש ב-tokens, latency של API calls, ואיזה סוכן עושה מה — הכול באותו מקום שבו מנטרים את השירותים האמיתיים.

זו הייתה שכבת ה-observability החסרה. לפני זה, פעולות סוכנים היו קופסה שחורה — היינו מפעילים חמש משימות מקבילות ופשוט... מקווים. עכשיו אני יכול לראות ש-Data השקיע 45 שניות ב-code review, השתמש ב-12K tokens, ביצע 3 API calls למודל השפה, ויצר review עם 7 ממצאים. כשמשימת סוכן לוקחת יותר מדי זמן, אני יכול לראות בדיוק איפה היא תקועה. כשעלויות קופצות, אני יכול לעקוב עד לסוכן והפעולה הספציפיים.

### התראות Teams: שומרים על בני אדם בתמונה בלי החלפת הקשר

Squad יכול להודיע לערוץ הצוות שלכם כשמשימות מסתיימות, כשנדרשת בדיקה אנושית, או כשמשהו נכשל. הקונפיגורציה היא שורה אחת ב-`.squad/config.yml`:

```yaml
notifications:
  teams:
    webhook: <url>
```

זהו. עכשיו כש-Picard מסיים לפרק משימה, כש-Data פותח PR לבדיקה, כש-Worf מסמן ממצא אבטחה — הצוות שלכם מקבל ping ב-Teams. בלי לבדוק טרמינלים. בלי "האם הסוכן סיים כבר?" ההתראה כוללת סיכום וקישור ישיר ל-PR או issue. זה מה שאפשר את תהליך העבודה "בדקתי PRs מהטלפון באמצע ישיבה".

---

## מה הלאה

הפוסט הזה כיסה צוות אחד עם Squad אחד. אבל מה קורה כשהחלטות ב-repo A צריכות לחול על repo B? כשתקני קוד צריכים להתפשט על 12 repos בלי העתקה-הדבקה?

ב[חלק 2](/blog/2026/03/12/scaling-ai-part2-collective) אראה איך מודל ה-upstream inheritance של Squad הופך צוותים מבודדים לקולקטיב מחובר. האנלוגיה ל-Borg הולכת ונהיית יותר מדויקת. 🖖

---

> 📚 **Series: Scaling AI-Native Software Engineering**
> - **חלק 0**: [מאורגן על ידי AI — איך Squad שינה את שגרת העבודה היומית שלי](/blog/2026/03/10/organized-by-ai)
> - **חלק 1**: ההתנגדות חסרת תועלת — צוות הנדסת AI הראשון שלך בעבודה ← אתם כאן
> - **חלק 2**: [הקולקטיב — ידע ארגוני לצוותי AI](/blog/2026/03/12/scaling-ai-part2-collective)
> - **חלק 3**: Unimatrix Zero — בקרוב

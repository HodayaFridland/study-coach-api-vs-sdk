# Study Coach: סוכן אחד, שני harnesses

**Study Coach** הוא מאמן לימודים אישי. הוא:
- שומר מבחנים ומפגשי לימוד.
- זוכר העדפות בין שיחות (למשל "עדיף לי ללמוד בערב, עד שעתיים ביום").
- בודק בלוח השנה העברי (Hebcal API) שלא קובעים מפגש לימוד בחג.

את אותו הסוכן בניתי פעמיים:

| | `API/` | `SDK/` |
|---|---|---|
| מי מריץ את הלולאה | הקוד שלי (`API/harness/loop.py`) | Claude Code (דרך `claude-agent-sdk`) |
| חיוב | מפתח API מ-Claude Console | ה-login של Claude Code |
| הכלים | אותם 6 כלים מ-`shared/` | אותם 6 כלים מ-`shared/`, עטופים ב-`@tool` |

## הרצה

מתיקיית הפרויקט, ב-PowerShell:

```powershell
# פעם אחת: סביבה עם גרסאות נעולות
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# בדיקות offline (בלי מפתח ובלי רשת)
.venv\Scripts\python -m pytest -q tests

# גרסת API: המפתח רק כמשתנה סביבה בטרמינל הזה, לעולם לא בקוד
$env:ANTHROPIC_API_KEY = "sk-ant-..."
.venv\Scripts\python API/main.py --scenario scenario.json --out results/api.json
Remove-Item Env:ANTHROPIC_API_KEY     # חובה לפני ה-SDK, אחרת החיוב עובר למפתח

# גרסת SDK: רצה על ה-login של Claude Code
.venv\Scripts\python SDK/main.py --scenario scenario.json --out results/sdk.json

# עדכון הטבלאות ב-REPORT.md מתוך קובצי התוצאות
.venv\Scripts\python shared/report.py
```

כל הרצה כותבת גם לוג מלא לצד התוצאות (`results/api.log`, `results/sdk.log`).

כדי פשוט לדבר עם הסוכן: `python API/main.py --chat` או `python SDK/main.py --chat`. מוסיפים `--resume` כדי להמשיך את השיחה הקודמת.

## מבנה

```
shared/            קוד הדומיין, משותף לשתי הגרסאות
  specs.py         המודל, ה-effort, ה-system prompt ותיאורי 6 הכלים (עותק אחד, כדי שההשוואה תהיה הוגנת)
  planner.py       מבחנים ומפגשים (study.json), פלט כלים קומפקטי, ToolError
  calendar_api.py  הכלי החיצוני: Hebcal API, מחזיר שורה אחת לכל חג
  memory_store.py  פורמט הזיכרון (memory.json): ערך חדש מחליף ישן, והישן נשמר ב-previous
  scenario.py      מדידה: snapshot של המצב, בדיקות pass/fail, ספירת שורות, קובץ תוצאות
  report.py        בונה את הטבלאות ב-REPORT.md
API/
  main.py, agent.py
  harness/         קובץ לכל אחריות, וכל פעולה מודפסת עם שם הקובץ: [loop.py] ...
    loop.py        while stop_reason == "tool_use", וכל ה-tool_result חוזרים בהודעה אחת
    tools.py       סכמות JSON, dispatch, ושגיאות שחוזרות למודל כ-is_error
    history.py     השיחה ב-JSONL, append-only (גם compaction נרשמת כשורה חדשה)
    memory.py      איפה הזיכרון נשמר, ושליפה של הרלוונטי בלבד (top-k)
    context.py     מה נכנס לכל תור: רק עובדות חדשות ורלוונטיות, אף פעם לא כל התוכנית
    compaction.py  מעל סף טוקנים: סיכום כל השיחה, והמשך מהסיכום בלבד
    caching.py     שתי נקודות cache_control: סוף ה-system, וסוף ההודעה האחרונה
    tokens.py      טוקנים ועלות לכל קריאה ולכל תור
SDK/
  main.py, agent.py, tools.py    כל שורה שמחליפה קובץ מ-harness מסומנת "# replaces: <file>"
tests/             26 בדיקות offline עם client מדומה, בלי מפתח
scenario.json      7 פניות בשני סשנים, ו-9 בדיקות
results/           api.json, sdk.json (+ לוגים של ההרצות)
REPORT.md          ההשוואה
```

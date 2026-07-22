1\. Vstup 1: Chybné instrukce

Load the uploaded Chybné instrukce Excel file.



Expected columns:

\- ProductsWrongInstructions\_ID

\- Kód produktu

\- StoreJob\_ID

\- Přeložené instrukce

\- Jméno uživatele

\- Pobočka

\- Host

\- Vytvořeno

\- Zkontrolováno

\- Zkontrolováno logistikou datum

\- Název stanice

Vytvor výstup reports\_clean

Create reports\_clean by cleaning the raw reports.



Rules:

\- Convert Kód produktu to text.

\- Trim and clean Kód produktu.

\- Trim and clean Přeložené instrukce.

\- Trim and clean Jméno uživatele.

\- Trim and clean Pobočka.

\- Trim and clean Název stanice.

\- Trim and clean StoreJob\_ID.

\- Convert Vytvořeno to datetime if possible.

\- Keep one row per original F9 report.

\- Do not deduplicate reports\_clean.



reports\_clean columns:

\- report\_id = ProductsWrongInstructions\_ID

\- Kód produktu

\- StoreJob\_ID

\- Přeložené instrukce

\- Jméno uživatele

\- Pobočka

\- Host

\- Vytvořeno

\- Zkontrolováno

\- Zkontrolováno logistikou datum

\- Název stanice



2\. Výstup cases\_mvp

Create cases\_mvp from reports\_clean.



A case is defined as:



Kód produktu + Přeložené instrukce



Group reports\_clean by:

\- Kód produktu

\- Přeložené instrukce



For each group calculate:

\- case\_id

\- case\_number

\- Kód produktu

\- Přeložené instrukce

\- report\_count = number of reports in the group

\- unique\_users\_count = number of distinct Jméno uživatele

\- first\_reported\_at = minimum Vytvořeno

\- last\_reported\_at = maximum Vytvořeno

\- branch\_count = number of distinct Pobočka

\- station\_count = number of distinct Název stanice

\- sample\_storejob\_ids = up to first 5 distinct StoreJob\_ID values joined by comma

\- status = "Neriešené"

\- priority

\- owner = empty

\- validator\_note = empty



Sort cases\_mvp by:

1\. report\_count descending

2\. last\_reported\_at descending



case\_id format:

CI-000001

CI-000002

CI-000003

...



Priority logic:

\- report\_count >= 20 → "Vysoká"

\- report\_count >= 5 and report\_count < 20 → "Stredná"

\- report\_count < 5 → "Nízka"



3\. Vstup 2: Produkty a vlastnosti

Load the uploaded Produkty a vlastnosti Excel file.



Create products\_clean.



Convert Kód produktu to text.

Trim and clean Kód produktu.



Keep all columns if possible, but the app must especially preserve these important columns if they exist:



Identification:

\- Kód produktu

\- Název produktu



Segmentation:

\- Segmentace (obecná)

\- Segment1

\- Segment2

\- Segment3

\- SEOPrefix\_ID

\- SC-Skupina



Physical/product parameters:

\- Typ obalu (Logistické parametry)

\- Výška

\- Šířka

\- Hloubka

\- Váha

\- Size1

\- Size2

\- Size3

\- GeoSize (id)



Packaging/storage properties:

\- Dobalovat (Skladová vlastnost)

\- Nebalit (Skladová vlastnost)

\- Bublinková fólie (Skladová vlastnost)

\- Fólie (Skladová vlastnost)

\- Obálka (Skladová vlastnost)

\- Kartonová krabička (Skladová vlastnost)

\- Prelep páskou (Skladová vlastnost)

\- Přelep uzávěr (Skladová vlastnost)

\- Utěsnit uzávěr (Skladová vlastnost)



Risk parameters:

\- IsFragile

\- Lehko poškoditelný (Logistické parametry)

\- Křehký produkt (Logistické parametry)

\- Často poškozovaný / reklamovaný (Skladová vlastnost)

\- Sklo (Logistické parametry)

\- Porcelán (Logistické parametry)

\- Teflon (Logistické parametry)

\- Ostré hrany (Logistické parametry)

\- Tenká lepenka (lego) (Logistické parametry)

\- Lehko znečistitelný (Logistické parametry)

\- Znečistí okolí (Logistické parametry)

\- Tekutý (Logistické parametry)

\- Má šroubovací uzávěr (Logistické parametry)

\- Má lehce oddělitelný uzávěr (Logistické parametry)

\- Sběratelská edice (Logistické parametry)

\- Shockwatch (Skladová vlastnost)



If some columns are missing, do not crash. Show a warning and continue with available columns.



4\. Výstup cases\_enriched

Create cases\_enriched by left joining cases\_mvp with products\_clean.



Join key:

cases\_mvp.Kód produktu = products\_clean.Kód produktu



Keep all rows from cases\_mvp.



Add product columns from products\_clean.



Add product\_match\_status:

\- if Název produktu is null or missing → "Produkt nenájdený"

\- otherwise → "Produkt nájdený"



5\. Pridaj instruction\_category

Add instruction\_category to cases\_enriched.



Use Přeložené instrukce as source text.



Lowercase the text and classify using this order:



if text contains "bublink" → "Bublinková fólie"

else if text contains "karton" or "krabi" → "Kartonová krabička"

else if text contains "obál" or "obalk" → "Obálka"

else if text contains "pásk" or "pask" → "Prelep páskou"

else if text contains "utěsni" or "utesni" → "Utěsnit uzávěr"

else if text contains "přelep" or "prelep" → "Přelep uzávěr"

else if text contains "fóli" or "foli" → "Fólie"

else if text contains "štítek" or "stitek" → "Štítok"

else → "Iné"



Important:

Bublinková fólie must be detected before general Fólie.



6\. Pridaj main\_trigger\_parameter

Add main\_trigger\_parameter based on instruction\_category:



Bublinková fólie → Bublinková fólie (Skladová vlastnost)

Fólie → Fólie (Skladová vlastnost)

Obálka → Obálka (Skladová vlastnost)

Kartonová krabička → Kartonová krabička (Skladová vlastnost)

Prelep páskou → Prelep páskou (Skladová vlastnost)

Přelep uzávěr → Přelep uzávěr (Skladová vlastnost)

Utěsnit uzávěr → Utěsnit uzávěr (Skladová vlastnost)

else → Nezistené



7\. Pridaj trigger\_parameter\_value

Add trigger\_parameter\_value.



For each row, read the value from the column named in main\_trigger\_parameter.



Examples:

\- if instruction\_category = "Bublinková fólie", trigger\_parameter\_value = value of "Bublinková fólie (Skladová vlastnost)"

\- if instruction\_category = "Fólie", trigger\_parameter\_value = value of "Fólie (Skladová vlastnost)"

\- if instruction\_category = "Obálka", trigger\_parameter\_value = value of "Obálka (Skladová vlastnost)"



If main\_trigger\_parameter = "Nezistené" or the target column does not exist, set trigger\_parameter\_value to null.



8\. Pravdivostná logika

Create a helper function is\_active(value).



Treat these values as active/true:

\- 1

\- "1"

\- true

\- TRUE

\- "TRUE"

\- "PRAVDA"

\- "Ano"

\- "Áno"

\- "Yes"

\- "Y"



Treat these values as inactive/false:

\- 0

\- "0"

\- false

\- FALSE

\- "FALSE"

\- "NEPRAVDA"

\- "Ne"

\- "Nie"

\- "No"

\- null

\- empty string



9\. Pridaj trigger\_detected

Add trigger\_detected.



If is\_active(trigger\_parameter\_value) = true:

\- trigger\_detected = 1

else:

\- trigger\_detected = 0



10\. Pridaj active\_risk\_parameters

Evaluate these risk parameters if the columns exist:



\- IsFragile

\- Lehko poškoditelný (Logistické parametry)

\- Křehký produkt (Logistické parametry)

\- Často poškozovaný / reklamovaný (Skladová vlastnost)

\- Sklo (Logistické parametry)

\- Porcelán (Logistické parametry)

\- Teflon (Logistické parametry)

\- Ostré hrany (Logistické parametry)

\- Tenká lepenka (lego) (Logistické parametry)

\- Lehko znečistitelný (Logistické parametry)

\- Znečistí okolí (Logistické parametry)

\- Tekutý (Logistické parametry)

\- Má šroubovací uzávěr (Logistické parametry)

\- Má lehce oddělitelný uzávěr (Logistické parametry)

\- Sběratelská edice (Logistické parametry)

\- Shockwatch (Skladová vlastnost)



For each row:

\- check each existing risk column with is\_active()

\- collect names of active risk parameters

\- if none are active, set:

&#x20; "Žiadne aktívne rizikové parametre"

\- otherwise join active names with "; "



Output column:

active\_risk\_parameters



11\. Pridaj has\_risk\_flag

Add has\_risk\_flag.



If active\_risk\_parameters = "Žiadne aktívne rizikové parametre":

\- has\_risk\_flag = 0

else:

\- has\_risk\_flag = 1



12\. Pridaj risk\_evaluation

Add risk\_evaluation.



If has\_risk\_flag = 0:

"Produkt nemá aktívne rizikové parametre v dostupných dátach."



If has\_risk\_flag = 1:

"Produkt má aktívne rizikové parametre: {active\_risk\_parameters}. Balenie môže byť oprávnené a musí byť validované opatrne."



13\. Pridaj ai\_decision\_hint

Add ai\_decision\_hint.



Rules:



If product\_match\_status != "Produkt nájdený":

"Produkt sa nepodarilo napojiť na produktové vlastnosti. Odporúčaná manuálna analýza."



Else if trigger\_detected = 1 and has\_risk\_flag = 0:

"Trigger parameter bol nájdený: {main\_trigger\_parameter} = aktívny. Produkt nemá aktívne rizikové parametre. Preveriť, či je tento baliaci parameter nastavený oprávnene."



Else if trigger\_detected = 1 and has\_risk\_flag = 1:

"Trigger parameter bol nájdený: {main\_trigger\_parameter} = aktívny. Produkt má rizikové parametre: {active\_risk\_parameters}. Balenie môže byť oprávnené."



Else if trigger\_detected = 0 and main\_trigger\_parameter = "Nezistené":

"Trigger parameter nie je známy. Preveriť systémovú logiku alebo pravidlo zobrazovania inštrukcie."



Else:

"Dáta sú nejednoznačné. Odporúčaná manuálna analýza."



14\. Výstup ai\_cases\_input

Create ai\_cases\_input from cases\_enriched.



Default filters:

\- product\_match\_status = "Produkt nájdený"

\- instruction\_category != "Štítok"



Default sorting:

\- report\_count descending



Default row limit:

\- TOP 100 rows



The app UI should allow changing:

\- TOP N

\- include/exclude Štítok

\- filter by instruction\_category

\- minimum report\_count

\- product\_match\_status

\- has\_risk\_flag

\- trigger\_detected



15\. Export výsledku

The app must create one output Excel workbook.



Workbook name:

Chybne\_instrukce\_processed.xlsx



Sheets:

1\. reports\_clean

2\. products\_clean

3\. cases\_mvp

4\. cases\_enriched

5\. ai\_cases\_input

6\. summary



The summary sheet should contain:

\- total\_reports

\- total\_cases

\- matched\_products\_count

\- unmatched\_products\_count

\- total\_ai\_input\_rows

\- counts by instruction\_category:

&#x20; - sum report\_count

&#x20; - count case\_id



16\. Streamlit UI

Create a Streamlit UI with:



Section 1: Upload files

\- upload Chybné instrukce Excel

\- upload Produkty a vlastnosti Excel

\- upload Baliace pravidlá Excel



Section 2: Processing settings

\- TOP N input, default 100

\- checkbox exclude Štítok, default true

\- multiselect instruction\_category

\- minimum report\_count



Section 3: Data quality summary

Show:

\- number of reports

\- number of products

\- number of cases

\- number of matched products

\- number of unmatched products

\- instruction\_category pivot



Section 4: Preview tables

\- preview cases\_mvp

\- preview cases\_enriched

\- preview ai\_cases\_input



Section 5: Download

\- download processed Excel workbook



17\. Dôležité pravidlá

Do not call AI in this MVP.

Do not change any product parameters.

Do not write back to source Excel files.

Do not require the user to use Power Query.

The app must replace the manual Power Query workflow.

The output ai\_cases\_input must be ready for upload to AI Studio.






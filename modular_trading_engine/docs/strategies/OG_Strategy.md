# Mechanische Uitleg van de OG Strategie (c0tt0nc4ndyta Framework)

De OG Strategy is een wiskundige, cyclische vertaling van het Day Trading Decrypted (DTD) systeem. Om een bot deze logica na te laten bouwen, moet de flow exact en binar (tested yes/no, holding yes/no) worden gedefinieerd. Hier is de mechanische flow van A tot Z.

### Fase 1: Break Levels Detecteren
Alles begint met het detecteren van de punten die een beweging proberen te breken.
1. **Definitie**: De wicks van twee of meer opeenvolgende candles van dezelfde kleur aan de top of bodem van een beweging.
2. **Mechanische logica**: 
   - **Bottom Side (onderkant)**: Groene candles (2 of meer) creëren een Break Level aan de onderkant van een move.
   - **Top Side (bovenkant)**: Rode candles (2 of meer) creëren een Break Level aan de bovenkant van een move.
   - De bot markeert de allereerste wick van deze reeks van dezelfde kleur als het Break Level, *niet* de meest extreme wick uit die reeks.

### Fase 2: Promotie naar Origin Levels (Polarity Identificeren)
Een Origin Level verdeelt de chart in twee structureel verschillende zones en activeert Polarity.
1. **Definitie**: Een Break Level dat minimaal twee keer onafhankelijk is getest door een wick of body, volgens strikte regels van "scheiding".
2. **Mechanische logica**:
   - **Gegevensverificatie ("tested")**: De wick of de body van een toekomstige candle moet de exacte prijs aanraken of er doorheen prikken. "Close enough" is geen test.
   - **Eerste Test (Test 1)**: De allereerste test mag direct plaatsvinden zodra het Break Level is gevormd. Als er bijvoorbeeld 2 rode candles zijn (het Break Level is in aanleg) en de prijs komt direct omhoog, maakt een groene candle en raakt de high van je eerste rode candle, dan is dát direct je eerste test. Je hoeft hiervoor niet te wachten op de vorming van een nieuw Break Level.
   - **Structurele Separatie (De Nieuwe Break Level Regel voor Test 2+)**: Voor de *tweede* test (en elke volgende test daarna) is wel strikte scheiding verplicht. De tweede test mag alléén plaatsvinden als er tussentijds een **nieuw Break Level is gevormd** ter scheiding. 
     - **Voorbeeld Top Side:** Na je initiële Break Level en eventuele eerste test, bouwt de chart een *nieuw* Break Level (minimaal 2 of meer rode candles) gevolgd door minimaal 1 groene candle. Pas vanaf dit moment mag het originele Break Level voor de *tweede keer* getest worden (deze groene candle mag zelf ook die tweede hit maken).
   - **Herhaling**: Voor élke volgende test (Test 3, Test 4, etc.) moet dit volledige scenario zich blijven herhalen. Er moet onafgebroken wéér een nieuw Break Level geprint worden vóórdat het origineel weer geldig getest kan worden.
   - Zodra de bot de tweede onafhankelijke hit verwerkt, promoveert de variabele van Break Level naar Origin Level. Het markeert nu Polarity en krijgt een `+1` (escaleert naar één timeframe hoger). Alles hierboven is wezenlijk anders in verwachting dan alles hieronder.
   - **De Highlander Regel**: De oudste actieve Origin Level dicteert de actieve Polarity. Dit "Highlander level" blijft dominant actief totdat er een Hard Close plaatsvindt die het gehele level invalideert. Tot die tijd bepaalt deze de hoofdrichting.

### Fase 3: Het Identificeren van Hold Level Kandidaten
Zodra de richting via de Origin Levels is vastgesteld, heeft de bot bescherming nodig: Hold Levels die prijstrending faciliteren en vasthouden.
1. **Definitie**: De body van de diepste rode candle aan de bodem van een vallei, of de hoogste groene candle aan de top van een piek.
2. **Mechanische logica**:
   - **Timing van de zoektocht**: Het ophalen (zoeken) naar een Hold Level kandidaat is exclusief toegestaan op exact twee structurele momenten:
     1. Direct op het moment van **Origin Creatie**.
     2. Direct na **Test 1** van datzelfde Origin Level.
   - **Long Setup (Support)**: De bot zoekt de laagste rode candle waarvan de `open` zich bóven het actieve Origin Level bevindt.
   - **Short Setup (Weerstand)**: De bot zoekt de hoogste groene candle waarvan de `open` zich ónder het actieve Origin Level bevindt.
   - De bot bewaart zowel de body (greedy entry, de beste prijs) als de wick (safe entry, veiliger bereik). Dit is nu een Hold Level kandidaat.

### Fase 4: Validatie via de Hard Close & Deep Dive 
Een kandidaat wordt pas goedgekeurd of een bestaand level wordt pas verwijderd wanneer de Hard Close mathematisch afdwingt wat er met het level gebeurt.
1. **Definitie**: Een candle die sluit met beide kanten van zijn body (zowel open als close) aan één specifieke kant van het level, in de kleur van de bewegingsrichting.
2. **Mechanische logica**:
   - **Deep Dive**: Als een wick door het Hold Level of Break Level prikt (ongeacht hoeveel afstand), maar de body sluit nog netjes aan zijn eigen kant van de grens, is er GEEN Hard Close geprint. De structuur staat nog intact; de bot laat het level op de chart staan. Het wordt of blijft een Reverse Level kandidaat.
   - **Validatie**: Een kandidaat blijft een kandidaat totdat er een mechanische afzetting plaatsvindt in de juiste richting.
   - **Verwijdering / Verloren**: Raakt de open én de close van een rode body onder een bottom Hold Level? Het Hold Level is "hard-closed" in de richting (down). De bot wist het oude Hold Level onmiddellijk van de chart af, hij is doorbroken.

### Fase 5: Trade Executie, Timeout (TTL) en Origin Invalidatie
De engine heeft nu beveiligde levels. Via RAT stapt hij eerder in dan de markt zijn structuur sluit.
1. **Definitie**: Rejection as Target houdt in dat de bot een Hold Level projecteert nog vóórdat deze zichtbaar boven/onder een body sluit, oftewel we positioneren ertegenaan voordat de formatie 100% af is.
2. **Mechanische logica**:
   - De engine scant naar de nieuwste *ongeteste* Hold Level kandidaten. Dit wordt ons toekomstige mikpunt of barrière, werkend als omdraaipunt (RAT).
   - Zolang de Polarity ongestoord blijft plaatst de bot een Limit Order strak op de body / wick van de RAT. 
   - **Timeout Regel (TTL)**: Een open Limit Order mag maximaal **20 candles** open blijven staan.
     - Als de order binnen deze 20 candles niet wordt gevuld, wordt de Limit Order onmiddellijk gecanceld.
     - Vanaf dat moment is deze specifieke setup **niet meer geldig om op te traden**.
   - **Herkansing na Test 1**: Het kan zijn dat de Origin na het verlopen van de eerste setup alsnog geraakt wordt. Dit is dan de **eerste test van een valide Origin Level** (Test 1). 
     - Vanaf dat exacte moment mag de bot wéér op zoek naar een valide Hold Level kandidaat en een nieuwe Limit Order plaatsen.
     - Ook nu geldt de harde eis: **maximaal 20 candles de tijd**. Niet gevuld binnen dit frame? Cancel de orders; de setup is wederom niet meer te traden.
   - **Origin Invalidatie (De Highlander Beperking)**: 
     - Zodra de (re-engagement) setup faalt en afloopt, is dit gehele Origin Level definitief **invalid** geworden voor setup-acquisitie.
     - Test 3, 4, 5, of nog hogere tests van ditzelfde genummerde Origin Level (de Highlander) mogen *absoluut niet* meer getrade worden. Dit voorkomt dat het systeem constant blijft hopen op een uitgewerkte Origin.
     - **Structurele Highlander Status**: Dit 'Invalid for Trading' Origin Level blijft echter wel op de chart staan als de actieve Polarity muur. Hij sneuvelt pas definitief door een Hard Close. Tot die tijd weigert hij trades, maar blokkeert hij structuur.
     - **Nieuwe Onafhankelijke Origins**: Het is mogelijk dat het systeem boven of onder de Highlander muur een nieuw, onafhankelijk Origin Level (inclusief correcte setup) creëert. Deze staat los van de vervallen Highlander. De bot registreert beide slim onder hun eigen ID en mag op de nieuwe, valide structuur wél gewoon positioneren.

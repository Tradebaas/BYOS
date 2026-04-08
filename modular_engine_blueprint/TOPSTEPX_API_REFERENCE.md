# TopStepX (ProjectX) API Reference

**Official Documentation:** [https://gateway.docs.projectx.com](https://gateway.docs.projectx.com)

Dit document beschrijft puur de technische mechanica en endpoints van de ProjectX (TopstepX) REST API voor het plaatsen en beheren van orders.

---

## 1. Environment Configuration (`.env`)

Voor veilige connectie met de gateway dienen de volgende variabelen op OS-niveau geconfigureerd te worden:

```env
# Base URLs
TOPSTEPX_REST_URL="https://api.topstepx.com/api"

# Authentication
TOPSTEPX_AUTH_TOKEN="<valid_jwt_token>"

# Account Specifications
TOPSTEPX_ACCOUNT_ID="<internal_account_id>"
```

*Technische werking:* 
Alle REST HTTP calls vereisen de header `Authorization: Bearer ${TOPSTEPX_AUTH_TOKEN}`. Indien de token expireert, retourneert de server `HTTP 401 Unauthorized`.

---

## 2. Platform Enums

De API accepteert strikte integers (enums) voor order operaties.

### 2.1 Order Types
| Type ID | Order Type | Verplichte JSON parameters |
|:---:|:---|:---|
| **1** | **Limit** | `limitPrice` (Moet een exact 0.25 tick increment zijn op NQ) |
| **2** | **Market** | Geen |
| **3** | **Stop** | `stopPrice` |
| **4** | **Stop Market** | `stopPrice` |
| **5** | **Trailing Stop** | *Configuratie afhankelijk, vereist trailing afstand* |

### 2.2 Market Sides
| Side ID | Richting | Technisch effect |
|:---:|:---|:---|
| **0** | **Buy** | Opent Long (of sluit een bestaande Short). |
| **1** | **Sell** | Opent Short (of sluit een bestaande Long). |

---

## 3. Core Endpoints

### 3.1 Resolving Active Contracts
**Endpoint:** `POST /Contract/search`

Omdat futures periodiek verlopen (roll-over), is een statische ticker (zoals "NQ") ongeldig in de order API. De API vereist het fysieke `symbolId` of `contractId` afhankelijk van de route (bijv. `CON.F.US.ENQ.M25`).

**Request Payload:**
```json
{
  "live": false,
  "searchText": "NQ"
}
```
**Functie:** Retourneert een lijst beschikbare contracten. Filter op `activeContract == true` om de huidig verhandelbare ticker op te halen.

---

### 3.2 Limit Order Entry + Server-Side OCO Brackets (Entry, SL, TP)
**Endpoint:** `POST /Order/place`

Omdat de engine hoofdzakelijk werkt met vooraf berekende wiskundige levels (Target / Hold Levels), is het plaatsen van geruste **Limit orders** de standaard. De API ondersteunt geïntegreerde Take Profit (TP) en Stop Loss (SL) brackets in de order payload. Dit creëert een server-side _One-Cancels-the-Other_ (OCO) koppeling. Als de bracket direct meegeleverd wordt bij de *Entry*, verzekert dit dat zodra de Limit Order vult, de positie direct voorzien is van afdekking.

> [!CAUTION]
> **CRITIEKE OPERATIONELE VEREISTE (AUTO BRACKETS):** 
> Om deze OCO-brackets (de `stopLossBracket` en `takeProfitBracket` in de API payload) daadwerkelijk door TopstepX te laten accepteren en koppelen, **MOET** de instelling **"Auto Brackets"** handmatig zijn ingeschakeld binnen de grafische interface (Frontend/UI) van het TopstepX platform voor het specifieke account. 
> *Als auto-brackets in de UI uitstaan, zal de API de aanhangende SL/TP levels negeren of de order in zijn geheel afwijzen, resulterend in ongedekte ('naked') posities op de markt!*


**Request Payload (Limit Buy met Brackets):**
```json
{
  "accountId": 465,
  "contractId": "CON.F.US.ENQ.M25",
  "type": 1, 
  "limitPrice": 18550.00,
  "side": 0, 
  "size": 1,
  "stopLossBracket": { 
    "ticks": -16, 
    "type": 4     
  },
  "takeProfitBracket": { 
    "ticks": 12,  
    "type": 1     
  }
}
```

**Technische mechanica van relatieve ticks:**
*   `ticks` wordt berekend vanaf de daadwerkelijke vullingsprijs (fill price) van de entry order.
*   **Bij een Long Entry (`side: 0`):** TP ticks zijn *positief* (boven prijs), SL ticks zijn *negatief* (onder prijs).
*   **Bij een Short Entry (`side: 1`):** TP ticks zijn *negatief* (onder prijs), SL ticks zijn *positief* (boven prijs).
*   `type: 4` (Stop Market) is de API-standaard voor Stop Loss executies on NQ.
*   `type: 1` (Limit) is de API-standaard voor Take Profit doelen.

---

### 3.3 Flatten (Positie Scrappen)
**Endpoint:** `POST /Position/close`

**Payload:**
```json
{
  "accountId": 465,
  "contractId": "CON.F.US.ENQ.M25"
}
```
**Functie:** Vuur een directe unconditionele marker order in de inverse richting af die exact hefboomt met de open size, resulterend in netto `0` contracten. Het server-side auto-annuleert actieve SL/TP brackets gekoppeld aan de oorspronkelijke positie (als de broker dit native ondersteunt, anders expliciet `cancelAll` vereist).

---

### 3.4 Cancel All (Werking Opschonen)
**Endpoint:** `POST /Order/cancelAll`

**Payload:**
```json
{
  "accountId": 465,
  "contractId": "CON.F.US.ENQ.M25"
}
```
**Functie:** Annuleert alle `Working` status orders (zoals rustende Limit, Stop of Trailing orders) voor het meegegeven contract. Dit heeft *geen* invloed op reeds afgesloten fills of actieve marktposities.

---

### 3.5 Account Status & Validatie
**Endpoint:** `POST /Account/search`

Voor we acties ondernemen (zeker voor trade deployment over **meerdere accounts**), verifiëren we of een account valide is (voldoende Buying Power / niet de Daily Loss Limit geraakt).

**Request Payload:** 
*(Lege of geen payload, stuurt parameters in body als json)*
```json
{}
```
**Functie:** Retourneert alle accounts van de gebruiker ("accounts" array). Belangrijk hierbij is te checken of `canTrade: true` is per `accountId`.

---

### 3.6 Limit Order Modificatie
**Endpoint:** `POST /Order/modify`

Essentieel om direct te kunnen reageren als structuur verschuift en het Limit order of brackets (OCO) verplaatst moeten worden.

**Request Payload (Aanpassen van Limit of Stops):**
```json
{
  "accountId": 465,
  "orderId": 26974,
  "size": 1,
  "limitPrice": 18552.25, 
  "stopPrice": 18540.00,
  "trailPrice": null
}
```
**Functie:** Wijzigt een bestaande en *actieve* open order (zoals een unfilled Limit, of de Stop Loss bracket van een filled entry). Hiermee voorkomen we 'Cancel+Replace', wat prioriteit in de queue kost.

---

### 3.7 Actieve Status Opvragen (Orders & Posities)
Voor orkestratie-controles vragen we bulk statussen op per account. Hierdoor bepalen we exact of de bot open targets of brackets heeft staan op een specifiek account.

*   **Open Orders Checken:** `POST /Order/searchOpen`
    *   **Payload:** `{ "accountId": 465 }`
    *   **Functie:** Retourneert alle rustende/open orders in de markt (Limit, actieve Brackets).
*   **Open Posities Checken:** `POST /Position/searchOpen`
    *   **Payload:** `{ "accountId": 465 }`
    *   **Functie:** Retourneert de daadwerkelijke marktpositie (netto long of short contracten, de `averagePrice` en `size`).

---

## 4. Real-Time Data (WebSocket via SignalR)

Voor high-performance orchestratie over meerdere accounts luisteren we live mee in plaats van agressieve REST polling. De ProjectX Real Time API gebruikt Microsoft SignalR websockets (`@microsoft/signalr` via JS/Python equivalenten).

We openen 2 Hubs parallel via `https://rtc.thefuturesdesk.projectx.com/hubs/...`:
1.  **User Hub (`/hubs/user`):** Ontvangt account specifieke events via PUSH. Dit elimineert de noodzaak om `searchOpen` frequent te callen.
    *   Abonnement: `Invoke('SubscribeOrders', accountId)` en `Invoke('SubscribePositions', accountId)`
    *   Relevantste events: `GatewayUserOrder`, `GatewayUserPosition`, `GatewayUserAccount`.
2.  **Market Hub (`/hubs/market`):** Voor de live candle en orderflow streams per symbol.
    *   Abonnement: `Invoke('SubscribeContractTrades', contractId)`
    *   Relevantste events: `GatewayTrade` (elke tick), `GatewayQuote` (BBO).

---

## 5. Known Error Codes (Observed Behavior)

Bij incorrect formatteren van de payload reageert de Gateway met een code.

| Error Code | API Beschrijving | Objectieve Oorzaak |
|:---:|:---|:---|
| **2** | `Invalid stop price. Price is not aligned to tick size.` | De berekende prijs is niet exact op het minimale tick interval afgetopt (bijv `0.25` voor ES/NQ). |
| **2** | `Not enough margin.` | Gevraagde `size` overstijgt het Account Max contract limiet of de koopkracht (Buying Power). |
| **2** | `Instrument is not in an active trading status.` | Poging tot orderinleg buiten handelstijden, of het gekozen `contractId` is verlopen. |
| **401** | `Unauthorized` | De JWT token mist in de header of is tijdsverlopen. |

# Tasks — PRD §10 (comandos) y §11 (script demo)

**Relacionado:** `PRD-WhatsApp-Debt-Budget-Yield-Savings.md` (v0.2) · código: `app/bot.py`  
**Objetivo:** Sustituir el echo demo por un **router de comandos + máquina de estados ligera** en memoria (clave = teléfono) que permita ejecutar el **script de demo §11** sin errores.

---

## Mapa rápido PRD → trabajo

| PRD | Qué construir |
|-----|----------------|
| **§10** | Contrato de comandos: `start`, `goal`, `budget`, `envelope`, `reminder`, `help principal`, opcional `menu` |
| **§11** | Flujo conversacional de 13 pasos: mismas preguntas/respuestas y orden para el pitch |

---

## Tareas (checklist)

### A. Fundamentos (estado y entrada)

- [ ] **A1.** Crear un diccionario global **en memoria**, por ejemplo `_sessions: dict[str, UserSession]` donde la clave es `msg.phone_number` (mismo string que usa Kapso al enviar).
- [ ] **A2.** Definir un `@dataclass` (o `TypedDict`) `UserSession` con campos mínimos: `step` (enum o string), `debt_label`, `payment_amount`, `due_date`, `income`, `essentials`, `flexible`, flags opcionales (`envelope_created`, etc.).
- [ ] **A3.** Función `get_session(phone: str) -> UserSession` que devuelva sesión nueva si no existe.
- [ ] **A4.** Normalizar texto entrante: `strip()`, comparación de comandos en **minúsculas** (`text.lower()`), y detección de frases para shortfall (p. ej. `can't cover principal`, `help principal`).

### B. Router de comandos (§10)

- [ ] **B1.** Si el mensaje coincide con un **comando explícito** (`start`, `menu`, `goal`, `budget`, `envelope`, `reminder`, `help principal`), ejecutar su manejador **antes** del modo guiado por pasos (o definir regla clara: comandos siempre ganan vs. solo cuando `step == IDLE`).
- [ ] **B2.** `start`: reiniciar o inicializar sesión; primera respuesta del PRD: *“I can help you plan a debt payment. What debt are we planning for?”*; `step` → esperar nombre de deuda.
- [ ] **B3.** `goal` (modo comando): si quieres permitir entrada compacta en una línea, parsear opcionalmente; si no, redirigir al flujo guiado igual que tras `start`.
- [ ] **B4.** `budget`: capturar ingreso + essentials + flexible (guiado o parseo de una línea tipo demo §11).
- [ ] **B5.** `envelope`: mostrar **sobre simulado** + **yield estimado simulado** (etiquetado “simulated / illustrative”, sin garantías).
- [ ] **B6.** `reminder`: mensaje estilo D-1 usando datos de sesión (monto, etiqueta de deuda); sin cron.
- [ ] **B7.** `help principal` / frase natural: respuesta shortfall PRD §8 (gap + 3 opciones + disclaimers).
- [ ] **B8.** `menu`: listar comandos en un solo mensaje corto.

### C. Máquina de estados para el script §11 (demo guiada)

- [ ] **C1.** Tras `start`, si el usuario escribe texto libre (ej. `Credit card`), guardar `debt_label` y preguntar **monto y fecha** en un solo mensaje o dos (según límites de WhatsApp).
- [ ] **C2.** Parsear respuesta tipo `$450 due May 15` (regex simple: `$` + número + resto de fecha como string legible).
- [ ] **C3.** Preguntar ingreso y dos buckets: mensaje fijo del estilo *“What’s your monthly income? Then essentials and flexible spending (numbers only).”* o dos turnos.
- [ ] **C4.** Calcular `available = income - essentials - flexible`; comparar con `payment_amount`; mensaje de **factibilidad** para el caso feliz ($700 vs $450).
- [ ] **C5.** Confirmar creación del **simulated payment envelope** (solo copy).
- [ ] **C6.** Asegurar que `reminder` y shortfall funcionen **aunque** el usuario haya saltado pasos con comandos (validar: si faltan datos, pedir `start` o el dato faltante).

### D. Calidad y demo

- [ ] **D1.** Mensajes **cortos**; si un mensaje es largo, dividir en 2 envíos o usar saltos de línea claros.
- [ ] **D2.** Cualquier texto no reconocido: empujar hacia `start` / `menu` sin lanzar excepción (try/except solo donde haya parsing).
- [ ] **D2b.** (Opcional PRD §7) Modo “shortfall demo”: comando tipo `demo shortfall` que fije `available_for_payment = 330` para forzar el guion del gap $120 sin romper el happy path.
- [ ] **D3.** Pruebas unitarias (2–3): función pura para `available`, parseo de monto `$450`, y generación del cuerpo del mensaje shortfall dado goal/available.
- [ ] **D4.** Ensayo con **Uvicorn + ngrok + Kapso** siguiendo el guion §11; imprimir **cheat sheet** de una página para quien presenta.

---

## Instrucciones: cómo crear el código (paso a paso)

### 1. Dónde tocar el repo

- Archivo principal: **`app/bot.py`** — sustituir el cuerpo de `handle_inbound` para que llame a tu router en lugar de `_reply_body_for_demo` directo.
- Opcional (recomendado si `bot.py` crece): nuevo módulo **`app/coach/`** o **`app/debt_coach.py`** con `UserSession`, handlers y textos; `bot.py` solo orquesta y llama `build_reply(phone, text) -> str`.

**No** añadas base de datos ni cron en esta iteración (PRD §5).

### 2. Patrón de diseño recomendado

1. **`parse_command(text: str) -> str | None`**  
   - Devuelve el nombre normalizado del comando si la línea es solo el comando (o empieza por él).  
   - Ejemplos: `"start"`, `"help principal"` (acepta también `help_principal` si quieres).

2. **`route_command(phone, cmd, session) -> str`**  
   - Switch / dict de callables que devuelven el **siguiente mensaje** al usuario y actualizan `session`.

3. **`route_conversation(phone, text, session) -> str`**  
   - Si `session.step` indica que estamos esperando “deuda”, “monto_fecha”, “presupuesto”, etc., interpretar `text` como respuesta libre, actualizar campos y devolver la siguiente pregunta o resumen.

4. **`handle_inbound`**  
   ```text
   text = inbound_text(msg)
   if not text: → mensaje corto pidiendo texto o ignorar con log
   session = get_session(msg.phone_number)
   cmd = parse_command(text)
   if cmd: reply = route_command(...)
   else: reply = route_conversation(...)
   await client.send_whatsapp_message(msg.phone_number, reply)
   ```

### 3. Datos mínimos en `UserSession`

Campos sugeridos (todos opcionales hasta que se rellenen):

- `step`: por ejemplo `WAITING_DEBT_NAME | WAITING_AMOUNT_DUE | WAITING_BUDGET | DONE_ONBOARDING`
- `debt_label: str | None`
- `payment_amount: Decimal | float | None`
- `due_date: str | None` (string legible basta para el demo)
- `income`, `essentials`, `flexible`: números o `None`
- Propiedad calculada `available() -> float | None` si los tres presupuesto están presentes

### 4. Textos legales / tono (PRD §2 y §8)

En **envelope** y **shortfall**, incluir siempre variante de:

- *“Here are general options to consider”*  
- *“Check your lender terms before changing payments.”*  
- *“This isn’t financial advice.”* / *“Illustrative / simulated yield only.”*

### 5. Implementación por comando (referencia rápida)

| Comando | Lógica mínima |
|---------|----------------|
| `start` | Reset session (o nueva), `step = WAITING_DEBT_NAME`, mensaje bienvenida §11 paso 2. |
| `menu` | Lista numerada de comandos. |
| `goal` | O bien inicia sub-flujo solo de meta, o muestra “Say start to begin”. |
| `budget` | Pide tres números o parsea una línea; luego calcula available vs goal. |
| `envelope` | Si falta `payment_amount`, pedir goal primero. Si no, mensaje con “envelope balance = goal (simulated)” + yield ficticio (ej. 0.1% del mes). |
| `reminder` | Si falta deuda/monto, error amable. Si no, plantilla D-1 con nombre y monto. |
| `help principal` | Necesita `payment_amount` y un “available for payment” — puede ser `available` de presupuesto o un override para demo shortfall. |

### 6. Parsing pragmático (sin librerías pesadas)

- Montos: `re.search(r"\$?\s*([\d,]+(?:\.\d+)?)", text)` y quitar comas.  
- Fecha: para el MVP, guardar el substring después del monto como `due_date` sin parsear a `datetime` (suficiente para copy).  
- Línea tipo demo: `income 3000 essentials 1800 flexible 500` — regex con nombres o split por palabras clave.

### 7. Pruebas (`tests/`)

- Archivo nuevo ej. **`tests/test_debt_coach.py`**:  
  - `test_available_income_minus_buckets`  
  - `test_parse_payment_line`  
  - `test_shortfall_message_contains_disclaimers`  

Importa funciones puras desde el módulo que elijas (si la lógica vive en `debt_coach.py`, testéala ahí).

### 8. Verificación manual antes del pitch

1. `start` → flujo completo §11 con los números del PRD §7.  
2. `reminder` suelto tras completar datos → mensaje correcto.  
3. `help principal` → tres bullets + frases obligatorias.  
4. Mensaje basura → no crash; sugiere `menu`.

---

## Script demo §11 (imprimir para quien presenta)

1. `start`  
2. Bot pregunta deuda  
3. `Credit card`  
4. Bot pide monto y fecha  
5. `$450 due May 15`  
6. Bot pide ingreso y presupuesto simple  
7. `Income 3000, essentials 1800, flexible 500`  
8. Bot: factibilidad + resumen  
9. Bot: sobre simulado creado (o usuario `envelope`)  
10. `reminder`  
11. Bot: mensaje D-1 simulado  
12. `I can't cover principal` (o variante con $330 disponible si implementáis D2b)  
13. Bot: gap + 3 opciones + disclaimers  

---

## Definición de “hecho”

- [ ] Un compañero puede seguir §11 en WhatsApp sin mirar el código.  
- [ ] §10: todos los comandos tienen comportamiento definido (aunque sea “complete setup first”).  
- [ ] Sin dependencias nuevas obligatorias; sin DB; sin cron.  
- [ ] Tests mínimos en verde en CI local (`pytest`).

---

*Creada para ejecutar PRD §10–§11. Actualizar esta nota si el contrato de comandos cambia.*
# Tasks — PRD §10 (commands) & §11 (demo script)

**Related:** [PRD v0.2](PRD-WhatsApp-Debt-Budget-Yield-Savings.md) · Code: `app/debt_coach.py`, `app/bot.py`  
**Goal:** Ship a **command router + light state machine** in memory (key = phone) so the **§11 demo script** runs reliably in WhatsApp.

*Spanish version / Obsidian mirror: `Hackathon CO 2026/Tasks-PRD-secciones-10-y-11-Bot-coach.md` — keep in sync when editing.*

---

## Quick map: PRD → work

| PRD | What to build |
|-----|-----------------|
| **§10** | Commands: `start`, `goal`, `budget`, `envelope`, `reminder`, `help principal`, optional `menu`, `demo shortfall` |
| **§11** | 13-step conversational demo: same prompts/order for the pitch |

---

## Task checklist

### A. Foundations (state & input)

- [x] **A1.** In-memory dict, e.g. `_sessions: dict[str, UserSession]` keyed by `msg.phone_number`.  
- [x] **A2.** `UserSession` dataclass: `step`, `debt_label`, `payment_amount`, `due_date`, `income`, `essentials`, `flexible`, optional `available_for_payment_override`.  
- [x] **A3.** `get_session(phone: str) -> UserSession`.  
- [ ] **A4.** Normalize inbound text; detect natural phrases for shortfall (e.g. *I can't cover principal*) in addition to `help principal`.

### B. Command router (§10)

- [x] **B1.** Explicit commands run through `parse_command` / `_route_command` before free-text conversation steps.  
- [x] **B2.** `start`: reset session; first line matches PRD §11.  
- [x] **B3.** `goal`: jump to amount/due prompt when debt label exists.  
- [x] **B4.** `budget`: prompt or validate income + two buckets (+ implied remainder).  
- [x] **B5.** `envelope`: simulated envelope + illustrative yield copy.  
- [x] **B6.** `reminder`: simulated D-1 message from session fields.  
- [x] **B7.** `help principal`: shortfall copy PRD §8 (gap + 3 options + disclaimers).  
- [x] **B8.** `menu`: list commands.  
- [x] **B9.** `demo shortfall`: optional override for pitch ($330 vs $450).

### C. State machine for §11 (guided demo)

- [x] **C1.** After `start`, free text → `debt_label`, then amount/due question.  
- [x] **C2.** Parse `$450 due May 15` style line.  
- [x] **C3.** Ask for income + essentials + flexible (one message).  
- [x] **C4.** Compute `available`, compare to goal, feasibility message.  
- [x] **C5.** Confirm simulated payment envelope in copy after budget step.  
- [x] **C6.** `reminder` / shortfall guard when data missing (“complete setup first”).

### D. Quality & demo

- [ ] **D1.** Keep WhatsApp messages short; split into two sends if needed.  
- [x] **D2.** Unknown / garbage text: no crash; nudge to `start` / `menu` (IDLE path).  
- [x] **D2b.** `demo shortfall` for $120 gap script.  
- [x] **D3.** Unit tests: parsing, happy path, shortfall — `tests/test_debt_coach.py`.  
- [ ] **D4.** Rehearse Uvicorn + ngrok + Kapso on §11; one-page cheat sheet for presenter.

---

## How to implement (for contributors)

### 1. Where to edit

- **`app/debt_coach.py`** — sessions, `parse_command`, `build_reply`, command + conversation routing.  
- **`app/bot.py`** — thin: `build_reply(msg.phone_number, inbound_text(msg))`.  

No DB or cron for this MVP (PRD §5).

### 2. Suggested pattern (already largely in place)

1. `parse_command(text) -> str | None`  
2. `_route_command(cmd, session) -> str`  
3. `_route_conversation(text, session) -> str`  
4. `build_reply(phone, text)` → `get_session` → command vs conversation branch.

### 3. Legal / tone (PRD §2, §8)

For **envelope** and **shortfall**, keep variants of:

- *“Here are general options to consider”*  
- *“Check your lender terms before changing payments.”*  
- *“This isn’t financial advice.”* / simulated yield disclaimers.

### 4. Command reference

| Command | Minimum behavior |
|---------|-------------------|
| `start` | Reset; `WAITING_DEBT_NAME`; welcome §11 step 2. |
| `menu` | List commands. |
| `goal` | If no debt label → ask; else prompt for `$… due …`. |
| `budget` | Prompt line or parse; then `available` vs goal. |
| `envelope` | Needs goal amount; simulated balance + yield line. |
| `reminder` | Needs amount + due date; D-1 copy. |
| `help principal` | Needs goal + available (or override). |

### 5. Pragmatic parsing

- Money: `re.search(r"\$?\s*([\d,]+(?:\.\d+)?)", text)`  
- Due date: keep rest of string as display text (no `datetime` required for demo).  
- Budget line: `Income … essentials … flexible …` (see `parse_budget_triple`).

### 6. Tests

- **`tests/test_debt_coach.py`** — extend with edge cases and natural-language triggers when A4 ships.

### 7. Manual QA before pitch

1. `start` → full §11 with PRD §7 numbers.  
2. `reminder` after setup → correct copy.  
3. `demo shortfall` → `help principal` → three bullets + required phrases.  
4. Random text at `IDLE` → suggests `start` / `menu`.

---

## §11 demo script (print for presenter)

1. `start`  
2. Bot asks debt  
3. `Credit card`  
4. Bot asks amount + due  
5. `$450 due May 15`  
6. Bot asks income + simple budget  
7. `Income 3000, essentials 1800, flexible 500`  
8. Bot: feasibility + summary  
9. Bot: envelope created in copy (or user types `envelope`)  
10. `reminder`  
11. Bot: simulated D-1  
12. `demo shortfall` then `help principal` (or natural phrase once A4 exists)  
13. Bot: gap + 3 options + disclaimers  

---

## Definition of done

- [ ] A teammate can run §11 on WhatsApp without reading code.  
- [x] §10: every command has defined behavior (including “complete setup first”).  
- [x] No new hard deps; no DB; no cron.  
- [x] `pytest` green locally (`tests/test_debt_coach.py`, `tests/test_app.py`).

---

*Update this file when the command contract changes.*

# MCZ Maestro local protocol notes

Websocket `ws://192.168.120.1:81` on the stove's own access point (`MCZ-01…`).
Frames are plain text, fields separated by `|`, values in hexadecimal.
These notes describe the stove's local interface as far as needed for
interoperability with Home Assistant. They were determined from the stove's
behaviour, publicly available community projects and the communication of the
official app with the stove. No code or other material of the manufacturer is
included. Values may differ between stove models and firmware versions.

## Reply frame types

| Type | Content | Request |
|---|---|---|
| `00` | Parameters / equipment | `C\|RecuperoParametri` |
| `01` | Information (state, temperatures, modes) | `C\|RecuperoInfo` — also the answer to every write |
| `02` | Database block | `C\|RecuperoBancaDati\|<n>` |
| `03` | Extra parameters (recipes, eco stop) | `C\|RecuperoParametriExtra\|11` |
| `04` | Chronothermostat week | `C\|RecuperoGiornoChrono` |
| `0A` | Alarms | `C\|RecuperaAllarmi` |
| `0B` | WiFi probes | `C\|RecuperoSondeWiFi` |
| `0D` | Database names | `C\|RecuperoElencoBancheDati` |
| `0E` | Software versions (contains AP credentials) | `C\|RecuperoVersioneSW` |

Unknown commands get an empty reply. Commands are prefix matched by the mainboard.

## Parameter frame and fans

`C|RecuperoParametri` → `00|<hex payload>`, one byte per value (payload without
the frame type):

| Byte | Meaning |
|---|---|
| 2 / 3 | Setpoint minimum / maximum (°C) |
| 6 / 7 | Power level minimum / maximum |
| 8–13 | Front fan: fitted, enabled, min level, max level, automatic allowed, off allowed |
| 14–19 | Ducted fan 1: same layout |
| 20–25 | Ducted fan 2: same layout |

Fan level: `C|WriteParametri|37|<level>` (front), `38` (ducted 1), `39` (ducted 2).
Level `0` = off ("no air"), `min..max` = manual, `max + 1` (usually `6`) = automatic.
Current levels are fields 2, 3 and 4 of the `01` frame. The official app does not
switch off the last running fan and hides fan control while silent mode
(parameter 45) is on.

## Chronothermostat

Read `C|RecuperoGiornoChrono`:

```
04|<sun>|<mon>|<tue>|<wed>|<thu>|<fri>|<sat>|<T1>|<T2>|<T3>
```

- Day 0 is **Sunday**.
- Each day: 24 hex chars = 12 bytes = 48 slots of 30 minutes, 2 bits per slot, MSB first.
- Slot value: `00` off, `01` T1, `10` T2, `11` T3.
- T1..T3: temperature in °C (hex).

Write one day: `C|ScriviGiornoChrono|<day 0-6>|<24 hex chars>` (answer: `01` frame).

Temperatures: `C|WriteParametri|1108|<°C>` (T1), `1109` (T2), `1110` (T3).
The app enforces 5–35 °C and T1 < T2 < T3.

Chrono on/off: `C|WriteParametri|1111|<0|1>`, state in field 25 of the `01` frame.

Example (Wednesday 18:00–19:30 on T1): `000000000000000000540000`
(byte 9 = `0x54` = `01 01 01 00` → slots 36, 37, 38).

## Other commands found in the app (not implemented yet)

| Command | Purpose |
|---|---|
| `C\|WriteBancaDati\|<cell>\|<bytes>\|<hex>` | Write database cell (148 eco-stop delay, 294 eco-stop hysteresis, 356 room input, 365, 459/460 recipes) |
| `C\|WriteParametri\|57\|<value>` | Sleep timer |
| `C\|WriteParametri\|154\|<id>` | Antifreeze |
| `C\|WriteParametri\|149\|<value>` | Profile / adaptive |
| `C\|RecuperoOreFunzionamento\|8` | Operating hours |
| `C\|SalvaDataOra\|ddmmyyyyHHMM` | Set stove clock (implemented, answer `AA\|<value>`) |

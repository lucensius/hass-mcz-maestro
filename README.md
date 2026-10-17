# MCZ Maestro Local – Home Assistant integration

[![Validate](https://github.com/lucensius/hass-mcz-maestro/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/lucensius/hass-mcz-maestro/actions/workflows/hassfest.yaml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-blue.svg)](LICENSE)

Control MCZ pellet stoves with **Maestro** electronics **locally** over the
stove's own WiFi – no cloud account needed. Built for running the stove in
**chrono mode**: the weekly program as a Home Assistant calendar, a start
button with a heating duration, a smart mode driven by any thermometer, a
chrono watchdog and automatic clock sync.

> **Core idea:** the stove always stays in chrono mode. Everything this
> integration does – including "heat now" – is done by editing the stove's
> chrono table.

This is an independent, unofficial project, not affiliated with MCZ Group S.p.A.
Please read the [safety notice](#safety-notice) before use.

---

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Entities](#entities)
- [Usage](#usage)
  - [Start / stop the stove](#start--stop-the-stove)
  - [Smart mode with an external thermometer](#smart-mode-with-an-external-thermometer)
  - [Weekly program in the calendar](#weekly-program-in-the-calendar)
  - [Day overview](#day-overview)
  - [Chrono watchdog](#chrono-watchdog)
  - [Stove clock](#stove-clock)
  - [Fans](#fans)
  - [Climate entity](#climate-entity)
- [Actions](#actions)
- [Examples](#examples)
- [How it works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)
- [Development](#development)
- [Safety notice](#safety-notice)
- [Legal](#legal)

---

## Features

| Feature | Description |
|---|---|
| **Start / stop** | One button writes heating time into the chrono table from now for the chosen duration (hour slider); another removes it again. |
| **Smart mode** | Heats via the chrono until an **external thermometer** reaches a target temperature. Can be switched on and off; with hysteresis and minimum runtime. |
| **Calendar** | The weekly program as a Home Assistant calendar: see all heating times in week/day/list view, create and delete entries right in the calendar. |
| **One-off entries** | Calendar entries without repetition heat exactly once – the weekly program stays as it is. Single occurrences of the weekly program can be skipped once. |
| **Day overview** | One sensor per weekday, e.g. `08:00–09:00, 15:00–16:00 (T1)`. |
| **Chrono watchdog** | If chrono mode is turned off at the stove or in the app, the integration turns it back on. |
| **Clock sync** | The stove clock (which the chrono runs on) is set automatically when it drifts by more than 2 minutes. |
| **Fans** | Front and ducted fans as fan entities: automatic mode (default), manual levels 1–5, off where the stove allows it. Only fitted fans are created. |
| **T1 / T2 / T3** | Read and set the three chrono temperatures (5–35 °C, T1 < T2 < T3). |
| **Actions** | `start_heating`, `stop_heating`, `set_chrono_day`, `copy_chrono_day` for automations and scripts. |
| **Robust connection** | Reconnects automatically; retries setup while the stove is unreachable. |
| **Translations** | English, German, French. |

---

## Requirements

- An MCZ stove with Maestro electronics and the WiFi module (access point
  named `MCZ-01…`). Stoves with **Maestro+** (Bluetooth/cloud) use a different
  protocol and are not supported.
- Home Assistant **2024.12** or newer.
- The machine running Home Assistant must reach the stove directly: it has to be
  connected to the **stove's WiFi access point** (stove address `192.168.120.1`,
  port `81`). A second WiFi adapter or a small WiFi bridge works well for this.

---

## Installation

### HACS (recommended)

1. Open **HACS** in Home Assistant.
2. Menu (⋮) → **Custom repositories**.
3. Repository: `https://github.com/lucensius/hass-mcz-maestro`, type
   **Integration** → **Add**.
4. Search for **MCZ Maestro Local** and click **Download**.
5. **Restart Home Assistant.**

Updates then show up in HACS like for any other integration.

### Manual

1. Download the [latest release](https://github.com/lucensius/hass-mcz-maestro/releases)
   or the repository as ZIP.
2. Copy the folder `custom_components/mczmaestro` into
   `<config>/custom_components/` of your Home Assistant installation.
3. Restart Home Assistant.

> This integration uses the domain `mczmaestro`, like the original integration
> by Aohzan. Remove the original before installing this one.

---

## Configuration

1. **Settings → Devices & services → Add integration → MCZ Maestro Local**
2. Enter host `192.168.120.1`, port `81` and the polling interval (default 30 s).
3. For the smart mode: open the integration, click **Configure** and choose the
   **external thermometer** (any sensor with device class temperature).

The device is created as **MCZ Maestro**. Rename it to whatever you like
(e.g. "Living room stove") – all entity names follow the device name.

All other settings (heating duration, heating level, smart target …) are
entities and are stored in Home Assistant, so they survive restarts.

---

## Entities

Entity names below are the English ones; Home Assistant shows them in your
language and prefixes them with the device name.

### Controls

| Entity | Type | Purpose |
|---|---|---|
| *device name* | Climate | Room temperature and status; modes see [Climate entity](#climate-entity) |
| Start stove | Button | Heat from now for the heating duration |
| Stop stove | Button | End the heating period started with *Start stove* |
| Heating duration | Number (slider, 0.5–12 h) | Duration for *Start stove* |
| Heating level | Select (T1/T2/T3) | Chrono temperature used by start and smart mode; attributes show the °C values |
| Heating until | Sensor (timestamp) | End of the running heating period, empty if none |
| Smart mode | Switch | Smart mode on/off |
| Smart target temperature | Number (5–30 °C) | Target at the external thermometer |
| Smart status | Sensor | `Off`, `No thermometer`, `Waiting`, `Heating` |
| Chrono | Calendar | Weekly program and temporary entries |
| Chrono Monday … Sunday | Sensor | Heating times of the day; attribute `schedule` as a list |
| Chrono mode | Switch | Chrono mode; while on, the chrono watchdog keeps it on |
| Fan / Ducted fan 1 / Ducted fan 2 | Fan | Fan level: preset *Automatic* or manual speed; only fans the stove is fitted with |

### Configuration and diagnostics

| Entity | Purpose |
|---|---|
| Temperature T1 / T2 / T3 | Chrono temperatures (5–35 °C, T1 < T2 < T3) |
| Smart hysteresis | How far below the target the temperature must drop before smart mode starts (default 0.5 °C) |
| Smart minimum runtime | Minimum runtime after a smart start (default 60 min) |
| Sync clock | Set the stove clock to Home Assistant's time now |
| State | Stove state in plain text, all raw values as attributes |
| Room temperature | Temperature at the stove's own sensor |
| Eco / Silent / Active / Automatic mode | Further stove modes |

---

## Usage

### Start / stop the stove

1. Set the **Heating duration**, e.g. 2 h.
2. Optionally choose the **Heating level** (T1, T2 or T3).
3. Press **Start stove**.

The integration writes the heating level into the chrono table from the
current 30-minute slot until the end of the duration (rounded up to the next
half hour). The stove starts through its chrono. **Heating until** shows the end.

- Pressing again restarts the duration from now.
- **Stop stove** removes the entries again; times of the weekly program stay.
- When the heating period is over, its entries are removed automatically –
  otherwise the stove would start again at the same time a week later.
- If the weekly program has a higher level at the same time, that level is kept.

### Smart mode with an external thermometer

Smart mode heats until a thermometer of your choice (e.g. in the living room)
reaches the target temperature:

| Situation | Reaction |
|---|---|
| Temperature ≤ target − hysteresis | Start: the current slot and the next 60 minutes are written into the chrono |
| Heating and temperature < target | The entry is extended continuously (always about 30–60 min ahead) |
| Temperature ≥ target and minimum runtime reached | The smart entries are removed; the stove stops through its chrono |
| Thermometer unavailable | No change until values come back |
| Smart mode switched off | Running smart entries are removed |

- Smart mode heats with the selected **Heating level**. Tip: set that level
  (e.g. T3) a bit above the target temperature, otherwise the stove throttles
  down early based on its own sensor.
- Smart mode **adds** to the weekly program: programmed times keep running even
  if the target has been reached.
- It is evaluated on every thermometer change and every poll of the stove.

### Weekly program in the calendar

The calendar entity **Chrono** shows the program in Home Assistant's calendar
(sidebar → Calendar) and in calendar cards:

| Calendar entry | Meaning |
|---|---|
| `Heat T1 (16 °C)` – repeats weekly | Part of the weekly program |
| `Heat T3 (18 °C) – Start` | Heating period from the start button |
| `Heat T3 (18 °C) – Smart` | Written by smart mode |
| `Heat T2 (17 °C) – One-off` | One-off entry |

**Creating entries** (Calendar → *Add event*):

- The **title** selects the level: put `T1`, `T2` or `T3` in it (e.g. "Heat T2").
  Without it, the selected heating level is used.
- **Repeat weekly** (any weekdays) or **daily**: becomes part of the weekly program.
- **No repetition**: heats exactly once on that date (only within the next
  7 days); the entry is removed afterwards.
- Times are rounded to half hours (start down, end up). All-day events and
  events spanning several days are not possible.

**Deleting entries:**

- Weekly entry → *All events*: removes the time from the weekly program.
- Weekly entry → *Only this event*: skips this time **once**; the program stays.
- One-off, start or smart entries: are removed.

### Day overview

One sensor per weekday shows all heating times of that day as they are
currently stored in the stove:

| Value | Meaning |
|---|---|
| `08:00–09:00, 15:00–16:00 (T1)` | two periods, both T1 |
| `06:00–08:00 T2, 18:00–22:00 T3` | different levels |
| `off` | no heating time on that day |

The attribute `schedule` contains the periods as a list, `temperatures` the
values of T1–T3.

### Chrono watchdog

While **Chrono mode** is on in Home Assistant, the integration checks on every
poll that the stove is still in chrono mode. If it was left (control panel,
app, power cut), it is switched on again (at most every 2 minutes, logged).

Turning **Chrono mode** off in Home Assistant on purpose also turns the
watchdog off. No other function of this integration switches the chrono off.

### Stove clock

The chrono runs on the stove's internal clock. If it differs by more than
2 minutes from Home Assistant's time, it is set automatically (at most once per
hour). The **Sync clock** button sets it immediately.

### Fans

The integration reads which fans the stove is fitted with (front fan, ducted
fan 1 and 2) and creates a fan entity for each of them.

| Action in Home Assistant | Effect on the stove |
|---|---|
| Turn on | **Automatic** mode – the stove chooses the speed (default) |
| Preset *Automatic* | Automatic mode |
| Speed 20 / 40 / 60 / 80 / 100 % | Manual level 1 / 2 / 3 / 4 / 5 |
| Turn off | "No air" – only offered if the stove allows it and another fan keeps running |

- The attribute `level` shows the raw value: `0` off, `1`–`5` manual, `6` automatic.
- While **silent mode** is on, the stove controls the fans itself; changing
  them is refused until silent mode is switched off.
- Like the official app, the integration never switches off the last running
  fan. With only a front fan, "off" is therefore not available.

### Climate entity

| Mode | Effect |
|---|---|
| **Heat** | Same as *Start stove* (duration and level from the entities) |
| **Auto** | Ends a running heating period; the weekly program runs (chrono on) |
| **Off** | Ends heating period and smart mode and switches the stove off; the chrono stays on and starts the stove at the next programmed time |

The entity shows *Heat* while a heating period runs, otherwise *Auto* when the
chrono is active.

---

## Actions

### `mczmaestro.start_heating`

Heat from now via the chrono.

| Field | Required | Description |
|---|---|---|
| `hours` | no | Duration in hours (0.5–24); default: *Heating duration* entity |
| `temperature` | no | `T1`, `T2` or `T3`; default: *Heating level* entity |

### `mczmaestro.stop_heating`

End the heating period started with the start button or `start_heating`.

### `mczmaestro.set_chrono_day`

Set the weekly program of one or more days. Times not listed are off; an empty
`schedule` switches the whole day off.

| Field | Required | Description |
|---|---|---|
| `day` | yes | `monday` … `sunday`, `weekdays` (Mon–Fri), `weekend` (Sat–Sun), `all`; also as a list |
| `schedule` | no | List of `start`, `end` (HH:MM, half hours) and `temperature` (T1–T3) |

### `mczmaestro.copy_chrono_day`

Copy the program of one day to other days.

| Field | Required | Description |
|---|---|---|
| `source` | yes | Day to copy from |
| `target` | yes | Days to copy to (like `day` above) |

All actions accept an optional `config_entry_id`, only needed with several stoves.

---

## Examples

### Set the weekly program

```yaml
action: mczmaestro.set_chrono_day
data:
  day: weekdays
  schedule:
    - {start: "06:00", end: "08:30", temperature: T2}
    - {start: "17:00", end: "22:00", temperature: T3}
```

```yaml
action: mczmaestro.copy_chrono_day
data:
  source: saturday
  target: sunday
```

### Automation: heat for three hours when someone comes home

```yaml
alias: Stove on arrival
triggers:
  - trigger: zone
    entity_id: person.example
    zone: zone.home
    event: enter
conditions:
  - condition: numeric_state
    entity_id: sensor.living_room_temperature
    below: 19
actions:
  - action: mczmaestro.start_heating
    data:
      hours: 3
      temperature: T3
```

### Automation: smart mode in the evening only

```yaml
alias: Smart mode evenings
triggers:
  - trigger: time
    at: "17:00:00"
    id: "on"
  - trigger: time
    at: "22:00:00"
    id: "off"
actions:
  - action: "switch.turn_{{ trigger.id }}"
    target:
      entity_id: switch.mcz_maestro_smart_mode
```

### Dashboard

Replace `mcz_maestro` with the prefix of your entity IDs
(*Settings → Devices & services → MCZ Maestro Local → Entities*).

```yaml
type: vertical-stack
cards:
  - type: thermostat
    entity: climate.mcz_maestro
  - type: entities
    title: Stove
    entities:
      - number.mcz_maestro_heating_duration
      - select.mcz_maestro_heating_level
      - button.mcz_maestro_start_stove
      - button.mcz_maestro_stop_stove
      - sensor.mcz_maestro_heating_until
  - type: entities
    title: Smart mode
    entities:
      - switch.mcz_maestro_smart_mode
      - number.mcz_maestro_smart_target_temperature
      - sensor.mcz_maestro_smart_status
  - type: calendar
    initial_view: listWeek
    entities:
      - calendar.mcz_maestro_chrono
  - type: markdown
    title: Weekly program
    content: >
      {% for d in ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'] %}
      **{{ d | capitalize }}:** {{ states('sensor.mcz_maestro_chrono_' ~ d) }}
      {% endfor %}
```

---

## How it works

**Chrono table.** The stove stores 48 slots of 30 minutes per weekday, each set
to *off*, *T1*, *T2* or *T3*. The whole week is read with
`C|RecuperoGiornoChrono`, one day is written with `C|ScriviGiornoChrono`.
Details: [docs/PROTOCOL.md](docs/PROTOCOL.md).

**Weekly program and temporary entries.** The stove only knows one weekly
table, so the start button, smart mode and one-off calendar entries write into
the same table. For every slot changed that way the integration remembers the
**actual date**, the **original value** and **who** changed it (start, smart,
one-off, skip). This allows it to

- remove entries selectively (stop, target reached, calendar delete),
- restore expired entries automatically so they do not repeat a week later,
- show the weekly program and one-off entries separately in the calendar,
- apply changes to the weekly program without losing running heating periods.

This is stored in `.storage/mczmaestro.<entry_id>` and survives restarts.
Before every write the table is read fresh from the stove and only days that
actually change are written.

**Connection.** Every reply of the stove is matched to its frame type (`01`
info, `04` chrono, `AA` clock …). Writes run in an executor thread and never
block Home Assistant. A lost connection is re-established with the next command.

---

## Troubleshooting

| Problem | What to check |
|---|---|
| Setup fails / entities unavailable | Is the Home Assistant host connected to the stove's WiFi? `ping 192.168.120.1` from that host. |
| Connection drops regularly | WiFi signal to the stove; the stove's access point allows only a few clients – close the MCZ app on phones connected directly. |
| Stove starts at the wrong time | Compare the stove clock (attributes of the *State* sensor: `Date_Time_Hours`, `Date_Time_Minutes`) with Home Assistant's time; press *Sync clock*. |
| Smart status shows *No thermometer* | Choose a thermometer under *Configure*; check that it reports a numeric value. |
| Debug log | Add `custom_components.mczmaestro: debug` under `logger:` in `configuration.yaml`. |

---

## Limitations

- **30-minute grid:** the chrono only knows half hours. Start and smart mode
  begin with the current slot, ends are rounded up.
- **One week ahead:** one-off entries are only possible for the next 7 days –
  the table repeats weekly.
- **Changes in the MCZ app:** if you change a slot in the app while a temporary
  entry occupies it, the integration restores the previous value once the
  temporary entry ends.
- **Stove memory:** every chrono change is stored in the stove. The integration
  writes only real changes (smart mode at most about every 30 minutes).
- **Regulation:** within a heating period the stove regulates by itself, based
  on its own sensor and the temperature T1/T2/T3.
- **Tested** with one stove model; values may differ on other models or firmware.

---

## Development

```bash
git clone https://github.com/lucensius/hass-mcz-maestro.git
cd hass-mcz-maestro
python3 -m pytest tests
```

| File | Content |
|---|---|
| `maestro/__init__.py` | Websocket controller, info frame |
| `maestro/chrono.py` | Chrono format: decode, encode, time ranges |
| `maestro/overlay.py` | Temporary entries on top of the weekly program (no HA dependency, unit tested) |
| `manager.py` | Start/stop, smart mode, chrono watchdog, clock, storage |
| `calendar.py` | Calendar entity |
| `services.py` | Actions |
| `fan.py`, `maestro/parameters.py` | Fans and the stove parameter frame |
| `docs/PROTOCOL.md` | Notes on the local protocol |

Issues and pull requests are welcome.

---

## Safety notice

A pellet stove is a combustion appliance. This software can switch it on
remotely and automatically.

- Follow the **operating manual and safety instructions of your stove** and
  all local regulations. In particular, only operate the stove remotely or by
  automation where the manufacturer and local rules allow it.
- Make sure the stove can be operated safely whenever it may start: clean
  burn pot, enough pellets, nothing flammable near the stove, free flue.
- Smoke and carbon monoxide detectors are strongly recommended.
- The integration relies on an unofficial, undocumented interface. Commands may
  behave differently than expected on your model or firmware. Check the
  behaviour of every function on your stove while you are present.
- Use at your own risk. The software is provided **without any warranty**; see
  sections 15 and 16 of the [GPL-3.0](LICENSE).

---

## Legal

- **License:** GNU General Public License v3.0 only – see [LICENSE](LICENSE).
  Copyright notices of included third-party code are listed in [NOTICE](NOTICE).
- **Based on** [Aohzan/hass-mcz-maestro](https://github.com/Aohzan/hass-mcz-maestro)
  (Apache-2.0, see [LICENSES/Apache-2.0.txt](LICENSES/Apache-2.0.txt)), which in
  turn builds on [Chibald/maestrogateway](https://github.com/Chibald/maestrogateway)
  (GPL-3.0). Protocol details were also cross-checked with
  [lexyan/mcz-maestro-esphome](https://github.com/lexyan/mcz-maestro-esphome).
  Changes are listed in the [CHANGELOG](CHANGELOG.md).
- **Trademarks:** "MCZ" and "Maestro" are trademarks of MCZ Group S.p.A. This
  project is independent and not affiliated with, endorsed or supported by
  MCZ Group S.p.A. The names are used only to describe compatibility.
- **Interoperability:** the protocol notes describe the stove's local interface
  solely to make this independently written software work with it. The project
  contains no code, firmware, images or other material of the manufacturer.

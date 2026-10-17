# Changelog

## 0.1.7

- fix error when adding new integration

## 0.1.6

- fix deviceinfo error
- fix deprecated code

## 0.1.5

- fix state from climate and sensor

## 0.1.4

- add debug
- fix state info error

## 0.1.3

- rename top dir

## 0.1.2

- add debug logs
- handle unknown values

## 0.1.1

- fix config flow dependency

## 0.1.0

- Initial release

## 0.2.0

- Chronothermostat weekly program: one sensor per day, services `mczmaestro.set_chrono_day` and `mczmaestro.copy_chrono_day`
- Chrono temperatures T1–T3 are read back from the stove, limits 5–35 °C, T1 < T2 < T3 enforced
- Writes no longer block the event loop and consume the stove's reply frame
- Automatic websocket reconnect after connection loss
- Protocol notes in `docs/PROTOCOL.md`

## 0.3.0

- Start/stop buttons with heating duration (slider) and heating level, service `start_heating` / `stop_heating`
- Smart mode: heats via the chrono until an external thermometer reaches the target (hysteresis, minimum runtime)
- Chrono calendar entity: weekly program and temporary entries, create/delete entries in the HA calendar
- Temporary chrono changes are tracked and restored automatically after they are over
- Chrono watchdog keeps the chrono mode on while "Mode Chrono" is on; climate "off" no longer disables the chrono
- Automatic stove clock sync (drift > 2 min) and "Uhrzeit synchronisieren" button
- Options flow to choose the external thermometer
- Day sensors show all times of a day, e.g. "08:00–09:00, 15:00–16:00 (T1)"
- German README

## 0.4.0

- Relicensed under GPL-3.0 (the code base contains GPL-3.0 code from maestrogateway); Apache-2.0 notices of the original integration kept, see NOTICE
- Entity names come from translations (English, German, French) and follow the device name chosen by the user; default device name "MCZ Maestro"
- English calendar entry titles
- Every chrono write is logged (day, before -> after)
- Manifest, HACS metadata and documentation point to this repository; English README with HACS installation, safety notice and legal information
- CI: hassfest, HACS validation and unit tests

## 0.5.0

- Fan entities for the front fan and ducted fans the stove is fitted with (read from the parameter frame): automatic mode (default), manual levels, off only where allowed and never for the last running fan; refused while silent mode is on
- Stove parameter frame parser with unit tests

## 0.6.0

- Smart strategy "Within chrono only" (new default): smart mode acts only during heating periods (weekly program, start button, one-off entries) and switches the rest of the period off once the target is reached; resumes when it gets cold again during the period
- Previous behaviour available as strategy "Additional heating"
- Smart status shows "Outside schedule" and "Target reached"

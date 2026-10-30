<p align="center">
  <img src="assets/logo.svg" alt="" width="72" />
</p>

<h1 align="center">SistemTemp</h1>

<p align="center">
  <b>English</b> · <a href="README.pt-BR.md">Português (Brasil)</a>
</p>

<p align="center">
  Temperature and telemetry monitor: follow temperature, humidity and pressure in real time, with alerts, a chart and a filterable history. All in a desktop app built with Python and Qt.
</p>

<p align="center">
  <img alt="Python 3.13+" src="https://img.shields.io/badge/Python-3.13%2B-3776ab?logo=python&logoColor=white" />
  <img alt="PyQt5" src="https://img.shields.io/badge/PyQt5-5.15-41cd52?logo=qt&logoColor=white" />
  <img alt="pyqtgraph" src="https://img.shields.io/badge/pyqtgraph-0.13-ef4444" />
  <img alt="NumPy" src="https://img.shields.io/badge/NumPy-2-013243?logo=numpy&logoColor=white" />
  <img alt="MVC" src="https://img.shields.io/badge/architecture-MVC-333333" />
</p>

<p align="center">
  <img src="assets/screenshot.png" alt="SistemTemp main screen: temperature, humidity, pressure and status cards, temperature chart and history table" />
</p>

> [!NOTE]
> **Readings are simulated.** The *Simular Leitura* (Simulate reading) button generates random values in place of a sensor. The history is saved to a SQLite database (`database/systemp.db`) and comes back when you open the app again. The interface is in Portuguese.

## Team

- **Samuel Schutz**
- **Gabriel Erharter**

## Features

- **Dark theme** across the whole window.
- **Real-time dashboard**: cards with the temperature, humidity and pressure of the latest reading.
- **Color-coded status**: green for stable weather, red for extreme heat, blue for intense cold and orange for very dry air.
- **Alerts**: a warning pops up when the temperature crosses the configured limits.
- **Temperature chart**: every reading becomes a point on the timeline.
- **History**: a table with date/time, temperature, humidity, pressure, dew point and condition.
- **Filters**: by temperature range (high > 30 °C, low < 15 °C) and by date.
- **Settings** (⚙): set the maximum and minimum temperature and the minimum humidity for alerts. The maximum must be greater than the minimum.
- **Saved history**: readings are stored in SQLite and reloaded when the app opens.
- **Logs**: events, alerts and errors go to `logs/systemp.log`.
- **Clear history** with confirmation, wiping the table, the chart and the database.

## Getting started

You need [Python](https://www.python.org) **3.13 or newer**.

```sh
git clone https://github.com/SamuelSchutz13/SistemTemp.git
cd SistemTemp

python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

python main.py
```

### Default alert limits

| Parameter           | Default | Alerts when               |
| ------------------- | ------- | ------------------------- |
| Maximum temperature | `35 °C` | the reading goes above it |
| Minimum temperature | `15 °C` | the reading drops below   |
| Minimum humidity    | `30 %`  | the reading drops below   |

You can change all of them in **⚙ Configurações** (Settings) while the app is open.

## Project structure

| File                                   | What it does                                                    |
| -------------------------------------- | --------------------------------------------------------------- |
| `main.py`                              | Entry point, applies the dark theme and opens the main window   |
| `models/telemetry_model.py`            | Alert limits, weather status, dew point and simulated reading   |
| `controllers/main_controller.py`       | Main window: cards, status and button actions                   |
| `controllers/grafico_controller.py`    | Temperature chart (pyqtgraph)                                   |
| `controllers/historico_controller.py`  | History table, filters and saving to the database               |
| `controllers/config_controller.py`     | Settings dialog and limit validation                            |
| `database/connection.py`               | SQLite database connection                                      |
| `utils/generate_log.py`                | Event logging to `logs/systemp.log`                             |
| `ui/*.ui`                              | Layouts and styles made in Qt Designer                          |

## How it works

```
ui/*.ui (Qt Designer)  ──  loadUi  ──>  controllers (window, chart, history, settings)
                                               │
                          ┌────────────────────┼────────────────────┐
                          ▼                    ▼                    ▼
              models/telemetry_model.py   database/systemp.db   logs/systemp.log
                 (rules and limits)          (history)            (events)
```

The architecture follows the **MVC** pattern: screens live in the `.ui` files, rules in the model, and the controllers connect one to the other.

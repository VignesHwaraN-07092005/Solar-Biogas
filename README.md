# 🌍 Solar-Biogas Intelligence Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-teal.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)

An intelligent platform that uses data and machine learning to optimize the process of turning organic waste into renewable energy (biogas) and electricity.

---

## 📖 What is this project? (For Everyone)

**Anaerobic digestion (AD)** is a natural process where microorganisms break down organic waste (like food scraps or manure) in the absence of oxygen to produce **biogas**, a renewable energy source that can be burned to generate electricity.

However, these biological systems are sensitive. If they get too acidic or too cold, the process breaks down. This project acts as the **"brain"** for these systems.

### What does it do?
- **Monitors Health:** It acts like a fitness tracker for the biogas digester, monitoring temperature, acidity (pH), and pressure to ensure the bacteria are healthy.
- **Predicts the Future:** It uses artificial intelligence to predict how much biogas will be produced tomorrow based on how much waste you feed it today.
- **Energy Conversion:** It calculates exactly how much electricity that biogas can generate for a community (e.g., powering lights, water pumps, or refrigerators).
- **Universal Dashboard:** Whether you have a massive industrial plant or a small community digester, you can upload your data or connect sensors to visualize the health of your system on a beautiful dashboard.

---

## 💻 Technical Overview (For Developers)

The **Biogas Intelligence Platform** bridges physical IoT telemetry, physics-based simulation, and machine learning to optimize anaerobic digesters, prevent reactor souring (acidosis), and forecast next-day biogas production.

### Core Architecture
- **Backend:** Built with **FastAPI** (Python) for high-performance REST APIs.
- **Data Ingestion:** A robust semantic ingestion engine that accepts arbitrary CSV/Excel uploads from SCADA systems and automatically normalizes units and aliases.
- **IoT Integration:** Direct ESP32 hardware ingest endpoints for real-time community digester monitoring.
- **Forecasting Engine:**
  - **GRU-14d Residual Model:** A Deep Learning model (Gated Recurrent Unit) validated on industrial plant data. Requires 14 days of historical data.
  - **XCO-Net Architecture:** An experimental deep convolutional network for research.
  - **EMA / Persistence Models:** Scale-compatible statistical baselines for smaller datasets.
- **Strict Data Provenance:** The system strictly separates industrial data from community data. Machine learning models trained on industrial data will responsibly withhold predictions on unvalidated community datasets to prevent unsafe operations.
- **Explainability:** Replaces generic black-box claims with local input sensitivity analysis so you always know *why* the model made a specific prediction.

---

## ✨ Key Features

- **📊 Multi-Scale Analytics:** Built for both massive industrial facilities (~5,300 Nm³/day) and small community digesters (~5 m³/day).
- **🔌 Flexible Data Uploads:** Drag and drop your SCADA exports or Excel spreadsheets. The system automatically figures out the columns (e.g., mapping `Temp_Outlet` to `temperature_c`) and converts units automatically.
- **🤖 Explainable AI (XAI):** The API (`/api/forecast/interp`) provides mathematical weight decompositions and sensitivity analysis for every prediction.
- **⚡ Microgrid Management:** Translates raw biogas volume into actionable electricity generation metrics (kW/kWh), mapping it to potential community loads.
- **🛡️ Safety Interlocks:** 5-category structured safety alerts (Digester, Gas, Sensor, Energy, Solar) to prevent system failure.

---

## 🚀 Quickstart Guide

### Prerequisites
- Python 3.10 or higher
- A virtual environment (recommended)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/VignesHwaraN-07092005/Solar-Biogas.git
   cd Solar-Biogas
   ```

2. **Set up a virtual environment**:
   ```bash
   python -m venv venv
   
   # On Windows:
   .\venv\Scripts\activate
   
   # On Linux/macOS:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure the environment**:
   ```bash
   cp .env.example .env
   ```
   *Edit the `.env` file to configure your database path, API keys, and CORS settings.*

### Running the Application

Start the FastAPI backend server:
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **Interactive Web Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- **API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Automated Testing

The repository contains a robust test suite covering time-series causality, model inference, SCADA ingestion, and security boundaries.

```bash
# Run the complete test suite
pytest

# Run tests with verbose output
pytest -v
```

---

## 📝 License

This project is licensed under the [MIT License](LICENSE).
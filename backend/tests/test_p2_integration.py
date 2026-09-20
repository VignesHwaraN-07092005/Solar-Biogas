import os
import re
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.simulator_service import SimulatorService

client = TestClient(app)

def test_p2_alert_thresholds_categorized():
    res = client.get('/api/alerts/thresholds')
    assert res.status_code == 200
    data = res.json()
    assert 'disclaimer' in data
    assert 'Prototype configurable alert threshold' in data['disclaimer']
    assert 'categories' in data
    for cat in ['DIGESTER', 'GAS', 'SENSOR', 'ENERGY', 'SOLAR']:
        assert cat in data['categories']
    # Backward compatibility
    assert 'alert_ph_min' in data
    assert 'alert_temp_min' in data
    assert 'alert_pressure_max' in data

def test_p2_alert_evaluate_5_categories():
    # 1. DIGESTER alert
    res_ph = client.post('/api/alerts/evaluate', json={'ph': 6.1})
    assert res_ph.status_code == 200
    d_ph = res_ph.json()
    assert d_ph['digester_status'] == 'CRITICAL'
    assert any(a['category'] == 'DIGESTER' for a in d_ph['alerts'])

    # 2. GAS alert (low biogas yield)
    res_gas = client.post('/api/alerts/evaluate', json={'biogas_production_m3_day': 0.2})
    assert res_gas.status_code == 200
    d_gas = res_gas.json()
    assert d_gas['gas_status'] == 'WARNING'
    assert any(a['category'] == 'GAS' and a['parameter'] == 'biogas_production' for a in d_gas['alerts'])

    # 3. SENSOR alert (offline)
    res_sens = client.post('/api/alerts/evaluate', json={'is_sensor_connected': False})
    assert res_sens.status_code == 200
    d_sens = res_sens.json()
    assert d_sens['sensor_status'] == 'WARNING'
    assert any(a['category'] == 'SENSOR' for a in d_sens['alerts'])

    # 4. ENERGY alert (low predicted electricity)
    res_nrg = client.post('/api/alerts/evaluate', json={'predicted_energy_kwh': 0.5})
    assert res_nrg.status_code == 200
    d_nrg = res_nrg.json()
    assert d_nrg['energy_status'] == 'WARNING'
    assert any(a['category'] == 'ENERGY' for a in d_nrg['alerts'])

    # 5. SOLAR alert (low battery)
    res_sol = client.post('/api/alerts/evaluate', json={'battery_soc_percent': 15.0})
    assert res_sol.status_code == 200
    d_sol = res_sol.json()
    assert d_sol['solar_status'] == 'WARNING'
    assert any(a['category'] == 'SOLAR' for a in d_sol['alerts'])

def test_p2_simulator_timeline_electricity_fields():
    sim = SimulatorService(seed=42, default_days=20)
    timeline = sim.get_simulator_timeline(days=20, warmup_days=14)
    assert len(timeline) == 20

    for i, r in enumerate(timeline):
        assert r['generator_status'] == 'NOT CONNECTED'
        assert r['estimated_electricity_kwh'] is not None and r['estimated_electricity_kwh'] > 0
        assert r['average_equivalent_power_kw'] is not None and r['average_equivalent_power_kw'] > 0
        expected_power = round(r['estimated_electricity_kwh'] / 24.0, 3)
        assert abs(r['average_equivalent_power_kw'] - expected_power) < 0.005

        if i >= 13: # day 14+ has prediction
            assert r['predicted_electricity_kwh'] is not None and r['predicted_electricity_kwh'] > 0

def test_p2_zero_forbidden_terms():
    PAT = re.compile(r'\b(cooking|burner|stove|kitchen|lpg)\b', re.IGNORECASE)
    violations = []
    for root_dir in ['backend/app', 'frontend/public', 'simulation']:
        for root, _, files in os.walk(root_dir):
            for f in files:
                if f.endswith(('.py', '.html', '.js', '.css', '.json')):
                    path = os.path.join(root, f)
                    with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                        for i, line in enumerate(fp):
                            if PAT.search(line):
                                violations.append((path, i + 1, line.strip()))
    assert len(violations) == 0, f'Found forbidden terms: {violations}'

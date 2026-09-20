from simulation.synthetic_data_generator.generate_dataset import generate_ad_timeseries

def test_generate_timeseries_shape_and_columns():
    df = generate_ad_timeseries(days=10, sampling_hours=24, seed=42)
    assert len(df) == 10
    expected_cols = [
        "device_id", "timestamp", "temperature_c", "ambient_temperature_c",
        "ph", "pressure_bar", "gas_flow_m3_day", "biogas_production_m3_day",
        "methane_percent", "feedstock_mass_kg", "solar_voltage_v", "source"
    ]
    for col in expected_cols:
        assert col in df.columns

def test_generator_physical_bounds():
    df = generate_ad_timeseries(days=30, sampling_hours=24, seed=123)
    assert (df["temperature_c"] >= 20.0).all()
    assert (df["temperature_c"] <= 45.0).all()
    assert (df["ph"] >= 5.5).all()
    assert (df["ph"] <= 8.5).all()
    assert (df["biogas_production_m3_day"] > 0.0).all()
    assert (df["source"] == "synthetic").all()

def test_deterministic_seeding():
    df1 = generate_ad_timeseries(days=5, seed=99)
    df2 = generate_ad_timeseries(days=5, seed=99)
    assert df1["biogas_production_m3_day"].tolist() == df2["biogas_production_m3_day"].tolist()

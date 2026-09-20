def generate_operator_recommendation(
    predicted_yield: float,
    current_temp: float = None,
    current_ph: float = None,
    recent_yield: float = None,
    feedstock_mass: float = None
) -> str:
    """
    Generate natural-language operator advisory based on biokinetic context.
    """
    recs = []
    
    if current_ph is not None and current_ph < 6.8:
        recs.append("Slurry pH is trending acidic. Reduce high-sugar/food waste feed by 20% and add buffer (alkaline/dung wash).")
    elif current_ph is not None and current_ph > 8.0:
        recs.append("pH is elevated (>8.0). Check for ammonia accumulation and flush with water.")
        
    if current_temp is not None and current_temp < 32.0:
        recs.append("Reactor temperature is below optimal mesophilic range (35 C). Verify solar heating element operation.")
        
    if recent_yield is not None and predicted_yield < recent_yield * 0.75:
        recs.append(f"Predicted gas yield is down significantly ({predicted_yield:.2f} m3 vs {recent_yield:.2f} m3 recent average). Inspect feed continuity.")
    elif predicted_yield > 4.0:
        recs.append(f"Predicted gas yield is healthy ({predicted_yield:.2f} m3/day). Maintain current feeding schedule.")
    else:
        recs.append("Digester operating within normal baseline parameters.")
        
    return " ".join(recs)

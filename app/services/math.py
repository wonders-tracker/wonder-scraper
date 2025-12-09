from typing import List, Dict
import statistics


def calculate_stats(prices: List[float]) -> Dict[str, float]:
    """
    Calculates min, max, average, and volume from a list of prices.
    Returns a dictionary with keys: min, max, avg, volume.
    """
    if not prices:
        return {"min": 0.0, "max": 0.0, "avg": 0.0, "volume": 0}

    # Optional: Simple outlier filtering
    # If we have enough data points, remove top/bottom 5% to avoid noise
    # clean_prices = sorted(prices)
    # if len(clean_prices) > 20:
    #     trim_count = int(len(clean_prices) * 0.05)
    #     clean_prices = clean_prices[trim_count:-trim_count]
    # else:
    #     clean_prices = prices

    # Using raw prices for now as requested, strict min/max

    return {"min": min(prices), "max": max(prices), "avg": round(statistics.mean(prices), 2), "volume": len(prices)}

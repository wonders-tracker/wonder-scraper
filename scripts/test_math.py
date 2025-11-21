from app.services.math import calculate_stats

def test_calculate_stats():
    prices = [10.0, 20.0, 30.0, 100.0]
    stats = calculate_stats(prices)
    
    print(f"Stats: {stats}")
    assert stats["min"] == 10.0
    assert stats["max"] == 100.0
    assert stats["avg"] == 40.0
    assert stats["volume"] == 4
    
    # Test empty
    assert calculate_stats([])["volume"] == 0

if __name__ == "__main__":
    test_calculate_stats()
    print("Tests passed!")


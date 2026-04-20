import requests

API_URL = "http://127.0.0.1:8000"

def test_formulas():
    print("🧪 Testing the Formula Registry...")

    # Test 1: A valid SUM function
    payload_sum = {
        "function_name": "SUM",
        "arguments": [15, 25, 10]
    }
    response_sum = requests.post(f"{API_URL}/formula/evaluate", json=payload_sum)
    print(f"\nTesting SUM(15, 25, 10):")
    print(response_sum.json())

    # Test 2: A valid MAX function
    payload_max = {
        "function_name": "MAX",
        "arguments": [5, 99, 21, 42]
    }
    response_max = requests.post(f"{API_URL}/formula/evaluate", json=payload_max)
    print(f"\nTesting MAX(5, 99, 21, 42):")
    print(response_max.json())

    # Test 3: An unknown function (should fail gracefully)
    payload_unknown = {
        "function_name": "MAGIC_AI_PREDICT",
        "arguments": [1, 2, 3]
    }
    response_unknown = requests.post(f"{API_URL}/formula/evaluate", json=payload_unknown)
    print(f"\nTesting Unknown Function:")
    print(response_unknown.json())
    
    # Test 4: MEDIAN with odd number of values
    payload_median = {
        "function_name": "MEDIAN",
        "arguments": [1, 2, 3, 4, 5]
    }
    response_median = requests.post(f"{API_URL}/formula/evaluate", json=payload_median)
    print(f"\nTesting MEDIAN(1, 2, 3, 4, 5):")
    print(response_median.json())
    
    # Test 5: MEDIAN with even number of values (should average middle two)
    payload_median_even = {
        "function_name": "MEDIAN",
        "arguments": [1, 2, 6, 4]
    }
    response_median_even = requests.post(f"{API_URL}/formula/evaluate", json=payload_median_even)
    print(f"\nTesting MEDIAN(1, 2, 6, 4) - even count:")
    print(response_median_even.json())
    
    # Test 6: COUNTIF with numeric exact match
    payload_countif = {
        "function_name": "COUNTIF",
        "arguments": [[1, 5, 5, 2, 5], 5]
    }
    response_countif = requests.post(f"{API_URL}/formula/evaluate", json=payload_countif)
    print(f"\nTesting COUNTIF([1,5,5,2,5], 5) - exact match:")
    print(response_countif.json())
    
    # Test 7: COUNTIF with comparison operator
    payload_countif_greater = {
        "function_name": "COUNTIF",
        "arguments": [[1, 5, 5, 2, 5], ">3"]
    }
    response_countif_greater = requests.post(f"{API_URL}/formula/evaluate", json=payload_countif_greater)
    print(f"\nTesting COUNTIF([1,5,5,2,5], '>3') - comparison:")
    print(response_countif_greater.json())
    
    # Test 8: COUNTIF with string exact match
    payload_countif_string = {
        "function_name": "COUNTIF",
        "arguments": [["apple", "banana", "apple", "cherry"], "apple"]
    }
    response_countif_string = requests.post(f"{API_URL}/formula/evaluate", json=payload_countif_string)
    print(f"\nTesting COUNTIF(['apple','banana','apple','cherry'], 'apple'):")
    print(response_countif_string.json())

if __name__ == "__main__":
    test_formulas()
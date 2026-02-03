import datetime
import pytz

# Base URL for Kalshi events
BASE_URL = "https://kalshi.com/markets/kxbtcd/bitcoin-price-abovebelow/"

def generate_kalshi_slug(target_time):
    """
    Generates the Kalshi event slug for a given datetime.
    Format: kxbtcd-[YY][MMM][DD][HH]
    Example: kxbtcd-25nov2614 (Nov 26, 2025, 14:00 ET)
    """
    # Ensure time is in Eastern Time
    et_tz = pytz.timezone('US/Eastern')
    if target_time.tzinfo is None:
        # Assume UTC if no timezone is provided, then convert to ET
        target_time = pytz.utc.localize(target_time).astimezone(et_tz)
    else:
        target_time = target_time.astimezone(et_tz)

    # Format components
    year = target_time.strftime("%y") # 2-digit year
    month = target_time.strftime("%b").lower() # 3-letter month, lowercase
    day = target_time.strftime("%d") # 2-digit day
    hour = target_time.strftime("%H") # 24-hour format
    
    slug = f"kxbtcd-{year}{month}{day}{hour}"
    return slug

def generate_kalshi_url(target_time):
    """
    Generates the full Kalshi URL for a given datetime.
    """
    slug = generate_kalshi_slug(target_time)
    return f"{BASE_URL}{slug}"

def generate_urls_until_year_end():
    """
    Generates URLs for every hour from now until Jan 1, 2026.
    Saves them to 'kalshi_urls_2025.txt'.
    """
    urls = []
    now = datetime.datetime.now(pytz.utc)
    
    # Start from the next full hour
    current_target = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
    
    # End date: Jan 1, 2026 00:00 UTC (approx, depends on ET)
    et_tz = pytz.timezone('US/Eastern')
    
    print(f"Generating URLs starting from: {current_target.astimezone(et_tz)}")
    
    while True:
        # Check if we reached 2026 in ET
        et_time = current_target.astimezone(et_tz)
        if et_time.year >= 2026:
            break
            
        urls.append(generate_kalshi_url(current_target))
        current_target += datetime.timedelta(hours=1)
        
    with open("kalshi_urls_2025.txt", "w") as f:
        for url in urls:
            f.write(url + "\n")
            
    print(f"Generated {len(urls)} URLs and saved to 'kalshi_urls_2025.txt'")

if __name__ == "__main__":
    print("--- Kalshi URL Generator ---")
    
    # Test with the user's specific example time to verify logic
    # User example: kxbtcd-25nov2614 -> Nov 26, 2025, 14:00 ET
    
    et_tz = pytz.timezone('US/Eastern')
    test_time = et_tz.localize(datetime.datetime(2025, 11, 26, 14, 0, 0))
    print(f"Test Time (ET): {test_time}")
    print(f"Generated URL: {generate_kalshi_url(test_time)}")
    
    print("\n--- Generating URLs until 2026 ---")
    generate_urls_until_year_end()

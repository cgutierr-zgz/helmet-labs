import requests
import json

def inspect_clob(token_id):
    url = "https://clob.polymarket.com/book"
    try:
        print(f"Fetching book for token: {token_id}")
        response = requests.get(url, params={"token_id": token_id})
        response.raise_for_status()
        data = response.json()
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Use a known token ID from previous output or fetch one
    # I'll fetch the event first to get a token ID
    slug = "bitcoin-up-or-down-november-26-2pm-et"
    url = "https://gamma-api.polymarket.com/events"
    resp = requests.get(url, params={"slug": slug})
    data = resp.json()
    if data:
        token_ids = eval(data[0]['markets'][0]['clobTokenIds'])
        inspect_clob(token_ids[0])

#!/usr/bin/env python3
"""
Sports ELO Bot - NBA team ratings vs Polymarket odds
Calculates ELO ratings from recent NBA games and compares to market odds.
Edge = significant difference between ELO prediction and market price.

SETUP: Get free API key from https://www.balldontlie.io/
       Set environment variable: export BALLDONTLIE_API_KEY="your_key"
       Or edit API_KEY below
"""

import requests
import json
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

STATE_FILE = Path(__file__).parent / "sports_elo_state.json"
LOG_FILE = Path(__file__).parent / "sports_elo_signals.log"

# balldontlie.io API - Get key from https://www.balldontlie.io/
API_BASE = "https://api.balldontlie.io/v1"
API_KEY = os.getenv("BALLDONTLIE_API_KEY", "")  # Set your API key here or in env

# ELO parameters
INITIAL_ELO = 1500
K_FACTOR = 20  # How much ratings change per game

# Mock mode (for testing without API key)
MOCK_MODE = not API_KEY


def load_state():
    """Load bot state from file"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "last_run": None,
        "elo_ratings": {},
        "games_processed": [],
        "signals_today": 0
    }


def save_state(state):
    """Save bot state to file"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def log_signal(signal_type, home_team, away_team, elo_prob, details):
    """Log a trading signal"""
    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "signal": signal_type,
        "home_team": home_team,
        "away_team": away_team,
        "elo_probability": elo_prob,
        "details": details
    }
    
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    
    print(f"[{timestamp}] SIGNAL: {signal_type}")
    print(f"  {home_team} vs {away_team} | ELO prob: {elo_prob:.1%}")
    print(f"  {details}")
    return log_entry


def get_mock_games():
    """Generate mock game data for testing"""
    teams = [
        "Boston Celtics", "Milwaukee Bucks", "Philadelphia 76ers", "Cleveland Cavaliers",
        "New York Knicks", "Miami Heat", "Brooklyn Nets", "Atlanta Hawks",
        "Los Angeles Lakers", "Denver Nuggets", "Phoenix Suns", "Golden State Warriors",
        "LA Clippers", "Sacramento Kings", "Dallas Mavericks", "Minnesota Timberwolves"
    ]
    
    games = []
    base_date = datetime.now() - timedelta(days=7)
    
    for i in range(20):
        home_idx = i % len(teams)
        away_idx = (i + 3) % len(teams)
        home_score = 100 + (i * 7) % 30
        away_score = 100 + (i * 11) % 30
        
        games.append({
            "id": 1000 + i,
            "date": (base_date + timedelta(days=i % 7)).isoformat(),
            "status": "Final",
            "home_team": {"full_name": teams[home_idx]},
            "visitor_team": {"full_name": teams[away_idx]},
            "home_team_score": home_score,
            "visitor_team_score": away_score
        })
    
    return games


def fetch_recent_games(days_back=14):
    """Fetch recent NBA games from balldontlie.io"""
    if MOCK_MODE:
        print("🧪 MOCK MODE: Using sample data (set BALLDONTLIE_API_KEY to use real API)")
        return get_mock_games()
    
    games = []
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    try:
        print(f"Fetching games from {start_date.date()} to {end_date.date()}...")
        
        headers = {"Authorization": API_KEY} if API_KEY else {}
        
        # Note: The free API has rate limits (60 req/min)
        # We'll fetch games page by page
        for page in range(1, 4):  # Get first 3 pages (up to 75 games)
            url = f"{API_BASE}/games"
            params = {
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "per_page": 25,
                "page": page
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                page_games = data.get("data", [])
                games.extend(page_games)
                
                # Check if there are more pages
                meta = data.get("meta", {})
                if page >= meta.get("total_pages", 1):
                    break
                
                time.sleep(1)  # Rate limit courtesy
            else:
                print(f"API error (page {page}): {response.status_code}")
                if response.status_code == 401:
                    print("⚠️  API key required! Get one at https://www.balldontlie.io/")
                break
        
        # Filter for completed games only
        completed = [g for g in games if g.get("status") == "Final"]
        print(f"Found {len(completed)} completed games")
        
        return completed
    
    except Exception as e:
        print(f"Error fetching games: {e}")
        return []


def calculate_expected_score(rating_a, rating_b):
    """Calculate expected score (win probability) for team A"""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def update_elo(winner_elo, loser_elo, k=K_FACTOR):
    """Update ELO ratings after a game"""
    expected_winner = calculate_expected_score(winner_elo, loser_elo)
    expected_loser = calculate_expected_score(loser_elo, winner_elo)
    
    new_winner_elo = winner_elo + k * (1 - expected_winner)
    new_loser_elo = loser_elo + k * (0 - expected_loser)
    
    return new_winner_elo, new_loser_elo


def process_games(games, state):
    """Process games and update ELO ratings"""
    elo_ratings = state.get("elo_ratings", {})
    processed = set(state.get("games_processed", []))
    
    # Sort games by date (oldest first)
    games_sorted = sorted(games, key=lambda g: g.get("date", ""))
    
    new_games = 0
    for game in games_sorted:
        game_id = game.get("id")
        if game_id in processed:
            continue
        
        home_team = game.get("home_team", {}).get("full_name", "Unknown")
        away_team = game.get("visitor_team", {}).get("full_name", "Unknown")
        home_score = game.get("home_team_score", 0)
        away_score = game.get("visitor_team_score", 0)
        
        # Initialize ELO if needed
        if home_team not in elo_ratings:
            elo_ratings[home_team] = INITIAL_ELO
        if away_team not in elo_ratings:
            elo_ratings[away_team] = INITIAL_ELO
        
        # Determine winner and update ELO
        if home_score > away_score:
            winner, loser = home_team, away_team
            winner_elo, loser_elo = elo_ratings[home_team], elo_ratings[away_team]
        else:
            winner, loser = away_team, home_team
            winner_elo, loser_elo = elo_ratings[away_team], elo_ratings[home_team]
        
        new_winner_elo, new_loser_elo = update_elo(winner_elo, loser_elo)
        
        elo_ratings[winner] = new_winner_elo
        elo_ratings[loser] = new_loser_elo
        
        processed.add(game_id)
        new_games += 1
    
    print(f"Processed {new_games} new games")
    
    state["elo_ratings"] = elo_ratings
    state["games_processed"] = list(processed)[-500:]  # Keep last 500 game IDs
    
    return elo_ratings


def fetch_upcoming_games():
    """Fetch upcoming NBA games (next 3 days)"""
    if MOCK_MODE:
        # Mock upcoming games
        teams = ["Boston Celtics", "Milwaukee Bucks", "Los Angeles Lakers", "Denver Nuggets"]
        return [
            {
                "id": 9001,
                "date": (datetime.now() + timedelta(days=1)).isoformat(),
                "status": "scheduled",
                "home_team": {"full_name": teams[0]},
                "visitor_team": {"full_name": teams[1]}
            },
            {
                "id": 9002,
                "date": (datetime.now() + timedelta(days=1)).isoformat(),
                "status": "scheduled",
                "home_team": {"full_name": teams[2]},
                "visitor_team": {"full_name": teams[3]}
            }
        ]
    
    try:
        start_date = datetime.now()
        end_date = start_date + timedelta(days=3)
        
        headers = {"Authorization": API_KEY} if API_KEY else {}
        
        url = f"{API_BASE}/games"
        params = {
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "per_page": 25
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            games = data.get("data", [])
            # Filter for not started games
            upcoming = [g for g in games if g.get("status", "").lower() in ["", "scheduled", "upcoming"]]
            print(f"Found {len(upcoming)} upcoming games")
            return upcoming
        else:
            print(f"Error fetching upcoming games: {response.status_code}")
            return []
    
    except Exception as e:
        print(f"Error fetching upcoming games: {e}")
        return []


def find_edges(upcoming_games, elo_ratings):
    """Find potential edges in upcoming games"""
    signals = []
    
    for game in upcoming_games:
        home_team = game.get("home_team", {}).get("full_name")
        away_team = game.get("visitor_team", {}).get("full_name")
        
        if not home_team or not away_team:
            continue
        
        # Get ELO ratings (default to initial if team is new)
        home_elo = elo_ratings.get(home_team, INITIAL_ELO)
        away_elo = elo_ratings.get(away_team, INITIAL_ELO)
        
        # Calculate ELO-based win probability for home team
        home_win_prob = calculate_expected_score(home_elo, away_elo)
        
        # Look for strong edges (>65% or <35% probability)
        # In a real bot, you'd compare to Polymarket odds here
        if home_win_prob > 0.65:
            signals.append(log_signal(
                "HOME_FAVORITE",
                home_team,
                away_team,
                home_win_prob,
                f"ELO: {home_elo:.0f} vs {away_elo:.0f} | Strong home favorite (check Polymarket odds)"
            ))
        elif home_win_prob < 0.35:
            signals.append(log_signal(
                "AWAY_FAVORITE",
                home_team,
                away_team,
                home_win_prob,
                f"ELO: {home_elo:.0f} vs {away_elo:.0f} | Strong away favorite (check Polymarket odds)"
            ))
    
    return signals


def cycle():
    """Main bot cycle - update ELO and find edges"""
    print(f"\n{'='*60}")
    print(f"Sports ELO Bot - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    state = load_state()
    
    # Fetch and process recent games to update ELO
    recent_games = fetch_recent_games(days_back=14)
    elo_ratings = process_games(recent_games, state)
    
    # Show top 10 teams by ELO
    print("\nTop 10 teams by ELO:")
    sorted_teams = sorted(elo_ratings.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (team, elo) in enumerate(sorted_teams, 1):
        print(f"  {i}. {team}: {elo:.0f}")
    
    # Fetch upcoming games and find edges
    print("\nAnalyzing upcoming games...")
    upcoming_games = fetch_upcoming_games()
    signals = find_edges(upcoming_games, elo_ratings)
    
    # Update state
    state["last_run"] = datetime.now().isoformat()
    state["signals_today"] = state.get("signals_today", 0) + len(signals)
    
    save_state(state)
    
    print(f"\nState saved. Signals today: {state.get('signals_today', 0)}")
    print("\nNOTE: To find real edges, compare ELO probabilities to Polymarket odds!")
    print("      Edge = |ELO_prob - Market_price| > threshold (e.g., 10%)")
    
    return signals


if __name__ == "__main__":
    cycle()

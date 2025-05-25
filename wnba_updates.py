import tweepy
import requests
from py_ball import boxscore, leagueleaders
from datetime import datetime, date
import os

# API Credentials (stored as GitHub Secrets)
X_API_KEY = os.environ.get('X_API_KEY')
X_API_SECRET = os.environ.get('X_API_SECRET')
X_ACCESS_TOKEN = os.environ.get('X_ACCESS_TOKEN')
X_ACCESS_TOKEN_SECRET = os.environ.get('X_ACCESS_TOKEN_SECRET')
ODDS_API_KEY = os.environ.get('ODDS_API_KEY')

# Tweepy setup
auth = tweepy.OAuthHandler(X_API_KEY, X_API_SECRET)
auth.set_access_token(X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET)
api = tweepy.API(auth, wait_on_rate_limit=True)

# Odds API endpoints
ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/basketball_wnba/odds"
SCORES_API_URL = "https://api.the-odds-api.com/v4/sports/basketball_wnba/scores"

def get_today_games():
    """Fetch today's WNBA games with betting odds."""
    today = date.today().isoformat()
    params = {"apiKey": ODDS_API_KEY, "regions": "us", "markets": "h2h"}
    try:
        response = requests.get(ODDS_API_URL, params=params)
        response.raise_for_status()
        games = response.json()
        return [game for game in games if game["commence_time"].startswith(today)]
    except Exception as e:
        print(f"Error fetching games: {e}")
        return []

def get_game_summary(game_id):
    """Fetch game summary (scores and top performers)."""
    try:
        params = {"apiKey": ODDS_API_KEY}
        response = requests.get(SCORES_API_URL, params=params)
        response.raise_for_status()
        games = response.json()
        game = next((g for g in games if g["id"] == game_id), None)
        if game and game.get("completed") and game.get("scores"):
            # Try to get top performers using py_ball
            try:
                box = boxscore.BoxScore(headers={}, game_id=game_id).data
                top_players = sorted(box.get('PlayerStats', []), key=lambda x: x['PTS'], reverse=True)[:2]
                performers = "\n".join(
                    f"- {p['NAME']} ({p['TEAM']}): {p['PTS']} pts, {p['REB']} reb"
                    for p in top_players
                )
            except Exception:
                performers = "Top performers unavailable."
            return (
                f"{game['away_team']} {game['scores']['away']['total']} - "
                f"{game['home_team']} {game['scores']['home']['total']}\n"
                f"Top Performers:\n{performers}"
            )
        return None
    except Exception as e:
        print(f"Error fetching summary for game {game_id}: {e}")
        return None

def get_top_players():
    """Fetch top 10 players by points per game."""
    try:
        leaders = leagueleaders.LeaderBoard(
            headers={}, league_id='10', stat_category_ll='PTS', per_mode='PerGame'
        ).data
        return "\n".join(
            f"{i+1}. {p['PLAYER']} ({p['TEAM']}): {p['PPG']} PPG"
            for i, p in enumerate(leaders[:10])
        )
    except Exception as e:
        print(f"Error fetching player stats: {e}")
        return "Player stats unavailable today."

def post_to_x(message):
    """Post a message to X."""
    try:
        if len(message) > 280:
            message = message[:277] + "..."
        api.update_status(message)
        print(f"Posted to X: {message}")
    except Exception as e:
        print(f"Error posting to X: {e}")

def main():
    """Main function to handle morning and evening posts."""
    games = get_today_games()
    now = datetime.utcnow()
    
    # Morning post (8 AM UTC / 4 AM EDT)
    if 7 <= now.hour < 9:
        if games:
            post = "🏀 Today's WNBA Games:\n"
            for game in games:
                odds = game["bookmakers"][0]["markets"][0]["outcomes"]
                commence_time = datetime.fromisoformat(
                    game["commence_time"].replace("Z", "+00:00")
                ).strftime("%I:%M %p ET")
                post += (
                    f"- {game['away_team']} @ {game['home_team']}, {commence_time}\n"
                    f"  Odds: {odds[0]['name']} {odds[0]['price']}, "
                    f"{odds[1]['name']} {odds[1]['price']} (via {game['bookmakers'][0]['title']})\n"
                )
            post += "#WNBA #BettingOdds"
            post_to_x(post)
        else:
            post = "🏀 No WNBA games today. Check out top player stats tonight! #WNBA"
            post_to_x(post)
    
    # Evening post (11 PM UTC / 7 PM EDT)
    elif 22 <= now.hour < 24:
        if games:
            for game in games:
                summary = get_game_summary(game["id"])
                if summary:
                    post = f"🏀 Game Summary:\n{summary}\n#WNBA #GameSummary"
                    post_to_x(post)
        else:
            stats = get_top_players()
            post = f"🏀 No games today. Top 10 Scorers:\n{stats}\n#WNBA #PlayerStats"
            post_to_x(post)

if __name__ == "__main__":
    main()
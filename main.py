#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests

parser = argparse.ArgumentParser(
    description="Monitor the CTFTime leaderboard for changes in a team's national ranking"
)
parser.add_argument(
    "--team",
    type=int,
    default=109611,
    help="CTFTime Team ID to track (default: 109611)",
)
parser.add_argument(
    "--country",
    type=str,
    default="no",
    help="Country code for leaderboard (default: no)",
)
args = parser.parse_args()

TEAM_ID = args.team
COUNTRY_CODE = args.country
API_URL = f"https://ctftime.org/api/v1/top-by-country/{COUNTRY_CODE}/"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

LEADERBOARD_FILE = Path("leaderboard.json")

USE_LINKS = True
INCLUDE_POINTS = False

if not WEBHOOK_URL:
    print("WEBHOOK_URL environment variable not set", file=sys.stderr)
    sys.exit(1)
elif not WEBHOOK_URL.startswith("https://stoat.chat/api/webhooks/"):
    print(
        f"WEBHOOK_URL does not appear to be a Stoat webhook URL. Found: {WEBHOOK_URL}",
        file=sys.stderr,
    )
    sys.exit(1)


def fetch_leaderboard():
    try:
        response = requests.get(API_URL, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch leaderboard (Request Error): {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Failed to decode leaderboard JSON: {e}", file=sys.stderr)
        sys.exit(1)


def load_old_leaderboard():
    if not LEADERBOARD_FILE.exists():
        return None
    try:
        return json.loads(LEADERBOARD_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError) as e:
        print(f"Could not load/decode old leaderboard file: {e}", file=sys.stderr)
        sys.exit(1)


def save_new_leaderboard(leaderboard):
    try:
        LEADERBOARD_FILE.write_text(json.dumps(leaderboard, indent=2), encoding="utf-8")
    except IOError as e:
        print(f"Failed to save new leaderboard file: {e}", file=sys.stderr)
        sys.exit(1)


def escape_markdown(text):
    return re.sub(r"([\\`*_{}\[\]()#+\-.!])", r"\\\1", text)


def format_team_name(team, use_link=True, include_points=False):
    name = escape_markdown(team["team_name"])

    if include_points:
        name += f" ({team['points']:.2f} p)"

    if use_link:
        url = f"https://ctftime.org/team/{team['team_id']}"
        name = f"[{name}](<{url}>)"

    return name


def format_team_list(team_ids, team_map, use_link=True, include_points=False):
    if not team_ids:
        return ""

    formatted = [
        format_team_name(team_map[t_id], use_link, include_points) for t_id in team_ids
    ]

    if len(formatted) == 1:
        return formatted[0]

    return ", ".join(formatted[:-1]) + " og " + formatted[-1]


def generate_message(old, new):
    new_map = {team["team_id"]: team for team in new}
    old_map = {team["team_id"]: team for team in old} if old else {}

    if TEAM_ID not in new_map:
        if TEAM_ID in old_map:
            old_place = old_map[TEAM_ID]["country_place"]
            return f"**{old_map[TEAM_ID]['team_name']} er ikke på den nye ledertavla! De lå sist på {old_place}. plass.**"
        else:
            return None

    team_name = format_team_name(new_map[TEAM_ID], USE_LINKS, INCLUDE_POINTS)
    new_place = new_map[TEAM_ID]["country_place"]

    if not old or TEAM_ID not in old_map:
        return f"**{team_name} ligger nå på {new_place}. plass**"

    old_place = old_map[TEAM_ID]["country_place"]

    passed_ids = []
    overtaken_ids = []

    for t_id, new_team in new_map.items():
        if t_id == TEAM_ID:
            continue

        if t_id not in old_map:
            continue

        old_t_place = old_map[t_id]["country_place"]
        new_t_place = new_team["country_place"]

        if new_t_place < new_place and old_t_place >= old_place:
            overtaken_ids.append(t_id)

        elif new_t_place > new_place and old_t_place <= old_place:
            passed_ids.append(t_id)

    passed_str = format_team_list(passed_ids, new_map, USE_LINKS, INCLUDE_POINTS)
    overtaken_str = format_team_list(overtaken_ids, new_map, USE_LINKS, INCLUDE_POINTS)

    if new_place == old_place:
        if passed_ids and overtaken_ids:
            return f"**{team_name} ligger fortsatt på {new_place}. plass. Vi tok igjen {passed_str}, men ble passert av {overtaken_str}.**"
        else:
            return None

    elif new_place == 1:
        return f"**{team_name} er på topp igjen!**"

    elif new_place < old_place:
        return f"**{team_name} har rykket opp til {new_place}. plass! Vi har tatt igjen {passed_str}.**"

    elif new_place > old_place:
        return f"**{team_name} har falt til {new_place}. plass etter å ha blitt passert av {overtaken_str}.**"

    return f"**{team_name} ligger nå på {new_place}. plass.**"


def send_webhook(message):
    try:
        r = requests.post(
            WEBHOOK_URL,
            timeout=30,
            json={
                "masquerade": {
                    "name": "CTFTime-Vakta",
                    "avatar": "https://ctftime.org/static/images/ctftime-logo-avatar.png",
                },
                "content": message,
            },
        )
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Failed to send webhook: {e}", file=sys.stderr)
    else:
        print("Webhook sent successfully!")


def main():
    old_leaderboard = load_old_leaderboard()
    new_leaderboard = fetch_leaderboard()

    message = generate_message(old_leaderboard, new_leaderboard)
    if message:
        send_webhook(message)
    else:
        print("No significant change in leaderboard detected. Skipping webhook.")
    save_new_leaderboard(new_leaderboard)


if __name__ == "__main__":
    main()

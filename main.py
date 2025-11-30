#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests

TEAM_INFO_URL_TEMPLATE = "https://ctftime.org/api/v1/teams/{team_id}/"
LEADERBOARD_URL_TEMPLATE = "https://ctftime.org/api/v1/top-by-country/{country}/"
TEAM_PAGE_URL_TEMPLATE = "https://ctftime.org/team/{team_id}"

LEADERBOARD_FILE = Path("leaderboard.json")

parser = argparse.ArgumentParser(
    description="Monitor CTFtime leaderboard for changes in a team's national ranking"
)

parser.add_argument(
    "--team",
    type=int,
    default=109611,
    help="CTFtime Team ID to track (default: 109611)",
)

args = parser.parse_args()
TEAM_ID = args.team

WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

USE_LINKS = True
INCLUDE_POINTS = False

if not WEBHOOK_URL:
    print("WEBHOOK_URL environment variable not set", file=sys.stderr)
    sys.exit(1)

if not WEBHOOK_URL.startswith("https://stoat.chat/api/webhooks/"):
    print(
        f"WEBHOOK_URL does not look like a Stoat webhook URL. Found: {WEBHOOK_URL}",
        file=sys.stderr,
    )
    sys.exit(1)


def fetch_team_info(team_id: int):
    url = TEAM_INFO_URL_TEMPLATE.format(team_id=team_id)

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 404:
            print(f"Team with ID {TEAM_ID} not found", file=sys.stderr)
            sys.exit(1)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch team info: {e}", file=sys.stderr)
        sys.exit(1)


def fetch_leaderboard(api_url: str):
    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        data = response.json()

        for team in data:
            team.pop("team_country", None)
            team.pop("place", None)

        return data

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch leaderboard: {e}", file=sys.stderr)
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
        print(f"Could not load old leaderboard file: {e}", file=sys.stderr)
        sys.exit(1)


def save_new_leaderboard(leaderboard):
    try:
        LEADERBOARD_FILE.write_text(json.dumps(leaderboard, indent=2), encoding="utf-8")
    except IOError as e:
        print(f"Failed to save leaderboard: {e}", file=sys.stderr)
        sys.exit(1)


def escape_markdown(text: str):
    return re.sub(r"([\\`*_{}\[\]()#+\-.!])", r"\\\1", text)


def format_team_name(team, use_link=True, include_points=False):
    name = escape_markdown(team["team_name"])

    if include_points:
        name += f" ({team['points']:.2f} p)"

    if use_link:
        url = TEAM_PAGE_URL_TEMPLATE.format(team_id=team["team_id"])
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


def generate_message(old, new, tracked_team_id):
    new_map = {t["team_id"]: t for t in new} if new else {}
    old_map = {t["team_id"]: t for t in old} if old else {}

    if tracked_team_id not in new_map:
        if tracked_team_id in old_map:
            old_place = old_map[tracked_team_id]["country_place"]
            return (
                f"**{old_map[tracked_team_id]['team_name']} er ikke på det nye "
                f"leaderboardet! De lå sist på {old_place}. plass.**"
            )
        return None

    team_name = format_team_name(new_map[tracked_team_id], USE_LINKS, INCLUDE_POINTS)
    new_place = new_map[tracked_team_id]["country_place"]

    if not old or tracked_team_id not in old_map:
        return f"**{team_name} ligger nå på {new_place}. plass**"

    old_place = old_map[tracked_team_id]["country_place"]

    passed_ids = []
    overtaken_ids = []

    for t_id, new_team in new_map.items():
        if t_id == tracked_team_id or t_id not in old_map:
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
            return (
                f"**{team_name} ligger fortsatt på {new_place}. plass. "
                f"Vi tok igjen {passed_str}, men ble passert av {overtaken_str}.**"
            )
        return None

    if new_place == 1:
        return f"**{team_name} er på topp igjen!**"

    if new_place < old_place:
        if passed_ids and overtaken_ids:
            return (
                f"**{team_name} har rykket opp til {new_place}. plass! "
                f"Vi har tatt igjen {passed_str}, men ble også passert av {overtaken_str}.**"
            )
        elif passed_ids:
            return (
                f"**{team_name} har rykket opp til {new_place}. plass! "
                f"Vi har tatt igjen {passed_str}.**"
            )
        else:
            return (
                f"**{team_name} har rykket opp til {new_place}. plass!**"
            )

    if new_place > old_place:
        if passed_ids and overtaken_ids:
            return (
                f"**{team_name} har falt til {new_place}. plass! "
                f"Vi tok igjen {passed_str}, men ble også passert av {overtaken_str}.**"
            )
        elif overtaken_ids:
            return (
                f"**{team_name} har falt til {new_place}. plass etter å ha blitt "
                f"passert av {overtaken_str}.**"
            )
        else:
            return (
                f"**{team_name} har falt til {new_place}. plass.**"
            )

    return f"**{team_name} ligger nå på {new_place}. plass.**"


def send_webhook(message: str):
    try:
        r = requests.post(
            WEBHOOK_URL,
            timeout=30,
            json={
                "masquerade": {
                    "name": "CTFtime-vakta",
                    "avatar": "https://ctftime.org/static/images/ctftime-logo-avatar.png",
                },
                "content": message,
            },
        )
        r.raise_for_status()
        print("Webhook sent successfully!")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send webhook: {e}", file=sys.stderr)


def main():
    team_info = fetch_team_info(TEAM_ID)
    country = team_info.get("country")
    if not country:
        print("Team info did not contain country", file=sys.stderr)
        sys.exit(1)

    country = country.lower()
    api_url = LEADERBOARD_URL_TEMPLATE.format(country=country)

    old_leaderboard = load_old_leaderboard()
    new_leaderboard = fetch_leaderboard(api_url)

    message = generate_message(old_leaderboard, new_leaderboard, TEAM_ID)

    if message:
        send_webhook(message)
    else:
        print("No significant change in leaderboard detected. Skipping webhook.")

    save_new_leaderboard(new_leaderboard)


if __name__ == "__main__":
    main()

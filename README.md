<h1 align="center">CTFtime-vakta</h1>

<p align="center">
Monitor a CTFtime team's national leaderboard position and get notified when the rank changes.
</p>

<p align="center">
  <img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/Iku-toppene/ctftime-vakta/run.yml?style=for-the-badge&logo=happycow&logoColor=white&label=Iku-toppene%20tracker">
</p>

---

## Features

- Tracks a team's national rank on CTFtime
- Detects rank changes and sends notifications via webhook
- Stores previous leaderboard positions in `leaderboard.json` for comparison

## Usage

```bash
# Clone the repository
git clone https://github.com/Iku-toppene/ctftime-vakta.git
cd ctftime-vakta

# Install dependencies
pip install -r requirements.txt

# Set your webhook URL
export WEBHOOK_URL="https://stoat.chat/api/webhooks/..."

# Run the script
python main.py --team YOUR_TEAM_ID
```

## License

MIT License © 2025 [Iku-toppene](https://github.com/Iku-toppene)

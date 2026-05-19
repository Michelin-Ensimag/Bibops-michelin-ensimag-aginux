"""Team C — State & Tools (identical contract to team_client, separate identity)."""
from src.racing.team_client.state_tools import HUB_BASE_URL, TeamState, ask_michelin_engineer

TEAM_ID = "team_c_validated"

__all__ = ["HUB_BASE_URL", "TEAM_ID", "TeamState", "ask_michelin_engineer"]

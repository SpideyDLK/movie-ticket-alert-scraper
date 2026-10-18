import os
from dotenv import load_dotenv

load_dotenv()
next_action_id = os.getenv("SCOPE_NEXT_ACTION")
def get_next_action_id() -> str | None:
    return next_action_id

def update_next_action_id(value: str) -> None:
    global next_action_id
    next_action_id = value
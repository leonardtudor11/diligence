"""Probe — confirm Vertex AI works via the hackathon auth path."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vertex_client import get_client, PROJECT_ID, LOCATION


def main() -> None:
    print(f"Project : {PROJECT_ID}")
    print(f"Location: {LOCATION}")
    print("Model   : gemini-2.5-flash")
    print()

    client = get_client()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=(
            "Reply with one short sentence confirming you are running "
            "on Vertex AI and can hear me."
        ),
    )
    print("RESPONSE:", response.text.strip())
    print()
    print("OK — Vertex auth path verified.")


if __name__ == "__main__":
    main()

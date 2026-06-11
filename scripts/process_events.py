import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
source_path = ROOT / "data" / "raw" / "events" / "github_events.jsonl"
target_path = ROOT / "data" / "processed" / "push_events.json"
environment = os.getenv("APP_ENV", "local")


def filter_events(events: list, event_type: str = "PushEvent") -> list:
    return [e for e in events if e.get("type") == event_type]


def main(source: Path = None, target: Path = None) -> None:
    src = source or source_path
    dst = target or target_path

    events = []
    with src.open() as f:
        for line in f:
            events.append(json.loads(line))

    filtered = filter_events(events)

    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w") as f:
        json.dump(filtered, f, indent=2)

    print(f"Environment: {environment}")
    print(f"Eventos leidos:          {len(events)}")
    print(f"PushEvents encontrados:  {len(filtered)}")
    print(f"Salida: {dst}")


if __name__ == "__main__":
    main()

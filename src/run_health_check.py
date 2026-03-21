import json

from services.health import run_health_check


def main() -> None:
    result = run_health_check()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

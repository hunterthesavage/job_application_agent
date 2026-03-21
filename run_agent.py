import json
import subprocess
import sys
from pathlib import Path

from services.settings import load_settings


RUNTIME_SETTINGS_FILE = "runtime_settings.json"


def run_command(command: list[str], step_name: str) -> int:
    print(f"\n=== {step_name} ===")
    print("Running:", " ".join(command))
    print()

    result = subprocess.run(command)
    return result.returncode


def write_runtime_settings_file() -> Path:
    settings = load_settings()
    output_path = Path(RUNTIME_SETTINGS_FILE)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

    print(f"\nWrote runtime settings to {output_path.resolve()}")
    return output_path


def main() -> None:
    try:
        write_runtime_settings_file()
    except Exception as exc:
        print(f"\nFailed to write runtime settings: {exc}")
        sys.exit(1)

    discovery_code = run_command(
        [sys.executable, "-m", "src.discover_job_urls"],
        "Step 1: Discover Job URLs",
    )

    if discovery_code != 0:
        print("\nDiscovery failed. Stopping run.")
        sys.exit(discovery_code)

    validation_code = run_command(
        [sys.executable, "-m", "src.validate_job_url", "--file", "job_urls.txt"],
        "Step 2: Validate and Append Jobs",
    )

    if validation_code != 0:
        print("\nValidation failed.")
        sys.exit(validation_code)

    digest_code = run_command(
        [sys.executable, "-m", "src.digest"],
        "Step 3: Generate Daily Digest",
    )

    if digest_code != 0:
        print("\nDigest generation failed.")
        sys.exit(digest_code)

    print("\nAgent run complete.")
    print("Daily digest saved to daily_digest.txt")
    print(f"Runtime settings saved to {RUNTIME_SETTINGS_FILE}")


if __name__ == "__main__":
    main()
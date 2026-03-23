import subprocess
import sys

from config import JOB_URLS_FILE


def run_command(command: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(command, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def main() -> None:
    print("Running discovery...")
    code, out, err = run_command([sys.executable, "-m", "src.discover_job_urls"])
    print(out)
    if code != 0:
        print(err)
        raise SystemExit(code)

    print("\nRunning SQLite ingestion from discovered URL file...")
    code, out, err = run_command([sys.executable, "-m", "src.ingest_from_urls_file", str(JOB_URLS_FILE)])
    print(out)
    if code != 0:
        print(err)
        raise SystemExit(code)

    print("\nDiscovery + ingestion complete.")


if __name__ == "__main__":
    main()

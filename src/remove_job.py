import sys

from services.sqlite_actions import get_job_by_id, remove_job


def main() -> None:
    args = sys.argv[1:]

    if not args:
        print("Usage: python -m src.remove_job <job_id>")
        raise SystemExit(1)

    try:
        job_id = int(args[0])
    except ValueError:
        print("Job id must be an integer.")
        raise SystemExit(1)

    job = get_job_by_id(job_id)
    if job is None:
        print(f"Job id {job_id} not found.")
        raise SystemExit(1)

    removed = remove_job(job_id)

    company = str(removed.get("company", "") or "").strip()
    title = str(removed.get("title", "") or "").strip()

    print(f"Removed job: {company} - {title}")


if __name__ == "__main__":
    main()

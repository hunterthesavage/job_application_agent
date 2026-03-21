import sys

from services.sqlite_actions import get_job_by_id, mark_job_as_applied


def main() -> None:
    args = sys.argv[1:]

    if not args:
        print("Usage: python -m src.move_job <job_id>")
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

    updated = mark_job_as_applied(job_id)

    company = str(updated.get("company", "") or "").strip()
    title = str(updated.get("title", "") or "").strip()
    applied_date = str(updated.get("applied_date", "") or "").strip()

    print(f"Marked as applied: {company} - {title}")
    print(f"Applied date: {applied_date}")


if __name__ == "__main__":
    main()

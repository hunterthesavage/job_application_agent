import sys

from services.cover_letters import generate_cover_letter_for_job_id


def main() -> None:
    args = sys.argv[1:]

    if not args:
        print("Usage: python -m src.generate_cover_letter <job_id>")
        raise SystemExit(1)

    try:
        job_id = int(args[0])
    except ValueError:
        print("Job id must be an integer.")
        raise SystemExit(1)

    result = generate_cover_letter_for_job_id(job_id)
    print(f"Generating cover letter for job {result['job_id']}: {result['company']} - {result['title']}")
    print(f"Saved cover letter to: {result['output_path']}")


if __name__ == "__main__":
    main()

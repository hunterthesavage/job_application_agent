import json
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

try:
    from ddgs import DDGS
except ImportError:
    DDGS = None


GREENHOUSE_BOARD_FILE = "greenhouse_boards.txt"
LEVER_BOARD_FILE = "lever_boards.txt"
OUTPUT_FILE = "job_urls.txt"
RUNTIME_SETTINGS_FILE = "runtime_settings.json"

ALLOWED_JOB_DOMAINS = [
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "ashbyhq.com",
    "smartrecruiters.com",
]

DEFAULT_GOOGLE_DISCOVERY_QUERIES = [
    '("VP" OR "Vice President" OR "Head of" OR "Chief") ("Technology" OR "IT" OR "Information" OR "Digital" OR "Engineering" OR "Platform") "remote" (site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com OR site:smartrecruiters.com)',
    '("Head of AI" OR "VP AI" OR "Chief AI Officer" OR "AI Strategy" OR "Applied AI") "remote" (site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com)',
    '("Chief Information Officer" OR "CIO" OR "Chief Technology Officer" OR "CTO") "remote" (site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:smartrecruiters.com)',
    '("VP" OR "Head of") ("Platform" OR "Infrastructure" OR "Enterprise Systems" OR "Enterprise Applications" OR "Cloud") "remote" (site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com)',
    '("VP" OR "Head of") ("Data" OR "Analytics" OR "Machine Learning") "remote" (site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com)',
    '("VP" OR "Head of" OR "Chief Digital Officer") ("Transformation" OR "Digital" OR "Technology Strategy") "remote" (site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com)',
    '("VP" OR "Chief" OR "Head of") ("Technology" OR "Engineering" OR "IT") ("remote" OR "United States") (site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com)',
]

SENIORITY_TERMS = [
    "vp",
    "vice president",
    "svp",
    "senior vice president",
    "head of",
    "chief",
    "cto",
    "cio",
    "coo",
]


def safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_csv_text(value: str) -> list[str]:
    text = safe_text(value)
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def load_runtime_settings() -> dict[str, str]:
    path = Path(RUNTIME_SETTINGS_FILE)

    if not path.exists():
        print(f"{RUNTIME_SETTINGS_FILE} not found, using default discovery behavior.")
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): safe_text(v) for k, v in data.items()}
    except Exception as exc:
        print(f"Failed to read {RUNTIME_SETTINGS_FILE}: {exc}")

    return {}


def load_board_urls(file_path: str) -> list[str]:
    urls = []

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)
    except FileNotFoundError:
        pass

    return urls


def title_has_target_seniority(title: str) -> bool:
    lowered = title.lower()
    return any(term in lowered for term in SENIORITY_TERMS)


def title_matches_settings(title: str, settings: dict[str, str]) -> bool:
    target_titles = parse_csv_text(settings.get("target_titles", ""))
    if not target_titles:
        return title_has_target_seniority(title)

    lowered = title.lower()
    return any(term.lower() in lowered for term in target_titles)


def build_google_discovery_queries(settings: dict[str, str]) -> list[str]:
    target_titles = parse_csv_text(settings.get("target_titles", ""))
    preferred_locations = parse_csv_text(settings.get("preferred_locations", ""))
    include_keywords = parse_csv_text(settings.get("include_keywords", ""))
    remote_only = settings.get("remote_only", "false").lower() == "true"

    if not target_titles and not preferred_locations and not include_keywords:
        return DEFAULT_GOOGLE_DISCOVERY_QUERIES

    queries = []
    site_block = "(site:greenhouse.io OR site:lever.co OR site:myworkdayjobs.com OR site:ashbyhq.com OR site:smartrecruiters.com)"

    title_terms = target_titles or [
        "VP Technology",
        "VP IT",
        "CIO",
        "CTO",
        "Head of Technology",
    ]

    location_terms = preferred_locations or (["remote"] if remote_only else ["remote", "United States"])

    keyword_block = ""
    if include_keywords:
        keyword_block = " ".join(f'"{keyword}"' for keyword in include_keywords[:3])

    for title in title_terms[:8]:
        for location in location_terms[:4]:
            parts = [f'"{title}"', f'"{location}"']
            if keyword_block:
                parts.append(keyword_block)
            parts.append(site_block)
            queries.append(" ".join(parts))

    # Keep some breadth
    if remote_only and not preferred_locations:
        queries.append(
            f'("VP" OR "Vice President" OR "Head of" OR "Chief") ("Technology" OR "IT" OR "Digital" OR "Platform") "remote" {site_block}'
        )

    return list(dict.fromkeys(queries))


def discover_greenhouse_jobs(board_url: str, settings: dict[str, str]) -> list[str]:
    response = requests.get(
        board_url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        title = a_tag.get_text(" ", strip=True)

        if not href or not title:
            continue

        full_url = urljoin(board_url, href)

        if "/jobs/" not in full_url:
            continue

        if not title_matches_settings(title, settings):
            continue

        links.append(full_url)

    return list(dict.fromkeys(links))


def discover_lever_jobs(board_url: str, settings: dict[str, str]) -> list[str]:
    response = requests.get(
        board_url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        title = a_tag.get_text(" ", strip=True)

        if not href or not title:
            continue

        full_url = urljoin(board_url, href)

        if not title_matches_settings(title, settings):
            continue

        if "/jobs/" in full_url:
            links.append(full_url)
            continue

        board_slug = board_url.replace("https://jobs.lever.co/", "").strip("/")
        if board_slug and f"jobs.lever.co/{board_slug}/" in full_url:
            links.append(full_url)

    return list(dict.fromkeys(links))


def is_allowed_job_url(url: str) -> bool:
    lowered = url.lower()
    return any(domain in lowered for domain in ALLOWED_JOB_DOMAINS)


def extract_result_url(result: dict) -> str:
    for key in ["href", "url", "link"]:
        value = result.get(key, "")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def discover_google_style_urls(settings: dict[str, str]) -> list[str]:
    if DDGS is None:
        print("DDGS package not installed, skipping Google-style discovery.")
        return []

    discovered = []
    queries = build_google_discovery_queries(settings)

    with DDGS() as ddgs:
        for query in queries:
            print(f"Searching query: {query}")

            try:
                results = list(ddgs.text(query, max_results=40))
                print(f"Search results returned: {len(results)}")

                for result in results:
                    url = extract_result_url(result)
                    title = str(result.get("title", "")).strip()

                    if not url:
                        continue

                    if not is_allowed_job_url(url):
                        continue

                    if title and not title_matches_settings(title, settings):
                        continue

                    discovered.append(url)
            except Exception as exc:
                print(f"Search failed for query '{query}': {exc}")

    return list(dict.fromkeys(discovered))


def load_existing_output_urls(file_path: str) -> set[str]:
    existing = set()

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line:
                    existing.add(line)
    except FileNotFoundError:
        pass

    return existing


def append_urls_to_output(file_path: str, urls: list[str]) -> int:
    existing = load_existing_output_urls(file_path)
    new_urls = [url for url in urls if url not in existing]

    if not new_urls:
        return 0

    with open(file_path, "a", encoding="utf-8") as file:
        for url in new_urls:
            file.write(url + "\n")

    return len(new_urls)


def main() -> None:
    settings = load_runtime_settings()

    greenhouse_board_urls = load_board_urls(GREENHOUSE_BOARD_FILE)
    lever_board_urls = load_board_urls(LEVER_BOARD_FILE)

    greenhouse_discovered = []
    lever_discovered = []
    search_discovered = []

    for board_url in greenhouse_board_urls:
        print(f"Checking Greenhouse board: {board_url}")

        try:
            urls = discover_greenhouse_jobs(board_url, settings)
            print(f"Found Greenhouse jobs: {len(urls)}")
            greenhouse_discovered.extend(urls)
        except Exception as exc:
            print(f"Failed on {board_url}: {exc}")

    for board_url in lever_board_urls:
        print(f"Checking Lever board: {board_url}")

        try:
            urls = discover_lever_jobs(board_url, settings)
            print(f"Found Lever jobs: {len(urls)}")
            lever_discovered.extend(urls)
        except Exception as exc:
            print(f"Failed on {board_url}: {exc}")

    search_discovered = discover_google_style_urls(settings)

    all_discovered = greenhouse_discovered + lever_discovered + search_discovered
    unique_urls = list(dict.fromkeys(all_discovered))
    added_count = append_urls_to_output(OUTPUT_FILE, unique_urls)

    print("\nDiscovery complete.")
    print(f"Greenhouse URLs found: {len(dict.fromkeys(greenhouse_discovered))}")
    print(f"Lever URLs found: {len(dict.fromkeys(lever_discovered))}")
    print(f"Search URLs found: {len(dict.fromkeys(search_discovered))}")
    print(f"Total unique URLs found: {len(unique_urls)}")
    print(f"New URLs added to {OUTPUT_FILE}: {added_count}")


if __name__ == "__main__":
    main()
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BOARD_FILE = "greenhouse_boards.txt"
OUTPUT_FILE = "job_urls.txt"

TARGET_KEYWORDS = [
    "vp",
    "vice president",
    "cio",
    "chief information officer",
    "coo",
    "chief operating officer",
    "cto",
    "chief technology officer",
    "head of ai",
    "head of platform",
    "chief digital officer",
    "technology",
    "it",
    "platform",
    "ai",
]


def load_board_urls(file_path: str) -> list[str]:
    urls = []

    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)

    return urls

def load_lever_board_urls(file_path: str) -> list[str]:
    return load_board_urls(file_path)

def title_looks_relevant(title: str) -> bool:
    lowered = title.lower()
    return any(keyword in lowered for keyword in TARGET_KEYWORDS)


def discover_greenhouse_jobs(board_url: str) -> list[str]:
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

        links.append(full_url)

    return list(dict.fromkeys(links))

def discover_lever_jobs(board_url: str) -> list[str]:
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

        if not href:
            continue

        full_url = urljoin(board_url, href)

        # Lever job URLs typically look like /company/jobid
        if board_url.replace("https://jobs.lever.co/", "") in full_url:
            links.append(full_url)

    return list(dict.fromkeys(links))

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
    lever_board_urls = load_lever_board_urls("lever_boards.txt")
    board_urls = load_board_urls(BOARD_FILE)

    all_discovered = []

    for board_url in board_urls:
        print(f"Checking board: {board_url}")

        try:
            urls = discover_greenhouse_jobs(board_url)
            print(f"Found relevant jobs: {len(urls)}")
            all_discovered.extend(urls)
        except Exception as exc:
            print(f"Failed on {board_url}: {exc}")

    unique_urls = list(dict.fromkeys(all_discovered))
    added_count = append_urls_to_output(OUTPUT_FILE, unique_urls)

    for board_url in lever_board_urls:
    	print(f"Checking Lever board: {board_url}")

    	try:
            urls = discover_lever_jobs(board_url)
            print(f"Found jobs: {len(urls)}")
            all_discovered.extend(urls)
        except Exception as exc:
            print(f"Failed on {board_url}: {exc}")

    print("\nDiscovery complete.")
    print(f"Total relevant URLs found: {len(unique_urls)}")
    print(f"New URLs added to {OUTPUT_FILE}: {added_count}")


if __name__ == "__main__":
    main()
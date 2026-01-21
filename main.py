import os
import sys
from urllib.parse import urlparse

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from html-scrape.py (hyphenated filename requires importlib)
import importlib.util
spec = importlib.util.spec_from_file_location("html_scrape", os.path.join(os.path.dirname(os.path.abspath(__file__)), "html-scrape.py"))
html_scrape = importlib.util.module_from_spec(spec)
spec.loader.exec_module(html_scrape)
scrape_wikipedia_links = html_scrape.scrape_wikipedia_links

from embeddings import EmbeddingStore


class WikiRacer:
    def __init__(self, db_path: str = None):
        self.embedding_store = EmbeddingStore(db_path)
        self.path_history = []
        self.visited_urls = set()
        self.max_depth = 20

    def _get_page_name_from_url(self, url: str) -> str:
        """Extract the page name from a Wikipedia URL."""
        parsed = urlparse(url)
        path = parsed.path
        if '/wiki/' in path:
            return path.split('/wiki/')[-1].replace('_', ' ')
        return url

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison (lowercase path)."""
        parsed = urlparse(url)
        return parsed.path.lower()

    def _scrape_and_embed(self, url: str) -> tuple:
        """
        Scrape a Wikipedia page and store embeddings.

        Returns:
            tuple: (links_data, collection) or (None, None) if failed
        """
        print(f"\nScraping: {url}")
        data = scrape_wikipedia_links(url)

        if not data or not data['links']:
            print("Failed to scrape or no links found.")
            return None, None

        print(f"Found {len(data['links'])} links on '{data['source_page']}'")

        collection = self.embedding_store.store_links(data['links'])
        return data, collection

    def _check_for_target(self, links: list, target_url: str) -> dict:
        """Check if the target URL is in the current page's links."""
        target_path = self._normalize_url(target_url)

        for link in links:
            if self._normalize_url(link['url']) == target_path:
                return link
        return None

    def _log_step(self, step_num: int, name: str, url: str, is_final: bool = False):
        """Log a step in the path."""
        self.path_history.append({'step': step_num, 'name': name, 'url': url})

        if is_final:
            print(f"\n{'='*60}")
            print(f"  STEP {step_num} (FINAL): {name}")
            print(f"  URL: {url}")
            print(f"{'='*60}")
        else:
            print(f"\n  STEP {step_num}: {name}")
            print(f"  URL: {url}")

    def race(self, start_url: str, end_url: str) -> bool:
        """
        Navigate from start Wikipedia page to end page using semantic similarity.

        Args:
            start_url: Starting Wikipedia URL
            end_url: Target Wikipedia URL

        Returns:
            bool: True if target was reached, False otherwise
        """
        self.path_history = []
        self.visited_urls = set()
        target_name = self._get_page_name_from_url(end_url)

        print("\n" + "="*60)
        print("  WIKIRACER - Semantic Wikipedia Navigator")
        print("="*60)
        print(f"\n  START: {start_url}")
        print(f"  TARGET: {end_url}")
        print(f"  Target page name: '{target_name}'")
        print("="*60)

        current_url = start_url
        step = 0

        # Log and mark starting point as visited
        start_name = self._get_page_name_from_url(start_url)
        self._log_step(step, start_name, start_url)
        self.visited_urls.add(self._normalize_url(start_url))

        while step < self.max_depth:
            step += 1

            # Scrape current page and create embeddings
            data, collection = self._scrape_and_embed(current_url)

            if data is None:
                print(f"\nFailed to process page. Stopping at step {step}.")
                return False

            links = data['links']

            # Check if target is directly linked
            target_link = self._check_for_target(links, end_url)
            if target_link:
                self._log_step(step, target_link['name'], target_link['url'], is_final=True)
                self._print_summary(True)
                return True

            # Find the closest unvisited link semantically
            # Convert visited_urls (normalized paths) to full URLs for comparison
            visited_full_urls = set()
            for link in links:
                if self._normalize_url(link['url']) in self.visited_urls:
                    visited_full_urls.add(link['url'])

            matches = self.embedding_store.find_closest(
                target_name,
                collection,
                n_results=1,
                exclude_urls=visited_full_urls
            )

            if not matches:
                print(f"\nNo unvisited links found. Stopping at step {step}.")
                self._print_summary(False)
                return False

            closest = matches[0]
            print(f"\n  Closest match to '{target_name}': '{closest['name']}' (distance: {closest['distance']:.4f})")

            # Mark as visited and move to the closest link
            self.visited_urls.add(self._normalize_url(closest['url']))
            self._log_step(step, closest['name'], closest['url'])
            current_url = closest['url']

            # Check if we've reached the target
            if self._normalize_url(current_url) == self._normalize_url(end_url):
                self._print_summary(True)
                return True

        print(f"\nMax depth ({self.max_depth}) reached without finding target.")
        self._print_summary(False)
        return False

    def _print_summary(self, success: bool):
        """Print a summary of the path taken."""
        print("\n" + "="*60)
        print("  PATH SUMMARY")
        print("="*60)

        for entry in self.path_history:
            marker = ">>>" if entry['step'] == len(self.path_history) - 1 else "   "
            print(f"{marker} Step {entry['step']}: {entry['name']}")
            print(f"        {entry['url']}")

        print("\n" + "="*60)
        if success:
            print(f"  SUCCESS! Reached target in {len(self.path_history) - 1} steps.")
        else:
            print(f"  FAILED. Could not reach target in {len(self.path_history) - 1} steps.")
        print("="*60 + "\n")


def validate_wikipedia_url(url: str) -> bool:
    """Validate that the URL is a Wikipedia article URL."""
    if not url:
        return False
    parsed = urlparse(url)
    return 'wikipedia.org' in parsed.netloc and '/wiki/' in parsed.path


def main():
    print("\n" + "="*60)
    print("  WIKIRACER - Find a path between Wikipedia pages")
    print("="*60 + "\n")

    # Get start URL
    while True:
        start_url = input("Enter the START Wikipedia URL: ").strip()
        if validate_wikipedia_url(start_url):
            break
        print("Invalid Wikipedia URL. Please enter a valid URL (e.g., https://en.wikipedia.org/wiki/Potato)")

    # Get end URL
    while True:
        end_url = input("Enter the TARGET Wikipedia URL: ").strip()
        if validate_wikipedia_url(end_url):
            break
        print("Invalid Wikipedia URL. Please enter a valid URL (e.g., https://en.wikipedia.org/wiki/Computer)")

    # Run the racer
    racer = WikiRacer()
    racer.race(start_url, end_url)


if __name__ == "__main__":
    main()

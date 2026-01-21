import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def scrape_wikipedia_links(url):
    """
    Scrapes a Wikipedia page and extracts all links.

    Args:
        url (str): The Wikipedia page URL to scrape

    Returns:
        dict: A dictionary containing the page title and list of links
    """
    try:
        headers = {
            'User-Agent': 'WikiRacer/1.0 (Educational Project)'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        page_title = soup.find('h1', class_='firstHeading')
        title = page_title.text if page_title else "Unknown"

        content = soup.find('div', {'id': 'mw-content-text'})

        if not content:
            print("Could not find main content area")
            return None

        links = []
        seen_urls = set()

        for link in content.find_all('a', href=True):
            href = link['href']

            if href.startswith('/wiki/') and ':' not in href:
                full_url = urljoin('https://en.wikipedia.org', href)
                link_text = link.get_text(strip=True)

                if full_url not in seen_urls and link_text:
                    seen_urls.add(full_url)
                    links.append({
                        'name': link_text,
                        'url': full_url
                    })

        return {
            'source_page': title,
            'source_url': url,
            'total_links': len(links),
            'links': links
        }

    except requests.exceptions.RequestException as e:
        print(f"Error fetching the page: {e}")
        return None
    except Exception as e:
        print(f"Error processing the page: {e}")
        return None

import requests
from bs4 import BeautifulSoup
import json
import sys
from urllib.parse import urljoin, urlparse

def scrape_wikipedia_links(url):
    """
    Scrapes a Wikipedia page and extracts all links.
    
    Args:
        url (str): The Wikipedia page URL to scrape
        
    Returns:
        dict: A dictionary containing the page title and list of links
    """
    try:
        # Send GET request to the Wikipedia page
        headers = {
            'User-Agent': 'WikiRacer/1.0 (Educational Project)'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Get the page title
        page_title = soup.find('h1', class_='firstHeading')
        title = page_title.text if page_title else "Unknown"
        
        # Find the main content area (to avoid navigation/sidebar links)
        content = soup.find('div', {'id': 'mw-content-text'})
        
        if not content:
            print("Could not find main content area")
            return None
        
        # Extract all links from the content area
        links = []
        seen_urls = set()  # To avoid duplicates
        
        # Find all <a> tags in the content
        for link in content.find_all('a', href=True):
            href = link['href']
            
            # Filter for Wikipedia article links only
            # Skip external links, citations, edit links, etc.
            if href.startswith('/wiki/') and ':' not in href:
                # Convert relative URL to absolute URL
                full_url = urljoin('https://en.wikipedia.org', href)
                
                # Get link text
                link_text = link.get_text(strip=True)
                
                # Avoid duplicates and empty link texts
                if full_url not in seen_urls and link_text:
                    seen_urls.add(full_url)
                    links.append({
                        'name': link_text,
                        'url': full_url
                    })
        
        # Create the result dictionary
        result = {
            'source_page': title,
            'source_url': url,
            'total_links': len(links),
            'links': links
        }
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the page: {e}")
        return None
    except Exception as e:
        print(f"Error processing the page: {e}")
        return None


def save_to_json(data, filename='wikipedia_links.json'):
    """
    Saves the extracted data to a JSON file.
    
    Args:
        data (dict): The data to save
        filename (str): The output filename
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Successfully saved links to {filename}")
    except Exception as e:
        print(f"Error saving to JSON: {e}")


def main():
    # Check if URL is provided as command line argument
    if len(sys.argv) > 1:
        wiki_url = sys.argv[1]
    else:
        # Default example URL
        wiki_url = input("Enter Wikipedia page URL: ").strip()
    
    # Validate it's a Wikipedia URL
    if 'wikipedia.org' not in wiki_url:
        print("Please provide a valid Wikipedia URL")
        return
    
    print(f"Scraping: {wiki_url}")
    print("This may take a few seconds...")
    
    # Scrape the links
    data = scrape_wikipedia_links(wiki_url)
    
    if data:
        print(f"\nFound {data['total_links']} links on the page: {data['source_page']}")
        
        # Display first 5 links as preview
        print("\nFirst 5 links:")
        for i, link in enumerate(data['links'][:5], 1):
            print(f"{i}. {link['name']} -> {link['url']}")
        
        # Save to JSON file
        output_file = 'wikipedia_links.json'
        save_to_json(data, output_file)
        
        # Also print the full JSON to console
        print(f"\nFull JSON output saved to {output_file}")
    else:
        print("Failed to scrape the page")


if __name__ == "__main__":
    main()
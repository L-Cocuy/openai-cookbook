"""A module for web crawling and scraping."""

import os
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

def get_same_domain_links(url:str) -> set:
    """Get all hyperlinks from a URL that are on the same domain.

    Args:
        url (str): The URL to crawl.

    Returns:
        set: A set of all hyperlinks from the URL that are on the same domain.
    """
    # Get the domain name
    partial_domain = urlparse(url).netloc

    # Create full domain name
    if not partial_domain.startswith('http'):
        full_domain = 'https://' + partial_domain

    # Send a GET request to the URL
    response = requests.get(url, timeout=5)

    # Create a BeautifulSoup object
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find all hyperlinks in the HTML
    links = soup.find_all('a')

    # Extract the href attributes from each hyperlink
    hrefs = [link.attrs.get('href') for link in links]

    # Filter out Nones, non-strings, and links that are empty strings
    hrefs = [link for link in hrefs if link and isinstance(link, str) and link != '']

    # Filter out any links that don't start with the domain name
    same_domain_links = [link for link in hrefs if link and link.startswith('/') or partial_domain in link]

    # Prepend the full domain, including https, to each link if it's missing
    same_domain_links = [link if link.startswith('http') else full_domain + link for link in same_domain_links]

    # Return the set of links
    return set(same_domain_links), full_domain

def crawl_and_scrape(links: list) -> None:
    """Crawl and scrape all links. Save scraped data to text files. 

    Args:
        links (list): A list of links to crawl and scrape.
    """
    # If the text directory doesn't exist, create it 
    if not os.path.exists('text/'):
        os.mkdir('text/')
      
    # Ensure directory is empty
    for file in os.listdir("text/"):
        os.remove("text/"+file)

    # Loop through each link
    for link in links:
       # Send a Get request to the link
        response = requests.get(link, timeout=5)

        # Create a BeautifulSoup object
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract the text of the HTML document
        text = soup.get_text()

        # Remove leading and trailing whitespace
        text = text.strip()

        # Remove all newlines or extra whitespace
        text=' '.join(text.split())

        # Write the text to a file
        with open('text/'+link.replace("/", "_")+".txt", 'w', encoding='utf-8') as f:
            f.write(text)
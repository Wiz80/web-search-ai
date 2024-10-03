import logging
import re
import os
from urllib.parse import urlparse

def save_scraped_content(url, content):

    parsed_url = urlparse(url)
    site_name = parsed_url.netloc.replace("www.", "")

    # Define the file name using the site name
    file_name = f"{site_name}_scraped_content.txt"

    # Ensure the directory exists where the file will be saved
    if not os.path.exists("scraped_sites"):
        os.makedirs("scraped_sites")

    # Full path to the file
    file_path = os.path.join("scraped_sites", file_name)

    # Write the content to the file, including the URL as a header
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"\n\nURL: {url}\n")
        f.write(f"Content:\n{content}\n")
        f.write("-" * 80)  # Separator between pages for readability
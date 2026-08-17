import json
import re
import requests
from bs4 import BeautifulSoup  # Make sure to pip install beautifulsoup4

def fetch_webnovel_metadata(novel_url_or_id):
    """
    Extracts book metadata from Webnovel. Try AJAX endpoint first; 
    falls back to HTML parsing if blocked.
    """
    # 1. Standardize the novel ID and URL
    if "webnovel.com" in novel_url_or_id:
        match = re.search(r"book/.*_(\d+)", novel_url_or_id)
        if not match:
            print("❌ Could not extract Novel ID from the provided URL.")
            return None
        novel_id = match.group(1)
        url = novel_url_or_id
    else:
        novel_id = str(novel_url_or_id)
        url = f"https://webnovel.com{novel_id}"

    # Anti-fingerprint headers mimicking a real Chrome user session
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }

    print(f"🔄 Attempting to fetch Webnovel data for ID: {novel_id}...")

    # METHOD 1: Try the hidden API endpoint first
    api_url = "https://webnovel.com"
    params = {"bookId": novel_id, "_csrfToken": ""}
    
    try:
        api_headers = headers.copy()
        api_headers["Referer"] = url
        res = requests.get(api_url, params=params, headers=api_headers, timeout=10)
        
        # Verify if the response is actually JSON before calling .json()
        if res.status_code == 200 and "application/json" in res.headers.get("Content-Type", ""):
            data = res.json()
            if data.get("code") == 0:
                print("✅ Success using internal API endpoint!")
                book_info = data.get("data", {}).get("bookInfo", {})
                status_code = book_info.get("type", 1)
                return {
                    "id": novel_id,
                    "title": book_info.get("bookName"),
                    "author": book_info.get("authorName"),
                    "status": "Completed" if status_code == 2 else "Ongoing",
                    "synopsis": book_info.get("synopsis"),
                    "tags": [t.get("tagName") for t in book_info.get("tagInfo", [])],
                    "cover_image": f"https://webnovel.com{novel_id}/300/300.jpg",
                    "url": url
                }
    except Exception:
        pass # If API method fails, silently proceed to fallback

    # METHOD 2: Fallback to HTML Web Scraping if API fails or blocks
    print("⚠️ API endpoint blocked or changed. Falling back to direct HTML parsing...")
    try:
        html_res = requests.get(url, headers=headers, timeout=10)
        if html_res.status_code != 200:
            print(f"❌ Both methods blocked by Webnovel. Status Code: {html_res.status_code}")
            return None
            
        soup = BeautifulSoup(html_res.text, "html.parser")
        
        # Read fields directly out of page elements or page JSON data scripts
        title = soup.find("h1", class_=re.compile(r"book-name|title"))
        author = soup.find("address", class_=re.compile(r"author|profile"))
        synopsis = soup.find("div", class_=re.compile(r"synopsis|desc"))
        
        # Try to find tags inside lists
        tag_elements = soup.find_all("a", href=re.compile(r"/tag/"))
        tags = list(set([t.get_text(strip=True) for t in tag_elements]))

        # Simple status lookups
        status = "Ongoing"
        if "Completed" in html_res.text or "completed" in html_res.text.lower():
            status = "Completed"

        return {
            "id": novel_id,
            "title": title.get_text(strip=True) if title else "Unknown Title",
            "author": author.get_text(strip=True).replace("Author:", "").strip() if author else "Unknown Author",
            "status": status,
            "synopsis": synopsis.get_text(strip=True) if synopsis else "No synopsis found.",
            "tags": tags,
            "cover_image": f"https://webnovel.com{novel_id}/300/300.jpg",
            "url": url
        }

    except Exception as e:
        print(f"❌ Failed completely: {e}")
        return None

# === Try running it again ===
if __name__ == "__main__":
    target_novel = "https://www.webnovel.com/book/reverend-insanity_7996858406002505"
    result = fetch_webnovel_metadata(target_novel)
    if result:
        print("\n📚 Extracted Metadata:")
        print(json.dumps(result, indent=4))

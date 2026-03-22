"""
URL crawling and content extraction service.
"""
import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from typing import Optional


async def crawl_url(url: str, timeout: int = 30) -> dict:
    """
    Crawl a URL and extract its main text content.

    Args:
        url: The URL to crawl
        timeout: Request timeout in seconds

    Returns:
        Dict with 'title', 'content', 'url', 'word_count', 'error' keys
    """
    result = {
        "url": url,
        "title": "",
        "content": "",
        "word_count": 0,
        "error": None,
    }

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "AI-Knowledge-System/1.0 (Educational Crawling Bot)",
            },
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title
        title_tag = soup.find("title")
        result["title"] = title_tag.get_text(strip=True) if title_tag else url

        # Remove unwanted elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        # Try to find main content area
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find(class_=lambda x: x and ("content" in x.lower() or "main" in x.lower()))
            or soup.find("body")
            or soup
        )

        # Convert HTML to markdown text
        result["content"] = md(str(main_content), heading_style="ATX")

        # Clean up whitespace
        lines = [line.strip() for line in result["content"].split("\n")]
        result["content"] = "\n".join(line for line in lines if line)

        # Count words
        result["word_count"] = len(result["content"].split())

    except httpx.TimeoutException:
        result["error"] = f"Request timed out after {timeout}s"
    except httpx.HTTPStatusError as e:
        result["error"] = f"HTTP error: {e.response.status_code}"
    except Exception as e:
        result["error"] = f"Crawling error: {str(e)}"

    return result


async def crawl_multiple_urls(urls: list[str]) -> list[dict]:
    """
    Crawl multiple URLs.

    Args:
        urls: List of URLs to crawl

    Returns:
        List of crawl result dicts
    """
    import asyncio

    results = []
    for url in urls:
        result = await crawl_url(url)
        results.append(result)

    return results

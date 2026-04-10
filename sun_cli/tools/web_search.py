"""Web search tool using DuckDuckGo (free, no API key required)."""

import base64
import re
import urllib.parse
from dataclasses import dataclass
from typing import List, Optional

import httpx

from . import ToolResult


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    href: str
    body: str


class DuckDuckGoSearch:
    """DuckDuckGo search client."""
    
    BASE_URL = "https://html.duckduckgo.com/html/"
    INSTANT_URL = "https://api.duckduckgo.com/"
    BING_JINA_URL = "https://r.jina.ai/http://www.bing.com/search"
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    
    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Search DuckDuckGo and return results.
        
        Args:
            query: Search query
            max_results: Maximum number of results (default: 5)
            
        Returns:
            List of SearchResult
        """
        try:
            # First try instant answer API
            instant = await self._get_instant_answer(query)
            if instant:
                return [instant]
            
            # Fall back to HTML scraping
            results = await self._search_html(query, max_results)
            if results:
                return results

            # Final fallback for regions where DDG HTML blocks/breaks.
            return await self._search_bing_via_jina(query, max_results)
        except Exception as e:
            return []
    
    async def _get_instant_answer(self, query: str) -> Optional[SearchResult]:
        """Try to get instant answer from DuckDuckGo."""
        try:
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            }
            
            response = await self.client.get(self.INSTANT_URL, params=params)
            
            if response.status_code != 200:
                return None
            
            data = response.json()
            
            # Check for abstract text
            abstract = data.get("AbstractText", "")
            if abstract:
                return SearchResult(
                    title=data.get("Heading", query),
                    href=data.get("AbstractURL", ""),
                    body=abstract,
                )
            
            # Check for answer
            answer = data.get("Answer", "")
            if answer:
                return SearchResult(
                    title=f"Answer: {query}",
                    href="",
                    body=answer,
                )
            
            return None
        except Exception:
            return None
    
    async def _search_html(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Search using DuckDuckGo HTML interface."""
        try:
            params = {
                "q": query,
                # Improve Chinese query relevance/stability.
                "kl": "cn-zh",
            }
            
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html",
                "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            }
            
            response = await self.client.get(
                self.BASE_URL,
                params=params,
                headers=headers,
            )
            
            if response.status_code != 200:
                return []
            
            return self._parse_html_results(response.text, max_results)
        except Exception:
            return []
    
    def _parse_html_results(self, html: str, max_results: int) -> List[SearchResult]:
        """Parse search results from DuckDuckGo HTML."""
        results = []
        
        # Parse result cards. DuckDuckGo HTML can vary between <a>/<div> snippets.
        result_blocks = re.findall(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>(.*?)</div>\s*</div>',
            html,
            re.DOTALL | re.IGNORECASE,
        )
        
        for href, title_html, tail_html in result_blocks:
            if len(results) >= max_results:
                break

            snippet_match = re.search(
                r'<(?:a|div|span|p)[^>]+class="result__snippet"[^>]*>(.*?)</(?:a|div|span|p)>',
                tail_html,
                re.DOTALL | re.IGNORECASE,
            )
            snippet_html = snippet_match.group(1) if snippet_match else ""

            # Clean up HTML entities
            title = self._clean_html(title_html)
            snippet = self._clean_html(snippet_html)
            
            # Skip ad results
            if "duckduckgo.com/y.js" in href or "duckduckgo.com/l/?" in href:
                continue
            
            # Handle redirect URLs
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = "https://duckduckgo.com" + href
            
            results.append(SearchResult(
                title=title,
                href=href,
                body=snippet,
            ))
        
        return results
    
    def _clean_html(self, html: str) -> str:
        """Remove HTML tags and entities."""
        # Remove tags
        text = re.sub(r'<[^>]+>', '', html)
        # Decode common entities
        text = text.replace("&quot;", '"')
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&#39;", "'")
        text = text.replace("&nbsp;", " ")
        # Collapse whitespace
        text = ' '.join(text.split())
        return text.strip()

    def _decode_bing_redirect(self, url: str) -> str:
        """Decode Bing redirect URL to original target when possible."""
        try:
            parsed = urllib.parse.urlparse(url)
            if "bing.com" not in parsed.netloc:
                return url

            params = urllib.parse.parse_qs(parsed.query)
            raw_u = (params.get("u") or [""])[0]
            if not raw_u:
                return url

            payload = raw_u[2:] if raw_u.startswith("a1") else raw_u
            padding = "=" * (-len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload + padding).decode("utf-8", errors="ignore")
            if decoded.startswith("http://") or decoded.startswith("https://"):
                return decoded
        except Exception:
            pass
        return url

    async def _search_bing_via_jina(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Fallback search using jina.ai markdown snapshot of Bing SERP."""
        try:
            response = await self.client.get(self.BING_JINA_URL, params={"q": query})
            if response.status_code != 200:
                return []

            matches = re.findall(
                r"^## \[(.*?)\]\((https?://[^\s)]+)\)",
                response.text,
                flags=re.MULTILINE,
            )
            results: List[SearchResult] = []
            seen_urls = set()

            for title, href in matches:
                if len(results) >= max_results:
                    break

                normalized_href = self._decode_bing_redirect(href.strip())
                if normalized_href in seen_urls:
                    continue
                seen_urls.add(normalized_href)

                results.append(
                    SearchResult(
                        title=title.strip(),
                        href=normalized_href,
                        body="",
                    )
                )

            return results
        except Exception:
            return []
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


async def web_search(query: str, max_results: int = 5) -> ToolResult:
    """Search the web using DuckDuckGo.
    
    Args:
        query: Search query
        max_results: Maximum number of results (1-10)
        
    Returns:
        ToolResult with search results
    """
    if not query or not query.strip():
        return ToolResult(success=False, content="", error="Query cannot be empty")
    
    # Limit max_results
    max_results = max(1, min(10, int(max_results) if max_results else 5))
    
    searcher = DuckDuckGoSearch()
    
    try:
        results = await searcher.search(query.strip(), max_results)
        await searcher.close()
        
        if not results:
            return ToolResult(
                success=True,
                content="No results found. Try a different query."
            )
        
        # Format results
        lines = [f"Search results for: '{query}'\n"]
        
        for i, result in enumerate(results, 1):
            lines.append(f"{i}. {result.title}")
            if result.href:
                lines.append(f"   URL: {result.href}")
            if result.body:
                # Truncate long snippets
                snippet = result.body[:200] + "..." if len(result.body) > 200 else result.body
                lines.append(f"   {snippet}")
            lines.append("")
        
        return ToolResult(success=True, content="\n".join(lines))
        
    except Exception as e:
        return ToolResult(success=False, content="", error=f"Search failed: {str(e)}")


# Synchronous wrapper for ToolExecutor
async def web_search_async(query: str = "", max_results: int = 5) -> str:
    """Async wrapper for web search."""
    result = await web_search(query, max_results)
    if result.success:
        return result.content
    return f"Error: {result.error}"

"""Web search tool using SearxNG with Baidu as fallback."""

import re
import json
from dataclasses import dataclass
from typing import List

import httpx

from . import ToolResult
from ..logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    href: str
    body: str


class SearxNGSearch:
    """SearxNG search client with automatic failover and Baidu fallback."""

    SEARXNG_INSTANCES = [
        "https://search.uselessthings.top",
        "https://search.bibiboy.eu.org",
        "https://searx.be",
    ]

    PROXY_URL = "http://localhost:7897"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            timeout=timeout,
            proxy=self.PROXY_URL,
            follow_redirects=True
        )
        self._current_instance = 0

    async def search(self, query: str, time_range: str = "day", limit: int = 5) -> List[SearchResult]:
        """Search using SearxNG first, fallback to Baidu if needed.

        Args:
            query: Search query
            time_range: Time range filter (day/week/month/year), default: day
            limit: Maximum number of results (default: 5)

        Returns:
            List of SearchResult
        """
        logger.debug(f"开始搜索: '{query}', 时间范围: {time_range}, 限制: {limit}")
        
        results = await self._search_searxng(query, time_range, limit)
        if results:
            logger.debug(f"SearxNG搜索成功，找到 {len(results)} 个结果")
            return results

        logger.debug("SearxNG搜索失败，尝试使用百度作为备选")
        results = await self._search_baidu(query, limit)
        if results:
            logger.debug(f"百度搜索成功，找到 {len(results)} 个结果")
        else:
            logger.debug("百度搜索也失败，返回空结果")
        return results

    async def _search_searxng(self, query: str, time_range: str, limit: int) -> List[SearchResult]:
        """Search using SearxNG instances."""
        for attempt in range(len(self.SEARXNG_INSTANCES)):
            instance_url = self.SEARXNG_INSTANCES[self._current_instance]
            logger.debug(f"尝试SearxNG实例 {attempt+1}/{len(self.SEARXNG_INSTANCES)}: {instance_url}")

            try:
                params = {
                    "q": query,
                    "format": "json",
                    "time_range": time_range,
                    "engines": "google",
                    "limit": limit,
                }
                logger.debug(f"搜索参数: {params}")

                response = await self.client.get(instance_url, params=params)
                logger.debug(f"SearxNG响应状态码: {response.status_code}")

                if response.status_code != 200:
                    logger.warning(f"SearxNG实例 {instance_url} 返回状态码 {response.status_code}")
                    self._switch_to_next_instance()
                    continue

                data = response.json()
                logger.debug(f"SearxNG返回数据: {json.dumps(data, ensure_ascii=False)[:200]}...")
                results = self._parse_searxng_results(data, limit)
                logger.debug(f"解析到 {len(results)} 个SearxNG结果")

                if results:
                    return results

                logger.warning(f"SearxNG实例 {instance_url} 没有返回结果")
                self._switch_to_next_instance()

            except Exception as e:
                logger.error(f"SearxNG实例 {instance_url} 错误: {e}")
                self._switch_to_next_instance()
                continue

        return []

    async def _search_baidu(self, query: str, limit: int) -> List[SearchResult]:
        """Search using Baidu as fallback."""
        try:
            baidu_url = "https://www.baidu.com/s"
            params = {
                "wd": query,
                "rn": limit,
            }
            logger.debug(f"百度搜索参数: {params}")

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
            }

            response = await self.client.get(baidu_url, params=params, headers=headers)
            logger.debug(f"百度响应状态码: {response.status_code}")

            if response.status_code != 200:
                logger.warning(f"百度返回状态码 {response.status_code}")
                return []

            results = self._parse_baidu_results(response.text, limit)
            logger.debug(f"解析到 {len(results)} 个百度结果")
            return results

        except Exception as e:
            logger.error(f"百度搜索错误: {e}")
            return []

    def _switch_to_next_instance(self) -> None:
        """Switch to the next SearxNG instance in the list."""
        self._current_instance = (self._current_instance + 1) % len(self.SEARXNG_INSTANCES)

    def _parse_searxng_results(self, data: dict, limit: int) -> List[SearchResult]:
        """Parse SearxNG JSON response into SearchResult objects."""
        results = []

        raw_results = data.get("results", []) or data.get("result", [])

        for item in raw_results[:limit]:
            if isinstance(item, dict):
                title = item.get("title", "")
                url = item.get("url", "") or item.get("href", "")
                content = item.get("content", "") or item.get("description", "")

                if title and url:
                    results.append(SearchResult(
                        title=self._clean_text(title),
                        href=url,
                        body=self._clean_text(content[:300]) if content else "",
                    ))

        return results

    def _parse_baidu_results(self, html: str, limit: int) -> List[SearchResult]:
        """Parse Baidu search results from HTML."""
        results = []

        pattern = r'<h3[^>]*class="[^"]*t[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?</h3>'
        matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

        for href, title_html in matches[:limit]:
            title = self._clean_html(title_html)
            if title and href:
                results.append(SearchResult(
                    title=title,
                    href=href,
                    body="",
                ))

        return results

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean HTML tags and entities from text."""
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace("&quot;", '"')
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&#39;", "'")
        text = text.replace("&nbsp;", " ")
        text = ' '.join(text.split())
        return text.strip()

    def _clean_html(self, html: str) -> str:
        """Remove HTML tags and decode entities."""
        return self._clean_text(html)

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


DuckDuckGoSearch = SearxNGSearch

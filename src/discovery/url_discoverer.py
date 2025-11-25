"""
URL Discovery Layer

Handles discovering URLs from documentation sites using multiple strategies:
1. Sitemap.xml parsing (fastest)
2. Common documentation patterns
3. Crawl4AI recursive discovery (fallback)
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Literal
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
from fnmatch import fnmatch

import httpx
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryResult:
    """Result of URL discovery operation"""
    urls: List[str]
    method: Literal["sitemap", "patterns", "crawl", "manual"]
    total_found: int
    filtered_count: int
    error: Optional[str] = None


class URLDiscoverer:
    """Discovers URLs from documentation sites using multiple strategies"""

    def __init__(
        self,
        timeout: int = 30,
        max_crawl_depth: int = 3,
        max_urls: int = 1000
    ):
        self.timeout = timeout
        self.max_crawl_depth = max_crawl_depth
        self.max_urls = max_urls

    async def discover(
        self,
        url_pattern: str,
        method: Literal["auto", "sitemap", "crawl", "manual"] = "auto"
    ) -> DiscoveryResult:
        """
        Discover URLs using the specified method

        Args:
            url_pattern: URL or pattern (e.g., https://docs.example.com/*)
            method: Discovery method to use

        Returns:
            DiscoveryResult with discovered URLs
        """
        logger.info(f"Starting URL discovery for {url_pattern} using method: {method}")

        # Parse the pattern to get base URL
        base_url = self._extract_base_url(url_pattern)

        try:
            if method == "manual":
                # Single URL, no discovery needed
                return DiscoveryResult(
                    urls=[url_pattern],
                    method="manual",
                    total_found=1,
                    filtered_count=1
                )

            if method == "auto" or method == "sitemap":
                # Try sitemap first
                result = await self._try_sitemap(base_url, url_pattern)
                if result.urls:
                    logger.info(f"Sitemap discovery found {len(result.urls)} URLs")
                    return result

                if method == "sitemap":
                    # User specifically requested sitemap, don't fallback
                    return DiscoveryResult(
                        urls=[],
                        method="sitemap",
                        total_found=0,
                        filtered_count=0,
                        error="No sitemap found"
                    )

            if method == "auto" or method == "crawl":
                # Fallback to crawl4ai recursive discovery
                logger.info("Falling back to Crawl4AI discovery")
                result = await self._crawl4ai_discover(url_pattern)
                return result

            # Shouldn't reach here
            return DiscoveryResult(
                urls=[],
                method=method,
                total_found=0,
                filtered_count=0,
                error=f"Unknown method: {method}"
            )

        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            return DiscoveryResult(
                urls=[],
                method=method,
                total_found=0,
                filtered_count=0,
                error=str(e)
            )

    def _extract_base_url(self, url_pattern: str) -> str:
        """Extract base URL from pattern"""
        # Remove wildcard if present
        url = url_pattern.replace('*', '')
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    async def _try_sitemap(
        self,
        base_url: str,
        url_pattern: str
    ) -> DiscoveryResult:
        """Try to discover URLs from sitemap.xml"""
        sitemap_locations = [
            f"{base_url}/sitemap.xml",
            f"{base_url}/sitemap_index.xml",
            f"{base_url}/docs/sitemap.xml",
            f"{base_url}/api/sitemap.xml",
        ]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for sitemap_url in sitemap_locations:
                try:
                    logger.debug(f"Trying sitemap: {sitemap_url}")
                    response = await client.get(sitemap_url)

                    if response.status_code == 200:
                        urls = self._parse_sitemap(response.text, url_pattern)
                        if urls:
                            return DiscoveryResult(
                                urls=urls[:self.max_urls],
                                method="sitemap",
                                total_found=len(urls),
                                filtered_count=len(urls[:self.max_urls])
                            )
                except Exception as e:
                    logger.debug(f"Sitemap {sitemap_url} failed: {e}")
                    continue

        return DiscoveryResult(
            urls=[],
            method="sitemap",
            total_found=0,
            filtered_count=0
        )

    def _parse_sitemap(self, content: str, pattern: str) -> List[str]:
        """Parse sitemap XML and filter URLs by pattern"""
        try:
            root = ET.fromstring(content)
            urls = []

            # Handle both regular sitemaps and sitemap indexes
            # Check for sitemap namespace
            namespaces = {
                'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'
            }

            # Try with namespace first
            locs = root.findall('.//sm:loc', namespaces)
            if not locs:
                # Try without namespace
                locs = root.findall('.//loc')

            for loc in locs:
                url = loc.text
                if url:
                    # Check if this is a sitemap index pointing to other sitemaps
                    if url.endswith('.xml'):
                        # This might be a sitemap index, skip for now
                        # TODO: Recursively fetch sub-sitemaps
                        continue

                    # Filter by pattern
                    if self._matches_pattern(url, pattern):
                        urls.append(url)

            return urls

        except ET.ParseError as e:
            logger.error(f"Failed to parse sitemap XML: {e}")
            return []

    def _matches_pattern(self, url: str, pattern: str) -> bool:
        """Check if URL matches the given pattern"""
        # If pattern has wildcard, use fnmatch
        if '*' in pattern:
            return fnmatch(url, pattern)

        # Otherwise, check if URL starts with pattern (prefix match)
        pattern_clean = pattern.rstrip('/')
        return url.startswith(pattern_clean)

    async def _crawl4ai_discover(self, url_pattern: str) -> DiscoveryResult:
        """Use Crawl4AI to recursively discover URLs"""
        discovered_urls = set()
        base_url = self._extract_base_url(url_pattern)
        start_url = url_pattern.replace('*', '')

        # Queue for BFS crawling
        to_visit = [(start_url, 0)]  # (url, depth)
        visited = set()

        browser_config = BrowserConfig(
            headless=True,
            verbose=False
        )

        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            js_code=[
                # Wait for any dynamic content
                "await new Promise(r => setTimeout(r, 1000));"
            ]
        )

        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                while to_visit and len(discovered_urls) < self.max_urls:
                    current_url, depth = to_visit.pop(0)

                    if current_url in visited:
                        continue

                    if depth >= self.max_crawl_depth:
                        continue

                    visited.add(current_url)

                    try:
                        logger.debug(f"Crawling {current_url} (depth: {depth})")
                        result = await crawler.arun(
                            url=current_url,
                            config=crawler_config
                        )

                        if result.success:
                            # Add current URL if it matches pattern
                            if self._matches_pattern(current_url, url_pattern):
                                discovered_urls.add(current_url)

                            # Extract and queue internal links
                            if result.links:
                                for link_data in result.links.get('internal', []):
                                    link = link_data.get('href', '')
                                    if link:
                                        # Normalize URL
                                        full_url = urljoin(base_url, link)

                                        # Only follow links within the same domain
                                        if full_url.startswith(base_url):
                                            if full_url not in visited:
                                                to_visit.append((full_url, depth + 1))

                        # Be nice to the server
                        await asyncio.sleep(0.5)

                    except Exception as e:
                        logger.warning(f"Failed to crawl {current_url}: {e}")
                        continue

            urls = list(discovered_urls)[:self.max_urls]

            return DiscoveryResult(
                urls=urls,
                method="crawl",
                total_found=len(discovered_urls),
                filtered_count=len(urls)
            )

        except Exception as e:
            logger.error(f"Crawl4AI discovery failed: {e}")
            return DiscoveryResult(
                urls=[],
                method="crawl",
                total_found=0,
                filtered_count=0,
                error=str(e)
            )

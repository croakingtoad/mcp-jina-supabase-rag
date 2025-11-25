"""
Content Extraction Layer

Handles extracting clean content from URLs using:
1. Jina AI Reader API (primary, fast)
2. Crawl4AI (fallback for complex pages)
"""
import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional, Literal
import os

import httpx
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

logger = logging.getLogger(__name__)


@dataclass
class ExtractedContent:
    """Extracted content from a URL"""
    url: str
    title: str
    content: str
    markdown: str
    success: bool
    error: Optional[str] = None
    method: Optional[str] = None


class ContentExtractor:
    """Extracts clean content from URLs using Jina or Crawl4AI"""

    def __init__(
        self,
        jina_api_key: Optional[str] = None,
        timeout: int = 30,
        max_parallel: int = 10
    ):
        self.jina_api_key = jina_api_key or os.getenv("JINA_API_KEY")
        self.timeout = timeout
        self.max_parallel = max_parallel

    async def extract(
        self,
        urls: List[str],
        method: Literal["auto", "jina", "crawl4ai"] = "auto"
    ) -> List[ExtractedContent]:
        """
        Extract content from URLs

        Args:
            urls: List of URLs to extract content from
            method: Extraction method to use

        Returns:
            List of ExtractedContent objects
        """
        logger.info(f"Extracting content from {len(urls)} URLs using method: {method}")

        if method == "auto":
            # Use Jina for bulk (>10 URLs) if API key available
            if self.jina_api_key and len(urls) > 10:
                method = "jina"
            else:
                method = "crawl4ai"

        if method == "jina":
            if not self.jina_api_key:
                logger.warning("Jina API key not found, falling back to Crawl4AI")
                return await self._crawl4ai_extract(urls)
            return await self._jina_extract(urls)
        else:
            return await self._crawl4ai_extract(urls)

    async def _jina_extract(self, urls: List[str]) -> List[ExtractedContent]:
        """Extract content using Jina AI Reader API"""
        results = []

        # Process in batches to avoid rate limits
        batch_size = self.max_parallel

        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            logger.debug(f"Processing Jina batch {i // batch_size + 1}")

            tasks = [self._jina_extract_single(url) for url in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Jina extraction failed: {result}")
                    results.append(ExtractedContent(
                        url="",
                        title="",
                        content="",
                        markdown="",
                        success=False,
                        error=str(result),
                        method="jina"
                    ))
                else:
                    results.append(result)

            # Rate limiting delay
            await asyncio.sleep(1)

        return results

    async def _jina_extract_single(self, url: str) -> ExtractedContent:
        """Extract content from a single URL using Jina"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Jina Reader API endpoint
                jina_url = f"https://r.jina.ai/{url}"

                headers = {
                    "Authorization": f"Bearer {self.jina_api_key}",
                    "X-Return-Format": "markdown"
                }

                response = await client.get(jina_url, headers=headers)
                response.raise_for_status()

                markdown_content = response.text

                # Extract title from first line if it's a heading
                lines = markdown_content.split('\n')
                title = ""
                if lines and lines[0].startswith('#'):
                    title = lines[0].lstrip('#').strip()
                else:
                    # Try to extract from URL
                    title = url.split('/')[-1].replace('-', ' ').replace('_', ' ')

                return ExtractedContent(
                    url=url,
                    title=title,
                    content=markdown_content,
                    markdown=markdown_content,
                    success=True,
                    method="jina"
                )

        except Exception as e:
            logger.error(f"Jina extraction failed for {url}: {e}")
            return ExtractedContent(
                url=url,
                title="",
                content="",
                markdown="",
                success=False,
                error=str(e),
                method="jina"
            )

    async def _crawl4ai_extract(self, urls: List[str]) -> List[ExtractedContent]:
        """Extract content using Crawl4AI"""
        results = []

        browser_config = BrowserConfig(
            headless=True,
            verbose=False
        )

        crawler_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            word_count_threshold=10,
            js_code=[
                # Wait for content to load
                "await new Promise(r => setTimeout(r, 2000));"
            ]
        )

        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                for url in urls:
                    try:
                        logger.debug(f"Crawling {url} with Crawl4AI")
                        result = await crawler.arun(url=url, config=crawler_config)

                        if result.success:
                            results.append(ExtractedContent(
                                url=url,
                                title=result.metadata.get('title', ''),
                                content=result.cleaned_html or result.html,
                                markdown=result.markdown or "",
                                success=True,
                                method="crawl4ai"
                            ))
                        else:
                            results.append(ExtractedContent(
                                url=url,
                                title="",
                                content="",
                                markdown="",
                                success=False,
                                error=result.error_message,
                                method="crawl4ai"
                            ))

                        # Be nice to the server
                        await asyncio.sleep(0.5)

                    except Exception as e:
                        logger.error(f"Crawl4AI extraction failed for {url}: {e}")
                        results.append(ExtractedContent(
                            url=url,
                            title="",
                            content="",
                            markdown="",
                            success=False,
                            error=str(e),
                            method="crawl4ai"
                        ))

            return results

        except Exception as e:
            logger.error(f"Crawl4AI extraction failed: {e}")
            return [
                ExtractedContent(
                    url=url,
                    title="",
                    content="",
                    markdown="",
                    success=False,
                    error=str(e),
                    method="crawl4ai"
                )
                for url in urls
            ]

import os
import re
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from crawl4ai import (
    AsyncWebCrawler,
    CrawlerRunConfig,
    CacheMode
)
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter
from log_manager import LoggerUtility

logger = LoggerUtility().get_logger()

load_dotenv()
class BestFirstCrawl:

    def __init__(self, keywords=None):
        self.keywords = keywords or ["crawl", "example", "async", "configuration"]
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )

    def prunning_filter(self):
        prune_filter = PruningContentFilter(
            threshold=0.45,
            threshold_type="dynamic"
        )
        markdown_generator = DefaultMarkdownGenerator(content_filter=prune_filter)
        return prune_filter, markdown_generator

    def build_crawler_config(self, depth: int, markdown_generator):
        max_pages = {1: 5, 2: 200}.get(depth, 500)
        keyword_scorer = KeywordRelevanceScorer(
            keywords=self.keywords,
            weight=0.7
        )
        return CrawlerRunConfig(
            deep_crawl_strategy=BestFirstCrawlingStrategy(
                max_depth=depth,
                include_external=False,
                max_pages=max_pages,
                url_scorer=keyword_scorer
            ),
            markdown_generator=markdown_generator,
            scraping_strategy=LXMLWebScrapingStrategy(),
            cache_mode=CacheMode.BYPASS,
            magic=True,
            verbose=True,
            override_navigator=True,
            scan_full_page=True,
            wait_for_images=True,
            simulate_user=True,
            adjust_viewport_to_content=True,
            remove_overlay_elements=True,
            user_agent=self.user_agent,
            user_agent_mode="random"
        )

    async def fetch_rendered_html(self, url: str) -> str:
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    ignore_https_errors=True,
                    user_agent=self.user_agent,
                    locale="en-US",
                    timezone_id="America/New_York",
                    viewport={"width": 1280, "height": 800},
                    color_scheme="light",
                    java_script_enabled=True,
                    permissions=["geolocation"]
                )
                page = await context.new_page()
                await page.goto(url, wait_until="commit")
                await page.wait_for_timeout(60)
                html = await page.content()
                await browser.close()
                return html
        except Exception as e:
            logger.exception(f"Unexpected error while rendering {url}")
            raise

    async def crawl_single_page(self, url: str):
        try:
            rendered_html = await self.fetch_rendered_html(url)
            _, markdown_generator = self.prunning_filter()
            config = self.build_crawler_config( depth=0, markdown_generator=markdown_generator)

            async with AsyncWebCrawler() as crawler:
                results = await crawler.arun(url=url, config=config, initial_html=rendered_html)
                return [{"url": result.url, "text": result.markdown.fit_markdown} for result in results]

        except Exception as e:
            logger.exception(f"Error during single page crawl of {url}")
            raise

    async def best_first_crawl(self, url: str, depth: int):
        try:
            rendered_html = await self.fetch_rendered_html(url)
            _, markdown_generator = self.prunning_filter()
            config = self.build_crawler_config(depth=depth, markdown_generator=markdown_generator)

            async with AsyncWebCrawler() as crawler:
                results = await crawler.arun(url=url, config=config, initial_html=rendered_html)
                return [{"url": result.url, "text": result.markdown.fit_markdown} for result in results]

        except Exception as e:
            logger.exception(f"Error during best first crawl of {url}")
            raise RuntimeError(f"Crawling failed for {url}") from e

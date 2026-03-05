"""JARVIS Browser Navigator — Playwright-based persistent browser control.

Maintains a single browser instance with multi-tab support.
Pilotable by voice commands, MCP tools, and autonomous actions.

Usage:
    from src.browser_navigator import browser_nav
    await browser_nav.launch()
    await browser_nav.navigate("https://google.com")
    await browser_nav.click_text("Suivant")
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis.browser")

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    Browser = BrowserContext = Page = Playwright = None


class BrowserNavigator:
    """Persistent browser controller via Playwright."""

    def __init__(self) -> None:
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._screenshots_dir = Path(tempfile.gettempdir()) / "jarvis_screenshots"
        self._screenshots_dir.mkdir(exist_ok=True)
        self._events: list[dict[str, Any]] = []

    @property
    def is_open(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    async def _ensure_browser(self) -> Page:
        """Ensure browser is running. Lazy-init."""
        if not HAS_PLAYWRIGHT:
            raise RuntimeError("playwright not installed. Run: pip install playwright && playwright install chromium")
        if not self.is_open:
            await self.launch()
        if self._page is None or self._page.is_closed():
            self._page = await self._context.new_page()
        return self._page

    async def launch(self, url: str | None = None, headless: bool = False) -> dict[str, Any]:
        """Open the browser (or reuse existing)."""
        if self.is_open:
            if url:
                return await self.navigate(url)
            return {"status": "already_open", "tabs": len(self._context.pages) if self._context else 0}

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=headless,
            args=["--start-maximized"],
        )
        self._context = await self._browser.new_context(
            viewport=None,  # full window
            locale="fr-FR",
            timezone_id="Europe/Paris",
        )
        self._page = await self._context.new_page()

        if url:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=10000)

        self._log("launch", url or "about:blank")
        logger.info("Browser launched (headless=%s)", headless)
        return {"status": "launched", "url": url or "about:blank"}

    async def close(self) -> dict[str, Any]:
        """Close the browser completely."""
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._browser = None
        self._context = None
        self._page = None
        self._pw = None
        self._log("close", "browser closed")
        return {"status": "closed"}

    # ── Navigation ────────────────────────────────────────────────────────

    async def navigate(self, url: str) -> dict[str, Any]:
        """Navigate to a URL."""
        page = await self._ensure_browser()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        await page.goto(url, wait_until="domcontentloaded", timeout=5000)
        self._log("navigate", url)
        return {"url": page.url, "title": await page.title()}

    async def go_back(self) -> dict[str, Any]:
        """Go back in history."""
        page = await self._ensure_browser()
        await page.go_back(wait_until="domcontentloaded", timeout=30000)
        self._log("back", page.url)
        return {"url": page.url, "title": await page.title()}

    async def go_forward(self) -> dict[str, Any]:
        """Go forward in history."""
        page = await self._ensure_browser()
        await page.go_forward(wait_until="domcontentloaded", timeout=5000)
        self._log("forward", page.url)
        return {"url": page.url, "title": await page.title()}

    async def reload(self) -> dict[str, Any]:
        """Reload current page."""
        page = await self._ensure_browser()
        await page.reload(wait_until="domcontentloaded", timeout=30000)
        return {"url": page.url, "title": await page.title()}

    # ── Interaction ───────────────────────────────────────────────────────

    async def click_text(self, text: str) -> dict[str, Any]:
        """Click an element containing text."""
        page = await self._ensure_browser()
        locator = page.get_by_text(text, exact=False).first
        await locator.click()
        self._log("click_text", text)
        await page.wait_for_load_state("domcontentloaded")
        return {"clicked": text, "url": page.url}

    async def click_button(self, label: str) -> dict[str, Any]:
        """Click a button by its label/name."""
        page = await self._ensure_browser()
        locator = page.get_by_role("button", name=label).first
        await locator.click()
        self._log("click_button", label)
        return {"clicked_button": label, "url": page.url}

    async def click_link(self, text: str) -> dict[str, Any]:
        """Click a link by its text."""
        page = await self._ensure_browser()
        locator = page.get_by_role("link", name=text).first
        await locator.click()
        self._log("click_link", text)
        await page.wait_for_load_state("domcontentloaded")
        return {"clicked_link": text, "url": page.url}

    async def scroll(self, direction: str = "down", amount: int = 500) -> dict[str, Any]:
        """Scroll the page."""
        page = await self._ensure_browser()
        delta = amount if direction == "down" else -amount
        await page.mouse.wheel(0, delta)
        self._log("scroll", f"{direction} {amount}px")
        return {"scrolled": direction, "amount": amount}

    async def fill_field(self, label: str, value: str) -> dict[str, Any]:
        """Fill a form field by its label."""
        page = await self._ensure_browser()
        locator = page.get_by_label(label).first
        await locator.fill(value, timeout=10000)
        self._log("fill", f"{label}={value[:30]}")
        return {"filled": label, "value": value[:50]}

    async def type_text(self, text: str) -> dict[str, Any]:
        """Type text into the currently focused element."""
        page = await self._ensure_browser()
        await page.keyboard.type(text)
        self._log("type", text[:30])
        return {"typed": text[:50]}

    async def press_key(self, key: str) -> dict[str, Any]:
        """Press a keyboard key (Enter, Escape, Tab, etc.)."""
        page = await self._ensure_browser()
        await page.keyboard.press(key)
        self._log("press", key)
        return {"pressed": key}

    # ── Search ────────────────────────────────────────────────────────────

    async def search(self, query: str) -> dict[str, Any]:
        """Search Google and show results."""
        page = await self._ensure_browser()
        url = f"https://www.google.com/search?q={query}&hl=fr"
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        self._log("search", query)
        return {"query": query, "url": page.url, "title": await page.title()}

    # ── Tabs ──────────────────────────────────────────────────────────────

    async def new_tab(self, url: str | None = None) -> dict[str, Any]:
        """Open a new tab."""
        ctx = self._context
        if not ctx:
            await self._ensure_browser()
            ctx = self._context
        page = await ctx.new_page()
        self._page = page
        if url:
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        self._log("new_tab", url or "about:blank")
        return {"tab_count": len(ctx.pages), "url": page.url}

    async def close_tab(self) -> dict[str, Any]:
        """Close current tab."""
        if not self._page or self._page.is_closed():
            return {"error": "no tab to close"}
        await self._page.close()
        # Switch to last remaining tab
        if self._context and self._context.pages:
            self._page = self._context.pages[-1]
            return {"closed": True, "remaining": len(self._context.pages), "url": self._page.url}
        self._page = None
        return {"closed": True, "remaining": 0}

    async def switch_tab(self, index: int) -> dict[str, Any]:
        """Switch to tab by index (0-based)."""
        if not self._context:
            return {"error": "no browser"}
        pages = self._context.pages
        if index < 0 or index >= len(pages):
            return {"error": f"tab {index} not found, have {len(pages)} tabs"}
        self._page = pages[index]
        await self._page.bring_to_front()
        return {"tab": index, "url": self._page.url, "title": await self._page.title()}

    async def list_tabs(self) -> list[dict[str, Any]]:
        """List all open tabs."""
        if not self._context:
            return []
        tabs = []
        for i, p in enumerate(self._context.pages):
            tabs.append({"index": i, "url": p.url, "title": await p.title()})
        return tabs

    # ── Content ───────────────────────────────────────────────────────────

    async def read_page(self, max_chars: int = 5000) -> str:
        """Extract visible text from the page."""
        page = await self._ensure_browser()
        text = await page.inner_text("body")
        return text[:max_chars]

    async def screenshot_page(self) -> str:
        """Take a screenshot. Returns file path."""
        page = await self._ensure_browser()
        ts = int(time.time())
        path = self._screenshots_dir / f"screen_{ts}.png"
        await page.screenshot(path=str(path), full_page=False)
        self._log("screenshot", str(path))
        return str(path)

    async def get_page_info(self) -> dict[str, Any]:
        """Get current page info."""
        page = await self._ensure_browser()
        return {
            "url": page.url,
            "title": await page.title(),
            "tab_count": len(self._context.pages) if self._context else 0,
        }

    # ── Window management ─────────────────────────────────────────────────

    async def move_to_screen(self, screen_index: int = 1) -> dict[str, Any]:
        """Move browser window to another screen (uses desktop_actions)."""
        try:
            from src.desktop_actions import move_window_to_next_monitor
            result = await move_window_to_next_monitor()
            return result
        except Exception as e:
            return {"error": str(e)}

    async def fullscreen(self) -> dict[str, Any]:
        """Toggle fullscreen."""
        page = await self._ensure_browser()
        await page.keyboard.press("F11")
        return {"fullscreen": True}

    # ── Status ────────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Browser status."""
        return {
            "open": self.is_open,
            "url": self._page.url if self._page and not self._page.is_closed() else None,
            "tab_count": len(self._context.pages) if self._context else 0,
            "events": len(self._events),
            "recent_events": self._events[-5:],
        }

    def _log(self, action: str, detail: str) -> None:
        self._events.append({"ts": time.time(), "action": action, "detail": detail[:100]})
        if len(self._events) > 200:
            self._events = self._events[-200:]


# Global singleton
browser_nav = BrowserNavigator()

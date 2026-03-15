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

# Lazy import to avoid circular deps
_browser_memory = None

def _get_memory():
    global _browser_memory
    if _browser_memory is None:
        try:
            from src.browser_memory import browser_memory
            _browser_memory = browser_memory
        except Exception:
            pass
    return _browser_memory

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
        if self._browser is not None:
            if hasattr(self._browser, 'is_connected'):
                return self._browser.is_connected()
            return True  # persistent context (BrowserContext has no is_connected)
        return False

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
        try:
            if self._context and self._context != self._browser:
                await self._context.close()
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass
        self._browser = None
        self._context = None
        self._page = None
        self._pw = None
        self._log("close", "browser closed")
        return {"status": "closed"}

    # ── Navigation ────────────────────────────────────────────────────────

    async def navigate(self, url: str) -> dict[str, Any]:
        """Navigate to a URL. Auto-tracks visit in browser memory."""
        page = await self._ensure_browser()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        await page.goto(url, wait_until="domcontentloaded", timeout=5000)
        title = await page.title()
        self._log("navigate", url)
        # Auto-track in browser memory
        await self._track_current_page(page)
        return {"url": page.url, "title": title}

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
        await self._track_current_page(page)
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

    # ── Memory & Intelligence ────────────────────────────────────────────

    async def _track_current_page(self, page: Page | None = None) -> None:
        """Auto-track current page in browser memory (background, non-blocking)."""
        mem = _get_memory()
        if not mem:
            return
        if page is None:
            page = self._page
        if not page or page.is_closed():
            return
        try:
            url = page.url
            if url in ("about:blank", ""):
                return
            title = await page.title()
            # Extract first 2000 chars of visible text for indexing
            try:
                content = await page.inner_text("body", timeout=2000)
                content = content[:2000]
            except Exception:
                content = ""
            mem.track_visit(url, title, content)
        except Exception as e:
            logger.debug("Memory tracking failed: %s", e)

    async def extract_landmarks(self) -> list[dict[str, Any]]:
        """Extract HTML landmarks (headings, links, buttons, forms) from current page.
        Stores them in browser memory for later voice navigation."""
        page = await self._ensure_browser()
        landmarks = await page.evaluate("""() => {
            const results = [];
            // Headings
            document.querySelectorAll('h1,h2,h3,h4').forEach((el, i) => {
                results.push({
                    type: 'heading',
                    selector: el.tagName + ':nth-of-type(' + (i+1) + ')',
                    text: el.textContent.trim().substring(0, 200),
                    label: el.tagName,
                    y: el.getBoundingClientRect().top + window.scrollY
                });
            });
            // Nav links
            document.querySelectorAll('nav a, [role="navigation"] a').forEach(el => {
                results.push({
                    type: 'nav_link',
                    selector: '',
                    text: el.textContent.trim().substring(0, 100),
                    label: el.href || '',
                    y: el.getBoundingClientRect().top + window.scrollY
                });
            });
            // Buttons
            document.querySelectorAll('button, [role="button"], input[type="submit"]').forEach(el => {
                const txt = el.textContent || el.value || el.getAttribute('aria-label') || '';
                if (txt.trim()) {
                    results.push({
                        type: 'button',
                        selector: '',
                        text: txt.trim().substring(0, 100),
                        label: 'button',
                        y: el.getBoundingClientRect().top + window.scrollY
                    });
                }
            });
            // Forms
            document.querySelectorAll('form').forEach((el, i) => {
                const inputs = el.querySelectorAll('input,textarea,select');
                results.push({
                    type: 'form',
                    selector: 'form:nth-of-type(' + (i+1) + ')',
                    text: 'Form with ' + inputs.length + ' fields',
                    label: el.action || '',
                    y: el.getBoundingClientRect().top + window.scrollY
                });
            });
            // Main content areas
            document.querySelectorAll('main, article, [role="main"]').forEach(el => {
                results.push({
                    type: 'content_area',
                    selector: el.tagName.toLowerCase(),
                    text: el.textContent.trim().substring(0, 150),
                    label: 'main content',
                    y: el.getBoundingClientRect().top + window.scrollY
                });
            });
            return results.slice(0, 200);
        }""")

        # Store in memory
        mem = _get_memory()
        if mem:
            mem.store_landmarks(page.url, landmarks)

        self._log("landmarks", f"{len(landmarks)} elements")
        return landmarks

    async def scroll_to_landmark(self, text: str) -> dict[str, Any]:
        """Scroll to a landmark by its text content (fuzzy match)."""
        page = await self._ensure_browser()
        result = await page.evaluate("""(searchText) => {
            const lower = searchText.toLowerCase();
            const elements = document.querySelectorAll('h1,h2,h3,h4,h5,h6,button,a,label,[role="heading"]');
            for (const el of elements) {
                if (el.textContent.toLowerCase().includes(lower)) {
                    el.scrollIntoView({behavior: 'smooth', block: 'center'});
                    return {found: true, text: el.textContent.trim().substring(0, 100),
                            tag: el.tagName, y: el.getBoundingClientRect().top};
                }
            }
            return {found: false};
        }""", text)
        self._log("scroll_to", text)
        return result

    async def bookmark_current(self, tags: list[str] | None = None,
                                notes: str = "") -> dict[str, Any]:
        """Bookmark the current page."""
        page = await self._ensure_browser()
        mem = _get_memory()
        if not mem:
            return {"error": "browser memory not available"}
        url = page.url
        title = await page.title()
        # Track first to ensure page exists
        await self._track_current_page(page)
        result = mem.bookmark(url, tags=tags, notes=notes)
        result["title"] = title
        self._log("bookmark", f"{title[:50]} {tags}")
        return result

    async def search_history(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search browsing history by semantic query."""
        mem = _get_memory()
        if not mem:
            return []
        return mem.search_pages(query, limit=limit)

    async def goto_remembered(self, name: str) -> dict[str, Any]:
        """Navigate to a remembered page by fuzzy name match."""
        mem = _get_memory()
        if not mem:
            return {"error": "browser memory not available"}
        page_info = mem.find_page_by_name(name)
        if not page_info:
            # Try semantic search
            results = mem.search_pages(name, limit=1)
            if results:
                page_info = results[0]
        if page_info:
            return await self.navigate(page_info["url"])
        return {"error": f"Aucune page trouvee pour '{name}'"}

    async def save_tab_session(self, name: str) -> dict[str, Any]:
        """Save all open tabs as a named session."""
        mem = _get_memory()
        if not mem or not self._context:
            return {"error": "no browser or memory"}
        urls = [p.url for p in self._context.pages if p.url != "about:blank"]
        return mem.save_session(name, urls)

    async def restore_tab_session(self, name: str) -> dict[str, Any]:
        """Restore a saved tab session."""
        mem = _get_memory()
        if not mem:
            return {"error": "browser memory not available"}
        urls = mem.load_session(name)
        if not urls:
            return {"error": f"Session '{name}' not found"}
        await self._ensure_browser()
        for url in urls:
            await self.new_tab(url)
        return {"session": name, "tabs_opened": len(urls)}

    async def summarize_page(self) -> dict[str, Any]:
        """Get page content and dispatch to cluster for AI summary."""
        page = await self._ensure_browser()
        url = page.url
        title = await page.title()
        content = await self.read_page(max_chars=3000)

        # Dispatch to M1 for summary
        summary = content[:500]  # Default fallback
        try:
            import aiohttp
            prompt = f"/nothink\nResume en 2-3 phrases ce contenu web. Titre: {title}\n\n{content[:2000]}"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://127.0.0.1:1234/api/v1/chat",
                    json={"model": "qwen3-8b", "input": prompt,
                          "temperature": 0.2, "max_output_tokens": 256,
                          "stream": False, "store": False},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Extract last message block
                        for block in reversed(data.get("output", [])):
                            if block.get("type") == "message":
                                for c in block.get("content", []):
                                    if c.get("type") == "output_text":
                                        summary = c["text"]
                                        break
                                break
        except Exception as e:
            logger.debug("AI summary failed, using truncated content: %s", e)

        # Store summary in memory
        mem = _get_memory()
        if mem:
            mem.track_visit(url, title, summary)
            mem.add_note(url, f"[Resume] {summary[:500]}")

        return {"url": url, "title": title, "summary": summary}

    async def get_page_landmarks_voice(self) -> str:
        """Get landmarks as voice-friendly text."""
        landmarks = await self.extract_landmarks()
        if not landmarks:
            return "Aucun repere trouve sur cette page."
        parts = []
        for lm in landmarks[:15]:
            if lm["type"] == "heading":
                parts.append(f"Titre: {lm['text'][:60]}")
            elif lm["type"] == "button":
                parts.append(f"Bouton: {lm['text'][:40]}")
            elif lm["type"] == "nav_link":
                parts.append(f"Lien: {lm['text'][:40]}")
            elif lm["type"] == "form":
                parts.append(f"Formulaire: {lm['text'][:40]}")
        return ". ".join(parts)

    # ── Find on Page ───────────────────────────────────────────────────────

    async def find_on_page(self, text: str) -> dict[str, Any]:
        """Find text on the current page (like Ctrl+F) and scroll to first match.
        Returns match count and highlights all matches."""
        page = await self._ensure_browser()
        result = await page.evaluate("""(searchText) => {
            // Remove previous highlights
            document.querySelectorAll('.jarvis-highlight').forEach(el => {
                const parent = el.parentNode;
                parent.replaceChild(document.createTextNode(el.textContent), el);
                parent.normalize();
            });
            if (!searchText) return {count: 0, found: false};

            const lower = searchText.toLowerCase();
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
            let count = 0;
            let firstEl = null;
            const nodes = [];
            while (walker.nextNode()) nodes.push(walker.currentNode);

            for (const node of nodes) {
                const idx = node.textContent.toLowerCase().indexOf(lower);
                if (idx >= 0) {
                    const span = document.createElement('span');
                    span.className = 'jarvis-highlight';
                    span.style.cssText = 'background:#ffeb3b;color:#000;padding:1px 3px;border-radius:3px;box-shadow:0 0 4px #ff9800';
                    const range = document.createRange();
                    range.setStart(node, idx);
                    range.setEnd(node, idx + searchText.length);
                    range.surroundContents(span);
                    count++;
                    if (!firstEl) firstEl = span;
                }
            }
            if (firstEl) {
                firstEl.scrollIntoView({behavior: 'smooth', block: 'center'});
                firstEl.style.outline = '3px solid #ff5722';
            }
            return {count, found: count > 0};
        }""", text)
        self._log("find", f"{text} -> {result.get('count', 0)} matches")
        return {**result, "query": text}

    async def clear_highlights(self) -> dict[str, Any]:
        """Remove all search highlights from page."""
        page = await self._ensure_browser()
        await page.evaluate("""() => {
            document.querySelectorAll('.jarvis-highlight').forEach(el => {
                const parent = el.parentNode;
                parent.replaceChild(document.createTextNode(el.textContent), el);
                parent.normalize();
            });
        }""")
        return {"cleared": True}

    # ── Read Links ─────────────────────────────────────────────────────────

    async def read_links(self, max_links: int = 20) -> list[dict[str, Any]]:
        """Extract all visible links from the page with text and href."""
        page = await self._ensure_browser()
        links = await page.evaluate("""(maxLinks) => {
            const seen = new Set();
            const results = [];
            for (const a of document.querySelectorAll('a[href]')) {
                const text = a.textContent.trim();
                const href = a.href;
                if (!text || text.length < 2 || seen.has(href)) continue;
                seen.add(href);
                const rect = a.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) continue;
                results.push({text: text.substring(0, 100), href, y: Math.round(rect.top + window.scrollY)});
                if (results.length >= maxLinks) break;
            }
            return results;
        }""", max_links)
        self._log("read_links", f"{len(links)} links")
        return links

    async def read_links_voice(self, max_links: int = 10) -> str:
        """Get links as voice-friendly text."""
        links = await self.read_links(max_links)
        if not links:
            return "Aucun lien visible sur cette page."
        parts = [f"{i+1}. {l['text']}" for i, l in enumerate(links)]
        return "Liens sur la page: " + ". ".join(parts)

    # ── Click by Number ────────────────────────────────────────────────────

    async def click_link_number(self, number: int) -> dict[str, Any]:
        """Click a link by its number (from read_links listing)."""
        links = await self.read_links(max_links=30)
        if number < 1 or number > len(links):
            return {"error": f"Lien {number} non trouve. Il y a {len(links)} liens."}
        link = links[number - 1]
        return await self.click_link(link["text"])

    # ── Auto Landmarks on Navigate ─────────────────────────────────────────

    async def navigate_and_analyze(self, url: str) -> dict[str, Any]:
        """Navigate to URL + auto-extract landmarks + track in memory."""
        nav_result = await self.navigate(url)
        try:
            landmarks = await self.extract_landmarks()
            nav_result["landmarks_count"] = len(landmarks)
        except Exception:
            nav_result["landmarks_count"] = 0
        return nav_result

    # ── Scroll to landmark with highlight ──────────────────────────────────

    async def scroll_to_landmark_highlight(self, text: str) -> dict[str, Any]:
        """Scroll to a landmark and highlight it visually."""
        page = await self._ensure_browser()
        result = await page.evaluate("""(searchText) => {
            // Clear previous highlights
            document.querySelectorAll('.jarvis-landmark-hl').forEach(el => {
                el.style.outline = '';
                el.style.background = '';
                el.classList.remove('jarvis-landmark-hl');
            });

            const lower = searchText.toLowerCase();
            const selectors = 'h1,h2,h3,h4,h5,h6,button,a,label,[role="heading"],nav,main,article,section,footer';
            for (const el of document.querySelectorAll(selectors)) {
                if (el.textContent.toLowerCase().includes(lower)) {
                    el.scrollIntoView({behavior: 'smooth', block: 'center'});
                    el.classList.add('jarvis-landmark-hl');
                    el.style.outline = '3px solid #2196F3';
                    el.style.background = 'rgba(33,150,243,0.1)';
                    setTimeout(() => {
                        el.style.outline = '';
                        el.style.background = '';
                        el.classList.remove('jarvis-landmark-hl');
                    }, 5000);
                    return {found: true, text: el.textContent.trim().substring(0, 100),
                            tag: el.tagName, y: el.getBoundingClientRect().top};
                }
            }
            return {found: false};
        }""", text)
        self._log("scroll_to_hl", text)
        return result

    # ── Persistent Context (cookie/login) ──────────────────────────────────

    async def launch_persistent(self, url: str | None = None, headless: bool = False) -> dict[str, Any]:
        """Launch with persistent storage (keeps cookies, sessions, logins)."""
        if self.is_open:
            if url:
                return await self.navigate(url)
            return {"status": "already_open"}

        if not HAS_PLAYWRIGHT:
            raise RuntimeError("playwright not installed")

        storage_dir = Path("/home/turbo/jarvis-m1-ops/data/browser_profile")
        storage_dir.mkdir(parents=True, exist_ok=True)

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch_persistent_context(
            user_data_dir=str(storage_dir),
            headless=headless,
            args=["--start-maximized"],
            locale="fr-FR",
            timezone_id="Europe/Paris",
            viewport=None,
        )
        # persistent context IS the context
        self._context = self._browser
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

        if url:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=10000)

        self._log("launch_persistent", url or "about:blank")
        return {"status": "launched_persistent", "url": url or "about:blank",
                "profile": str(storage_dir)}

    # ── Page interaction helpers ───────────────────────────────────────────

    async def read_selection(self) -> str:
        """Read the currently selected text on the page."""
        page = await self._ensure_browser()
        text = await page.evaluate("() => window.getSelection().toString()")
        return text or "Aucun texte selectionne."

    async def scroll_to_top(self) -> dict[str, Any]:
        """Scroll to the top of the page."""
        page = await self._ensure_browser()
        await page.evaluate("() => window.scrollTo({top: 0, behavior: 'smooth'})")
        return {"scrolled": "top"}

    async def scroll_to_bottom(self) -> dict[str, Any]:
        """Scroll to the bottom of the page."""
        page = await self._ensure_browser()
        await page.evaluate("() => window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'})")
        return {"scrolled": "bottom"}

    async def get_page_structure(self) -> dict[str, Any]:
        """Get a structured overview: headings tree + link count + form count."""
        page = await self._ensure_browser()
        structure = await page.evaluate("""() => {
            const headings = [];
            document.querySelectorAll('h1,h2,h3,h4').forEach(el => {
                headings.push({level: parseInt(el.tagName[1]), text: el.textContent.trim().substring(0, 120)});
            });
            const links = document.querySelectorAll('a[href]').length;
            const buttons = document.querySelectorAll('button,[role="button"]').length;
            const forms = document.querySelectorAll('form').length;
            const images = document.querySelectorAll('img').length;
            const inputs = document.querySelectorAll('input,textarea,select').length;
            return {headings, links, buttons, forms, images, inputs};
        }""")
        structure["url"] = page.url
        structure["title"] = await page.title()
        return structure

    async def get_page_structure_voice(self) -> str:
        """Page structure as voice-friendly text."""
        s = await self.get_page_structure()
        parts = [f"Page: {s['title']}."]
        if s["headings"]:
            h_text = ", ".join(h["text"][:40] for h in s["headings"][:5])
            parts.append(f"Titres: {h_text}.")
        parts.append(f"{s['links']} liens, {s['buttons']} boutons, {s['forms']} formulaires, {s['images']} images.")
        return " ".join(parts)

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

"""JARVIS Dashboard — Textual TUI unifying all JARVIS functionality.

Panels:
  - Cluster: Live M1/M2/M3 status with model info
  - System: CPU, RAM, GPU, uptime
  - Skills: All learned skills with categories
  - Brain: Pattern detection, auto-learned skills
  - Trading: Pipeline status, positions, signals
  - Log: Scrolling action log
  - Input: Command bar at bottom
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Static,
)

# ── Imports JARVIS ──────────────────────────────────────────────────────────
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import config, JARVIS_VERSION
from src.skills import load_skills, format_skills_list
from src.brain import get_brain_status, format_brain_report


# ── Helpers ─────────────────────────────────────────────────────────────────

async def _fetch_cluster() -> list[dict]:
    """Fetch cluster node status."""
    results = []
    async with httpx.AsyncClient(timeout=5) as c:
        for node in config.lm_nodes:
            entry = {
                "name": node.name,
                "role": node.role,
                "url": node.url,
                "gpus": node.gpus,
                "vram": node.vram_gb,
                "model": node.default_model,
                "online": False,
                "models_count": 0,
            }
            try:
                r = await c.get(f"{node.url}/api/v1/models")
                r.raise_for_status()
                entry["online"] = True
                entry["models_count"] = len([m for m in r.json().get("models", []) if m.get("loaded_instances")])
            except Exception:
                pass
            results.append(entry)
    return results


async def _fetch_system() -> dict:
    """Fetch system info via PowerShell (non-blocking)."""
    import subprocess

    def _get():
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "$os = Get-CimInstance Win32_OperatingSystem; "
                 "$cpu = Get-CimInstance Win32_Processor | Select -First 1; "
                 "$ram_total = [math]::Round($os.TotalVisibleMemorySize/1MB,1); "
                 "$ram_free = [math]::Round($os.FreePhysicalMemory/1MB,1); "
                 "$ram_used = $ram_total - $ram_free; "
                 "$uptime = (Get-Date) - $os.LastBootUpTime; "
                 "$disks = Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | "
                 "  ForEach-Object { \"$($_.DeviceID) $([math]::Round($_.FreeSpace/1GB,1))/$([math]::Round($_.Size/1GB,1))GB\" }; "
                 "\"CPU: $($cpu.Name)|RAM: ${ram_used}/${ram_total} GB|Uptime: $($uptime.Days)j $($uptime.Hours)h|Disks: $($disks -join ', ')\""],
                capture_output=True, text=True, timeout=15,
            )
            return r.stdout.strip()
        except Exception as e:
            return f"Erreur: {e}"

    return await asyncio.to_thread(_get)


async def _fetch_trading() -> str:
    """Fetch trading status summary."""
    try:
        from src.trading import pipeline_status
        status = await asyncio.to_thread(pipeline_status)
        if isinstance(status, dict):
            lines = []
            if "positions" in status:
                lines.append(f"Positions: {len(status['positions'])}")
            if "pending_signals" in status:
                lines.append(f"Signaux: {status['pending_signals']}")
            if "pnl" in status:
                lines.append(f"PnL: {status['pnl']}")
            return " | ".join(lines) if lines else json.dumps(status, default=str)[:200]
        return str(status)[:200]
    except Exception as e:
        return f"Trading: {e}"


# ── CSS ─────────────────────────────────────────────────────────────────────

DASHBOARD_CSS = """
Screen {
    layout: grid;
    grid-size: 3 3;
    grid-gutter: 1;
    grid-rows: auto 1fr auto;
}

#cluster-panel {
    column-span: 1;
    row-span: 1;
    border: solid $accent;
    padding: 1;
    height: 100%;
}

#system-panel {
    column-span: 1;
    row-span: 1;
    border: solid $secondary;
    padding: 1;
    height: 100%;
}

#trading-panel {
    column-span: 1;
    row-span: 1;
    border: solid $warning;
    padding: 1;
    height: 100%;
}

#skills-panel {
    column-span: 1;
    row-span: 1;
    border: solid $success;
    padding: 1;
    height: 100%;
    overflow-y: auto;
}

#log-panel {
    column-span: 1;
    row-span: 1;
    border: solid $primary;
    padding: 0 1;
    height: 100%;
}

#brain-panel {
    column-span: 1;
    row-span: 1;
    border: solid $error;
    padding: 1;
    height: 100%;
}

#input-bar {
    column-span: 3;
    row-span: 1;
    height: 3;
    dock: bottom;
}

.panel-title {
    text-style: bold;
    color: $text;
    margin-bottom: 1;
}

#cluster-panel .panel-title { color: $accent; }
#system-panel .panel-title { color: $secondary; }
#trading-panel .panel-title { color: $warning; }
#skills-panel .panel-title { color: $success; }
#log-panel .panel-title { color: $primary; }
#brain-panel .panel-title { color: $error; }
"""


# ── Widgets ─────────────────────────────────────────────────────────────────

class ClusterPanel(Static):
    """Live cluster status panel."""

    def compose(self) -> ComposeResult:
        yield Label("[b]CLUSTER IA[/b]", classes="panel-title")
        yield Static("Chargement...", id="cluster-content")


class SystemPanel(Static):
    """System info panel."""

    def compose(self) -> ComposeResult:
        yield Label("[b]SYSTEME[/b]", classes="panel-title")
        yield Static("Chargement...", id="system-content")


class TradingPanel(Static):
    """Trading status panel."""

    def compose(self) -> ComposeResult:
        yield Label("[b]TRADING[/b]", classes="panel-title")
        yield Static("Chargement...", id="trading-content")


class SkillsPanel(VerticalScroll):
    """Skills list panel."""

    def compose(self) -> ComposeResult:
        yield Label("[b]SKILLS[/b]", classes="panel-title")
        yield Static("Chargement...", id="skills-content")


class BrainPanel(Static):
    """Brain status panel."""

    def compose(self) -> ComposeResult:
        yield Label("[b]BRAIN[/b]", classes="panel-title")
        yield Static("Chargement...", id="brain-content")


class LogPanel(Static):
    """Scrolling action log."""

    def compose(self) -> ComposeResult:
        yield Label("[b]LOG[/b]", classes="panel-title")
        yield RichLog(id="log-output", max_lines=200, wrap=True, markup=True)


# ── Main App ────────────────────────────────────────────────────────────────

class JarvisDashboard(App):
    """JARVIS Unified Dashboard."""

    TITLE = f"JARVIS v{JARVIS_VERSION} — Dashboard Unifie"
    SUB_TITLE = "69 outils MCP | Cluster 3 machines | Brain IA"
    CSS = DASHBOARD_CSS

    BINDINGS = [
        Binding("f5", "refresh", "Rafraichir"),
        Binding("f1", "skills", "Skills"),
        Binding("f2", "cluster", "Cluster"),
        Binding("f3", "brain", "Brain"),
        Binding("q", "quit", "Quitter"),
        Binding("escape", "quit", "Quitter"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield ClusterPanel(id="cluster-panel")
        yield SystemPanel(id="system-panel")
        yield TradingPanel(id="trading-panel")
        yield SkillsPanel(id="skills-panel")
        yield LogPanel(id="log-panel")
        yield BrainPanel(id="brain-panel")
        yield Input(placeholder="Commande JARVIS... (F5=refresh, Q=quitter)", id="input-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Start periodic refresh on mount."""
        self._log("Dashboard JARVIS demarre.")
        self.refresh_all()
        self.set_interval(30, self.refresh_all)

    def _log(self, text: str) -> None:
        """Add a line to the log panel."""
        try:
            log_widget = self.query_one("#log-output", RichLog)
            ts = time.strftime("%H:%M:%S")
            log_widget.write(f"[dim]{ts}[/dim] {text}")
        except Exception:
            pass

    @work(thread=False)
    async def refresh_all(self) -> None:
        """Refresh all panels."""
        self._log("[bold]Rafraichissement...[/bold]")
        await asyncio.gather(
            self._refresh_cluster(),
            self._refresh_system(),
            self._refresh_trading(),
            self._refresh_skills(),
            self._refresh_brain(),
        )
        self._log("Rafraichissement termine.")

    async def _refresh_cluster(self) -> None:
        """Refresh cluster panel."""
        try:
            nodes = await _fetch_cluster()
            lines = []
            online = sum(1 for n in nodes if n["online"])
            lines.append(f"[bold]{online}/{len(nodes)} en ligne[/bold]\n")
            for n in nodes:
                if n["online"]:
                    status = "[green]ONLINE[/green]"
                    detail = f"{n['models_count']} modeles"
                else:
                    status = "[red]OFFLINE[/red]"
                    detail = ""
                lines.append(
                    f"  {status} [bold]{n['name']}[/bold] ({n['role']})\n"
                    f"    {n['gpus']} GPU, {n['vram']}GB VRAM\n"
                    f"    {n['model']}"
                    + (f" — {detail}" if detail else "")
                )
            content = "\n".join(lines)
            self.query_one("#cluster-content", Static).update(content)
            self._log(f"Cluster: {online}/{len(nodes)} noeuds en ligne")
        except Exception as e:
            self.query_one("#cluster-content", Static).update(f"[red]Erreur: {e}[/red]")

    async def _refresh_system(self) -> None:
        """Refresh system panel."""
        try:
            raw = await _fetch_system()
            parts = raw.split("|")
            content = "\n".join(f"  {p.strip()}" for p in parts)
            self.query_one("#system-content", Static).update(content)
        except Exception as e:
            self.query_one("#system-content", Static).update(f"[red]Erreur: {e}[/red]")

    async def _refresh_trading(self) -> None:
        """Refresh trading panel."""
        try:
            info = await _fetch_trading()
            lines = [
                f"  Exchange: [bold]{config.exchange.upper()}[/bold] Futures",
                f"  Levier: {config.leverage}x",
                f"  TP: {config.tp_percent}% | SL: {config.sl_percent}%",
                f"  Paires: {len(config.pairs)}",
                f"  Dry run: {'[green]OUI[/green]' if config.dry_run else '[red]NON[/red]'}",
                f"\n  {info}",
            ]
            self.query_one("#trading-content", Static).update("\n".join(lines))
        except Exception as e:
            self.query_one("#trading-content", Static).update(f"[red]Erreur: {e}[/red]")

    async def _refresh_skills(self) -> None:
        """Refresh skills panel."""
        try:
            skills = load_skills()
            categories: dict[str, list] = {}
            for s in skills:
                categories.setdefault(s.category, []).append(s)

            lines = [f"[bold]{len(skills)} skills total[/bold]\n"]
            for cat, sk_list in sorted(categories.items()):
                lines.append(f"  [bold underline]{cat.upper()}[/bold underline] ({len(sk_list)})")
                for s in sk_list[:5]:
                    usage = f" [{s.usage_count}x]" if s.usage_count > 0 else ""
                    lines.append(f"    {s.name}{usage}: {s.description[:40]}")
                if len(sk_list) > 5:
                    lines.append(f"    ... +{len(sk_list) - 5} autres")
                lines.append("")

            self.query_one("#skills-content", Static).update("\n".join(lines))
        except Exception as e:
            self.query_one("#skills-content", Static).update(f"[red]Erreur: {e}[/red]")

    async def _refresh_brain(self) -> None:
        """Refresh brain panel."""
        try:
            status = get_brain_status()
            lines = [
                f"  Skills total: [bold]{status['total_skills']}[/bold]",
                f"  Auto-appris: [green]{status['auto_learned']}[/green]",
                f"  Custom: {status['custom']}",
                f"  Par defaut: {status['default']}",
                f"  Actions loguees: {status['total_actions']}",
                f"  Analyses: {status['total_analyses']}",
            ]
            if status["patterns_detected"]:
                lines.append("\n  [bold]Patterns:[/bold]")
                for p in status["patterns_detected"][:3]:
                    conf = f"{p['confidence']:.0%}"
                    lines.append(f"    {p['name']} ({p['count']}x, {conf})")
            self.query_one("#brain-content", Static).update("\n".join(lines))
        except Exception as e:
            self.query_one("#brain-content", Static).update(f"[red]Erreur: {e}[/red]")

    @on(Input.Submitted)
    async def handle_input(self, event: Input.Submitted) -> None:
        """Handle command input."""
        cmd = event.value.strip()
        if not cmd:
            return
        event.input.clear()
        self._log(f"[bold yellow]> {cmd}[/bold yellow]")

        # Built-in dashboard commands
        lower = cmd.lower()
        if lower in ("refresh", "r", "f5"):
            self.refresh_all()
        elif lower in ("quit", "q", "exit"):
            self.exit()
        elif lower == "skills":
            await self._refresh_skills()
            self._log("Skills rafraichis.")
        elif lower == "cluster":
            await self._refresh_cluster()
            self._log("Cluster rafraichi.")
        elif lower == "brain":
            await self._refresh_brain()
            self._log("Brain rafraichi.")
        elif lower == "brain learn":
            self._log("Lancement apprentissage brain...")
            await self._run_brain_learn()
        elif lower.startswith("skill "):
            skill_name = cmd[6:].strip()
            self._log(f"Recherche skill: {skill_name}...")
            await self._run_skill(skill_name)
        elif lower.startswith("query "):
            query_text = cmd[6:].strip()
            self._log(f"Query cluster M1: {query_text[:50]}...")
            await self._run_query(query_text)
        elif lower == "help":
            self._log(
                "[bold]Commandes dashboard:[/bold]\n"
                "  refresh / r / F5  — Rafraichir tout\n"
                "  cluster           — Refresh cluster\n"
                "  skills            — Refresh skills\n"
                "  brain             — Refresh brain\n"
                "  brain learn       — Lancer apprentissage\n"
                "  skill <nom>       — Info sur un skill\n"
                "  query <texte>     — Query M1 (Qwen3-30B)\n"
                "  quit / q          — Quitter\n"
            )
        else:
            self._log(f"Commande inconnue: {cmd}. Tape 'help' pour l'aide.")

    async def _run_brain_learn(self) -> None:
        """Run brain learning."""
        try:
            from src.brain import analyze_and_learn
            report = await asyncio.to_thread(analyze_and_learn, True, 0.5)
            if report["skills_created"]:
                self._log(f"[green]Skills crees: {', '.join(report['skills_created'])}[/green]")
            elif report["patterns"]:
                self._log(f"[yellow]{report['patterns_found']} patterns detectes, confiance insuffisante.[/yellow]")
            else:
                self._log("Pas assez d'historique pour apprendre.")
            await self._refresh_brain()
            await self._refresh_skills()
        except Exception as e:
            self._log(f"[red]Erreur brain: {e}[/red]")

    async def _run_skill(self, name: str) -> None:
        """Show skill details."""
        try:
            from src.skills import find_skill
            skill, score = find_skill(name)
            if skill:
                steps_text = ", ".join(s.tool for s in skill.steps)
                self._log(
                    f"[bold]{skill.name}[/bold] (score={score:.2f})\n"
                    f"  {skill.description}\n"
                    f"  Triggers: {', '.join(skill.triggers[:3])}\n"
                    f"  Steps: {steps_text}\n"
                    f"  Usage: {skill.usage_count}x | Categorie: {skill.category}"
                )
            else:
                self._log(f"[yellow]Skill '{name}' non trouve (score={score:.2f})[/yellow]")
        except Exception as e:
            self._log(f"[red]Erreur skill: {e}[/red]")

    async def _run_query(self, text: str) -> None:
        """Query M1 via LM Studio."""
        try:
            node = config.lm_nodes[0]
            self._log(f"Envoi a {node.name} ({node.default_model})...")
            async with httpx.AsyncClient(timeout=60) as c:
                r = await c.post(f"{node.url}/api/v1/chat", json={
                    "model": node.default_model,
                    "input": text,
                    "temperature": 0.7,
                    "max_output_tokens": 1024,
                    "stream": False,
                    "store": False,
                })
                r.raise_for_status()
                response = r.json()["output"][0]["content"]
                self._log(f"[green][{node.name}][/green] {response[:500]}")
        except Exception as e:
            self._log(f"[red]Erreur query: {e}[/red]")

    def action_refresh(self) -> None:
        self.refresh_all()

    def action_skills(self) -> None:
        self._log("Rafraichissement skills...")
        self.run_worker(self._refresh_skills())

    def action_cluster(self) -> None:
        self._log("Rafraichissement cluster...")
        self.run_worker(self._refresh_cluster())

    def action_brain(self) -> None:
        self._log("Rafraichissement brain...")
        self.run_worker(self._refresh_brain())


def run_dashboard():
    """Entry point for running the dashboard."""
    app = JarvisDashboard()
    app.run()


if __name__ == "__main__":
    run_dashboard()

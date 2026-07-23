"""
Enhanced CLI Interface for CoHost.AI
Provides a beautiful, organized, and informative command-line interface.
"""

import time
import threading
from datetime import datetime
from typing import Optional, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.align import Align

class CLIInterface:
    """Enhanced CLI interface with real-time status updates and beautiful formatting."""

    def __init__(self, show_detailed_logs: bool = False, refresh_rate: float = 0.1):
        self.console = Console()
        self.show_detailed_logs = show_detailed_logs
        self.refresh_rate = refresh_rate
        
        # State tracking
        self.status = "Starting..."
        self.last_question = ""
        self.last_response = ""
        self.last_activity = ""
        self.stats = {
            "questions_processed": 0,
            "speech_inputs": 0,
            "udp_messages": 0,
            "errors": 0,
            "uptime_start": time.time()
        }
        
        # Live display
        self.layout = Layout()
        self.live_display: Optional[Live] = None
        self.update_lock = threading.Lock()
        
        self._setup_layout()
    
    def _setup_layout(self):
        """Setup the layout structure."""
        self.layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        self.layout["main"].split_row(
            Layout(name="status", ratio=1),
            Layout(name="activity", ratio=2)
        )
    
    def _create_header(self) -> Panel:
        """Create the header panel."""
        title = Text("🤖 CoHost.AI - AI Streaming Co-Host", style="bold magenta")
        subtitle = Text(f"Status: {self.status}", style="cyan")
        
        header_content = Align.center(
            Text.assemble(title, "\n", subtitle)
        )
        
        return Panel(
            header_content,
            style="bright_blue",
            padding=(0, 1)
        )
    
    def _create_status_panel(self) -> Panel:
        """Create the status information panel."""
        uptime = time.time() - self.stats["uptime_start"]
        uptime_str = f"{int(uptime // 3600):02d}:{int((uptime % 3600) // 60):02d}:{int(uptime % 60):02d}"
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="bold")
        table.add_column("Value", style="green")
        
        table.add_row("🕐 Uptime", uptime_str)
        table.add_row("❓ Questions", str(self.stats["questions_processed"]))
        table.add_row("🎙️ Voice Inputs", str(self.stats["speech_inputs"]))
        table.add_row("📡 UDP Messages", str(self.stats["udp_messages"]))
        table.add_row("❌ Errors", str(self.stats["errors"]))
        
        return Panel(
            table,
            title="📊 Statistics",
            style="blue",
            padding=(1, 1)
        )
    
    def _create_activity_panel(self) -> Panel:
        """Create the recent activity panel."""
        content = []
        
        if self.last_question:
            content.append(Text("🔵 Last Question:", style="bold blue"))
            content.append(Text(f"   {self.last_question[:80]}{'...' if len(self.last_question) > 80 else ''}", style="white"))
            content.append(Text())
        
        if self.last_response:
            content.append(Text("🟢 Last Response:", style="bold green"))
            content.append(Text(f"   {self.last_response[:80]}{'...' if len(self.last_response) > 80 else ''}", style="white"))
            content.append(Text())
        
        if self.last_activity:
            content.append(Text("⚡ Last Activity:", style="bold yellow"))
            content.append(Text(f"   {self.last_activity}", style="white"))
        
        if not content:
            content = [Text("Waiting for activity...", style="dim")]
        
        activity_text = Text()
        for item in content:
            activity_text.append(item)
            activity_text.append("\n")
        
        return Panel(
            activity_text,
            title="📝 Recent Activity",
            style="green",
            padding=(1, 1)
        )
    
    def _create_footer(self) -> Panel:
        """Create the footer panel."""
        controls = [
            "🎤 Ctrl+M: Start/Stop Recording",
            "❌ Ctrl+C: Exit"
        ]
        
        footer_text = Text(" | ".join(controls), style="bold")
        
        return Panel(
            Align.center(footer_text),
            style="bright_black",
            padding=(0, 1)
        )
    
    def _update_display(self):
        """Update the live display."""
        with self.update_lock:
            self.layout["header"].update(self._create_header())
            self.layout["status"].update(self._create_status_panel())
            self.layout["activity"].update(self._create_activity_panel())
            self.layout["footer"].update(self._create_footer())
    
    def start_display(self):
        """Start the live display."""
        self._update_display()
        self.live_display = Live(
            self.layout,
            console=self.console,
            refresh_per_second=1/self.refresh_rate,
            screen=True
        )
        self.live_display.start()
    
    def stop_display(self):
        """Stop the live display."""
        if self.live_display:
            self.live_display.stop()
    
    def update_status(self, status: str):
        """Update the current status."""
        self.status = status
        self.last_activity = f"{datetime.now().strftime('%H:%M:%S')} - {status}"
        self._update_display()
    
    def log_question(self, question: str, source: str = "Unknown"):
        """Log a new question."""
        self.last_question = question
        self.stats["questions_processed"] += 1
        
        if "Voice Input" in question:
            self.stats["speech_inputs"] += 1
        else:
            self.stats["udp_messages"] += 1
        
        self.last_activity = f"{datetime.now().strftime('%H:%M:%S')} - Question from {source}"
        self._update_display()
        
        if self.show_detailed_logs:
            self.console.print(f"[yellow]📥 Question ({source}): {question}")
    
    def log_response(self, response: str):
        """Log an AI response."""
        self.last_response = response
        self.last_activity = f"{datetime.now().strftime('%H:%M:%S')} - AI response generated"
        self._update_display()
        
        if self.show_detailed_logs:
            self.console.print(f"[green]🤖 Response: {response}")
    
    def log_tts_start(self, text: str):
        """Log TTS synthesis start."""
        self.last_activity = f"{datetime.now().strftime('%H:%M:%S')} - Synthesizing speech"
        self._update_display()
        
        if self.show_detailed_logs:
            self.console.print(f"[blue]🔊 TTS: {text[:50]}...")
    
    def log_tts_cached(self, text: str):
        """Log TTS cache hit."""
        self.last_activity = f"{datetime.now().strftime('%H:%M:%S')} - Using cached audio"
        self._update_display()
        
        if self.show_detailed_logs:
            self.console.print(f"[cyan]⚡ Cached TTS: {text[:50]}...")
    
    def log_speech_start(self):
        """Log speech recognition start."""
        self.last_activity = f"{datetime.now().strftime('%H:%M:%S')} - Recording speech..."
        self._update_display()
        
        if self.show_detailed_logs:
            self.console.print("[magenta]🎤 Recording started")
    
    def log_speech_stop(self):
        """Log speech recognition stop."""
        self.last_activity = f"{datetime.now().strftime('%H:%M:%S')} - Processing speech..."
        self._update_display()
        
        if self.show_detailed_logs:
            self.console.print("[magenta]🛑 Recording stopped")
    
    def log_error(self, error: str):
        """Log an error."""
        self.stats["errors"] += 1
        self.last_activity = f"{datetime.now().strftime('%H:%M:%S')} - Error: {error[:30]}..."
        self._update_display()
        
        if self.show_detailed_logs:
            self.console.print(f"[red]❌ Error: {error}")
    
    def log_info(self, message: str):
        """Log an info message."""
        self.last_activity = f"{datetime.now().strftime('%H:%M:%S')} - {message}"
        self._update_display()
        
        if self.show_detailed_logs:
            self.console.print(f"[white]ℹ️  {message}")
    
    def show_startup_message(self):
        """Show startup message."""
        self.console.print(Panel.fit(
            "[bold green]🚀 CoHost.AI Started![/bold green]\n\n"
            "[cyan]Features enabled:[/cyan]\n"
            "• 📡 UDP broadcast listening\n"
            "• 🎤 Local speech recognition\n"
            "• 🤖 AI responses via Ollama\n"
            "• 🔊 Text-to-speech with caching\n"
            "• 📺 OBS integration\n"
            "• ⚡ Performance optimizations\n\n"
            "[yellow]Press Ctrl+C to exit[/yellow]",
            title="Welcome to CoHost.AI",
            style="bright_green"
        ))
        time.sleep(2)  # Give user time to read

    def show_shutdown_message(self):
        """Show shutdown message."""
        self.console.print(Panel.fit(
            "[bold red]👋 CoHost.AI Stopped[/bold red]\n\n"
            f"[cyan]Session Statistics:[/cyan]\n"
            f"• Questions processed: {self.stats['questions_processed']}\n"
            f"• Voice inputs: {self.stats['speech_inputs']}\n"
            f"• UDP messages: {self.stats['udp_messages']}\n"
            f"• Errors: {self.stats['errors']}\n"
            f"• Uptime: {int((time.time() - self.stats['uptime_start']) // 60)} minutes",
            title="Goodbye",
            style="bright_red"
        ))

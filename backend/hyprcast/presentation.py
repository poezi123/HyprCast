"""Praesentationsmodus: verhindert Bildschirmsperre und Standby, solange er an ist.

Nutzt einen logind-Inhibitor (systemd-inhibit). hypridle respektiert den
standardmaessig; beim Beenden des Prozesses ist er sofort wieder weg.
"""

import asyncio


class Presentation:
    def __init__(self) -> None:
        self._proc: asyncio.subprocess.Process | None = None

    @property
    def active(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def set(self, on: bool) -> None:
        if on and not self.active:
            self._proc = await asyncio.create_subprocess_exec(
                "systemd-inhibit", "--what=idle:sleep", "--who=HyprCast",
                "--why=Praesentation laeuft", "--mode=block", "sleep", "infinity",
            )
        elif not on and self.active:
            self._proc.terminate()
            await self._proc.wait()
            self._proc = None

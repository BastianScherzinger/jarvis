"""
JARVIS System Profile Analyzer
Analysiert Hardware beim Start und empfiehlt die optimale KI-Konfiguration.
"""
from __future__ import annotations
import os
import sys
import platform
import subprocess
import ctypes

R  = "\033[0m";  B  = "\033[1m"
GR = "\033[92m"; RD = "\033[91m"
YL = "\033[93m"; CY = "\033[96m"
GY = "\033[90m"; MG = "\033[95m"
BL = "\033[94m"


def _get_ram_gb() -> float:
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength",                 ctypes.c_ulong),
                ("dwMemoryLoad",             ctypes.c_ulong),
                ("ullTotalPhys",             ctypes.c_ulonglong),
                ("ullAvailPhys",             ctypes.c_ulonglong),
                ("ullTotalPageFile",         ctypes.c_ulonglong),
                ("ullAvailPageFile",         ctypes.c_ulonglong),
                ("ullTotalVirtual",          ctypes.c_ulonglong),
                ("ullAvailVirtual",          ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return stat.ullTotalPhys / (1024 ** 3)
    except Exception:
        pass
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception:
        return 8.0


def _get_cpu_name() -> str:
    try:
        res = subprocess.run(
            ["wmic", "cpu", "get", "name"],
            capture_output=True, text=True, timeout=6,
            encoding="utf-8", errors="replace",
        )
        lines = [l.strip() for l in res.stdout.splitlines() if l.strip() and l.strip() != "Name"]
        if lines:
            return lines[0]
    except Exception:
        pass
    return platform.processor() or "Unbekannte CPU"


def _get_gpu_info() -> tuple:
    """Returns (gpu_name: str, vram_gb: float)."""
    gpu_name = ""
    vram_gb = 0.0

    # nvidia-smi zuerst — genaueste VRAM-Info
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=6,
            encoding="utf-8", errors="replace",
        )
        if res.returncode == 0:
            line = res.stdout.strip().splitlines()[0]
            parts = line.split(",")
            if len(parts) >= 2:
                gpu_name = parts[0].strip()
                vram_gb = float(parts[1].strip()) / 1024.0
                return gpu_name, vram_gb
    except Exception:
        pass

    # wmic Fallback (funktioniert auch ohne NVIDIA)
    try:
        res = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "caption,AdapterRAM"],
            capture_output=True, text=True, timeout=6,
            encoding="utf-8", errors="replace",
        )
        lines = [l.strip() for l in res.stdout.splitlines()
                 if l.strip() and "Caption" not in l and "AdapterRAM" not in l]
        for line in lines:
            parts = line.split()
            if not parts:
                continue
            try:
                ram_bytes = int(parts[-1])
                if ram_bytes > 0 and ram_bytes > vram_gb * (1024 ** 3):
                    vram_gb = ram_bytes / (1024 ** 3)
                    gpu_name = " ".join(parts[:-1])
            except (ValueError, IndexError):
                if not gpu_name:
                    gpu_name = line
    except Exception:
        pass

    return gpu_name or "Nicht erkannt", vram_gb


def _is_laptop() -> bool:
    """True wenn Akku vorhanden (= Laptop / Notebook)."""
    try:
        res = subprocess.run(
            ["wmic", "path", "Win32_Battery", "get", "Status"],
            capture_output=True, text=True, timeout=6,
            encoding="utf-8", errors="replace",
        )
        lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
        return len(lines) > 1
    except Exception:
        return False


def _determine_tier(ram_gb: float, vram_gb: float, is_laptop: bool) -> dict:
    if ram_gb >= 64:
        return {
            "tier":          "SERVER",
            "label":         "HIGH-END SERVER / ALIENWARE",
            "color":         MG,
            "primary":       "Claude API + Starke lokale KI",
            "local_model":   "llama3.3:70b",
            "fallback_model":"qwen2.5:32b",
            "local_desc":    "Stärkstes lokales Modell (70B, 64+ GB RAM)",
            "strategy":      "Parallelbetrieb: Claude für Planung, lokale 70B für Ausführung",
        }
    elif ram_gb >= 32:
        return {
            "tier":          "WORKSTATION",
            "label":         "WORKSTATION / HIGH-END DESKTOP",
            "color":         CY,
            "primary":       "Claude API + Starkes lokales Modell",
            "local_model":   "qwen2.5:32b",
            "fallback_model":"qwen2.5:14b",
            "local_desc":    "Sehr starkes lokales Modell (32B, 32 GB RAM)",
            "strategy":      "32B offline für alle Sub-Tasks, Claude für komplexe Logik",
        }
    elif ram_gb >= 16:
        label = "LAPTOP HIGH-END" if is_laptop else "DESKTOP MID-RANGE"
        return {
            "tier":          "MID-RANGE",
            "label":         label,
            "color":         BL,
            "primary":       "Claude API (primär)",
            "local_model":   "qwen2.5:14b",
            "fallback_model":"qwen2.5:7b",
            "local_desc":    "Gutes lokales Modell (14B, 16 GB RAM)",
            "strategy":      "Claude als Haupt-KI, 14B für schnelle lokale Aufgaben",
        }
    elif ram_gb >= 8:
        return {
            "tier":          "LAPTOP",
            "label":         "LAPTOP / STANDARD",
            "color":         GR,
            "primary":       "Claude API (Haupt-Gehirn)",
            "local_model":   "qwen2.5:7b",
            "fallback_model":"qwen2.5-coder:1.5b",
            "local_desc":    "Balanciertes Modell (7B, 8 GB RAM)",
            "strategy":      "Claude API primär, 7B als Fallback und für Sub-Tasks",
        }
    else:
        return {
            "tier":          "MINIMAL",
            "label":         "ULTRABOOK / LOW-END",
            "color":         YL,
            "primary":       "Claude API (zwingend erforderlich)",
            "local_model":   "qwen2.5-coder:1.5b",
            "fallback_model":"llama3.2:1b",
            "local_desc":    "Kleinstes Modell (1.5B, < 4 GB RAM)",
            "strategy":      "Fast ausschließlich Claude API — lokale KI nur für Micro-Tasks",
        }


def analyze() -> dict:
    """Vollständige Hardware-Analyse — gibt Profil-Dict zurück."""
    ram_gb      = _get_ram_gb()
    cpu_name    = _get_cpu_name()
    gpu_name, vram_gb = _get_gpu_info()
    laptop      = _is_laptop()
    tier_info   = _determine_tier(ram_gb, vram_gb, laptop)

    return {
        "ram_gb":    ram_gb,
        "cpu":       cpu_name,
        "gpu":       gpu_name,
        "vram_gb":   vram_gb,
        "is_laptop": laptop,
        **tier_info,
    }


def print_banner(profile: dict) -> None:
    """Iron Man Stil System-Analyse Banner."""
    C = profile["color"]

    cpu_short = profile["cpu"][:42] + "..." if len(profile["cpu"]) > 45 else profile["cpu"]
    gpu_short = profile["gpu"][:42] + "..." if len(profile["gpu"]) > 45 else profile["gpu"]
    vram_str  = f"{profile['vram_gb']:.1f} GB VRAM" if profile["vram_gb"] > 0.5 else "kein dedizierter VRAM"
    hw_type   = "Laptop / Notebook" if profile["is_laptop"] else "Desktop / Server / Workstation"

    print()
    print(f"  {C}╔{'═' * 58}╗{R}")
    print(f"  {C}║{B}  ⚙  JARVIS  SYSTEM ANALYSE{R}{C}{'':>31}║{R}")
    print(f"  {C}╠{'═' * 58}╣{R}")
    print(f"  {C}║{R}  {GY}CPU   {R}{B}{cpu_short:<46}{C}║{R}")
    print(f"  {C}║{R}  {GY}RAM   {R}{B}{profile['ram_gb']:.0f} GB{R:<43}{C}║{R}")
    print(f"  {C}║{R}  {GY}GPU   {R}{B}{gpu_short:<46}{C}║{R}")
    print(f"  {C}║{R}  {GY}VRAM  {R}{B}{vram_str:<46}{C}║{R}")
    print(f"  {C}║{R}  {GY}TYP   {R}{B}{hw_type:<46}{C}║{R}")
    print(f"  {C}╠{'═' * 58}╣{R}")
    print(f"  {C}║{B}  TIER: {profile['tier']}  —  {profile['label']:<33}{R}{C}║{R}")
    print(f"  {C}╠{'═' * 58}╣{R}")
    print(f"  {C}║{R}  {GY}Primär    {R}{profile['primary']:<48}{C}║{R}")
    print(f"  {C}║{R}  {GY}Lokal     {R}{C}{B}{profile['local_model']:<10}{R}  {GY}{profile['local_desc'][:36]:<36}{C}║{R}")
    print(f"  {C}║{R}  {GY}Fallback  {R}{profile['fallback_model']:<48}{C}║{R}")
    print(f"  {C}║{R}  {GY}Strategie {R}{profile['strategy'][:48]:<48}{C}║{R}")
    print(f"  {C}╚{'═' * 58}╝{R}")
    print()


def write_profile(profile: dict, base_dir: str) -> None:
    """Schreibt System-Profil ins obsidian_brain Journal."""
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    vram_str = f"{profile['vram_gb']:.1f} GB" if profile["vram_gb"] > 0.5 else "kein dedizierter VRAM"
    content = f"""# JARVIS System Profil
Erstellt: {now}

## Hardware
- **CPU**: {profile['cpu']}
- **RAM**: {profile['ram_gb']:.0f} GB
- **GPU**: {profile['gpu']}
- **VRAM**: {vram_str}
- **Typ**: {'Laptop' if profile['is_laptop'] else 'Desktop / Server'}

## KI-Empfehlung
- **Tier**: {profile['tier']} — {profile['label']}
- **Primär**: {profile['primary']}
- **Lokales Modell**: {profile['local_model']}
- **Fallback**: {profile['fallback_model']}
- **Strategie**: {profile['strategy']}
"""
    import os
    path = os.path.join(base_dir, "obsidian_brain", "system_profile.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

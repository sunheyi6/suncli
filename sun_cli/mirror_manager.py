"""Mirror manager for Sun CLI - Auto-detect China mainland and use domestic mirrors."""

import re
import socket
import subprocess
from typing import Optional, Dict, List
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console


@dataclass
class MirrorConfig:
    """Configuration for a mirror source."""
    name: str
    original_url: str
    china_url: str
    env_var: Optional[str] = None
    config_file: Optional[Path] = None


class MirrorManager:
    """Manages automatic mirror switching based on IP location."""
    
    # Known China mainland mirrors
    MIRRORS = {
        "pypi": MirrorConfig(
            name="PyPI",
            original_url="pypi.org",
            china_url="pypi.tuna.tsinghua.edu.cn",
            env_var="PIP_INDEX_URL",
        ),
        "npm": MirrorConfig(
            name="npm",
            original_url="registry.npmjs.org",
            china_url="registry.npmmirror.com",
            env_var="NPM_CONFIG_REGISTRY",
        ),
        "docker": MirrorConfig(
            name="Docker Hub",
            original_url="docker.io",
            china_url="docker.mirrors.ustc.edu.cn",
        ),
        "github": MirrorConfig(
            name="GitHub",
            original_url="github.com",
            china_url="gh.api.99988866.xyz",
        ),
        "huggingface": MirrorConfig(
            name="HuggingFace",
            original_url="huggingface.co",
            china_url="hf-mirror.com",
            env_var="HF_ENDPOINT",
        ),
    }
    
    def __init__(self, console: Console):
        self.console = console
        self._is_china_mainland: Optional[bool] = None
        self._detected_mirrors: List[str] = []
    
    def _get_public_ip(self) -> Optional[str]:
        """Get public IP address."""
        try:
            # Try multiple IP detection services
            services = [
                ("ifconfig.me", 80, b"/", 5),
                ("icanhazip.com", 80, b"/", 5),
                ("api.ipify.org", 80, b"/", 5),
            ]
            
            for host, port, path, timeout in services:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    sock.connect((host, port))
                    request = f"GET {path.decode()} HTTP/1.1\r\nHost: {host}\r\n\r\n"
                    sock.send(request.encode())
                    response = sock.recv(1024).decode('utf-8', errors='ignore')
                    sock.close()
                    
                    # Extract IP from response
                    lines = response.split('\n')
                    for line in lines:
                        line = line.strip()
                        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', line):
                            return line
                except Exception:
                    continue
                    
        except Exception:
            pass
        return None
    
    def _is_china_ip(self, ip: str) -> bool:
        """Check if IP is from China mainland (simplified check)."""
        # China IP ranges (simplified, covers most common ones)
        china_ranges = [
            ("1.0.0.0", "1.0.0.255"),
            ("1.1.8.0", "1.1.8.255"),
            ("1.2.4.0", "1.2.4.255"),
            ("1.4.4.0", "1.4.4.255"),
            ("1.8.0.0", "1.8.255.255"),
            ("14.16.0.0", "14.31.255.255"),
            ("14.196.0.0", "14.197.255.255"),
            ("27.8.0.0", "27.31.255.255"),
            ("27.40.0.0", "27.47.255.255"),
            ("27.50.128.0", "27.50.255.255"),
            ("36.0.0.0", "36.63.255.255"),
            ("36.96.0.0", "36.127.255.255"),
            ("36.248.0.0", "36.255.255.255"),
            ("39.0.0.0", "39.255.255.255"),
            ("40.72.0.0", "40.73.255.255"),
            ("42.0.0.0", "42.15.255.255"),
            ("42.48.0.0", "42.59.255.255"),
            ("42.80.0.0", "42.81.255.255"),
            ("42.83.0.0", "42.83.255.255"),
            ("42.84.0.0", "42.84.255.255"),
            ("42.96.0.0", "42.103.255.255"),
            ("42.120.0.0", "42.125.255.255"),
            ("42.128.0.0", "42.143.255.255"),
            ("42.156.0.0", "42.159.255.255"),
            ("42.160.0.0", "42.167.255.255"),
            ("42.176.0.0", "42.183.255.255"),
            ("42.192.0.0", "42.199.255.255"),
            ("42.201.0.0", "42.201.255.255"),
            ("42.202.0.0", "42.207.255.255"),
            ("42.224.0.0", "42.239.255.255"),
            ("42.242.0.0", "42.243.255.255"),
            ("42.248.0.0", "42.255.255.255"),
            ("43.0.0.0", "43.15.255.255"),
            ("43.224.0.0", "43.255.255.255"),
            ("45.65.16.0", "45.65.31.255"),
            ("45.112.0.0", "45.127.255.255"),
            ("47.92.0.0", "47.127.255.255"),
            ("47.240.0.0", "47.255.255.255"),
            ("49.0.0.0", "49.15.255.255"),
            ("49.64.0.0", "49.95.255.255"),
            ("49.112.0.0", "49.123.255.255"),
            ("49.128.0.0", "49.255.255.255"),
            ("52.80.0.0", "52.83.255.255"),
            ("54.222.0.0", "54.223.255.255"),
            ("58.16.0.0", "58.31.255.255"),
            ("58.32.0.0", "58.63.255.255"),
            ("58.65.232.0", "58.65.255.255"),
            ("58.66.0.0", "58.67.255.255"),
            ("58.68.0.0", "58.71.255.255"),
            ("58.82.0.0", "58.83.255.255"),
            ("58.87.64.0", "58.87.127.255"),
            ("58.99.128.0", "58.99.255.255"),
            ("58.100.0.0", "58.143.255.255"),
            ("58.144.0.0", "58.159.255.255"),
            ("58.192.0.0", "58.255.255.255"),
            ("59.32.0.0", "59.63.255.255"),
            ("59.64.0.0", "59.127.255.255"),
            ("59.151.0.0", "59.151.255.255"),
            ("59.172.0.0", "59.175.255.255"),
            ("59.191.0.0", "59.191.255.255"),
            ("59.192.0.0", "59.255.255.255"),
            ("60.0.0.0", "60.31.255.255"),
            ("60.160.0.0", "60.191.255.255"),
            ("60.194.0.0", "60.195.255.255"),
            ("60.200.0.0", "60.223.255.255"),
            ("60.232.0.0", "60.233.255.255"),
            ("60.235.0.0", "60.235.255.255"),
            ("60.245.128.0", "60.245.255.255"),
            ("60.247.0.0", "60.247.255.255"),
            ("60.252.0.0", "60.252.255.255"),
            ("60.255.0.0", "60.255.255.255"),
            ("61.4.80.0", "61.4.95.255"),
            ("61.28.0.0", "61.28.255.255"),
            ("61.29.128.0", "61.29.255.255"),
            ("61.45.128.0", "61.45.255.255"),
            ("61.47.128.0", "61.47.255.255"),
            ("61.48.0.0", "61.55.255.255"),
            ("61.87.192.0", "61.87.255.255"),
            ("61.128.0.0", "61.191.255.255"),
            ("61.232.0.0", "61.237.255.255"),
            ("61.240.0.0", "61.243.255.255"),
            ("101.0.0.0", "101.63.255.255"),
            ("101.64.0.0", "101.127.255.255"),
            ("101.128.0.0", "101.255.255.255"),
            ("103.0.0.0", "103.255.255.255"),
            ("106.0.0.0", "106.127.255.255"),
            ("110.0.0.0", "110.255.255.255"),
            ("111.0.0.0", "111.255.255.255"),
            ("112.0.0.0", "112.127.255.255"),
            ("113.0.0.0", "113.255.255.255"),
            ("114.0.0.0", "114.255.255.255"),
            ("115.0.0.0", "115.255.255.255"),
            ("116.0.0.0", "116.255.255.255"),
            ("117.0.0.0", "117.255.255.255"),
            ("118.0.0.0", "118.255.255.255"),
            ("119.0.0.0", "119.255.255.255"),
            ("120.0.0.0", "120.255.255.255"),
            ("121.0.0.0", "121.255.255.255"),
            ("122.0.0.0", "122.255.255.255"),
            ("123.0.0.0", "123.255.255.255"),
            ("124.0.0.0", "124.255.255.255"),
            ("125.0.0.0", "125.255.255.255"),
            ("126.0.0.0", "126.255.255.255"),
            ("139.0.0.0", "139.255.255.255"),
            ("140.75.0.0", "140.75.255.255"),
            ("140.143.0.0", "140.143.255.255"),
            ("140.205.0.0", "140.205.255.255"),
            ("140.210.0.0", "140.210.255.255"),
            ("140.224.0.0", "140.255.255.255"),
            ("144.0.0.0", "144.255.255.255"),
            ("150.0.0.0", "150.255.255.255"),
            ("153.0.0.0", "153.255.255.255"),
            ("157.0.0.0", "157.255.255.255"),
            ("159.226.0.0", "159.226.255.255"),
            ("161.207.0.0", "161.207.255.255"),
            ("162.105.0.0", "162.105.255.255"),
            ("163.0.0.0", "163.255.255.255"),
            ("166.111.0.0", "166.111.255.255"),
            ("167.139.0.0", "167.139.255.255"),
            ("167.189.0.0", "167.189.255.255"),
            ("168.160.0.0", "168.160.255.255"),
            ("171.0.0.0", "171.255.255.255"),
            ("175.0.0.0", "175.255.255.255"),
            ("180.0.0.0", "180.255.255.255"),
            ("182.0.0.0", "182.255.255.255"),
            ("183.0.0.0", "183.255.255.255"),
            ("202.0.0.0", "203.255.255.255"),
            ("210.0.0.0", "211.255.255.255"),
            ("218.0.0.0", "218.255.255.255"),
            ("219.0.0.0", "219.255.255.255"),
            ("220.0.0.0", "220.255.255.255"),
            ("221.0.0.0", "221.255.255.255"),
            ("222.0.0.0", "222.255.255.255"),
            ("223.0.0.0", "223.255.255.255"),
        ]
        
        def ip_to_int(ip_str: str) -> int:
            parts = ip_str.split('.')
            return (int(parts[0]) << 24) + (int(parts[1]) << 16) + (int(parts[2]) << 8) + int(parts[3])
        
        ip_int = ip_to_int(ip)
        
        for start, end in china_ranges:
            if ip_to_int(start) <= ip_int <= ip_to_int(end):
                return True
        return False
    
    def detect_location(self) -> bool:
        """Detect if user is in China mainland."""
        if self._is_china_mainland is not None:
            return self._is_china_mainland
        
        # Get IP and check
        ip = self._get_public_ip()
        if ip:
            self._is_china_mainland = self._is_china_ip(ip)
        else:
            # Fallback: check timezone or LANG
            import os
            tz = os.environ.get('TZ', '')
            lang = os.environ.get('LANG', '')
            # Simple heuristic
            self._is_china_mainland = 'CN' in tz or 'zh_CN' in lang
        
        return self._is_china_mainland
    
    def setup_mirrors(self) -> Dict[str, str]:
        """Setup environment for China mirrors. Returns dict of applied mirrors."""
        applied = {}
        
        if not self.detect_location():
            return applied
        
        import os
        
        # Setup mirrors
        for key, mirror in self.MIRRORS.items():
            if mirror.env_var:
                # Check if already set
                current = os.environ.get(mirror.env_var)
                if not current or mirror.original_url in current:
                    # Set to China mirror
                    if key == "pypi":
                        china_url = f"https://{mirror.china_url}/simple"
                    elif key == "npm":
                        china_url = f"https://{mirror.china_url}"
                    elif key == "huggingface":
                        china_url = f"https://{mirror.china_url}"
                    else:
                        china_url = mirror.china_url
                    
                    os.environ[mirror.env_var] = china_url
                    applied[key] = china_url
                    self._detected_mirrors.append(mirror.name)
        
        return applied
    
    def notify_user(self) -> None:
        """Notify user about mirror usage (only once)."""
        if not self._detected_mirrors:
            return
        
        # Show notification
        mirrors_str = ", ".join(self._detected_mirrors)
        self.console.print(
            f"[dim]已检测到中国大陆网络环境，自动使用国内镜像: {mirrors_str}[/dim]",
            style="cyan"
        )


# Global instance
_mirror_manager: Optional[MirrorManager] = None


def get_mirror_manager(console: Optional[Console] = None) -> MirrorManager:
    """Get or create global mirror manager."""
    global _mirror_manager
    if _mirror_manager is None:
        _mirror_manager = MirrorManager(console or Console())
    return _mirror_manager


def init_mirrors(console: Console) -> None:
    """Initialize mirrors on startup."""
    mm = get_mirror_manager(console)
    mm.setup_mirrors()
    mm.notify_user()

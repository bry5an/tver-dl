import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

class VPNChecker:
    """Verifies VPN connection to Japan."""
    
    SERVICES = [
        ("https://ipapi.co/json/", lambda r: r.json().get("country_code")),
        ("https://ip.seeip.org/geoip", lambda r: r.json().get("country_code")),
        ("https://api.myip.com", lambda r: r.json().get("cc")),
    ]

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def check(self) -> bool:
        """Check if connected to a VPN (trying multiple IP geolocation services in parallel)."""
        self.logger.info("Checking VPN connection...")
        
        connected = False
        details = "Unknown"

        def check_service(url, parser):
            try:
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                country = parser(response)
                ip = response.json().get("ip", "unknown")
                return country, ip
            except Exception:
                return None, None

        with ThreadPoolExecutor(max_workers=len(self.SERVICES)) as executor:
            futures = [executor.submit(check_service, url, parser) for url, parser in self.SERVICES]
            
            for future in as_completed(futures):
                country, ip = future.result()
                if country:
                    if country == "JP":
                        self.logger.info(f"✓ Connected via Japan IP ({ip})")
                        return True
                    details = f"Country: {country}, IP: {ip}"

        # If we get here, no service confirmed JP
        self.logger.warning(f"Not connected to Japan VPN (Last detected: {details})")
        print("  TVer downloads may fail without Japanese IP")
        response = input("Continue anyway? (y/n): ")
        return response.lower() == "y"

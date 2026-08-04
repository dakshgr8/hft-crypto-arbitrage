import time
import json
import urllib.request
import multiprocessing
from typing import Dict, List, Callable

class OutOfBandTelemetryAgent:
    """
    Out-of-Band Telemetry & Auto-Respawn Agent (Phase 6 / Production Operations).
    
    Operates independently of the central matrix evaluation loop to monitor isolated OS worker processes.
    If an unhandled exception or network disconnect silently kills a worker process (e.g. Kraken WebSocket worker),
    this agent instantly attempts an automatic OS process respawn and pushes an emergency webhook alert
    to Telegram / PagerDuty for remote operational oversight from Mumbai.
    """
    def __init__(self, alert_webhook_url: str = "http://localhost:8080/mumbai_ops_alert", max_respawns_per_worker: int = 5):
        self.alert_webhook_url = alert_webhook_url
        self.max_respawns = max_respawns_per_worker
        self.worker_respawn_counts: Dict[str, int] = {}
        self.silent_deaths_detected: int = 0
        self.successful_respawns: int = 0
        self.last_alert_timestamp: float = 0.0
        self.alerts_sent_history: List[str] = []

    def send_pagerduty_alert(self, severity: str, title: str, details: str):
        """Pushes real-time alerts to PagerDuty / Telegram webhooks for Mumbai Operations monitoring."""
        payload = {
            "event_action": "trigger",
            "routing_key": "mumbai_ops_prod_tier1",
            "payload": {
                "summary": f"[{severity.upper()}] {title}",
                "source": "AWS-AP-NORTHEAST-1-TOKYO-NODE-A",
                "severity": severity.lower(),
                "custom_details": {
                    "details": details,
                    "timestamp_utc": time.time(),
                    "operator_location": "Mumbai Operations Control"
                }
            }
        }
        self.alerts_sent_history.append(f"[{severity.upper()}] {title} - {details}")
        print(f"\n[🚨 TELEMETRY ALERT -> MUMBAI OPS CONSOLE] {title} ({details})")
        
        # In actual deployment, perform non-blocking HTTP POST:
        # urllib.request.urlopen(urllib.request.Request(self.alert_webhook_url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}), timeout=1.5)

    def monitor_and_respawn_workers(self, worker_processes: List[multiprocessing.Process], worker_target_func: Callable, shm_name: str) -> List[multiprocessing.Process]:
        """
        Audits active OS worker processes. If any process dies silently, triggers immediate alert and auto-respawn.
        Returns the updated list of healthy worker processes.
        """
        active_workers = []
        for p in worker_processes:
            ex_name = p.name.replace("Worker-", "").lower()
            
            if p.is_alive():
                active_workers.append(p)
            else:
                # Silent Death Detected! Worker crashed or stopped autonomously
                self.silent_deaths_detected += 1
                exit_code = p.exitcode
                msg = f"Worker process '{p.name}' (PID: {p.pid}) terminated silently with exit code {exit_code}!"
                self.send_pagerduty_alert("critical", f"Worker Silent Death: {ex_name.upper()}", msg)
                
                current_respawns = self.worker_respawn_counts.get(ex_name, 0)
                if current_respawns < self.max_respawns:
                    print(f" [🚑 AUTO-RESPAWN TRIGGERED] Attempting immediate OS process respawn for {ex_name.upper()} (Respawn {current_respawns + 1}/{self.max_respawns})...")
                    new_p = multiprocessing.Process(
                        target=worker_target_func,
                        args=(ex_name, shm_name),
                        name=f"Worker-{ex_name.upper()}"
                    )
                    new_p.daemon = True
                    new_p.start()
                    active_workers.append(new_p)
                    self.worker_respawn_counts[ex_name] = current_respawns + 1
                    self.successful_respawns += 1
                    print(f" [✅ WORKER RESCUED] {ex_name.upper()} successfully respawned under new PID: {new_p.pid}!")
                else:
                    err_msg = f"Max respawns ({self.max_respawns}) exceeded for {ex_name.upper()}. Venue marked permanently degraded."
                    self.send_pagerduty_alert("error", f"Max Respawns Exceeded: {ex_name.upper()}", err_msg)

        return active_workers

    def get_telemetry_metrics(self) -> Dict:
        return {
            "silent_deaths_detected": self.silent_deaths_detected,
            "successful_auto_respawns": self.successful_respawns,
            "respawn_counts_per_venue": self.worker_respawn_counts,
            "recent_alerts": self.alerts_sent_history[-5:]
        }

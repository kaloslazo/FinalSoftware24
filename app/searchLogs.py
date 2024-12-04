import os
import datetime
import re

def analyze_logs():
    """Analyzes concert booking and test run logs for the current day."""
    metrics = {
        'retrievals': 0,
        'confirmations': 0, 
        'cancellations': 0,
        'requests': 0,
        'errors': 0,
        'total_concerts': 0
    }

    today = datetime.datetime.now()
    log_files = [
        f"concert_booking_{today.strftime('%d_%m_%Y')}.log",
        f"test_run_{today.strftime('%Y%m%d')}.log"
    ]

    for log_file in log_files:
        if not os.path.exists(log_file):
            continue
            
        with open(log_file) as f:
            for line in f:
                if "Successfully retrieved" in line:
                    metrics['retrievals'] += 1
                    match = re.search(r"retrieved (\d+) concerts", line)
                    if match:
                        metrics['total_concerts'] += int(match.group(1))
                elif "HTTP Request:" in line:
                    metrics['requests'] += 1
                elif "Successfully confirmed ticket" in line:
                    metrics['confirmations'] += 1
                elif "Successfully cancelled ticket" in line:
                    metrics['cancellations'] += 1
                elif "ERROR" in line:
                    metrics['errors'] += 1

    print_report(metrics)
    return metrics

def print_report(metrics):
    """Prints a simple report of the metrics."""
    print("\nLog Analysis Summary")
    print("-" * 30)
    print(f"HTTP Requests: {metrics['requests']}")
    print(f"Concert Retrievals: {metrics['retrievals']}")
    print(f"Total Concerts: {metrics['total_concerts']}")
    print(f"Confirmations: {metrics['confirmations']}")
    print(f"Cancellations: {metrics['cancellations']}")
    print(f"Errors: {metrics['errors']}")
    success_rate = calculate_success_rate(metrics)
    print(f"Success Rate: {success_rate:.1f}%")

def calculate_success_rate(metrics):
    """Calculates success rate percentage."""
    total = metrics['retrievals'] + metrics['confirmations'] + metrics['cancellations']
    if total == 0:
        return 100.0
    return ((total - metrics['errors']) / total) * 100

if __name__ == '__main__':
    analyze_logs()
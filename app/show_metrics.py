import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import subprocess

def analyze_jmeter_results(results_file):
    """
    Analyzes JMeter test results from a JTL file and generates comprehensive metrics
    
    Args:
        results_file: Path to the JTL file containing JMeter results
    Returns:
        Dictionary containing various performance metrics
    """
    # Read the JTL file into a pandas DataFrame
    df = pd.read_csv(results_file)
    
    # Convert timestamp to datetime for better analysis
    df['timeStamp'] = pd.to_datetime(df['timeStamp'], unit='ms')
    
    # Calculate basic metrics
    total_requests = len(df)
    successful_requests = len(df[df['responseCode'] == 200])
    availability = (successful_requests / total_requests) * 100
    
    # Calculate reliability (responses under 1000ms threshold)
    reliable_requests = len(df[(df['responseCode'] == 200) & (df['Latency'] <= 1000)])
    reliability = (reliable_requests / total_requests) * 100
    
    # Try to get code coverage, default to 0 if it fails
    try:
        pytest_cmd = ['python', '-m', 'pytest', '--cov=app', 'app/test_api.py']
        pytest_output = subprocess.run(pytest_cmd, capture_output=True, text=True)
        coverage_lines = [line for line in pytest_output.stdout.split('\n') if '%' in line]
        coverage_percent = float(coverage_lines[-1].split()[-1].strip('%')) if coverage_lines else 0
    except Exception:
        coverage_percent = 0
    
    # Calculate detailed latency metrics
    latency_metrics = {
        'avg_latency': df['Latency'].mean(),
        'max_latency': df['Latency'].max(),
        'min_latency': df['Latency'].min(),
        'p95_latency': df['Latency'].quantile(0.95),
        'p99_latency': df['Latency'].quantile(0.99)
    }
    
    # Calculate throughput (requests per second)
    duration = (df['timeStamp'].max() - df['timeStamp'].min()).total_seconds()
    throughput = total_requests / duration if duration > 0 else 0
    
    # Generate visualizations
    create_latency_plot(df)
    
    return {
        'total_requests': total_requests,
        'successful_requests': successful_requests,
        'availability': availability,
        'reliability': reliability,
        'code_coverage': coverage_percent,
        'throughput': throughput,
        **latency_metrics
    }

def create_latency_plot(df):
    """
    Creates a visualization of latency distribution over time
    """
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x='timeStamp', y='Latency')
    plt.title('Response Latency Over Time')
    plt.xlabel('Time')
    plt.ylabel('Latency (ms)')
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Create output directory if it doesn't exist
    output_dir = Path('app/tests/out/plots')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    plt.savefig(output_dir / 'latency_distribution.png')
    plt.close()

def format_results_report(results):
    """
    Formats the analysis results into a readable report
    """
    report = f"""
Performance Test Results
-----------------------
Total Requests: {results['total_requests']}
Successful Requests: {results['successful_requests']}

Performance Metrics:
- Availability: {results['availability']:.2f}%
- Reliability: {results['reliability']:.2f}%
- Code Coverage: {results['code_coverage']:.2f}%

Latency Analysis:
- Average: {results['avg_latency']:.2f}ms
- Maximum: {results['max_latency']:.2f}ms
- Minimum: {results['min_latency']:.2f}ms
- 95th Percentile: {results['p95_latency']:.2f}ms
- 99th Percentile: {results['p99_latency']:.2f}ms

Throughput: {results['throughput']:.2f} requests/second

A latency distribution plot has been saved to:
app/tests/out/plots/latency_distribution.png
"""
    return report

if __name__ == '__main__':
    # Analyze results
    results = analyze_jmeter_results('tests/out/results.jtl')
    
    # Generate and display report
    report = format_results_report(results)
    print(report)
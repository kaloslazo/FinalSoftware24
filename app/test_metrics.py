# test_metrics.py
import pandas as pd
import numpy as np
import pytest
import logging
from datetime import datetime
from pathlib import Path

class TestMetricsCollector:
    def __init__(self):
        self.results_file = Path("./tests/out/results.jtl")
        self.coverage_file = Path("./coverage/coverage.txt")
        self.setup_logging()

    def setup_logging(self):
        """Configure logging for metrics collection"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'metrics_{datetime.now().strftime("%Y%m%d")}.log'),
                logging.StreamHandler()
            ]
        )

    def run_all_tests(self):
        """Execute all tests and collect metrics"""
        # Run pytest with coverage
        pytest.main([
            '--cov=app',
            '--cov-report=html',
            '--cov-report=term-missing',
            'tests/',
            '-v'
        ])

    def calculate_metrics(self):
        """Calculate performance metrics from test results"""
        try:
            # Read test results
            df = pd.read_csv(self.results_file)
            
            # Calculate metrics
            total_requests = len(df)
            successful_requests = len(df[df['responseCode'] == 200])
            availability = (successful_requests / total_requests) * 100
            
            reliable_requests = len(df[(df['responseCode'] == 200) & (df['Latency'] <= 1000)])
            reliability = (reliable_requests / total_requests) * 100
            
            # Get code coverage
            coverage = 0
            if self.coverage_file.exists():
                with open(self.coverage_file, 'r') as f:
                    coverage = float(f.read().strip())
            
            metrics = {
                'availability': availability,
                'reliability': reliability,
                'code_coverage': coverage,
                'avg_latency': df['Latency'].mean(),
                'max_latency': df['Latency'].max()
            }
            
            self.display_metrics(metrics)
            return metrics
            
        except Exception as e:
            logging.error(f"Error calculating metrics: {str(e)}")
            raise

    def display_metrics(self, metrics):
        """Display formatted metrics report"""
        report = f"""
        Test Metrics Report
        ==================
        Code Coverage: {metrics['code_coverage']:.2f}%
        API Availability: {metrics['availability']:.2f}%
        Service Reliability: {metrics['reliability']:.2f}%
        Average Latency: {metrics['avg_latency']:.2f}ms
        Maximum Latency: {metrics['max_latency']:.2f}ms
        
        Coverage Target: {'✅' if metrics['code_coverage'] >= 90 else '❌'} 90%
        """
        print(report)
        logging.info(report)

if __name__ == '__main__':
    collector = TestMetricsCollector()
    collector.run_all_tests()
    collector.calculate_metrics()
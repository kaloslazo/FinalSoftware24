import os
import subprocess
import pytest
import logging
from datetime import datetime
from pathlib import Path

class TestRunner:
    def __init__(self):
        self.setup_directories()
        self.setup_logging()
        
    def setup_directories(self):
        """Create necessary directories if they don't exist"""
        Path("tests/out").mkdir(parents=True, exist_ok=True)
        Path("coverage").mkdir(exist_ok=True)
        Path("tests/jmeter").mkdir(parents=True, exist_ok=True)
        
    def setup_logging(self):
        """Configure logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'test_run_{datetime.now().strftime("%Y%m%d")}.log'),
                logging.StreamHandler()
            ]
        )

    def clean_previous_results(self):
        """Clean up previous test results"""
        logging.info("Cleaning previous test results...")
        try:
            subprocess.run(["rm", "-rf", "tests/out/*"], check=True)
            subprocess.run(["rm", "-rf", "coverage/*"], check=True)
            subprocess.run(["rm", "-rf", "htmlcov/*"], check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Error cleaning previous results: {str(e)}")
            raise

    def run_unit_tests(self):
        """Run unit tests with coverage"""
        logging.info("Running unit tests with coverage...")
        result = pytest.main([
            '--cov=app',
            '--cov-report=html',
            '--cov-report=term-missing',
            '--cov-report=xml:coverage/coverage.xml',
            'tests/integration',
            '-v'
        ])
        
        # Save coverage percentage
        if os.path.exists("coverage/coverage.xml"):
            import xml.etree.ElementTree as ET
            tree = ET.parse("coverage/coverage.xml")
            root = tree.getroot()
            coverage = float(root.attrib['line-rate']) * 100
            with open("coverage/coverage.txt", "w") as f:
                f.write(str(coverage))
        
        return result == 0

    def run_performance_tests(self):
        """Run JMeter performance tests"""
        logging.info("Running JMeter performance tests...")
        try:
            result = subprocess.run([
                "jmeter",
                "-n",
                "-t", "tests/jmeter/test_plan.jmx",
                "-l", "tests/out/results.jtl"
            ], check=True)
            return True
        except subprocess.CalledProcessError as e:
            logging.error(f"Error running JMeter tests: {str(e)}")
            return False

    def calculate_metrics(self):
        """Calculate and display test metrics"""
        from calculate_metrics import calculate_metrics
        try:
            results = calculate_metrics("tests/out/results.jtl")
            logging.info("\nTest Results Summary:")
            logging.info("-" * 40)
            for metric, value in results.items():
                logging.info(f"{metric}: {value:.2f}")
            return results
        except Exception as e:
            logging.error(f"Error calculating metrics: {str(e)}")
            raise

    def run_all_tests(self):
        """Execute complete test suite"""
        try:
            logging.info("Starting test execution...")
            
            # 1. Clean previous results
            self.clean_previous_results()
            
            # 2. Run unit tests with coverage
            if not self.run_unit_tests():
                logging.error("Unit tests failed!")
                return False
                
            # 3. Run performance tests
            if not self.run_performance_tests():
                logging.error("Performance tests failed!")
                return False
                
            # 4. Calculate and display metrics
            metrics = self.calculate_metrics()
            
            # Check coverage target
            if metrics['code_coverage'] < 90:
                logging.warning("Code coverage is below 90% target!")
                return False
                
            logging.info("All tests completed successfully!")
            return True
            
        except Exception as e:
            logging.error(f"Error during test execution: {str(e)}")
            return False

if __name__ == "__main__":
    runner = TestRunner()
    success = runner.run_all_tests()
    exit(0 if success else 1)
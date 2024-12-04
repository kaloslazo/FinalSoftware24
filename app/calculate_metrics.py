import pandas as pd
import numpy as np

def calculate_metrics(results_file):
    df = pd.read_csv(results_file)

    # availability (% de respuestas exitosas)
    total_requests = len(df)
    successful_requests = len(df['responseCode'] == 200)
    print(successful_requests)
    availability = (successful_requests / total_requests) * 100

    # reliability (% de respuestas correctas y a tiempo)
    reliable_requests = len((df['responseCode'] == 200) & (df['Latency'] <= 1000))
    reliability = (reliable_requests / total_requests) * 100

    coverage = 0
    try:
        with open('coverage/coverage.txt', 'r') as f:
            coverage = float(f.read().strip())
    except:
        pass

    avg_latency = df['Latency'].mean()
    max_latency = df['Latency'].max()

    return {
        'availability': availability,
        'reliability': reliability,
        'code_coverage': coverage,
        'avg_latency': avg_latency,
        'max_latency': max_latency
    }

if __name__ == '__main__':
    results = calculate_metrics('./app/tests/out/results.jtl')

    print(f"""
    Resultados de las Pruebas:
    -------------------------
    Availability: {results['availability']:.2f}%
    Reliability: {results['reliability']:.2f}%
    Code Coverage: {results['code_coverage']:.2f}%
    Latencia Promedio: {results['avg_latency']:.2f}ms
    Latencia Máxima: {results['max_latency']:.2f}ms
    """)

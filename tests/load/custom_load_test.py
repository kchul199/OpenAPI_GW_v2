import asyncio
import time
import statistics
from collections import Counter
import httpx

# Configuration
TARGET_URL = "http://localhost:8080/_health"
CONCURRENT_USERS = 200
DURATION_SECONDS = 30
REQUEST_TIMEOUT = 5.0

class LoadTestResults:
    def __init__(self):
        self.latencies = []
        self.status_codes = Counter()
        self.errors = 0
        self.start_time = 0
        self.end_time = 0

    def record_success(self, latency, status_code):
        self.latencies.append(latency)
        self.status_codes[status_code] += 1

    def record_error(self):
        self.errors += 1

    def report(self):
        total_requests = len(self.latencies) + self.errors
        duration = self.end_time - self.start_time
        rps = total_requests / duration if duration > 0 else 0
        
        print("\n" + "="*50)
        print(" LOAD TEST REPORT")
        print("="*50)
        print(f"Target URL:        {TARGET_URL}")
        print(f"Concurrency:       {CONCURRENT_USERS}")
        print(f"Duration:          {duration:.2f}s")
        print(f"Total Requests:    {total_requests}")
        print(f"Avg RPS:           {rps:.2f}")
        print(f"Error Rate:        {(self.errors/total_requests)*100:.2f}%" if total_requests > 0 else "N/A")
        
        if self.latencies:
            print("-" * 50)
            print(f"Latency Avg:       {statistics.mean(self.latencies)*1000:.2f}ms")
            print(f"Latency Median:    {statistics.median(self.latencies)*1000:.2f}ms")
            print(f"Latency P95:       {statistics.quantiles(self.latencies, n=20)[18]*1000:.2f}ms")
            print(f"Latency P99:       {statistics.quantiles(self.latencies, n=100)[98]*1000:.2f}ms")
            print("-" * 50)
            print("Status Codes:")
            for code, count in sorted(self.status_codes.items()):
                print(f"  {code}: {count}")
        print("="*50 + "\n")

async def worker(client, results, stop_event):
    while not stop_event.is_set():
        start = time.perf_counter()
        try:
            resp = await client.get(TARGET_URL, timeout=REQUEST_TIMEOUT)
            latency = time.perf_counter() - start
            results.record_success(latency, resp.status_code)
        except Exception:
            results.record_error()

async def run_load_test():
    results = LoadTestResults()
    stop_event = asyncio.Event()
    
    print(f"Starting load test on {TARGET_URL} with {CONCURRENT_USERS} users for {DURATION_SECONDS}s...")
    
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=CONCURRENT_USERS)) as client:
        results.start_time = time.perf_counter()
        
        workers = [asyncio.create_task(worker(client, results, stop_event)) for _ in range(CONCURRENT_USERS)]
        
        await asyncio.sleep(DURATION_SECONDS)
        stop_event.set()
        
        await asyncio.gather(*workers)
        results.end_time = time.perf_counter()
        
    results.report()

if __name__ == "__main__":
    asyncio.run(run_load_test())

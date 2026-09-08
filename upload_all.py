import os
import sys
import time
import requests

pdf_dirs = [
    r'c:\Users\Dell\OneDrive\Desktop\superjoin2\starter-datasets\starter-datasets\delhivery',
    r'c:\Users\Dell\OneDrive\Desktop\superjoin2\starter-datasets\starter-datasets\india-macroeconomy',
]

print("Starting upload of starter PDFs...", flush=True)

for d in pdf_dirs:
    for f in sorted(os.listdir(d)):
        if f.endswith('.pdf'):
            path = os.path.join(d, f)
            print(f"\nUploading {f} ({os.path.getsize(path)/1024:.1f} KB)...", flush=True)
            t0 = time.time()
            with open(path, 'rb') as fp:
                resp = requests.post(
                    'http://localhost:8000/api/upload',
                    files={'file': (f, fp, 'application/pdf')},
                    timeout=120
                )
            elapsed = time.time() - t0
            if resp.status_code == 200:
                data = resp.json()
                print(f"  OK [{elapsed:.2f}s]: {data.get('facts_extracted', 0)} facts extracted, "
                      f"{data.get('relationships_detected', 0)} total cross-doc relationships detected", flush=True)
            else:
                print(f"  FAILED [{elapsed:.2f}s]: {resp.status_code} {resp.text[:200]}", flush=True)

print("\nAll starter PDFs processed!", flush=True)

# Final stats summary
stats = requests.get('http://localhost:8000/api/stats').json()
print("\nFinal Knowledge Layer Stats:", flush=True)
print(f"  Total Documents: {stats.get('documents', 0)}", flush=True)
print(f"  Total Facts: {stats.get('facts', 0)}", flush=True)
print(f"  Total Relationships: {stats.get('relationships', 0)}", flush=True)
print(f"  Relationship Types: {stats.get('relationship_breakdown', {})}", flush=True)
print(f"  Extraction Failures: {stats.get('failures', 0)}", flush=True)

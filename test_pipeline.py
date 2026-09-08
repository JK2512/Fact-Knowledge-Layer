import time
import os
from backend.pdf_parser import PDFParser
from backend.fact_extractor import FactExtractor
from backend.fact_linker import FactLinker
from backend.models import Document

path = r'c:\Users\Dell\OneDrive\Desktop\superjoin2\starter-datasets\starter-datasets\delhivery\03-delhivery-q4-fy24-earnings-presentation.pdf'
print(f"Testing on {os.path.basename(path)} (size: {os.path.getsize(path)/1024:.1f} KB)...", flush=True)

t0 = time.time()
with PDFParser(path) as parser:
    t_open = time.time()
    print(f"Opened doc in {t_open-t0:.3f}s, pages: {parser.page_count}", flush=True)
    
    pages = parser.extract_all_text()
    t_text = time.time()
    print(f"Extracted text in {t_text-t_open:.3f}s", flush=True)
    
    tables = parser.extract_all_tables()
    t_tables = time.time()
    print(f"Extracted tables in {t_tables-t_text:.3f}s, table pages: {len(tables)}", flush=True)
    
    title = parser.get_title()
    meta = parser.get_metadata()

extractor = FactExtractor()
t_ext0 = time.time()
facts, failures = extractor.extract(pages, tables, 'test-doc-1', title)
t_ext1 = time.time()
print(f"Extracted {len(facts)} facts, {len(failures)} failures in {t_ext1-t_ext0:.3f}s", flush=True)

print("Sample facts:", flush=True)
for f in facts[:5]:
    print(f"  [{f.fact_type}] {f.subject} | {f.predicate} | {f.value} | {f.time_period} | conf: {f.confidence:.2f}", flush=True)

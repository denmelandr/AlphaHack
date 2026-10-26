"""Export the live schema to both compatibility locations."""
import argparse
import json
from pathlib import Path
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-url', default='http://localhost:8080')
args = parser.parse_args()
with urllib.request.urlopen(args.base_url.rstrip('/')+'/openapi.json', timeout=30) as response:
    spec = json.load(response)
if 'openapi' not in spec or 'paths' not in spec:
    raise SystemExit('Response is not an OpenAPI schema')
root = Path(__file__).resolve().parents[1]
for relative in ['docs/openapi.json', 'credit-conveyor/docs/openapi.json']:
    (root / relative).write_text(json.dumps(spec, ensure_ascii=False, indent=2)+'\n')
print(f"Exported {len(spec['paths'])} API paths")

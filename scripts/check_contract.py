"""Validate snapshot, collection routes and (optionally) the live API schema."""
import argparse
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--base-url', default='http://localhost:8080')
    args = parser.parse_args()
    spec = json.loads((ROOT / 'docs/openapi.json').read_text())
    nested = json.loads((ROOT / 'credit-conveyor/docs/openapi.json').read_text())
    if spec != nested:
        raise SystemExit('FAIL: OpenAPI copies differ; run export_openapi.py')
    def shape(path):
        return re.sub(r'\{[^}]+\}', '{id}', path)
    operations = {(method.upper(), shape(path)) for path, methods in spec['paths'].items() for method in methods if method in {'get','post','patch','put','delete'}}
    collection = json.loads((ROOT / 'docs/postman_collection.json').read_text())
    other = json.loads((ROOT / 'credit-conveyor/docs/postman_collection.json').read_text())
    if collection != other:
        raise SystemExit('FAIL: Postman copies differ')
    for item in collection['item']:
        r = item['request']
        path = re.sub(r'\{\{\w+\}\}', '{id}', r['url'].removeprefix('{{base_url}}'))
        if (r['method'], shape(path)) not in operations:
            raise SystemExit(f"FAIL: unknown operation in {item['name']}")
        if 'body' in r:
            json.loads(r['body']['raw'])
    if args.live:
        with urllib.request.urlopen(args.base_url.rstrip('/')+'/openapi.json', timeout=30) as response:
            live = json.load(response)
        if spec != live:
            raise SystemExit('FAIL: snapshot differs from live OpenAPI')
    print(f"PASS: {len(spec['paths'])} paths, {len(operations)} operations, {len(collection['item'])} collection requests" + ('; live schema matches' if args.live else ''))

if __name__ == '__main__':
    main()

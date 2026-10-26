"""Run the checked-in Postman requests using only Python's standard library."""
import argparse
import json
from pathlib import Path
import re
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://localhost:8080')
    args = parser.parse_args()
    collection = json.loads((ROOT / 'docs/postman_collection.json').read_text())
    variables = {v['key']: v['value'] for v in collection['variable']}
    variables['base_url'] = args.base_url.rstrip('/')

    def expand(text):
        return re.sub(r'\{\{(\w+)\}\}', lambda m: str(variables[m[1]]), text)

    def body_value(value):
        if isinstance(value, dict):
            return {k: body_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [body_value(v) for v in value]
        if isinstance(value, str):
            match = re.fullmatch(r'\{\{(\w+)\}\}', value)
            if match:
                resolved = variables[match[1]]
                return int(resolved) if match[1].endswith('_id') else resolved
            return expand(value)
        return value

    for item in collection['item']:
        request = item['request']
        headers = {h['key']: expand(h['value']) for h in request.get('header', [])}
        body = request.get('body')
        data = json.dumps(body_value(json.loads(body['raw']))).encode() if body else None
        req = urllib.request.Request(expand(request['url']), data=data, headers=headers, method=request['method'])
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                status, result = response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            # No credentials, headers or response bodies in output.
            raise SystemExit(f"FAIL {item['name']}: HTTP {exc.code}") from None
        except urllib.error.URLError as exc:
            raise SystemExit(f"API unavailable: {exc.reason}") from None
        if status != item['x-alpha']['status']:
            raise SystemExit(f"FAIL {item['name']}: unexpected HTTP {status}")
        for key, selector in item['x-alpha']['extract'].items():
            if selector == 'first_servicing_id':
                value = next((a['id'] for a in result if a['state'] in ['SERVICING', 'DISBURSED']), None)
                if value is None:
                    raise SystemExit('No servicing seed credit found')
            else:
                value = result
                for part in selector.split('.'):
                    value = value[int(part)] if part.isdigit() else value[part]
            variables[key] = value
        print(f"OK {item['name']}: HTTP {status}")
    print(f"PASS: {len(collection['item'])} requests; synthetic application id={variables['app_id']}")

if __name__ == '__main__':
    main()

"""Download licensed Google Fonts handwriting assets and retain their licenses."""
import concurrent.futures
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'data' / 'handwriting_fonts'
FAMILIES = ['allura','dancingscript','caveat','marckscript','badscript','sacramento',
            'kalam','patrickhand','handlee','shadowsintolight','satisfy','parisienne',
            'amiri','arefruqaa','lateef','scheherazadenew','reemkufi','mirza']

def fetch(family):
    folder = ROOT / family
    folder.mkdir(parents=True, exist_ok=True)
    category='apache' if family=='satisfy' else 'ofl'
    base = f'https://raw.githubusercontent.com/google/fonts/main/{category}/{family}/'
    metadata = urllib.request.urlopen(base+'METADATA.pb', timeout=30).read().decode()
    import re
    names = re.findall(r'filename: "([^"]+)"', metadata)
    selected=next((n for n in names if 'Regular' in n),names[0])
    for name in [selected, 'LICENSE.txt' if category=='apache' else 'OFL.txt']:
        target = folder/name
        if not target.exists():
            target.write_bytes(urllib.request.urlopen(base+urllib.parse.quote(name), timeout=30).read())
    return {'family':family, 'file':str(folder/selected), 'source':base, 'license':'Apache-2.0' if category=='apache' else 'OFL-1.1'}

if __name__ == '__main__':
    import urllib.parse
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(fetch,FAMILIES))
    (ROOT/'sources.json').write_text(json.dumps(results,indent=2)+'\n')
    print(f'Downloaded {len(results)} font families with licenses')

"""Download and inspect the Mobility Database Delhi DTC feed (mdb-1262) and probe DMRC."""
import urllib.request
import urllib.error
import zipfile
import io
import os
import hashlib
import json
from datetime import datetime

HEADERS = {'User-Agent': 'Mozilla/5.0 SafarSetu/0.1 (transit research)'}

def download_and_inspect(url, label, mdb_id):
    out_dir = f'data/raw/{mdb_id}'
    meta_dir = 'data/metadata'
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(meta_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Downloading {label}: {url}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=120)
        data = resp.read()
    except urllib.error.HTTPError as e:
        print(f"HTTP ERROR {e.code}: {e.reason}")
        return None
    except Exception as ex:
        print(f"ERROR: {ex}")
        return None

    print(f"Downloaded {len(data):,} bytes")
    sha256 = hashlib.sha256(data).hexdigest()
    print(f"SHA-256: {sha256}")

    zip_path = os.path.join(out_dir, f'{mdb_id}-latest.zip')
    with open(zip_path, 'wb') as f:
        f.write(data)
    print(f"Saved: {zip_path}")

    try:
        buf = io.BytesIO(data)
        with zipfile.ZipFile(buf, 'r') as zf:
            print(f"\nZIP files: {zf.namelist()}")
            
            file_stats = {}
            for fname in zf.namelist():
                try:
                    content = zf.read(fname).decode('utf-8', errors='replace')
                    lines = [l for l in content.strip().split('\n') if l.strip()]
                    rows = len(lines) - 1
                    header = lines[0][:200] if lines else ''
                    sample = lines[1][:200] if len(lines) > 1 else '(empty)'
                    file_stats[fname] = {'rows': rows}
                    print(f"\n  {fname} ({rows:,} rows)")
                    print(f"    HDR: {header}")
                    print(f"    R1:  {sample}")
                except Exception as ex:
                    print(f"  {fname}: READ ERROR {ex}")

            zf.extractall(out_dir)
            print(f"\nExtracted to {out_dir}")

            # Check feed_info.txt for dates
            if 'feed_info.txt' in zf.namelist():
                fi = zf.read('feed_info.txt').decode('utf-8', errors='replace')
                print(f"\nfeed_info.txt:\n{fi}")

        meta = {
            'source': 'Mobility Database',
            'mdb_id': mdb_id,
            'label': label,
            'url': url,
            'downloaded_at': datetime.utcnow().isoformat() + 'Z',
            'size_bytes': len(data),
            'sha256': sha256,
        }
        meta_path = os.path.join(meta_dir, f'{mdb_id}-metadata.json')
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2)
        print(f"Metadata: {meta_path}")
        return meta

    except zipfile.BadZipFile as e:
        print(f"BAD ZIP: {e}")
        # Print first bytes to diagnose
        print(f"First 200 bytes: {data[:200]!r}")
        return None


# Delhi DTC Bus
download_and_inspect(
    'https://files.mobilitydatabase.org/mdb-1262/latest.zip',
    'Delhi Transport Corporation (DTC) Bus',
    'mdb-1262'
)

# Try nearby IDs for DMRC metro
for mdb_id in ['mdb-1263', 'mdb-1264', 'mdb-1265', 'mdb-1494', 'mdb-1260', 'mdb-1261']:
    url = f'https://files.mobilitydatabase.org/{mdb_id}/latest.zip'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=10)
        ctype = resp.headers.get('Content-Type', '?')
        clen = resp.headers.get('Content-Length', '?')
        data_first = resp.read(200)
        print(f"\n  {mdb_id}: OK type={ctype} len={clen} magic={data_first[:4].hex()}")
        if data_first[:2] == b'PK':
            print(f"  => Valid ZIP for {mdb_id}")
    except urllib.error.HTTPError as e:
        print(f"  {mdb_id}: HTTP {e.code}")
    except Exception as ex:
        print(f"  {mdb_id}: ERR {ex}")


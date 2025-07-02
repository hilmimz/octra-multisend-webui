import json, base64, hashlib, time, random, asyncio
import aiohttp
from datetime import datetime, timedelta
import nacl.signing

μ = 1_000_000
session = None

priv = addr = rpc = None
sk = pub = None

h = []  # history
cb, cn, lu, lh = None, None, 0, 0

def ld():
    global priv, addr, rpc, sk, pub
    try:
        with open('wallet.json', 'r') as f:
            d = json.load(f)
        priv = d.get('priv')
        addr = d.get('addr')
        rpc = d.get('rpc', 'https://octra.network')
        sk = nacl.signing.SigningKey(base64.b64decode(priv))
        pub = base64.b64encode(sk.verify_key.encode()).decode()
        return True
    except:
        return False

async def req(m, p, d=None, t=10):
    global session
    if not session:
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=t))
    try:
        url = f"{rpc}{p}"
        async with getattr(session, m.lower())(url, json=d if m == 'POST' else None) as resp:
            text = await resp.text()
            try:
                j = json.loads(text) if text else None
            except:
                j = None
            return resp.status, text, j
    except asyncio.TimeoutError:
        return 0, "timeout", None
    except Exception as e:
        return 0, str(e), None

async def st():
    global cb, cn, lu
    now = time.time()
    if cb is not None and (now - lu) < 30:
        return cn, cb
    
    results = await asyncio.gather(
        req('GET', f'/balance/{addr}'),
        req('GET', '/staging', 5),
        return_exceptions=True
    )
    
    s, t, j = results[0] if not isinstance(results[0], Exception) else (0, str(results[0]), None)
    s2, _, j2 = results[1] if not isinstance(results[1], Exception) else (0, None, None)
    
    if s == 200 and j:
        cn = int(j.get('nonce', 0))
        cb = float(j.get('balance', 0))
        lu = now
        if s2 == 200 and j2:
            our = [tx for tx in j2.get('staged_transactions', []) if tx.get('from') == addr]
            if our:
                cn = max(cn, max(int(tx.get('nonce', 0)) for tx in our))
    elif s == 404:
        cn, cb, lu = 0, 0.0, now
    elif s == 200 and t and not j:
        try:
            parts = t.strip().split()
            if len(parts) >= 2:
                cb = float(parts[0]) if parts[0].replace('.', '').isdigit() else 0.0
                cn = int(parts[1]) if parts[1].isdigit() else 0
                lu = now
            else:
                cn, cb = None, None
        except:
            cn, cb = None, None
    return cn, cb

async def gh():
    global h, lh
    now = time.time()
    if now - lh < 60 and h:
        return
    s, t, j = await req('GET', f'/address/{addr}?limit=20')
    if s != 200 or (not j and not t):
        return
    
    if j and 'recent_transactions' in j:
        tx_hashes = [ref["hash"] for ref in j.get('recent_transactions', [])]
        tx_results = await asyncio.gather(*[req('GET', f'/tx/{hash}', 5) for hash in tx_hashes], return_exceptions=True)
        
        existing_hashes = {tx['hash'] for tx in h}
        nh = []
        
        for i, (ref, result) in enumerate(zip(j.get('recent_transactions', []), tx_results)):
            if isinstance(result, Exception):
                continue
            s2, _, j2 = result
            if s2 == 200 and j2 and 'parsed_tx' in j2:
                p = j2['parsed_tx']
                tx_hash = ref['hash']
                
                if tx_hash in existing_hashes:
                    continue
                
                ii = p.get('to') == addr
                ar = p.get('amount_raw', p.get('amount', '0'))
                a = float(ar) if '.' in str(ar) else int(ar) / μ
                msg = None
                if 'data' in j2:
                    try:
                        data = json.loads(j2['data'])
                        msg = data.get('message')
                    except:
                        pass
                nh.append({
                    'time': datetime.fromtimestamp(p.get('timestamp', 0)),
                    'hash': tx_hash,
                    'amt': a,
                    'to': p.get('to') if not ii else p.get('from'),
                    'type': 'in' if ii else 'out',
                    'ok': True,
                    'nonce': p.get('nonce', 0),
                    'epoch': ref.get('epoch', 0),
                    'msg': msg
                })
        
        oh = datetime.now() - timedelta(hours=1)
        h[:] = sorted(nh + [tx for tx in h if tx.get('time', datetime.now()) > oh], key=lambda x: x['time'], reverse=True)[:50]
        lh = now
    elif s == 404 or (s == 200 and t and 'no transactions' in t.lower()):
        h.clear()
        lh = now

def mk(to, a, n, msg=None):
    tx = {
        "from": addr,
        "to_": to,
        "amount": str(int(a * μ)),
        "nonce": int(n),
        "ou": "1" if a < 1000 else "3",
        "timestamp": time.time() + random.random() * 0.01
    }
    if msg:
        tx["message"] = msg
    bl = json.dumps({k: v for k, v in tx.items() if k != "message"}, separators=(",", ":"))
    sig = base64.b64encode(sk.sign(bl.encode()).signature).decode()
    tx.update(signature=sig, public_key=pub)
    return tx, hashlib.sha256(bl.encode()).hexdigest()

async def snd(tx):
    t0 = time.time()
    s, t, j = await req('POST', '/send-tx', tx)
    dt = time.time() - t0
    if s == 200:
        if j and j.get('status') == 'accepted':
            return True, j.get('tx_hash', ''), dt, j
        elif t.lower().startswith('ok'):
            return True, t.split()[-1], dt, None
    return False, json.dumps(j) if j else t, dt, j

def get_wallet_info():
    return addr, pub

async def get_wallet_summary():
    n, b = await st()
    await gh()
    
    # Get staged txs
    _, _, j = await req('GET', '/staging', 2)
    sc = len([tx for tx in j.get('staged_transactions', []) if tx.get('from') == addr]) if j else 0

    # Ringkasan transaksi
    txs = []
    seen_hashes = set()
    sorted_h = sorted(h, key=lambda x: x['time'], reverse=True)
    for tx in sorted_h:
        if tx['hash'] in seen_hashes:
            continue
        seen_hashes.add(tx['hash'])

        txs.append({
            "time": tx['time'].strftime('%Y-%m-%d %H:%M:%S'),
            "type": tx['type'],
            "amount": float(tx['amt']),
            "address": tx.get('to', '---'),
            "msg": tx.get('msg'),
            "epoch": tx.get('epoch', 0),
            "status": "pending" if not tx.get('epoch') else f"e{tx.get('epoch', 0)}"
        })

    return {
        "address": addr,
        "public_key": pub,
        "balance": b,
        "nonce": n,
        "pending_count": sc,
        "transactions": txs
    }

async def get_pending_count():
    _, _, j = await req('GET', '/staging', 2)
    sc = len([tx for tx in j.get('staged_transactions', []) if tx.get('from') == addr]) if j else 0
    return sc
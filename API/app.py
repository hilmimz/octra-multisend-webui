import asyncio
from flask import Flask, jsonify, request
from cli import ld, get_wallet_info, st, mk, snd, get_wallet_summary, get_pending_count, addr
from flask_cors import CORS

# Inisialisasi Flask
app = Flask(__name__)
CORS(app)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Load wallet saat app dinyalakan
@app.before_request
def load_wallet():
    if not ld():
        raise RuntimeError("Gagal memuat wallet.json")
    

@app.route("/wallet/info", methods=["GET"])
async def wallet_info():
    address, public_key = get_wallet_info()
    return jsonify({
        "address": address,
        "public_key": public_key
    })

@app.route("/wallet/balance", methods=["GET"])
def wallet_balance():
    address, _ = get_wallet_info()
    nonce, balance = loop.run_until_complete(st())
    return jsonify({
        "address": address,
        "nonce": nonce,
        "balance": balance
    })

@app.route("/wallet/send", methods=["POST"])
def wallet_send():
    try:
        data = request.get_json()
        to = data.get("to")
        amount = float(data.get("amount"))
        message = data.get("message", None)
        nonce = data.get("nonce")

        if not to or not amount:
            return jsonify({"error": "Missing parameters"}), 400

        tx, tx_hash = mk(to, amount, nonce+1, msg=message)

        success, result, duration, response = loop.run_until_complete(snd(tx))

        if success:
            return jsonify({
                "success": True,
                "tx_hash": result,
                "duration": duration
            })
        else:
            return jsonify({
                "success": False,
                "error": result,
                "duration": duration
            }), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/wallet/summary", methods=["GET"])
def wallet_summary():
    try:
        result = loop.run_until_complete(get_wallet_summary())
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/wallet/pending-count", methods=["GET"])
def pending_count():
    count = loop.run_until_complete(get_pending_count())
    return jsonify({"pending_count": count})

if __name__ == "__main__":
    app.run(port=5000)
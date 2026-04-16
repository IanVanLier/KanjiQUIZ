import json
import os
import random
import glob
import io
import zipfile
from flask import Flask, render_template, request, jsonify, send_file
import genanki

app = Flask(__name__)

# --- Configuration ---
RANKS = ["Student", "Trainee", "Debut Idol", "Major Idol", "Prima Idol", 
         "Divine Idol", "Eternal Idol", "Immortal Idol", "Owner"]
STATS_FILE = 'tmw_comprehensive_stats.json'
CUSTOM_STATS_FILE = 'custom_stats.json'
MAP_FILE = 'readings_map.json'
CUSTOM_BANK = 'term_meta_bank_Custom.json'

def load_extra_readings():
    """Loads the readings_map.json for alternative readings."""
    if os.path.exists(MAP_FILE):
        with open(MAP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_standard_data():
    """Loads numbered banks, excluding the Custom bank to prevent cross-contamination."""
    extra_map = load_extra_readings()
    kanji_map = {} 
    json_files = [f for f in glob.glob("term_meta_bank_*.json") if "Custom" not in f]
    
    for fn in json_files:
        with open(fn, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                for entry in data:
                    kanji, meta = entry[0], entry[2]
                    rank = meta.get('frequency', {}).get('displayValue')
                    if rank in RANKS and kanji not in kanji_map:
                        alts = list(set(extra_map.get(kanji, [])))
                        reading = meta.get('reading')
                        if reading in alts: alts.remove(reading)
                        kanji_map[kanji] = {'kanji': kanji, 'bank_reading': reading, 'alt_readings': alts, 'rank': rank}
            except: continue
    
    formatted = {rank: [] for rank in RANKS}
    for info in kanji_map.values():
        formatted[info['rank']].append(info)
    return formatted, kanji_map

def load_custom_only_data():
    """Loads ONLY the Custom bank file to ensure total separation."""
    extra_map = load_extra_readings()
    custom_list = []
    if not os.path.exists(CUSTOM_BANK):
        return []
    
    with open(CUSTOM_BANK, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            for entry in data:
                kanji, meta = entry[0], entry[2]
                alts = list(set(extra_map.get(kanji, [])))
                reading = meta.get('reading')
                if reading in alts: alts.remove(reading)
                custom_list.append({'kanji': kanji, 'bank_reading': reading, 'alt_readings': alts, 'rank': 'Custom'})
        except: pass
    return custom_list

def load_stats(is_custom=False):
    path = CUSTOM_STATS_FILE if is_custom else STATS_FILE
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    return {"Custom": {"failed": [], "passed": []}} if is_custom else {rank: {"failed": [], "passed": []} for rank in RANKS}

def save_stats(stats, is_custom=False):
    path = CUSTOM_STATS_FILE if is_custom else STATS_FILE
    with open(path, 'w', encoding='utf-8') as f: 
        json.dump(stats, f, ensure_ascii=False, indent=4)

# --- Routes ---

@app.route('/')
def home():
    std_data, _ = load_standard_data()
    std_stats = load_stats(is_custom=False)
    
    rank_info = {}
    for rank in RANKS:
        total = len(std_data[rank])
        rs = std_stats.get(rank, {"passed": [], "failed": []})
        rank_info[rank] = {"total": total, "passed": len(rs["passed"]), "failed": len(rs["failed"]), "unreviewed": max(0, total - (len(rs["passed"]) + len(rs["failed"])))}
    
    custom_data = load_custom_only_data()
    c_stats = load_stats(is_custom=True).get("Custom", {"passed": [], "failed": []})
    custom_info = {
        "total": len(custom_data),
        "passed": len(c_stats["passed"]),
        "failed": len(c_stats["failed"]),
        "unreviewed": max(0, len(custom_data) - (len(c_stats["passed"]) + len(c_stats["failed"])))
    }
    
    return render_template('home.html', rank_info=rank_info, custom_info=custom_info, ranks=RANKS, custom_exists=os.path.exists(CUSTOM_BANK))

@app.route('/api/import_custom', methods=['POST'])
def import_custom():
    if 'file' not in request.files: return jsonify({"error": "No file"}), 400
    content = request.files['file'].read().decode('utf-8')
    lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('=')]
    
    extra_map = load_extra_readings()
    custom_entries = []
    seen = set()
    for word in lines:
        if word in extra_map and word not in seen:
            custom_entries.append([word, "freq", {"reading": extra_map[word][0], "frequency": {"displayValue": "Custom"}}])
            seen.add(word)
    
    with open(CUSTOM_BANK, 'w', encoding='utf-8') as f:
        json.dump(custom_entries, f, ensure_ascii=False, separators=(',', ':'))
    return jsonify({"count": len(custom_entries)})

@app.route('/api/clear_custom', methods=['POST'])
def clear_custom():
    if os.path.exists(CUSTOM_BANK): os.remove(CUSTOM_BANK)
    if os.path.exists(CUSTOM_STATS_FILE): os.remove(CUSTOM_STATS_FILE)
    return jsonify({"status": "cleared"})

@app.route('/quiz/<rank>/<mode>')
def quiz(rank, mode):
    is_custom = (rank == "Custom")
    data = load_custom_only_data() if is_custom else load_standard_data()[0][rank]
    rs = load_stats(is_custom=is_custom).get(rank, {"passed": [], "failed": []})
    stats = {"total": len(data), "passed": len(rs["passed"]), "failed": len(rs["failed"]), "unreviewed": len(data) - (len(rs["passed"]) + len(rs["failed"]))}
    return render_template('quiz.html', rank=rank, mode=mode, stats=stats)

@app.route('/api/get_word/<rank>/<mode>')
def get_word(rank, mode):
    is_custom = (rank == "Custom")
    all_words = load_custom_only_data() if is_custom else load_standard_data()[0].get(rank, [])
    stats = load_stats(is_custom=is_custom).get(rank, {"passed": [], "failed": []})
    
    reviewed = set(stats["passed"] + stats["failed"])
    if mode == "unreviewed": candidates = [w for w in all_words if w['kanji'] not in reviewed]
    elif mode == "failures": candidates = [w for w in all_words if w['kanji'] in stats["failed"]]
    else: candidates = all_words

    if not candidates: return jsonify({"error": "Empty"}), 404
    return jsonify(random.choice(candidates))

@app.route('/api/report/<rank>', methods=['POST'])
def report(rank):
    is_custom = (rank == "Custom")
    data = request.json
    stats = load_stats(is_custom=is_custom)
    kanji = data['kanji']
    
    if rank not in stats: stats[rank] = {"failed": [], "passed": []}
    if data['correct']:
        if kanji in stats[rank]["failed"]: stats[rank]["failed"].remove(kanji)
        if kanji not in stats[rank]["passed"]: stats[rank]["passed"].append(kanji)
    else:
        if kanji not in stats[rank]["failed"]: stats[rank]["failed"].append(kanji)
        if kanji in stats[rank]["passed"]: stats[rank]["passed"].remove(kanji)
    
    save_stats(stats, is_custom=is_custom)
    total_len = len(load_custom_only_data() if is_custom else load_standard_data()[0][rank])
    return jsonify({"status": "ok", "new_stats": {
        "total": total_len, "passed": len(stats[rank]["passed"]), "failed": len(stats[rank]["failed"]), 
        "unreviewed": total_len - (len(stats[rank]["passed"]) + len(stats[rank]["failed"]))
    }})

@app.route('/export_custom_failures/<format>')
def export_custom_failures(format):
    stats = load_stats(is_custom=True).get("Custom", {}).get("failed", [])
    custom_data = {w['kanji']: w for w in load_custom_only_data()}
    failed_entries = [custom_data[k] for k in stats if k in custom_data]

    if format == "txt":
        output = "\n".join([w['kanji'] for w in failed_entries])
        return send_file(io.BytesIO(output.encode()), mimetype='text/plain', as_attachment=True, download_name='custom_failures.txt')
    elif format == "anki":
        deck = genanki.Deck(random.randrange(1 << 30, 1 << 31), "Custom Failures")
        model = genanki.Model(1607392500, 'TMW Custom', fields=[{'name': 'K'}, {'name': 'R'}, {'name': 'A'}], templates=[{'name': 'C', 'qfmt': '<div style="font-size:70px;text-align:center;">{{K}}</div>', 'afmt': '{{FrontSide}}<hr><div style="text-align:center;"><div style="font-size:35px;color:#bb86fc;">{{R}}</div><div style="font-size:18px;color:#888;">{{A}}</div></div>'}])
        for v in failed_entries:
            deck.add_note(genanki.Note(model=model, fields=[v['kanji'], v['bank_reading'], " / ".join(v['alt_readings'])]))
        mem = io.BytesIO(); genanki.Package(deck).write_to_file(mem); mem.seek(0)
        return send_file(mem, mimetype='application/octet-stream', as_attachment=True, download_name='Custom_Failures.apkg')

@app.route('/export_failed')
def export_failed():
    stats = load_stats(is_custom=False)
    _, std_lookup = load_standard_data()
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, 'w') as zf:
        for rank in RANKS:
            failed = stats.get(rank, {}).get("failed", [])
            if not failed: continue
            deck = genanki.Deck(random.randrange(1 << 30, 1 << 31), f"TMW::{rank}")
            model = genanki.Model(1607392319 + RANKS.index(rank), 'TMW', fields=[{'name': 'K'}, {'name': 'R'}, {'name': 'A'}], templates=[{'name': 'C', 'qfmt': '<div style="font-size:70px;text-align:center;">{{K}}</div>', 'afmt': '{{FrontSide}}<hr><div style="text-align:center;"><div style="font-size:35px;color:#bb86fc;">{{R}}</div><div style="font-size:18px;color:#888;">{{A}}</div></div>'}])
            for k in failed:
                if k in std_lookup:
                    v = std_lookup[k]
                    deck.add_note(genanki.Note(model=model, fields=[k, v['bank_reading'], " / ".join(v['alt_readings'])]))
            genanki.Package(deck).write_to_file("tmp.apkg"); zf.write("tmp.apkg", f"TMW_{rank}.apkg"); os.remove("tmp.apkg")
    mem.seek(0)
    return send_file(mem, mimetype='application/zip', as_attachment=True, download_name='Rank_Failures.zip')

# --- Templates ---

home_html = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: sans-serif; background: #0f0f0f; color: #e0e0e0; text-align: center; padding: 20px; }
        .main-layout { display: flex; gap: 20px; justify-content: center; max-width: 1400px; margin: 0 auto; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 15px; flex: 3; }
        .card { background: #181818; padding: 15px; border-radius: 10px; border: 1px solid #222; }
        .side-panel { flex: 1; min-width: 320px; }
        .stats { font-size: 12px; margin-bottom: 10px; color: #888; display: flex; justify-content: space-between; }
        .btn { display: block; padding: 10px; margin: 5px 0; background: #252525; border: 1px solid #333; color: #ccc; text-decoration: none; border-radius: 4px; font-size: 13px; cursor: pointer; text-align:center; }
        .btn:hover { background: #333; color: #fff; }
        .btn-new { border-left: 3px solid #bb86fc; }
        .btn-fail { border-left: 3px solid #cf6679; }
        .btn-all { border-left: 3px solid #03dac6; }
        .reset { font-size: 10px; color: #444; cursor: pointer; margin-top: 10px; }
        .export { margin-top: 20px; display: inline-block; padding: 10px 20px; background: #bb86fc; color: #000; border-radius: 20px; text-decoration: none; font-weight: bold; width: 100%; box-sizing: border-box; }
        .custom-controls { margin-top: 10px; display: flex; gap: 5px; }
        .custom-controls .btn { flex: 1; font-size: 11px; padding: 5px; background: #1a1a1a; }
    </style>
</head>
<body>
    <h1>TMW Rank Trainer</h1>
    <div class="main-layout">
        <div class="grid">
            {% for rank in ranks %}
            <div class="card">
                <div style="font-size: 18px; margin-bottom: 10px;">{{rank}}</div>
                {% set info = rank_info[rank] %}
                <div class="stats"><span>New: {{info.unreviewed}}</span><span style="color: #03dac6">OK: {{info.passed}}</span><span style="color: #cf6679">Fail: {{info.failed}}</span></div>
                <a href="/quiz/{{rank}}/unreviewed" class="btn btn-new">New Only</a>
                <a href="/quiz/{{rank}}/failures" class="btn btn-fail">Failures Only</a>
                <a href="/quiz/{{rank}}/all" class="btn btn-all">Everything</a>
            </div>
            {% endfor %}
        </div>
        <div class="side-panel">
            <div class="card" style="border: 1px dashed #bb86fc;">
                <div style="font-size: 18px; color: #bb86fc;">Custom Word List</div>
                {% if custom_exists %}
                    <div class="stats" style="margin-top:10px;"><span>New: {{custom_info.unreviewed}}</span><span style="color: #03dac6">OK: {{custom_info.passed}}</span><span style="color: #cf6679">Fail: {{custom_info.failed}}</span></div>
                    <a href="/quiz/Custom/unreviewed" class="btn btn-new">New Only</a>
                    <a href="/quiz/Custom/failures" class="btn btn-fail">Failures Only</a>
                    <a href="/quiz/Custom/all" class="btn btn-all">Everything</a>
                    <div style="color: #666; font-size: 11px; margin: 10px 0;">Export Custom Failures:</div>
                    <div class="custom-controls">
                        <a href="/export_custom_failures/txt" class="btn">To .txt</a>
                        <a href="/export_custom_failures/anki" class="btn">To .apkg</a>
                    </div>
                    <div class="reset" style="color: #cf6679; margin-top: 15px;" onclick="clearCustom()">DELETE CUSTOM BANK</div>
                {% else %}
                    <p style="font-size: 12px; color: #666;">Upload your jiten-export.txt</p>
                    <input type="file" id="customFile" style="display: none;" onchange="handleUpload(this)">
                    <button class="btn btn-all" onclick="document.getElementById('customFile').click()">Import .txt File</button>
                {% endif %}
            </div>
            <a href="/export_failed" class="export">Export All Rank Failures</a>
        </div>
    </div>
    <script>
        async function clearCustom() { if(confirm("Delete Custom Bank and its stats?")) { await fetch('/api/clear_custom', {method:'POST'}); location.reload(); } }
        async function handleUpload(input) {
            const formData = new FormData(); formData.append('file', input.files[0]);
            await fetch('/api/import_custom', { method: 'POST', body: formData });
            location.reload();
        }
    </script>
</body>
</html>
"""

quiz_html = """
<!DOCTYPE html>
<html>
<head>
    <script src="https://unpkg.com/wanakana"></script>
    <style>
        body { background: #121212; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; font-family: "Yu Mincho", serif; margin: 0; overflow: hidden; }
        .quiz-header { position: absolute; top: 0; width: 100%; background: #181818; padding: 15px 0; border-bottom: 1px solid #333; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; }
        .header-top { display: flex; justify-content: space-between; width: 600px; margin-bottom: 10px; }
        .progress-container { width: 600px; height: 6px; background: #222; border-radius: 3px; overflow: hidden; }
        .progress-bar { height: 100%; width: 0%; background: #bb86fc; transition: width 0.5s; }
        .kanji { font-size: 110px; margin-top: 40px; }
        input { font-size: 32px; text-align: center; padding: 15px; background: #1e1e1e; color: white; border: 2px solid #333; border-radius: 8px; width: 450px; outline: none; margin-top: 20px; }
        .reading-list { display: flex; flex-direction: column; align-items: center; gap: 8px; margin-top: 20px; min-height: 120px; }
        .reading-item { font-size: 24px; padding: 4px 12px; border-radius: 6px; font-family: sans-serif; }
        .primary { border: 2px solid #bb86fc; color: #bb86fc; }
        .alt { color: #666; }
        .user-match { background: rgba(255, 165, 0, 0.2); color: #ffa500 !important; border: 2px solid #ffa500; }
        .wrong { color: #cf6679; text-decoration: line-through; }
    </style>
</head>
<body>
    <div class="quiz-header">
        <div class="header-top">
            <a href="/" style="color: #888; text-decoration: none;">← Home</a>
            <div style="font-weight: bold;">{{rank}}</div>
            <div style="font-size: 14px; color: #aaa; display: flex; gap: 15px;">
                <span>New: <b id="sn">{{stats.unreviewed}}</b></span>
                <span style="color: #03dac6">OK: <b id="so">{{stats.passed}}</b></span>
                <span style="color: #cf6679">Fail: <b id="sf">{{stats.failed}}</b></span>
            </div>
        </div>
        <div class="progress-container"><div class="progress-bar" id="pb"></div></div>
    </div>
    <div class="kanji" id="kj">...</div>
    <input type="text" id="ans" autocomplete="off" autofocus>
    <div id="fb" class="reading-list"></div>
    <script>
        let cur = {}; let isProc = false; const input = document.getElementById('ans'); wanakana.bind(input);
        function upd(s) {
            document.getElementById('sn').innerText = s.unreviewed; document.getElementById('so').innerText = s.passed; document.getElementById('sf').innerText = s.failed;
            document.getElementById('pb').style.width = ((s.passed + s.failed) / s.total * 100) + "%";
        }
        async function next() {
            const res = await fetch(`/api/get_word/{{rank}}/{{mode}}`);
            if(!res.ok) { document.getElementById('kj').innerText = "Finished!"; input.style.display="none"; return; }
            cur = await res.json(); document.getElementById('kj').innerText = cur.kanji;
            input.value = ''; document.getElementById('fb').innerHTML = ''; isProc = false;
        }
        input.addEventListener('keypress', async (e) => {
            if(e.key === 'Enter') {
                const val = input.value.trim();
                if(val === "" || isProc) return;
                isProc = true;
                const isH = val === cur.bank_reading; const isS = cur.alt_readings.includes(val);
                const ok = isH || isS; navigator.clipboard.writeText(cur.kanji);
                const fb = document.getElementById('fb'); fb.innerHTML = '';
                const bEl = document.createElement('div'); bEl.className = 'reading-item primary' + (isH ? ' user-match' : ''); bEl.innerText = cur.bank_reading; fb.appendChild(bEl);
                cur.alt_readings.forEach(a => { const aEl = document.createElement('div'); aEl.className = 'reading-item alt' + (a === val ? ' user-match' : ''); aEl.innerText = a; fb.appendChild(aEl); });
                if(!ok) { const w = document.createElement('div'); w.className='reading-item wrong'; w.innerText = val; fb.appendChild(w); }
                const r = await fetch(`/api/report/{{rank}}`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({kanji: cur.kanji, correct: ok})});
                upd((await r.json()).new_stats); setTimeout(next, ok ? 800 : 3000);
            }
        });
        upd({{stats|tojson}}); next();
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    if not os.path.exists('templates'): os.makedirs('templates')
    with open('templates/home.html', 'w', encoding='utf-8') as f: f.write(home_html)
    with open('templates/quiz.html', 'w', encoding='utf-8') as f: f.write(quiz_html)
    app.run(debug=True, port=5000)
from flask import Flask, render_template, request, jsonify, send_file
import os
import uuid
import csv
from datetime import datetime
from pdf_utils import compare_pdfs, generate_html_report, generate_csv_report
app = Flask(__name__)
app.secret_key = "pdf_comparator_secret_2026"
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
@app.route('/')
def index():
    return render_template('index.html')
@app.route('/compare_two', methods=['POST'])
def compare_two():
    if 'pdf1' not in request.files or 'pdf2' not in request.files:
        return jsonify({'error': 'Both PDF files are required'}), 400
    pdf1 = request.files['pdf1']
    pdf2 = request.files['pdf2']
    if pdf1.filename == '' or pdf2.filename == '':
        return jsonify({'error': 'Please select both PDF files'}), 400
    session_id = str(uuid.uuid4())
    pdf1_name = pdf1.filename
    pdf2_name = pdf2.filename
    pdf1_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_pdf1.pdf")
    pdf2_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_pdf2.pdf")
    pdf1.save(pdf1_path)
    pdf2.save(pdf2_path)
    try:
        differences = compare_pdfs(pdf1_path, pdf2_path, pdf1_name, pdf2_name)
        html_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{session_id}_report.html")
        csv_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{session_id}_report.csv")
        generate_html_report(differences, pdf1_name, pdf2_name, html_path)
        generate_csv_report(differences, pdf1_name, pdf2_name, csv_path)
        summary = {
            'total_pages': differences['total_pages'],
            'pages_with_diffs': differences['pages_with_diffs'],
            'total_differences': differences['total_differences'],
            'modified_lines': differences['modified_lines'],
            'only_in_pdf_a': differences['only_in_pdf_a'],
            'only_in_pdf_b': differences['only_in_pdf_b'],
            'session_id': session_id,
            'pdf1_name': pdf1_name,
            'pdf2_name': pdf2_name
        }
        return jsonify({'success': True, 'summary': summary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
import re
import difflib
_STRIP_WORDS = re.compile(
    r'\b(new|old|latest|original|final|draft|copy|backup|revised|'
    r'updated|modified|version|ver|rev|report|file|doc|document|'
    r'pdf|comparsion|comparison|sample)\b',
    re.IGNORECASE
)
_STRIP_VER = re.compile(r'v\s*\d+(\.\d+)*', re.IGNORECASE)
_STRIP_NUMS = re.compile(r'\d+')
_SEPARATORS = re.compile(r'[\s_\-\.]+')
def get_base_name(filename: str) -> str:
    name = os.path.splitext(filename)[0]
    name = _STRIP_VER.sub('', name)
    name = _STRIP_WORDS.sub('', name)
    name = _STRIP_NUMS.sub('', name)
    name = _SEPARATORS.sub(' ', name).strip().lower()
    return name
def names_are_similar(a: str, b: str, threshold: float = 0.60) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    return ratio >= threshold
def find_matching_pairs(file_names):
    n = len(file_names)
    bases = [get_base_name(fn) for fn in file_names]
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(x, y):
        parent[find(x)] = find(y)
    for i in range(n):
        for j in range(i + 1, n):
            if names_are_similar(bases[i], bases[j]):
                union(i, j)
    from collections import defaultdict
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    pairs = []
    unmatched = []
    for members in groups.values():
        if len(members) >= 2:
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    pairs.append((members[i], members[j]))
        else:
            unmatched.extend(members)
    base_map = {file_names[i]: bases[i] for i in range(n)}
    return pairs, unmatched, base_map
@app.route('/preview_pairs', methods=['POST'])
def preview_pairs():
    file_names = request.json.get('file_names', [])
    if len(file_names) < 2:
        return jsonify({'error': 'At least 2 files required'}), 400
    pairs, unmatched, base_map = find_matching_pairs(file_names)
    pair_list = [{'a': file_names[i], 'b': file_names[j],
                  'base_a': base_map.get(file_names[i], ''),
                  'base_b': base_map.get(file_names[j], '')} for i, j in pairs]
    unmatched_list = [file_names[i] for i in unmatched]
    return jsonify({'pairs': pair_list, 'unmatched': unmatched_list, 'base_map': base_map})
@app.route('/compare_all', methods=['POST'])
def compare_all():
    files = request.files.getlist('pdfs')
    if len(files) < 2:
        return jsonify({'error': 'At least 2 PDF files are required'}), 400
    session_id = str(uuid.uuid4())
    saved_paths, file_names = [], []
    for f in files:
        if f.filename == '':
            continue
        path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_{f.filename}")
        f.save(path)
        saved_paths.append(path)
        file_names.append(f.filename)
    try:
        all_results = []
        for i in range(len(saved_paths)):
            for j in range(i + 1, len(saved_paths)):
                diffs = compare_pdfs(saved_paths[i], saved_paths[j],
                                     file_names[i], file_names[j])
                all_results.append({
                    'pdf_a': file_names[i],
                    'pdf_b': file_names[j],
                    'differences': diffs
                })
        html_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{session_id}_all_report.html")
        csv_path  = os.path.join(app.config['OUTPUT_FOLDER'], f"{session_id}_all_report.csv")

        generate_multi_html_report(all_results, html_path)
        generate_multi_csv_report(all_results, csv_path)

        total_diffs = sum(r['differences']['total_differences'] for r in all_results)
        summary = {
            'pairs_compared': len(all_results),
            'total_differences': total_diffs,
            'session_id': session_id,
            'files': file_names,
            'pairs': [{'a': file_names[i], 'b': file_names[j]}
                      for i in range(len(file_names)) for j in range(i+1, len(file_names))],
            'unmatched': []
        }
        return jsonify({'success': True, 'summary': summary, 'mode': 'all'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/compare_multiple', methods=['POST'])
def compare_multiple():
    files = request.files.getlist('pdfs')
    if len(files) < 2:
        return jsonify({'error': 'At least 2 PDF files are required'}), 400
    session_id = str(uuid.uuid4())
    saved_paths = []
    file_names = []
    for f in files:
        if f.filename == '':
            continue
        path = os.path.join(app.config['UPLOAD_FOLDER'], f"{session_id}_{f.filename}")
        f.save(path)
        saved_paths.append(path)
        file_names.append(f.filename)
    try:
        pairs, unmatched, base_map = find_matching_pairs(file_names)
        if not pairs:
            msg = ("No matching PDF pairs found. Detected base names: " +
                   ", ".join(f'"{fn}" → "{b}"' for fn, b in base_map.items()) +
                   ". Upload PDFs whose names share a common topic word "
                   "(e.g. 'salary_old.pdf' & 'salary_new.pdf', or 'invoice v1.pdf' & 'invoice v2.pdf').")
            return jsonify({'error': msg}), 400
        all_results = []
        for i, j in pairs:
            diffs = compare_pdfs(saved_paths[i], saved_paths[j],
                                 file_names[i], file_names[j])
            all_results.append({
                'pdf_a': file_names[i],
                'pdf_b': file_names[j],
                'differences': diffs
            })
        html_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{session_id}_multi_report.html")
        csv_path  = os.path.join(app.config['OUTPUT_FOLDER'], f"{session_id}_multi_report.csv")
        generate_multi_html_report(all_results, html_path)
        generate_multi_csv_report(all_results, csv_path)
        total_diffs = sum(r['differences']['total_differences'] for r in all_results)
        summary = {
            'pairs_compared': len(all_results),
            'total_differences': total_diffs,
            'session_id': session_id,
            'files': file_names,
            'pairs': [{'a': file_names[i], 'b': file_names[j],
                       'base': base_map.get(file_names[i], '')} for i, j in pairs],
            'unmatched': [file_names[i] for i in unmatched],
            'base_map': base_map
        }
        return jsonify({'success': True, 'summary': summary, 'mode': 'multiple'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
@app.route('/download_csv/<session_id>')
def download_csv(session_id):
    for suffix in ['_report.csv', '_multi_report.csv', '_all_report.csv']:
        path = os.path.join(app.config['OUTPUT_FOLDER'], f"{session_id}{suffix}")
        if os.path.exists(path):
            return send_file(path, as_attachment=True, download_name='comparison_report.csv')
    return jsonify({'error': 'Report not found'}), 404
@app.route('/view_html/<session_id>')
def view_html(session_id):
    for suffix in ['_report.html', '_multi_report.html', '_all_report.html']:
        path = os.path.join(app.config['OUTPUT_FOLDER'], f"{session_id}{suffix}")
        if os.path.exists(path):
            return send_file(path)
    return jsonify({'error': 'Report not found'}), 404
def generate_multi_html_report(all_results, output_path):
    from pdf_utils import escape_html
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total_diffs_all = sum(r['differences']['total_differences'] for r in all_results)
    total_pages_all = sum(r['differences']['total_pages'] for r in all_results)
    total_modified = sum(r['differences']['modified_lines'] for r in all_results)
    total_only_a = sum(r['differences']['only_in_pdf_a'] for r in all_results)
    total_only_b = sum(r['differences']['only_in_pdf_b'] for r in all_results)
    pairs = len(all_results)
    pair_sections_html = ""
    for pair_idx, res in enumerate(all_results):
        diffs = res['differences']
        diff_list = diffs.get('diff_list', [])
        pdf_a = res['pdf_a']
        pdf_b = res['pdf_b']
        pair_id = f"pair_{pair_idx}"
        rows_html = ""
        current_page = None
        for diff in diff_list:
            page = diff['page']
            if page != current_page:
                rows_html += f'<tr class="page-header-row"><td colspan="5">PAGE {page}</td></tr>'
                current_page = page
            type_class = {
                'Modified': 'type-modified',
                'Only in PDF A': 'type-only-a',
                'Only in PDF B': 'type-only-b'
            }.get(diff['type'], '')
            rows_html += f"""<tr class="diff-row {type_class}-row" data-page="{page}" data-type="{diff['type']}">
                <td class="line-no">{diff.get('line_no_a','')}</td>
                <td class="line-no">{diff.get('line_no_b','')}</td>
                <td><span class="badge {type_class}">{diff['type']}</span></td>
                <td class="content-cell">{diff.get('highlighted_a','')}</td>
                <td class="content-cell">{diff.get('highlighted_b','')}</td>
            </tr>"""
        unique_pages = sorted(set(d['page'] for d in diff_list))
        page_options = ''.join(f'<option value="{p}">Page {p}</option>' for p in unique_pages)
        pair_sections_html += f"""
        <div class="pair-section" id="{pair_id}">
          <div class="pair-header" onclick="togglePair('{pair_id}')">
            <span class="pair-icon">📄</span>
            <span class="pair-title">{escape_html(pdf_a)} <span class="vs-badge">VS</span> {escape_html(pdf_b)}</span>
            <div class="pair-mini-stats">
              <span class="ms ms-blue">{diffs['total_pages']} pages</span>
              <span class="ms ms-orange">{diffs['pages_with_diffs']} w/diffs</span>
              <span class="ms ms-red">{diffs['total_differences']} diffs</span>
            </div>
            <span class="pair-chevron" id="chevron_{pair_id}">▼</span>
          </div>
          <div class="pair-body" id="body_{pair_id}">
            <div class="stats-grid">
              <div class="stat-card"><span class="stat-number n-blue">{diffs['total_pages']}</span><span class="stat-label">Total Pages</span></div>
              <div class="stat-card"><span class="stat-number n-orange">{diffs['pages_with_diffs']}</span><span class="stat-label">Pages w/ Diffs</span></div>
              <div class="stat-card"><span class="stat-number n-blue">{diffs['total_differences']}</span><span class="stat-label">Total Diffs</span></div>
              <div class="stat-card"><span class="stat-number n-yellow">{diffs['modified_lines']}</span><span class="stat-label">Modified Lines</span></div>
              <div class="stat-card"><span class="stat-number n-red">{diffs['only_in_pdf_a']}</span><span class="stat-label">Only in PDF A</span></div>
              <div class="stat-card"><span class="stat-number n-green">{diffs['only_in_pdf_b']}</span><span class="stat-label">Only in PDF B</span></div>
            </div>
            <div class="legend">
              <div class="legend-item"><div class="legend-box lb-modified"></div> Modified line</div>
              <div class="legend-item"><div class="legend-box lb-only-a"></div> Only in PDF A (removed)</div>
              <div class="legend-item"><div class="legend-box lb-only-b"></div> Only in PDF B (added)</div>
              <div class="legend-item" style="margin-left:auto">
                <span style="background:rgba(248,81,73,0.4);color:#ff8080;padding:2px 6px;border-radius:3px">Red</span>&nbsp;= removed chars&nbsp;
                <span style="background:rgba(63,185,80,0.4);color:#80ff99;padding:2px 6px;border-radius:3px">Green</span>&nbsp;= added chars
              </div>
            </div>
            <div class="filters">
              <label>Page:</label>
              <select onchange="filterPair('{pair_id}', this)">
                <option value="all">All Pages</option>{page_options}
              </select>
              <label>Type:</label>
              <select onchange="filterPairType('{pair_id}', this)">
                <option value="all">All Types</option>
                <option value="Modified">Modified</option>
                <option value="Only in PDF A">Only in PDF A</option>
                <option value="Only in PDF B">Only in PDF B</option>
              </select>
              <label>Search:</label>
              <input type="text" placeholder="Filter by content..." oninput="filterPairSearch('{pair_id}', this)">
              <button class="btn btn-export" onclick="exportPairCSV('{pair_id}', '{escape_html(pdf_a)}', '{escape_html(pdf_b)}')">⬇ Export CSV</button>
              <span class="diff-count" id="count_{pair_id}">Showing {len(diff_list)} difference(s)</span>
            </div>
            <div class="table-wrap">
              <table class="diff-table" id="table_{pair_id}">
                <thead>
                  <tr>
                    <th>LINE NO<br>({escape_html(pdf_a.upper())})</th>
                    <th>LINE NO<br>({escape_html(pdf_b.upper())})</th>
                    <th>TYPE</th>
                    <th>{escape_html(pdf_a.upper())}</th>
                    <th>{escape_html(pdf_b.upper())}</th>
                  </tr>
                </thead>
                <tbody>{rows_html}</tbody>
              </table>
            </div>
          </div>
        </div>"""
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Multi-PDF Comparison Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0d1117; color: #e6edf3; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 30px; min-height: 100vh; }}
  .report-header {{ border-bottom: 2px solid #00c8c8; padding-bottom: 20px; margin-bottom: 30px; }}
  .report-header h1 {{ font-size: 2rem; color: #00c8c8; font-weight: 700; letter-spacing: 1px; }}
  .report-meta {{ color: #8b949e; font-size: 0.9rem; margin-top: 8px; }}
  .report-meta strong {{ color: #e6edf3; }}
  .overall-stats {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; margin-bottom: 28px; }}
  .overall-stats h2 {{ color: #00c8c8; font-size: 1rem; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 16px; }}
  .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; }}
  .stat-card {{ background: #0d1117; border: 1px solid #30363d; border-radius: 10px; padding: 16px; text-align: center; transition: border-color 0.2s; }}
  .stat-card:hover {{ border-color: #00c8c8; }}
  .stat-number {{ font-size: 2.2rem; font-weight: 700; display: block; line-height: 1; margin-bottom: 4px; }}
  .stat-label {{ font-size: 0.7rem; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; }}
  .n-blue {{ color: #00c8c8; }} .n-green {{ color: #3fb950; }} .n-orange {{ color: #f0883e; }}
  .n-red {{ color: #f85149; }} .n-yellow {{ color: #e3b341; }} .n-purple {{ color: #bc8cff; }}
  .pair-section {{ margin-bottom: 20px; border: 1px solid #30363d; border-radius: 12px; overflow: hidden; transition: border-color 0.2s; }}
  .pair-section:hover {{ border-color: rgba(0,200,200,0.4); }}
  .pair-header {{ background: #161b22; padding: 16px 20px; cursor: pointer; display: flex; align-items: center; gap: 14px; user-select: none; transition: background 0.2s; }}
  .pair-header:hover {{ background: #1c2128; }}
  .pair-icon {{ font-size: 1.3rem; }}
  .pair-title {{ font-size: 1rem; font-weight: 600; color: #e6edf3; flex: 1; }}
  .vs-badge {{ background: #00c8c8; color: #0d1117; font-size: 0.7rem; padding: 2px 7px; border-radius: 4px; font-weight: 700; margin: 0 6px; }}
  .pair-mini-stats {{ display: flex; gap: 8px; }}
  .ms {{ font-size: 0.75rem; padding: 3px 8px; border-radius: 20px; font-weight: 600; }}
  .ms-blue {{ background: rgba(0,200,200,0.15); color: #00c8c8; }}
  .ms-orange {{ background: rgba(240,136,62,0.15); color: #f0883e; }}
  .ms-red {{ background: rgba(248,81,73,0.15); color: #f85149; }}
  .pair-chevron {{ color: #8b949e; font-size: 0.9rem; transition: transform 0.3s; }}
  .pair-chevron.collapsed {{ transform: rotate(-90deg); }}
  .pair-body {{ padding: 20px; border-top: 1px solid #30363d; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 16px; margin: 16px 0; padding: 14px; background: #161b22; border-radius: 8px; border: 1px solid #30363d; font-size: 0.82rem; }}
  .legend-item {{ display: flex; align-items: center; gap: 7px; }}
  .legend-box {{ width: 13px; height: 13px; border-radius: 3px; }}
  .lb-modified {{ background: #f0883e33; border: 1px solid #f0883e; }}
  .lb-only-a {{ background: #f8514933; border: 1px solid #f85149; }}
  .lb-only-b {{ background: #3fb95033; border: 1px solid #3fb950; }}
  .filters {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; align-items: center; }}
  .filters label {{ color: #8b949e; font-size: 0.82rem; }}
  .filters select, .filters input {{ background: #161b22; border: 1px solid #30363d; color: #e6edf3; padding: 5px 10px; border-radius: 6px; font-size: 0.82rem; }}
  .btn {{ padding: 6px 14px; border-radius: 6px; border: none; cursor: pointer; font-size: 0.82rem; font-weight: 600; transition: all 0.2s; }}
  .btn-export {{ background: #238636; color: #fff; }}
  .btn-export:hover {{ background: #2ea043; }}
  .diff-count {{ color: #8b949e; font-size: 0.8rem; margin-left: auto; }}
  .table-wrap {{ overflow-x: auto; border: 1px solid #30363d; border-radius: 8px; }}
  .diff-table {{ width: 100%; border-collapse: collapse; }}
  .diff-table th {{ background: #161b22; color: #8b949e; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 1px; padding: 10px 14px; text-align: left; border-bottom: 1px solid #30363d; }}
  .diff-table td {{ padding: 9px 14px; border-bottom: 1px solid #21262d; font-size: 0.82rem; vertical-align: top; font-family: 'Consolas','Courier New',monospace; }}
  .page-header-row td {{ background: #1c2128; color: #00c8c8; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 2px; padding: 7px 14px; font-family: 'Segoe UI',sans-serif; }}
  .line-no {{ color: #8b949e; text-align: center; width: 65px; font-size: 0.78rem; }}
  .type-modified-row td {{ background: rgba(240,136,62,0.05); }}
  .type-only-a-row td {{ background: rgba(248,81,73,0.05); }}
  .type-only-b-row td {{ background: rgba(63,185,80,0.05); }}
  .badge {{ padding: 3px 8px; border-radius: 20px; font-size: 0.72rem; font-weight: 600; white-space: nowrap; font-family: 'Segoe UI',sans-serif; }}
  .type-modified {{ background: rgba(240,136,62,0.2); color: #f0883e; border: 1px solid #f0883e55; }}
  .type-only-a {{ background: rgba(248,81,73,0.2); color: #f85149; border: 1px solid #f8514955; }}
  .type-only-b {{ background: rgba(63,185,80,0.2); color: #3fb950; border: 1px solid #3fb95055; }}
  .char-removed {{ background: rgba(248,81,73,0.4); color: #ff8080; border-radius: 2px; }}
  .char-added {{ background: rgba(63,185,80,0.4); color: #80ff99; border-radius: 2px; }}
  .removed-line {{ background: rgba(248,81,73,0.25); color: #f85149; }}
  .added-line {{ background: rgba(63,185,80,0.25); color: #3fb950; }}
  .content-cell {{ word-break: break-word; max-width: 380px; line-height: 1.6; }}
  .footer {{ margin-top: 40px; text-align: center; color: #484f58; font-size: 0.8rem; padding-top: 20px; border-top: 1px solid #21262d; }}
</style>
</head>
<body>
<div class="report-header">
  <h1>📊 Multi-PDF Comparison Report</h1>
  <div class="report-meta">
    Generated: {now} &nbsp;|&nbsp; <strong>{pairs}</strong> pair(s) compared
  </div>
</div>
<div class="overall-stats">
  <h2>📈 Overall Summary</h2>
  <div class="stats-grid">
    <div class="stat-card"><span class="stat-number n-purple">{pairs}</span><span class="stat-label">Pairs Compared</span></div>
    <div class="stat-card"><span class="stat-number n-blue">{total_pages_all}</span><span class="stat-label">Total Pages</span></div>
    <div class="stat-card"><span class="stat-number n-blue">{total_diffs_all}</span><span class="stat-label">Total Diffs</span></div>
    <div class="stat-card"><span class="stat-number n-yellow">{total_modified}</span><span class="stat-label">Modified Lines</span></div>
    <div class="stat-card"><span class="stat-number n-red">{total_only_a}</span><span class="stat-label">Only in PDF A</span></div>
    <div class="stat-card"><span class="stat-number n-green">{total_only_b}</span><span class="stat-label">Only in PDF B</span></div>
  </div>
</div>
{pair_sections_html}
<div class="footer">© 2026 | PDF Comparison Tool | Developed by Atul Raj</div>
<script>
function togglePair(pairId) {{
  const body = document.getElementById('body_' + pairId);
  const chevron = document.getElementById('chevron_' + pairId);
  const isHidden = body.style.display === 'none';
  body.style.display = isHidden ? 'block' : 'none';
  chevron.classList.toggle('collapsed', !isHidden);
}}
function getVisibleRows(pairId) {{
  return document.querySelectorAll('#table_' + pairId + ' tbody tr:not(.page-header-row)');
}}
function applyPairFilters(pairId) {{
  const pageFilter = document.querySelector('#body_' + pairId + ' select:nth-of-type(1)')?.value || 'all';
  const typeFilter = document.querySelector('#body_' + pairId + ' select:nth-of-type(2)')?.value || 'all';
  const search = (document.querySelector('#body_' + pairId + ' input[type=text]')?.value || '').toLowerCase();
  const tbody = document.querySelector('#table_' + pairId + ' tbody');
  const rows = tbody.querySelectorAll('tr');
  let visible = 0;
  let lastPageHeader = null;
  let pageHasVisible = false;
  rows.forEach(row => {{
    if (row.classList.contains('page-header-row')) {{
      if (lastPageHeader) lastPageHeader.style.display = pageHasVisible ? '' : 'none';
      lastPageHeader = row;
      pageHasVisible = false;
      return;
    }}
    const page = row.getAttribute('data-page') || '';
    const type = row.getAttribute('data-type') || '';
    const content = row.textContent.toLowerCase();
    const show = (pageFilter === 'all' || page === pageFilter) &&
                 (typeFilter === 'all' || type === typeFilter) &&
                 (!search || content.includes(search));
    row.style.display = show ? '' : 'none';
    if (show) {{ visible++; pageHasVisible = true; }}
  }});
  if (lastPageHeader) lastPageHeader.style.display = pageHasVisible ? '' : 'none';
  const countEl = document.getElementById('count_' + pairId);
  if (countEl) countEl.textContent = 'Showing ' + visible + ' difference(s)';
}}
function filterPair(pairId, sel) {{ applyPairFilters(pairId); }}
function filterPairType(pairId, sel) {{ applyPairFilters(pairId); }}
function filterPairSearch(pairId, inp) {{ applyPairFilters(pairId); }}
function exportPairCSV(pairId, pdfA, pdfB) {{
  const rows = document.querySelectorAll('#table_' + pairId + ' tbody tr:not(.page-header-row):not([style*="display: none"])');
  let csv = 'Page,Line_A,Line_B,Type,Content_A,Content_B\\n';
  rows.forEach(row => {{
    const cells = row.querySelectorAll('td');
    if (cells.length >= 5) {{
      const page = row.getAttribute('data-page') || '';
      const vals = [page, cells[0].textContent, cells[1].textContent, cells[2].textContent, cells[3].textContent, cells[4].textContent];
      csv += vals.map(v => '"' + v.replace(/"/g,'""') + '"').join(',') + '\\n';
    }}
  }});
  const blob = new Blob([csv], {{type: 'text/csv'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = pdfA + '_vs_' + pdfB + '.csv';
  a.click();
}}
</script>
</body>
</html>"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
def generate_multi_csv_report(all_results, output_path):
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['PDF_A', 'PDF_B', 'Page', 'Line_A', 'Line_B', 'Type', 'Content_A', 'Content_B'])
        for res in all_results:
            for diff in res['differences'].get('diff_list', []):
                writer.writerow([
                    res['pdf_a'], res['pdf_b'],
                    diff.get('page', ''), diff.get('line_no_a', ''), diff.get('line_no_b', ''),
                    diff.get('type', ''), diff.get('content_a', ''), diff.get('content_b', '')
                ])

if __name__ == "__main__":
    if os.environ.get("RENDER"):
        app.run(host="0.0.0.0", port=5000)
    else:
        app.run(debug=True, port=5000)

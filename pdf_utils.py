import pdfplumber
import difflib
import csv
from datetime import datetime
def extract_pdf_text(pdf_path):
    pages_data = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                lines = text.split('\n')
                clean_lines = [line.strip() for line in lines if line.strip()]
                pages_data.append({
                    'page': page_num,
                    'lines': clean_lines
                })
    except Exception as e:
        raise Exception(f"Error reading PDF: {str(e)}")
    return pages_data
def compare_pdfs(pdf1_path, pdf2_path, pdf1_name, pdf2_name):
    pages_a = extract_pdf_text(pdf1_path)
    pages_b = extract_pdf_text(pdf2_path)
    total_pages_a = len(pages_a)
    total_pages_b = len(pages_b)
    total_pages = max(total_pages_a, total_pages_b)
    diff_list = []
    pages_with_diffs = set()
    modified_count = 0
    only_in_a_count = 0
    only_in_b_count = 0
    for page_idx in range(total_pages):
        page_num = page_idx + 1
        lines_a = pages_a[page_idx]['lines'] if page_idx < len(pages_a) else []
        lines_b = pages_b[page_idx]['lines'] if page_idx < len(pages_b) else []
        matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                a_block = lines_a[i1:i2]
                b_block = lines_b[j1:j2]
                max_len = max(len(a_block), len(b_block))
                for k in range(max_len):
                    line_a = a_block[k] if k < len(a_block) else ""
                    line_b = b_block[k] if k < len(b_block) else ""
                    line_no_a = i1 + k + 1 if k < len(a_block) else ""
                    line_no_b = j1 + k + 1 if k < len(b_block) else ""
                    char_diffs_a, char_diffs_b = highlight_char_diffs(line_a, line_b)
                    diff_list.append({
                        'page': page_num,
                        'line_no_a': line_no_a,
                        'line_no_b': line_no_b,
                        'type': 'Modified',
                        'content_a': line_a,
                        'content_b': line_b,
                        'highlighted_a': char_diffs_a,
                        'highlighted_b': char_diffs_b
                    })
                    modified_count += 1
                    pages_with_diffs.add(page_num)
            elif tag == 'delete':
                for k, line in enumerate(lines_a[i1:i2]):
                    diff_list.append({
                        'page': page_num,
                        'line_no_a': i1 + k + 1,
                        'line_no_b': '',
                        'type': 'Only in PDF A',
                        'content_a': line,
                        'content_b': '',
                        'highlighted_a': f'<span class="removed-line">{escape_html(line)}</span>',
                        'highlighted_b': ''
                    })
                    only_in_a_count += 1
                    pages_with_diffs.add(page_num)
            elif tag == 'insert':
                for k, line in enumerate(lines_b[j1:j2]):
                    diff_list.append({
                        'page': page_num,
                        'line_no_a': '',
                        'line_no_b': j1 + k + 1,
                        'type': 'Only in PDF B',
                        'content_a': '',
                        'content_b': line,
                        'highlighted_a': '',
                        'highlighted_b': f'<span class="added-line">{escape_html(line)}</span>'
                    })
                    only_in_b_count += 1
                    pages_with_diffs.add(page_num)
    return {
        'total_pages': total_pages,
        'pages_with_diffs': len(pages_with_diffs),
        'total_differences': len(diff_list),
        'modified_lines': modified_count,
        'only_in_pdf_a': only_in_a_count,
        'only_in_pdf_b': only_in_b_count,
        'diff_list': diff_list,
        'pdf1_name': pdf1_name,
        'pdf2_name': pdf2_name
    }
def escape_html(text):
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))
def highlight_char_diffs(text_a, text_b):
    if not text_a and not text_b:
        return '', ''
    matcher = difflib.SequenceMatcher(None, text_a, text_b)
    result_a = []
    result_b = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            result_a.append(escape_html(text_a[i1:i2]))
            result_b.append(escape_html(text_b[j1:j2]))
        elif tag == 'replace':
            result_a.append(f'<span class="char-removed">{escape_html(text_a[i1:i2])}</span>')
            result_b.append(f'<span class="char-added">{escape_html(text_b[j1:j2])}</span>')
        elif tag == 'delete':
            result_a.append(f'<span class="char-removed">{escape_html(text_a[i1:i2])}</span>')
        elif tag == 'insert':
            result_b.append(f'<span class="char-added">{escape_html(text_b[j1:j2])}</span>')
    return ''.join(result_a), ''.join(result_b)
def generate_html_report(differences, pdf1_name, pdf2_name, output_path):
    diff_list = differences.get('diff_list', [])
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    rows_html = ""
    current_page = None
    for diff in diff_list:
        page = diff['page']
        if page != current_page:
            rows_html += f"""
            <tr class="page-header-row">
                <td colspan="5">PAGE {page}</td>
            </tr>"""
            current_page = page
        type_class = {
            'Modified': 'type-modified',
            'Only in PDF A': 'type-only-a',
            'Only in PDF B': 'type-only-b'
        }.get(diff['type'], '')
        rows_html += f"""
        <tr class="diff-row {type_class}-row">
            <td class="line-no">{diff.get('line_no_a', '')}</td>
            <td class="line-no">{diff.get('line_no_b', '')}</td>
            <td><span class="badge {type_class}">{diff['type']}</span></td>
            <td class="content-cell">{diff.get('highlighted_a', '')}</td>
            <td class="content-cell">{diff.get('highlighted_b', '')}</td>
        </tr>"""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PDF Comparison Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0d1117;
    color: #e6edf3;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    padding: 30px;
    min-height: 100vh;
  }}
  .report-header {{
    border-bottom: 2px solid #00c8c8;
    padding-bottom: 20px;
    margin-bottom: 30px;
  }}
  .report-header h1 {{
    font-size: 2rem;
    color: #00c8c8;
    font-weight: 700;
    letter-spacing: 1px;
  }}
  .report-meta {{
    color: #8b949e;
    font-size: 0.9rem;
    margin-top: 8px;
  }}
  .report-meta strong {{ color: #e6edf3; }}

  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 16px;
    margin-bottom: 30px;
  }}
  .stat-card {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 20px;
    text-align: center;
    transition: border-color 0.2s;
  }}
  .stat-card:hover {{ border-color: #00c8c8; }}
  .stat-number {{
    font-size: 2.5rem;
    font-weight: 700;
    display: block;
    line-height: 1;
    margin-bottom: 6px;
  }}
  .stat-label {{
    font-size: 0.75rem;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 1px;
  }}
  .n-blue {{ color: #00c8c8; }}
  .n-green {{ color: #3fb950; }}
  .n-orange {{ color: #f0883e; }}
  .n-red {{ color: #f85149; }}
  .n-purple {{ color: #bc8cff; }}
  .n-yellow {{ color: #e3b341; }}
  .legend {{
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    margin-bottom: 24px;
    padding: 16px;
    background: #161b22;
    border-radius: 8px;
    border: 1px solid #30363d;
  }}
  .legend-item {{ display: flex; align-items: center; gap: 8px; font-size: 0.85rem; }}
  .legend-box {{ width: 14px; height: 14px; border-radius: 3px; }}
  .lb-modified {{ background: #f0883e33; border: 1px solid #f0883e; }}
  .lb-only-a {{ background: #f8514933; border: 1px solid #f85149; }}
  .lb-only-b {{ background: #3fb95033; border: 1px solid #3fb950; }}
  .filters {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 20px;
    align-items: center;
  }}
  .filters label {{ color: #8b949e; font-size: 0.85rem; }}
  .filters select, .filters input {{
    background: #161b22;
    border: 1px solid #30363d;
    color: #e6edf3;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 0.85rem;
  }}
  .btn {{
    padding: 8px 18px;
    border-radius: 6px;
    border: none;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 600;
    transition: all 0.2s;
  }}
  .btn-teal {{ background: #00c8c8; color: #0d1117; }}
  .btn-teal:hover {{ background: #00a8a8; }}
  .btn-export {{ background: #238636; color: #fff; }}
  .btn-export:hover {{ background: #2ea043; }}
  .diff-count {{ color: #8b949e; font-size: 0.85rem; margin-left: auto; }}
  .diff-table {{ width: 100%; border-collapse: collapse; }}
  .diff-table th {{
    background: #161b22;
    color: #8b949e;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 12px 16px;
    text-align: left;
    border-bottom: 1px solid #30363d;
    position: sticky;
    top: 0;
  }}
  .diff-table td {{
    padding: 10px 16px;
    border-bottom: 1px solid #21262d;
    font-size: 0.85rem;
    vertical-align: top;
    font-family: 'Consolas', 'Courier New', monospace;
  }}
  .page-header-row td {{
    background: #1c2128;
    color: #00c8c8;
    font-weight: 700;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    padding: 8px 16px;
    border-bottom: 1px solid #30363d;
    font-family: 'Segoe UI', sans-serif;
  }}
  .line-no {{
    color: #8b949e;
    text-align: center;
    width: 70px;
    font-size: 0.8rem;
  }}
  .type-modified-row td {{ background: rgba(240,136,62,0.06); }}
  .type-only-a-row td {{ background: rgba(248,81,73,0.06); }}
  .type-only-b-row td {{ background: rgba(63,185,80,0.06); }}
  .badge {{
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    white-space: nowrap;
    font-family: 'Segoe UI', sans-serif;
  }}
  .type-modified {{ background: rgba(240,136,62,0.2); color: #f0883e; border: 1px solid #f0883e55; }}
  .type-only-a {{ background: rgba(248,81,73,0.2); color: #f85149; border: 1px solid #f8514955; }}
  .type-only-b {{ background: rgba(63,185,80,0.2); color: #3fb950; border: 1px solid #3fb95055; }}
  .char-removed {{ background: rgba(248,81,73,0.4); color: #ff8080; border-radius: 2px; }}
  .char-added {{ background: rgba(63,185,80,0.4); color: #80ff99; border-radius: 2px; }}
  .removed-line {{ background: rgba(248,81,73,0.25); color: #f85149; }}
  .added-line {{ background: rgba(63,185,80,0.25); color: #3fb950; }}
  .content-cell {{ word-break: break-word; max-width: 400px; line-height: 1.6; }}
  .table-wrap {{
    overflow-x: auto;
    border: 1px solid #30363d;
    border-radius: 10px;
    background: #0d1117;
  }}
  .footer {{
    margin-top: 40px;
    text-align: center;
    color: #484f58;
    font-size: 0.8rem;
    padding-top: 20px;
    border-top: 1px solid #21262d;
  }}
  @media print {{
    .filters, .btn {{ display: none; }}
    body {{ background: white; color: black; }}
  }}
</style>
</head>
<body>
<div class="report-header">
  <h1>📊 PDF Comparison Report</h1>
  <div class="report-meta">
    Generated: {now} &nbsp;|&nbsp;
    PDF A: <strong>{escape_html(pdf1_name)}</strong> vs
    PDF B: <strong>{escape_html(pdf2_name)}</strong>
  </div>
</div>
<div class="stats-grid">
  <div class="stat-card">
    <span class="stat-number n-blue">{differences['total_pages']}</span>
    <span class="stat-label">Total Pages</span>
  </div>
  <div class="stat-card">
    <span class="stat-number n-orange">{differences['pages_with_diffs']}</span>
    <span class="stat-label">Pages with Diffs</span>
  </div>
  <div class="stat-card">
    <span class="stat-number n-blue">{differences['total_differences']}</span>
    <span class="stat-label">Total Differences</span>
  </div>
  <div class="stat-card">
    <span class="stat-number n-yellow">{differences['modified_lines']}</span>
    <span class="stat-label">Modified Lines</span>
  </div>
  <div class="stat-card">
    <span class="stat-number n-red">{differences['only_in_pdf_a']}</span>
    <span class="stat-label">Only in PDF A</span>
  </div>
  <div class="stat-card">
    <span class="stat-number n-green">{differences['only_in_pdf_b']}</span>
    <span class="stat-label">Only in PDF B</span>
  </div>
</div>
<div class="legend">
  <div class="legend-item"><div class="legend-box lb-modified"></div> Modified line (exists in both, content differs)</div>
  <div class="legend-item"><div class="legend-box lb-only-a"></div> Only in PDF A (removed / missing in B)</div>
  <div class="legend-item"><div class="legend-box lb-only-b"></div> Only in PDF B (added / missing in A)</div>
  <div class="legend-item" style="margin-left:auto">
    <span style="background:rgba(248,81,73,0.4);color:#ff8080;padding:2px 6px;border-radius:3px">Red</span>&nbsp;= removed chars &nbsp;
    <span style="background:rgba(63,185,80,0.4);color:#80ff99;padding:2px 6px;border-radius:3px">Green</span>&nbsp;= added chars
  </div>
</div>
<div class="filters">
  <label>Page:</label>
  <select id="filterPage" onchange="applyFilter()">
    <option value="all">All Pages</option>
    {''.join(f'<option value="{p}">Page {p}</option>' for p in sorted(set(d['page'] for d in diff_list)))}
  </select>
  <label>Type:</label>
  <select id="filterType" onchange="applyFilter()">
    <option value="all">All Types</option>
    <option value="Modified">Modified</option>
    <option value="Only in PDF A">Only in PDF A</option>
    <option value="Only in PDF B">Only in PDF B</option>
  </select>
  <label>Search:</label>
  <input type="text" id="searchInput" placeholder="Filter by content..." oninput="applyFilter()">
  <button class="btn btn-teal" onclick="applyFilter()">Apply</button>
  <button class="btn btn-export" onclick="exportCSV()">⬇ Export Filtered CSV</button>
  <span class="diff-count" id="diffCount">Showing {len(diff_list)} difference(s)</span>
</div>
<div class="table-wrap">
<table class="diff-table" id="diffTable">
  <thead>
    <tr>
      <th>LINE NO<br>({escape_html(pdf1_name.upper())})</th>
      <th>LINE NO<br>({escape_html(pdf2_name.upper())})</th>
      <th>TYPE</th>
      <th>{escape_html(pdf1_name.upper())}</th>
      <th>{escape_html(pdf2_name.upper())}</th>
    </tr>
  </thead>
  <tbody id="diffBody">
    {rows_html}
  </tbody>
</table>
</div>
<div class="footer">© 2026 | PDF Comparison Tool | Developed by Atul Raj</div>
<script>
function applyFilter() {{
  const page = document.getElementById('filterPage').value;
  const type = document.getElementById('filterType').value;
  const search = document.getElementById('searchInput').value.toLowerCase();
  const rows = document.querySelectorAll('#diffBody tr');
  let visible = 0;
  let currentPageHeader = null;
  let pageHeaderVisible = false;
  rows.forEach(row => {{
    if (row.classList.contains('page-header-row')) {{
      currentPageHeader = row;
      pageHeaderVisible = false;
      row.style.display = 'none';
      return;
    }}
    const cells = row.querySelectorAll('td');
    if (!cells.length) return;
    const rowPage = row.getAttribute('data-page') || '';
    const rowType = cells[2]?.textContent.trim() || '';
    const content = (cells[3]?.textContent + ' ' + cells[4]?.textContent).toLowerCase();

    const pageMatch = page === 'all' || rowPage === page;
    const typeMatch = type === 'all' || rowType === type;
    const searchMatch = !search || content.includes(search);

    if (pageMatch && typeMatch && searchMatch) {{
      row.style.display = '';
      visible++;
      if (currentPageHeader) {{
        currentPageHeader.style.display = '';
        pageHeaderVisible = true;
        currentPageHeader = null;
      }}
    }} else {{
      row.style.display = 'none';
    }}
  }});
  document.getElementById('diffCount').textContent = `Showing ${{visible}} difference(s)`;
}}
function exportCSV() {{
  const rows = document.querySelectorAll('#diffBody tr:not(.page-header-row):not([style*="display: none"])');
  let csv = 'Page,Line_A,Line_B,Type,Content_A,Content_B\\n';
  rows.forEach(row => {{
    const cells = row.querySelectorAll('td');
    if (cells.length >= 5) {{
      const page = row.getAttribute('data-page') || '';
      const vals = [page, cells[0].textContent, cells[1].textContent,
                    cells[2].textContent, cells[3].textContent, cells[4].textContent];
      csv += vals.map(v => '"' + v.replace(/"/g, '""') + '"').join(',') + '\\n';
    }}
  }});
  const blob = new Blob([csv], {{type: 'text/csv'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'filtered_comparison.csv';
  a.click();
}}
</script>
</body>
</html>"""
    import re
    current_page_val = None
    lines = html.split('\n')
    result_lines = []
    for line in lines:
        if 'class="page-header-row"' in line:
            m = re.search(r'PAGE (\d+)', line)
            if m:
                current_page_val = m.group(1)
        if 'class="diff-row' in line and current_page_val:
            line = line.replace('class="diff-row', f'data-page="{current_page_val}" class="diff-row')
        result_lines.append(line)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result_lines))
def generate_csv_report(differences, pdf1_name, pdf2_name, output_path):
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Page', f'Line_No ({pdf1_name})', f'Line_No ({pdf2_name})',
            'Type', pdf1_name, pdf2_name
        ])
        for diff in differences.get('diff_list', []):
            writer.writerow([
                diff.get('page', ''),
                diff.get('line_no_a', ''),
                diff.get('line_no_b', ''),
                diff.get('type', ''),
                diff.get('content_a', ''),
                diff.get('content_b', '')
            ])
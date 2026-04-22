#!/usr/bin/env python3
"""
Bookmark Manager
Exports bookmarks from multiple browsers (Chrome, Edge, Firefox, Zen, Comet, Vivaldi)
to Netscape HTML and JSON formats.
"""

import os
import json
import sqlite3
import shutil
import tempfile
import argparse
from pathlib import Path
from datetime import datetime

# Browser configurations
BROWSER_CONFIGS = {
    "Chrome": {
        "type": "chromium",
        "path": Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data",
    },
    "Edge": {
        "type": "chromium",
        "path": Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data",
    },
    "Vivaldi": {
        "type": "chromium",
        "path": Path(os.environ.get("LOCALAPPDATA", "")) / "Vivaldi" / "User Data",
    },
    "Comet": {
        "type": "chromium",
        "path": Path(os.environ.get("LOCALAPPDATA", "")) / "Perplexity" / "Comet" / "User Data", # Perplexity's Comet browser
    },
    "Firefox": {
        "type": "firefox",
        "path": Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles",
    },
    "Zen": {
        "type": "firefox",
        "path": Path(os.environ.get("APPDATA", "")) / "zen" / "Profiles",
    },
}

def get_chromium_bookmarks(profile_path):
    """Extract bookmarks from a Chromium-based profile."""
    bookmarks_file = profile_path / "Bookmarks"
    if not bookmarks_file.exists():
        return None
    
    try:
        with open(bookmarks_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("roots", {})
    except Exception as e:
        print(f"  Error reading Chromium bookmarks at {bookmarks_file}: {e}")
        return None

def get_firefox_bookmarks(profile_path):
    """Extract bookmarks from a Firefox-based profile (SQLite)."""
    db_path = profile_path / "places.sqlite"
    if not db_path.exists():
        return None

    # Copy to temp file to avoid locks if browser is open
    temp_dir = tempfile.mkdtemp()
    temp_db = Path(temp_dir) / "places.sqlite"
    try:
        shutil.copy2(db_path, temp_db)
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Query for bookmarks
        # type 1 = URL, 2 = Folder
        query = """
        SELECT b.id, b.parent, b.type, b.title, p.url
        FROM moz_bookmarks b
        LEFT JOIN moz_places p ON b.fk = p.id
        WHERE b.title IS NOT NULL OR p.url IS NOT NULL
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        # Build a tree structure
        bookmarks_by_id = {}
        for row in rows:
            b_id, parent_id, b_type, title, url = row
            bookmarks_by_id[b_id] = {
                "id": b_id,
                "parent": parent_id,
                "type": "folder" if b_type == 2 else "url",
                "name": title if title else (url if url else "Untitled"),
                "url": url,
                "children": []
            }
            
        # Link children to parents
        root_nodes = []
        for b_id, node in bookmarks_by_id.items():
            parent_id = node["parent"]
            if parent_id in bookmarks_by_id:
                bookmarks_by_id[parent_id]["children"].append(node)
            else:
                # Top level folders (usually Toolbar, Menu, Unsorted)
                if node["name"] in ["Bookmarks Toolbar", "Bookmarks Menu", "Other Bookmarks"]:
                    root_nodes.append(node)
        
        conn.close()
        return root_nodes
        
    except Exception as e:
        print(f"  Error reading Firefox bookmarks at {db_path}: {e}")
        return None
    finally:
        shutil.rmtree(temp_dir)

def flatten_chromium(roots, browser_name, profile_name):
    """Convert Chromium's nested structure to a unified format."""
    unified = []
    
    def process_node(node):
        if node.get("type") == "folder":
            return {
                "name": node.get("name"),
                "type": "folder",
                "children": [process_node(child) for child in node.get("children", [])]
            }
        else:
            return {
                "name": node.get("name"),
                "type": "url",
                "url": node.get("url")
            }

    for root_key, root_val in roots.items():
        if root_val.get("children"):
            unified.append({
                "name": f"{browser_name} ({profile_name}) - {root_key.replace('_', ' ').title()}",
                "type": "folder",
                "children": [process_node(child) for child in root_val.get("children", [])]
            })
            
    return unified

def flatten_firefox(root_nodes, browser_name, profile_name):
    """Convert Firefox's structure to a unified format."""
    unified = []
    
    def process_node(node):
        if node["type"] == "folder":
            return {
                "name": node["name"],
                "type": "folder",
                "children": [process_node(child) for child in node["children"]]
            }
        else:
            return {
                "name": node["name"],
                "type": "url",
                "url": node["url"]
            }

    for node in root_nodes:
        unified.append({
            "name": f"{browser_name} ({profile_name}) - {node['name']}",
            "type": "folder",
            "children": [process_node(child) for child in node["children"]]
        })
        
    return unified

def _count_bookmarks(node):
    """Recursively count URL bookmarks in a node."""
    if node["type"] == "url":
        return 1
    return sum(_count_bookmarks(c) for c in node.get("children", []))


def generate_html(bookmarks):
    """Generate a styled Netscape Bookmark HTML file."""
    total = sum(_count_bookmarks(b) for b in bookmarks)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    style = """
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #22263a;
    --border: #2e3354;
    --accent: #7c6aff;
    --accent2: #a78bfa;
    --text: #e2e8f0;
    --text-muted: #8892b0;
    --link: #7dd3fc;
    --link-hover: #38bdf8;
    --folder-icon: #fbbf24;
    --radius: 8px;
    --font: 'Segoe UI', system-ui, -apple-system, sans-serif;
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    font-size: 14px;
    line-height: 1.6;
    min-height: 100vh;
  }
  #app { max-width: 960px; margin: 0 auto; padding: 32px 24px 80px; }

  /* Header */
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
    margin-bottom: 32px;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--border);
  }
  .header-left h1 {
    font-size: 26px;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent2), var(--link));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .header-left p { color: var(--text-muted); font-size: 13px; margin-top: 4px; }
  .stats {
    display: flex;
    gap: 12px;
  }
  .stat {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 8px 16px;
    text-align: center;
  }
  .stat-value { font-size: 20px; font-weight: 700; color: var(--accent2); }
  .stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }

  /* Search */
  .search-wrap { position: relative; margin-bottom: 24px; }
  .search-wrap svg {
    position: absolute; left: 12px; top: 50%; transform: translateY(-50%);
    color: var(--text-muted); pointer-events: none;
  }
  #search {
    width: 100%;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text);
    font-family: var(--font);
    font-size: 14px;
    padding: 10px 12px 10px 40px;
    outline: none;
    transition: border-color 0.2s;
  }
  #search:focus { border-color: var(--accent); }
  #search::placeholder { color: var(--text-muted); }
  #search-count { font-size: 12px; color: var(--text-muted); margin-top: 6px; min-height: 18px; }

  /* Controls */
  .controls { display: flex; gap: 8px; margin-bottom: 20px; }
  .btn {
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text-muted);
    cursor: pointer;
    font-family: var(--font);
    font-size: 12px;
    padding: 6px 14px;
    transition: all 0.15s;
  }
  .btn:hover { border-color: var(--accent); color: var(--accent2); }

  /* Bookmarks tree (Netscape-compatible structure) */
  H1 { display: none; }
  DL { list-style: none; padding-left: 0; }
  #bookmark-tree { padding-left: 0; }
  #bookmark-tree > DT > H3 {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    margin-bottom: 8px;
    padding: 12px 16px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 15px;
    font-weight: 600;
    color: var(--text);
    transition: border-color 0.2s, background 0.2s;
    user-select: none;
  }
  #bookmark-tree > DT > H3:hover { border-color: var(--accent); background: var(--surface2); }
  #bookmark-tree > DT > H3::before { content: "▶"; font-size: 10px; color: var(--accent); transition: transform 0.2s; }
  #bookmark-tree > DT.open > H3::before { transform: rotate(90deg); }
  #bookmark-tree > DT > H3 .folder-icon { color: var(--folder-icon); font-size: 16px; }
  #bookmark-tree > DT > H3 .badge {
    margin-left: auto;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 20px;
    font-size: 11px;
    color: var(--text-muted);
    padding: 1px 8px;
    font-weight: 400;
  }
  #bookmark-tree > DT > DL {
    display: none;
    background: var(--surface);
    border: 1px solid var(--border);
    border-top: none;
    border-radius: 0 0 var(--radius) var(--radius);
    margin-bottom: 8px;
    padding: 8px 0;
  }
  #bookmark-tree > DT.open > DL { display: block; }

  /* Nested folders */
  DL DL { padding-left: 0; }
  DL DT > H3 {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 16px 7px 20px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-muted);
    cursor: pointer;
    user-select: none;
    transition: background 0.15s, color 0.15s;
  }
  DL DT > H3:hover { background: var(--surface2); color: var(--text); }
  DL DT > H3::before { content: "▶"; font-size: 9px; color: var(--border); transition: transform 0.2s; flex-shrink: 0; }
  DL DT.open > H3::before { transform: rotate(90deg); color: var(--accent); }
  DL DT > H3::after { content: "📁"; font-size: 13px; }
  DL DT > DL { display: none; padding-left: 16px; border-left: 2px solid var(--border); margin-left: 28px; }
  DL DT.open > DL { display: block; }

  /* Links */
  DL DT > A {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 16px 6px 20px;
    color: var(--link);
    text-decoration: none;
    font-size: 13px;
    border-radius: 0;
    transition: background 0.15s, color 0.15s;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }
  DL DT > A:hover { background: var(--surface2); color: var(--link-hover); }
  DL DT > A::before { content: "🔗"; font-size: 11px; flex-shrink: 0; opacity: 0.6; }

  /* Hidden items during search */
  DT.hidden { display: none !important; }

  /* No results */
  #no-results { display: none; text-align: center; padding: 48px; color: var(--text-muted); }
  #no-results.visible { display: block; }
</style>"""

    script = """
<script>
(function() {
  function setup() {
    // Make top-level folders collapsible
    var topDTs = document.querySelectorAll('#bookmark-tree > DT');
    topDTs.forEach(function(dt) {
      var h3 = dt.querySelector(':scope > H3');
      var dl = dt.querySelector(':scope > DL');
      if (!h3) return;

      // Add count badge
      var links = dl ? dl.querySelectorAll('A').length : 0;
      if (links > 0) {
        var badge = document.createElement('span');
        badge.className = 'badge';
        badge.textContent = links;
        h3.appendChild(badge);
      }

      h3.addEventListener('click', function() {
        dt.classList.toggle('open');
      });
    });

    // Make nested folders collapsible
    var nestedDTs = document.querySelectorAll('#bookmark-tree DL DT');
    nestedDTs.forEach(function(dt) {
      var h3 = dt.querySelector(':scope > H3');
      if (!h3) return;
      h3.addEventListener('click', function(e) {
        e.stopPropagation();
        dt.classList.toggle('open');
      });
    });

    // Expand all / Collapse all
    document.getElementById('btn-expand').addEventListener('click', function() {
      document.querySelectorAll('#bookmark-tree DT').forEach(function(dt) {
        if (dt.querySelector(':scope > H3')) dt.classList.add('open');
      });
    });
    document.getElementById('btn-collapse').addEventListener('click', function() {
      document.querySelectorAll('#bookmark-tree DT').forEach(function(dt) {
        dt.classList.remove('open');
      });
    });

    // Search
    var searchInput = document.getElementById('search');
    var countEl = document.getElementById('search-count');
    var noResults = document.getElementById('no-results');

    searchInput.addEventListener('input', function() {
      var q = this.value.trim().toLowerCase();
      if (!q) {
        document.querySelectorAll('#bookmark-tree DT').forEach(function(dt) {
          dt.classList.remove('hidden');
        });
        countEl.textContent = '';
        noResults.classList.remove('visible');
        return;
      }

      var allLinkDTs = document.querySelectorAll('#bookmark-tree DT:has(> A)');
      var matched = 0;
      allLinkDTs.forEach(function(dt) {
        var a = dt.querySelector(':scope > A');
        var text = (a.textContent + ' ' + a.href).toLowerCase();
        if (text.includes(q)) {
          dt.classList.remove('hidden');
          matched++;
          // Ensure ancestors are visible and open
          var parent = dt.parentElement;
          while (parent && parent.id !== 'bookmark-tree') {
            if (parent.tagName === 'DT') {
              parent.classList.remove('hidden');
              parent.classList.add('open');
            } else if (parent.tagName === 'DL') {
              // also open its parent DT
            }
            parent = parent.parentElement;
          }
        } else {
          dt.classList.add('hidden');
        }
      });

      // Hide folder DTs that have no visible children
      var folderDTs = document.querySelectorAll('#bookmark-tree DT:has(> H3)');
      folderDTs.forEach(function(dt) {
        var visibleChildren = dt.querySelectorAll('DT:not(.hidden) > A');
        if (visibleChildren.length === 0) {
          dt.classList.add('hidden');
        } else {
          dt.classList.remove('hidden');
          dt.classList.add('open');
        }
      });

      countEl.textContent = matched + ' bookmark' + (matched !== 1 ? 's' : '') + ' matched';
      noResults.classList.toggle('visible', matched === 0);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup);
  } else {
    setup();
  }
})();
</script>"""

    lines = [
        '<!DOCTYPE NETSCAPE-Bookmark-file-1>',
        '<!-- This is an automatically generated file. DO NOT EDIT! -->',
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        '<TITLE>Bookmarks</TITLE>',
        style,
        '<body>',
        '<div id="app">',
        '  <div class="header">',
        '    <div class="header-left">',
        '      <h1>Bookmarks</h1>',
        f'     <p>Exported {generated}</p>',
        '    </div>',
        '    <div class="stats">',
        f'      <div class="stat"><div class="stat-value">{total}</div><div class="stat-label">Bookmarks</div></div>',
        f'      <div class="stat"><div class="stat-value">{len(bookmarks)}</div><div class="stat-label">Sources</div></div>',
        '    </div>',
        '  </div>',
        '  <div class="search-wrap">',
        '    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>',
        '    <input id="search" type="text" placeholder="Search bookmarks..." autocomplete="off">',
        '  </div>',
        '  <div id="search-count"></div>',
        '  <div class="controls">',
        '    <button class="btn" id="btn-expand">Expand All</button>',
        '    <button class="btn" id="btn-collapse">Collapse All</button>',
        '  </div>',
        '  <div id="no-results">No bookmarks matched your search.</div>',
        '<H1>Bookmarks</H1>',
        '<DL id="bookmark-tree"><p>',
    ]

    def add_node(node, indent):
        space = "    " * indent
        if node["type"] == "folder":
            lines.append(f'{space}<DT><H3>{node["name"]}</H3>')
            lines.append(f'{space}<DL><p>')
            for child in node.get("children", []):
                add_node(child, indent + 1)
            lines.append(f'{space}</DL><p>')
        else:
            url = node.get("url") or ""
            name = node.get("name") or url
            lines.append(f'{space}<DT><A HREF="{url}">{name}</A>')

    for root in bookmarks:
        add_node(root, 1)

    lines.append('</DL><p>')
    lines.append('</div>')
    lines.append(script)
    lines.append('</body>')
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Export bookmarks from multiple browsers to HTML and JSON.")
    parser.add_argument("-o", "--output", help="Base name for output files (default: bookmarks)", default="bookmarks")
    args = parser.parse_args()

    all_bookmarks = []
    
    print("Searching for browser bookmarks...")
    
    for browser_name, config in BROWSER_CONFIGS.items():
        base_path = config["path"]
        if not base_path.exists():
            continue
            
        print(f"Checking {browser_name}...")
        
        if config["type"] == "chromium":
            # Check for profiles (Default, Profile 1, etc.)
            profiles = []
            if (base_path / "Bookmarks").exists():
                profiles.append(base_path) # Single profile/Direct path
            
            # Scan subdirectories for "Bookmarks" file
            for item in base_path.iterdir():
                if item.is_dir() and (item / "Bookmarks").exists():
                    profiles.append(item)
            
            for profile in profiles:
                profile_name = profile.name
                print(f"  Found profile: {profile_name}")
                roots = get_chromium_bookmarks(profile)
                if roots:
                    all_bookmarks.extend(flatten_chromium(roots, browser_name, profile_name))
                    
        elif config["type"] == "firefox":
            # Firefox profiles are usually folders in the Profiles dir
            for profile in base_path.iterdir():
                if profile.is_dir() and (profile / "places.sqlite").exists():
                    profile_name = profile.name
                    print(f"  Found profile: {profile_name}")
                    root_nodes = get_firefox_bookmarks(profile)
                    if root_nodes:
                        all_bookmarks.extend(flatten_firefox(root_nodes, browser_name, profile_name))

    if not all_bookmarks:
        print("No bookmarks found!")
        return

    # Save to JSON
    json_path = f"{args.output}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_bookmarks, f, indent=4)
    print(f"Saved JSON export to: {os.path.abspath(json_path)}")

    # Save to HTML
    html_path = f"{args.output}.html"
    html_content = generate_html(all_bookmarks)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Saved HTML export to: {os.path.abspath(html_path)}")
    
    print("\nSuccess! You can now import 'bookmarks.html' into any browser.")

if __name__ == "__main__":
    main()

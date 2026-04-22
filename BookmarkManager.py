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

def generate_html(bookmarks):
    """Generate Netscape Bookmark HTML string."""
    lines = [
        '<!DOCTYPE NETSCAPE-Bookmark-file-1>',
        '<!-- This is an automatically generated file.',
        '     It will be read and overwritten.',
        '     DO NOT EDIT! -->',
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        '<TITLE>Bookmarks</TITLE>',
        '<H1>Bookmarks</H1>',
        '<DL><p>'
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
            lines.append(f'{space}<DT><A HREF="{node["url"]}">{node["name"]}</A>')

    for root in bookmarks:
        add_node(root, 1)

    lines.append('</DL><p>')
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

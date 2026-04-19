#!/usr/bin/env python3
"""
Directory Tree Generator
Creates a UTF-8 tree diagram of folders and files in a Windows directory.
"""

import os
import sys
from pathlib import Path


def generate_tree(directory, prefix="", is_last=True, show_hidden=False):
    """
    Recursively generate a tree structure of the directory.
    
    Args:
        directory: Path object or string path to the directory
        prefix: String prefix for the current line (for indentation)
        is_last: Boolean indicating if this is the last item in current level
        show_hidden: Boolean to show hidden files/folders
    
    Returns:
        List of strings representing the tree structure
    """
    directory = Path(directory)
    
    if not directory.exists():
        return [f"Error: Directory '{directory}' does not exist"]
    
    if not directory.is_dir():
        return [f"Error: '{directory}' is not a directory"]
    
    tree_lines = []
    
    try:
        # Get all items in the directory
        items = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        
        # Filter out hidden files if requested
        if not show_hidden:
            items = [item for item in items if not item.name.startswith('.')]
        
        for index, item in enumerate(items):
            is_last_item = (index == len(items) - 1)
            
            # Determine the connector symbol
            connector = "└── " if is_last_item else "├── "
            
            # Add the current item
            tree_lines.append(f"{prefix}{connector}{item.name}")
            
            # If it's a directory, recurse into it
            if item.is_dir():
                # Determine the extension for the prefix
                extension = "    " if is_last_item else "│   "
                try:
                    subtree = generate_tree(
                        item, 
                        prefix=prefix + extension, 
                        is_last=is_last_item,
                        show_hidden=show_hidden
                    )
                    tree_lines.extend(subtree)
                except PermissionError:
                    tree_lines.append(f"{prefix}{extension}[Permission Denied]")
                    
    except PermissionError:
        tree_lines.append(f"{prefix}[Permission Denied]")
    
    return tree_lines


def save_tree_to_file(directory, output_file=None, show_hidden=False):
    """
    Generate tree and save to a file.
    
    Args:
        directory: Path to the root directory
        output_file: Output file path (optional, defaults to tree.txt in current dir)
        show_hidden: Boolean to show hidden files/folders
    """
    directory = Path(directory)
    
    if output_file is None:
        output_file = Path("tree.txt")
    else:
        output_file = Path(output_file)
    
    # Generate the tree
    tree_lines = [str(directory.absolute())]
    tree_lines.extend(generate_tree(directory, show_hidden=show_hidden))
    
    # Write to file with UTF-8 encoding
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(tree_lines))
    
    print(f"Tree diagram saved to: {output_file.absolute()}")
    return output_file


def print_tree(directory, show_hidden=False):
    """
    Print the tree structure to console.
    
    Args:
        directory: Path to the root directory
        show_hidden: Boolean to show hidden files/folders
    """
    directory = Path(directory)
    
    # Print the tree
    print(str(directory.absolute()))
    tree_lines = generate_tree(directory, show_hidden=show_hidden)
    for line in tree_lines:
        print(line)


def main():
    """Main function to handle command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate a UTF-8 tree diagram of a directory structure',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Print tree to console
  python directorytree.py C:\\Users\\YourName\\Documents
  
  # Save tree to a file
  python directorytree.py C:\\Users\\YourName\\Documents -o output.txt
  
  # Include hidden files
  python directorytree.py C:\\Users\\YourName\\Documents --show-hidden
        """
    )
    
    parser.add_argument(
        'directory',
        help='Path to the directory to diagram'
    )
    
    parser.add_argument(
        '-o', '--output',
        help='Output file path (if not specified, prints to console)',
        default=None
    )
    
    parser.add_argument(
        '--show-hidden',
        action='store_true',
        help='Include hidden files and folders (starting with .)'
    )
    
    args = parser.parse_args()
    
    try:
        if args.output:
            save_tree_to_file(args.directory, args.output, args.show_hidden)
        else:
            print_tree(args.directory, args.show_hidden)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
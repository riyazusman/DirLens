import os
import sys
import ctypes
import webbrowser
from datetime import datetime
import heapq
import html
import subprocess

def is_admin():
    # Check if the script is running with elevated privileges.
    try:
        # Check for Windows
        return ctypes.windll.shell32.IsUserAnAdmin()
    except AttributeError:
        # Check for Linux/macOS
        return os.geteuid() == 0

def format_size(bytes_size):
    # Helper to format bytes into readable units.
    units = ['B', 'KB', 'MB', 'GB', 'TB','PB', 'EB']
    for unit in units[:-1]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} {units[-1]}"

def scan_directory(path, state=None):
    # Recursively scans a directory and returns a nested dictionary containing the structure and cumulative sizes.
    
    # Initialize the state dictionary on the first call
    if state is None:
        state = {'dirs_scanned': 0, 'files_scanned': 0, 'ext_stats': {}, 'top_files': []}

    state['dirs_scanned'] += 1
    
    # Update terminal output every 50 directories to prevent performance lag
    if state['dirs_scanned'] % 50 == 0:
        safe_path_str = str(path).encode('ascii', 'replace').decode('ascii')
        trunc_path = safe_path_str[:45].ljust(45)
        message = f"Scanning: {state['dirs_scanned']} folders | {state['files_scanned']} files | {trunc_path}"
        sys.stdout.write(f"\r{message.ljust(100)}")
        sys.stdout.flush()

    tree = {
        'name': os.path.basename(path) or path,
        'path': path,
        'size': 0,
        'exclusive_size': 0,
        'children': [],
        'error': None
    }

    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    size = entry.stat(follow_symlinks=False).st_size
                    tree['size'] += size
                    tree['exclusive_size'] += size
                    state['files_scanned'] += 1

                    # File extension tracking
                    _, ext = os.path.splitext(entry.name)
                    ext = ext.lower() or "[no extension]"
                    
                    if ext not in state['ext_stats']:
                        state['ext_stats'][ext] = {'count': 0, 'size': 0}
                        
                    state['ext_stats'][ext]['count'] += 1
                    state['ext_stats'][ext]['size'] += size

                    # Top 10 Files tracking
                    if len(state['top_files']) < 10:
                        heapq.heappush(state['top_files'], (size, entry.path, entry.name))
                    else:
                        heapq.heappushpop(state['top_files'], (size, entry.path, entry.name))
                    
                elif entry.is_dir(follow_symlinks=False):
                    child_tree = scan_directory(entry.path, state)
                    tree['size'] += child_tree['size']
                    tree['children'].append(child_tree)
                    
            except (PermissionError, FileNotFoundError, OSError):
                continue
                
    except PermissionError:
        tree['error'] = 'Permission Denied'
    except FileNotFoundError:
        tree['error'] = 'Not Found'
    except OSError as e:
        # Catch network drops or hardware-level read errors on the directory itself
        tree['error'] = f'I/O Error: {e.strerror}'

    return tree

def print_tree(node, prefix="", is_last=True, current_depth=0, max_depth=2):
    # Recursively prints the directory tree with sizes using visual branch characters. Sorts children by size (largest first) and stops at max_depth.

    # Determine the branch character based on position
    if current_depth == 0:
        connector = ""
    else:
        connector = "└── " if is_last else "├── "
        
    size_str = format_size(node['size'])
    
    # Indicate if a folder was skipped due to permissions
    if node.get('error'):
        display_name = f"{node['name']} [{node['error']}]"
    else:
        display_name = node['name']
        
    print(f"{prefix}{connector}{display_name} ({size_str})")
    
    # Stop digging if we hit the depth limit
    if current_depth >= max_depth:
        return
        
    # Sort subdirectories by size (largest to smallest)
    children = sorted(node['children'], key=lambda x: x['size'], reverse=True)
    count = len(children)
    
    for i, child in enumerate(children):
        is_last_child = (i == count - 1)
        
        # Calculate the spacing for the next level down
        if current_depth == 0:
            extension = ""
        else:
            extension = "    " if is_last else "│   "
            
        next_prefix = prefix + extension
        print_tree(child, next_prefix, is_last_child, current_depth + 1, max_depth)

def export_to_html(node, state, output_filename="dirlens_report.html"):
    # Generates the HTML report with collapsible tree nodes and statistics.

    def get_user_path(p):
        # Strips internal Windows long-path prefixes for the UI.
        if p.startswith('\\\\?\\UNC\\'):
            return '\\\\' + p[8:]
        if p.startswith('\\\\?\\'):
            return p[4:]
        return p
    
    def build_html_list(current_node):
        # Recursively builds the HTML list for the current node and its children.
        size_str = format_size(current_node['size'])
        escaped_name = html.escape(get_user_path(current_node['name']))
        
        # Handle permission error styling
        if current_node.get('error'):
            escaped_error = html.escape(str(current_node['error']))
            name_display = f"{escaped_name} <span class='error'>[{escaped_error}]</span>"
        else:
            name_display = escaped_name

        # Sort children by size descending
        children = sorted(current_node['children'], key=lambda x: x['size'], reverse=True)
        
        if not children:
            return f"<li>{name_display} <span class='size'>({size_str})</span></li>\n"
            
        list_html = f"<li><span class='caret'>{name_display} <span class='size'>({size_str})</span></span>\n"
        list_html += "<ul class='nested'>\n"
        for child in children:
            list_html += build_html_list(child)
        list_html += "</ul>\n</li>\n"
        return list_html

    # File Extension Summary
    sorted_exts = sorted(state['ext_stats'].items(), key=lambda x: x[1]['size'], reverse=True)[:10]
    
    ext_html = "<div class='ext-summary'><h3>Top 10 File Types by Size</h3><ul class='ext-list'>"
    for ext, data in sorted_exts:
        safe_ext = html.escape(ext)
        ext_html += f"<li><span class='ext-name'>{safe_ext}</span> <span class='size'>{format_size(data['size'])} ({data['count']} files)</span></li>"
    ext_html += "</ul></div>"

    # Top 10 Largest Files
    sorted_files = sorted(state['top_files'], key=lambda x: x[0], reverse=True)
    files_html = "<div class='sidebar-section'><h3>Top 10 Largest Files</h3><ul class='ext-list'>"
    for f_size, f_path, f_name in sorted_files:
        user_path = get_user_path(f_path)
        safe_path = html.escape(user_path, quote=True)
        safe_name = html.escape(f_name)
        files_html += f"<li><span class='ext-name' title='{safe_path}'>{safe_name}</span> "
        files_html += f"<div class='item-meta'><span class='size'>{format_size(f_size)}</span>"
        files_html += f"<button class='copy-btn' data-path='{safe_path}'>📋</button></div></li>"
    files_html += "</ul></div>"

    # Top 10 Largest Folders
    all_folders = []
    def gather_folders(curr_node):
        all_folders.append((curr_node['exclusive_size'], curr_node['path'], curr_node['name']))
        for child in curr_node['children']:
            gather_folders(child)
            
    gather_folders(node)
    top_folders = sorted(all_folders, key=lambda x: x[0], reverse=True)[:10]
    
    folders_html = "<div class='sidebar-section'><h3>Top 10 Folders (Exclusive Size)</h3><ul class='ext-list'>"
    for f_size, f_path, f_name in top_folders:
        user_path = get_user_path(f_path)
        safe_path = html.escape(user_path, quote=True)
        safe_name = html.escape(f_name)
        folders_html += f"<li><span class='ext-name' title='{safe_path}'>{safe_name}</span> "
        folders_html += f"<div class='item-meta'><span class='size'>{format_size(f_size)}</span>"
        folders_html += f"<button class='copy-btn' data-path='{safe_path}'>📋</button></div></li>"
    folders_html += "</ul></div>"


    # HTML Template
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>DirLens Report</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                background-color: #ffffff;
                color: #111111;
                margin: 40px auto;
                max-width: 1400px;
                line-height: 1.6;
                display: flex;
                gap: 80px; /* Increased negative space */
            }}
            .main-content {{ flex: 2; padding-left: 40px; }}
            h2, h3 {{ font-weight: 500; border-bottom: 1px solid #111; padding-bottom: 10px; margin-top: 0; }}
            ul {{ list-style-type: none; margin: 0; padding: 0; }}
            #rootUL {{ margin-top: 20px; }}
            li {{ margin: 6px 0; }}
            .nested {{
                display: none;
                margin-left: 20px;
                padding-left: 15px;
                border-left: 1px solid #e0e0e0;
            }}
            .active {{ display: block; }}
            .caret {{ cursor: pointer; user-select: none; font-weight: 500; }}
            .caret::before {{
                content: "\\25B6";
                color: #111;
                display: inline-block;
                margin-right: 8px;
                font-size: 0.75em;
                transition: transform 0.15s ease-in-out;
            }}
            .caret-down::before {{ transform: rotate(90deg); }}
            .sidebar {{ flex: 1; border-left: 1px solid #111; padding-left: 40px; padding-right: 40px;}}
            .sidebar-section {{ margin-bottom: 50px; }}
            .size {{ color: #777; font-size: 0.9em; font-weight: normal; margin-left: 8px; white-space: nowrap; }}
            .ext-list li {{ display: flex; justify-content: space-between; margin-bottom: 12px; gap: 20px; }}
            .ext-name {{ font-weight: 500; word-break: break-all; }}
            .error {{ color: #d32f2f; font-size: 0.85em; margin-left: 4px; }}
            .item-meta {{ display: flex; align-items: center; gap: 12px; }}
            .copy-btn {{
                background: transparent; border: 0px solid #111; color: #111;
                font-family: inherit; font-size: 0.75em; padding: 2px 8px;
                cursor: pointer; transition: all 0.2s ease;
            }}
            /*.copy-btn:hover {{
                background: #111; color: #ffffff;
            }}*/
            @media (max-width: 900px) {{
                body {{
                    flex-direction: column;
                    gap: 40px;
                    margin: 20px;
                }}
                .main-content {{
                    padding-left: 0;
                }}
                .sidebar {{
                    border-left: none;
                    border-top: 1px solid #111;
                    padding-left: 0;
                    padding-right: 0;
                    padding-top: 40px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="main-content">
            <h2>Folder Tree Analysis</h2>
            <ul id="rootUL">
                {build_html_list(node)}
            </ul>
        </div>
        <div class="sidebar">
            {folders_html}
            {files_html}
            {ext_html}
        </div>

        <script>
            var toggler = document.getElementsByClassName("caret");
            for (var i = 0; i < toggler.length; i++) {{
                toggler[i].addEventListener("click", function(e) {{
                    // Prevent toggling if selecting text
                    if(window.getSelection().toString().length === 0) {{
                        this.parentElement.querySelector(".nested").classList.toggle("active");
                        this.classList.toggle("caret-down");
                    }}
                }});
            }}
            
            // Auto-expand the very first root node
            if (toggler.length > 0) {{
                toggler[0].click();
            }}

            // Clipboard Copy Functionality
            var copyButtons = document.getElementsByClassName("copy-btn");
            for (var j = 0; j < copyButtons.length; j++) {{
                copyButtons[j].addEventListener("click", function() {{
                    var btn = this;
                    var path = btn.getAttribute("data-path");
                    
                    navigator.clipboard.writeText(path).then(function() {{
                        var originalText = btn.innerText;
                        btn.innerText = "✅";
                        
                        // Reset the button after 2 seconds
                        setTimeout(function() {{
                            btn.innerText = originalText;
                            btn.style.background = "transparent";
                            btn.style.color = "#111";
                    }}, 2000);
                    }}).catch(function(err) {{
                        console.error('Failed to copy: ', err);
                    }});
                }});
            }}
        </script>
    </body>
    </html>
    """

    with open(output_filename, "w", encoding="utf-8") as file:
        file.write(html_template)
        
    return os.path.abspath(output_filename)

if __name__ == "__main__":
    # Increase recursion depth for deeply nested directories
    sys.setrecursionlimit(5000)

    # Enforce elevated permissions
    if not is_admin():
        if os.name == 'nt':
            choice = input("Admin privileges are recommended to include system folders. Elevate now? (y/n): ").strip().lower()
            if choice == 'y':
                try:
                    # Safely quote and reconstruct arguments for Windows shell
                    safe_args = subprocess.list2cmdline(sys.argv)

                    # Attempt to spawn the elevated process
                    ret = ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", sys.executable, safe_args, None, 1
                    )
                    if ret > 32:
                        sys.exit()  # Exit the original un-elevated process
                    else:
                        print("Elevation cancelled at UAC prompt. Proceeding with standard privileges...\n")
                except Exception:
                    # Catches the error if the user clicks "No" on the UAC prompt
                    print("Elevation cancelled. Proceeding with standard privileges...\n")
            else:
                print("Proceeding with standard privileges...\n")
        else:
            print("Note: Running without 'sudo'. Restricted folders will be skipped.\n")

    # CLI Parameter and Smart Default
    if len(sys.argv) > 1:
        # If a parameter was provided via CLI, use it
        default_path = sys.argv[1].strip('"\'')
    else:
        # Default to the directory where the script is located
        default_path = os.path.abspath(os.path.dirname(__file__))

        # Default to the user directory
        #default_path = os.path.expanduser("~") 

    # Allow dynamic path selection
    user_input = input(f"Enter path to scan (Enter to use '{default_path}', Type 'q' to quit): ").strip()

    if not user_input:
        target_path = default_path
    else:
        if user_input.lower() == 'q':
            print("Exiting...")
            sys.exit(0)
        # Strip quotes if the user dragged and dropped a folder into the terminal
        target_path = user_input.strip('"\'')

    safe_target_path = str(target_path).encode('ascii', 'replace').decode('ascii')

    # Validate the target path before proceeding
    if not os.path.exists(target_path):
        print(f"Error: The path '{safe_target_path}' does not exist.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Ensure the target path is a directory
    if not os.path.isdir(target_path):
        print(f"Error: The path '{safe_target_path}' is a file, not a directory.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Convert to an absolute path to ensure accurate prefixing
    target_path = os.path.abspath(target_path)
    
    # Bypass Windows MAX_PATH 260-character limit
    if os.name == 'nt' and not target_path.startswith('\\\\?\\'):
        if target_path.startswith('\\\\'):
            # Handle UNC network paths (e.g., \\server\share -> \\?\UNC\server\share)
            target_path = f"\\\\?\\UNC\\{target_path[2:]}"
        else:
            # Handle standard local paths (e.g., C:\folder -> \\?\C:\folder)
            target_path = f"\\\\?\\{target_path}"

    print(f"Starting scan of {safe_target_path}...\n")

    # Initialize state dictionary
    scan_state = {'dirs_scanned': 0, 'files_scanned': 0, 'ext_stats': {}, 'top_files': []}
    
    # Run the scanner
    result = scan_directory(target_path, scan_state)
    
    # Clear the dynamic progress line
    sys.stdout.write("\r" + " " * 100 + "\r")
    sys.stdout.flush()
    
    print("Scan complete! Generating report...\n")
    
    # Run the formatter with a depth of 2 to keep it readable on console
    # print_tree(result, max_depth=2)

    # Generate the HTML file and open it automatically
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"dirlens_report_{timestamp}.html"
    html_path = export_to_html(result, scan_state, output_filename=report_filename)
    print(f"Report saved to: {html_path}")
    webbrowser.open(f"file://{html_path}")

    input("\nPress Enter to exit...")
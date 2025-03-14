import os
from collections import defaultdict
from datetime import datetime
from utils import Colors, format_win_path, ensure_logs_dir


def print_hierarchical(items):
    """Print files in hierarchical format with full paths"""
    structure = defaultdict(list)

    for full_path in sorted(items):
        parent = os.path.dirname(full_path)
        name = os.path.basename(full_path)
        structure[parent].append((name, os.path.isdir(full_path)))

    for parent in sorted(structure.keys()):
        print(f"{Colors.CYAN}{parent}\\{Colors.END}")
        for name, is_dir in sorted(structure[parent]):
            if is_dir:
                print(f"  ├─ {Colors.CYAN}{name}\\{Colors.END}")
            else:
                print(f"  ├─ {name}")


def export_to_file(items, filename):
    """Export list to logs folder with proper full paths"""
    logs_dir = ensure_logs_dir()
    full_path = os.path.join(logs_dir, filename)

    structure = defaultdict(list)
    for full_item in sorted(items):
        parent = os.path.dirname(full_item)
        name = os.path.basename(full_item)
        structure[parent].append((name, os.path.isdir(full_item)))

    # Explicitly use UTF-8 encoding to handle special characters
    with open(full_path, 'w', encoding='utf-8') as f:
        for parent in sorted(structure.keys()):
            f.write(f"{parent}\\{os.linesep}")  # Using os.linesep instead of \n

            for name, is_dir in sorted(structure[parent]):
                if is_dir:
                    f.write(f"  {name}\\\n")
                else:
                    f.write(f"  {name}\n")

            f.write("\n")

    print(f"{Colors.GREEN}List exported to {format_win_path(full_path)}{Colors.END}")


def paginated_display(items, title, max_per_page=20):
    """Display items with pagination controls"""
    if not items:
        return

    page = 0
    total = len(items)
    items = sorted(items)

    while True:
        start = page * max_per_page
        end = start + max_per_page
        current_page = items[start:end]

        print(f"\n{Colors.YELLOW}{title} ({total} items){Colors.END}")
        print(f"Page {page+1}/{(total-1)//max_per_page+1}\n")
        print_hierarchical(current_page)

        if end < total:
            choice = input(f"\n{Colors.CYAN}N-next, P-previous, Q-quit: {Colors.END}").lower()
            if choice == 'n':
                page = min(page + 1, total // max_per_page)
            elif choice == 'p':
                page = max(page - 1, 0)
            elif choice == 'q':
                break
            os.system('cls' if os.name == 'nt' else 'clear')
        else:
            break


def show_sample(items, title, base_folder=None):
    """Interactive display with multiple viewing options"""
    items = sorted(items) if isinstance(items, set) else items
    if not items:
        return

    # Convert to absolute paths if base folder provided
    abs_items = []
    for item in items:
        if base_folder and not os.path.isabs(item):
            abs_item = os.path.join(base_folder, item)
            abs_items.append(format_win_path(abs_item))
        else:
            abs_items.append(format_win_path(item))

    print(f"\n{Colors.YELLOW}{title} ({len(abs_items)} items){Colors.END}")
    print(f"{Colors.CYAN}1. Show first 3 items")
    print("2. Browse all (paginated)")
    print(f"3. Export to file{Colors.END}")

    choice = input(f"{Colors.MAGENTA}Choose option: {Colors.END}").strip()

    if choice == '1':
        print(f"\n{Colors.YELLOW}First 3 items:{Colors.END}")
        print_hierarchical(abs_items[:3])
    elif choice == '2':
        paginated_display(abs_items, title)
    elif choice == '3':
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = title.lower().replace(' ', '_')
        filename = f"{safe_title}_{timestamp}.txt"
        export_to_file(abs_items, filename)

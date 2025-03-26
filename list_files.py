import os


def get_file_size(filepath):
    size = os.path.getsize(filepath)
    if size < 1024:
        return f"{size} bytes"
    elif size < 1024*1024:
        return f"{size/1024:.1f} KB"
    else:
        return f"{size/(1024*1024):.1f} MB"


def list_files(startpath):
    for root, dirs, files in os.walk(startpath, followlinks=True):
        # Include hidden directories (starting with .)
        dirs[:] = [d for d in dirs]  # Remove the hidden filter

        level = root.replace(startpath, '').count(os.sep)
        indent = '│   ' * level
        print(f'{indent}📁 {os.path.basename(root)}/')
        subindent = '│   ' * (level + 1)

        # List all files, including hidden ones
        for f in sorted(files):
            filepath = os.path.join(root, f)
            is_hidden = f.startswith('.')
            icon = '🔒' if is_hidden else '📄'
            print(f'{subindent}{icon} {f:<30} {get_file_size(filepath)}')


if __name__ == "__main__":
    print("Listing all files (including hidden):")
    print("─" * 50)
    list_files('.')

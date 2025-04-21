

# Read the file and parse `.data` and `.text` segments
with open(file_name, 'r', encoding='utf-8') as file:
    print(f"Reading file: {file_name}")
    for line in file:
        # Remove comments and strip whitespace
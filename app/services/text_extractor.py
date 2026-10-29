def extract_txt_text(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8-sig") as f:
        return f.read()
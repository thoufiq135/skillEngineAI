from pathlib import Path

text = Path("backend/api.py").read_text()

start = text.index("def create_access_token")
end = text.index("def verify_access_token")

print(text[start:end])

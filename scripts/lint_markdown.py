import glob
from pathlib import Path
import re
import subprocess
import sys

# Strips YAML headers "front matter" from markdown files for linting with pymarkdownlnt (maybe there is a better way)

errors = False
pymarkdown_config = str(Path(__file__).parent / "pymarkdown.yaml")
for doc in glob.glob("**/*.md", recursive=True):
    with open(doc, "r") as file:
        file_contents = file.read()
        match = re.search(r"^---\s*$(.*?)^---\s*$(.*)", file_contents, re.DOTALL | re.MULTILINE)
        markdown = match.group(2) if match else file_contents
        result = subprocess.run(["pymarkdown", "--config", pymarkdown_config, "scan-stdin"], input=markdown, capture_output=True, text=True)
        for line in filter(None, result.stdout.split("\\n")):
            print(line.strip().replace("stdin:", f"{doc}:"))
        errors |= result.returncode != 0

if errors:
    sys.exit(1)

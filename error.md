# Claude Code File Write Error - Known Bug & Workarounds

## The Problem

When using Claude Code CLI, you may encounter the error:
```
"File has not been read yet. Read it first before writing to it."
```

This occurs even when you've successfully read the file immediately before attempting to write.

## Root Cause

This is a **known bug in Claude Code** where the Read and Write/Edit tools have broken state synchronization:

1. The Read tool maintains file state in its own context
2. The Write/Edit tools have a separate state context
3. These contexts don't always communicate with each other properly
4. Result: The Write tool doesn't recognize that the Read just occurred

### Windows/MINGW-Specific Issues

On Windows systems (MINGW64), additional issues compound the problem:
- Line ending conversion (CRLF vs LF) may be detected as file modification
- File system timestamp resolution differences
- Internal file hash/tracking cache doesn't persist correctly between tool calls

## Workarounds

### 1. Use Python via Bash (Recommended)

```bash
python << 'SCRIPT'
from pathlib import Path

file_path = Path('C:/GitHub/SHATTERED/path/to/file.txt')
content = '''
Your file content here
'''
file_path.write_text(content)
print(f"Written to {file_path}")
SCRIPT
```

### 2. Use Bash Heredocs for Simple Files

```bash
cat > /path/to/file.txt << 'EOF'
new content here

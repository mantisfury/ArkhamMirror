"""
Allow running workers as a module:
    python -m arkham_frame.workers --pool cpu-ner --count 2
"""

from .cli import main

if __name__ == "__main__":
    main()

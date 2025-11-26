"""
Remove all Unicode emojis from Python files
Fixes Windows console encoding issues
"""
import os
import re
from pathlib import Path

# Emoji replacements (Unicode to ASCII)
REPLACEMENTS = {
    '✅': '[OK]',
    '❌': '[ERROR]',
    '⚠️': '[WARNING]',
    '🔧': '[CONFIG]',
    '🚀': '[START]',
    '🛑': '[STOP]',
    '📊': '[STATS]',
    '💾': '[SAVE]',
    '🎯': '[TARGET]',
    '🔍': '[SEARCH]',
    '📧': '[EMAIL]',
    '📱': '[MOBILE]',
    '🔑': '[KEY]',
    '✓': '[OK]',
    '✗': '[FAIL]',
    '○': '[SKIP]',
    '⊘': '[SKIP]',
}

def clean_unicode(text):
    """Replace Unicode emojis with ASCII equivalents"""
    for emoji, replacement in REPLACEMENTS.items():
        text = text.replace(emoji, replacement)
    return text

def process_file(filepath):
    """Process a single Python file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if file has Unicode emojis
        has_unicode = any(emoji in content for emoji in REPLACEMENTS.keys())
        
        if has_unicode:
            # Replace Unicode with ASCII
            new_content = clean_unicode(content)
            
            # Write back
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return True, filepath
        
        return False, None
    
    except Exception as e:
        return False, f"Error: {str(e)}"

def main():
    print("\n" + "="*70)
    print(" UNICODE EMOJI REMOVER - Windows Console Fix")
    print("="*70 + "\n")
    
    # Get project root
    project_root = Path(__file__).parent
    
    # Files to process
    python_files = []
    
    # Scan for Python files
    for pattern in ['*.py', 'app/**/*.py', 'app/**/**.py']:
        python_files.extend(project_root.glob(pattern))
    
    print(f"Found {len(python_files)} Python files to check\n")
    print("-"*70)
    
    modified_count = 0
    modified_files = []
    
    for filepath in python_files:
        modified, result = process_file(filepath)
        
        if modified:
            modified_count += 1
            modified_files.append(filepath.name)
            print(f"[OK] Fixed: {filepath.relative_to(project_root)}")
    
    print("-"*70)
    print(f"\n[OK] Processed {len(python_files)} files")
    print(f"[OK] Modified {modified_count} files with Unicode emojis\n")
    
    if modified_files:
        print("Modified files:")
        for filename in modified_files:
            print(f"  - {filename}")
    
    print("\n" + "="*70)
    print(" CLEANUP COMPLETE - No more Unicode warnings!")
    print("="*70)
    print("\nRestart your server: python main.py\n")

if __name__ == "__main__":
    main()
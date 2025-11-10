#!/usr/bin/env python3
"""
Script to clean up complex chain functions and simplify the chain building architecture.
This will remove the complex ATM scanning functions and replace them with comments.
"""

def cleanup_complex_functions():
    """Remove complex chain functions and replace with simplified architecture."""
    
    with open('main.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Check for complex function starts that should be removed
        if ('def request_atm_scan_for_ts_chain(' in line or
            'def complete_atm_scan_and_build_chain(' in line):
            
            # Skip the function - find the next function definition or class definition
            print(f"Found complex function at line {i+1}: {line.strip()}")
            
            # Skip until we find the next function/class definition at the same indentation level
            while i < len(lines):
                current_line = lines[i]
                
                # If we find another function/method at same level (4 spaces) or class, stop
                if (current_line.startswith('    def ') and 
                    'def request_atm_scan_for_ts_chain(' not in current_line and
                    'def complete_atm_scan_and_build_chain(' not in current_line):
                    break
                elif current_line.startswith('class '):
                    break
                elif current_line.strip() == '' and i+1 < len(lines) and lines[i+1].startswith('    def '):
                    # Empty line before next function
                    i += 1
                    break
                
                i += 1
            
            # Add a comment explaining what was removed
            new_lines.append('    # ===== COMPLEX FUNCTION REMOVED =====\n')
            new_lines.append('    # This complex chain building function was removed during simplification.\n')
            new_lines.append('    # All chains now use the unified master ATM calculation.\n')
            new_lines.append('\n')
            continue
        
        new_lines.append(line)
        i += 1
    
    # Write the cleaned up file
    with open('main_cleaned.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"Cleanup complete! Original: {len(lines)} lines, Cleaned: {len(new_lines)} lines")
    print("Saved as main_cleaned.py")

if __name__ == "__main__":
    cleanup_complex_functions()
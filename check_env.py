"""
Helper script to check and validate .env file format
Run this to diagnose .env file parsing issues
"""
import os
import sys

def check_env_file():
    """Check .env file for common formatting issues"""
    env_path = ".env"
    
    if not os.path.exists(env_path):
        print(f"❌ .env file not found at: {env_path}")
        print("\nCreate a .env file with the following format:")
        print("MONGODB_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/dbname?retryWrites=true&w=majority")
        return False
    
    print(f"✅ Found .env file at: {env_path}")
    print("\nChecking file format...")
    print("=" * 60)
    
    issues = []
    with open(env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    for line_num, line in enumerate(lines, 1):
        line = line.rstrip('\n\r')
        
        # Skip empty lines and comments
        if not line.strip() or line.strip().startswith('#'):
            continue
        
        # Check for common issues
        if '=' not in line:
            issues.append(f"Line {line_num}: No '=' found (should be KEY=VALUE)")
            continue
        
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        
        # Check for spaces around =
        if ' =' in line or '= ' in line:
            issues.append(f"Line {line_num}: Spaces around '=' (should be KEY=VALUE, not KEY = VALUE)")
        
        # Check for unquoted values with spaces
        if value and ' ' in value and not (value.startswith('"') and value.endswith('"')):
            if 'MONGODB_URI' not in key:  # MongoDB URI can have spaces in query params
                issues.append(f"Line {line_num}: Value contains spaces but isn't quoted")
        
        # Check for special characters that might need quoting
        if value and any(char in value for char in ['#', ';', '$']) and not value.startswith('"'):
            if not value.startswith('mongodb'):  # MongoDB URI is an exception
                issues.append(f"Line {line_num}: Value contains special characters (#, ;, $) - consider quoting")
    
    if issues:
        print("\n⚠️  Potential issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\n💡 Tips:")
        print("  - Use KEY=VALUE format (no spaces around =)")
        print("  - Quote values with spaces: KEY=\"value with spaces\"")
        print("  - MongoDB URIs don't need quotes unless they contain spaces")
        print("  - Comments should start with #")
        return False
    else:
        print("\n✅ .env file format looks good!")
        return True

def show_env_example():
    """Show example .env file format"""
    print("\n" + "=" * 60)
    print("Example .env file format:")
    print("=" * 60)
    print("""
# MongoDB Atlas Configuration
MONGODB_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/cover_letters?retryWrites=true&w=majority
MONGODB_DB_NAME=cover_letters
MONGODB_COLLECTION_NAME=letters

# Other API Keys (examples)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
""")

if __name__ == "__main__":
    print("=" * 60)
    print("Environment File (.env) Checker")
    print("=" * 60)
    
    if check_env_file():
        print("\n✅ Your .env file is properly formatted!")
    else:
        show_env_example()
    
    print("\n" + "=" * 60)
    print("Common .env File Issues:")
    print("=" * 60)
    print("""
1. ❌ Spaces around equals sign:
   MONGODB_URI = value  (WRONG)
   ✅ MONGODB_URI=value  (CORRECT)

2. ❌ Unquoted values with special characters:
   KEY=value with spaces  (WRONG)
   ✅ KEY="value with spaces"  (CORRECT)

3. ❌ Comments without #:
   This is a comment  (WRONG)
   ✅ # This is a comment  (CORRECT)

4. ✅ MongoDB URIs (usually don't need quotes):
   MONGODB_URI=mongodb+srv://user:pass@cluster.net/db?options
   
5. ⚠️  If password has special characters, URL-encode them:
   Password: p@ss#word
   In URI: p%40ss%23word
   """)


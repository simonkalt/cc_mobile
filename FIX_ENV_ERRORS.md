# Fixing .env File Parsing Errors

## Error: "Python-dotenv could not parse statement starting at line X"

This error usually occurs when there are formatting issues in your `.env` file.

## Common Causes and Fixes

### 1. **Spaces Around Equals Sign**

```bash
# ❌ WRONG
MONGODB_URI = mongodb+srv://...

# ✅ CORRECT
MONGODB_URI=mongodb+srv://...
```

### 2. **Unquoted Values with Special Characters**

```bash
# ❌ WRONG (if value has spaces or special chars)
SOME_KEY=value with spaces

# ✅ CORRECT
SOME_KEY="value with spaces"
```

### 3. **Comments Without # Symbol**

```bash
# ❌ WRONG
This is a comment

# ✅ CORRECT
# This is a comment
```

### 4. **Multi-line Values (Not Properly Formatted)**

```bash
# ❌ WRONG
LONG_VALUE=line1
line2
line3

# ✅ CORRECT (use quotes for multi-line)
LONG_VALUE="line1
line2
line3"
```

### 5. **Invisible Characters or Encoding Issues**

- Make sure your `.env` file uses UTF-8 encoding
- Remove any invisible characters
- Avoid copying from Word/rich text editors

### 6. **Trailing Spaces or Tabs**

```bash
# ❌ WRONG (has trailing space)
MONGODB_URI=mongodb+srv://...

# ✅ CORRECT
MONGODB_URI=mongodb+srv://...
```

## Quick Fix Steps

1. **Check the specific lines mentioned in the error:**

   ```bash
   # View lines 17-18
   sed -n '17,18p' .env
   ```

2. **Common fixes for MongoDB connection strings:**

   - Make sure there are NO spaces around the `=` sign
   - Don't quote the entire MongoDB URI (unless it has spaces)
   - URL-encode special characters in passwords: `@` → `%40`, `#` → `%23`, etc.

3. **Example of correct MongoDB URI format:**

   ```env
   MONGODB_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/cover_letters?retryWrites=true&w=majority
   ```

4. **If password has special characters, URL-encode them:**
   ```env
   # Password: p@ss#word
   # In connection string: p%40ss%23word
   MONGODB_URI=mongodb+srv://user:p%40ss%23word@cluster0.xxxxx.mongodb.net/db
   ```

## Diagnostic Tools

Run the checker script:

```bash
python check_env.py
```

This will identify common formatting issues in your `.env` file.

## Manual Check

1. Open your `.env` file in a text editor
2. Go to lines 17-18 (the ones mentioned in the error)
3. Check for:
   - Spaces around `=`
   - Missing quotes for values with spaces
   - Comments without `#`
   - Trailing spaces
   - Special characters that need encoding

## Still Having Issues?

If the error persists:

1. **Create a minimal .env file:**

   ```env
   MONGODB_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/cover_letters?retryWrites=true&w=majority
   MONGODB_DB_NAME=cover_letters
   MONGODB_COLLECTION_NAME=letters
   ```

2. **Test with just these three variables**

3. **Add other variables one at a time** to identify which one causes the issue

4. **Check for hidden characters:**
   - Use a hex editor or `cat -A .env` to see invisible characters
   - Re-type the problematic lines manually

## Example .env File Format

```env
# MongoDB Atlas Configuration
MONGODB_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/cover_letters?retryWrites=true&w=majority
MONGODB_DB_NAME=cover_letters
MONGODB_COLLECTION_NAME=letters

# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Other configuration
SOME_CONFIG=value
ANOTHER_CONFIG="value with spaces"
```

## Notes

- `.env` files are case-sensitive
- No spaces around `=` sign
- Values with spaces should be quoted
- Comments start with `#`
- Empty lines are allowed
- MongoDB URIs typically don't need quotes

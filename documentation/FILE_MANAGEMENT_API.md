# File Management API Documentation

API endpoints for managing files (rename and delete) in S3 bucket. Files are organized by user_id folders: `{user_id}/{filename}`

## Base URL

```
http://localhost:8000  (local)
https://your-domain.com  (production)
```

## Endpoints

### 1. Rename File

**PUT** `/api/files/rename`

Rename a file in the user's S3 folder.

**Request Body:**

```json
{
  "oldKey": "user_id/resume.pdf",
  "newFileName": "my_resume_2024.pdf",
  "user_id": "507f1f77bcf86cd799439011",
  "user_email": "user@example.com"
}
```

**Request Fields:**

- `oldKey` (required): Current S3 key in format `{user_id}/{filename}`
- `newFileName` (required): New filename (just the filename, not the full path)
- `user_id` (optional): User ID - required if `user_email` is not provided
- `user_email` (optional): User email - will be resolved to `user_id` if provided

**Response (200 OK):**

```json
{
  "success": true,
  "key": "user_id/my_resume_2024.pdf",
  "oldKey": "user_id/resume.pdf",
  "fileName": "my_resume_2024.pdf",
  "message": "File renamed successfully",
  "files": [
    {
      "key": "user_id/my_resume_2024.pdf",
      "name": "my_resume_2024.pdf",
      "size": 123456,
      "lastModified": "2024-01-15T10:30:00Z"
    },
    {
      "key": "user_id/another_file.pdf",
      "name": "another_file.pdf",
      "size": 234567,
      "lastModified": "2024-01-14T09:20:00Z"
    }
  ]
}
```

**Response Fields:**

- `success`: Boolean indicating success
- `key`: New S3 key after rename
- `oldKey`: Original S3 key
- `fileName`: New filename (sanitized)
- `message`: Success message
- `files`: Updated list of all files for the user (sorted by lastModified, newest first)

**Error Responses:**

- `400 Bad Request`: Invalid filename or missing required fields
- `403 Forbidden`: Cannot rename files that don't belong to this user
- `409 Conflict`: A file with the new name already exists
- `404 Not Found`: User not found (when using user_email)
- `500 Internal Server Error`: S3 error or other server error

**Notes:**

- Filename is sanitized to remove unsafe characters
- If new filename is the same as old filename, operation succeeds with no changes
- Cannot rename files that don't belong to the user
- Returns updated file list automatically

---

### 2. Delete File

**DELETE** `/api/files/delete`

Delete a file from the user's S3 folder.

**Request Body:**

```json
{
  "key": "user_id/resume.pdf",
  "user_id": "507f1f77bcf86cd799439011",
  "user_email": "user@example.com"
}
```

**Request Fields:**

- `key` (required): S3 key in format `{user_id}/{filename}` of the file to delete
- `user_id` (optional): User ID - required if `user_email` is not provided
- `user_email` (optional): User email - will be resolved to `user_id` if provided

**Response (200 OK):**

```json
{
  "success": true,
  "key": "user_id/resume.pdf",
  "message": "File deleted successfully",
  "files": [
    {
      "key": "user_id/another_file.pdf",
      "name": "another_file.pdf",
      "size": 234567,
      "lastModified": "2024-01-14T09:20:00Z"
    }
  ]
}
```

**Response Fields:**

- `success`: Boolean indicating success
- `key`: S3 key of the deleted file
- `message`: Success message
- `files`: Updated list of all files for the user (sorted by lastModified, newest first)

**Error Responses:**

- `400 Bad Request`: Missing required fields or attempting to delete system files
- `403 Forbidden`: Cannot delete files that don't belong to this user
- `404 Not Found`: User not found (when using user_email)
- `500 Internal Server Error`: S3 error or other server error

**Notes:**

- Cannot delete system files (e.g., `.folder_initialized`)
- Cannot delete files that don't belong to the user
- Returns updated file list automatically after deletion

---

## React/JavaScript Implementation Examples

### Rename File

```javascript
const renameFile = async (oldKey, newFileName, userId) => {
  try {
    const response = await fetch("http://localhost:8000/api/files/rename", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        oldKey: oldKey,
        newFileName: newFileName,
        user_id: userId,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Rename failed");
    }

    const result = await response.json();

    // Update your file list with the returned files
    if (result.files) {
      setFiles(result.files);
    }

    return result;
  } catch (error) {
    console.error("Rename error:", error);
    throw error;
  }
};
```

### Delete File

```javascript
const deleteFile = async (fileKey, userId) => {
  try {
    const response = await fetch("http://localhost:8000/api/files/delete", {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        key: fileKey,
        user_id: userId,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Delete failed");
    }

    const result = await response.json();

    // Update your file list with the returned files
    if (result.files) {
      setFiles(result.files);
    }

    return result;
  } catch (error) {
    console.error("Delete error:", error);
    throw error;
  }
};
```

### Long Press Handler Example (React Native)

```javascript
import { LongPressGestureHandler } from "react-native-gesture-handler";

const FileItem = ({ file, userId, onRename, onDelete }) => {
  const [showOptions, setShowOptions] = useState(false);

  const handleLongPress = () => {
    setShowOptions(true);
  };

  const handleRename = async () => {
    const newName = await prompt("Enter new filename:", file.name);
    if (newName && newName !== file.name) {
      try {
        await renameFile(file.key, newName, userId);
        setShowOptions(false);
      } catch (error) {
        alert("Failed to rename file: " + error.message);
      }
    }
  };

  const handleDelete = async () => {
    const confirmed = await confirm(
      "Are you sure you want to delete this file?"
    );
    if (confirmed) {
      try {
        await deleteFile(file.key, userId);
        setShowOptions(false);
      } catch (error) {
        alert("Failed to delete file: " + error.message);
      }
    }
  };

  return (
    <LongPressGestureHandler onActivated={handleLongPress}>
      <View>
        <Text>{file.name}</Text>
        {showOptions && (
          <View>
            <Button title="Rename" onPress={handleRename} />
            <Button title="Delete" onPress={handleDelete} />
            <Button title="Cancel" onPress={() => setShowOptions(false)} />
          </View>
        )}
      </View>
    </LongPressGestureHandler>
  );
};
```

### Web Long Press Handler Example

```javascript
const FileItem = ({ file, userId, onRename, onDelete }) => {
  const [showOptions, setShowOptions] = useState(false);
  const longPressTimer = useRef(null);

  const handleMouseDown = () => {
    longPressTimer.current = setTimeout(() => {
      setShowOptions(true);
    }, 500); // 500ms for long press
  };

  const handleMouseUp = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
    }
  };

  const handleTouchStart = () => {
    longPressTimer.current = setTimeout(() => {
      setShowOptions(true);
    }, 500); // 500ms for long press
  };

  const handleTouchEnd = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
    }
  };

  const handleRename = async () => {
    const newName = prompt("Enter new filename:", file.name);
    if (newName && newName !== file.name) {
      try {
        await renameFile(file.key, newName, userId);
        setShowOptions(false);
      } catch (error) {
        alert("Failed to rename file: " + error.message);
      }
    }
  };

  const handleDelete = async () => {
    const confirmed = confirm("Are you sure you want to delete this file?");
    if (confirmed) {
      try {
        await deleteFile(file.key, userId);
        setShowOptions(false);
      } catch (error) {
        alert("Failed to delete file: " + error.message);
      }
    }
  };

  return (
    <div
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      <div>{file.name}</div>
      {showOptions && (
        <div>
          <button onClick={handleRename}>Rename</button>
          <button onClick={handleDelete}>Delete</button>
          <button onClick={() => setShowOptions(false)}>Cancel</button>
        </div>
      )}
    </div>
  );
};
```

## Important Notes

1. **File Keys**: The `key` field in file objects is the full S3 key: `{user_id}/{filename}`. Use this for rename and delete operations.

2. **Filename Sanitization**: The server automatically sanitizes filenames to remove unsafe characters. Only alphanumeric characters, dots, dashes, underscores, and spaces are allowed.

3. **Automatic File List Update**: Both rename and delete operations return the updated file list, so you don't need to make a separate API call to refresh the list.

4. **User Validation**: The server validates that files belong to the user before allowing rename or delete operations.

5. **System Files**: System files (like `.folder_initialized`) cannot be deleted.

6. **Error Handling**: Always handle errors appropriately and provide user feedback.

7. **CORS**: Make sure your frontend URL is included in the `CORS_ORIGINS` environment variable on the backend.

## Related Endpoints

- **List Files**: `GET /api/files/list` - Get list of files for a user
- **Upload File**: `POST /api/files/upload` - Upload a new file

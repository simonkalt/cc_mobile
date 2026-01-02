# Server API Requirements for S3 File Operations

The client has been updated to use server-side S3 operations instead of direct client access. The server needs to implement the following endpoints:

## Required Endpoints

### 1. List Files
**Endpoint:** `GET /api/files/list`

**Description:** Returns a list of files from S3 bucket for the authenticated user.

**Request:**
- Method: `GET`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer {token}` (optional, if using token auth)

**Response:**
```json
{
  "files": [
    {
      "key": "PDF Resumes/1234567890_resume.pdf",
      "name": "1234567890_resume.pdf",
      "size": 123456,
      "lastModified": "2024-01-15T10:30:00Z"
    },
    ...
  ]
}
```

**Empty Response (No Files):**
When there are no files, the endpoint returns:
```json
{
  "files": []
}
```

**Notes:**
- Filter files by user if needed (use user_id or user_email from auth token)
- Sort by lastModified (newest first) is optional - client will sort if needed
- Only return actual files (not folders/directories)
- **IMPORTANT**: The `files` array will always be present, even if empty. The frontend should **always** display the file selection UI (including the "Add File" button) regardless of whether `files.length === 0`. The UI should never be hidden when there are zero files, as users need access to the add button to upload their first file.

---

### 2. Upload File
**Endpoint:** `POST /api/files/upload`

**Description:** Uploads a file to S3 bucket on behalf of the user.

**Request:**
- Method: `POST`
- Headers:
  - `Content-Type: application/json`
  - `Authorization: Bearer {token}` (optional, if using token auth)
- Body:
```json
{
  "fileName": "resume.pdf",
  "fileData": "base64_encoded_file_data",
  "contentType": "application/pdf",
  "user_id": "user_id_from_auth",
  "user_email": "user@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "key": "PDF Resumes/1234567890_resume.pdf",
  "fileKey": "PDF Resumes/1234567890_resume.pdf",
  "message": "File uploaded successfully"
}
```

**Notes:**
- Decode base64 fileData before uploading to S3
- Generate unique filename (timestamp + original filename)
- Use prefix: `PDF Resumes/`
- Store file metadata associated with user if needed
- Return the S3 key that can be used to reference the file

---

### 3. Get File (for Chat/Processing)
**Endpoint:** Already handled in `/chat` endpoint

**Description:** The existing `/chat` endpoint should handle fetching files from S3 when a file key is provided in the `resume` field.

**Current Behavior:**
- Client sends `resume` field with either:
  - S3 key (string) for existing files: `"PDF Resumes/1234567890_resume.pdf"`
  - Base64 data (string) for newly uploaded files: `"JVBERi0xLjQKJeLjz9MKMy..."`

**Server Should:**
- If `resume` is an S3 key (starts with "PDF Resumes/" or contains "/"), fetch from S3
- If `resume` is base64 data, use it directly
- Process the file content for the chat/cover letter generation

---

## Implementation Notes

### S3 Configuration
The server should have:
- AWS credentials configured (environment variables or IAM role)
- S3 bucket: `custom-cover-user-resumes`
- S3 prefix: `PDF Resumes/`
- Proper IAM permissions for:
  - `s3:ListObjectsV2` (for listing files)
  - `s3:PutObject` (for uploading)
  - `s3:GetObject` (for retrieving)

### User Association
- Files should be associated with users (user_id or user_email)
- Filter files by user when listing
- Only allow users to access their own files

### Error Handling
- Return appropriate HTTP status codes (200, 400, 401, 403, 500)
- Include error messages in response:
```json
{
  "detail": "Error message here"
}
```

### Security
- Validate user authentication
- Validate file types (only PDFs?)
- Validate file sizes (max size limit?)
- Sanitize filenames
- Use proper S3 bucket policies

---

## Example Server Implementation (Python/FastAPI)

```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import boto3
from botocore.exceptions import ClientError
import base64
from datetime import datetime

router = APIRouter()

# S3 Configuration
S3_BUCKET = "custom-cover-user-resumes"
S3_PREFIX = "PDF Resumes/"
s3_client = boto3.client('s3')

class FileUploadRequest(BaseModel):
    fileName: str
    fileData: str  # base64 encoded
    contentType: str = "application/pdf"
    user_id: str = None
    user_email: str = None

@router.get("/api/files/list")
async def list_files(user: dict = Depends(get_current_user)):
    """List files for the authenticated user"""
    try:
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix=S3_PREFIX
        )
        
        files = []
        for obj in response.get('Contents', []):
            # Filter by user if needed
            # Only return actual files (not folders)
            if not obj['Key'].endswith('/'):
                files.append({
                    "key": obj['Key'],
                    "name": obj['Key'].replace(S3_PREFIX, ""),
                    "size": obj['Size'],
                    "lastModified": obj['LastModified'].isoformat()
                })
        
        return {"files": files}
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"S3 error: {str(e)}")

@router.post("/api/files/upload")
async def upload_file(request: FileUploadRequest, user: dict = Depends(get_current_user)):
    """Upload a file to S3"""
    try:
        # Decode base64
        file_bytes = base64.b64decode(request.fileData)
        
        # Generate unique filename
        timestamp = int(datetime.now().timestamp() * 1000)
        s3_key = f"{S3_PREFIX}{timestamp}_{request.fileName}"
        
        # Upload to S3
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=file_bytes,
            ContentType=request.contentType
        )
        
        return {
            "success": True,
            "key": s3_key,
            "fileKey": s3_key,
            "message": "File uploaded successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
```

---

## Testing

After implementing these endpoints, test with:

1. **List Files:**
   ```bash
   curl -X GET "https://your-backend.com/api/files/list" \
     -H "Authorization: Bearer {token}"
   ```

2. **Upload File:**
   ```bash
   curl -X POST "https://your-backend.com/api/files/upload" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer {token}" \
     -d '{
       "fileName": "test.pdf",
       "fileData": "base64_encoded_data_here",
       "contentType": "application/pdf"
     }'
   ```

---

## Migration Checklist

- [ ] Implement `GET /api/files/list` endpoint
- [ ] Implement `POST /api/files/upload` endpoint
- [ ] Update `/chat` endpoint to handle S3 file keys
- [ ] Configure AWS credentials on server
- [ ] Set up S3 bucket permissions
- [ ] Test file listing
- [ ] Test file upload
- [ ] Test file retrieval in chat endpoint
- [ ] Add user-based file filtering/security
- [ ] Add file validation (type, size)
- [ ] Add error handling and logging


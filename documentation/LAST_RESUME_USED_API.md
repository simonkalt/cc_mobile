# Last Resume Used API Documentation

This document describes how to use the `lastResumeUsed` field in user settings to track and retrieve the default resume for a user upon login.

## Overview

The `lastResumeUsed` field is stored in the user's preferences under `preferences.appSettings.lastResumeUsed`. This field stores the S3 key (path) of the resume file that should be used by default when the user logs in.

## Schema Structure

The field is located at:
```
preferences.appSettings.lastResumeUsed
```

**Full Schema Path:**
```json
{
  "preferences": {
    "appSettings": {
      "printProperties": { ... },
      "personalityProfiles": [ ... ],
      "selectedModel": "gemini-2.5-flash",
      "lastResumeUsed": "507f1f77bcf86cd799439011/resume_2024.pdf"
    }
  }
}
```

## Field Details

- **Type**: `string` (optional)
- **Default**: `null`
- **Format**: S3 key path in format `{user_id}/{filename}`
- **Example**: `"507f1f77bcf86cd799439011/my_resume.pdf"`

## API Endpoints

### 1. Get User Settings (Retrieve lastResumeUsed)

**GET** `/api/users/{user_id}`

Retrieves the user's settings including `lastResumeUsed`.

**Request:**
```bash
GET /api/users/507f1f77bcf86cd799439011
```

**Response:**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "John Doe",
  "email": "john@example.com",
  "preferences": {
    "appSettings": {
      "printProperties": { ... },
      "personalityProfiles": [ ... ],
      "selectedModel": "gemini-2.5-flash",
      "lastResumeUsed": "507f1f77bcf86cd799439011/my_resume.pdf"
    }
  }
}
```

### 2. Update lastResumeUsed

**PUT** `/api/users/{user_id}`

Updates the `lastResumeUsed` field in the user's app settings.

**Request:**
```bash
PUT /api/users/507f1f77bcf86cd799439011
Content-Type: application/json
```

**Request Body:**
```json
{
  "preferences": {
    "appSettings": {
      "lastResumeUsed": "507f1f77bcf86cd799439011/my_resume.pdf"
    }
  }
}
```

**Response (200 OK):**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "John Doe",
  "email": "john@example.com",
  "preferences": {
    "appSettings": {
      "lastResumeUsed": "507f1f77bcf86cd799439011/my_resume.pdf"
    }
  }
}
```

## Client-Side Usage Examples

### React/JavaScript - Setting lastResumeUsed

```javascript
// Function to set the last resume used
async function setLastResumeUsed(userId, resumeKey) {
  const API_BASE_URL = 'http://localhost:8000';
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/users/${userId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        preferences: {
          appSettings: {
            lastResumeUsed: resumeKey  // e.g., "507f1f77bcf86cd799439011/my_resume.pdf"
          }
        }
      })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const updatedUser = await response.json();
    console.log('Last resume used updated:', updatedUser.preferences.appSettings.lastResumeUsed);
    return updatedUser;
  } catch (error) {
    console.error('Error setting last resume used:', error);
    throw error;
  }
}

// Usage: Set last resume when user selects/uploads a resume
const handleResumeSelect = async (userId, resumeKey) => {
  await setLastResumeUsed(userId, resumeKey);
  console.log(`Resume ${resumeKey} set as default for user ${userId}`);
};
```

### React/JavaScript - Retrieving lastResumeUsed on Login

```javascript
// Function to get user settings and retrieve lastResumeUsed
async function getUserSettings(userId) {
  const API_BASE_URL = 'http://localhost:8000';
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/users/${userId}`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const user = await response.json();
    const lastResumeUsed = user.preferences?.appSettings?.lastResumeUsed;
    
    if (lastResumeUsed) {
      console.log('Default resume found:', lastResumeUsed);
      // Use this resume key to load the resume file
      return lastResumeUsed;
    } else {
      console.log('No default resume set');
      return null;
    }
  } catch (error) {
    console.error('Error retrieving user settings:', error);
    throw error;
  }
}

// Usage: On user login, retrieve and use the last resume
const handleUserLogin = async (userId) => {
  const defaultResumeKey = await getUserSettings(userId);
  
  if (defaultResumeKey) {
    // Load the resume using the S3 key
    // You can use the /api/files/list endpoint to get file details
    // or directly use the key to download the file
    loadResumeFromS3(defaultResumeKey);
  }
};
```

### React/JavaScript - Complete Example: Login Flow

```javascript
// Complete example: Login and load default resume
async function loginAndLoadDefaultResume(userId) {
  const API_BASE_URL = 'http://localhost:8000';
  
  try {
    // 1. Get user settings
    const userResponse = await fetch(`${API_BASE_URL}/api/users/${userId}`);
    const user = await userResponse.json();
    
    // 2. Check for lastResumeUsed
    const lastResumeUsed = user.preferences?.appSettings?.lastResumeUsed;
    
    if (lastResumeUsed) {
      // 3. Extract filename from S3 key
      const filename = lastResumeUsed.split('/').pop();
      
      // 4. Get file list to verify the resume exists
      const filesResponse = await fetch(
        `${API_BASE_URL}/api/files/list?user_id=${userId}`
      );
      const filesData = await filesResponse.json();
      
      // 5. Find the resume in the file list
      const resumeFile = filesData.files.find(
        file => file.key === lastResumeUsed || file.name === filename
      );
      
      if (resumeFile) {
        console.log('Loading default resume:', resumeFile.name);
        // Load the resume into your form/application
        setSelectedResume(resumeFile);
      } else {
        console.warn('Default resume not found in file list');
      }
    } else {
      console.log('No default resume set for user');
    }
  } catch (error) {
    console.error('Error loading default resume:', error);
  }
}
```

### React/JavaScript - Update lastResumeUsed After Upload

```javascript
// Update lastResumeUsed after successfully uploading a resume
async function handleResumeUpload(userId, uploadedFile) {
  const API_BASE_URL = 'http://localhost:8000';
  
  try {
    // 1. Upload the file (using your existing upload endpoint)
    const uploadResponse = await fetch(`${API_BASE_URL}/api/files/upload`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        fileName: uploadedFile.name,
        fileData: uploadedFile.base64Data,
        contentType: 'application/pdf',
        user_id: userId
      })
    });
    
    const uploadResult = await uploadResponse.json();
    
    // 2. Get the S3 key from the upload response
    // The key format is: {user_id}/{filename}
    const resumeKey = `${userId}/${uploadedFile.name}`;
    
    // 3. Set this as the lastResumeUsed
    await setLastResumeUsed(userId, resumeKey);
    
    console.log('Resume uploaded and set as default:', resumeKey);
    return uploadResult;
  } catch (error) {
    console.error('Error uploading resume:', error);
    throw error;
  }
}
```

## cURL Examples

### Get lastResumeUsed

```bash
curl -X GET "http://localhost:8000/api/users/507f1f77bcf86cd799439011" \
  -H "Content-Type: application/json"
```

### Set lastResumeUsed

```bash
curl -X PUT "http://localhost:8000/api/users/507f1f77bcf86cd799439011" \
  -H "Content-Type: application/json" \
  -d '{
    "preferences": {
      "appSettings": {
        "lastResumeUsed": "507f1f77bcf86cd799439011/my_resume.pdf"
      }
    }
  }'
```

## Notes

1. **S3 Key Format**: The `lastResumeUsed` field should contain the full S3 key path, which is typically in the format `{user_id}/{filename}`.

2. **File Validation**: Before using `lastResumeUsed`, verify that the file still exists in the user's S3 folder using the `/api/files/list` endpoint.

3. **Default Behavior**: If `lastResumeUsed` is `null` or the file doesn't exist, the application should handle this gracefully (e.g., show an empty resume field or prompt the user to select a resume).

4. **Updating on Selection**: Consider updating `lastResumeUsed` whenever the user:
   - Uploads a new resume
   - Selects a resume from the file list
   - Uses a resume to generate a cover letter

5. **Migration**: For existing users, `lastResumeUsed` will be `null` until they select or upload a resume.

## Error Handling

```javascript
async function getLastResumeUsed(userId) {
  try {
    const user = await getUserSettings(userId);
    const lastResumeUsed = user.preferences?.appSettings?.lastResumeUsed;
    
    if (!lastResumeUsed) {
      return null; // No default resume set
    }
    
    // Verify the file exists
    const filesResponse = await fetch(
      `${API_BASE_URL}/api/files/list?user_id=${userId}`
    );
    const filesData = await filesResponse.json();
    
    const resumeExists = filesData.files.some(
      file => file.key === lastResumeUsed
    );
    
    if (!resumeExists) {
      console.warn('Default resume not found, clearing lastResumeUsed');
      // Optionally clear the invalid reference
      await setLastResumeUsed(userId, null);
      return null;
    }
    
    return lastResumeUsed;
  } catch (error) {
    console.error('Error getting last resume used:', error);
    return null;
  }
}
```


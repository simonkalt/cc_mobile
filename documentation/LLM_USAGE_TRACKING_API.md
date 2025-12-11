# LLM Usage Tracking API Documentation

This document describes the API functionality for tracking LLM (Large Language Model) usage counts and the last LLM used by each user.

## Overview

The system automatically tracks:
- **LLM Usage Counts**: How many times each LLM has been used by a user
- **Last LLM Used**: The most recently used LLM for each user

These fields are automatically updated whenever an LLM is successfully called through the API.

## Schema Structure

The LLM tracking fields are stored at the root level of the user document:

```json
{
  "_id": "ObjectId",
  "name": "John Doe",
  "email": "john@example.com",
  "llm_counts": {
    "gpt-4.1": 15,
    "claude-sonnet-4-20250514": 8,
    "gemini-2.5-flash": 3,
    "grok-4-fast-reasoning": 2
  },
  "last_llm_used": "gpt-4.1",
  "preferences": { ... }
}
```

## Field Descriptions

### `llm_counts` (object)
- **Type**: `object` (dictionary/map)
- **Description**: Tracks usage count for each LLM model
- **Structure**: Key-value pairs where:
  - **Key**: Normalized LLM name (e.g., `"gpt-4.1"`, `"claude-sonnet-4-20250514"`)
  - **Value**: Integer count of how many times that LLM has been used
- **Initialization**: Empty object `{}` for new users
- **Auto-increment**: Automatically incremented when an LLM is successfully called

### `last_llm_used` (string)
- **Type**: `string` or `null`
- **Description**: The name of the most recently used LLM
- **Format**: Normalized LLM name (e.g., `"gpt-4.1"`, `"claude-sonnet-4-20250514"`)
- **Initialization**: `null` for new users
- **Auto-update**: Automatically updated to the current LLM whenever an LLM is successfully called

## Automatic Tracking

The system automatically tracks LLM usage in the following scenarios:

### 1. Job Info Generation (`POST /api/job-info`)
When a cover letter is generated using the job info endpoint, the LLM usage is automatically tracked if `user_id` or `user_email` is provided.

**Example Request:**
```json
{
  "llm": "gpt-4.1",
  "company_name": "Acme Corp",
  "resume": "...",
  "jd": "...",
  "user_id": "693326c07fcdaab8e81cdd2f"
}
```

**Automatic Updates:**
- `llm_counts.gpt-4.1` is incremented by 1
- `last_llm_used` is set to `"gpt-4.1"`

### 2. Chat Requests (`POST /chat`)
When a chat request is made, the LLM usage is automatically tracked if `user_id` or `user_email` is provided in the request body.

**Example Request:**
```json
{
  "prompt": "Hello, how are you?",
  "active_model": "claude-sonnet-4-20250514",
  "user_id": "693326c07fcdaab8e81cdd2f"
}
```

**Automatic Updates:**
- `llm_counts.claude-sonnet-4-20250514` is incremented by 1
- `last_llm_used` is set to `"claude-sonnet-4-20250514"`

## API Endpoints

### 1. Get User (Retrieve LLM Usage Data)

**GET** `/api/users/{user_id}`

Retrieves user data including LLM usage counts and last LLM used.

**Request:**
```bash
GET /api/users/693326c07fcdaab8e81cdd2f
```

**Response (200 OK):**
```json
{
  "id": "693326c07fcdaab8e81cdd2f",
  "name": "John Doe",
  "email": "john@example.com",
  "llm_counts": {
    "gpt-4.1": 15,
    "claude-sonnet-4-20250514": 8,
    "gemini-2.5-flash": 3
  },
  "last_llm_used": "gpt-4.1",
  "preferences": { ... },
  "dateCreated": "2024-04-27T00:00:00.000Z",
  "dateUpdated": "2024-12-07T22:08:36.138Z"
}
```

**Response for New User (No LLM Usage Yet):**
```json
{
  "id": "693326c07fcdaab8e81cdd2f",
  "name": "John Doe",
  "email": "john@example.com",
  "llm_counts": {},
  "last_llm_used": null,
  "preferences": { ... }
}
```

### 2. Update Last LLM Used (Manual Update)

**PUT** `/api/users/{user_id}`

Manually update the `last_llm_used` field. Note: This does not increment usage counts. Use this only if you need to manually set the last LLM used without making an actual LLM call.

**Request:**
```bash
PUT /api/users/693326c07fcdaab8e81cdd2f
Content-Type: application/json
```

**Request Body:**
```json
{
  "last_llm_used": "gemini-2.5-flash"
}
```

**Response (200 OK):**
```json
{
  "id": "693326c07fcdaab8e81cdd2f",
  "name": "John Doe",
  "email": "john@example.com",
  "llm_counts": {
    "gpt-4.1": 15,
    "claude-sonnet-4-20250514": 8
  },
  "last_llm_used": "gemini-2.5-flash",
  "preferences": { ... }
}
```

**Note**: The `llm_counts` field cannot be manually updated through the API. It is automatically managed by the system when LLMs are called.

## LLM Name Normalization

LLM names are normalized before being stored. The normalization function converts various input formats to a consistent format:

**Examples:**
- `"ChatGPT"` → `"gpt-4.1"`
- `"Claude"` → `"claude-sonnet-4-20250514"`
- `"Gemini"` → `"gemini-2.5-flash"`
- `"Grok"` → `"grok-4-fast-reasoning"`

This ensures consistent tracking regardless of how the LLM name is provided in the request.

## Client-Side Implementation Examples

### JavaScript/React Example: Get LLM Usage Stats

```javascript
const getLLMUsageStats = async (userId) => {
  try {
    const response = await fetch(`http://localhost:8000/api/users/${userId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const userData = await response.json();
    
    // Access LLM usage data
    const llmCounts = userData.llm_counts || {};
    const lastLLMUsed = userData.last_llm_used;
    
    // Display usage statistics
    console.log('LLM Usage Counts:', llmCounts);
    console.log('Last LLM Used:', lastLLMUsed);
    
    // Calculate total usage
    const totalUsage = Object.values(llmCounts).reduce((sum, count) => sum + count, 0);
    console.log('Total LLM Calls:', totalUsage);
    
    // Get most used LLM
    const mostUsedLLM = Object.entries(llmCounts).reduce((a, b) => 
      llmCounts[a[0]] > llmCounts[b[0]] ? a : b
    );
    console.log('Most Used LLM:', mostUsedLLM[0], 'with', mostUsedLLM[1], 'calls');
    
    return {
      llmCounts,
      lastLLMUsed,
      totalUsage,
      mostUsedLLM: mostUsedLLM[0]
    };
  } catch (error) {
    console.error('Error fetching LLM usage stats:', error);
    throw error;
  }
};
```

### React Native Example: Display Usage Statistics

```javascript
import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';

const LLMUsageStats = ({ userId }) => {
  const [stats, setStats] = useState({
    llmCounts: {},
    lastLLMUsed: null,
    totalUsage: 0
  });

  useEffect(() => {
    fetchLLMStats();
  }, [userId]);

  const fetchLLMStats = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/users/${userId}`);
      const userData = await response.json();
      
      const llmCounts = userData.llm_counts || {};
      const totalUsage = Object.values(llmCounts).reduce((sum, count) => sum + count, 0);
      
      setStats({
        llmCounts,
        lastLLMUsed: userData.last_llm_used,
        totalUsage
      });
    } catch (error) {
      console.error('Error fetching LLM stats:', error);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>LLM Usage Statistics</Text>
      
      <Text style={styles.label}>Total Calls: {stats.totalUsage}</Text>
      <Text style={styles.label}>Last Used: {stats.lastLLMUsed || 'None'}</Text>
      
      <Text style={styles.subtitle}>Usage by Model:</Text>
      {Object.entries(stats.llmCounts).map(([llm, count]) => (
        <View key={llm} style={styles.statRow}>
          <Text style={styles.llmName}>{llm}:</Text>
          <Text style={styles.count}>{count} calls</Text>
        </View>
      ))}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    padding: 16,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 12,
  },
  label: {
    fontSize: 16,
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 18,
    fontWeight: '600',
    marginTop: 16,
    marginBottom: 8,
  },
  statRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 4,
  },
  llmName: {
    fontSize: 14,
  },
  count: {
    fontSize: 14,
    fontWeight: '600',
  },
});

export default LLMUsageStats;
```

### Example: Track Usage After LLM Call

```javascript
const generateCoverLetter = async (jobData, userId) => {
  try {
    // Make LLM call - usage is automatically tracked
    const response = await fetch('http://localhost:8000/api/job-info', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ...jobData,
        llm: 'gpt-4.1',
        user_id: userId  // Required for tracking
      }),
    });

    const result = await response.json();
    
    // Fetch updated usage stats
    const userResponse = await fetch(`http://localhost:8000/api/users/${userId}`);
    const userData = await userResponse.json();
    
    console.log('LLM Usage Updated:');
    console.log('Last Used:', userData.last_llm_used);
    console.log('Count for gpt-4.1:', userData.llm_counts['gpt-4.1']);
    
    return result;
  } catch (error) {
    console.error('Error generating cover letter:', error);
    throw error;
  }
};
```

## Error Handling

### User Not Found
If the user ID is invalid or the user doesn't exist:
- **Status Code**: `404 Not Found`
- **Response**: `{"detail": "User not found"}`

### Database Unavailable
If the database connection is unavailable:
- **Status Code**: `503 Service Unavailable`
- **Response**: `{"detail": "Database connection unavailable"}`

### Tracking Failures
If LLM usage tracking fails (e.g., database error), the LLM call will still succeed, but a warning will be logged. The tracking failure does not affect the LLM response.

## Best Practices

1. **Always Provide User ID**: Include `user_id` or `user_email` in LLM API requests to enable automatic tracking
2. **Don't Manually Update Counts**: Let the system automatically manage `llm_counts` - don't try to manually increment it
3. **Use Normalized Names**: When manually setting `last_llm_used`, use the normalized LLM name format
4. **Handle Null Values**: New users will have `llm_counts: {}` and `last_llm_used: null` - handle these cases in your UI
5. **Monitor Usage**: Regularly check `llm_counts` to understand user behavior and LLM preferences

## Related Endpoints

- **Get User**: `GET /api/users/{user_id}` - Returns LLM usage data
- **Update User**: `PUT /api/users/{user_id}` - Can update `last_llm_used` manually
- **Job Info**: `POST /api/job-info` - Automatically tracks LLM usage
- **Chat**: `POST /chat` - Automatically tracks LLM usage

## Notes

- LLM usage is only tracked when `user_id` or `user_email` is provided in the request
- Tracking happens automatically after a successful LLM call
- Failed LLM calls do not increment usage counts
- The `llm_counts` field is read-only through the API (can only be updated automatically)
- LLM names are normalized to ensure consistent tracking across different input formats


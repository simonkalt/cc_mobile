# Frontend Implementation Guide

Complete guide for implementing a frontend application that integrates with the Cover Letter API backend.

## Table of Contents

1. [Overview](#overview)
2. [Setup & Configuration](#setup--configuration)
3. [Authentication Flow](#authentication-flow)
4. [API Client Setup](#api-client-setup)
5. [Core Features Implementation](#core-features-implementation)
6. [State Management](#state-management)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)
9. [Complete React Examples](#complete-react-examples)

---

## Overview

This guide provides comprehensive instructions for building a frontend application that integrates with the Cover Letter API. The backend provides:

- **User Management**: Registration, login, profile management
- **Cover Letter Generation**: AI-powered cover letter creation
- **File Management**: Resume upload and management
- **Personality Profiles**: Custom writing styles
- **PDF Generation**: Export cover letters as PDFs
- **SMS/Email Verification**: Two-factor authentication
- **Subscription Management**: User subscriptions

### Base URLs

- **Development**: `http://localhost:8000`
- **Production**: `https://your-api-domain.com`

### CORS Configuration

The backend is configured to accept requests from:

- `http://localhost:3000`
- `http://localhost:3001`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:3001`
- Additional origins can be configured via `CORS_ORIGINS` environment variable

---

## Setup & Configuration

### 1. Environment Variables

Create a `.env` file in your frontend project root:

```env
REACT_APP_API_BASE_URL=http://localhost:8000
REACT_APP_ENV=development
```

For production:

```env
REACT_APP_API_BASE_URL=https://your-api-domain.com
REACT_APP_ENV=production
```

### 2. Install Dependencies

```bash
npm install axios
# or
yarn add axios
```

### 3. API Configuration

Create `src/config/api.js`:

```javascript
const API_BASE_URL =
  process.env.REACT_APP_API_BASE_URL || "http://localhost:8000";

export const API_ENDPOINTS = {
  // User endpoints
  REGISTER: `${API_BASE_URL}/api/users/register`,
  LOGIN: `${API_BASE_URL}/api/users/login`,
  GET_USER: (userId) => `${API_BASE_URL}/api/users/${userId}`,
  GET_USER_BY_EMAIL: (email) => `${API_BASE_URL}/api/users/email/${email}`,
  UPDATE_USER: (userId) => `${API_BASE_URL}/api/users/${userId}`,
  DELETE_USER: (userId) => `${API_BASE_URL}/api/users/${userId}`,

  // Cover letter endpoints
  GENERATE_COVER_LETTER: `${API_BASE_URL}/api/job-info`,
  GENERATE_WITH_TEXT_RESUME: `${API_BASE_URL}/api/cover-letter/generate-with-text-resume`,
  CHAT: `${API_BASE_URL}/api/chat`,

  // File management
  UPLOAD_FILE: `${API_BASE_URL}/api/files/upload`,
  GET_FILES: (userId) => `${API_BASE_URL}/api/files/user/${userId}`,
  DELETE_FILE: (fileId) => `${API_BASE_URL}/api/files/${fileId}`,

  // Cover letter management
  SAVE_COVER_LETTER: `${API_BASE_URL}/api/cover-letters`,
  GET_COVER_LETTERS: (userId) =>
    `${API_BASE_URL}/api/cover-letters/user/${userId}`,
  GET_COVER_LETTER: (letterId) =>
    `${API_BASE_URL}/api/cover-letters/${letterId}`,
  DELETE_COVER_LETTER: (letterId) =>
    `${API_BASE_URL}/api/cover-letters/${letterId}`,

  // PDF generation
  GENERATE_PDF: `${API_BASE_URL}/api/pdf/generate`,

  // Job URL analysis
  ANALYZE_JOB_URL: `${API_BASE_URL}/api/job-url/analyze`,

  // Personality profiles
  GET_PERSONALITY_PROFILES: `${API_BASE_URL}/api/personality/profiles`,
  GET_DEFAULT_PROFILE: `${API_BASE_URL}/api/personality/default`,

  // LLM configuration
  GET_LLMS: `${API_BASE_URL}/api/llm-config/llms`,

  // SMS verification
  SEND_SMS_CODE: `${API_BASE_URL}/api/sms/send-code`,
  VERIFY_SMS_CODE: `${API_BASE_URL}/api/sms/verify-code`,

  // Email verification
  SEND_EMAIL_CODE: `${API_BASE_URL}/api/email/send-code`,
  VERIFY_EMAIL_CODE: `${API_BASE_URL}/api/email/verify-code`,

  // Health check
  HEALTH: `${API_BASE_URL}/api/health`,
  ROOT: `${API_BASE_URL}/`,
};

export default API_BASE_URL;
```

---

## Authentication Flow

### 1. User Registration

```javascript
// src/services/authService.js
import axios from "axios";
import { API_ENDPOINTS } from "../config/api";

export const registerUser = async (userData) => {
  try {
    const response = await axios.post(API_ENDPOINTS.REGISTER, {
      name: userData.name,
      email: userData.email,
      password: userData.password,
      phone: userData.phone || null,
      address: userData.address || null,
      preferences: {
        theme: "light",
        newsletterOptIn: false,
        appSettings: {
          selectedModel: "gpt-4",
          printProperties: {
            fontFamily: "Georgia",
            fontSize: 11,
            lineHeight: 1.15,
            margins: {
              top: 1.0,
              right: 0.75,
              bottom: 0.25,
              left: 0.75,
            },
            pageSize: {
              width: 8.5,
              height: 11.0,
            },
          },
          personalityProfiles: [],
        },
      },
    });

    // Store user ID in localStorage
    localStorage.setItem("userId", response.data.id);
    localStorage.setItem("userEmail", response.data.email);

    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || "Registration failed");
    }
    throw new Error("Network error: Could not connect to server");
  }
};
```

### 2. User Login

```javascript
export const loginUser = async (email, password) => {
  try {
    const response = await axios.post(API_ENDPOINTS.LOGIN, {
      email,
      password,
    });

    if (response.data.success && response.data.user) {
      // Store user data
      localStorage.setItem("userId", response.data.user.id);
      localStorage.setItem("userEmail", response.data.user.email);
      localStorage.setItem("userName", response.data.user.name);

      return response.data.user;
    } else {
      throw new Error("Login failed");
    }
  } catch (error) {
    if (error.response) {
      const status = error.response.status;
      if (status === 401) {
        throw new Error("Invalid email or password");
      } else if (status === 403) {
        throw new Error("Account is inactive. Please contact support.");
      } else {
        throw new Error(error.response.data.detail || "Login failed");
      }
    }
    throw new Error("Network error: Could not connect to server");
  }
};
```

### 3. Logout

```javascript
export const logoutUser = () => {
  localStorage.removeItem("userId");
  localStorage.removeItem("userEmail");
  localStorage.removeItem("userName");
  // Redirect to login page
  window.location.href = "/login";
};
```

### 4. Check Authentication Status

```javascript
export const isAuthenticated = () => {
  return !!localStorage.getItem("userId");
};

export const getCurrentUserId = () => {
  return localStorage.getItem("userId");
};

export const getCurrentUserEmail = () => {
  return localStorage.getItem("userEmail");
};
```

---

## API Client Setup

### Create Axios Instance

```javascript
// src/services/apiClient.js
import axios from "axios";
import API_BASE_URL from "../config/api";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add any auth tokens here if needed
    const userId = localStorage.getItem("userId");
    if (userId) {
      config.headers["X-User-Id"] = userId;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // Handle specific error codes
      if (error.response.status === 401) {
        // Unauthorized - redirect to login
        localStorage.clear();
        window.location.href = "/login";
      } else if (error.response.status === 503) {
        // Service unavailable
        console.error("Service unavailable. Please try again later.");
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

---

## Core Features Implementation

### 1. Cover Letter Generation

```javascript
// src/services/coverLetterService.js
import apiClient from "./apiClient";
import { API_ENDPOINTS } from "../config/api";

export const generateCoverLetter = async (requestData) => {
  try {
    const response = await apiClient.post(API_ENDPOINTS.GENERATE_COVER_LETTER, {
      llm: requestData.llm || "gpt-4",
      date_input: requestData.date || new Date().toISOString().split("T")[0],
      company_name: requestData.companyName,
      hiring_manager: requestData.hiringManager || "",
      ad_source: requestData.adSource || "",
      resume: requestData.resume, // Can be text, S3 key, or base64 PDF
      jd: requestData.jobDescription,
      additional_instructions: requestData.additionalInstructions || "",
      tone: requestData.tone || "Professional",
      address: requestData.address || "",
      phone_number: requestData.phoneNumber || "",
      user_id: requestData.userId,
      user_email: requestData.userEmail,
    });

    return {
      markdown: response.data.markdown,
      html: response.data.html,
    };
  } catch (error) {
    if (error.response) {
      throw new Error(
        error.response.data.detail || "Failed to generate cover letter"
      );
    }
    throw new Error("Network error: Could not connect to server");
  }
};

// Generate with pasted resume text
export const generateCoverLetterWithTextResume = async (requestData) => {
  try {
    const response = await apiClient.post(
      API_ENDPOINTS.GENERATE_WITH_TEXT_RESUME,
      {
        llm: requestData.llm || "gpt-4",
        date_input: requestData.date || new Date().toISOString().split("T")[0],
        company_name: requestData.companyName,
        hiring_manager: requestData.hiringManager || "",
        ad_source: requestData.adSource || "",
        resume_text: requestData.resumeText, // Plain text resume
        jd: requestData.jobDescription,
        additional_instructions: requestData.additionalInstructions || "",
        tone: requestData.tone || "Professional",
        address: requestData.address || "",
        phone_number: requestData.phoneNumber || "",
        user_id: requestData.userId,
        user_email: requestData.userEmail,
      }
    );

    return {
      markdown: response.data.markdown,
      html: response.data.html,
    };
  } catch (error) {
    if (error.response) {
      throw new Error(
        error.response.data.detail || "Failed to generate cover letter"
      );
    }
    throw new Error("Network error: Could not connect to server");
  }
};
```

### 2. File Upload (Resume)

```javascript
// src/services/fileService.js
import apiClient from "./apiClient";
import { API_ENDPOINTS } from "../config/api";

export const uploadResume = async (file, userId) => {
  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("user_id", userId);
    formData.append("file_type", "resume");

    const response = await apiClient.post(API_ENDPOINTS.UPLOAD_FILE, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });

    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || "Failed to upload file");
    }
    throw new Error("Network error: Could not upload file");
  }
};

export const getUserFiles = async (userId) => {
  try {
    const response = await apiClient.get(API_ENDPOINTS.GET_FILES(userId));
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || "Failed to fetch files");
    }
    throw new Error("Network error: Could not fetch files");
  }
};

export const deleteFile = async (fileId) => {
  try {
    const response = await apiClient.delete(API_ENDPOINTS.DELETE_FILE(fileId));
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || "Failed to delete file");
    }
    throw new Error("Network error: Could not delete file");
  }
};
```

### 3. Cover Letter Management

```javascript
// src/services/coverLetterManagementService.js
import apiClient from "./apiClient";
import { API_ENDPOINTS } from "../config/api";

export const saveCoverLetter = async (coverLetterData) => {
  try {
    const response = await apiClient.post(API_ENDPOINTS.SAVE_COVER_LETTER, {
      user_id: coverLetterData.userId,
      title: coverLetterData.title,
      content: coverLetterData.content,
      company_name: coverLetterData.companyName,
      job_description: coverLetterData.jobDescription,
      llm_used: coverLetterData.llmUsed,
      metadata: coverLetterData.metadata || {},
    });

    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(
        error.response.data.detail || "Failed to save cover letter"
      );
    }
    throw new Error("Network error: Could not save cover letter");
  }
};

export const getUserCoverLetters = async (userId) => {
  try {
    const response = await apiClient.get(
      API_ENDPOINTS.GET_COVER_LETTERS(userId)
    );
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(
        error.response.data.detail || "Failed to fetch cover letters"
      );
    }
    throw new Error("Network error: Could not fetch cover letters");
  }
};

export const getCoverLetter = async (letterId) => {
  try {
    const response = await apiClient.get(
      API_ENDPOINTS.GET_COVER_LETTER(letterId)
    );
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(
        error.response.data.detail || "Failed to fetch cover letter"
      );
    }
    throw new Error("Network error: Could not fetch cover letter");
  }
};

export const deleteCoverLetter = async (letterId) => {
  try {
    const response = await apiClient.delete(
      API_ENDPOINTS.DELETE_COVER_LETTER(letterId)
    );
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(
        error.response.data.detail || "Failed to delete cover letter"
      );
    }
    throw new Error("Network error: Could not delete cover letter");
  }
};
```

### 4. PDF Generation

```javascript
// src/services/pdfService.js
import apiClient from "./apiClient";
import { API_ENDPOINTS } from "../config/api";

export const generatePDF = async (pdfData) => {
  try {
    const response = await apiClient.post(
      API_ENDPOINTS.GENERATE_PDF,
      {
        html_content: pdfData.htmlContent,
        user_id: pdfData.userId,
        print_properties: pdfData.printProperties || {},
      },
      {
        responseType: "blob", // Important for binary data
      }
    );

    // Create download link
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", pdfData.filename || "cover-letter.pdf");
    document.body.appendChild(link);
    link.click();
    link.remove();

    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || "Failed to generate PDF");
    }
    throw new Error("Network error: Could not generate PDF");
  }
};
```

### 5. Job URL Analysis

```javascript
// src/services/jobUrlService.js
import apiClient from "./apiClient";
import { API_ENDPOINTS } from "../config/api";

export const analyzeJobUrl = async (jobUrl) => {
  try {
    const response = await apiClient.post(API_ENDPOINTS.ANALYZE_JOB_URL, {
      url: jobUrl,
    });

    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(
        error.response.data.detail || "Failed to analyze job URL"
      );
    }
    throw new Error("Network error: Could not analyze job URL");
  }
};
```

### 6. User Settings Management

```javascript
// src/services/userService.js
import apiClient from "./apiClient";
import { API_ENDPOINTS } from "../config/api";

export const getUser = async (userId) => {
  try {
    const response = await apiClient.get(API_ENDPOINTS.GET_USER(userId));
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || "Failed to fetch user");
    }
    throw new Error("Network error: Could not fetch user");
  }
};

// Get user's generation credits
export const getUserCredits = async (userId) => {
  try {
    const user = await getUser(userId);
    // generation_credits will be null/undefined if not set, default to 0
    return user.generation_credits ?? 0;
  } catch (error) {
    console.error("Failed to get user credits:", error);
    return 0; // Default to 0 on error
  }
};

// Get user's max credits
export const getUserMaxCredits = async (userId) => {
  try {
    const user = await getUser(userId);
    // max_credits will be null/undefined if not set, default to 10
    return user.max_credits ?? 10;
  } catch (error) {
    console.error("Failed to get user max credits:", error);
    return 10; // Default to 10 on error
  }
};

export const updateUser = async (userId, updates) => {
  try {
    const response = await apiClient.put(
      API_ENDPOINTS.UPDATE_USER(userId),
      updates
    );
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || "Failed to update user");
    }
    throw new Error("Network error: Could not update user");
  }
};

// Update personality profiles
export const updatePersonalityProfiles = async (userId, profiles) => {
  try {
    const response = await apiClient.put(API_ENDPOINTS.UPDATE_USER(userId), {
      preferences: {
        appSettings: {
          personalityProfiles: profiles,
        },
      },
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(
        error.response.data.detail || "Failed to update personality profiles"
      );
    }
    throw new Error("Network error: Could not update personality profiles");
  }
};

// Update selected LLM model
export const updateSelectedModel = async (userId, modelName) => {
  try {
    const response = await apiClient.put(API_ENDPOINTS.UPDATE_USER(userId), {
      preferences: {
        appSettings: {
          selectedModel: modelName,
        },
      },
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(
        error.response.data.detail || "Failed to update selected model"
      );
    }
    throw new Error("Network error: Could not update selected model");
  }
};

// Update print properties
export const updatePrintProperties = async (userId, printProperties) => {
  try {
    const response = await apiClient.put(API_ENDPOINTS.UPDATE_USER(userId), {
      preferences: {
        appSettings: {
          printProperties: printProperties,
        },
      },
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(
        error.response.data.detail || "Failed to update print properties"
      );
    }
    throw new Error("Network error: Could not update print properties");
  }
};
```

### 7. SMS Verification

```javascript
// src/services/smsService.js
import apiClient from "./apiClient";
import { API_ENDPOINTS } from "../config/api";

export const sendSMSCode = async (email, phone, purpose) => {
  try {
    const response = await apiClient.post(API_ENDPOINTS.SEND_SMS_CODE, {
      email: email || null,
      phone: phone || null,
      purpose: purpose, // 'forgot_password', 'change_password', 'finish_registration'
    });

    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || "Failed to send SMS code");
    }
    throw new Error("Network error: Could not send SMS code");
  }
};

export const verifySMSCode = async (email, phone, code, purpose) => {
  try {
    const response = await apiClient.post(API_ENDPOINTS.VERIFY_SMS_CODE, {
      email: email || null,
      phone: phone || null,
      code: code,
      purpose: purpose,
    });

    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(
        error.response.data.detail || "Failed to verify SMS code"
      );
    }
    throw new Error("Network error: Could not verify SMS code");
  }
};
```

---

## State Management

### Using React Context

```javascript
// src/context/UserContext.js
import React, { createContext, useContext, useState, useEffect } from "react";
import { getUser, getCurrentUserId } from "../services/authService";
import { getUser as fetchUser } from "../services/userService";

const UserContext = createContext();

export const UserProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadUser = async () => {
      const userId = getCurrentUserId();
      if (userId) {
        try {
          setLoading(true);
          const userData = await fetchUser(userId);
          setUser(userData);
          setError(null);
        } catch (err) {
          setError(err.message);
          console.error("Failed to load user:", err);
        } finally {
          setLoading(false);
        }
      } else {
        setLoading(false);
      }
    };

    loadUser();
  }, []);

  const updateUser = async (updates) => {
    try {
      const updatedUser = await updateUser(user.id, updates);
      setUser(updatedUser);
      return updatedUser;
    } catch (err) {
      throw err;
    }
  };

  const value = {
    user,
    loading,
    error,
    updateUser,
    refreshUser: async () => {
      const userId = getCurrentUserId();
      if (userId) {
        const userData = await fetchUser(userId);
        setUser(userData);
      }
    },
  };

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
};

export const useUser = () => {
  const context = useContext(UserContext);
  if (!context) {
    throw new Error("useUser must be used within a UserProvider");
  }
  return context;
};
```

---

## Error Handling

### Error Handler Utility

```javascript
// src/utils/errorHandler.js
export const handleApiError = (error) => {
  if (error.response) {
    // Server responded with error status
    const status = error.response.status;
    const message = error.response.data?.detail || error.message;

    switch (status) {
      case 400:
        return { type: "validation", message };
      case 401:
        return { type: "auth", message: "Please log in to continue" };
      case 403:
        return {
          type: "permission",
          message: "You do not have permission to perform this action",
        };
      case 404:
        return { type: "notFound", message: "Resource not found" };
      case 409:
        return { type: "conflict", message };
      case 422:
        return { type: "validation", message };
      case 500:
        return {
          type: "server",
          message: "Server error. Please try again later.",
        };
      case 503:
        return {
          type: "service",
          message: "Service unavailable. Please try again later.",
        };
      default:
        return { type: "unknown", message };
    }
  } else if (error.request) {
    // Request made but no response
    return {
      type: "network",
      message: "Network error. Please check your connection.",
    };
  } else {
    // Something else happened
    return {
      type: "unknown",
      message: error.message || "An unexpected error occurred",
    };
  }
};

// Usage in components
try {
  await generateCoverLetter(data);
} catch (error) {
  const errorInfo = handleApiError(error);
  setError(errorInfo.message);
  // Show error to user
}
```

---

## Best Practices

### 1. Loading States

Always show loading indicators for async operations:

```javascript
const [loading, setLoading] = useState(false);

const handleGenerate = async () => {
  setLoading(true);
  try {
    const result = await generateCoverLetter(data);
    // Handle success
  } catch (error) {
    // Handle error
  } finally {
    setLoading(false);
  }
};
```

### 2. Form Validation

Validate inputs before sending to API:

```javascript
const validateCoverLetterForm = (data) => {
  const errors = {};

  if (!data.companyName?.trim()) {
    errors.companyName = "Company name is required";
  }

  if (!data.jobDescription?.trim()) {
    errors.jobDescription = "Job description is required";
  }

  if (!data.resume?.trim()) {
    errors.resume = "Resume is required";
  }

  return errors;
};
```

### 3. Debouncing

Use debouncing for search/autocomplete features:

```javascript
import { debounce } from "lodash";

const debouncedSearch = debounce(async (query) => {
  const results = await searchJobs(query);
  setResults(results);
}, 300);
```

### 4. Caching

Cache user data and settings:

```javascript
// Cache user data for 5 minutes
const CACHE_DURATION = 5 * 60 * 1000;
let cachedUser = null;
let cacheTime = null;

export const getCachedUser = async (userId) => {
  const now = Date.now();
  if (cachedUser && cacheTime && now - cacheTime < CACHE_DURATION) {
    return cachedUser;
  }

  cachedUser = await getUser(userId);
  cacheTime = now;
  return cachedUser;
};
```

### 5. Retry Logic

Implement retry for failed requests:

```javascript
const retryRequest = async (fn, retries = 3, delay = 1000) => {
  try {
    return await fn();
  } catch (error) {
    if (retries > 0) {
      await new Promise((resolve) => setTimeout(resolve, delay));
      return retryRequest(fn, retries - 1, delay * 2);
    }
    throw error;
  }
};
```

---

## Complete React Examples

### Cover Letter Generator Component

```javascript
// src/components/CoverLetterGenerator.js
import React, { useState } from "react";
import { generateCoverLetter } from "../services/coverLetterService";
import { useUser } from "../context/UserContext";
import { handleApiError } from "../utils/errorHandler";

const CoverLetterGenerator = () => {
  const { user } = useUser();
  const [formData, setFormData] = useState({
    companyName: "",
    hiringManager: "",
    adSource: "",
    jobDescription: "",
    resume: "",
    additionalInstructions: "",
    tone: "Professional",
    llm: "gpt-4",
  });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const coverLetter = await generateCoverLetter({
        ...formData,
        userId: user?.id,
        userEmail: user?.email,
      });

      setResult(coverLetter);
    } catch (err) {
      const errorInfo = handleApiError(err);
      setError(errorInfo.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="cover-letter-generator">
      <form onSubmit={handleSubmit}>
        <div>
          <label>Company Name *</label>
          <input
            type="text"
            value={formData.companyName}
            onChange={(e) =>
              setFormData({ ...formData, companyName: e.target.value })
            }
            required
          />
        </div>

        <div>
          <label>Hiring Manager</label>
          <input
            type="text"
            value={formData.hiringManager}
            onChange={(e) =>
              setFormData({ ...formData, hiringManager: e.target.value })
            }
          />
        </div>

        <div>
          <label>Job Description *</label>
          <textarea
            value={formData.jobDescription}
            onChange={(e) =>
              setFormData({ ...formData, jobDescription: e.target.value })
            }
            required
            rows={10}
          />
        </div>

        <div>
          <label>Resume *</label>
          <textarea
            value={formData.resume}
            onChange={(e) =>
              setFormData({ ...formData, resume: e.target.value })
            }
            required
            rows={15}
          />
        </div>

        <div>
          <label>LLM Model</label>
          <select
            value={formData.llm}
            onChange={(e) => setFormData({ ...formData, llm: e.target.value })}
          >
            <option value="gpt-4">GPT-4</option>
            <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
            <option value="claude-3-opus">Claude 3 Opus</option>
          </select>
        </div>

        {error && <div className="error">{error}</div>}

        <button type="submit" disabled={loading}>
          {loading ? "Generating..." : "Generate Cover Letter"}
        </button>
      </form>

      {result && (
        <div className="result">
          <h2>Generated Cover Letter</h2>
          <div dangerouslySetInnerHTML={{ __html: result.html }} />
        </div>
      )}
    </div>
  );
};

export default CoverLetterGenerator;
```

### User Settings Component

```javascript
// src/components/UserSettings.js
import React, { useState, useEffect } from "react";
import { useUser } from "../context/UserContext";
import {
  updateUser,
  updatePersonalityProfiles,
  updateSelectedModel,
} from "../services/userService";
import { handleApiError } from "../utils/errorHandler";

const UserSettings = () => {
  const { user, refreshUser } = useUser();
  const [personalityProfiles, setPersonalityProfiles] = useState([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user) {
      setPersonalityProfiles(
        user.preferences?.appSettings?.personalityProfiles || []
      );
      setSelectedModel(user.preferences?.appSettings?.selectedModel || "");
    }
  }, [user]);

  const handleSavePersonalityProfiles = async () => {
    setSaving(true);
    try {
      await updatePersonalityProfiles(user.id, personalityProfiles);
      await refreshUser();
      alert("Personality profiles saved successfully!");
    } catch (error) {
      const errorInfo = handleApiError(error);
      alert(`Failed to save: ${errorInfo.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSelectedModel = async () => {
    setSaving(true);
    try {
      await updateSelectedModel(user.id, selectedModel);
      await refreshUser();
      alert("Selected model saved successfully!");
    } catch (error) {
      const errorInfo = handleApiError(error);
      alert(`Failed to save: ${errorInfo.message}`);
    } finally {
      setSaving(false);
    }
  };

  if (!user) {
    return <div>Loading...</div>;
  }

  return (
    <div className="user-settings">
      <h2>User Settings</h2>

      <section>
        <h3>Personality Profiles</h3>
        {/* Render personality profiles editor */}
        <button onClick={handleSavePersonalityProfiles} disabled={saving}>
          {saving ? "Saving..." : "Save Profiles"}
        </button>
      </section>

      <section>
        <h3>Selected LLM Model</h3>
        <select
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
        >
          <option value="gpt-4">GPT-4</option>
          <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
          <option value="claude-3-opus">Claude 3 Opus</option>
        </select>
        <button onClick={handleSaveSelectedModel} disabled={saving}>
          {saving ? "Saving..." : "Save Model"}
        </button>
      </section>
    </div>
  );
};

export default UserSettings;
```

---

## Generation Credits

### Overview

For users without an active subscription (subscription status is "free"), the system tracks `generation_credits` which are decremented each time a cover letter is generated.

### Accessing Credits

The `generation_credits` field is included in the user object returned by all user endpoints:

```javascript
// Get user data (includes generation_credits)
const user = await getUser(userId);
const credits = user.generation_credits ?? 0; // Default to 0 if null/undefined

console.log(`User has ${credits} generation credits remaining`);
```

### Example: Check Credits Before Generation

```javascript
// src/components/CoverLetterGenerator.js
import { getUser } from "../services/userService";

const CoverLetterGenerator = () => {
  const [credits, setCredits] = useState(null);
  const { user } = useUser();

  useEffect(() => {
    if (user?.id) {
      loadCredits();
    }
  }, [user]);

  const loadCredits = async () => {
    try {
      const userData = await getUser(user.id);
      setCredits(userData.generation_credits ?? 0);
    } catch (error) {
      console.error("Failed to load credits:", error);
      setCredits(0);
    }
  };

  const handleGenerate = async () => {
    // Check if user has subscription
    const hasSubscription =
      user?.subscriptionStatus && user.subscriptionStatus !== "free";

    // For free users, check credits
    if (!hasSubscription) {
      if (credits === null) {
        await loadCredits(); // Refresh credits
      }

      if (credits <= 0) {
        alert(
          "You have no generation credits remaining. Please upgrade your plan or purchase credits."
        );
        return;
      }
    }

    // Proceed with generation
    // ... generation logic
  };

  return (
    <div>
      {!hasSubscription && credits !== null && (
        <div className="credits-display">
          <p>
            You have <b>{credits}</b> of {user.max_credits ?? 10} free
            generation credits.
          </p>
        </div>
      )}
      {/* Rest of component */}
    </div>
  );
};
```

### Example: Display Credits in User Profile

```javascript
// src/components/UserProfile.js
import { getUser } from "../services/userService";
import { useUser } from "../context/UserContext";

const UserProfile = () => {
  const { user, refreshUser } = useUser();
  const [credits, setCredits] = useState(null);

  useEffect(() => {
    if (user?.id) {
      // Credits are included in user object
      setCredits(user.generation_credits ?? 0);
    }
  }, [user]);

  const hasSubscription =
    user?.subscriptionStatus && user.subscriptionStatus !== "free";

  return (
    <div className="user-profile">
      <h2>User Profile</h2>

      {!hasSubscription && (
        <div className="credits-section">
          <h3>Generation Credits</h3>
          <p>
            You have <b>{credits ?? 0}</b> of {user.max_credits ?? 10} free
            generation credits.
          </p>
          {credits === 0 && (
            <p className="warning">
              You have no credits remaining. Upgrade to a subscription plan for
              unlimited generations.
            </p>
          )}
        </div>
      )}

      {hasSubscription && (
        <div className="subscription-info">
          <p>Active Subscription: {user.subscriptionStatus}</p>
          <p>Unlimited cover letter generations</p>
        </div>
      )}
    </div>
  );
};
```

### Notes

- `generation_credits` is only decremented for users with subscription status "free"
- Users with active subscriptions (status: "active", "trialing", etc.) have unlimited generations
- The field may be `null` or `undefined` for users who haven't had credits set yet (defaults to 0)
- `max_credits` is the fixed maximum credits for the free tier (defaults to 10)
- Credits are automatically decremented on the backend after successful cover letter generation
- Always refresh user data after generating a cover letter to get updated credit count
- Display format: "You have {generation_credits} of {max_credits} free generation credits"

---

## Additional Resources

- [User API Documentation](./USER_API_DOCUMENTATION.md)
- [Cover Letter Generation API](./COVER_LETTER_GENERATION_API.md)
- [File Management API](./FILE_MANAGEMENT_API.md)
- [SMS Verification API](./SMS_VERIFICATION_API.md)
- [Health Check API](./HEALTH_CHECK_API.md)

---

## Support

For issues or questions:

1. Check the API documentation for specific endpoints
2. Review error messages in the browser console
3. Check network requests in browser DevTools
4. Verify CORS configuration matches your frontend URL

---

**Last Updated**: 2024-12-31

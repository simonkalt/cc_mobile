/**
 * Comprehensive API Connection Debug Script
 * 
 * This script tests every step of connecting to your local Python server
 * and running multiple API endpoints to identify where failures occur.
 * 
 * Usage: node debug-api-connection.js
 */

const BACKEND_URL = "http://192.168.0.94:8000";

// Test user credentials (from your logs)
const USER_ID = "693326c07fcdaab8e81cdd2f";
const USER_EMAIL = "simonkalt@gmail.com";
const AUTH_TOKEN = USER_ID; // Using user ID as token (as per your code)

// Colors for console output
const colors = {
  reset: "\x1b[0m",
  bright: "\x1b[1m",
  red: "\x1b[31m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  blue: "\x1b[34m",
  cyan: "\x1b[36m",
};

function log(message, color = "reset") {
  console.log(`${colors[color]}${message}${colors.reset}`);
}

function logSection(title) {
  console.log("\n" + "=".repeat(60));
  log(title, "bright");
  console.log("=".repeat(60));
}

function logStep(step, message) {
  log(`\n[Step ${step}] ${message}`, "cyan");
}

function logSuccess(message) {
  log(`✅ ${message}`, "green");
}

function logError(message) {
  log(`❌ ${message}`, "red");
}

function logWarning(message) {
  log(`⚠️  ${message}`, "yellow");
}

function logInfo(message) {
  log(`ℹ️  ${message}`, "blue");
}

// Test 1: Basic Connectivity
async function testBasicConnectivity() {
  logSection("TEST 1: Basic Connectivity");
  
  logStep(1, "Checking if server is reachable...");
  logInfo(`Target URL: ${BACKEND_URL}`);
  
  let timeoutId;
  try {
    // Try a simple fetch to see if we can reach the server
    const controller = new AbortController();
    timeoutId = setTimeout(() => controller.abort(), 5000);
    
    logInfo("Attempting connection (5 second timeout)...");
    const response = await fetch(BACKEND_URL, {
      method: "GET",
      signal: controller.signal,
      headers: {
        "Accept": "*/*",
      },
    });
    
    if (timeoutId) clearTimeout(timeoutId);
    
    logSuccess(`Server responded with status: ${response.status} ${response.statusText}`);
    logInfo(`Response headers: ${JSON.stringify([...response.headers.entries()], null, 2)}`);
    
    const text = await response.text();
    logInfo(`Response body (first 200 chars): ${text.substring(0, 200)}`);
    
    return true;
  } catch (error) {
    if (timeoutId) clearTimeout(timeoutId);
    
    if (error.name === "AbortError") {
      logError("Connection timeout - server did not respond within 5 seconds");
      logInfo("Possible causes:");
      logInfo("  - Server is not running");
      logInfo("  - Wrong IP address or port");
      logInfo("  - Firewall blocking connection");
      logInfo("  - Network connectivity issue");
    } else if (error.message.includes("ECONNREFUSED")) {
      logError("Connection refused - server is not accepting connections");
      logInfo("Possible causes:");
      logInfo("  - Server is not running on port 8000");
      logInfo("  - Server is bound to localhost instead of 0.0.0.0");
      logInfo("  - Wrong port number");
    } else if (error.message.includes("ENOTFOUND") || error.message.includes("getaddrinfo")) {
      logError("DNS resolution failed - cannot resolve hostname");
      logInfo("Possible causes:");
      logInfo("  - Invalid IP address");
      logInfo("  - Network configuration issue");
    } else if (error.message.includes("Network request failed")) {
      logError("Network request failed");
      logInfo("Possible causes:");
      logInfo("  - No network connection");
      logInfo("  - CORS issue (if testing from browser)");
      logInfo("  - Server not accessible from this network");
    } else {
      logError(`Unexpected error: ${error.message}`);
      logInfo(`Error type: ${error.name}`);
      logInfo(`Error stack: ${error.stack}`);
    }
    
    return false;
  }
}

// Test 2: Health Check Endpoint
async function testHealthCheck() {
  logSection("TEST 2: Health Check Endpoint");
  
  const endpoint = `${BACKEND_URL}/api/health`;
  logStep(1, `Testing endpoint: ${endpoint}`);
  
  try {
    logInfo("Sending GET request...");
    const startTime = Date.now();
    
    const response = await fetch(endpoint, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
    });
    
    const duration = Date.now() - startTime;
    logInfo(`Response received in ${duration}ms`);
    logInfo(`Status: ${response.status} ${response.statusText}`);
    
    if (!response.ok) {
      logError(`Health check failed with status ${response.status}`);
      const errorText = await response.text();
      logInfo(`Error response: ${errorText}`);
      return false;
    }
    
    const data = await response.json();
    logSuccess("Health check passed!");
    logInfo(`Response data: ${JSON.stringify(data, null, 2)}`);
    
    if (data.ready) {
      logSuccess("Server is ready to handle requests");
    } else {
      logWarning("Server responded but reports not ready");
      logInfo(`MongoDB status: ${JSON.stringify(data.mongodb, null, 2)}`);
    }
    
    return true;
  } catch (error) {
    logError(`Health check failed: ${error.message}`);
    logInfo(`Error type: ${error.name}`);
    
    if (error.message.includes("fetch")) {
      logInfo("This suggests the server is not reachable or the endpoint doesn't exist");
    }
    
    return false;
  }
}

// Test 3: Terms of Service Endpoint
async function testTermsOfService() {
  logSection("TEST 3: Terms of Service Endpoint");
  
  const endpoint = `${BACKEND_URL}/api/files/terms-of-service`;
  logStep(1, `Testing endpoint: ${endpoint}`);
  
  try {
    logInfo("Sending GET request (no authentication required)...");
    const startTime = Date.now();
    
    const response = await fetch(endpoint, {
      method: "GET",
      headers: {
        "Accept": "application/pdf",
      },
    });
    
    const duration = Date.now() - startTime;
    logInfo(`Response received in ${duration}ms`);
    logInfo(`Status: ${response.status} ${response.statusText}`);
    logInfo(`Content-Type: ${response.headers.get("Content-Type")}`);
    logInfo(`Content-Length: ${response.headers.get("Content-Length") || "unknown"}`);
    
    if (!response.ok) {
      logError(`Terms of Service request failed with status ${response.status}`);
      
      // Try to get error details
      const contentType = response.headers.get("Content-Type");
      if (contentType && contentType.includes("application/json")) {
        const errorData = await response.json();
        logInfo(`Error response: ${JSON.stringify(errorData, null, 2)}`);
      } else {
        const errorText = await response.text();
        logInfo(`Error response: ${errorText.substring(0, 500)}`);
      }
      
      return false;
    }
    
    const blob = await response.blob();
    logSuccess(`Terms of Service PDF retrieved successfully!`);
    logInfo(`PDF size: ${blob.size} bytes (${(blob.size / 1024).toFixed(2)} KB)`);
    logInfo(`Blob type: ${blob.type}`);
    
    if (blob.size === 0) {
      logWarning("PDF blob is empty - this might indicate an issue");
    }
    
    return true;
  } catch (error) {
    logError(`Terms of Service request failed: ${error.message}`);
    logInfo(`Error type: ${error.name}`);
    
    if (error.message.includes("fetch")) {
      logInfo("This suggests the server is not reachable or the endpoint doesn't exist");
    }
    
    return false;
  }
}

// Test 4: User Preferences Endpoint
async function testUserPreferences() {
  logSection("TEST 4: User Preferences Endpoint");
  
  const endpoint = `${BACKEND_URL}/api/users/${USER_ID}`;
  logStep(1, `Testing endpoint: ${endpoint}`);
  logInfo(`User ID: ${USER_ID}`);
  logInfo(`Auth Token: ${AUTH_TOKEN}`);
  
  try {
    logInfo("Sending GET request with authentication...");
    const startTime = Date.now();
    
    const response = await fetch(endpoint, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": `Bearer ${AUTH_TOKEN}`,
      },
    });
    
    const duration = Date.now() - startTime;
    logInfo(`Response received in ${duration}ms`);
    logInfo(`Status: ${response.status} ${response.statusText}`);
    
    if (response.status === 404) {
      logError("User not found");
      logInfo("Possible causes:");
      logInfo("  - User ID is incorrect");
      logInfo("  - User doesn't exist in database");
      return false;
    }
    
    if (response.status === 401 || response.status === 403) {
      logError("Authentication failed");
      logInfo("Possible causes:");
      logInfo("  - Invalid auth token");
      logInfo("  - Token format is incorrect");
      logInfo("  - Server requires different authentication");
      return false;
    }
    
    if (!response.ok) {
      logError(`User preferences request failed with status ${response.status}`);
      const errorText = await response.text();
      logInfo(`Error response: ${errorText.substring(0, 500)}`);
      return false;
    }
    
    const data = await response.json();
    logSuccess("User preferences retrieved successfully!");
    logInfo(`User ID: ${data.id}`);
    logInfo(`User Email: ${data.email}`);
    logInfo(`User Name: ${data.name || "N/A"}`);
    
    if (data.preferences) {
      logInfo(`Has preferences: Yes`);
      if (data.preferences.appSettings) {
        logInfo(`Has app settings: Yes`);
        logInfo(`Selected model: ${data.preferences.appSettings.selectedModel || "N/A"}`);
        logInfo(`Personality profiles count: ${data.preferences.appSettings.personalityProfiles?.length || 0}`);
      } else {
        logWarning("User has preferences but no appSettings");
      }
    } else {
      logWarning("User has no preferences object");
    }
    
    return true;
  } catch (error) {
    logError(`User preferences request failed: ${error.message}`);
    logInfo(`Error type: ${error.name}`);
    
    if (error.message.includes("fetch")) {
      logInfo("This suggests the server is not reachable or the endpoint doesn't exist");
    }
    
    return false;
  }
}

// Test 5: Files List Endpoint
async function testFilesList() {
  logSection("TEST 5: Files List Endpoint");
  
  const urlParams = new URLSearchParams();
  urlParams.append("user_id", USER_ID);
  urlParams.append("user_email", USER_EMAIL);
  const endpoint = `${BACKEND_URL}/api/files/list?${urlParams.toString()}`;
  
  logStep(1, `Testing endpoint: ${endpoint}`);
  logInfo(`User ID: ${USER_ID}`);
  logInfo(`User Email: ${USER_EMAIL}`);
  logInfo(`Auth Token: ${AUTH_TOKEN}`);
  
  try {
    logInfo("Sending GET request with authentication...");
    const startTime = Date.now();
    
    const response = await fetch(endpoint, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": `Bearer ${AUTH_TOKEN}`,
      },
    });
    
    const duration = Date.now() - startTime;
    logInfo(`Response received in ${duration}ms`);
    logInfo(`Status: ${response.status} ${response.statusText}`);
    
    if (response.status === 401 || response.status === 403) {
      logError("Authentication failed");
      logInfo("Possible causes:");
      logInfo("  - Invalid auth token");
      logInfo("  - Token format is incorrect");
      logInfo("  - Server requires different authentication");
      return false;
    }
    
    if (!response.ok) {
      logError(`Files list request failed with status ${response.status}`);
      const errorText = await response.text();
      logInfo(`Error response: ${errorText.substring(0, 500)}`);
      return false;
    }
    
    const data = await response.json();
    logSuccess("Files list retrieved successfully!");
    
    const files = data.files || [];
    logInfo(`Total files found: ${files.length}`);
    
    if (files.length > 0) {
      logInfo("\nFiles:");
      files.slice(0, 5).forEach((file, index) => {
        logInfo(`  ${index + 1}. ${file.name || file.key}`);
        logInfo(`     Key: ${file.key}`);
        logInfo(`     Size: ${file.size || 0} bytes`);
      });
      if (files.length > 5) {
        logInfo(`  ... and ${files.length - 5} more files`);
      }
    } else {
      logWarning("No files found in response");
      logInfo("This might be normal if the user has no files uploaded");
    }
    
    return true;
  } catch (error) {
    logError(`Files list request failed: ${error.message}`);
    logInfo(`Error type: ${error.name}`);
    
    if (error.message.includes("fetch")) {
      logInfo("This suggests the server is not reachable or the endpoint doesn't exist");
    }
    
    return false;
  }
}

// Main test runner
async function runAllTests() {
  console.clear();
  log("\n" + "=".repeat(60), "bright");
  log("API Connection Debug Script", "bright");
  log("=".repeat(60), "bright");
  logInfo(`Backend URL: ${BACKEND_URL}`);
  logInfo(`User ID: ${USER_ID}`);
  logInfo(`User Email: ${USER_EMAIL}`);
  logInfo(`Start time: ${new Date().toISOString()}`);
  
  const results = {
    connectivity: false,
    healthCheck: false,
    termsOfService: false,
    userPreferences: false,
    filesList: false,
  };
  
  // Test 1: Basic Connectivity (must pass for others to work)
  results.connectivity = await testBasicConnectivity();
  
  if (!results.connectivity) {
    logSection("SUMMARY");
    logError("Basic connectivity test failed - cannot proceed with other tests");
    logInfo("\nTroubleshooting steps:");
    logInfo("1. Verify your Python server is running");
    logInfo("2. Check that the server is bound to 0.0.0.0 (not just localhost)");
    logInfo(`3. Verify the IP address ${BACKEND_URL.split("://")[1].split(":")[0]} is correct`);
    logInfo("4. Check firewall settings");
    logInfo("5. Try accessing the server from a browser: " + BACKEND_URL);
    return;
  }
  
  // Test 2: Health Check
  results.healthCheck = await testHealthCheck();
  
  // Test 3: Terms of Service
  results.termsOfService = await testTermsOfService();
  
  // Test 4: User Preferences
  results.userPreferences = await testUserPreferences();
  
  // Test 5: Files List
  results.filesList = await testFilesList();
  
  // Final Summary
  logSection("FINAL SUMMARY");
  
  const passed = Object.values(results).filter(r => r).length;
  const total = Object.keys(results).length;
  
  logInfo(`Tests passed: ${passed}/${total}`);
  console.log("\nDetailed results:");
  
  Object.entries(results).forEach(([test, passed]) => {
    if (passed) {
      logSuccess(`  ${test}: PASSED`);
    } else {
      logError(`  ${test}: FAILED`);
    }
  });
  
  console.log("\n");
  
  if (passed === total) {
    logSuccess("All tests passed! Your API connection is working correctly.", "green");
  } else {
    logWarning("Some tests failed. Review the detailed output above for troubleshooting.", "yellow");
  }
  
  logInfo(`End time: ${new Date().toISOString()}`);
  console.log("\n");
}

// Run the tests
runAllTests().catch((error) => {
  logError(`Fatal error running tests: ${error.message}`);
  logInfo(`Error stack: ${error.stack}`);
  process.exit(1);
});


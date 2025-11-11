import React, { useState, useEffect } from "react";

import {
  StyleSheet,
  Text,
  View,
  TextInput,
  Button,
  Alert,
  ActivityIndicator,
  TouchableOpacity,
} from "react-native";

import { SafeAreaView } from "react-native-safe-area-context";

// ⚠️ IMPORTANT: Replace this with your computer's local network IP
// Do NOT use 'localhost' or '127.0.0.1'
// Find it with 'ifconfig' (Mac/Linux) or 'ipconfig' (Windows)
const BACKEND_URL = "https://cc-mobile.onrender.com"; // <-- CHANGE THIS

export default function App() {
  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);
  const [llms, setLlms] = useState([]);
  const [selectedModel, setSelectedModel] = useState(null);
  const [loadingLlms, setLoadingLlms] = useState(true);

  // Fetch available LLMs on component mount
  useEffect(() => {
    fetchAvailableLlms();
  }, []);

  const fetchAvailableLlms = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/llms`);
      const data = await res.json();

      if (data.llms && data.llms.length > 0) {
        setLlms(data.llms);
        // Set the first available LLM as default
        setSelectedModel(data.llms[0].value);
      } else {
        Alert.alert(
          "No LLMs Available",
          "No language models are configured on the server."
        );
      }
    } catch (error) {
      console.error(error);
      Alert.alert("Error", "Could not fetch available LLMs from the backend.");
    } finally {
      setLoadingLlms(false);
    }
  };

  const handleSendPrompt = async () => {
    if (!prompt) {
      Alert.alert("Error", "Please enter a prompt.");
      return;
    }

    if (!selectedModel) {
      Alert.alert("Error", "Please select a language model.");
      return;
    }

    setLoading(true);
    setResponse("");

    try {
      // Send the request to the /chat endpoint with the selected model
      const res = await fetch(`${BACKEND_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prompt: prompt,
          active_model: selectedModel,
        }),
      });

      const data = await res.json();

      if (data.response) {
        setResponse(data.response);
      } else {
        throw new Error("Invalid response from server");
      }
    } catch (error) {
      console.error(error);
      Alert.alert("Request Failed", "Could not connect to the backend.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>LLM Chat App</Text>

      {/* LLM Selection Radio Buttons */}
      {loadingLlms ? (
        <ActivityIndicator size="small" style={styles.llmLoader} />
      ) : (
        <View style={styles.llmContainer}>
          <Text style={styles.llmTitle}>Select Language Model:</Text>
          {llms.map((llm) => (
            <TouchableOpacity
              key={llm.value}
              style={styles.radioButton}
              onPress={() => setSelectedModel(llm.value)}
            >
              <View style={styles.radioCircle}>
                {selectedModel === llm.value && (
                  <View style={styles.radioChecked} />
                )}
              </View>
              <Text style={styles.radioLabel}>{llm.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      <TextInput
        style={styles.input}
        placeholder="Type your prompt here..."
        value={prompt}
        onChangeText={setPrompt}
        multiline
      />

      <Button
        title={loading ? "Sending..." : "Send Prompt"}
        onPress={handleSendPrompt}
        disabled={loading || !selectedModel}
      />

      {loading && <ActivityIndicator size="large" style={styles.loader} />}

      {response && (
        <View style={styles.responseContainer}>
          <Text style={styles.responseTitle}>Server Response:</Text>
          <Text style={styles.responseText}>{response}</Text>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#f5f5f5",
    alignItems: "center",
    padding: 20,
  },
  title: {
    fontSize: 24,
    fontWeight: "bold",
    marginBottom: 20,
  },
  llmContainer: {
    width: "100%",
    marginBottom: 20,
    padding: 15,
    backgroundColor: "#fff",
    borderRadius: 8,
    borderColor: "#eee",
    borderWidth: 1,
  },
  llmTitle: {
    fontSize: 16,
    fontWeight: "bold",
    marginBottom: 12,
  },
  llmLoader: {
    marginBottom: 20,
  },
  radioButton: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 10,
  },
  radioCircle: {
    height: 20,
    width: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: "#007AFF",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 10,
  },
  radioChecked: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: "#007AFF",
  },
  radioLabel: {
    fontSize: 16,
  },
  input: {
    width: "100%",
    borderColor: "#ccc",
    borderWidth: 1,
    borderRadius: 8,
    padding: 15,
    marginBottom: 20,
    backgroundColor: "#fff",
    minHeight: 100,
    textAlignVertical: "top",
  },
  loader: {
    marginTop: 20,
  },
  responseContainer: {
    marginTop: 30,
    width: "100%",
    padding: 15,
    backgroundColor: "#fff",
    borderRadius: 8,
    borderColor: "#eee",
    borderWidth: 1,
  },
  responseTitle: {
    fontSize: 16,
    fontWeight: "bold",
    marginBottom: 5,
  },
  responseText: {
    fontSize: 16,
  },
});

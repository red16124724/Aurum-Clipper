import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

// No StrictMode: its dev-only double-invoke of effects restarts/cancels the
// background download + transcription polling, which froze the progress bars.
createRoot(document.getElementById("root")).render(<App />);

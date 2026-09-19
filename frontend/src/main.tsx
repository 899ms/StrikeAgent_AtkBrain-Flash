import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { appBase } from "./appBase";
import { LocaleProvider } from "./i18n";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <LocaleProvider>
      <BrowserRouter basename={appBase() || undefined}>
        <App />
      </BrowserRouter>
    </LocaleProvider>
  </React.StrictMode>
);

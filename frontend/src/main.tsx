import React from "react";
import ReactDOM from "react-dom/client";

function Placeholder() {
  return <div>看板初始化中…</div>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Placeholder />
  </React.StrictMode>
);

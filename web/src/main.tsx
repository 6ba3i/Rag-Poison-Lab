import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { Experiments } from "./pages/Experiments";
import { Overview } from "./pages/Overview";
import { Results } from "./pages/Results";
import { Settings } from "./pages/Settings";
import { UserDetail } from "./pages/UserDetail";
import { Users } from "./pages/Users";
import "./styles/index.css";

function App(): JSX.Element {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview" element={<Overview />} />
          <Route path="experiments" element={<Experiments />} />
          <Route path="users" element={<Users />} />
          <Route path="users/:userId" element={<UserDetail />} />
          <Route path="results" element={<Results />} />
          <Route path="settings" element={<Settings />} />
          <Route path="dashboard/:userId" element={<UserDetail />} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);

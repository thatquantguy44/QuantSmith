import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, createHashRouter, RouterProvider } from "react-router-dom";
import "./index.css";
import { Layout } from "./app/layout";
import { Overview } from "./app/routes/overview";
import { Trends } from "./app/routes/trends";
import { GraphView } from "./app/routes/graph";
import { Changes } from "./app/routes/changes";
import { Review } from "./app/routes/review";
import { Research } from "./app/routes/research";
import { Ask } from "./app/routes/ask";

// Client-side routes (file-based by convention under src/app/routes/).
const routes = [
  {
    element: <Layout />,
    children: [
      { index: true, element: <Overview /> },
      { path: "trends", element: <Trends /> },
      { path: "graph", element: <GraphView /> },
      { path: "changes", element: <Changes /> },
      { path: "review", element: <Review /> },
      { path: "research", element: <Research /> },
      { path: "ask", element: <Ask /> },
    ],
  },
];

// Clean paths for the served app; hash routing for the self-contained snapshot,
// which is opened from an arbitrary base path where pathname routing can't match.
const useHash = import.meta.env.VITE_HASH_ROUTER === "1";
const router = useHash ? createHashRouter(routes) : createBrowserRouter(routes);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);

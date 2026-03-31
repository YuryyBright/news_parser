// src/App.tsx
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import { queryClient } from "./lib/queryClient";
import { Layout } from "./components/layout/Layout";
import { LoginPage } from "./pages/LoginPage";
import { FeedPage } from "./pages/FeedPage";
import { ArticlesPage } from "./pages/ArticlesPage";
import { SourcesPage } from "./pages/SourcesPage";
import { TasksPage } from "./pages/TasksPage";
import { NotFoundPage } from "./pages/NotFoundPage";
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Публічна сторінка */}
          <Route path="/login" element={<LoginPage />} />

          {/* Захищені сторінки з Layout */}
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/feed" replace />} />
            <Route path="feed" element={<FeedPage />} />
            <Route path="articles" element={<ArticlesPage />} />
            <Route path="sources" element={<SourcesPage />} />
            <Route path="tasks" element={<TasksPage />} />
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>

      {/* Toast notifications */}
      <Toaster
        position="bottom-right"
        toastOptions={{
          className:
            "dark:bg-slate-800 dark:text-slate-100 dark:border-slate-700",
        }}
      />
    </QueryClientProvider>
  );
}

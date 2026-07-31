import { createBrowserRouter } from "react-router-dom";
import { Layout } from "@/components/layout/Layout";
import HomePage from "@/pages/HomePage";
import SupportFormPage from "@/pages/SupportFormPage";
import SupportResultsPage from "@/pages/SupportResultsPage";
import CostFormPage from "@/pages/CostFormPage";
import CostDisclaimerPage from "@/pages/CostDisclaimerPage";
import CostResultsPage from "@/pages/CostResultsPage";
import ProviderSearchPage from "@/pages/ProviderSearchPage";
import AllSchemesPage from "@/pages/AllSchemesPage";
import PlaceholderPage from "@/pages/PlaceholderPage";

export const router = createBrowserRouter(
  [
    {
      element: <Layout />,
      children: [
        { path: "/", element: <HomePage /> },
        { path: "/support", element: <SupportFormPage /> },
        { path: "/support/results", element: <SupportResultsPage /> },
        { path: "/support/schemes", element: <AllSchemesPage /> },
        { path: "/costs", element: <CostFormPage /> },
        { path: "/costs/disclaimer", element: <CostDisclaimerPage /> },
        { path: "/costs/results", element: <CostResultsPage /> },
        { path: "/providers", element: <ProviderSearchPage /> },
        { path: "/placeholder", element: <PlaceholderPage /> },
        {
          path: "*",
          element: (
            <div className="text-center py-20">
              <h1 className="text-4xl font-bold mb-4">Page not found</h1>
              <p className="text-lg text-zinc-600">
                The page you're looking for doesn't exist.
              </p>
              <a href="/" className="btn-dark mt-6 inline-flex">
                Go home
              </a>
            </div>
          ),
        },
      ],
    },
  ],
  { basename: import.meta.env.BASE_URL },
);

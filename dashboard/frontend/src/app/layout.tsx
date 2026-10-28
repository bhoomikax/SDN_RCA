import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { RunSelectionProvider } from "@/lib/run-selection";

export const metadata: Metadata = {
  title: "SDN Fault Localisation — Research Demo",
  description: "Topology-Aware, Temporally Informed Root-Cause Analysis",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <RunSelectionProvider>
          <div className="flex min-h-screen">
            <Sidebar />
            <main className="flex-1 min-w-0 px-6 py-5 lg:px-8">{children}</main>
          </div>
        </RunSelectionProvider>
      </body>
    </html>
  );
}

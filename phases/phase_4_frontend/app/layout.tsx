import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "AI Restaurant Recommendations",
  description: "Find the perfect place to eat based on your mood and preferences."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

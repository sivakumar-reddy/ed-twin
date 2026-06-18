import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ed-twin — what actually constrains ED throughput",
  description:
    "An interactive emergency department digital twin. Drag the capacity levers and see what actually moves length of stay. Physicians, not beds.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI4MS · 管理科学科研工作台",
  description: "与阶段智能体协作，从选题、证据和研究设计走向可审批、可复现的管理科学研究。",
  other: {
    "codex-preview": "development",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}


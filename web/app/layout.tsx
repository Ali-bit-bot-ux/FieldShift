import type { Metadata } from "next";
import "@fontsource-variable/noto-sans/wght.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "FieldShift",
  description: "Crop rotation planner · Планировщик севооборота · Ауыспалы егіс жоспарлағышы",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VisionGuard | Panel de seguridad",
  description: "Panel de monitoreo y analítica de detecciones.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}

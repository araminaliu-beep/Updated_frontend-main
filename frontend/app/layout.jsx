import "./globals.css";

export const metadata = {
  title: "Meeting Action Dashboard",
  description: "Meeting-to-action project execution dashboard",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Mini-Devin | Autonomous Issue-to-PR System',
  description:
    'Mini-Devin is an autonomous GitHub issue-to-pull-request multi-agent system.',
  icons: {
    icon: '/logo.svg',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-surface-container-lowest text-on-surface antialiased selection:bg-primary/20">
        {children}
      </body>
    </html>
  );
}

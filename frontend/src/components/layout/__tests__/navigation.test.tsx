import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { Sidebar } from '../Sidebar';
import { Header } from '../Header';

describe('Sidebar Navigation & Header Context (Tasks 1 & 12)', () => {
  it('renders all 8 autonomous agent views in the sidebar navigation', () => {
    const handleSelectNav = vi.fn();
    render(<Sidebar activeNav="dashboard" onSelectNav={handleSelectNav} />);

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Live Console')).toBeInTheDocument();
    expect(screen.getByText('Plan Approval')).toBeInTheDocument();
    expect(screen.getByText('Diff Viewer')).toBeInTheDocument();
    expect(screen.getByText('Tests & Preview')).toBeInTheDocument();
    expect(screen.getByText('Artifacts')).toBeInTheDocument();
    expect(screen.getByText('Transparency')).toBeInTheDocument();
    expect(screen.getByText('Evaluation')).toBeInTheDocument();
  });

  it('triggers onSelectNav callback when a navigation item is clicked', () => {
    const handleSelectNav = vi.fn();
    render(<Sidebar activeNav="dashboard" onSelectNav={handleSelectNav} />);

    const liveConsoleBtn = screen.getByRole('button', { name: /Live Console/i });
    fireEvent.click(liveConsoleBtn);

    expect(handleSelectNav).toHaveBeenCalledWith('live-console');
  });

  it('displays the Nikunj Nanda · Frontend Lead attribution in the sidebar footer', () => {
    render(<Sidebar activeNav="dashboard" />);
    expect(screen.getByText(/Nikunj Nanda · Frontend Lead/i)).toBeInTheDocument();
  });

  it('renders dynamic breadcrumbs in Header corresponding to activeNav', () => {
    const { rerender } = render(
      <Header onToggleMobileSidebar={vi.fn()} activeNav="dashboard" />
    );
    expect(screen.getByText('Dashboard')).toBeInTheDocument();

    rerender(<Header onToggleMobileSidebar={vi.fn()} activeNav="diff-viewer" />);
    expect(screen.getByText('Diff Viewer')).toBeInTheDocument();

    rerender(<Header onToggleMobileSidebar={vi.fn()} activeNav="evaluation" />);
    expect(screen.getByText('Evaluation')).toBeInTheDocument();
  });

  it('renders honest backend offline status pill in Header', () => {
    render(<Header onToggleMobileSidebar={vi.fn()} activeNav="dashboard" />);
    expect(screen.getByText(/Not connected \(foundation preview\)/i)).toBeInTheDocument();
  });
});

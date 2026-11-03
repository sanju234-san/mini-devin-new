import React from 'react';
import { CapabilityCard, CapabilityCardProps } from './CapabilityCard';
import {
  QuiltIcon,
  TerminalIcon,
  StreamIcon,
  ChecklistIcon,
  RuleIcon,
  DiffIcon,
  SplitIcon,
  ScienceIcon,
  BugIcon,
  FolderZipIcon,
  InventoryIcon,
  MonitoringIcon,
  InsightsIcon,
} from '../icons/Icons';

export const CapabilitiesGrid: React.FC = () => {
  const capabilities: CapabilityCardProps[] = [
    {
      id: 'live-console',
      title: 'Live Console',
      description: 'Monitor agent activity and execution progress in real time.',
      footerFeature:
        'Real-time WebSocket event stream, bash execution logs & thinking trace',
      icon: <TerminalIcon className="w-5 h-5" />,
      footerIcon: <StreamIcon className="w-4 h-4" />,
      colorScheme: 'cyan',
    },
    {
      id: 'plan-approval',
      title: 'Plan Approval',
      description: 'Review and approve the implementation plan before coding begins.',
      footerFeature:
        'Interactive step approval, file modification scope & requirement breakdown',
      icon: <ChecklistIcon className="w-5 h-5" />,
      footerIcon: <RuleIcon className="w-4 h-4" />,
      colorScheme: 'indigo',
    },
    {
      id: 'diff-viewer',
      title: 'Diff Viewer',
      description: 'Review generated code changes in an IDE-style interface.',
      footerFeature:
        'Side-by-side split view, unified hunk inspection & syntax highlighting',
      icon: <DiffIcon className="w-5 h-5" />,
      footerIcon: <SplitIcon className="w-4 h-4" />,
      colorScheme: 'emerald',
    },
    {
      id: 'tests-and-preview',
      title: 'Tests & Preview',
      description: 'Monitor test execution and preview sandbox results.',
      footerFeature:
        'Automated test runner output, coverage assertions & container preview',
      icon: <ScienceIcon className="w-5 h-5" />,
      footerIcon: <BugIcon className="w-4 h-4" />,
      colorScheme: 'blue',
    },
    {
      id: 'artifacts',
      title: 'Artifacts',
      description:
        'Review implementation plans, diffs, logs, screenshots, and walkthroughs.',
      footerFeature:
        'Persistent artifact manifest, trace logs & execution recording exports',
      icon: <FolderZipIcon className="w-5 h-5" />,
      footerIcon: <InventoryIcon className="w-4 h-4" />,
      colorScheme: 'amber',
    },
    {
      id: 'eval-results',
      title: 'Eval Results',
      description: 'Review fix accuracy, test performance, and evaluation metrics.',
      footerFeature:
        'SWE-bench validation scores, token cost analytics & accuracy benchmarks',
      icon: <MonitoringIcon className="w-5 h-5" />,
      footerIcon: <InsightsIcon className="w-4 h-4" />,
      colorScheme: 'teal',
    },
  ];

  return (
    <section className="flex flex-col gap-space-md pt-space-xs">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <QuiltIcon className="w-5 h-5 text-primary" />
          <h2 className="text-xl font-semibold text-on-surface">
            Platform Capabilities &amp; Subsystems
          </h2>
        </div>
        <p className="text-sm text-on-surface-variant">
          Dedicated inspection and verification surfaces for the autonomous coding lifecycle
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-space-lg">
        {capabilities.map((card) => (
          <CapabilityCard key={card.id} {...card} />
        ))}
      </div>
    </section>
  );
};

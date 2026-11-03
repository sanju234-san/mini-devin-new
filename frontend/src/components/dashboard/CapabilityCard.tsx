import React from 'react';

export interface CapabilityCardProps {
  id: string;
  title: string;
  description: string;
  footerFeature: string;
  icon: React.ReactNode;
  footerIcon: React.ReactNode;
  colorScheme: 'cyan' | 'indigo' | 'emerald' | 'blue' | 'amber' | 'teal';
}

const colorStyles = {
  cyan: {
    iconBox: 'text-tertiary',
    borderHover: 'hover:border-tertiary/40',
    titleHover: 'group-hover:text-tertiary',
    badge: 'bg-tertiary/10 text-tertiary border-tertiary/30',
    footerIcon: 'text-tertiary/70',
  },
  indigo: {
    iconBox: 'text-secondary',
    borderHover: 'hover:border-secondary/40',
    titleHover: 'group-hover:text-secondary',
    badge: 'bg-secondary/10 text-secondary border-secondary/30',
    footerIcon: 'text-secondary/70',
  },
  emerald: {
    iconBox: 'text-emerald-400',
    borderHover: 'hover:border-emerald-400/40',
    titleHover: 'group-hover:text-emerald-400',
    badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    footerIcon: 'text-emerald-400/70',
  },
  blue: {
    iconBox: 'text-primary',
    borderHover: 'hover:border-primary/40',
    titleHover: 'group-hover:text-primary',
    badge: 'bg-primary/10 text-primary border-primary/30',
    footerIcon: 'text-primary/70',
  },
  amber: {
    iconBox: 'text-amber-400',
    borderHover: 'hover:border-amber-400/40',
    titleHover: 'group-hover:text-amber-400',
    badge: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    footerIcon: 'text-amber-400/70',
  },
  teal: {
    iconBox: 'text-teal-400',
    borderHover: 'hover:border-teal-400/40',
    titleHover: 'group-hover:text-teal-400',
    badge: 'bg-teal-500/10 text-teal-400 border-teal-500/30',
    footerIcon: 'text-teal-400/70',
  },
};

export const CapabilityCard: React.FC<CapabilityCardProps> = ({
  title,
  description,
  footerFeature,
  icon,
  footerIcon,
  colorScheme,
}) => {
  const styles = colorStyles[colorScheme];

  return (
    <div
      className={`group relative rounded-xl bg-surface-container-low border border-outline-variant/30 ${styles.borderHover} p-space-lg flex flex-col justify-between transition-all duration-200 shadow-sm cursor-default`}
      aria-label={`${title} - Coming Soon`}
    >
      <div className="flex flex-col gap-space-md">
        <div className="flex items-center justify-between">
          <div
            className={`w-10 h-10 rounded-lg bg-surface-container-high border border-outline-variant/30 flex items-center justify-center ${styles.iconBox}`}
          >
            {icon}
          </div>
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider border ${styles.badge}`}
          >
            Coming Soon
          </span>
        </div>

        <div>
          <h3
            className={`text-base font-semibold text-on-surface ${styles.titleHover} transition-colors`}
          >
            {title}
          </h3>
          <p className="text-sm text-on-surface-variant mt-1 leading-relaxed">
            {description}
          </p>
        </div>
      </div>

      <div className="mt-space-lg pt-space-md border-t border-outline-variant/20 flex items-start gap-2 text-outline">
        <div className={`flex-shrink-0 mt-0.5 ${styles.footerIcon}`}>
          {footerIcon}
        </div>
        <span className="font-mono text-xs leading-tight text-outline">
          {footerFeature}
        </span>
      </div>
    </div>
  );
};

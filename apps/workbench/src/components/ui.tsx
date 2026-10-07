import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import type { TaskStatus } from '../domain/types';
import { taskLabels } from '../domain/workspace';
import { Icon, type IconName } from './Icon';

export function Button({
  children,
  icon,
  variant = '',
  className = '',
  type = 'button',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  icon?: IconName;
  variant?: 'primary' | 'ghost' | 'danger' | '';
}) {
  return (
    <button type={type} className={`button ${variant} ${className}`} {...props}>
      {icon && <Icon name={icon} />}
      {children}
    </button>
  );
}

export function IconButton({
  label,
  icon,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; icon: IconName }) {
  return (
    <button
      type="button"
      {...props}
      aria-label={label}
      title={label}
      className={`icon-button ${props.className ?? ''}`}
    >
      <Icon name={icon} />
    </button>
  );
}

export function PageHeader({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      <div className="page-actions">{children}</div>
    </div>
  );
}

export function SectionHeader({
  title,
  eyebrow,
  to,
  action = '查看全部',
}: {
  title: string;
  eyebrow?: string;
  to?: string;
  action?: string;
}) {
  return (
    <div className="section-head">
      <h2>
        {title}
        {eyebrow && <small>{eyebrow}</small>}
      </h2>
      {to && (
        <Link className="text-button" to={to}>
          {action}
          <Icon name="arrow" />
        </Link>
      )}
    </div>
  );
}

export function Badge({ status = '', children }: { status?: string; children: ReactNode }) {
  return (
    <span className={`tag ${status}`}>
      <span className="tag-dot" />
      {children}
    </span>
  );
}

export function TaskBadge({ status }: { status: TaskStatus }) {
  return <Badge status={status}>{taskLabels[status]}</Badge>;
}

export function Notice({ children, warm = false }: { children: ReactNode; warm?: boolean }) {
  return (
    <div className={`notice ${warm ? 'warm' : ''}`}>
      <Icon name="info" />
      <span>{children}</span>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  icon = 'folder',
  children,
}: {
  title: string;
  description: string;
  icon?: IconName;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <Icon name={icon} />
      <h3>{title}</h3>
      <p>{description}</p>
      {children}
    </div>
  );
}

export function Progress({ value, label }: { value: number | null; label: string }) {
  const bounded = value === null ? undefined : Math.min(100, Math.max(0, value));
  return (
    <div
      className={`progress ${value === null ? 'indeterminate' : ''}`}
      role="progressbar"
      aria-label={label}
      aria-valuenow={bounded}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <span style={{ width: bounded === undefined ? '35%' : `${bounded}%` }} />
    </div>
  );
}

export function SearchField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="search-field">
      <Icon name="search" />
      <input
        type="search"
        aria-label={label}
        placeholder={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

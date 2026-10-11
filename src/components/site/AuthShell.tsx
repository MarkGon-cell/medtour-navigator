import { HeartPulse } from "lucide-react";
import type { ReactElement, ReactNode } from "react";
import { PageHeader } from "./PageHeader";

export interface AuthShellProps {
  /** 底栏胶囊标题（Sign in / Create account）。 */
  headerTitle: string;
  headerSubtitle?: string;
  /** 卡片大标题。 */
  title: string;
  subtitle: string;
  children: ReactNode;
  /** 卡片下方的切换链接。 */
  footer: ReactNode;
}

/**
 * 登录/注册共用外壳：柔和的主色光晕背景 + 居中玻璃卡片。
 * 顶部保留全站胶囊顶栏（MedTour | …）。
 */
export function AuthShell({
  headerTitle,
  headerSubtitle,
  title,
  subtitle,
  children,
  footer,
}: AuthShellProps): ReactElement {
  return (
    <div className="relative min-h-screen bg-background">
      {/* 柔和主色光晕 */}
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/2 h-[380px] w-[640px] max-w-[120vw] -translate-x-1/2 rounded-full bg-primary/15 blur-3xl" />
        <div className="absolute -bottom-32 -right-24 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
      </div>

      <div className="relative">
        <PageHeader title={headerTitle} subtitle={headerSubtitle} backTo="/" />

        <main className="mx-auto flex w-full max-w-md flex-col items-center px-4 py-8 sm:py-12">
          <div className="w-full rounded-3xl border border-border/70 bg-card/80 p-6 shadow-soft backdrop-blur sm:p-8">
            <div className="flex flex-col items-center text-center">
              <div className="grid h-12 w-12 place-items-center rounded-2xl bg-primary/10 text-primary">
                <HeartPulse className="h-6 w-6" />
              </div>
              <h1 className="mt-4 text-2xl font-bold tracking-tight">{title}</h1>
              <p className="mt-1.5 text-sm text-muted-foreground">{subtitle}</p>
            </div>

            {children}
          </div>

          <div className="mt-5 text-center text-sm text-muted-foreground">{footer}</div>
        </main>
      </div>
    </div>
  );
}

/** 输入框左侧图标（绝对定位，配合 pl-10 使用）。 */
export function FieldIcon({ icon }: { icon: ReactNode }): ReactElement {
  return (
    <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground">
      {icon}
    </span>
  );
}

/** 错误/成功提示条（带图标，圆角）。 */
export function FormBanner({
  kind,
  text,
  icon,
}: {
  kind: "error" | "success";
  text: string;
  icon: ReactNode;
}): ReactElement {
  return (
    <div
      className={`flex items-start gap-2 rounded-xl p-3 text-sm ${
        kind === "error"
          ? "bg-destructive/10 text-destructive"
          : "bg-emerald-500/10 text-emerald-600"
      }`}
    >
      <span className="mt-0.5 shrink-0">{icon}</span>
      <span>{text}</span>
    </div>
  );
}

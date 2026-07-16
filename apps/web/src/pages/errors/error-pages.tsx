import { Link, isRouteErrorResponse, useRouteError } from "react-router";
import { FileQuestion, ShieldX, TriangleAlert } from "lucide-react";
import { Button } from "@/shared/ui";

function ErrorShell({
  icon,
  code,
  title,
  description,
  children,
}: {
  icon: React.ReactNode;
  code: string;
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-page px-6 text-center">
      <div className="flex size-16 items-center justify-center rounded-full bg-surface-2 text-ink-muted">{icon}</div>
      <p className="text-sm font-medium text-ink-muted">{code}</p>
      <h1 className="text-xl font-semibold text-ink-1">{title}</h1>
      <p className="max-w-md text-sm leading-6 text-ink-2">{description}</p>
      <div className="mt-2 flex items-center gap-3">{children}</div>
    </div>
  );
}

export function NotFoundPage() {
  return (
    <ErrorShell
      icon={<FileQuestion className="size-8" aria-hidden />}
      code="404"
      title="页面不存在"
      description="你访问的地址不存在或已被移动。请检查链接，或回到工作台继续。"
    >
      <Button asChild>
        <Link to="/app">回到工作台</Link>
      </Button>
    </ErrorShell>
  );
}

export function ForbiddenPage() {
  return (
    <ErrorShell
      icon={<ShieldX className="size-8" aria-hidden />}
      code="403"
      title="没有访问权限"
      description="当前账号没有访问该页面的权限。如需开通，请联系系统管理员。"
    >
      <Button asChild>
        <Link to="/app">回到工作台</Link>
      </Button>
    </ErrorShell>
  );
}

/** 路由级兜底错误页（渲染异常等）。 */
export function SystemErrorPage() {
  const error = useRouteError();
  const detail = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : error instanceof Error
      ? error.message
      : "未知错误";
  return (
    <ErrorShell
      icon={<TriangleAlert className="size-8" aria-hidden />}
      code="系统错误"
      title="页面出现了问题"
      description={`系统发生了意外错误，请刷新重试；问题持续请联系管理员。（${detail}）`}
    >
      <Button onClick={() => window.location.reload()}>刷新页面</Button>
      <Button variant="secondary" asChild>
        <Link to="/app">回到工作台</Link>
      </Button>
    </ErrorShell>
  );
}

import { Home } from "lucide-react";
import { Link } from "react-router-dom";
import { buttonVariants } from "@/shared/ui/Button";

export function NotFoundPage() {
  return (
    <div className="grid min-h-screen place-items-center bg-[var(--sh-surface-canvas)] p-6">
      <div className="text-center">
        <p className="text-sm font-semibold text-[var(--sh-brand-600)]">页面未找到</p>
        <h1 className="mt-2 text-3xl font-bold text-[var(--sh-ink-strong)]">
          这里没有正在制作的内容
        </h1>
        <p className="mt-3 text-[var(--sh-ink-muted)]">检查链接，或回到首页继续创作。</p>
        <Link className={`${buttonVariants()} mt-6`} to="/app">
          <Home aria-hidden="true" />
          回到首页
        </Link>
      </div>
    </div>
  );
}

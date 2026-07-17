import { Link } from "react-router";
import { Compass } from "lucide-react";
import { Button } from "@/shared/ui";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center gap-4 px-6 text-center">
      <Compass className="size-12 text-ink-faint" aria-hidden />
      <div>
        <h1 className="text-xl font-semibold text-ink-strong">页面不存在</h1>
        <p className="mt-1 text-sm text-ink-muted">链接可能已失效，或页面已被移动。</p>
      </div>
      <Button asChild>
        <Link to="/app">回到首页</Link>
      </Button>
    </div>
  );
}

import { creationPptContentAssets, creationPptCoverAssets } from "@/assets/creation/catalog";

type DemoSlide = {
  alt: string;
  eyebrow: string;
  source: string;
  subtitle: string;
  title: string;
};

const coverSlides: DemoSlide[] = [
  {
    alt: "百格光窗与果汁标签组成的百分数课件封面",
    eyebrow: "六年级数学",
    source: creationPptCoverAssets[0],
    subtitle: "从生活中的数据，看见整体与部分",
    title: "认识百分数",
  },
  {
    alt: "暖光桌面上的三瓶果汁组成的百分数课件封面",
    eyebrow: "生活里的数学",
    source: creationPptCoverAssets[1],
    subtitle: "读懂标签，也读懂部分与整体",
    title: "标签里的百分数",
  },
  {
    alt: "师生围绕果汁标签讨论的百分数课件封面",
    eyebrow: "课堂观察",
    source: creationPptCoverAssets[2],
    subtitle: "先发现问题，再把判断带回课堂",
    title: "百分数侦探课",
  },
];

const contentSlides: DemoSlide[] = [
  {
    alt: "学生观察三瓶果汁标签的课堂情境图",
    eyebrow: "生活观察",
    source: creationPptContentAssets[0],
    subtitle: "标签里的部分和整体要一起看",
    title: "先找完整信息",
  },
  {
    alt: "百格图中涂出百分之三十七的课堂示意图",
    eyebrow: "可视化理解",
    source: creationPptContentAssets[1],
    subtitle: "涂色格表示整体中的 37 份",
    title: "37% 在哪里",
  },
  {
    alt: "学生在黑板前交流百分数判断理由的课堂图",
    eyebrow: "课堂交流",
    source: creationPptContentAssets[2],
    subtitle: "先观察，再用一句话解释自己的判断",
    title: "说出判断理由",
  },
];

function at<T>(items: T[], index: number) {
  const safeIndex = ((index % items.length) + items.length) % items.length;
  return items[safeIndex] as T;
}

function DemoCover({ slide }: { slide: DemoSlide }) {
  return (
    <div className="relative size-full bg-[var(--sh-artifact-paper)]">
      <img
        alt=""
        aria-hidden="true"
        className="absolute inset-0 size-full object-cover"
        decoding="async"
        src={slide.source}
      />
      <div className="absolute inset-0 bg-gradient-to-r from-[var(--sh-artifact-paper)] via-[var(--sh-artifact-paper)]/90 to-transparent" />
      <div className="relative flex size-full max-w-[56%] flex-col justify-center px-[7%] text-[var(--sh-artifact-ink)]">
        <p className="text-[clamp(0.45rem,3cqw,0.78rem)] font-semibold text-[var(--sh-art-green)]">
          {slide.eyebrow}
        </p>
        <p className="mt-[4%] text-[clamp(0.8rem,8.5cqw,2.15rem)] font-bold leading-tight">
          {slide.title}
        </p>
        <p className="mt-[4%] max-w-[28rem] text-[clamp(0.42rem,3cqw,0.82rem)] leading-relaxed text-[var(--sh-artifact-muted)]">
          {slide.subtitle}
        </p>
      </div>
    </div>
  );
}

function DemoContent({ slide }: { slide: DemoSlide }) {
  return (
    <div className="relative size-full bg-[var(--sh-artifact-paper)] text-[var(--sh-artifact-ink)]">
      <div className="relative z-10 flex h-full w-[38%] flex-col justify-center pl-[6%] pr-[3%]">
        <p className="text-[clamp(0.42rem,2.8cqw,0.76rem)] font-semibold text-[var(--sh-art-green)]">
          {slide.eyebrow}
        </p>
        <p className="mt-[5%] text-[clamp(0.72rem,7.2cqw,1.85rem)] font-bold leading-tight">
          {slide.title}
        </p>
        <p className="mt-[6%] text-[clamp(0.4rem,2.6cqw,0.74rem)] leading-relaxed text-[var(--sh-artifact-muted)]">
          {slide.subtitle}
        </p>
        <span className="mt-[8%] h-1 w-[34%] rounded-full bg-[var(--sh-art-gold)]" />
      </div>
      <div className="absolute inset-y-[10%] right-[4%] w-[60%] overflow-hidden rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] shadow-[var(--sh-shadow-card)]">
        <img
          alt=""
          aria-hidden="true"
          className="size-full object-cover"
          decoding="async"
          src={slide.source}
        />
      </div>
    </div>
  );
}

export function PercentSlidePreview({
  compact = false,
  page,
  topic,
  variant = 0,
}: {
  compact?: boolean;
  page?: number;
  topic?: string;
  variant?: number;
}) {
  const isCover = page === undefined || page === 0;
  const slide = isCover
    ? at(coverSlides, variant)
    : at(contentSlides, Math.max(0, page - 1) + variant);

  return (
    <div
      aria-label={topic ? `${topic}课堂课件页面预览` : slide.alt}
      className={`relative aspect-video overflow-hidden rounded-[var(--sh-radius-sm)] bg-[var(--sh-artifact-paper)] shadow-[var(--sh-shadow-card)] [container-type:inline-size] ${compact ? "ring-1 ring-[var(--sh-line-subtle)]" : ""}`}
      role="img"
    >
      {topic ? (
        <div className="flex size-full flex-col justify-center bg-[var(--sh-artifact-paper)] px-[10%] text-[var(--sh-artifact-ink)]">
          <p className="text-xs font-semibold text-[var(--sh-art-green)]">小学数学课堂</p>
          <p className="mt-[3%] text-[clamp(0.8rem,8.5cqw,2.3rem)] font-bold leading-tight">
            {topic}
          </p>
          <div className="mt-5 grid grid-cols-6 gap-1">
            {Array.from({ length: 18 }, (_, index) => (
              <span
                className={`aspect-square rounded-sm ${index < 9 ? "bg-[var(--sh-art-gold)]" : "bg-[var(--sh-art-paper-green)]"}`}
                key={index}
              />
            ))}
          </div>
        </div>
      ) : isCover ? (
        <DemoCover slide={slide} />
      ) : (
        <DemoContent slide={slide} />
      )}
    </div>
  );
}

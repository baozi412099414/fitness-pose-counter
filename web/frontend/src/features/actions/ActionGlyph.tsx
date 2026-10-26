import { cn } from "@/lib/cn";

/**
 * 动作线稿图标（1.5px 荧光绿线 + 抽象姿态，不用照片）。
 * 按动作 id 映射到三款内置姿态，未知动作回退到通用站姿。
 */

type Variant = "squat" | "pushup" | "jumping_jack" | "unknown";

function variantOf(id: string): Variant {
  switch (id) {
    case "squat":
      return "squat";
    case "pushup":
      return "pushup";
    case "jumping_jack":
      return "jumping_jack";
    default:
      return "unknown";
  }
}

const stroke = "rgb(var(--accent-rgb))";

export interface ActionGlyphProps {
  actionId: string;
  size?: number;
  className?: string;
}

export function ActionGlyph({ actionId, size = 32, className }: ActionGlyphProps) {
  const variant = variantOf(actionId);
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={stroke}
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("shrink-0", className)}
      aria-hidden="true"
    >
      {variant === "squat" && (
        <>
          <circle cx="12" cy="4" r="2.3" />
          <path d="M12 6.5 10 11" />
          <path d="M10 11 8 8" />
          <path d="M10 11 6 10" />
          <path d="M10 11 11 15" />
          <path d="M11 15 8 17.5" />
          <path d="M11 15 4.5 15.5" />
        </>
      )}
      {variant === "pushup" && (
        <>
          <circle cx="8" cy="8" r="2.3" />
          <path d="M10 9 14 11.5" />
          <path d="M14 11.5 21 13" />
          <path d="M14 11.5 15 19" />
          <path d="M15 19 19 20" />
          <path d="M10 9 6 18" />
          <path d="M6 18 3 19.5" />
        </>
      )}
      {variant === "jumping_jack" && (
        <>
          <circle cx="12" cy="5" r="2.3" />
          <path d="M12 7.5V12" />
          <path d="M12 9.5 5 4" />
          <path d="M12 9.5 19 4" />
          <path d="M12 12 5 20" />
          <path d="M12 12 19 20" />
        </>
      )}
      {variant === "unknown" && (
        <>
          <circle cx="12" cy="5" r="2.5" />
          <path d="M12 7.5V14" />
          <path d="M12 10l-4-1.5" />
          <path d="M12 10l4-1.5" />
          <path d="M12 14l-4 4" />
          <path d="M12 14l4 4" />
        </>
      )}
    </svg>
  );
}
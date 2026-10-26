import type { Grade } from "@/lib/types";

/** 与桌面版 QualityChecker.grade 一致：<60 待改进、60 及格、75 良好、90 优秀 */
export function gradeOf(score: number | null | undefined): Grade | null {
  if (score == null || Number.isNaN(score)) return null;
  if (score >= 90) return "优秀";
  if (score >= 75) return "良好";
  if (score >= 60) return "及格";
  return "待改进";
}

export function gradeTone(
  grade: Grade | null,
): "mint" | "cyan" | "amber" | "coral" | "neutral" {
  switch (grade) {
    case "优秀":
      return "mint";
    case "良好":
      return "cyan";
    case "及格":
      return "amber";
    case "待改进":
      return "coral";
    default:
      return "neutral";
  }
}

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m} 分 ${s} 秒` : `${s} 秒`;
}

import type {
  ActionKey,
  LoadedSample,
  SampleMeta,
  TrainCheckState,
} from "./types";

export const ACTION_META: Record<
  ActionKey,
  { name: string; down: string; up: string; hint: string }
> = {
  squat: {
    name: "深蹲",
    down: "下蹲",
    up: "起身",
    hint: "大腿平行地面，膝盖对齐脚尖",
  },
  pushup: {
    name: "俯卧撑",
    down: "下压",
    up: "撑起",
    hint: "头肩髋踝保持一条直线",
  },
  jumping_jack: {
    name: "开合跳",
    down: "打开",
    up: "收回",
    hint: "手举过头，双脚张开约两倍肩宽",
  },
};

export const SAMPLES: SampleMeta[] = [
  {
    id: "squat_standard",
    file: "squat_standard.json",
    action: "squat",
    caseLabel: "标准深蹲",
    count: 3,
    score: 78.2,
    errors: [],
  },
  {
    id: "squat_shallow",
    file: "squat_shallow.json",
    action: "squat",
    caseLabel: "蹲得不够深",
    count: 3,
    score: 47.3,
    errors: ["蹲得不够深", "右腿下蹲幅度不足", "站起时腿没伸直"],
  },
  {
    id: "squat_knee_fwd",
    file: "squat_knee_fwd.json",
    action: "squat",
    caseLabel: "膝盖前移",
    count: 3,
    score: 54.6,
    errors: ["小腿前倾太多", "膝盖明显前移了"],
  },
  {
    id: "squat_minimal",
    file: "squat_minimal.json",
    action: "squat",
    caseLabel: "最简 3 点数据",
    count: 3,
    score: 75.8,
    errors: [],
  },
  {
    id: "pushup_standard",
    file: "pushup_standard.json",
    action: "pushup",
    caseLabel: "标准俯卧撑",
    count: 3,
    score: 88.3,
    errors: [],
  },
  {
    id: "pushup_sag",
    file: "pushup_sag.json",
    action: "pushup",
    caseLabel: "塌腰",
    count: 3,
    score: 64.3,
    errors: ["收紧核心，头肩髋踝保持一条直线"],
  },
  {
    id: "jack_standard",
    file: "jack_standard.json",
    action: "jumping_jack",
    caseLabel: "标准开合跳",
    count: 3,
    score: 100,
    errors: [],
  },
  {
    id: "jack_low_hands",
    file: "jack_low_hands.json",
    action: "jumping_jack",
    caseLabel: "手没举过头",
    count: 3,
    score: 48,
    errors: ["左手再举高一点", "右手再举高一点"],
  },
];

export const DEFAULT_SAMPLE: Record<ActionKey, string> = {
  squat: "squat_standard",
  pushup: "pushup_standard",
  jumping_jack: "jack_standard",
};

const ACTION_CHECKS: Record<
  ActionKey,
  { key: string; label: string }[]
> = {
  squat: [
    { key: "depth", label: "下蹲深度" },
    { key: "knee", label: "膝盖方向" },
    { key: "straight", label: "起身伸直" },
  ],
  pushup: [
    { key: "depth", label: "下压深度" },
    { key: "core", label: "核心稳定" },
    { key: "straight", label: "手臂伸直" },
  ],
  jumping_jack: [
    { key: "hands", label: "手举过头" },
    { key: "feet", label: "双脚张开" },
    { key: "sync", label: "左右同步" },
  ],
};

const SAMPLE_FAILS: Record<string, string[]> = {
  squat_shallow: ["depth", "straight"],
  squat_knee_fwd: ["knee"],
  pushup_sag: ["core"],
  jack_low_hands: ["hands"],
};

export function checksForSample(sample: SampleMeta): TrainCheckState[] {
  // 最简 3 点数据只够判深度，用来演示「缺关键点则少判几条」
  if (sample.id === "squat_minimal") {
    return [{ key: "depth", label: "下蹲深度", ok: true }];
  }
  const fails = new Set(SAMPLE_FAILS[sample.id] ?? []);
  return ACTION_CHECKS[sample.action].map((check) => ({
    ...check,
    ok: !fails.has(check.key),
  }));
}

export function isActionKey(value: string | undefined): value is ActionKey {
  return (
    value === "squat" ||
    value === "pushup" ||
    value === "jumping_jack"
  );
}

interface RawSample {
  fps?: number;
  points: number[];
  frames: [number, number][][];
}

/** 读取 samples/*.json，归一化到 0..1 并居中（保持比例） */
export async function loadSample(sample: SampleMeta): Promise<LoadedSample> {
  const res = await fetch(`/samples/${sample.file}`);
  if (!res.ok) throw new Error(`sample ${sample.file} not found`);
  const raw = (await res.json()) as RawSample;
  if (!raw.frames?.length || !raw.points?.length) {
    throw new Error(`sample ${sample.file} is empty`);
  }

  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const frame of raw.frames) {
    for (const [x, y] of frame) {
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    }
  }

  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const size = Math.max(1, maxX - minX, maxY - minY);
  const pad = 0.86;

  const frames = raw.frames.map((frame) =>
    frame.map(([x, y], i) => ({
      index: raw.points[i],
      x: 0.5 + ((x - cx) / size) * pad,
      y: 0.5 + ((y - cy) / size) * pad,
    })),
  );

  const fps = raw.fps && raw.fps > 0 ? raw.fps : 30;
  return {
    id: sample.id,
    fps,
    duration: Math.max(1, frames.length / fps),
    frames,
  };
}

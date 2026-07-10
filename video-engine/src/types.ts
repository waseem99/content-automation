export type Objective = "engagement" | "compliance" | "monetization";

export type VisualVariant =
  | "hook"
  | "swarm"
  | "bridge"
  | "traffic"
  | "reveal"
  | "cta";

export type SafetyLevel = "safe" | "sensitive" | "graphic" | "prohibited";

export interface BrandProfile {
  id: string;
  name: string;
  tagline: string;
  primaryColor: string;
  secondaryColor: string;
  backgroundColor: string;
  captionColor: string;
  watermark: string;
  tone: string;
  voiceStyle: string;
}

export interface CaptionChunk {
  startSec: number;
  endSec: number;
  text: string;
  highlight?: string;
  emphasis?: "neutral" | "danger" | "positive" | "fact";
}

export interface StoryScene {
  id: string;
  startSec: number;
  endSec: number;
  headline: string;
  body: string;
  visual: VisualVariant;
  accent?: string;
  safetyLevel: SafetyLevel;
  objectives: Objective[];
}

export interface EditorialSource {
  title: string;
  publisher?: string;
  url?: string;
  status: "verified" | "needs_verification";
}

export interface RenderSettings {
  width: number;
  height: number;
  fps: number;
  codec: "h264";
  durationSeconds: number;
}

export interface VideoProject {
  schemaVersion: "p65.video_project.v1";
  id: string;
  title: string;
  brand: BrandProfile;
  format: "vertical_short";
  narration: string;
  scenes: StoryScene[];
  captions: CaptionChunk[];
  sources: EditorialSource[];
  render: RenderSettings;
  voiceoverFile?: string;
  disclosure: string;
  callToAction: string;
  humanReviewRequired: true;
  editorialStatus: "demo_only_not_approved" | "ready_for_human_review" | "approved";
}

export interface VideoInputProps {
  project: VideoProject;
}

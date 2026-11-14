/** EduNest 2.0 API types + tiny helpers shared by the new pages. */
import type { Reward } from "@/components/fun/Celebrate";

export interface Badge { id: string; emoji: string; earned: boolean; at: string | null }
export interface World { id: string; emoji: string; xp: number; stage: number; stages: number; next_at: number | null }
export interface Quest { id: string; kind: string; target: number; progress: number; xp: number; coins: number; emoji: string; done: boolean; claimed: boolean }
export interface ShopItem { id: string; emoji: string; cost: number; owned: boolean }
export interface GameProfile {
  student_id: number; name: string; xp: number; coins: number;
  level: { level: number; key: string; xp_in_level: number; xp_for_next: number | null; next_at: number | null };
  streak: { current: number; best: number; freezes: number; today: boolean };
  badges: Badge[]; worlds: World[]; team: string; avatar: { hat?: string; color?: string; pet?: string }; leaderboard_opt_in: boolean;
  quests?: Quest[]; checked_in?: boolean; mystery_done?: boolean; week?: { day: string; xp: number }[];
  recent?: { kind: string; xp: number; coins: number; day: string; world: string }[]; shop?: ShopItem[];
}
export interface Puzzle { skill: string; emoji: string; difficulty: number; question: string; options: string[]; token: string; show?: string[]; seconds?: number }
export interface AnswerOut { correct: boolean; answer: number; explanation: string; reward: Reward | null }
export interface SkillScore { score: number; attempts: number; accuracy: number; level: number; trend: number }
export interface Scores { student_id: number; label: string; overall: number; skills: Record<string, SkillScore>; recommend: string; emoji: Record<string, string>; history: { week: string; accuracy: number }[] }
export interface PracticeQ { q: string; o: string[]; a: number; e: string; topic?: string }
export interface Source { name: string; snippet: string; resource_id?: number; chapter?: number; document_id?: number }
export interface TopicOut { title: string; explanation: string; example: string; points: string[]; videos: { title: string; url: string }[]; practice: PracticeQ[]; sources: Source[]; provider: string; found: boolean; reward: Reward | null }
export interface AskOut { conversation_id: number; reply: string; sources: Source[]; provider: string; mode: string; reward: Reward | null; ocr_text: string | null }
export interface SolveOut { ocr_text: string; question: string; topic: string; steps: string[]; answer: string; explanation: string; provider: string; reward: Reward | null }
export interface ChittiStatus { provider: string; online: boolean; modes: string[]; languages: string[]; consent: boolean }
export interface Resource {
  id: number; kind: string; title: string; description: string; class_id: number | null; subject_id: number | null; year: number | null; institution: string;
  has_file: boolean; content_type: string; url: string; chapter_count: number; approved: boolean; created_at: string; completed: number[];
  bookmarks: { chapter: number; note: string }[]; chapters?: { title: string; text: string }[];
}
export interface Announcement { id: number; title: string; body: string; audience: string; section_id: number | null; pinned: boolean; emoji: string; author: string; created_at: string }
export interface Contact { user_id: number; name: string; role: string; unread: number; about: string }
export interface Dm { id: number; mine: boolean; body: string; at: string; read: boolean }
export interface ForumPostT {
  id: number; kind: string; title: string; body: string; section_id: number | null; subject_id: number | null; solved: boolean; hidden: boolean; likes: number; liked: boolean;
  author: string; author_role: string; mine: boolean; replies_count: number; created_at: string; can_moderate: boolean;
  replies?: { id: number; body: string; accepted: boolean; hidden: boolean; author: string; author_role: string; mine: boolean; created_at: string }[];
}
export interface Thread { id: number; topic: string; anonymous: boolean; status: string; student: string | null; created_at: string; messages: { id: number; from_staff: boolean; body: string; at: string }[] }
export interface ProjectT { id: number; title: string; summary: string; category: string; status: string; emoji: string; max_members: number; members: { user_id: number; name: string }[]; owner: string; mine: boolean; joined: boolean; created_at: string; comments?: { id: number; body: string; author: string; role: string; at: string }[] }
export interface PortfolioT { id: number; kind: string; title: string; details: string; achieved_on: string | null; has_file: boolean; content_type: string; created_at: string }
export interface Stop { name: string; lat: number; lng: number; minute: number; eta_min?: number; passed?: boolean }
export interface Live { vehicle: { id: number; number: string; driver_name: string; driver_phone: string; capacity: number; route_id: number }; route: { id: number; name: string; start_time: string; stops: Stop[] };
  position: { lat: number; lng: number; speed_kmh: number }; state: string; simulated: boolean; stops: Stop[]; updated_at: string }
export interface Pattern { key: string; params: Record<string, string | number>; action: string; severity: "high" | "medium" | "good" }

export const fmtDate = (s: string | null | undefined, lang: string) => (s ? new Date(s).toLocaleDateString(lang, { day: "numeric", month: "short" }) : "—");
export const fmtTime = (s: string, lang: string) => new Date(s).toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" });
export const pctText = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${Math.round(v)}%`);
